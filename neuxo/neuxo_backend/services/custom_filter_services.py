"""
Custom Filter Services - HTTP Handler Layer
Handles custom filter related API endpoints
"""

from __future__ import annotations

import traceback

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from neuxo_backend.controller.custom_filter_controller import (
    delete_custom_filter,
    get_custom_filters,
    save_custom_filter,
)
from neuxo_backend.services.utils import getUserID
from users.utils.utils import requireLogin


# ---------------------------------------- Get Custom Filters ---------------------------------------- #


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getCustomFilters",
    tags=["Custom Filter"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getCustomFilters(request: HttpRequest) -> JsonResponse:
    """Get all custom filters for the user"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        filters = get_custom_filters(user_id)

        return JsonResponse({"message": "Success", "data": filters}, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Save Custom Filter ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Filter ID for update"},
                "filter_name": {"type": "string"},
                "filter": {
                    "type": "object",
                    "properties": {
                        "trigger": {"type": "array"},
                        "company_size": {"type": "array"},
                        "followers": {"type": "array"},
                        "country": {"type": "array"},
                        "organization_type": {"type": "array"},
                        "industry": {"type": "array"},
                    },
                },
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_saveCustomFilter",
    tags=["Custom Filter"],
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def saveCustomFilter(request: HttpRequest) -> JsonResponse:
    """Create or update a custom filter"""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        data = request.data

        filter_id = data.get("id")
        filter_name = data.get("filter_name")
        filter_data = data.get("filter", {})

        result = save_custom_filter(
            user_id=user_id,
            filter_id=filter_id,
            filter_name=filter_name,
            filter_data=filter_data,
        )

        if "error" in result:
            return JsonResponse(
                {"message": result["error"]}, status=HTTP_400_BAD_REQUEST
            )

        message = "Update Success" if filter_id else "Save Success"
        response = {"message": message}

        if "data" in result:
            response["data"] = result["data"]

        return JsonResponse(response, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Delete Custom Filter ---------------------------------------- #


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="DELETE_deleteCustomFilter",
    tags=["Custom Filter"],
)
@csrf_exempt
@api_view(["DELETE"])
@requireLogin
def deleteCustomFilter(request: HttpRequest, id: str) -> JsonResponse:
    """Delete a custom filter"""
    if request.method != "DELETE":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        result = delete_custom_filter(filter_id=id, user_id=user_id)

        if "error" in result:
            return JsonResponse(
                {"message": result["error"]}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse({"message": "Delete Success"}, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)
