from __future__ import annotations

import operator
from functools import reduce

from django.db.models import Case, CharField, Q, Value, When
from django.utils import timezone

from neuxo_backend.models import (
    CompanyFunding,
    EventsList,
    GuestList,
    LinkedinCompany,
    LinkedinJob,
    LinkedinPersonalEmail,
    Notification,
)
from users.models import UserWatchList


def get_watchlist_data(request):
    """
    Get paginated watchlist for the current user.
    Returns tuple of (paginator_info, response_data).
    """
    user_id = request.user.get("id", None)
    if not user_id:
        return {"page": 1, "limit": 10, "total_page": 0, "total_item": 0}, []

    # Get parameters
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 50))
    search_key = request.GET.get("search_key", None)
    company_size = request.GET.get("company_size", None)
    followers = request.GET.get("followers", None)
    country = request.GET.get("country", None)

    if page < 1:
        page = 1
    if limit < 1 or limit > 200:
        limit = 50

    # Get user's watchlist
    watchlist = UserWatchList.objects.filter(user_id=user_id).select_related("company")

    # Apply search filter
    if search_key:
        watchlist = watchlist.filter(company__name__icontains=search_key)

    # Apply company size filter
    if company_size:
        sizes = company_size.split(",")
        watchlist = watchlist.filter(company__size__in=sizes)

    # Apply country filter
    if country:
        countries = country.split(",")
        watchlist = watchlist.filter(company__country__in=countries)

    # Apply followers filter
    if followers:
        lst_followers = followers.split(",")
        follower_conditions = []

        for follower in lst_followers:
            if follower == "1000001+":
                follower_conditions.append(Q(company__followers__gte=1000001))
            else:
                try:
                    follower_range = list(map(int, follower.split("-")))
                    follower_conditions.append(
                        Q(company__followers__gte=follower_range[0])
                        & Q(company__followers__lte=follower_range[1])
                    )
                except (ValueError, IndexError):
                    continue

        if follower_conditions:
            follower_filters = reduce(operator.or_, follower_conditions)
            watchlist = watchlist.filter(follower_filters)

    # Order by PIN time first, then created_at
    watchlist = watchlist.order_by(
        Case(
            When(time_PIN__isnull=False, then=Value(0)),
            default=Value(1),
            output_field=CharField(),
        ),
        "-time_PIN",
        "-created_at",
    )

    # Get total count
    total_count = watchlist.count()

    # Paginate
    offset = (page - 1) * limit
    watchlist_page = watchlist[offset : offset + limit]

    # Build response data
    response_data = []
    for item in watchlist_page:
        company = item.company
        if not company:
            continue

        # Get contact count
        contact_count = LinkedinPersonalEmail.objects.filter(
            company_id=company.id
        ).count()

        # Get recent trigger data
        triggers = _get_company_triggers(company)

        company_data = {
            "watchlist_id": str(item.id),
            "company_id": str(company.id),
            "company_name": company.name,
            "avatar_url": company.avatar_url,
            "linkedin_url": company.linkedin_url,
            "website": company.website,
            "twitter_url": company.link_twitter,
            "size": company.size,
            "industry": company.industry,
            "country": company.country,
            "category": company.category,
            "short_description": company.short_description,
            "followers": company.followers,
            "note": item.note,
            "time_PIN": (
                item.time_PIN.strftime("%Y-%m-%d %H:%M:%S") if item.time_PIN else None
            ),
            "is_pinned": item.time_PIN is not None,
            "created_at": item.created_at.strftime("%Y-%m-%d"),
            "contact_count": contact_count,
            "triggers": triggers,
        }
        response_data.append(company_data)

    # Build pagination info
    total_pages = (total_count + limit - 1) // limit
    paginator = {
        "page": page,
        "limit": limit,
        "total_page": total_pages,
        "total_item": total_count,
    }

    return paginator, response_data


def _get_company_triggers(company) -> list:
    """Get trigger types for a company."""
    triggers = []

    # Check for recent funding
    if CompanyFunding.objects.filter(company=company).exists():
        triggers.append("funding")

    # Check for recent jobs/hiring
    if LinkedinJob.objects.filter(company=company).exclude(status="removed").exists():
        triggers.append("hiring")

    # Check for events
    guest_event_ids = GuestList.objects.filter(company=company).values_list(
        "event_id", flat=True
    )
    if EventsList.objects.filter(id__in=guest_event_ids).exists():
        triggers.append("event")

    return triggers


def add_company_to_watchlist(user_id: int, company_id: str) -> tuple[bool, str]:
    """
    Add a company to user's watchlist.
    Returns tuple of (success, message).
    """
    # Check watchlist limit
    count_watchlist = UserWatchList.objects.filter(user_id=user_id).count()
    if count_watchlist >= 200:
        return False, "You can only watch 200 companies"

    # Check if already in watchlist
    existing = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()
    if existing:
        return False, "Company already in watchlist"

    # Check if company exists
    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return False, "Company not found"

    # Create watchlist entry
    UserWatchList.objects.create(user_id=user_id, company_id=company_id)

    return True, "Success"


def remove_company_from_watchlist(user_id: int, company_ids: str) -> tuple[bool, str]:
    """
    Remove companies from user's watchlist.
    Returns tuple of (success, message).
    """
    if not company_ids:
        return False, "Company ids are required"

    ids = company_ids.split(",")

    for company_id in ids:
        company_id = company_id.strip()
        watchlist_item = UserWatchList.objects.filter(
            user_id=user_id, company_id=company_id
        ).first()

        if not watchlist_item:
            return False, f"Company {company_id} not on watchlist"

        watchlist_item.delete()

    return True, "Success"


def pin_watchlist_company(
    user_id: int, company_id: str, is_pin: bool
) -> tuple[bool, str]:
    """
    PIN or unPIN a company in watchlist.
    Returns tuple of (success, message).
    """
    watchlist_item = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()

    if not watchlist_item:
        return False, "Company not in watchlist"

    if is_pin:
        watchlist_item.time_PIN = timezone.now()
    else:
        watchlist_item.time_PIN = None

    watchlist_item.save()

    return True, "Success"


def edit_note_for_company(user_id: int, company_id: str, note: str) -> tuple[bool, str]:
    """
    Edit note for a company in watchlist.
    Returns tuple of (success, message).
    """
    watchlist_item = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()

    if not watchlist_item:
        return False, "Company not in watchlist"

    watchlist_item.note = note
    watchlist_item.updated_at = timezone.now()
    watchlist_item.save()

    return True, "Success"


def get_detail_info_for_company(company_id: str) -> dict | None:
    """Get detailed information for a company."""
    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return None

    # Get contacts
    contacts = LinkedinPersonalEmail.objects.filter(company_id=company_id).values(
        "id",
        "first_name",
        "last_name",
        "email",
        "role",
        "linkedin_url",
        "twitter_url",
        "avatar_linkedin_url",
    )

    contacts_list = []
    for contact in contacts:
        first = contact.get("first_name") or ""
        last = contact.get("last_name") or ""
        name = (first + " " + last).strip() if first != last else last

        contacts_list.append(
            {
                **contact,
                "name": name,
            }
        )

    # Get funding data
    fundings = CompanyFunding.objects.filter(linkedin_url=company.linkedin_url).values(
        "name", "date", "amount", "category", "round"
    )
    funding_list = []
    for f in fundings:
        f["date"] = f["date"].strftime("%Y-%m-%d") if f.get("date") else ""
        funding_list.append(f)

    # Get recent jobs
    jobs = (
        LinkedinJob.objects.filter(company=company)
        .exclude(status="removed")
        .values("title", "linkedin_url", "created_at")
        .order_by("-created_at")[:10]
    )
    jobs_list = []
    for j in jobs:
        j["created_at"] = (
            j["created_at"].strftime("%Y-%m-%d") if j.get("created_at") else ""
        )
        jobs_list.append(j)

    # Get events
    guest_event_ids = GuestList.objects.filter(company=company).values_list(
        "event_id", flat=True
    )
    events = EventsList.objects.filter(id__in=guest_event_ids).values(
        "name", "event_url", "start_date"
    )
    events_list = []
    for e in events:
        e["event_url"] = "https://lu.ma/" + e["event_url"] if e.get("event_url") else ""
        e["start_date"] = (
            e["start_date"].strftime("%Y-%m-%d") if e.get("start_date") else ""
        )
        events_list.append(e)

    return {
        "company_id": str(company.id),
        "name": company.name,
        "avatar_url": company.avatar_url,
        "linkedin_url": company.linkedin_url,
        "website": company.website,
        "twitter_url": company.link_twitter,
        "size": company.size,
        "industry": company.industry,
        "country": company.country,
        "category": company.category,
        "short_description": company.short_description,
        "description": company.description,
        "followers": company.followers,
        "headquarters": company.headquarters,
        "organization_type": company.organization_type,
        "contacts": contacts_list,
        "fundings": funding_list,
        "jobs": jobs_list,
        "events": events_list,
    }


def get_all_notify_for_user(user_id: int) -> list:
    """Get all notifications for companies in user's watchlist."""
    # Get company IDs from user's watchlist
    watchlist_company_ids = UserWatchList.objects.filter(user_id=user_id).values_list(
        "company_id", flat=True
    )

    # Get notifications for those companies
    notifications = (
        Notification.objects.filter(company_id__in=watchlist_company_ids)
        .select_related("company")
        .order_by("-created_at")[:100]
    )

    result = []
    for notif in notifications:
        result.append(
            {
                "id": str(notif.id),
                "type": notif.type,
                "title": notif.title,
                "post_url": notif.post_url,
                "time_post": (
                    notif.time_post.strftime("%Y-%m-%d %H:%M:%S")
                    if notif.time_post
                    else ""
                ),
                "company_id": str(notif.company_id) if notif.company_id else "",
                "company_name": notif.company.name if notif.company else "",
                "is_send": notif.is_send,
                "created_at": notif.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    return result


def new_notify_today(company_id: str) -> int:
    """Get count of new notifications for a company today."""
    today = timezone.now().date()
    count = Notification.objects.filter(
        company_id=company_id, created_at__date=today
    ).count()
    return count
