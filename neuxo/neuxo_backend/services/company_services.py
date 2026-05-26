from __future__ import annotations

from django.http import HttpRequest, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from pydantic import ValidationError
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
from neuxo_backend.models import LinkedinCompany
from neuxo_backend.dto.company_dto import (
    AddCompanyNoteRequest,
    AddCompanyNoteResponse,
    ColumnFieldResponse,
    CompanyDetailData,
    CompanyDetailResponse,
    CountryCompanyData,
    CountryCompanyResponse,
    MatchingCompanyMeta,
    MatchingCompanyResponse,
    MessageResponse,
    ShowingColumn,
    UpdateShowingColumnsData,
    UpdateShowingColumnsRequest,
    UpdateShowingColumnsResponse,
    ValidationErrorResponse,
)
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
    responses={200: MatchingCompanyResponse},
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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

    print("Ready for geting data")
    paginator, output_data, showing_columns = getDataCompany(request)
    response = MatchingCompanyResponse(
        message="Success",
        meta=MatchingCompanyMeta(columns=showing_columns),
        pagination=paginator,
        data=output_data,
    )
    return JsonResponse(response.model_dump(), status=HTTP_200_OK)


# @extend_schema(
#     parameters=[],
#     responses={200: SalesListResponse},
#     auth=None,
#     operation_id="GET_AllSales",
#     tags=["Matching"],
#     operation=None,
# )
# @csrf_exempt
# @api_view(["GET"])
# @requireLogin
# def getAllSales(request: HttpRequest) -> JsonResponse:
#     if request.method != "GET":
#         response = MessageResponse(message="Invalid request method")
#         return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

#     sales_data = list(SalesPerson.objects.all().values_list("name", flat=True))
#     sales_data.append("None")

#     response = SalesListResponse(message="Success", data=sales_data)
#     return JsonResponse(response.model_dump(), status=HTTP_200_OK)


# ---------------------------------------- listCountryCompany ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={200: CountryCompanyResponse},
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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

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

    response = CountryCompanyResponse(
        message="Success",
        data=CountryCompanyData(
            list_country=list(list_country),
            industry=list(industry),
            organization_type=list(organization_type),
            trigger=["event", "funding", "news", "hiring"],
        ),
    )
    return JsonResponse(response.model_dump(), status=HTTP_200_OK)


# ---------------------------------------- updateShowingColumns ---------------------------------------- #


@extend_schema(
    request=UpdateShowingColumnsRequest,
    responses={200: UpdateShowingColumnsResponse},
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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)
    data = request.data
    name_columns_and_status = data.get("name_columns", [])
    userId = request.user.get("id", None)

    if not name_columns_and_status:
        response = MessageResponse(message="Data is empty")
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

    try:
        payload = UpdateShowingColumnsRequest.model_validate(data)
    except ValidationError as exc:
        response = ValidationErrorResponse(
            message="Invalid payload",
            errors=exc.errors(),
        )
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

    name_columns_and_status = payload.name_columns

    showing_columns = updateShowingColumnsData(userId, name_columns_and_status)
    normalized_columns = [
        ShowingColumn.model_validate(item) for item in showing_columns
    ]
    response = UpdateShowingColumnsResponse(
        message="Success",
        data=UpdateShowingColumnsData(columns=normalized_columns),
    )
    return JsonResponse(response.model_dump(), status=HTTP_200_OK)


# ---------------------------------------- downloadMatchingCompany ---------------------------------------- #


@csrf_exempt
@api_view(["GET"])
@requireLogin
def downloadMatchingCompany(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)
    _, output_data, _ = getDataCompany(request)
    response_data = pd.DataFrame([item.model_dump() for item in output_data])

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
    responses={200: ColumnFieldResponse},
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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)
    table = request.GET.get("table", None)
    if table:
        showing_columns = getShowingColumnsCustom(table, request)
    else:
        showing_columns = getShowingColumns(request.user.get("id", None))

    normalized_columns = [
        ShowingColumn.model_validate(item) for item in showing_columns
    ]
    response = ColumnFieldResponse(message="Success", columns=normalized_columns)
    return JsonResponse(response.model_dump(), status=HTTP_200_OK)


# -------------------------------------- Show company detail --------------------------------------#


@extend_schema(
    parameters=[],
    responses={200: CompanyDetailResponse},
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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)
    try:
        user_id = request.user.get("id", None)
        data = getCompanyDetailById(user_id, id)
        if not data:
            response = MessageResponse(message="No data found")
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)
        normalized = CompanyDetailData.model_validate(data)
        response = CompanyDetailResponse(message="Success", data=normalized)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        import traceback

        traceback.print_exc()
        response = MessageResponse(message=str(e))
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)


@extend_schema(
    request=AddCompanyNoteRequest,
    responses={200: AddCompanyNoteResponse},
    auth=None,
    operation_id="GET_CompanyNote",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def addNoteCompanyFromUser(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)
    data = request.data
    if data == {}:
        response = MessageResponse(message="Data is empty")
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)
    if len(data) == 0:
        response = MessageResponse(message="Data is empty")
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)
    if "company_id" not in data[0]:
        response = MessageResponse(message="Company_id is required")
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)
    if "note" not in data[0]:
        response = MessageResponse(message="Note is required")
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)
    try:
        payload = AddCompanyNoteRequest.model_validate(data)
    except ValidationError as exc:
        response = ValidationErrorResponse(
            message="Invalid payload",
            errors=exc.errors(),
        )
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)
    for item in payload.root:
        company_id = item.company_id
        note_user = item.note
        LinkedinCompany.objects.filter(id=company_id).update(note_of_user=note_user)
    response = AddCompanyNoteResponse(
        message="Success", data="Update note to database successfully"
    )
    return JsonResponse(response.model_dump(), status=HTTP_200_OK)
