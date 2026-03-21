"""
Email Controller - Business Logic Layer
Handles email-related business logic operations
"""
from __future__ import annotations

import operator
from collections import defaultdict
from datetime import datetime, timedelta
from functools import reduce
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    Max,
    Q,
    Value,
    When,
)
from django.utils import timezone
import pytz

from neuxo_backend.models import (
    EmailHistoryNote,
    EmailTemplate,
    LinkedinCompany,
    LinkedinPersonalEmail,
    MailAppAccount,
    MailHistory,
    Signature,
)

# Keywords to exclude from email filtering
KEYWORDS_EXCLUDE_EMAIL = [
    "OOO",
    "O-O-O",
    "Out of office",
    "out of reach",
    "on vacation",
    "away from desk",
    "automatic reply",
    "on leave",
    "little access to email",
    "not access to email",
]


def calculate_follow_up_date(
    email_status: str,
    last_sent_date: datetime,
    email_sent: int,
    is_replied: bool,
    follow_up_date: datetime,
    time_zone: str = "Asia/Saigon",
) -> Optional[str]:
    """Calculate the follow-up date based on email status and sent count"""
    if email_status == "REPLIED" or is_replied:
        return None

    if follow_up_date and follow_up_date != "":
        return (
            follow_up_date.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(follow_up_date, datetime)
            else follow_up_date
        )

    if last_sent_date is None:
        return None

    try:
        tz = pytz.timezone(time_zone)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("Asia/Saigon")

    # Calculate follow-up based on email count
    days_to_add = min(3 + (email_sent - 1) * 2, 14)
    if isinstance(last_sent_date, str):
        last_sent_date = datetime.strptime(last_sent_date, "%Y-%m-%d %H:%M:%S")

    follow_up = last_sent_date + timedelta(days=days_to_add)
    return follow_up.strftime("%Y-%m-%d %H:%M:%S")


def get_follow_up_status(
    email_status: str, follow_up_date: str, time_zone: str = "Asia/Saigon"
) -> str:
    """Determine follow-up status based on current date"""
    if email_status == "REPLIED":
        return "Completed"

    if follow_up_date is None or follow_up_date == "":
        return "Not Set"

    try:
        tz = pytz.timezone(time_zone)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("Asia/Saigon")

    now = datetime.now(tz)

    if isinstance(follow_up_date, str):
        follow_up = datetime.strptime(follow_up_date, "%Y-%m-%d %H:%M:%S")
        follow_up = tz.localize(follow_up) if follow_up.tzinfo is None else follow_up
    else:
        follow_up = follow_up_date

    diff_days = (follow_up.date() - now.date()).days

    if diff_days < 0:
        return "Overdue"
    elif diff_days == 0:
        return "Focused"
    else:
        return "Upcoming"


def get_email_conversations(
    user_id: int,
    page: int = 1,
    limit: int = 100,
    email_status: Optional[str] = None,
    email_count_start: int = 0,
    email_count_end: int = 10000,
    search_key: Optional[str] = None,
    last_activity_start_date: Optional[str] = None,
    last_activity_end_date: Optional[str] = None,
    follow_up_status: Optional[str] = None,
    priority: Optional[str] = None,
    time_zone: str = "Asia/Saigon",
) -> Tuple[Dict, List[Dict]]:
    """
    Get all email conversations with statistics and filtering
    Returns pagination info and list of email conversations
    """
    # Build base query
    lst_mail = (
        MailHistory.objects.filter(user__id=user_id)
        .exclude(subject="unsubscribe")
        .exclude(main_target_mail__icontains="no-reply")
        .exclude(main_target_mail__icontains="noreply")
        .exclude(main_target_mail__icontains="unsubscribe")
        .exclude(main_target_mail__icontains="luma-mail.com")
        .exclude(main_target_mail__icontains="googlemail.com")
        .exclude(main_target_mail__icontains="accounts.google.com")
        .exclude(main_target_mail__icontains="hubspot.com")
        .exclude(main_target_mail__icontains="linkedin.com")
        .annotate(email=F("main_target_mail"))
        .values("email")
        .annotate(
            contact_name=F("email"),
            company_name=F("email"),
            email_sent=Count(Case(When(type="SEND", then=1), default=None)),
            reply_count=Count("id", filter=Q(type="RECIEVE")),
            seen_count=Count("id", filter=Q(status_mail="SEEN")),
            success_count=Count("id", filter=Q(status_mail="SUCCESS")),
            last_sent_date=Max("time_send"),
            error_message=Case(
                When(
                    status_mail="ERROR",
                    error_message__icontains="Address not found",
                    then=Value("Email address not found"),
                ),
                When(
                    status_mail="ERROR",
                    error_message__icontains="Message blocked",
                    then=Value("Message blocked"),
                ),
                default=Value(None),
                output_field=CharField(),
            ),
            email_status_calc=Case(
                When(reply_count__gt=0, then=Value("REPLIED")),
                When(seen_count__gt=0, then=Value("SEEN")),
                When(success_count__gt=0, then=Value("SENT")),
                default=Value("ERROR"),
                output_field=CharField(),
            ),
        )
        .filter(
            email_sent__gte=int(email_count_start),
            email_sent__lte=int(email_count_end),
        )
        .order_by("-last_sent_date")
    )

    # Apply search filter
    if search_key:
        lst_mail = lst_mail.filter(email__icontains=search_key.strip())

    # Apply date range filter
    if last_activity_start_date and last_activity_end_date:
        start_dt = datetime.strptime(last_activity_start_date.strip(), "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(last_activity_end_date.strip(), "%Y-%m-%d %H:%M:%S")
        lst_mail = lst_mail.filter(last_sent_date__range=[start_dt, end_dt])

    # Get note and priority data
    all_note_priority = EmailHistoryNote.objects.filter(
        user__id=user_id
    ).values(
        "main_target_email",
        "user_note",
        "priority",
        "is_replied",
        "follow_up_date",
    )
    note_priority_map = {
        item["main_target_email"]: item for item in all_note_priority
    }

    # Process results
    results = []
    for mail in lst_mail:
        email_addr = mail["email"]
        note_data = note_priority_map.get(email_addr, {})

        # Extract company and contact names
        domain = email_addr.split("@")[-1].split(".")[0] if "@" in email_addr else ""
        company_name = "personal" if "gmail" in domain.lower() else domain
        contact_name = email_addr.split("@")[0] if "@" in email_addr else email_addr

        # Calculate follow-up
        follow_up_date = calculate_follow_up_date(
            mail["email_status_calc"],
            mail["last_sent_date"],
            mail["email_sent"],
            note_data.get("is_replied", False),
            note_data.get("follow_up_date"),
            time_zone,
        )
        follow_up_stat = get_follow_up_status(
            mail["email_status_calc"], follow_up_date, time_zone
        )

        result = {
            "email": email_addr,
            "company_name": company_name,
            "contact_name": contact_name,
            "email_sent": mail["email_sent"],
            "reply_count": mail["reply_count"],
            "email_status": mail["email_status_calc"],
            "last_sent_date": (
                mail["last_sent_date"].strftime("%Y-%m-%d %H:%M:%S")
                if mail["last_sent_date"]
                else None
            ),
            "error_message": mail["error_message"],
            "user_note": note_data.get("user_note", ""),
            "priority": note_data.get("priority", ""),
            "is_replied": note_data.get("is_replied", False),
            "follow_up_date": follow_up_date,
            "follow_up_status": follow_up_stat,
        }
        results.append(result)

    # Apply post-query filters
    if email_status:
        status_list = email_status.split(",")
        results = [r for r in results if r["email_status"] in status_list]

    if follow_up_status:
        status_list = follow_up_status.split(",")
        results = [r for r in results if r["follow_up_status"] in status_list]

    if priority:
        priority_list = priority.split(",")
        results = [r for r in results if r["priority"] in priority_list]

    # Pagination
    total = len(results)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_results = results[start_idx:end_idx]

    pagination = {
        "page": page,
        "total_page": (total // limit) + (1 if total % limit > 0 else 0),
        "total_item": total,
    }

    return pagination, paginated_results


def get_mail_conversation_details(
    user_id: int, target_mail: str, page: int = 1, limit: int = 50
) -> Tuple[Dict, List[Dict]]:
    """Get email conversation thread details"""
    mails = (
        MailHistory.objects.filter(user__id=user_id, main_target_mail=target_mail)
        .order_by("-time_send")
        .values(
            "id",
            "mail_send",
            "mail_recieved",
            "subject",
            "content",
            "html_mail_content",
            "time_send",
            "type",
            "status_mail",
            "error_message",
        )
    )

    total = mails.count()
    start_idx = (page - 1) * limit
    paginated = mails[start_idx : start_idx + limit]

    results = []
    for mail in paginated:
        results.append(
            {
                "id": str(mail["id"]),
                "from": mail["mail_send"],
                "to": mail["mail_recieved"],
                "subject": mail["subject"],
                "content": mail["content"],
                "html_content": mail["html_mail_content"],
                "time_send": (
                    mail["time_send"].strftime("%Y-%m-%d %H:%M:%S")
                    if mail["time_send"]
                    else None
                ),
                "type": mail["type"],
                "status": mail["status_mail"],
                "error_message": mail["error_message"],
            }
        )

    pagination = {
        "page": page,
        "total_page": (total // limit) + (1 if total % limit > 0 else 0),
        "total_item": total,
    }

    return pagination, results


def get_email_templates(user_id: int) -> List[Dict]:
    """Get all email templates for a user"""
    templates = EmailTemplate.objects.filter(user__id=user_id).values(
        "id",
        "template_name",
        "template_subject",
        "template_content",
        "attachments",
        "created_at",
        "updated_at",
    )
    return list(templates)


def create_email_template(
    user_id: int,
    template_name: str,
    template_subject: str,
    template_content: str,
    attachments: List = None,
) -> Dict:
    """Create a new email template"""
    template = EmailTemplate.objects.create(
        user_id=user_id,
        template_name=template_name,
        template_subject=template_subject,
        template_content=template_content,
        attachments=attachments or [],
    )
    return {
        "id": str(template.id),
        "template_name": template.template_name,
        "template_subject": template.template_subject,
        "template_content": template.template_content,
        "attachments": template.attachments,
    }


def update_email_template(
    template_id: str,
    user_id: int,
    template_name: str = None,
    template_subject: str = None,
    template_content: str = None,
    attachments: List = None,
) -> bool:
    """Update an existing email template"""
    template = EmailTemplate.objects.filter(id=template_id, user__id=user_id).first()
    if not template:
        return False

    if template_name:
        template.template_name = template_name
    if template_subject:
        template.template_subject = template_subject
    if template_content:
        template.template_content = template_content
    if attachments is not None:
        template.attachments = attachments

    template.save()
    return True


def delete_email_template(template_id: str, user_id: int) -> bool:
    """Delete an email template"""
    deleted_count, _ = EmailTemplate.objects.filter(
        id=template_id, user__id=user_id
    ).delete()
    return deleted_count > 0


def get_signatures(user_id: int) -> List[Dict]:
    """Get all signatures for a user"""
    signatures = Signature.objects.filter(user_gmail__user__id=user_id).values(
        "id",
        "signature_name",
        "signature_html",
        "user_gmail__email",
        "created_at",
        "updated_at",
    )
    return [
        {
            "id": str(s["id"]),
            "name": s["signature_name"],
            "html": s["signature_html"],
            "email": s["user_gmail__email"],
            "created_at": s["created_at"],
            "updated_at": s["updated_at"],
        }
        for s in signatures
    ]


def create_or_update_signature(
    user_id: int,
    signature_name: str,
    signature_html: str,
    email_account_id: str = None,
    signature_id: str = None,
) -> Dict:
    """Create or update a signature"""
    if signature_id:
        # Update existing
        sig = Signature.objects.filter(
            id=signature_id, user_gmail__user__id=user_id
        ).first()
        if sig:
            sig.signature_name = signature_name
            sig.signature_html = signature_html
            sig.save()
            return {"id": str(sig.id), "updated": True}
        return None

    # Create new
    mail_account = MailAppAccount.objects.filter(
        user__id=user_id, id=email_account_id
    ).first()
    if not mail_account:
        # Get default account
        mail_account = MailAppAccount.objects.filter(user__id=user_id).first()

    if not mail_account:
        return None

    sig = Signature.objects.create(
        user_gmail=mail_account,
        signature_name=signature_name,
        signature_html=signature_html,
    )
    return {"id": str(sig.id), "created": True}


def delete_signature(signature_id: str, user_id: int) -> bool:
    """Delete a signature"""
    deleted_count, _ = Signature.objects.filter(
        id=signature_id, user_gmail__user__id=user_id
    ).delete()
    return deleted_count > 0


def update_email_record(
    user_id: int, target_email: str, note: str = None, priority: str = None
) -> bool:
    """Update email record note and priority"""
    record, created = EmailHistoryNote.objects.get_or_create(
        user_id=user_id,
        main_target_email=target_email,
        defaults={"user_note": note or "", "priority": priority or "MEDIUM"},
    )

    if not created:
        if note is not None:
            record.user_note = note
        if priority is not None:
            record.priority = priority
        record.save()

    return True


def set_follow_up_date(user_id: int, target_email: str, follow_up_date: str) -> bool:
    """Set follow-up date for email"""
    record, created = EmailHistoryNote.objects.get_or_create(
        user_id=user_id,
        main_target_email=target_email,
        defaults={"follow_up_date": follow_up_date},
    )

    if not created:
        record.follow_up_date = (
            datetime.strptime(follow_up_date, "%Y-%m-%d %H:%M:%S")
            if follow_up_date
            else None
        )
        record.save()

    return True
