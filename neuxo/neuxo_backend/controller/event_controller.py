from __future__ import annotations

from datetime import datetime, timezone as tz

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.db.models import (
    Case,
    CharField,
    F,
    IntegerField,
    Q,
    Value,
    When,
)
from django.db.models.functions import Cast, Concat

from neuxo_backend.models import EventsList, GuestList, LinkedinCompany, MainEvents


def get_events_data(request):
    """
    Get paginated and filtered events data.
    Returns tuple of (paginator_info, response_data).
    """
    # Get parameters
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 100))
    main_events = request.GET.get("main_event", None)
    search = request.GET.get("search_key", None)
    status = request.GET.get("status", None)
    country_filter = request.GET.get("country", None)

    if page < 1:
        page = 1
    if limit < 1 or limit > 200:
        limit = 100

    now = datetime.now(tz.utc)

    LIST_FIELDS = [
        "id",
        "name",
        "full_event_url",
        "full_start_date",
        "full_created_at",
        "location",
        "country",
        "event_parent",
        "companies",
        "guests",
        "event_image",
        "start_at",
        "end_at",
        "approval_status",
        "main_event__id",
        "status",
    ]

    # Base query
    if start_date and end_date:
        if len(start_date) == 10:
            start_date = start_date + " 00:00:00"
        if len(end_date) == 10:
            end_date = end_date + " 23:59:59"
        main_data = EventsList.objects.filter(start_at__range=[start_date, end_date])
    else:
        main_data = EventsList.objects.all()

    # Filter by main events
    if main_events:
        main_events_ids = str(main_events).replace("-", "").split(",")
        main_data = main_data.filter(main_event_id__in=main_events_ids)

    # Annotate with computed fields
    main_data = main_data.annotate(
        full_event_url=Concat(
            Value("https://lu.ma/"), F("event_url"), output_field=models.CharField()
        ),
        full_created_at=Cast(F("created_at"), output_field=models.DateField()),
        full_start_date=Cast(F("start_date"), output_field=models.DateField()),
        companies=Cast(F("number_of_company"), output_field=models.CharField()),
        guests=Cast(F("number_of_guest"), output_field=models.CharField()),
        status=Case(
            When(start_at__gt=now, then=Value("UPCOMING")),
            When(start_at__lte=now, end_at__gte=now, then=Value("ONGOING")),
            When(end_at__lt=now, then=Value("PAST")),
            default=Value(None),
            output_field=CharField(),
        ),
    ).values(*LIST_FIELDS)

    # Filter by status
    if status:
        main_data = main_data.filter(Q(status=status))
        if status == "UPCOMING":
            main_data = main_data.filter(start_at__gt=now).order_by("start_at")
        elif status == "ONGOING":
            main_data = main_data.filter(start_at__lte=now, end_at__gte=now).order_by(
                "start_at"
            )
        elif status == "PAST":
            main_data = main_data.filter(end_at__lt=now).order_by("-start_at")
    else:
        # Default ordering: ONGOING > UPCOMING > PAST
        main_data = main_data.annotate(
            order_priority=Case(
                When(status="ONGOING", then=Value(1)),
                When(status="UPCOMING", then=Value(2)),
                When(status="PAST", then=Value(3)),
                default=Value(999),
                output_field=IntegerField(),
            )
        ).order_by(
            "order_priority",
            Case(
                When(status__in=["ONGOING", "UPCOMING"], then=F("start_at")),
                output_field=models.DateTimeField(),
            ),
            Case(
                When(status="PAST", then=F("start_at")),
                output_field=models.DateTimeField(),
            ).desc(),
        )

    # Apply search filter
    if search:
        main_data = main_data.filter(Q(name__icontains=search))

    # Transform approval status
    result = []
    for data in main_data:
        transformed = {
            **data,
            "event_url": data.pop("full_event_url"),
            "start_date": data.pop("full_start_date"),
            "created_at": data.pop("full_created_at"),
            "approval_status": _transform_approval_status(data["approval_status"]),
        }
        result.append(transformed)

    # Filter by country
    if country_filter and country_filter.strip() != "null":
        countries = country_filter.split(",")
        result = [r for r in result if str(r.get("country")) in countries]

    # Pagination
    total_count = len(result)
    if total_count == 0:
        return (
            {"page": 1, "total_page": 1, "total_item": 0},
            [],
        )

    response_data = result[(page - 1) * limit : page * limit]
    total_pages = (total_count + limit - 1) // limit

    paginator = {
        "page": page,
        "total_page": total_pages,
        "total_item": total_count,
    }

    return paginator, response_data


def _transform_approval_status(status: str | None) -> str | None:
    """Transform approval status to display format."""
    status_map = {
        "approved": "Going",
        "waitlist": "Pending",
        "pending_approval": "Pending",
        "invited": "Invited",
    }
    return status_map.get(status, None)


def get_event_by_id(event_id: str) -> dict | None:
    """Get main event details by ID."""
    event = MainEvents.objects.filter(id=event_id).values().first()

    if not event:
        return None

    # Transform URLs
    if event.get("twitter_url"):
        event["twitter_url"] = "https://x.com/" + event["twitter_url"]
    if event.get("linkedin_url"):
        event["linkedin_url"] = "https://www.linkedin.com" + event["linkedin_url"]
    if event.get("instagram_url"):
        event["instagram_url"] = "https://www.instagram.com/" + event["instagram_url"]
    if event.get("youtube_url"):
        event["youtube_url"] = "https://www.youtube.com/@" + event["youtube_url"]

    return event


def get_list_country_and_parent_event() -> dict:
    """Get list of countries and parent events for filtering."""
    main_events = MainEvents.objects.values("id", "name").order_by("name")
    list_country = (
        EventsList.objects.filter(country__isnull=False)
        .values_list("country", flat=True)
        .distinct()
    )

    return {
        "main_events": list(main_events),
        "list_country": list(list_country),
    }


def get_event_guests(request, event_id: str):
    """
    Get paginated guest list for an event.
    Returns tuple of (paginator_info, response_data).
    """
    search = request.GET.get("search_key", None)
    role = request.GET.get("role", None)
    country = request.GET.get("country", None)
    category = request.GET.get("category", None)
    headquarter = request.GET.get("headquarter", "[]")
    sortByVal = request.GET.get("sortByVal", None)
    orderByVal = request.GET.get("orderByVal", "DESC")
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 100))

    # Parse headquarter list
    try:
        import ast

        headquarter = ast.literal_eval(headquarter)
    except (ValueError, SyntaxError):
        headquarter = []

    field_mapping = {
        "contact_name": "name",
        "contact_email": "email",
        "company_name": "company__name",
        "headquarters": "company__headquarters",
        "country": "company__country",
        "category": "category",
        "note": "note",
        "role": "role",
        "email_status": "email_status",
    }

    LIST_FIELDS = [
        "id",
        "name",
        "role",
        "linkedin_url",
        "linkedin_url_full",
        "twitter_url",
        "twitter_url_full",
        "website",
        "event__name",
        "event__id",
        "company__name",
        "company__id",
        "company__headquarters",
        "company__country",
        "category",
        "email",
        "created_at",
        "note",
        "email_input_from_user",
        "email_status_emailinfor",
        "send_by_emailinfor",
        "last_activity_emailinfor",
        "error_emailinfor",
    ]

    # Base query
    main_data = GuestList.objects.filter(event_id=event_id).annotate(
        category=F("company__category"),
        twitter_url_full=Case(
            When(
                twitter_url__isnull=False,
                then=Concat(Value("https://twitter.com/"), F("twitter_url")),
            ),
            default=Value(None),
            output_field=CharField(),
        ),
        linkedin_url_full=Case(
            When(
                linkedin_url__isnull=False,
                then=Concat(Value("https://www.linkedin.com"), F("linkedin_url")),
            ),
            default=Value(None),
            output_field=CharField(),
        ),
        created_at_str=Cast(F("created_at"), output_field=CharField()),
        email_status=F("email_status_emailinfor"),
    )

    # Apply sorting
    if sortByVal and sortByVal in field_mapping:
        sort_field = field_mapping.get(sortByVal, sortByVal)
        revert = orderByVal.upper() == "DESC"
        main_data = main_data.order_by(f"-{sort_field}" if revert else sort_field)

    main_data = main_data.values(*LIST_FIELDS)

    # Transform data
    transformed_data = []
    for item in main_data:
        transformed = {
            **item,
            "created_at": (
                str(item["created_at"])[:10] if item.get("created_at") else ""
            ),
            "twitter_url": item.get("twitter_url_full") or None,
            "linkedin_url": item.get("linkedin_url_full") or None,
            "email_information": [
                {
                    "email_status": item.get("email_status_emailinfor") or "UNREACHED",
                    "send_by": item.get("send_by_emailinfor") or "",
                    "last_activity": item.get("last_activity_emailinfor") or "",
                    "error": item.get("error_emailinfor") or "",
                    "last_reply": "",
                }
            ],
        }
        transformed_data.append(transformed)

    # Apply filters
    filtered_data = transformed_data

    if search:
        search_lower = search.lower()
        filtered_data = [
            item
            for item in filtered_data
            if search_lower in (item.get("name") or "").lower()
            or search_lower in (item.get("email") or "").lower()
            or search_lower in (item.get("company__name") or "").lower()
        ]

    filters = {
        "role": role,
        "company__country": country,
        "category": category,
    }

    for key, value in filters.items():
        if value:
            values = value.split(",")
            filtered_data = [item for item in filtered_data if item.get(key) in values]

    if headquarter:
        filtered_data = [
            item
            for item in filtered_data
            if item.get("company__headquarters") in headquarter
        ]

    # Pagination
    paginator_obj = Paginator(filtered_data, limit)
    try:
        page_data = paginator_obj.page(page)
    except PageNotAnInteger:
        page_data = paginator_obj.page(1)
    except EmptyPage:
        page_data = paginator_obj.page(paginator_obj.num_pages)

    paginator = {
        "page": page_data.number,
        "limit": page_data.paginator.per_page,
        "total_page": paginator_obj.num_pages,
        "total_item": paginator_obj.count,
    }

    return paginator, list(page_data)


def get_columns_events_guest(event_id: str) -> dict:
    """Get filter columns for event guests."""
    guests = GuestList.objects.filter(event_id=event_id)

    # Get unique values for each filter column
    roles = (
        guests.filter(role__isnull=False)
        .values_list("role", flat=True)
        .distinct()
        .order_by("role")
    )

    countries = (
        guests.filter(company__country__isnull=False)
        .values_list("company__country", flat=True)
        .distinct()
        .order_by("company__country")
    )

    categories = (
        guests.filter(company__category__isnull=False)
        .values_list("company__category", flat=True)
        .distinct()
        .order_by("company__category")
    )

    headquarters = (
        guests.filter(company__headquarters__isnull=False)
        .values_list("company__headquarters", flat=True)
        .distinct()
        .order_by("company__headquarters")
    )

    email_statuses = (
        guests.filter(email_status_emailinfor__isnull=False)
        .values_list("email_status_emailinfor", flat=True)
        .distinct()
    )

    return {
        "role": list(roles),
        "country": list(countries),
        "category": list(categories),
        "headquarter": list(headquarters),
        "email_status": list(email_statuses),
    }


def update_guest_note(guest_id: str, note: str) -> bool:
    """Update note for a guest."""
    guest = GuestList.objects.filter(id=guest_id).first()
    if not guest:
        return False
    guest.note = note
    guest.save()
    return True


def update_guest_email(guest_id: str, email: str) -> bool:
    """Update email for a guest."""
    guest = GuestList.objects.filter(id=guest_id).first()
    if not guest:
        return False
    guest.email = email
    guest.email_input_from_user = True
    guest.save()
    return True


def get_company_link_to_event(event_id: str) -> list:
    """Get companies linked to an event through guests."""
    guests = GuestList.objects.filter(event_id=event_id, company__isnull=False)
    company_ids = guests.values_list("company_id", flat=True).distinct()

    companies = LinkedinCompany.objects.filter(id__in=company_ids).values(
        "id",
        "name",
        "avatar_url",
        "linkedin_url",
        "website",
        "size",
        "industry",
        "country",
        "category",
        "short_description",
    )

    result = []
    for company in companies:
        guest_count = guests.filter(company_id=company["id"]).count()
        result.append(
            {
                **company,
                "guest_count": guest_count,
            }
        )

    return result


def get_guests_by_event(request):
    event_id = request.GET.get("event_id", None)

    if not event_id:
        return False

    LIST_FIELDS = [
        "name",
        "role",
        "linkedin_url",
        "twitter_url",
        "website",
        "email",
        "company__country",
        "created_at",
    ]

    main_data = (
        GuestList.objects.filter(event_id=event_id)
        .annotate(contact_name=F("name"), company_country=F("company__country"))
        .values(*LIST_FIELDS)
    )

    for data in main_data:
        data["created_at"] = data["created_at"].strftime("%Y-%m-%d")
        data["twitter_url"] = (
            "https://twitter.com/" + data["twitter_url"]
            if data["twitter_url"]
            else None
        )
        data["linkedin_url"] = (
            "https://www.linkedin.com" + data["linkedin_url"]
            if data["linkedin_url"]
            else None
        )

    if len(main_data) == 0:
        return []
    size = len(list(main_data))
    data = list(main_data)[:size]
    return data
