from __future__ import annotations

from io import BytesIO

import pandas as pd
from django.db import models
from django.db.models import F
from django.db.models.functions import Cast, Concat
from django.db.models import Value
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from neuxo_backend.controller.event_controller import (
    get_columns_events_guest,
    get_company_link_to_event,
    get_event_by_id,
    get_event_guests,
    get_events_data,
    get_list_country_and_parent_event,
    update_guest_email,
    update_guest_note,
)
from neuxo_backend.models import EventsList, GuestList
from neuxo_backend.services import PARAMETERS
from users.utils.utils import requireLogin


# OpenAPI parameters for event endpoints
PARAMETERS_EVENT = [
    OpenApiParameter(
        name="start_date",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="end_date",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="page",
        required=False,
        type=int,
    ),
    OpenApiParameter(
        name="limit",
        required=False,
        type=int,
    ),
    OpenApiParameter(
        name="search_key",
        description="search_key",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="main_event",
        description="main_events",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="country",
        description="locations",
        required=False,
        type=str,
    ),
    OpenApiParameter(
        name="status",
        description="status",
        required=False,
        type=str,
        enum=["UPCOMING", "ONGOING", "PAST"],
    ),
]


# ---------------------------------------- getEvents ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS_EVENT,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_Events",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getEvents(request: HttpRequest) -> JsonResponse:
    """Get paginated list of events with filtering and sorting."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        paginator, response_data = get_events_data(request)

        return JsonResponse(
            {
                "message": "Success",
                "pagination": paginator,
                "data": response_data,
            },
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getListCountryAndParentEvent ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_ListCountryAndParentEvent",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getListCountryAndParentEvent(request: HttpRequest) -> JsonResponse:
    """Get list of countries and parent events for filtering."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        metadata = get_list_country_and_parent_event()
        return JsonResponse(
            {"message": "Success", "data": metadata},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getEventByID ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_EventById",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getEventByID(request: HttpRequest, id: str) -> JsonResponse:
    """Get main event details by ID."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        event_data = get_event_by_id(id)

        if not event_data:
            return JsonResponse(
                {"message": "Main event not found"}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse(
            {"message": "Success", "data": event_data},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getEventGuests ---------------------------------------- #


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="event_id", description="filter by event_id", required=True, type=str
        ),
        OpenApiParameter(
            name="search_key", description="search", required=False, type=str
        ),
        OpenApiParameter(name="role", description="filter", required=False, type=str),
        OpenApiParameter(
            name="country", description="filter", required=False, type=str
        ),
        OpenApiParameter(
            name="category", description="filter", required=False, type=str
        ),
        OpenApiParameter(
            name="email_status", description="filter", required=False, type=str
        ),
        OpenApiParameter(
            name="headquarter", description="filter", required=False, type=str
        ),
        OpenApiParameter(name="page", description="page", required=False, type=int),
        OpenApiParameter(name="limit", description="limit", required=False, type=int),
        OpenApiParameter(
            name="sortByVal", description="sortByVal", required=False, type=str
        ),
        OpenApiParameter(
            name="orderByVal",
            description="Direction in which to order the results by (ASC by default)",
            required=False,
            type=str,
            enum=["ASC", "DESC"],
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_EventGuests",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getEventGuests(request: HttpRequest) -> JsonResponse:
    """Get paginated guest list for an event."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    event_id = request.GET.get("event_id", None)
    if not event_id:
        return JsonResponse(
            {"message": "Event id is required"}, status=HTTP_400_BAD_REQUEST
        )

    try:
        paginator, response_data = get_event_guests(request, event_id)

        return JsonResponse(
            {
                "message": "Success",
                "pagination": paginator,
                "data": response_data,
            },
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getColumnsEventsGuest ---------------------------------------- #


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="event_id", description="filter by event_id", required=True, type=str
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_ColumnsFilterGuests",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getColumnsEventsGuest(request: HttpRequest) -> JsonResponse:
    """Get filter columns for event guests."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    event_id = request.GET.get("event_id", None)
    if not event_id:
        return JsonResponse(
            {"message": "Event id is required"}, status=HTTP_400_BAD_REQUEST
        )

    try:
        columns = get_columns_events_guest(event_id)
        return JsonResponse(
            {"message": "Success", "data": columns},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- updateNoteGuests ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Guest id"},
                "note": {"type": "string", "description": "Note"},
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_UpdateNoteGuests",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateNoteGuests(request: HttpRequest) -> JsonResponse:
    """Update note for a guest."""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = request.data
        guest_id = data.get("id")
        note = data.get("note", "")

        if not guest_id:
            return JsonResponse(
                {"message": "Guest id is required"}, status=HTTP_400_BAD_REQUEST
            )

        success = update_guest_note(guest_id, note)

        if not success:
            return JsonResponse(
                {"message": "Guest not found"}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse(
            {"message": "Success"},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- updateEmailGuests ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Guest id"},
                "email": {"type": "string", "description": "Email"},
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_UpdateEmailGuests",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateEmailGuests(request: HttpRequest) -> JsonResponse:
    """Update email for a guest."""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = request.data
        guest_id = data.get("id")
        email = data.get("email")

        if not guest_id or not email:
            return JsonResponse(
                {"message": "Guest id and email are required"},
                status=HTTP_400_BAD_REQUEST,
            )

        success = update_guest_email(guest_id, email)

        if not success:
            return JsonResponse(
                {"message": "Guest not found"}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse(
            {"message": "Success"},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getCompanyLinkToEvent ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_CompanyLinkToEvent",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getCompanyLinkToEvent(request: HttpRequest, id: str) -> JsonResponse:
    """Get companies linked to an event."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        companies = get_company_link_to_event(id)
        return JsonResponse(
            {"message": "Success", "data": companies},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- downloadEvents ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_DownloadEvents",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def downloadEvents(request: HttpRequest) -> HttpResponse:
    """Download events data as Excel file."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        excel_file = BytesIO()

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
        ]

        main_data = EventsList.objects.filter(number_of_company__gt=0)
        main_data = (
            main_data.annotate(
                full_event_url=Concat(
                    Value("https://lu.ma/"),
                    F("event_url"),
                    output_field=models.CharField(),
                ),
                full_created_at=Cast(F("created_at"), output_field=models.DateField()),
                full_start_date=Cast(F("start_date"), output_field=models.DateField()),
                companies=Cast(F("number_of_company"), output_field=models.CharField()),
                guests=Cast(F("number_of_guest"), output_field=models.CharField()),
            )
            .values(*LIST_FIELDS)
            .order_by("-start_date")
        )

        result = [
            {
                **data,
                "event_url": data.pop("full_event_url"),
                "start_date": data.pop("full_start_date"),
                "created_at": data.pop("full_created_at"),
            }
            for data in main_data
        ]

        response_data = pd.DataFrame(result)

        # Convert timezone-aware datetime columns
        for col in response_data.select_dtypes(
            include=["datetime64[ns, UTC]", "datetime64[ns]"]
        ):
            response_data[col] = pd.to_datetime(response_data[col]).dt.tz_localize(None)

        response_data.to_excel(excel_file, index=False, engine="openpyxl")
        excel_file.seek(0)

        response = HttpResponse(
            excel_file,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment;filename="Events.xlsx"'

        return response
    except Exception as e:
        return JsonResponse(
            {"message": "Download failed", "exception": str(e)},
            status=HTTP_400_BAD_REQUEST,
        )


# ---------------------------------------- downloadCompanyInEvents ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_DownloadCompanyInEvents",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def downloadCompanyInEvents(request: HttpRequest, id: str) -> HttpResponse:
    """Download companies in an event as Excel file."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        excel_file = BytesIO()

        companies = get_company_link_to_event(id)
        response_data = pd.DataFrame(companies)

        response_data.to_excel(excel_file, index=False, engine="openpyxl")
        excel_file.seek(0)

        response = HttpResponse(
            excel_file,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment;filename="CompaniesInEvent.xlsx"'

        return response
    except Exception as e:
        return JsonResponse(
            {"message": "Download failed", "exception": str(e)},
            status=HTTP_400_BAD_REQUEST,
        )


# ---------------------------------------- downloadGuests ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_DownloadGuests",
    tags=["Event"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def downloadGuests(request: HttpRequest) -> HttpResponse:
    """Download guests data as Excel file."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        excel_file = BytesIO()

        start_date = request.GET.get("start_date", None)
        end_date = request.GET.get("end_date", None)

        LIST_FIELD = [
            "name",
            "linkedin_url",
            "twitter_url",
            "website",
            "event__name",
            "company__name",
            "company__country",
            "category",
            "email",
            "created_at",
        ]

        main_data = GuestList.objects.filter(company__isnull=False).annotate(
            category=F("company__category")
        )

        if start_date and end_date:
            if len(start_date) == 10:
                start_date = start_date + " 00:00:00"
            if len(end_date) == 10:
                end_date = end_date + " 23:59:59"
            main_data = main_data.filter(created_at__range=[start_date, end_date])

        main_data = main_data.values(*LIST_FIELD)

        response_data = pd.DataFrame(list(main_data))

        # Convert timezone-aware datetime columns
        for col in response_data.select_dtypes(
            include=["datetime64[ns, UTC]", "datetime64[ns]"]
        ):
            response_data[col] = pd.to_datetime(response_data[col]).dt.tz_localize(None)

        response_data.to_excel(excel_file, index=False, engine="openpyxl")
        excel_file.seek(0)

        response = HttpResponse(
            excel_file,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment;filename="Guests.xlsx"'

        return response
    except Exception as e:
        return JsonResponse(
            {"message": "Download failed", "exception": str(e)},
            status=HTTP_400_BAD_REQUEST,
        )
