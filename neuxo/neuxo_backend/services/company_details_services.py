from __future__ import annotations

from datetime import timedelta

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
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
from neuxo_backend.models import LinkedinCompany
from neuxo_backend.models import Notification, UserNotification
from neuxo_backend.services import PARAMETERS
from users.models import Users
from users.utils.utils import requireLogin


# ---------------------------------------- getCompanyById ---------------------------------------- #


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


# ---------------------------------------- getEventsByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        all_data = getTriggerDataByCompanyId(id)
        return JsonResponse(
            {"message": "Success", "data": all_data.get("event", [])},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getJobsByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        all_data = getTriggerDataByCompanyId(id)
        return JsonResponse(
            {"message": "Success", "data": all_data.get("hiring", [])},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getContactsByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=[],
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        all_data = getTriggerDataByCompanyId(id)
        return JsonResponse(
            {"message": "Success", "data": all_data.get("contacts", [])},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getFundingByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        all_data = getTriggerDataByCompanyId(id)
        return JsonResponse(
            {"message": "Success", "data": all_data.get("funding", [])},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getTriggerByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        all_data = getTriggerDataByCompanyId(id)
        return JsonResponse(
            {"message": "Success", "data": all_data}, status=HTTP_200_OK
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- addTwitterForCompany ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"url_twitter": {"type": "string"}},
        }
    },
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        url_twitter = request.data.get("url_twitter")
        company = addTwitterUrl(id, url_twitter)
        if not company:
            return JsonResponse(
                {"message": "Company not found"}, status=HTTP_400_BAD_REQUEST
            )
        return JsonResponse(
            {"message": "Success", "data": {"link_twitter": url_twitter}},
            status=HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getListContactByCompanyID ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    company = LinkedinCompany.objects.filter(id=id).first()
    if not company:
        return JsonResponse(
            {"message": "Company not found"}, status=HTTP_400_BAD_REQUEST
        )
    data = getContactsWithDetails(id)
    return JsonResponse({"message": "Success", "data": data}, status=HTTP_200_OK)


# ---------------------------------------- addContactForCompany ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "linkedin_url": {"type": "string"},
                "twitter_url": {"type": "string"},
            },
            "required": ["linkedin_url"],
        }
    },
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        linkedin_url = request.data.get("linkedin_url", None)
        twitter_url = request.data.get("twitter_url", None)

        if not linkedin_url:
            return JsonResponse(
                {"message": "Linkedin url is required"}, status=HTTP_400_BAD_REQUEST
            )

        contact, error = _addContact(id, linkedin_url, twitter_url)
        if error:
            return JsonResponse({"message": error}, status=HTTP_400_BAD_REQUEST)
        return JsonResponse({"message": "Success"}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- addEmailForContact ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        }
    },
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        email = request.data.get("email", None)
        if not email:
            return JsonResponse(
                {"message": "Email is required"}, status=HTTP_400_BAD_REQUEST
            )
        error = addEmailToContact(id, email)
        if error:
            return JsonResponse({"message": error}, status=HTTP_400_BAD_REQUEST)
        return JsonResponse({"message": "Success"}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- removeEmailForContact ---------------------------------------- #


@extend_schema(
    request={},
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        error = removeEmailFromContact(id)
        if error:
            return JsonResponse({"message": error}, status=HTTP_400_BAD_REQUEST)
        return JsonResponse({"message": "Success"}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- updateEmailForContact ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        }
    },
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        email = request.data.get("email", None)
        if not email:
            return JsonResponse(
                {"message": "Email is required"}, status=HTTP_400_BAD_REQUEST
            )
        error = _updateEmail(contact_id, id, email)
        if error:
            return JsonResponse({"message": error}, status=HTTP_400_BAD_REQUEST)
        return JsonResponse({"message": "Success"}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- deleteContactCompany ---------------------------------------- #


@extend_schema(
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        user_id = request.user.get("id", None)
        error = deleteContact(user_id, id)
        if error:
            return JsonResponse({"message": error}, status=HTTP_400_BAD_REQUEST)
        return JsonResponse({"message": "Success"}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- getNotifyForCompany ---------------------------------------- #


@extend_schema(
    parameters=None,
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        current_user = request.user.get("id", None)
        seven_days_ago = timezone.now() - timedelta(days=7)

        company = LinkedinCompany.objects.filter(id=id).first()
        if not company:
            return JsonResponse(
                {"message": "Company not found"}, status=HTTP_400_BAD_REQUEST
            )

        count_notify_is_read = UserNotification.objects.filter(
            user_id=current_user,
            notification__company_id=id,
            notification__time_post__gte=seven_days_ago,
        ).count()
        count_notify_all = Notification.objects.filter(
            company_id=id, time_post__gte=seven_days_ago
        ).count()

        new_notify = count_notify_all - count_notify_is_read
        return JsonResponse(
            {"message": "Success", "new_notify": new_notify}, status=HTTP_200_OK
        )
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- seenNotifyForCompany ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "ids": {"type": "string", "example": '"id1", "id2"'},
            },
        }
    },
    responses={"200": "Success"},
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
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        user_id = request.user.get("id", None)
        notify_ids = request.data.get("ids")

        if not notify_ids:
            return JsonResponse(
                {"message": "Notify ids is required"}, status=HTTP_400_BAD_REQUEST
            )

        user = Users.objects.filter(id=user_id).first()
        notify_ids = notify_ids.split(",")
        for notify_id in notify_ids:
            notify = Notification.objects.filter(id=notify_id).first()
            if not notify:
                return JsonResponse(
                    {"message": "Notify not found"}, status=HTTP_400_BAD_REQUEST
                )

            check_exist_seen = UserNotification.objects.filter(
                user=user, notification=notify
            ).exists()
            if check_exist_seen:
                continue

            UserNotification.objects.create(user=user, notification=notify)

        return JsonResponse({"message": "Success"}, status=HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)
