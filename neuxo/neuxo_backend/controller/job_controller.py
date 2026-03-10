from __future__ import annotations

from django.db.models import Case, F, JSONField, Q, TextField, Value, When
from datetime import datetime, timedelta
from neuxo_backend.controller import INDUSTRIES_REJECT
from neuxo_backend.models import LinkedinJob, LinkedinLocation


def get_jobs_data(request):
    """
    Get paginated and filtered LinkedIn jobs data.
    Returns tuple of (paginator_info, response_data, showing_columns).
    """
    # Field mapping for response transformation
    field_mapping = {
        "company__avatar_url": "avatar_url",
        "title": "job_title",
        "category__name": "category",
        "company__name": "company",
        "company__id": "company_id",
        "location__name": "country",
        "linkedin_url": "linkedin_url",
        "created_at": "created_at",
        "lst_email": "lst_email",
        "status_mail": "status_mail",
    }
    reverse_field_mapping = {v: k for k, v in field_mapping.items()}
    reverse_field_mapping["time"] = "created_at"

    # Get parameters
    start_date = request.GET.get(
        "start_date",
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00"),
    )
    end_date = request.GET.get("end_date", datetime.now().strftime("%Y-%m-%d 23:59:59"))
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 100))
    search_key = request.GET.get("search_key", None)
    sortByVal = request.GET.get("sortByVal", "created_at")
    orderByVal = request.GET.get("orderByVal", "DESC")
    category = request.GET.get("category", None)

    if page < 1:
        page = 1
    if limit < 1 or limit > 200:
        limit = 100

    # Normalize date strings
    if len(start_date) == 10:
        start_date = start_date + " 00:00:00"
    if len(end_date) == 10:
        end_date = end_date + " 23:59:59"

    # Base query
    jobs = (
        LinkedinJob.objects.select_related("company", "category", "location")
        .filter(created_at__range=[start_date, end_date])
        .filter(company__is_finding_company__isnull=True, company__is_blacklist=False)
        .exclude(company__industry__in=INDUSTRIES_REJECT)
        .exclude(category__isnull=True)
        .exclude(status="removed")
        .defer("description", "short_description")
    )

    # Apply search filter
    if search_key:
        jobs = jobs.filter(
            Q(title__icontains=search_key) | Q(company__name__icontains=search_key)
        )

    # Apply category filter
    if category:
        categories = category.split(",")
        jobs = jobs.filter(category__name__in=categories)

    # Map sort field
    if sortByVal in reverse_field_mapping:
        sort_field = reverse_field_mapping.get(sortByVal, "created_at")
    else:
        sort_field = sortByVal

    # Apply sorting
    revert = orderByVal.upper() == "DESC"
    jobs = jobs.order_by(f"-{sort_field}" if revert else sort_field)

    # Annotate with email fields
    jobs = jobs.annotate(
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

    # Get total count before pagination
    total_count = jobs.count()

    # Get paginated data
    offset = (page - 1) * limit
    jobs_page = jobs[offset : offset + limit]

    # Transform data to response format
    response_data = jobs_page.values(*field_mapping.keys())
    response_data = [
        {field_mapping[key]: value for key, value in data.items()}
        for data in response_data
    ]

    # Build pagination info
    total_pages = (total_count + limit - 1) // limit
    paginator = {
        "page": page,
        "limit": limit,
        "total_page": total_pages,
        "total_item": total_count,
    }

    # Showing columns for jobs
    showing_columns = [
        {"name": "avatar_url", "is_show": True},
        {"name": "job_title", "is_show": True},
        {"name": "category", "is_show": True},
        {"name": "company", "is_show": True},
        {"name": "country", "is_show": True},
        {"name": "linkedin_url", "is_show": True},
        {"name": "created_at", "is_show": True, "can_arrange": True},
    ]

    return paginator, response_data, showing_columns


def get_job_by_id(job_id: str) -> dict | None:
    """Get detailed job information by ID."""
    job = (
        LinkedinJob.objects.filter(id=job_id)
        .select_related("company", "category", "location", "label")
        .first()
    )

    if not job:
        return None

    return {
        "job_id": str(job.id),
        "job_title": job.title,
        "category": job.category.name if job.category else None,
        "company": job.company.name if job.company else None,
        "location": job.location.name if job.location else None,
        "linkedin_url": job.linkedin_url,
        "created_at": job.created_at.strftime("%Y-%m-%d") if job.created_at else None,
        "label": job.label.name if job.label else None,
        "note": job.note,
        "description": job.description,
    }


def get_job_metadata() -> dict:
    """Get metadata for job filtering (countries/locations)."""
    locations = (
        LinkedinLocation.objects.values_list("name", flat=True)
        .distinct()
        .order_by("name")
    )
    return {"country": list(locations)}


def get_jobs_for_download(request) -> list:
    """Get jobs data for Excel download."""
    start_date = request.GET.get(
        "start_date",
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00"),
    )
    end_date = request.GET.get("end_date", datetime.now().strftime("%Y-%m-%d 23:59:59"))
    search_key = request.GET.get("search_key", None)

    if len(start_date) == 10:
        start_date = start_date + " 00:00:00"
    if len(end_date) == 10:
        end_date = end_date + " 23:59:59"

    jobs = LinkedinJob.objects.filter(created_at__range=[start_date, end_date]).values(
        "title",
        "category__name",
        "company__name",
        "location__name",
        "linkedin_url",
        "created_at",
        "label__name",
    )

    if search_key:
        jobs = jobs.filter(
            Q(title__icontains=search_key) | Q(company__name__icontains=search_key)
        )

    field_mapping = {
        "title": "job_title",
        "category__name": "category",
        "company__name": "company",
        "location__name": "location",
        "linkedin_url": "linkedin_url",
        "created_at": "created_at",
        "label__name": "label",
    }

    return [{field_mapping[key]: value for key, value in item.items()} for item in jobs]
