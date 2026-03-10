from __future__ import annotations

from io import BytesIO

import pandas as pd
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from neuxo_backend.controller.funding_controller import (
    get_funding_by_id,
    get_funding_metadata,
    get_fundings_data,
    get_fundings_for_download,
)
from neuxo_backend.services import PARAMETERS
from users.utils.utils import requireLogin


# ---------------------------------------- getFundings ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS
    + [
        OpenApiParameter(
            name="category", description="categories", required=False, type=str
        ),
        OpenApiParameter(name="round", description="rounds", required=False, type=str),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_Fundings",
    tags=["Funding"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getFundings(request: HttpRequest) -> JsonResponse:
    """Get paginated list of fundings with filtering and sorting."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        paginator, response_data, showing_columns = get_fundings_data(request)

        return JsonResponse(
            {
                "message": "Success",
                "meta": {"columns": showing_columns},
                "pagination": paginator,
                "data": response_data,
            },
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getMetaData ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_FundingMetaData",
    tags=["Funding"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getMetaData(request: HttpRequest) -> JsonResponse:
    """Get metadata for funding filtering (rounds and categories)."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        metadata = get_funding_metadata()
        return JsonResponse(
            {"message": "Success", "data": metadata},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getFundingByID ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_FundingById",
    tags=["Funding"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getFundingByID(request: HttpRequest, id: str) -> JsonResponse:
    """Get detailed funding information by ID."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        funding_data = get_funding_by_id(id)

        if not funding_data:
            return JsonResponse(
                {"message": "No data found"}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse(
            {"message": "Success", "data": funding_data},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- downloadFunding ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_DownloadFundings",
    tags=["Funding"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def downloadFunding(request: HttpRequest) -> HttpResponse:
    """Download fundings data as Excel file."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        excel_file = BytesIO()

        # Get data for download
        fundings_data = get_fundings_for_download(request)
        response_data = pd.DataFrame(fundings_data)

        # Convert timezone-aware datetime columns to timezone-unaware
        for col in response_data.select_dtypes(
            include=["datetime64[ns, UTC]", "datetime64[ns]"]
        ):
            response_data[col] = pd.to_datetime(response_data[col]).dt.tz_localize(None)

        # Write to Excel
        response_data.to_excel(excel_file, index=False, engine="openpyxl")
        excel_file.seek(0)

        # Create HTTP response
        response = HttpResponse(
            excel_file,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment;filename="Fundings.xlsx"'

        return response
    except Exception as e:
        return JsonResponse(
            {"message": "Download failed", "exception": str(e)},
            status=HTTP_400_BAD_REQUEST,
        )
