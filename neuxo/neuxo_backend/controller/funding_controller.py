from __future__ import annotations

from django.db.models import Case, F, FloatField, JSONField, TextField, Value, When
from django.db.models.functions import Cast

from neuxo_backend.models import CompanyFunding


def get_fundings_data(request):
    """
    Get paginated and filtered funding data.
    Returns tuple of (paginator_info, response_data, showing_columns).
    """
    # Get parameters
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 100))
    search_key = request.GET.get("search_key", None)
    round_filter = request.GET.get("round", None)
    category_filter = request.GET.get("category", None)
    sortByVal = request.GET.get("sortByVal", "date")
    orderByVal = request.GET.get("orderByVal", "DESC")

    if page < 1:
        page = 1
    if limit < 1 or limit > 200:
        limit = 100

    # Base query
    if start_date and end_date:
        if len(start_date) == 10:
            start_date = start_date + " 00:00:00"
        if len(end_date) == 10:
            end_date = end_date + " 23:59:59"
        fundings = CompanyFunding.objects.filter(date__range=[start_date, end_date])
    else:
        fundings = CompanyFunding.objects.all()

    # Annotate with additional fields
    fundings = fundings.annotate(
        funding_amount=Cast(F("amount"), FloatField()),
        lst_email=Case(
            When(company__lst_email_contact__isnull=True, then=Value("[]")),
            default=F("company__lst_email_contact"),
            output_field=JSONField(),
        ),
        status_mail=Case(
            When(company__user_reach_out__isnull=True, then=Value("Send mail")),
            default=F("company__user_reach_out"),
            output_field=TextField(),
        ),
    )

    # Apply search filter
    if search_key:
        fundings = fundings.filter(name__icontains=search_key)

    # Apply round filter
    if round_filter:
        rounds = round_filter.split(",")
        fundings = fundings.filter(round__in=rounds)

    # Apply category filter
    if category_filter:
        categories = category_filter.split(",")
        fundings = fundings.filter(category__in=categories)

    # Map sort field
    sort_field_map = {
        "company": "name",
        "category": "category",
        "round": "round",
        "funding_amount": "funding_amount",
        "time": "date",
    }
    sort_field = sort_field_map.get(sortByVal, sortByVal)

    # Apply sorting
    revert = orderByVal.upper() == "DESC"
    fundings = fundings.order_by(f"-{sort_field}" if revert else sort_field)

    # Get values
    fundings_data = fundings.values(
        "logo_url",
        "name",
        "round",
        "funding_amount",
        "date",
        "category",
        "project_url",
        "website",
        "linkedin_url",
        "created_at",
        "company_id",
        "lst_email",
        "status_mail",
    )

    # Manual pagination
    total_count = fundings_data.count()
    response_data = list(fundings_data)[(page - 1) * limit : page * limit]

    # Format dates
    for item in response_data:
        if item.get("created_at"):
            item["created_at"] = item["created_at"].strftime("%Y-%m-%d")
        if item.get("date"):
            item["date"] = item["date"].strftime("%Y-%m-%d")

    total_pages = (total_count + limit - 1) // limit
    paginator = {
        "page": page,
        "total_page": total_pages,
        "total_item": total_count,
    }

    # Showing columns for funding
    showing_columns = [
        {"name": "logo_url", "is_show": True},
        {"name": "name", "is_show": True},
        {"name": "round", "is_show": True},
        {"name": "funding_amount", "is_show": True, "can_arrange": True},
        {"name": "date", "is_show": True, "can_arrange": True},
        {"name": "category", "is_show": True},
        {"name": "project_url", "is_show": True},
        {"name": "website", "is_show": True},
        {"name": "linkedin_url", "is_show": True},
    ]

    return paginator, response_data, showing_columns


def get_funding_by_id(funding_id: str) -> dict | None:
    """Get detailed funding information by ID."""
    funding = CompanyFunding.objects.filter(id=funding_id).values().first()

    if not funding:
        return None

    # Format dates
    if funding.get("created_at"):
        funding["created_at"] = funding["created_at"].strftime("%Y-%m-%d")
    if funding.get("date"):
        funding["date"] = funding["date"].strftime("%Y-%m-%d")
    if funding.get("updated_at"):
        funding["updated_at"] = funding["updated_at"].strftime("%Y-%m-%d")

    return funding


def get_funding_metadata() -> dict:
    """Get metadata for funding filtering (rounds and categories)."""
    rounds = (
        CompanyFunding.objects.values_list("round", flat=True)
        .distinct()
        .order_by("round")
    )

    categories_raw = (
        CompanyFunding.objects.values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )

    # Process categories (they may be comma-separated)
    unique_categories = set()
    for cat_str in categories_raw:
        if cat_str:
            categories = cat_str.split(",")
            unique_categories.update([c.strip() for c in categories])

    return {
        "round": [r for r in rounds if r],
        "category": sorted(unique_categories),
    }


def get_fundings_for_download(request) -> list:
    """Get fundings data for Excel download."""
    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)

    if start_date and end_date:
        if len(start_date) == 10:
            start_date = start_date + " 00:00:00"
        if len(end_date) == 10:
            end_date = end_date + " 23:59:59"
        fundings = CompanyFunding.objects.filter(date__range=[start_date, end_date])
    else:
        fundings = CompanyFunding.objects.all()

    result = list(
        fundings.values(
            "name",
            "round",
            "amount",
            "date",
            "category",
            "project_url",
            "website",
            "linkedin_url",
            "created_at",
        )
    )

    return result
