from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_405_METHOD_NOT_ALLOWED,
)
from neuxo_backend.controller.company_controller import getDataCompany
from users.utils.utils import requireLogin
from neuxo_backend.services import PARAMETERS


@extend_schema(
    parameters=PARAMETERS
    + [
        OpenApiParameter(
            name="count_trigger",
            description="count_trigger",
            required=False,
            type=int,
            enum=[1, 2, 3, 4],
        ),
        OpenApiParameter(
            name="assignee", description="assignee", required=False, type=str
        ),
        OpenApiParameter(
            name="country", description="country", required=False, type=str
        ),
        OpenApiParameter(
            name="company_size", description="company_size", required=False, type=str
        ),
        OpenApiParameter(
            name="followers", description="followers", required=False, type=str
        ),
        OpenApiParameter(
            name="industry", description="industry", required=False, type=str
        ),
        OpenApiParameter(
            name="trigger", description="trigger", required=False, type=str
        ),
        OpenApiParameter(
            name="organization_type",
            description="organization_type",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="category", description="category", required=False, type=str
        ),
        OpenApiParameter(
            name="company_email", description="company_email", required=False, type=str
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_MatchingCompany",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getMatchingCompany(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    print("Ready for geting data")
    paginator, output_data, showing_columns = getDataCompany(request)
    return JsonResponse(
        {
            "message": "Success",
            "meta": {"columns": showing_columns},
            "pagination": paginator,
            "data": list(output_data),
        },
        status=HTTP_200_OK,
    )
