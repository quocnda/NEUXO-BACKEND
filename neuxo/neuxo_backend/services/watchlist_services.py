from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from neuxo_backend.controller.watchlist_controller import (
    add_company_to_watchlist,
    edit_note_for_company,
    get_all_notify_for_user,
    get_detail_info_for_company,
    get_watchlist_data,
    new_notify_today,
    pin_watchlist_company,
    remove_company_from_watchlist,
)
from users.utils.utils import requireLogin


# OpenAPI parameters for watchlist endpoints
PARAMETERS_WATCHLIST = [
    OpenApiParameter(
        name="search_key", description="find keyword", required=False, type=str
    ),
    OpenApiParameter(
        name="start_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-1-1 00:00:00", value="2024-1-1 00:00:00")],
    ),
    OpenApiParameter(
        name="end_date",
        required=False,
        type=str,
        examples=[OpenApiExample("2024-12-31 00:00:00", value="2024-12-31 00:00:00")],
    ),
    OpenApiParameter(
        name="page",
        required=False,
        type=int,
        examples=[OpenApiExample("1", value="1")],
    ),
    OpenApiParameter(
        name="limit",
        required=False,
        type=int,
        examples=[OpenApiExample("10", value="10")],
    ),
    OpenApiParameter(name="icp_id", required=False, type=str),
    OpenApiParameter(
        name="company_size", description="company_size", required=False, type=str
    ),
    OpenApiParameter(
        name="followers", description="followers", required=False, type=str
    ),
    OpenApiParameter(name="country", description="country", required=False, type=str),
]


# ---------------------------------------- addCompanyToWatchList ---------------------------------------- #


@extend_schema(
    parameters=[],
    request={
        "application/json": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Company id"}},
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_AddCompanyToWatchList",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def addCompanyToWatchList(request: HttpRequest) -> JsonResponse:
    """Add a company to user's watchlist."""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = request.data
        company_id = data.get("id")
        user_id = request.user.get("id", None)

        if not company_id:
            return JsonResponse(
                {"message": "Company id is required"}, status=HTTP_400_BAD_REQUEST
            )

        success, message = add_company_to_watchlist(user_id, company_id)

        if not success:
            return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": message}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- removeCompanyFromWatchList ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "string",
                    "description": "Comma-separated company IDs",
                },
            },
            "required": ["ids"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_RemoveCompanyFromWatchList",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def removeCompanyFromWatchList(request: HttpRequest) -> JsonResponse:
    """Remove companies from user's watchlist."""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = request.data
        company_ids = data.get("ids", None)
        user_id = request.user.get("id", None)

        if not company_ids:
            return JsonResponse(
                {"message": "Company ids are required"}, status=HTTP_400_BAD_REQUEST
            )

        success, message = remove_company_from_watchlist(user_id, company_ids)

        if not success:
            return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": message}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getWatchList ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS_WATCHLIST,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetWatchList",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getWatchList(request: HttpRequest) -> JsonResponse:
    """Get user's watchlist."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        paginator, data = get_watchlist_data(request)

        return JsonResponse(
            {
                "message": "Success",
                "pagination": paginator,
                "data": data,
            },
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- PINWatchlist ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Company id"},
                "is_pin": {"type": "boolean", "description": "Pin status"},
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_PINWatchlist",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def PINWatchlist(request: HttpRequest) -> JsonResponse:
    """PIN or unPIN a company in watchlist."""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = request.data
        company_id = data.get("id")
        is_pin = data.get("is_pin", True)
        user_id = request.user.get("id", None)

        if not company_id:
            return JsonResponse(
                {"message": "Company id is required"}, status=HTTP_400_BAD_REQUEST
            )

        success, message = pin_watchlist_company(user_id, company_id, is_pin)

        if not success:
            return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": message}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- editNoteForCompany ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Company id"},
                "note": {"type": "string", "description": "Note content"},
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_EditNoteForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def editNoteForCompany(request: HttpRequest) -> JsonResponse:
    """Edit note for a company in watchlist."""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = request.data
        company_id = data.get("id")
        note = data.get("note", "")
        user_id = request.user.get("id", None)

        if not company_id:
            return JsonResponse(
                {"message": "Company id is required"}, status=HTTP_400_BAD_REQUEST
            )

        success, message = edit_note_for_company(user_id, company_id, note)

        if not success:
            return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": message}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getDetailInfoForCompany ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetDetailInfoForCompany",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getDetailInfoForCompany(request: HttpRequest, id: str) -> JsonResponse:
    """Get detailed info for a company."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = get_detail_info_for_company(id)

        if not data:
            return JsonResponse(
                {"message": "Company not found"}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse({"message": "Success", "data": data}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getAllNotifyForUser ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_GetAllNotifyForUser",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllNotifyForUser(request: HttpRequest) -> JsonResponse:
    """Get all notifications for user's watchlist companies."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = request.user.get("id", None)
        notifications = get_all_notify_for_user(user_id)

        return JsonResponse(
            {"message": "Success", "data": notifications},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- newNotifyToday ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_NewNotifyToday",
    tags=["Watchlist"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def newNotifyToday(request: HttpRequest, id: str) -> JsonResponse:
    """Get count of new notifications for a company today."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        count = new_notify_today(id)

        return JsonResponse(
            {"message": "Success", "data": {"count": count}},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)
