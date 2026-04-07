"""
Tracker Services - HTTP Handler Layer
Handles email tracking related API endpoints
"""

from __future__ import annotations

import json
import re
import traceback
import urllib.request
from datetime import datetime
from ipaddress import ip_address, ip_network

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view

from neuxo_backend.models import EmailOpenedNotification, EmailTracker


# Private IP ranges for detection
PRIVATE_IP_RANGES = [
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
]


def is_private_ip(ip_str: str) -> bool:
    """Check if IP is private"""
    try:
        ip = ip_address(ip_str)
        return any(ip in net for net in PRIVATE_IP_RANGES)
    except ValueError:
        return True


def is_suspicious_user_agent(user_agent: str) -> bool:
    """Check if user agent is suspicious (bot, crawler, etc.)"""
    if not user_agent:
        return True

    # Multiple Mozilla occurrences
    if user_agent.count("Mozilla") > 1:
        return True

    # Old browser pattern
    old_browser_pattern = r"Chrome/([0-5][0-9])|Edge/([0-1][0-2])"
    if re.search(old_browser_pattern, user_agent):
        return True

    # Bot keywords
    bot_keywords = ["bot", "crawler", "spider", "preview", "fetch", "scan"]
    if any(bot in user_agent.lower() for bot in bot_keywords):
        return True

    return False


def is_real_email_open(ip_str: str, user_agent: str) -> bool:
    """Check if email open is from a real user"""
    return not is_suspicious_user_agent(user_agent)


# 1x1 transparent PNG pixel
TRANSPARENT_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfa"
    b"\x0f\x00\x01\x05\x01\x02\xcf\xa0.\xcd\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------- Email Tracking Pixel ---------------------------------------- #


@extend_schema(
    responses={"200": "Image pixel"},
    auth=None,
    operation_id="GET_emailTrackingPixel",
    tags=["Tracker"],
)
@csrf_exempt
@api_view(["GET"])
def email_tracking_pixel(request: HttpRequest, tracking_id: str) -> HttpResponse:
    """
    Track email opens using a 1x1 transparent pixel.
    This endpoint is called when the tracking image in an email is loaded.
    """
    # Get tracker record
    email_tracker = (
        EmailTracker.objects.select_related("mail_history__user")
        .filter(tracking_id=tracking_id)
        .first()
    )

    if not email_tracker:
        # Return pixel even if tracker not found
        response = HttpResponse(content_type="image/png")
        response.write(TRANSPARENT_PIXEL)
        return response

    # Get client info
    user_agent = request.headers.get("User-Agent", "Unknown")
    client_ip = request.META.get("REMOTE_ADDR", "0.0.0.0")

    # Check if real email open
    if not is_real_email_open(client_ip, user_agent):
        try:
            email_tracker.status = "BOT_DETECTED"
            email_tracker.save()
        except Exception:
            pass

        response = HttpResponse(content_type="image/png")
        response.write(TRANSPARENT_PIXEL)
        return response

    current_time = datetime.now()

    # Get geolocation data
    location_data = {}
    try:
        with urllib.request.urlopen(
            f"http://ip-api.com/json/{client_ip}", timeout=5
        ) as url:
            location_data = json.loads(url.read().decode())
    except Exception:
        location_data = {"error": "Geo-location service unavailable"}

    # Update tracking record
    if not email_tracker.opened:
        email_tracker.opened = True
        email_tracker.first_opened_at = current_time

        # Update mail history status if exists
        if email_tracker.mail_history:
            email_tracker.mail_history.status_mail = "SEEN"
            email_tracker.mail_history.save()

    email_tracker.opened_count += 1
    email_tracker.last_opened_at = current_time
    email_tracker.ip_address = client_ip
    email_tracker.user_agent = user_agent
    email_tracker.location_data = location_data
    email_tracker.save()

    # Create or update notification
    if email_tracker.mail_history:
        notification_data = {
            "recipient_mail": email_tracker.mail_history.mail_recieved,
            "mail_subject": email_tracker.mail_history.subject,
            "last_opened_at": email_tracker.last_opened_at.isoformat(),
            "open_count": email_tracker.opened_count,
        }

        notification = EmailOpenedNotification.objects.filter(
            email_tracker=email_tracker
        ).first()

        if not notification:
            EmailOpenedNotification.objects.create(
                user=email_tracker.mail_history.user,
                email_tracker=email_tracker,
                data=notification_data,
            )
        else:
            notification.data = notification_data
            notification.is_read = False
            notification.save()

    response = HttpResponse(content_type="image/png")
    response.write(TRANSPARENT_PIXEL)
    return response


# ---------------------------------------- Email Tracking Stats ---------------------------------------- #


@extend_schema(
    responses={"200": "Success"},
    auth=None,
    operation_id="GET_emailTrackingStats",
    tags=["Tracker"],
)
@csrf_exempt
@api_view(["GET"])
def email_tracking_stats(request: HttpRequest) -> JsonResponse:
    """Get email tracking statistics"""
    try:
        from django.db.models import Count, Sum, Q

        stats = EmailTracker.objects.aggregate(
            total_tracked=Count("id"),
            total_opened=Count("id", filter=Q(opened=True)),
            total_opens=Sum("opened_count"),
        )

        return JsonResponse(
            {
                "message": "Success",
                "data": {
                    "total_tracked": stats.get("total_tracked", 0),
                    "total_opened": stats.get("total_opened", 0),
                    "total_opens": stats.get("total_opens", 0) or 0,
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"message": str(e)}, status=400)


# ---------------------------------------- Logging ---------------------------------------- #


@csrf_exempt
def logging(request: HttpRequest) -> HttpResponse:
    """Get tracker logs (placeholder)"""
    return HttpResponse("<pre>Logging endpoint - implement as needed</pre>")
