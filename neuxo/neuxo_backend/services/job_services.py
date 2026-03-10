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

from neuxo_backend.controller.job_controller import (
    get_job_by_id,
    get_job_metadata,
    get_jobs_data,
    get_jobs_for_download,
)
from neuxo_backend.services import PARAMETERS
from users.utils.utils import requireLogin


# ---------------------------------------- getJobs ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS
    + [
        OpenApiParameter(
            name="category",
            description="category",
            required=False,
            type=str,
        ),
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_Jobs",
    tags=["Job"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getJobs(request: HttpRequest) -> JsonResponse:
    """Get paginated list of LinkedIn jobs with filtering and sorting."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        paginator, response_data, showing_columns = get_jobs_data(request)

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
    operation_id="GET_JobMetaData",
    tags=["Job"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getMetaData(request: HttpRequest) -> JsonResponse:
    """Get metadata for job filtering (countries/locations)."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        metadata = get_job_metadata()
        return JsonResponse(
            {"message": "Success", "data": metadata},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getJobById ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_JobById",
    tags=["Job"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getJobById(request: HttpRequest, id: str) -> JsonResponse:
    """Get detailed job information by ID."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        job_data = get_job_by_id(id)

        if not job_data:
            return JsonResponse(
                {"message": "No data found"}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse(
            {"message": "Success", "data": job_data},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- downloadJob ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_DownloadJobs",
    tags=["Job"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def downloadJob(request: HttpRequest) -> HttpResponse:
    """Download jobs data as Excel file."""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        excel_file = BytesIO()

        # Get data for download
        jobs_data = get_jobs_for_download(request)
        response_data = pd.DataFrame(jobs_data)

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
        response["Content-Disposition"] = 'attachment;filename="Jobs.xlsx"'

        return response
    except Exception as e:
        return JsonResponse(
            {"message": "Download failed", "exception": str(e)},
            status=HTTP_400_BAD_REQUEST,
        )
