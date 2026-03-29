"""
Email Services - HTTP Handler Layer
Handles email-related API endpoints
"""
from __future__ import annotations

import imaplib
import os
import traceback
from datetime import datetime
from uuid import uuid4

from django.db import transaction
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

from neuxo_backend.controller.email_controller import (
    create_email_template,
    create_or_update_signature,
    delete_email_template,
    delete_signature,
    get_email_conversations,
    get_email_templates,
    get_mail_conversation_details,
    get_signatures,
    set_follow_up_date,
    update_email_record,
    update_email_template,
)
from neuxo_backend.models import MailAppAccount
from neuxo_backend.tasks import enqueue_mail_account_crawl
from neuxo_backend.services.utils import (
    PARAMETERS,
    PARAMETERS_EMAIL,
    getParams,
    getUserID,
)
from users.utils.crypto_hash import encrypt_password
from users.utils.utils import requireLogin


# ---------------------------------------- Email Account Management ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["email", "password"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_saveEmailAccount",
    tags=["Email Management"],
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def saveEmailAccount(request: HttpRequest) -> JsonResponse:
    """Add a new email account (Gmail with app password)"""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = request.data
        email = data.get("email", None)
        password = data.get("password", None)

        if not email or not password:
            return JsonResponse(
                {"message": "Email and password are required"},
                status=HTTP_400_BAD_REQUEST,
            )

        email = email.strip().lower()
        password = password.strip()
        user_id = getUserID(request)

        # Check if account already exists
        existing = MailAppAccount.objects.filter(
            user__id=user_id, email=email
        ).first()
        if existing:
            return JsonResponse(
                {"message": "Email account already exists"},
                status=HTTP_400_BAD_REQUEST,
            )

        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email.lower().strip(), password)
            mail.logout()
        except imaplib.IMAP4.error:
            return JsonResponse(
                {
                    "message": "Cannot connect to Gmail with this app password. Please verify IMAP is enabled and the app password is correct."
                },
                status=HTTP_400_BAD_REQUEST,
            )

        encrypted_password = encrypt_password(password)

        account = MailAppAccount.objects.create(
            email=email,
            password_app=encrypted_password,
            user_id=user_id,
        )

        transaction.on_commit(
            lambda: enqueue_mail_account_crawl.delay(str(account.id))
        )

        return JsonResponse(
            {
                "message": "Email account added successfully. Mailbox crawl has been queued and will run in the background."
            },
            status=HTTP_200_OK,
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Email Conversations ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS_EMAIL + PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllConversation",
    tags=["Email Management"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllConversationStatic(request: HttpRequest) -> JsonResponse:
    """Get all email conversations with statistics"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)

        # Get parameters
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 100))
        email_status = request.GET.get("email_status", None)
        email_count_start = int(request.GET.get("email_count_start", 0))
        email_count_end = int(request.GET.get("email_count_end", 10000))
        search_key = request.GET.get("search_key", None)
        last_activity_start_date = request.GET.get("last_activity_start_date", None)
        last_activity_end_date = request.GET.get("last_activity_end_date", None)
        follow_up_status = request.GET.get("follow_up_status", None)
        priority = request.GET.get("priority", None)
        time_zone = request.GET.get("time_zone", "Asia/Saigon")

        pagination, data = get_email_conversations(
            user_id=user_id,
            page=page,
            limit=limit,
            email_status=email_status,
            email_count_start=email_count_start,
            email_count_end=email_count_end,
            search_key=search_key,
            last_activity_start_date=last_activity_start_date,
            last_activity_end_date=last_activity_end_date,
            follow_up_status=follow_up_status,
            priority=priority,
            time_zone=time_zone,
        )

        return JsonResponse(
            {"message": "Success", "pagination": pagination, "data": data},
            status=HTTP_200_OK,
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    parameters=[
        *PARAMETERS,
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getMailDetails",
    tags=["Email Management"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getMailConversation(request: HttpRequest) -> JsonResponse:
    """Get email conversation thread details"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        target_mail = request.GET.get("target_mail", None)
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 50))

        if not target_mail:
            return JsonResponse(
                {"message": "target_mail is required"}, status=HTTP_400_BAD_REQUEST
            )

        pagination, data = get_mail_conversation_details(
            user_id=user_id, target_mail=target_mail, page=page, limit=limit
        )

        return JsonResponse(
            {"message": "Success", "pagination": pagination, "data": data},
            status=HTTP_200_OK,
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Email Templates ---------------------------------------- #


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getEmailTemplates",
    tags=["Email Template"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getEmailTemplate(request: HttpRequest) -> JsonResponse:
    """Get all email templates for the user"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        templates = get_email_templates(user_id)

        return JsonResponse(
            {"message": "Success", "data": templates}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getEmailTemplateById",
    tags=["Email Template"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getEmailTemplateById(request: HttpRequest, id: str) -> JsonResponse:
    """Get email template by ID"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        from neuxo_backend.models import EmailTemplate

        template = EmailTemplate.objects.filter(id=id, user__id=user_id).values(
            "id",
            "template_name",
            "template_subject",
            "template_content",
            "attachments",
        ).first()

        if not template:
            return JsonResponse(
                {"message": "Template not found"}, status=HTTP_400_BAD_REQUEST
            )

        return JsonResponse({"message": "Success", "data": template}, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "template_name": {"type": "string"},
                "template_subject": {"type": "string"},
                "template_content": {"type": "string"},
                "attachments": {"type": "array"},
            },
            "required": ["template_name", "template_subject", "template_content"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="POST_createEmailTemplate",
    tags=["Email Template"],
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def createEmailTemplate(request: HttpRequest) -> JsonResponse:
    """Create a new email template"""
    if request.method != "POST":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        data = request.data

        template_name = data.get("template_name")
        template_subject = data.get("template_subject")
        template_content = data.get("template_content")
        attachments = data.get("attachments", [])

        if not template_name or not template_subject or not template_content:
            return JsonResponse(
                {"message": "template_name, template_subject, and template_content are required"},
                status=HTTP_400_BAD_REQUEST,
            )

        result = create_email_template(
            user_id=user_id,
            template_name=template_name,
            template_subject=template_subject,
            template_content=template_content,
            attachments=attachments,
        )

        return JsonResponse(
            {"message": "Template created successfully", "data": result},
            status=HTTP_200_OK,
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "template_name": {"type": "string"},
                "template_subject": {"type": "string"},
                "template_content": {"type": "string"},
                "attachments": {"type": "array"},
            },
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_updateEmailTemplate",
    tags=["Email Template"],
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateEmailTemplate(request: HttpRequest, id: str) -> JsonResponse:
    """Update an existing email template"""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        data = request.data

        success = update_email_template(
            template_id=id,
            user_id=user_id,
            template_name=data.get("template_name"),
            template_subject=data.get("template_subject"),
            template_content=data.get("template_content"),
            attachments=data.get("attachments"),
        )

        if not success:
            return JsonResponse(
                {"message": "Template not found or no permission"},
                status=HTTP_400_BAD_REQUEST,
            )

        return JsonResponse(
            {"message": "Template updated successfully"}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="DELETE_deleteEmailTemplate",
    tags=["Email Template"],
)
@csrf_exempt
@api_view(["DELETE"])
@requireLogin
def deleteEmailTemplate(request: HttpRequest, id: str) -> JsonResponse:
    """Delete an email template"""
    if request.method != "DELETE":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        success = delete_email_template(template_id=id, user_id=user_id)

        if not success:
            return JsonResponse(
                {"message": "Template not found or no permission"},
                status=HTTP_400_BAD_REQUEST,
            )

        return JsonResponse(
            {"message": "Template deleted successfully"}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Signatures ---------------------------------------- #


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllSignatures",
    tags=["Email Signature"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAllSignatureMail(request: HttpRequest) -> JsonResponse:
    """Get all email signatures for the user"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        signatures = get_signatures(user_id)

        return JsonResponse(
            {"message": "Success", "data": signatures}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "signature_name": {"type": "string"},
                "signature_html": {"type": "string"},
                "email_account_id": {"type": "string"},
                "signature_id": {"type": "string"},
            },
            "required": ["signature_name", "signature_html"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_putSignature",
    tags=["Email Signature"],
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def putSignatureMail(request: HttpRequest) -> JsonResponse:
    """Create or update an email signature"""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        data = request.data

        signature_name = data.get("signature_name")
        signature_html = data.get("signature_html")
        email_account_id = data.get("email_account_id")
        signature_id = data.get("signature_id")

        if not signature_name or not signature_html:
            return JsonResponse(
                {"message": "signature_name and signature_html are required"},
                status=HTTP_400_BAD_REQUEST,
            )

        result = create_or_update_signature(
            user_id=user_id,
            signature_name=signature_name,
            signature_html=signature_html,
            email_account_id=email_account_id,
            signature_id=signature_id,
        )

        if not result:
            return JsonResponse(
                {"message": "Failed to create/update signature. No email account found."},
                status=HTTP_400_BAD_REQUEST,
            )

        return JsonResponse(
            {"message": "Signature saved successfully", "data": result},
            status=HTTP_200_OK,
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="DELETE_deleteSignature",
    tags=["Email Signature"],
)
@csrf_exempt
@api_view(["DELETE"])
@requireLogin
def deleteSignatureMail(request: HttpRequest, id: str) -> JsonResponse:
    """Delete an email signature"""
    if request.method != "DELETE":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        success = delete_signature(signature_id=id, user_id=user_id)

        if not success:
            return JsonResponse(
                {"message": "Signature not found or no permission"},
                status=HTTP_400_BAD_REQUEST,
            )

        return JsonResponse(
            {"message": "Signature deleted successfully"}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Email Record Management ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "target_email": {"type": "string"},
                "note": {"type": "string"},
                "priority": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            },
            "required": ["target_email"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_updateRecord",
    tags=["Email Management"],
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def updateRecord(request: HttpRequest) -> JsonResponse:
    """Update email record note and priority"""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        data = request.data

        target_email = data.get("target_email")
        if not target_email:
            return JsonResponse(
                {"message": "target_email is required"}, status=HTTP_400_BAD_REQUEST
            )

        note = data.get("note")
        priority = data.get("priority")

        success = update_email_record(
            user_id=user_id, target_email=target_email, note=note, priority=priority
        )

        return JsonResponse(
            {"message": "Record updated successfully"}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "target_email": {"type": "string"},
                "follow_up_date": {"type": "string"},
            },
            "required": ["target_email"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_setFollowUpDate",
    tags=["Email Management"],
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def setFollowUpDateForReplied(request: HttpRequest) -> JsonResponse:
    """Set follow-up date for an email"""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        data = request.data

        target_email = data.get("target_email")
        if not target_email:
            return JsonResponse(
                {"message": "target_email is required"}, status=HTTP_400_BAD_REQUEST
            )

        follow_up_date = data.get("follow_up_date")
        success = set_follow_up_date(
            user_id=user_id, target_email=target_email, follow_up_date=follow_up_date
        )

        return JsonResponse(
            {"message": "Follow-up date set successfully"}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)
