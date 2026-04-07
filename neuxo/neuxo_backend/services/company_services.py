from __future__ import annotations

from django.http import HttpRequest, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_400_BAD_REQUEST,
)
from neuxo_backend.controller.company_controller import (
    getDataCompany,
    updateShowingColumnsData,
)
from neuxo_backend.controller.company_details_controller import (
    getCompanyDetailById,
)
from users.utils.utils import requireLogin
from neuxo_backend.services import PARAMETERS
from neuxo_backend.controller.utils import getShowingColumns, getShowingColumnsCustom
from neuxo_backend.models import LinkedinCompany, SalesPerson
from io import BytesIO

import pandas as pd


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


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_AllSales",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllSales(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    sales_data = list(SalesPerson.objects.all().values_list("name", flat=True))
    sales_data.append("None")

    return JsonResponse(
        {"message": "Success", "data": sales_data},
        status=HTTP_200_OK,
    )


# ---------------------------------------- listCountryCompany ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_listCountryCompany",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def listCountryCompany(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    list_country = (
        LinkedinCompany.objects.filter(country__isnull=False, country__gt="")
        .exclude(country="Vietnam")
        .values_list("country", flat=True)
        .distinct()
        .order_by("country")
    )
    industry = (
        LinkedinCompany.objects.filter(industry__isnull=False)
        .exclude(country="Vietnam")
        .values_list("industry", flat=True)
        .distinct()
        .order_by("industry")
    )
    organization_type = (
        LinkedinCompany.objects.filter(organization_type__isnull=False)
        .exclude(country="Vietnam")
        .values_list("organization_type", flat=True)
        .distinct()
        .order_by("organization_type")
    )

    return JsonResponse(
        {
            "message": "Success",
            "data": {
                "list_country": list(list_country),
                "industry": list(industry),
                "organization_type": list(organization_type),
                "trigger": ["event", "funding", "news", "hiring"],
            },
        },
        status=HTTP_200_OK,
    )


# ---------------------------------------- updateShowingColumns ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "name_columns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "is_show": {"type": "boolean"},
                            "can_arrange": {"type": "boolean"},
                        },
                    },
                }
            },
            "required": ["name_columns"],
        }
    },
    responses=None,
    auth=None,
    operation_id="PUT_updateShowingColumns",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateShowingColumns(request: HttpRequest) -> JsonResponse:
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    data = request.data
    name_columns_and_status = data.get("name_columns", [])
    userId = request.user.get("id", None)

    if not name_columns_and_status:
        return JsonResponse({"message": "Data is empty"}, status=HTTP_400_BAD_REQUEST)

    showing_columns = updateShowingColumnsData(userId, name_columns_and_status)
    return JsonResponse(
        {"message": "Success", "data": {"columns": showing_columns}},
        status=HTTP_200_OK,
    )


# ---------------------------------------- downloadMatchingCompany ---------------------------------------- #


@csrf_exempt
@api_view(["GET"])
@requireLogin
def downloadMatchingCompany(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    _, output_data, _ = getDataCompany(request)
    response_data = pd.DataFrame(list(output_data))

    response_data["company_size"] = response_data["company_size"].apply(
        lambda x: f"'{x}" if x else x
    )
    response_data["linkedin"] = response_data["external"].apply(
        lambda x: x.get("linkedin") if isinstance(x, dict) else None
    )
    response_data["website"] = response_data["external"].apply(
        lambda x: x.get("website") if isinstance(x, dict) else None
    )
    response_data["twitter"] = response_data["external"].apply(
        lambda x: x.get("twitter") if isinstance(x, dict) else None
    )
    response_data = response_data.drop(columns=["external"])

    excel_file = BytesIO()
    response_data.to_excel(excel_file, index=False, engine="openpyxl")
    excel_file.seek(0)

    response = HttpResponse(
        excel_file,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="matching_companies.xlsx"'
    return response


# ---------------------------------------- getColumnField ---------------------------------------- #


@extend_schema(
    parameters=[
        OpenApiParameter(name="table", description="table", required=False, type=str)
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_columnField",
    tags=["Matching"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getColumnField(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    table = request.GET.get("table", None)
    if table:
        showing_columns = getShowingColumnsCustom(table, request)
    else:
        showing_columns = getShowingColumns(request.user.get("id", None))

    return JsonResponse(
        {"message": "Success", "columns": showing_columns}, status=HTTP_200_OK
    )


# -------------------------------------- Show company detail --------------------------------------#


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_CompanyById",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getCompanyById(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        user_id = request.user.get("id", None)
        data = getCompanyDetailById(user_id, id)
        if not data:
            return JsonResponse(
                {"message": "No data found"}, status=HTTP_400_BAD_REQUEST
            )
        return JsonResponse({"message": "Success", "data": data}, status=HTTP_200_OK)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)
