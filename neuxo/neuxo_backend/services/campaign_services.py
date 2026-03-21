"""
Campaign Services - HTTP Handler Layer
Handles email campaign/sequence related API endpoints
"""
from __future__ import annotations

import traceback
from datetime import datetime

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from neuxo_backend.controller.campaign_controller import (
    edit_campaign_name,
    get_campaign_about,
    get_campaign_details,
    get_campaigns,
    update_campaign_status,
)
from neuxo_backend.services.utils import PARAMETERS, PARAMETERS_EMAIL, getUserID
from users.utils.utils import requireLogin, requireRoles


# ---------------------------------------- Campaign List ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS
    + [
        OpenApiParameter(
            name="campaign_status",
            description="Campaign status filter (Active,Paused,Completed)",
            required=False,
            type=str,
        )
    ],
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getCampaignStatic",
    tags=["Campaign Management"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getCampaignStatic(request: HttpRequest) -> JsonResponse:
    """Get all campaigns with statistics"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        if not user_id:
            return JsonResponse(
                {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
            )

        # Parse parameters
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")
        campaign_status = request.GET.get("campaign_status")
        search_key = request.GET.get("search_key")

        if start_date:
            start_date = datetime.strptime(start_date.strip(), "%Y-%m-%d %H:%M:%S")
        if end_date:
            end_date = datetime.strptime(end_date.strip(), "%Y-%m-%d %H:%M:%S")

        pagination, data = get_campaigns(
            user_id=user_id,
            page=page,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            campaign_status=campaign_status,
            search_key=search_key,
        )

        return JsonResponse(
            {"message": "Success", "pagination": pagination, "data": data},
            status=HTTP_200_OK,
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Update Campaign Status ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "status_campaign": {
                    "type": "string",
                    "enum": ["Resume", "Pause", "Stop", "Remove"],
                }
            },
            "required": ["status_campaign"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="POST_updateStatusCampaign",
    tags=["Campaign Management"],
)
@csrf_exempt
@api_view(["POST"])
@requireLogin
def updateStatusCampaign(request: HttpRequest, id: str) -> JsonResponse:
    """Update campaign status (Resume/Pause/Stop/Remove)"""
    if request.method != "POST":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        if not user_id:
            return JsonResponse(
                {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
            )

        status_campaign = request.data.get("status_campaign")
        if not status_campaign:
            return JsonResponse(
                {"message": "status_campaign is required"},
                status=HTTP_400_BAD_REQUEST,
            )

        success, message = update_campaign_status(
            campaign_id=id, user_id=user_id, new_status=status_campaign
        )

        if not success:
            return JsonResponse({"message": message}, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": message}, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Campaign Details ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS_EMAIL + PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getDetailCampaign",
    tags=["Campaign Management"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getDetailCampaign(request: HttpRequest, id: str) -> JsonResponse:
    """Get detailed campaign information"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        if not user_id:
            return JsonResponse(
                {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
            )

        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 50))
        email_status = request.GET.get("email_status")

        success, result = get_campaign_details(
            campaign_id=id,
            user_id=user_id,
            page=page,
            limit=limit,
            email_status=email_status,
        )

        if not success:
            return JsonResponse(result, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": "Success", "data": result}, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Campaign About ---------------------------------------- #


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAboutCampaign",
    tags=["Campaign Management"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
def getAboutCampaign(request: HttpRequest, id: str) -> JsonResponse:
    """Get campaign about information"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        if not user_id:
            return JsonResponse(
                {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
            )

        success, result = get_campaign_about(campaign_id=id, user_id=user_id)

        if not success:
            return JsonResponse(result, status=HTTP_400_BAD_REQUEST)

        return JsonResponse({"message": "Success", "data": result}, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Admin: Get All Email Stats ---------------------------------------- #


@extend_schema(
    parameters=PARAMETERS,
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_getAllEmailStaticByAdmin",
    tags=["Campaign Management"],
)
@csrf_exempt
@api_view(["GET"])
@requireLogin
@requireRoles(["Admin"])
def getAllEmailStaticByAdmin(request: HttpRequest) -> JsonResponse:
    """Admin: Get total email statistics across all users"""
    if request.method != "GET":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        from neuxo_backend.models import MailHistory, SequenceEmail
        from django.db.models import Count, Sum

        # Get overall statistics
        total_campaigns = SequenceEmail.objects.exclude(
            sequence_status="PENDING"
        ).count()

        email_stats = MailHistory.objects.aggregate(
            total_sent=Count("id", filter=models.Q(type="SEND")),
            total_received=Count("id", filter=models.Q(type="RECIEVE")),
        )

        result = {
            "total_campaigns": total_campaigns,
            "total_emails_sent": email_stats.get("total_sent", 0),
            "total_emails_received": email_stats.get("total_received", 0),
        }

        return JsonResponse({"message": "Success", "data": result}, status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)


# ---------------------------------------- Edit Campaign Name ---------------------------------------- #


@extend_schema(
    request={
        "application/json": {
            "type": "object",
            "properties": {"campaign_name": {"type": "string"}},
            "required": ["campaign_name"],
        }
    },
    responses={"200": "Success"},
    auth=None,
    operation_id="PUT_editNameCampaign",
    tags=["Campaign Management"],
)
@csrf_exempt
@api_view(["PUT"])
@requireLogin
def editNameCampaign(request: HttpRequest, id: str) -> JsonResponse:
    """Edit campaign name"""
    if request.method != "PUT":
        return JsonResponse(
            {"message": "Invalid request method"}, status=HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user_id = getUserID(request)
        if not user_id:
            return JsonResponse(
                {"message": "User not found"}, status=HTTP_400_BAD_REQUEST
            )

        campaign_name = request.data.get("campaign_name")
        if not campaign_name:
            return JsonResponse(
                {"message": "campaign_name is required"},
                status=HTTP_400_BAD_REQUEST,
            )

        success = edit_campaign_name(
            campaign_id=id, user_id=user_id, new_name=campaign_name
        )

        if not success:
            return JsonResponse(
                {"message": "Campaign not found or no permission"},
                status=HTTP_400_BAD_REQUEST,
            )

        return JsonResponse(
            {"message": "Campaign name updated successfully"}, status=HTTP_200_OK
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=HTTP_400_BAD_REQUEST)
