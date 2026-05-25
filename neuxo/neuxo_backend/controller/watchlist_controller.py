from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Case, F, JSONField, Q, Value, When
from django.db.models.query import QuerySet
from django.utils import timezone

from neuxo_backend.models import (
    CompanyFunding,
    EventsList,
    GuestList,
    HistoryGenAI,
    LinkedinCompany,
    LinkedinJob,
    LinkedinPersonalEmail,
    ListICP,
    MasterCompanies,
    Mentions,
    MentionsLinkedin,
    MentionsSubDomain,
    MentionsTwitter,
    NewsInformation,
    Notification,
    UserNotification,
)
from neuxo_backend.crawler.LinkedinJobServices import LinkedinJobService
from neuxo_backend.crawler.LinkedinLeadService import LinkedinLeadService
from neuxo_backend.crawler.LinkedinPostServices import LinkedinPostService
from neuxo_backend.crawler.LinkedinProfileService import LinkedinProfileService
from neuxo_backend.crawler.Subdomain import Subdomains
from users.models import UserWatchList, Users

logger = logging.getLogger(__name__)
WATCHLIST_LOG_DIR = Path(__file__).resolve().parents[2] / "log"


# ------------------------------------ Utility Functions ------------------------------------#


def getParamsVer2(request):
    """Get pagination and date parameters from request."""
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 100))
    if page < 1:
        page = 1
    if limit < 1 or limit > 200:
        limit = 10
    if start_date and len(start_date) == 10:
        start_date = start_date + " 00:00:00"
    if end_date and len(end_date) == 10:
        end_date = end_date + " 23:59:59"
    return start_date, end_date, page, limit


def calculate_profile_completeness(
    linkedin_url=False,
    link_twitter=False,
    website=False,
    size=False,
    description=False,
    followers=False,
    headquarters=False,
    industry=False,
    organization_type=False,
    category=False,
    labels=False,
    short_description=False,
    country=False,
    have_data_individual=False,
):
    """Calculate the profile completeness percentage for a company."""
    weights = {
        "linkedin_url": 20,
        "link_twitter": 10,
        "website": 10,
        "size": 5,
        "description": 5,
        "followers": 5,
        "headquarters": 5,
        "industry": 5,
        "organization_type": 5,
        "category": 5,
        "labels": 5,
        "short_description": 5,
        "country": 5,
        "have_data_individual": 10,
    }

    completeness = 0
    total_weight = 0
    missing_fields = []

    profile_data = {
        "linkedin_url": linkedin_url,
        "link_twitter": link_twitter,
        "website": website,
        "size": size,
        "description": description,
        "followers": followers,
        "headquarters": headquarters,
        "industry": industry,
        "organization_type": organization_type,
        "category": category,
        "labels": labels,
        "short_description": short_description,
        "country": country,
        "have_data_individual": have_data_individual,
    }

    for field, value in profile_data.items():
        if value:
            completeness += weights[field]
        else:
            missing_fields.append(field)
        total_weight += weights[field]

    return (completeness / total_weight) * 100, missing_fields


def getPagination(request, input_data):
    """Get paginated data from a queryset or list."""
    _, _, page, limit = getParamsVer2(request)
    if isinstance(input_data, list):
        paginator = Paginator(input_data, limit)
        try:
            output_data = paginator.page(page)
        except PageNotAnInteger:
            output_data = paginator.page(1)
        except EmptyPage:
            output_data = paginator.page(paginator.num_pages)

        paginator_info = {
            "page": output_data.number,
            "limit": output_data.paginator.per_page,
            "total_page": paginator.num_pages,
            "total_item": paginator.count,
        }
        return paginator_info, list(output_data)
    elif isinstance(input_data, QuerySet):
        total_count = input_data.count()
        paginated_queryset = input_data[(page - 1) * limit : page * limit]
        total_pages = (total_count + limit - 1) // limit
        paginator_info = {
            "page": page,
            "limit": limit,
            "total_page": total_pages,
            "total_item": total_count,
        }
        return paginator_info, paginated_queryset


def getTriggerDataByCompanyId(id):
    """Get trigger data (funding, hiring, events, news, contacts) for a company."""
    company = LinkedinCompany.objects.filter(id=id).first()
    if not company:
        return None

    all_data = {
        "company_information": {
            "name": company.name,
            "linkedin_url": company.linkedin_url,
            "website": company.website,
            "size": company.size,
            "industry": company.industry,
            "organization_type": company.organization_type,
            "headquarters": company.headquarters,
            "followers": company.followers,
            "category": [company.category],
            "short_description": company.short_description,
            "label": company.labels,
            "link_twitter": company.link_twitter,
            "country": company.country,
            "avatar_linkedin_url": company.avatar_url,
            "is_blacklist": company.is_blacklist,
        },
        "funding": [],
        "hiring": [],
        "event": [],
        "news": [],
        "contacts": [],
    }

    # Funding
    funding_data = CompanyFunding.objects.filter(
        linkedin_url=company.linkedin_url
    ).values("name", "date", "amount", "category", "project_url")
    funding_seen = set()
    for item in funding_data:
        item["date"] = item["date"].strftime("%Y-%m-%d") if item["date"] else ""
        key = (
            item["name"],
            item["date"],
            item["amount"],
            item["category"],
            item["project_url"],
        )
        if key not in funding_seen:
            funding_seen.add(key)
            all_data["funding"].append(item)

    # Hiring
    hiring_data = (
        LinkedinJob.objects.filter(company=company)
        .exclude(status="removed")
        .values("title", "category__name", "linkedin_url", "label__name", "created_at")
        .order_by("-created_at")
    )
    hiring_seen = set()
    for item in hiring_data:
        item["created_at"] = (
            item["created_at"].strftime("%Y-%m-%d") if item["created_at"] else ""
        )
        key = (item["title"], item["linkedin_url"])
        if key not in hiring_seen:
            hiring_seen.add(key)
            all_data["hiring"].append(item)

    # Events
    event_ids = GuestList.objects.filter(company=company).values_list(
        "event__id", flat=True
    )
    event_data = (
        EventsList.objects.filter(id__in=event_ids)
        .values("name", "event_url", "start_date")
        .order_by("-start_date")
    )
    event_seen = set()
    for item in event_data:
        item["event_url"] = (
            "https://lu.ma/" + item["event_url"] if item["event_url"] else ""
        )
        item["start_date"] = (
            item["start_date"].strftime("%Y-%m-%d") if item["start_date"] else ""
        )
        key = (item["name"], item["event_url"], item["start_date"])
        if key not in event_seen:
            event_seen.add(key)
            all_data["event"].append(item)

    # News
    news_data = (
        NewsInformation.objects.filter(company=company)
        .values("link_news", "category", "time_post", "title")
        .order_by("-time_post")
    )
    news_seen = set()
    for item in news_data:
        item["time_post"] = (
            item["time_post"].strftime("%Y-%m-%d") if item["time_post"] else ""
        )
        key = (item["link_news"], item["category"], item["time_post"], item["title"])
        if key not in news_seen:
            news_seen.add(key)
            all_data["news"].append(item)

    # Contacts
    data = LinkedinPersonalEmail.objects.filter(company__id=id).values(
        "id",
        "first_name",
        "last_name",
        "linkedin_url",
        "role",
        "twitter_url",
        "created_at",
        "avatar_linkedin_url",
    )
    for item in data:
        item["created_at"] = (
            item["created_at"].strftime("%Y-%m-%d") if item["created_at"] else ""
        )
        item["first_name"] = item["first_name"] if item["first_name"] else ""
        item["last_name"] = item["last_name"] if item["last_name"] else ""
        item["name"] = (
            item["first_name"] + " " + item["last_name"]
            if item["first_name"] != item["last_name"]
            else item["last_name"]
        )
        all_data["contacts"].append(item)

    return all_data


# ------------------------------------ Watchlist Data Functions ------------------------------------#


def get_watchlist_data(request):
    """Get watchlist data for the current user."""
    userId = request.user.get("id", None)
    search = request.GET.get("search_key", None)
    start_date, end_date, page, limit = getParamsVer2(request)
    icp_id = request.GET.get("icp_id", None)
    company_size = request.GET.get("company_size", None)
    country = request.GET.get("country", None)
    sortByVal = request.GET.get("sortByVal", None)
    orderByVal = request.GET.get("orderByVal", "DESC")

    company_watchlist = UserWatchList.objects.filter(user_id=userId).select_related(
        "company"
    )

    if start_date and end_date:
        company_watchlist = company_watchlist.filter(
            created_at__range=[start_date, end_date]
        )

    if search is not None:
        company_watchlist = company_watchlist.filter(Q(company__name__icontains=search))

    if icp_id is not None:
        list_icp_id = icp_id.split(",")
        company_watchlist = company_watchlist.filter(ICP__id__in=list_icp_id)

    if company_size:
        company_sizes = company_size.split(",")
        company_watchlist = company_watchlist.filter(company__size__in=company_sizes)

    if country:
        countries = country.split(",")
        company_watchlist = company_watchlist.filter(company__country__in=countries)

    company_watchlist = company_watchlist.annotate(
        lst_email=Case(
            When(company__lst_email_contact__isnull=True, then=Value("[]")),
            default=F("company__lst_email_contact"),
            output_field=JSONField(),
        )
    )

    company_watchlist = company_watchlist.values(
        "id",
        "company_id",
        "note",
        "company__name",
        "company__website",
        "company__industry",
        "company__size",
        "company__followers",
        "company__short_description",
        "company__linkedin_url",
        "company__labels",
        "company__category",
        "company__organization_type",
        "company__headquarters",
        "company__country",
        "created_at",
        "company__updated_at",
        "company__note_of_user",
        "company__link_twitter",
        "company__description",
        "company__avatar_url",
        "time_PIN",
        "lst_email",
    )

    if not sortByVal:
        company_watchlist = company_watchlist.order_by("-time_PIN", "-created_at")

    response_data = []
    paginator, output_data = getPagination(request, company_watchlist)

    for company in output_data:
        labels = (
            ", ".join(company["company__labels"]) if company["company__labels"] else ""
        )
        trigger = (
            MasterCompanies.objects.filter(company_id=company["company_id"])
            .values("trigger", "funding_amount", "contact")
            .first()
        )
        dict_company = {
            "id": company["id"],
            "guest": list(company["lst_email"]) if company["lst_email"] else [],
            "company_id": company["company_id"],
            "note": company["note"],
            "company": company["company__name"],
            "external": {
                "hubspot": "https://app.hubspot.com/contacts/20599301/objects/0-3/views/37601064/list?globalSearchQuery="
                + company["company__name"].replace(" ", "+"),
                "linkedin": company["company__linkedin_url"],
                "website": company["company__website"],
                "twitter": company["company__link_twitter"],
            },
            "label": labels,
            "trigger": trigger["trigger"] if trigger else "",
            "created_at": company["created_at"].strftime("%Y-%m-%d"),
            "updated_at": company["company__updated_at"].strftime("%Y-%m-%d"),
            "funding_amount": (
                float(trigger["funding_amount"])
                if trigger and trigger["funding_amount"]
                else 0
            ),
            "contacts": trigger["contact"] if trigger else "",
            "company_size": company["company__size"],
            "category": [company["company__category"]],
            "followers": company["company__followers"],
            "headquarters": company["company__headquarters"],
            "country": company["company__country"],
            "organization_type": company["company__organization_type"],
            "industry": company["company__industry"],
            "short_description": company["company__short_description"],
            "avatar_url": company["company__avatar_url"],
            "lst_email": list(company["lst_email"]) if company["lst_email"] else [],
            "PIN": True if company["time_PIN"] else False,
        }
        completeness, missing_field = calculate_profile_completeness(
            linkedin_url=True if company["company__linkedin_url"] else False,
            link_twitter=True if company["company__link_twitter"] else False,
            website=True if company["company__website"] else False,
            size=True if company["company__size"] else False,
            description=True if company["company__description"] else False,
            followers=True if company["company__followers"] else False,
            headquarters=True if company["company__headquarters"] else False,
            industry=True if company["company__industry"] else False,
            organization_type=True if company["company__organization_type"] else False,
            category=True if company["company__category"] else False,
            labels=True if company["company__labels"] else False,
            short_description=True if company["company__short_description"] else False,
            country=True if company["company__country"] else False,
            have_data_individual=True if company["lst_email"] else False,
        )
        dict_company["completeness"] = completeness
        dict_company["completeness_missing"] = missing_field
        response_data.append(dict_company)

    if sortByVal == "label":
        response_data = sorted(
            response_data,
            key=lambda x: x["label"].lower(),
            reverse=True if orderByVal.upper() == "DESC" else False,
        )
    return paginator, response_data


# ------------------------------------ Add/Remove Watchlist ------------------------------------#


def _append_watchlist_pipeline_log(company_id: str, message: str) -> None:
    """Append watchlist pipeline logs to neuxo/log/<company_id>.log."""
    try:
        WATCHLIST_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = WATCHLIST_LOG_DIR / f"{company_id}.log"
        time_text = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_file.open("a", encoding="utf-8") as file_obj:
            file_obj.write(f"[{time_text}] {message}\n")
    except Exception:
        logger.exception("Failed writing watchlist log for company_id=%s", company_id)


def _run_watchlist_linkedin_pipeline(company_id: str) -> None:
    """Run LinkedIn enrichment in background for a watched company."""
    try:
        company = LinkedinCompany.objects.filter(id=company_id).first()
        if company is None:
            _append_watchlist_pipeline_log(
                company_id, "company not found, skip pipeline"
            )
            return

        company_name = (company.name or "").strip()
        company_website = (company.website or "").strip()
        company_linkedin_url = (company.linkedin_url or "").strip()

        leads_service = LinkedinLeadService()
        profile_service = LinkedinProfileService()
        post_service = LinkedinPostService()
        job_service = LinkedinJobService()
        sub_domain = Subdomains()
        _append_watchlist_pipeline_log(
            company_id,
            (
                "start linkedin pipeline "
                f"company_name={company_name or '<empty>'} "
                f"company_website={company_website or '<empty>'} "
                f"company_linkedin_url={company_linkedin_url or '<empty>'}"
            ),
        )

        lead_records = []
        if company_website:
            lead_records = leads_service.run_get_leads_and_upsert_by_company_url(
                [company_website]
            )
        _append_watchlist_pipeline_log(company_id, f"lead_records={len(lead_records)}")

        people_urls = [
            person.linkedin_url.strip()
            for person in lead_records
            if person.linkedin_url and person.linkedin_url.strip()
        ]
        people_urls = list(dict.fromkeys(people_urls))

        profile_records = []
        if people_urls:
            profile_records = profile_service.run_get_profiles_and_upsert_by_query(
                people_urls
            )
        _append_watchlist_pipeline_log(
            company_id, f"profile_records={len(profile_records)}"
        )

        post_urls = list(
            dict.fromkeys(
                [
                    *([company_linkedin_url] if company_linkedin_url else []),
                    *people_urls,
                ]
            )
        )

        post_records = []
        if post_urls:
            post_records = post_service.run_get_posts_and_upsert_mentions_by_urls(
                post_urls
            )
        _append_watchlist_pipeline_log(company_id, f"post_records={len(post_records)}")

        job_records = []
        if company_name:
            job_records = job_service.run_get_jobs_and_upsert_by_company_names(
                [company_name]
            )
        if company_website:
            subdomain_count = sub_domain.getSubdomainsByLinkCompany(company_website)
            _append_watchlist_pipeline_log(
                company_id, f"subdomain_count={subdomain_count}"
            )
        _append_watchlist_pipeline_log(company_id, f"job_records={len(job_records)}")
        _append_watchlist_pipeline_log(company_id, "linkedin pipeline completed")
    except Exception as exc:
        logger.exception(
            "Watchlist LinkedIn pipeline failed for company_id=%s", company_id
        )
        _append_watchlist_pipeline_log(
            company_id,
            f"linkedin pipeline failed: {type(exc).__name__}: {exc}",
        )


def add_company_to_watchlist(user_id: int, company_id: str) -> tuple:
    """Add a company to user's watchlist."""
    count_watchlist = UserWatchList.objects.filter(user_id=user_id).count()
    if count_watchlist >= 200:
        return False, "You can only watch 200 companies"

    existing = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()
    if existing:
        return False, "Company already in watchlist"

    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return False, "Company not found"

    UserWatchList.objects.create(user_id=user_id, company_id=company_id)

    threading.Thread(
        target=_run_watchlist_linkedin_pipeline,
        args=(str(company.id),),
        daemon=True,
    ).start()

    return True, "Success"


def remove_company_from_watchlist(user_id: int, company_ids: str) -> tuple:
    """Remove companies from user's watchlist."""
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


# ------------------------------------ PIN Watchlist ------------------------------------#


def pin_watchlist_company(user_id: int, company_id: str) -> tuple:
    """PIN or unPIN a company in watchlist (toggle mode)."""
    watchlist_item = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()

    if not watchlist_item:
        return False, "Company not found in watchlist"

    if watchlist_item.time_PIN is None:
        watchlist_item.time_PIN = timezone.now()
        watchlist_item.updated_at = timezone.now()
        watchlist_item.save()
        return True, "Pin Company Successful!"
    else:
        watchlist_item.time_PIN = None
        watchlist_item.updated_at = timezone.now()
        watchlist_item.save()
        return True, "Unpin Company Successful!"


# ------------------------------------ Edit Note/ICP ------------------------------------#


def edit_note_for_company(user_id: int, data: list) -> tuple:
    """Edit note for companies in watchlist."""
    for item in data:
        company_id = item.get("company_id", None)
        note = item.get("note", None)
        UserWatchList.objects.filter(company_id=company_id, user_id=user_id).update(
            note=note
        )
    return True, "Success"


def save_icp_for_company(user_id: int, company_id: str, icp_id: str) -> tuple:
    """Save ICP for a company in watchlist."""
    check_exist_company = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).exists()
    if not check_exist_company:
        return False, "Company not found in watchlist"

    icp = ListICP.objects.filter(id=icp_id).first()
    if not icp:
        return False, "ICP not found"

    UserWatchList.objects.filter(user_id=user_id, company_id=company_id).update(
        ICP=icp, updated_at=timezone.now()
    )
    return True, "Success"


# ------------------------------------ Guest Management ------------------------------------#


def add_new_guest_mention(
    user_id: int,
    company_id: str,
    linkedin_url: str,
    twitter_url: str = None,
    email: str = None,
) -> tuple:
    """Add a new guest mention for a company."""
    linkedin_url = linkedin_url.strip("/")
    company = LinkedinCompany.objects.filter(id=company_id).first()

    if not company:
        return False, "Company not found", None

    check_guest = LinkedinPersonalEmail.objects.filter(
        linkedin_url=linkedin_url, company_id=company_id
    ).first()
    if check_guest:
        return False, "Guest already exists", None

    with transaction.atomic():
        new_guest = LinkedinPersonalEmail.objects.create(
            linkedin_url=linkedin_url,
            twitter_url=twitter_url,
            email=email if email else "",
            company_id=company_id,
        )

        user_watchlist = UserWatchList.objects.get(
            user_id=user_id, company_id=company_id
        )
        target_guest_data = user_watchlist.target_guest

        if target_guest_data is None:
            target_guest_data = []

        target_guest_data.append(str(new_guest.id.hex))
        user_watchlist.target_guest = target_guest_data
        user_watchlist.save()

    return (
        True,
        "Add person success, please wait for a moment to get data",
        str(new_guest.id.hex),
    )


def add_guest_available_mention(user_id: int, company_id: str, guest_id: str) -> tuple:
    """Add an existing guest to the user's watchlist mention."""
    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return False, "Company not found"

    check_guest = LinkedinPersonalEmail.objects.filter(
        id=guest_id, company_id=company_id
    ).first()
    if not check_guest:
        return False, "Guest not found"

    user_watchlist = UserWatchList.objects.get(user_id=user_id, company_id=company_id)
    target_guest_data = user_watchlist.target_guest

    if target_guest_data and isinstance(target_guest_data, list):
        if str(guest_id.replace("-", "")) in target_guest_data:
            return False, "Guest already exists"

    if target_guest_data is None:
        target_guest_data = []

    target_guest_data.append(str(guest_id.replace("-", "")))
    user_watchlist.target_guest = target_guest_data
    user_watchlist.save()

    return True, "Success"


def get_all_guest_mention_for_company(user_id: int, company_id: str) -> list:
    """Get all guest mentions for a company."""
    user_watchlist = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()
    if not user_watchlist:
        return []

    guest_list = user_watchlist.target_guest
    if guest_list is None or len(guest_list) == 0:
        return []

    data = []
    for guest in guest_list:
        guest_data = LinkedinPersonalEmail.objects.filter(id=guest).values().first()
        if guest_data:
            data.append(guest_data)
    return data


def remove_guest_mention_for_company(
    user_id: int, company_id: str, guest_id: str
) -> tuple:
    """Remove a guest mention from a company."""
    company_watchlist = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()
    if not company_watchlist:
        return False, "Company not on watchlist"

    target_guest_data = company_watchlist.target_guest
    guest_id = guest_id.replace("-", "")

    if target_guest_data and guest_id in target_guest_data:
        target_guest_data.remove(guest_id)
        if len(target_guest_data) == 0:
            target_guest_data = None
        company_watchlist.target_guest = target_guest_data
        company_watchlist.save()
        return True, "Success"
    else:
        return False, "Guest not found"


def get_all_contact_for_company(user_id: int, company_id: str) -> list:
    """Get all contacts for a company with target_guest flag."""
    contact_data = getTriggerDataByCompanyId(company_id)
    if not contact_data:
        return []

    contacts = contact_data.get("contacts", [])

    user_watchlist = UserWatchList.objects.filter(
        user_id=user_id, company_id=company_id
    ).first()
    if not user_watchlist:
        return contacts

    target_guest_data = user_watchlist.target_guest

    data = []
    for item in contacts:
        if target_guest_data and isinstance(target_guest_data, list):
            guest_id = item.get("id")
            if guest_id and str(guest_id.hex) in target_guest_data:
                item["target_guest"] = True
            else:
                item["target_guest"] = False
        else:
            item["target_guest"] = False
        data.append(item)
    return data


# ------------------------------------ Update Company/Contact ------------------------------------#


def update_company(
    company_id: str, twitter_url: str = None, website: str = None, country: str = None
) -> tuple:
    """Update company information."""
    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return False, "Company not found"

    if country:
        company.country = country
    if website:
        company.website = website
    if twitter_url:
        company.link_twitter = twitter_url
    company.save()

    return True, "Success"


def update_contact(
    contact_id: str, linkedin_url: str = None, twitter_url: str = None
) -> tuple:
    """Update contact information."""
    personal_contact = LinkedinPersonalEmail.objects.filter(id=contact_id).first()
    if not personal_contact:
        return False, "Contact not found"

    if linkedin_url:
        personal_contact.linkedin_url = linkedin_url
    if twitter_url:
        personal_contact.twitter_url = twitter_url
    personal_contact.updated_at = timezone.now()
    personal_contact.save()

    return True, "Success"


# ------------------------------------ Mentions/Notifications ------------------------------------#


def get_all_mentioned_company_per_user(
    user_id: int,
    company_id: str,
    filter_type: str = None,
    offset: int = 0,
    limit: int = 10,
):
    """Get all mentions for a company for a user."""
    # if offset == 0:
    #     seven_days_ago = timezone.now() - timedelta(days=7)
    # else:
    seven_days_ago = timezone.make_aware(datetime(2024, 1, 1))

    company = LinkedinCompany.objects.filter(id=company_id).first()
    if not company:
        return {"offset": offset, "limit": 0, "total_item": 0}, []

    list_notify = Notification.objects.filter(
        company_id=company_id, time_post__gte=seven_days_ago, guest_id__isnull=True
    )

    if filter_type:
        filters = filter_type.split(",")
        list_notify = list_notify.filter(type__in=filters)

    list_notify = list_notify.values(
        "id", "type", "title", "post_url", "time_post"
    ).order_by("-time_post")

    result = []
    for item in list_notify:
        user_notify = UserNotification.objects.filter(
            user_id=user_id, notification_id=item["id"]
        ).first()
        item["is_read"] = user_notify.is_read if user_notify else False
        result.append(item)

    total_record = len(result)
    max_records = min(total_record - offset, limit) if total_record > offset else 0
    result = result[offset : offset + max_records]

    pagination = {
        "offset": offset,
        "limit": max_records,
        "total_item": total_record,
    }
    return pagination, result


def get_mention_per_people(
    user_id: int,
    company_id: str,
    offset: int = 0,
    limit: int = 10,
    range_time: str = None,
):
    """Get mentions per people for a company."""
    seven_days_ago = timezone.make_aware(datetime(2024, 1, 1))
    if range_time == "SEVEN_DAYS":
        seven_days_ago = timezone.now() - timedelta(days=7)

    user_watchlist = (
        UserWatchList.objects.filter(user_id=user_id, company_id=company_id)
        .values("target_guest")
        .first()
    )

    if not user_watchlist:
        return {"offset": offset, "limit": limit, "total_item": 0}, []

    list_guest = LinkedinPersonalEmail.objects.filter(
        company__id=company_id
    ).values_list("id", flat=True)
    guest = list(list_guest)
    guest_ids = [str(g).replace("-", "") for g in guest]

    data = (
        Notification.objects.filter(
            guest_id__in=guest_ids, time_post__gte=seven_days_ago
        )
        .values("id", "type", "title", "post_url", "time_post", "guest_id")
        .order_by("-time_post")
    )

    result = []
    for item in data:
        guest_data = (
            LinkedinPersonalEmail.objects.filter(id=item["guest_id"])
            .values("id", "first_name", "last_name", "role")
            .first()
        )
        item["guest"] = guest_data

        user_notify = UserNotification.objects.filter(
            user_id=user_id, notification_id=item["id"]
        ).first()
        item["is_read"] = user_notify.is_read if user_notify else False
        result.append(item)

    total_record = len(result)
    max_records = min(total_record - offset, limit) if total_record > offset else 0
    result = result[offset : offset + max_records]

    pagination = {
        "offset": offset,
        "limit": max_records,
        "total_item": total_record,
    }
    return pagination, result


def get_all_mention(
    user_id: int,
    filter_type: str = None,
    offset: int = 0,
    limit: int = 10,
    mention_type: str = None,
):
    """Get all mentions across user's watchlist."""
    if offset == 0:
        seven_days_ago = timezone.now() - timedelta(days=7)
    else:
        seven_days_ago = timezone.make_aware(datetime(2024, 1, 1))

    list_company = UserWatchList.objects.filter(user_id=user_id).values_list(
        "company_id", flat=True
    )
    list_company = list(set(list_company))
    if not list_company:
        return {"offset": offset, "limit": limit, "total_item": 0}, []

    if mention_type == "contact":
        list_notify = (
            Notification.objects.filter(
                company_id__in=list_company,
                time_post__gte=seven_days_ago,
                guest_id__isnull=False,
            )
            .values(
                "id",
                "type",
                "title",
                "post_url",
                "time_post",
                "guest_id",
                "company__name",
            )
            .order_by("-time_post")
        )

        result = []
        for item in list_notify:
            guest_data = (
                LinkedinPersonalEmail.objects.filter(id=item["guest_id"])
                .values("id", "first_name", "last_name", "role", "avatar_linkedin_url")
                .first()
            )
            item["guest"] = guest_data

            user_notify = UserNotification.objects.filter(
                user_id=user_id, notification_id=item["id"]
            ).first()
            item["is_read"] = user_notify.is_read if user_notify else False
            result.append(item)
    else:
        list_notify = Notification.objects.filter(
            company_id__in=list_company,
            time_post__gte=seven_days_ago,
            guest_id__isnull=True,
        )

        if filter_type:
            filters = filter_type.split(",")
            list_notify = list_notify.filter(type__in=filters)

        list_notify = list_notify.values(
            "id",
            "type",
            "title",
            "post_url",
            "time_post",
            "company__name",
            "company__avatar_url",
        ).order_by("-time_post")

        result = []
        for item in list_notify:
            user_notify = UserNotification.objects.filter(
                user_id=user_id, notification_id=item["id"]
            ).first()
            item["is_read"] = user_notify.is_read if user_notify else False
            result.append(item)

    total_record = len(result)
    max_records = min(total_record - offset, limit) if total_record > offset else 0
    result = result[offset : offset + max_records]

    pagination = {
        "offset": offset,
        "limit": max_records,
        "total_item": total_record,
    }
    return pagination, result


def seen_all_mention(
    user_id: int, mention_type: str = None, filter_type: str = None
) -> bool:
    """Mark all mentions as seen."""
    list_company = UserWatchList.objects.filter(user_id=user_id).values_list(
        "company_id", flat=True
    )
    list_company = list(set(list_company))

    if not list_company:
        return True

    user = Users.objects.filter(id=user_id).first()

    if mention_type == "contact":
        list_notify = Notification.objects.filter(
            company_id__in=list_company, guest_id__isnull=False
        ).values_list("id", flat=True)
    else:
        list_notify = Notification.objects.filter(
            company_id__in=list_company, guest_id__isnull=True
        )
        if filter_type:
            filters = filter_type.split(",")
            list_notify = list_notify.filter(type__in=filters)
        list_notify = list_notify.values_list("id", flat=True)

    for notify_id in list_notify:
        check_exist_seen = UserNotification.objects.filter(
            user=user, notification_id=notify_id
        ).exists()
        if check_exist_seen:
            continue
        notify = Notification.objects.get(id=notify_id)
        UserNotification.objects.create(user=user, notification=notify)

    return True


def get_all_notify_for_user(user_id: int) -> int:
    """Get count of new notifications for user."""
    seven_days_ago = timezone.now() - timedelta(days=7)

    user_watchlist = UserWatchList.objects.filter(user_id=user_id).values_list(
        "company_id", flat=True
    )
    list_company = list(set(user_watchlist))

    count_notify_is_read = UserNotification.objects.filter(
        user_id=user_id,
        notification__company_id__in=list_company,
        notification__time_post__gte=seven_days_ago,
    ).count()
    count_notify_all = Notification.objects.filter(
        company_id__in=list_company, time_post__gte=seven_days_ago
    ).count()

    new_notify = count_notify_all - count_notify_is_read
    return new_notify


def new_notify_today(company_id: str) -> dict:
    """Get count of new notifications for a company in last 7 days."""
    seven_days_ago = timezone.now() - timedelta(days=7)

    count_guest = Mentions.objects.filter(
        company_id=company_id, guest_id__isnull=False, updated_at__gte=seven_days_ago
    ).count()
    data_linkedin = MentionsLinkedin.objects.filter(
        mentions__company_id=company_id, updated_at__gte=seven_days_ago
    ).count()
    data_twitter = MentionsTwitter.objects.filter(
        mentions__company_id=company_id, updated_at__gte=seven_days_ago
    ).count()
    data_subdomain = MentionsSubDomain.objects.filter(
        mentions__company_id=company_id, updated_at__gte=seven_days_ago
    )[:3].count()
    data_news = NewsInformation.objects.filter(
        company_id=company_id, time_post__gte=seven_days_ago
    ).count()
    data_hiring = LinkedinJob.objects.filter(
        company_id=company_id, updated_at__gte=seven_days_ago
    ).count()

    event_ids = GuestList.objects.filter(company__id=company_id).values_list(
        "event__id", flat=True
    )
    data_event = EventsList.objects.filter(
        id__in=event_ids, start_date__gte=seven_days_ago
    ).count()

    total_record = (
        data_linkedin
        + data_twitter
        + data_subdomain
        + data_news
        + data_hiring
        + data_event
    )
    return {"total_record": total_record, "guest": count_guest}


# ------------------------------------ ICP ------------------------------------#


def get_list_icp() -> list:
    """Get list of ICPs."""
    list_icp = ListICP.objects.all().values("id", "icp_name").order_by("icp_name")
    return list(list_icp)


# ------------------------------------ Detail Info ------------------------------------#


def get_detail_info_for_company(company_id: str) -> dict:
    """Get detailed info for a company."""
    return getTriggerDataByCompanyId(company_id)


# ------------------------------------ Validation ------------------------------------#


def check_had_other_watchlist(current_user_id: int, watchlist_info: list) -> list:
    """Check if companies are in other watchlists."""
    linkedin_pattern = (
        r"^(https?:\/\/)?(www\.)?linkedin\.com\/(in|company)\/[\w\-@.&#]+\/?$"
    )

    unique_rows = set()
    for item in watchlist_info:
        company_linkedin = item.get("company_linkedin")
        contact_linkedin = item.get("contact_linkedin")
        pair = (company_linkedin, contact_linkedin)

        if pair in unique_rows:
            item["status"] = {
                "status_code": 0,
                "message": "Invalid: Duplicate row in file. Please remove it and re-upload.",
            }
            continue
        unique_rows.add(pair)

        # Validate LinkedIn URL
        if company_linkedin and not re.match(linkedin_pattern, company_linkedin):
            item["status"] = {
                "status_code": 0,
                "message": "Invalid Company LinkedIn link. Use format: https://www.linkedin.com/company/company_name/",
            }
            continue

        # Check if already in watchlist
        company_linkedin_clean = (
            company_linkedin.rstrip("/") if company_linkedin else ""
        )
        existing_company = LinkedinCompany.objects.filter(
            linkedin_url=company_linkedin_clean
        ).first()

        if existing_company:
            existing_watchlist = UserWatchList.objects.filter(
                company_id=existing_company.id
            )
            if existing_watchlist.exists():
                if existing_watchlist.filter(user_id=current_user_id).exists():
                    item["status"] = {
                        "status_code": 0,
                        "message": "Invalid: Company is already in your watchlist. Please remove it and re-upload.",
                    }
                else:
                    item["status"] = {
                        "status_code": 0,
                        "message": "Warning: Company is in your teammate's watchlist. You can still add it to yours",
                    }
            else:
                item["status"] = {"status_code": 1, "message": "Valid"}
        else:
            item["status"] = {"status_code": 1, "message": "Valid"}

    return watchlist_info


def check_had_create_manual_watchlist(
    current_user_id: int, company_linkedin: str
) -> dict:
    """Check if company LinkedIn URL is in user's or teammate's watchlist."""
    linkedin_pattern = r"^(https?:\/\/)?(www\.)?linkedin\.com\/company\/[\w\-@.&#]+\/?$"
    if not re.match(linkedin_pattern, company_linkedin):
        return {
            "error": "Invalid Company LinkedIn link. Use format: https://www.linkedin.com/company/company_name/"
        }

    company_linkedin = company_linkedin.rstrip("/")
    already_in_watchlist = False
    already_in_teammate_watchlist = False

    existing_company = (
        LinkedinCompany.objects.filter(linkedin_url=company_linkedin).only("id").first()
    )
    if existing_company:
        existing_watchlist = UserWatchList.objects.filter(
            company_id=existing_company.id
        ).values_list("user_id", flat=True)
        if existing_watchlist:
            already_in_watchlist = current_user_id in existing_watchlist
            already_in_teammate_watchlist = any(
                user_id != current_user_id for user_id in existing_watchlist
            )

    return {
        "existWatchlist": already_in_watchlist,
        "otherWatchlist": already_in_teammate_watchlist,
    }


# ------------------------------------ AI Completions History ------------------------------------#


def create_completion_history(user_id: int, field: str, obj_id: str) -> str:
    """Create a completion history record."""
    user = Users.objects.filter(id=user_id).first()
    if not user:
        return None

    history_data = {"role": "init", "user": user, field: obj_id}
    history = HistoryGenAI.objects.create(**history_data)
    return str(history.id)


def save_history_gen(user_id: int, completion_id: str, messages: list) -> bool:
    """Save AI chat history."""
    user = Users.objects.filter(id=user_id).first()
    if not user:
        return False

    num_old_completions_id = HistoryGenAI.objects.filter(
        completion_id=completion_id
    ).count()
    if num_old_completions_id == len(messages):
        return True

    company_id = (
        HistoryGenAI.objects.filter(id=completion_id, role="init")
        .values("company_id")
        .first()
    )
    person_id = (
        HistoryGenAI.objects.filter(id=completion_id, role="init")
        .values("person_contact_id")
        .first()
    )

    if company_id:
        company_id = company_id["company_id"]
    if person_id:
        person_id = person_id["person_contact_id"]

    count = 0
    for mess in messages:
        role = mess.get("role", None)
        content = mess.get("content", None)
        HistoryGenAI.objects.update_or_create(
            completion_id=completion_id,
            user=user,
            order_number=count,
            defaults={
                "role": role,
                "content": content,
                "updated_at": timezone.now(),
                "company_id": company_id,
                "person_contact_id": person_id,
            },
        )
        count += 1
    return True


def get_all_completions(
    user_id: int, filter_field: str, obj_id: str, page: int = 1, limit: int = 10
):
    """Get all AI completions for a company or contact."""
    user = Users.objects.filter(id=user_id).first()
    if not user:
        return {"page": page, "total_page": 0, "total_item": 0}, []

    filter_kwargs = {"user": user, filter_field: obj_id}
    history_list = HistoryGenAI.objects.filter(**filter_kwargs).order_by(
        "completion_id", "order_number"
    )

    grouped = defaultdict(
        lambda: {"subject": "", "completions": [], "time_updated": None}
    )
    for h in history_list:
        if not h.completion_id:
            continue

        comp = grouped[h.completion_id]
        comp["id"] = h.completion_id
        if comp["subject"] == "":
            subject = (
                HistoryGenAI.objects.filter(id=h.completion_id)
                .values("summarize_content")
                .first()
            )
            if subject:
                comp["subject"] = subject["summarize_content"]
            else:
                comp["subject"] = ""
        comp["completions"].append(
            {
                "role": h.role,
                "content": h.content,
                "order_number": h.order_number,
                "time_updated": h.updated_at,
                "completions_id": h.completion_id,
            }
        )
        if comp["time_updated"] is None or h.updated_at > comp["time_updated"]:
            comp["time_updated"] = h.updated_at

    data = sorted(grouped.values(), key=lambda x: x["time_updated"], reverse=True)
    total = len(data)
    if page and limit:
        data = data[(page - 1) * limit : page * limit]

    pagination = {
        "page": page,
        "total_page": total // limit + (1 if total % limit else 0),
        "total_item": total,
    }
    return pagination, data


def edit_subject_completions(completion_id: str, subject: str) -> bool:
    """Edit the subject of a completion."""
    HistoryGenAI.objects.filter(id=completion_id).update(summarize_content=subject)
    return True


def delete_completions(completion_id: str) -> bool:
    """Delete a completion."""
    completion = HistoryGenAI.objects.filter(completion_id=completion_id)
    if not completion.exists():
        return False
    completion.delete()
    return True
