"""
Gen-Email Services - HTTP handlers for AI-powered email generation.

This module provides REST API endpoints for generating personalized emails
using AI (OpenAI) for sales outreach campaigns.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from users.utils.utils import requireLogin
from neuxo_backend.controller.gen_email_controller import (
    generate_email_for_campaign,
    validate_email_content,
    EmailGenerator,
)


@extend_schema(
    tags=["Gen-Email"],
    summary="Generate AI-powered email",
    description="Generate a personalized email using AI based on recipient and event information.",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "sender_name": {"type": "string", "description": "Name of the email sender"},
                "recipient_name": {"type": "string", "description": "Name of the recipient"},
                "recipient_email": {"type": "string", "description": "Email address of the recipient"},
                "company_name": {"type": "string", "description": "Name of the recipient's company"},
                "event_name": {"type": "string", "description": "Name of the event"},
                "event_location": {"type": "string", "description": "Location of the event"},
                "event_dates": {"type": "string", "description": "Dates of the event"},
                "email_type": {
                    "type": "string",
                    "enum": ["first_email", "follow_up", "custom"],
                    "description": "Type of email to generate",
                },
                "custom_instructions": {"type": "string", "description": "Custom instructions for email generation"},
            },
            "required": ["sender_name", "recipient_email"],
        }
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "content": {"type": "string"},
                "success": {"type": "boolean"},
            },
        },
        400: {"description": "Bad request - missing required fields"},
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    },
    examples=[
        OpenApiExample(
            "Generate first email",
            value={
                "sender_name": "John",
                "recipient_name": "Alice",
                "recipient_email": "alice@example.com",
                "company_name": "TechCorp",
                "event_name": "Web Summit 2024",
                "event_location": "Lisbon",
                "email_type": "first_email",
            },
            request_only=True,
        ),
    ],
)
@api_view(["POST"])
@requireLogin
def generateEmail(request):
    """Generate a personalized email using AI."""
    try:
        data = request.data
        
        # Validate required fields
        sender_name = data.get("sender_name")
        recipient_email = data.get("recipient_email")
        
        if not sender_name:
            return Response(
                {"error": "sender_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not recipient_email:
            return Response(
                {"error": "recipient_email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Extract optional fields
        recipient_name = data.get("recipient_name", "")
        company_name = data.get("company_name")
        event_name = data.get("event_name")
        event_location = data.get("event_location")
        event_dates = data.get("event_dates")
        email_type = data.get("email_type", "first_email")
        custom_instructions = data.get("custom_instructions", "")
        
        # Generate email
        result = generate_email_for_campaign(
            sender_name=sender_name,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            company_name=company_name,
            event_name=event_name,
            event_location=event_location,
            event_dates=event_dates,
            email_type=email_type,
            custom_instructions=custom_instructions,
        )
        
        if result.get("success"):
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": result.get("error", "Failed to generate email")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    tags=["Gen-Email"],
    summary="Generate bulk emails",
    description="Generate multiple personalized emails for a list of recipients.",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "sender_name": {"type": "string", "description": "Name of the email sender"},
                "recipients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "company_name": {"type": "string"},
                        },
                        "required": ["email"],
                    },
                    "description": "List of recipients",
                },
                "event_name": {"type": "string", "description": "Name of the event"},
                "event_location": {"type": "string", "description": "Location of the event"},
                "event_dates": {"type": "string", "description": "Dates of the event"},
                "email_type": {"type": "string", "enum": ["first_email", "follow_up", "custom"]},
            },
            "required": ["sender_name", "recipients"],
        }
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string"},
                            "subject": {"type": "string"},
                            "content": {"type": "string"},
                            "success": {"type": "boolean"},
                        },
                    },
                },
                "total": {"type": "integer"},
                "successful": {"type": "integer"},
                "failed": {"type": "integer"},
            },
        },
    },
)
@api_view(["POST"])
@requireLogin
def generateBulkEmails(request):
    """Generate multiple personalized emails for a list of recipients."""
    try:
        data = request.data
        
        sender_name = data.get("sender_name")
        recipients = data.get("recipients", [])
        
        if not sender_name:
            return Response(
                {"error": "sender_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not recipients or len(recipients) == 0:
            return Response(
                {"error": "recipients list is required and cannot be empty"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Limit bulk generation
        max_recipients = 50
        if len(recipients) > max_recipients:
            return Response(
                {"error": f"Maximum {max_recipients} recipients allowed per request"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        event_name = data.get("event_name")
        event_location = data.get("event_location")
        event_dates = data.get("event_dates")
        email_type = data.get("email_type", "first_email")
        custom_instructions = data.get("custom_instructions", "")
        
        results = []
        successful = 0
        failed = 0
        
        for recipient in recipients:
            recipient_email = recipient.get("email")
            if not recipient_email:
                results.append({
                    "email": "",
                    "success": False,
                    "error": "Missing email address",
                })
                failed += 1
                continue
            
            result = generate_email_for_campaign(
                sender_name=sender_name,
                recipient_name=recipient.get("name", ""),
                recipient_email=recipient_email,
                company_name=recipient.get("company_name"),
                event_name=event_name,
                event_location=event_location,
                event_dates=event_dates,
                email_type=email_type,
                custom_instructions=custom_instructions,
            )
            
            results.append({
                "email": recipient_email,
                "subject": result.get("subject", ""),
                "content": result.get("content", ""),
                "success": result.get("success", False),
                "error": result.get("error") if not result.get("success") else None,
            })
            
            if result.get("success"):
                successful += 1
            else:
                failed += 1
        
        return Response({
            "results": results,
            "total": len(recipients),
            "successful": successful,
            "failed": failed,
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    tags=["Gen-Email"],
    summary="Validate email content",
    description="Validate email subject and content for potential issues (length, spam words, etc.).",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Email subject line"},
                "content": {"type": "string", "description": "Email body content"},
            },
            "required": ["subject", "content"],
        }
    },
    responses={
        200: {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "word_count": {"type": "integer"},
            },
        },
    },
)
@api_view(["POST"])
@requireLogin
def validateEmailContent(request):
    """Validate email content for potential issues."""
    try:
        data = request.data
        
        subject = data.get("subject", "")
        content = data.get("content", "")
        
        if not subject:
            return Response(
                {"error": "subject is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not content:
            return Response(
                {"error": "content is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        result = validate_email_content(subject, content)
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    tags=["Gen-Email"],
    summary="Get available email types",
    description="Get the list of available email types and their descriptions.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "email_types": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
)
@api_view(["GET"])
@requireLogin
def getEmailTypes(request):
    """Get available email types and their descriptions."""
    email_types = [
        {
            "type": "first_email",
            "name": "First Outreach",
            "description": "Initial contact email for networking at events. Warm, professional tone.",
        },
        {
            "type": "follow_up",
            "name": "Follow-up",
            "description": "Follow-up email after initial outreach. Shorter, references previous contact.",
        },
        {
            "type": "custom",
            "name": "Custom Email",
            "description": "Custom email with your own instructions. Provide custom_instructions parameter.",
        },
    ]
    
    return Response({"email_types": email_types}, status=status.HTTP_200_OK)
