from drf_spectacular.utils import OpenApiParameter

# Shared parameters for pagination and filtering
PARAMETERS = [
    OpenApiParameter(name="page", description="Page number", required=False, type=int),
    OpenApiParameter(
        name="limit", description="Number of items per page", required=False, type=int
    ),
    OpenApiParameter(
        name="search_key", description="Search keyword", required=False, type=str
    ),
    OpenApiParameter(
        name="start_date",
        description="Start date (format: YYYY-MM-DD HH:MM:SS)",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="end_date",
        description="End date (format: YYYY-MM-DD HH:MM:SS)",
        required=False,
        type=str,
    ),
]

PARAMETERS_EMAIL = [
    OpenApiParameter(
        name="email_status",
        description="Email status filter (REPLIED,SEEN,ERROR,SENT)",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="email_count_start",
        description="Minimum email count",
        required=False,
        type=int,
    ),
    OpenApiParameter(
        name="email_count_end",
        description="Maximum email count",
        required=False,
        type=int,
    ),
    OpenApiParameter(
        name="last_activity_start_date",
        description="Last activity start date",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="last_activity_end_date",
        description="Last activity end date",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="follow_up_status",
        description="Follow-up status (Focused,Overdue,Upcoming)",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="priority",
        description="Priority filter (HIGH,MEDIUM,LOW)",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="time_zone",
        description="Timezone (default: Asia/Saigon)",
        required=False,
        type=str,
    ),
]


def getParams(request):
    """Extract common pagination parameters from request"""
    from datetime import datetime

    start_date = request.GET.get("start_date", None)
    end_date = request.GET.get("end_date", None)
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))

    if start_date:
        start_date = datetime.strptime(start_date.strip(), "%Y-%m-%d %H:%M:%S")
    if end_date:
        end_date = datetime.strptime(end_date.strip(), "%Y-%m-%d %H:%M:%S")

    return start_date, end_date, page, limit


def getUserID(request):
    """Extract user ID from request"""
    user_info = request.user
    user_id = user_info.get("id", None)
    return user_id
