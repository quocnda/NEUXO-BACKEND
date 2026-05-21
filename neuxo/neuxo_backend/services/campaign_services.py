"""
Campaign Services - HTTP Handler Layer
Handles email campaign/sequence related API endpoints
"""

from __future__ import annotations

import traceback

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema
from pydantic import ValidationError
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
from neuxo_backend.dto.campaign_dto import (
    AdminEmailStatsData,
    AdminEmailStatsResponse,
    CampaignAboutResponse,
    CampaignDetailQuery,
    CampaignDetailResponse,
    CampaignListQuery,
    CampaignListResponse,
    EditCampaignNameRequest,
    MessageResponse,
    UpdateCampaignStatusRequest,
    ValidationErrorResponse,
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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

    try:
        user_id = getUserID(request)
        if not user_id:
            response = MessageResponse(message="User not found")
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        try:
            query = CampaignListQuery.model_validate(request.GET.dict())
        except ValidationError as exc:
            response = ValidationErrorResponse(
                message="Invalid query parameters",
                errors=exc.errors(),
            )
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        pagination, data = get_campaigns(
            user_id=user_id,
            page=query.page,
            limit=query.limit,
            start_date=query.start_date,
            end_date=query.end_date,
            campaign_status=query.campaign_status,
            search_key=query.search_key,
        )

        response = CampaignListResponse(
            message="Success", pagination=pagination, data=data
        )
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        response = MessageResponse(message=str(e))
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)


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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

    try:
        user_id = getUserID(request)
        if not user_id:
            response = MessageResponse(message="User not found")
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        try:
            payload = UpdateCampaignStatusRequest.model_validate(request.data)
        except ValidationError as exc:
            response = ValidationErrorResponse(
                message="Invalid payload",
                errors=exc.errors(),
            )
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        success, message = update_campaign_status(
            campaign_id=id, user_id=user_id, new_status=payload.status_campaign
        )

        if not success:
            response = MessageResponse(message=message)
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        response = MessageResponse(message=message)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        response = MessageResponse(message=str(e))
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)


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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

    try:
        user_id = getUserID(request)
        if not user_id:
            response = MessageResponse(message="User not found")
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        try:
            query = CampaignDetailQuery.model_validate(request.GET.dict())
        except ValidationError as exc:
            response = ValidationErrorResponse(
                message="Invalid query parameters",
                errors=exc.errors(),
            )
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        success, result = get_campaign_details(
            campaign_id=id,
            user_id=user_id,
            page=query.page,
            limit=query.limit,
            email_status=query.email_status,
        )

        if not success:
            return JsonResponse(result.model_dump(), status=HTTP_400_BAD_REQUEST)

        response = CampaignDetailResponse(message="Success", data=result)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        response = MessageResponse(message=str(e))
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)


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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

    try:
        user_id = getUserID(request)
        if not user_id:
            response = MessageResponse(message="User not found")
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        success, result = get_campaign_about(campaign_id=id, user_id=user_id)

        if not success:
            return JsonResponse(result.model_dump(), status=HTTP_400_BAD_REQUEST)

        response = CampaignAboutResponse(message="Success", data=result)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        response = MessageResponse(message=str(e))
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)


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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

    try:
        from neuxo_backend.models import MailHistory, SequenceEmail
        from django.db.models import Count, Q

        # Get overall statistics
        total_campaigns = SequenceEmail.objects.exclude(
            sequence_status="PENDING"
        ).count()

        email_stats = MailHistory.objects.aggregate(
            total_sent=Count("id", filter=Q(type="SEND")),
            total_received=Count("id", filter=Q(type="RECIEVE")),
        )

        result = AdminEmailStatsData(
            total_campaigns=total_campaigns,
            total_emails_sent=email_stats.get("total_sent", 0),
            total_emails_received=email_stats.get("total_received", 0),
        )
        response = AdminEmailStatsResponse(message="Success", data=result)
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        response = MessageResponse(message=str(e))
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)


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
        response = MessageResponse(message="Invalid request method")
        return JsonResponse(response.model_dump(), status=HTTP_405_METHOD_NOT_ALLOWED)

    try:
        user_id = getUserID(request)
        if not user_id:
            response = MessageResponse(message="User not found")
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        try:
            payload = EditCampaignNameRequest.model_validate(request.data)
        except ValidationError as exc:
            response = ValidationErrorResponse(
                message="Invalid payload",
                errors=exc.errors(),
            )
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        success = edit_campaign_name(
            campaign_id=id, user_id=user_id, new_name=payload.campaign_name
        )

        if not success:
            response = MessageResponse(message="Campaign not found or no permission")
            return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)

        response = MessageResponse(message="Campaign name updated successfully")
        return JsonResponse(response.model_dump(), status=HTTP_200_OK)

    except Exception as e:
        traceback.print_exc()
        response = MessageResponse(message=str(e))
        return JsonResponse(response.model_dump(), status=HTTP_400_BAD_REQUEST)
