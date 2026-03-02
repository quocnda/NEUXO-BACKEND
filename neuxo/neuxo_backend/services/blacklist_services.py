from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from neuxo_backend.controller.blacklist_controller import (
    addToBlacklist,
    getBlacklistData,
    removeFromBlacklist,
)

from neuxo_backend.services import PARAMETERS
from users.utils.utils import requireLogin


# ---------------------------------------- addBlackList ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_AddBlackList",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def addBlackList(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    data = request.data
    lst_id = data.get("ids")
    if not lst_id:
        return JsonResponse(
            {"message": "Company ids are required"}, status=HTTP_400_BAD_REQUEST
        )
    ids = lst_id.split(",")
    not_found = addToBlacklist(ids)
    if not_found:
        return JsonResponse(
            {"message": f"Companies not found: {', '.join(not_found)}"},
            status=HTTP_400_BAD_REQUEST,
        )
    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- removeBlacklist ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_RemoveBlackList",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def removeBlacklist(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    data = request.data
    lst_id = data.get("ids")
    if not lst_id:
        return JsonResponse(
            {"message": "Company ids are required"}, status=HTTP_400_BAD_REQUEST
        )
    ids = lst_id.split(",")
    not_found = removeFromBlacklist(ids)
    if not_found:
        return JsonResponse(
            {"message": f"Companies not found: {', '.join(not_found)}"},
            status=HTTP_400_BAD_REQUEST,
        )
    return JsonResponse({"message": "Success"}, status=HTTP_200_OK)


# ---------------------------------------- getBlacklist ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_BlacklistCompany",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getBlacklist(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    paginator, data, showing_columns = getBlacklistData(request)
    return JsonResponse(
        {
            "message": "Success",
            "meta": {"columns": showing_columns},
            "pagination": paginator,
            "data": data,
        },
        status=HTTP_200_OK,
    )
