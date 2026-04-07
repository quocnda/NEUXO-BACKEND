"""
Campaign Controller - Business Logic Layer
Handles email campaign/sequence related business logic
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from django.db.models import Count, F, Q
from django.utils import timezone

from neuxo_backend.models import MailHistory, SequenceEmail, SequenceEmailStep


def get_campaigns(
    user_id: int,
    page: int = 1,
    limit: int = 10,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    campaign_status: Optional[str] = None,
    search_key: Optional[str] = None,
) -> Tuple[Dict, List[Dict]]:
    """
    Get all campaigns with statistics for a user
    """
    campaigns = (
        SequenceEmail.objects.filter(user_id=user_id)
        .exclude(sequence_status="PENDING")
        .order_by("-created_at")
    )

    # Apply filters
    if start_date and end_date:
        campaigns = campaigns.filter(created_at__range=[start_date, end_date])

    if campaign_status:
        status_mapping = {
            "Active": "PROCESSING",
            "Paused": "PAUSE",
            "Completed": "COMPLETED",
        }
        status_list = campaign_status.split(",")
        mapped_statuses = [status_mapping.get(s, s) for s in status_list]
        campaigns = campaigns.filter(sequence_status__in=mapped_statuses)

    if search_key:
        campaigns = campaigns.filter(campaign_name__icontains=search_key)

    total_count = campaigns.count()

    # Paginate
    if page and limit:
        offset = (page - 1) * limit
        campaigns = campaigns[offset : offset + limit]

    # Get email statistics for all campaigns in one query
    campaign_ids = [c.id for c in campaigns]
    all_emails = MailHistory.objects.filter(campaign_id__in=campaign_ids)

    email_stats = all_emails.values("campaign_id").annotate(
        total_sent=Count("id", filter=Q(type="SEND")),
        total_opened=Count("id", filter=Q(emailtracker__opened=True)),
    )
    stats_map = {str(s["campaign_id"]): s for s in email_stats}

    results = []
    for campaign in campaigns:
        campaign_id_str = str(campaign.id)
        stats = stats_map.get(campaign_id_str, {})

        # Get reply count
        sent_emails = all_emails.filter(campaign_id=campaign.id, type="SEND")
        message_ids = list(sent_emails.values_list("message_id", flat=True).distinct())

        reply_count = (
            MailHistory.objects.filter(
                email_ref_first_id__in=message_ids,
                type="RECIEVE",
                status_mail="SUCCESS",
            )
            .exclude(mail_send="mailer-daemon@googlemail.com")
            .exclude(mail_send__icontains="noreply")
            .count()
        )

        # Update campaign stats
        total_sent = stats.get("total_sent", 0)
        total_opened = stats.get("total_opened", 0)

        # Add followup emails to sent count
        followup_sent = MailHistory.objects.filter(
            email_ref_first_id__in=message_ids, type="SEND"
        ).count()
        total_sent += followup_sent

        # Update campaign record
        campaign.num_email_sent = total_sent
        campaign.num_email_replied = reply_count
        campaign.num_email_opened = total_opened
        campaign.save()

        # Determine status display
        status_display = campaign.sequence_status
        status_choices = []

        if status_display == "PROCESSING":
            status_display = "Active"
            status_choices = ["Pause", "Stop", "Remove"]
        elif status_display == "PAUSE":
            status_display = "Paused"
            status_choices = ["Resume", "Stop", "Remove"]
        elif status_display == "COMPLETED":
            status_display = "Completed"
            status_choices = ["Remove"]

        results.append(
            {
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.campaign_name,
                "day_created": campaign.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "total_email_sent": total_sent,
                "total_email_replied": reply_count,
                "total_email_opened": total_opened,
                "campaign_status": status_display,
                "status_choice": status_choices,
            }
        )

    pagination = {
        "page": page,
        "total_page": (total_count // limit) + (1 if total_count % limit > 0 else 0),
        "total_item": total_count,
    }

    return pagination, results


def update_campaign_status(
    campaign_id: str, user_id: int, new_status: str
) -> Tuple[bool, str]:
    """
    Update campaign status (Resume/Pause/Stop/Remove)
    Returns (success, message)
    """
    campaign = SequenceEmail.objects.filter(id=campaign_id, user_id=user_id).first()
    if not campaign:
        return False, "Campaign not found"

    if new_status == "Resume":
        # Calculate time gap and adjust follow-up dates
        time_before = campaign.updated_at
        gap_time = timezone.now() - time_before

        SequenceEmailStep.objects.filter(sequence=campaign).update(
            follow_up_date=F("follow_up_date") + gap_time,
            updated_at=timezone.now(),
            is_paused=False,
        )
        campaign.sequence_status = "PROCESSING"
        campaign.save()
        return True, "Campaign resumed"

    elif new_status == "Pause":
        campaign.sequence_status = "PAUSE"
        SequenceEmailStep.objects.filter(sequence=campaign).update(
            is_paused=True, updated_at=timezone.now()
        )
        campaign.save()
        return True, "Campaign paused"

    elif new_status == "Stop":
        campaign.sequence_status = "COMPLETED"
        SequenceEmailStep.objects.filter(sequence=campaign).update(
            status="COMPLETED", updated_at=timezone.now()
        )
        campaign.save()
        return True, "Campaign stopped"

    elif new_status == "Remove":
        SequenceEmailStep.objects.filter(sequence=campaign).delete()
        campaign.delete()
        return True, "Campaign removed"

    return False, "Invalid status"


def get_campaign_details(
    campaign_id: str,
    user_id: int,
    page: int = 1,
    limit: int = 50,
    email_status: Optional[str] = None,
) -> Tuple[bool, Dict]:
    """Get detailed campaign information"""
    campaign = SequenceEmail.objects.filter(id=campaign_id, user_id=user_id).first()
    if not campaign:
        return False, {"message": "Campaign not found"}

    # Status display
    status_display = campaign.sequence_status
    status_choices = []

    if status_display == "PROCESSING":
        status_display = "Active"
        status_choices = ["Pause", "Stop", "Remove"]
    elif status_display == "PAUSE":
        status_display = "Paused"
        status_choices = ["Resume", "Stop", "Remove"]
    elif status_display == "COMPLETED":
        status_display = "Completed"
        status_choices = ["Remove"]

    # Get email targets
    email_targets = campaign.email_targets or []

    # Get sent emails
    sent_emails = MailHistory.objects.filter(campaign_id=campaign_id, type="SEND")
    message_ids = list(sent_emails.values_list("message_id", flat=True).distinct())

    # Calculate statistics
    total_sent = sent_emails.count()
    total_sent += MailHistory.objects.filter(
        email_ref_first_id__in=message_ids, type="SEND"
    ).count()

    total_received = (
        MailHistory.objects.filter(
            email_ref_first_id__in=message_ids,
            type="RECIEVE",
            status_mail="SUCCESS",
        )
        .exclude(main_target_mail="mailer-daemon@googlemail.com")
        .exclude(main_target_mail__icontains="noreply")
        .count()
    )

    total_error = MailHistory.objects.filter(
        campaign_id=campaign_id, status_mail="ERROR"
    ).count()

    total_opened = sent_emails.filter(emailtracker__opened=True).count()

    # Get per-email statistics
    email_details = []
    for target in email_targets:
        target_email = target.get("email", "") if isinstance(target, dict) else target

        target_sent = sent_emails.filter(main_target_mail=target_email)
        target_msg_ids = list(target_sent.values_list("message_id", flat=True))

        sent_count = target_sent.count()
        reply_count = (
            MailHistory.objects.filter(
                email_ref_first_id__in=target_msg_ids,
                type="RECIEVE",
                status_mail="SUCCESS",
            )
            .exclude(mail_send__icontains="noreply")
            .count()
        )

        opened_count = target_sent.filter(emailtracker__opened=True).count()

        status = (
            "REPLIED" if reply_count > 0 else ("OPENED" if opened_count > 0 else "SENT")
        )

        email_details.append(
            {
                "email": target_email,
                "sent_count": sent_count,
                "reply_count": reply_count,
                "opened_count": opened_count,
                "status": status,
            }
        )

    # Apply email status filter
    if email_status:
        status_list = email_status.split(",")
        email_details = [e for e in email_details if e["status"] in status_list]

    # Pagination
    total_emails = len(email_details)
    start_idx = (page - 1) * limit
    paginated_emails = email_details[start_idx : start_idx + limit]

    result = {
        "campaign_id": str(campaign.id),
        "campaign_name": campaign.campaign_name,
        "campaign_status": status_display,
        "status_choice": status_choices,
        "created_at": campaign.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "start_date": campaign.start_date.strftime("%Y-%m-%d %H:%M:%S")
        if campaign.start_date
        else None,
        "end_date": campaign.end_date.strftime("%Y-%m-%d %H:%M:%S")
        if campaign.end_date
        else None,
        "statistics": {
            "total_targets": len(email_targets),
            "total_sent": total_sent,
            "total_received": total_received,
            "total_opened": total_opened,
            "total_error": total_error,
        },
        "pagination": {
            "page": page,
            "total_page": (total_emails // limit)
            + (1 if total_emails % limit > 0 else 0),
            "total_item": total_emails,
        },
        "email_details": paginated_emails,
    }

    return True, result


def get_campaign_about(campaign_id: str, user_id: int) -> Tuple[bool, Dict]:
    """Get campaign about info"""
    campaign = SequenceEmail.objects.filter(id=campaign_id, user_id=user_id).first()
    if not campaign:
        return False, {"message": "Campaign not found"}

    return True, {
        "campaign_id": str(campaign.id),
        "campaign_name": campaign.campaign_name,
        "sequence_name": campaign.sequence_name,
        "source": campaign.source,
        "event_id": campaign.event_id,
        "created_at": campaign.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "start_date": campaign.start_date.strftime("%Y-%m-%d %H:%M:%S")
        if campaign.start_date
        else None,
        "end_date": campaign.end_date.strftime("%Y-%m-%d %H:%M:%S")
        if campaign.end_date
        else None,
        "email_targets_count": len(campaign.email_targets or []),
        "enable_bimonthly_send": campaign.enable_bimonthly_send,
        "max_email_bimonthly": campaign.max_email_bimonthly,
    }


def edit_campaign_name(campaign_id: str, user_id: int, new_name: str) -> bool:
    """Edit campaign name"""
    updated = SequenceEmail.objects.filter(id=campaign_id, user_id=user_id).update(
        campaign_name=new_name, updated_at=timezone.now()
    )
    return updated > 0
