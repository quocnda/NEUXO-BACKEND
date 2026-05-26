from __future__ import annotations

from datetime import timedelta

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from pydantic import ValidationError
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from neuxo_backend.controller.company_details_controller import (
    addContactForCompany as _addContact,
    addEmailToContact,
    addTwitterUrl,
    deleteContact,
    getCompanyDetailById,
    getContactsWithDetails,
    getTriggerDataByCompanyId,
    removeEmailFromContact,
    updateEmailForContact as _updateEmail,
)
from neuxo_backend.dto.company_dto import CompanyDetailResponse, MessageResponse
from neuxo_backend.dto.company_details_dto import (
    AddContactForCompanyRequest,
    AddEmailForContactRequest,
    AddTwitterForCompanyRequest,
    AddTwitterForCompanyResponse,
    CompanyContactDetailResponse,
    CompanyContactsResponse,
    CompanyEventsResponse,
    CompanyFundingResponse,
    CompanyJobsResponse,
    CompanyNotifyResponse,
    CompanyTriggerResponse,
    SeenNotifyForCompanyRequest,
    UpdateEmailForContactRequest,
)
from neuxo_backend.models import LinkedinCompany
from neuxo_backend.models import Notification, UserNotification
from neuxo_backend.services import PARAMETERS
from users.models import Users
from users.utils.utils import requireLogin


def _message_response(message: str, status_code: int) -> JsonResponse:
    response = MessageResponse(message=message)
    return JsonResponse(response.model_dump(), status=status_code)


def _parse_request(model_cls, payload):
    try:
        return model_cls.model_validate(payload), None
    except ValidationError as exc:
        return None, exc


# ---------------------------------------- getCompanyById ---------------------------------------- #


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
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        user_id = request.user.get("id", None)
        data = getCompanyDetailById(user_id, id)
        if not data:
            return _message_response("No data found", HTTP_400_BAD_REQUEST)
        response = CompanyDetailResponse(message="Success", data=data)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        import traceback

        traceback.print_exc()
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- getEventsByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={200: CompanyEventsResponse},
    auth=None,
    operation_id="GET_EventsByCompanyID",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getEventsByCompanyID(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        all_data = getTriggerDataByCompanyId(id)
        response = CompanyEventsResponse(
            message="Success", data=all_data.get("event", [])
        )
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- getJobsByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={200: CompanyJobsResponse},
    auth=None,
    operation_id="GET_JobsByCompanyID",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getJobsByCompanyID(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        all_data = getTriggerDataByCompanyId(id)
        response = CompanyJobsResponse(
            message="Success", data=all_data.get("hiring", [])
        )
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- getContactsByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={200: CompanyContactsResponse},
    auth=None,
    operation_id="GET_ContactsByCompanyID",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getContactsByCompanyID(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        all_data = getTriggerDataByCompanyId(id)
        response = CompanyContactsResponse(
            message="Success", data=all_data.get("contacts", [])
        )
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- getFundingByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={200: CompanyFundingResponse},
    auth=None,
    operation_id="GET_FundingByCompanyID",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getFundingByCompanyID(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        all_data = getTriggerDataByCompanyId(id)
        response = CompanyFundingResponse(
            message="Success", data=all_data.get("funding", [])
        )
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- getTriggerByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={200: CompanyTriggerResponse},
    auth=None,
    operation_id="GET_TriggerByCompanyID",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getTriggerByCompanyID(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        all_data = getTriggerDataByCompanyId(id)
        response = CompanyTriggerResponse(message="Success", data=all_data)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- addTwitterForCompany ---------------------------------------- #


@extend_schema(
    request=AddTwitterForCompanyRequest,
    responses={200: AddTwitterForCompanyResponse},
    auth=None,
    operation_id="POST_addTwitterForCompany",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def addTwitterForCompany(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "POST":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        request_dto, error = _parse_request(AddTwitterForCompanyRequest, request.data)
        if error:
            return _message_response("Invalid request payload", HTTP_400_BAD_REQUEST)

        url_twitter = request_dto.url_twitter
        company = addTwitterUrl(id, url_twitter)
        if not company:
            return _message_response("Company not found", HTTP_400_BAD_REQUEST)
        response = AddTwitterForCompanyResponse(
            message="Success", data={"link_twitter": url_twitter}
        )
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- getListContactByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={200: CompanyContactDetailResponse},
    auth=None,
    operation_id="GET_ListContactByCompanyID",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getListContactByCompanyID(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    company = LinkedinCompany.objects.filter(id=id).first()
    if not company:
        return _message_response("Company not found", HTTP_400_BAD_REQUEST)
    data = getContactsWithDetails(id)
    response = CompanyContactDetailResponse(message="Success", data=data)
    return JsonResponse(response.model_dump(), status=HTTP_200_OK)


# ---------------------------------------- addContactForCompany ---------------------------------------- #


@extend_schema(
    request=AddContactForCompanyRequest,
    responses={200: MessageResponse},
    auth=None,
    operation_id="POST_addContactForCompany",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def addContactForCompany(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "POST":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        request_dto, error = _parse_request(AddContactForCompanyRequest, request.data)
        if error:
            return _message_response("Linkedin url is required", HTTP_400_BAD_REQUEST)

        linkedin_url = request_dto.linkedin_url
        twitter_url = request_dto.twitter_url

        if not linkedin_url:
            return _message_response("Linkedin url is required", HTTP_400_BAD_REQUEST)

        contact, error = _addContact(id, linkedin_url, twitter_url)
        if error:
            return _message_response(error, HTTP_400_BAD_REQUEST)
        response = MessageResponse(message="Success")
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- addEmailForContact ---------------------------------------- #


@extend_schema(
    request=AddEmailForContactRequest,
    responses={200: MessageResponse},
    auth=None,
    operation_id="POST_addEmailForContact",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def addEmailForContact(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "POST":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        request_dto, error = _parse_request(AddEmailForContactRequest, request.data)
        if error:
            return _message_response("Email is required", HTTP_400_BAD_REQUEST)

        email = request_dto.email
        if not email:
            return _message_response("Email is required", HTTP_400_BAD_REQUEST)
        error = addEmailToContact(id, email)
        if error:
            return _message_response(error, HTTP_400_BAD_REQUEST)
        response = MessageResponse(message="Success")
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- removeEmailForContact ---------------------------------------- #


@extend_schema(
    request={},
    responses={200: MessageResponse},
    auth=None,
    operation_id="DELETE_removeEmailForContact",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["DELETE"])
@requireLogin
def removeEmailForContact(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "DELETE":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        error = removeEmailFromContact(id)
        if error:
            return _message_response(error, HTTP_400_BAD_REQUEST)
        response = MessageResponse(message="Success")
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- updateEmailForContact ---------------------------------------- #


@extend_schema(
    request=UpdateEmailForContactRequest,
    responses={200: MessageResponse},
    auth=None,
    operation_id="PUT_updateEmailForContact",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateEmailForContact(
    request: HttpRequest, contact_id: str, id: str
) -> JsonResponse:
    if request.method != "PUT":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        request_dto, error = _parse_request(UpdateEmailForContactRequest, request.data)
        if error:
            return _message_response("Email is required", HTTP_400_BAD_REQUEST)

        email = request_dto.email
        if not email:
            return _message_response("Email is required", HTTP_400_BAD_REQUEST)
        error = _updateEmail(contact_id, id, email)
        if error:
            return _message_response(error, HTTP_400_BAD_REQUEST)
        response = MessageResponse(message="Success")
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- deleteContactCompany ---------------------------------------- #


@extend_schema(
    responses={200: MessageResponse},
    auth=None,
    operation_id="PUT_deleteContactCompany",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def deleteContactCompany(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "PUT":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        user_id = request.user.get("id", None)
        error = deleteContact(user_id, id)
        if error:
            return _message_response(error, HTTP_400_BAD_REQUEST)
        response = MessageResponse(message="Success")
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- getNotifyForCompany ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={200: CompanyNotifyResponse},
    auth=None,
    operation_id="GET_NotifyForCompany",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getNotifyForCompany(request: HttpRequest, id: str) -> JsonResponse:
    if request.method != "GET":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        current_user = request.user.get("id", None)
        seven_days_ago = timezone.now() - timedelta(days=1024)

        company = LinkedinCompany.objects.filter(id=id).first()
        if not company:
            return _message_response("Company not found", HTTP_400_BAD_REQUEST)

        count_notify_is_read = UserNotification.objects.filter(
            user_id=current_user,
            notification__company_id=id,
            notification__time_post__gte=seven_days_ago,
        ).count()
        count_notify_all = Notification.objects.filter(
            company_id=id, time_post__gte=seven_days_ago
        ).count()

        new_notify = count_notify_all - count_notify_is_read
        response = CompanyNotifyResponse(message="Success", new_notify=new_notify)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)


# ---------------------------------------- seenNotifyForCompany ---------------------------------------- #


@extend_schema(
    request=SeenNotifyForCompanyRequest,
    responses={200: MessageResponse},
    auth=None,
    operation_id="POST_seenNotifyForCompany",
    tags=["Company"],
    operation=None,
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def seenNotifyForCompany(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return _message_response("Invalid request method", HTTP_405_METHOD_NOT_ALLOWED)
    try:
        user_id = request.user.get("id", None)

        request_dto, error = _parse_request(SeenNotifyForCompanyRequest, request.data)
        if error:
            return _message_response("Notify ids is required", HTTP_400_BAD_REQUEST)

        notify_ids = request_dto.ids

        if not notify_ids:
            return _message_response("Notify ids is required", HTTP_400_BAD_REQUEST)

        user = Users.objects.filter(id=user_id).first()
        notify_ids = notify_ids.split(",")
        for notify_id in notify_ids:
            notify = Notification.objects.filter(id=notify_id).first()
            if not notify:
                return _message_response("Notify not found", HTTP_400_BAD_REQUEST)

            check_exist_seen = UserNotification.objects.filter(
                user=user, notification=notify
            ).exists()
            if check_exist_seen:
                continue

            UserNotification.objects.create(user=user, notification=notify)

        response = MessageResponse(message="Success")
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)
    except Exception as e:
        return _message_response(str(e), HTTP_400_BAD_REQUEST)
