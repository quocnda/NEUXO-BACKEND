"""
Email Controller - Business Logic Layer
Handles email-related business logic operations
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from email.utils import parseaddr
from typing import Dict, List, Optional, Tuple

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
    MailGenHistory,
    MailAppAccount,
    MailHistory,
    SequenceEmail,
    SequenceEmailStep,
    SequenceEmailStepHistory,
    Signature,
)
from users.models import Users
from neuxo_backend.controller.llm_controller import (
    _generate_preview_content,
    _normalize_sequence_source,
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

EXCLUDED_TRACKING_DOMAINS = [
    "no-reply",
    "noreply",
    "unsubscribe",
    "luma-mail.com",
    "googlemail.com",
    "accounts.google.com",
    "hubspot.com",
    "linkedin.com",
]

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    results = _get_email_conversation_results(
        user_id=user_id,
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


def _get_email_conversation_results(
    user_id: int,
    email_status: Optional[str] = None,
    email_count_start: int = 0,
    email_count_end: int = 10000,
    search_key: Optional[str] = None,
    last_activity_start_date: Optional[str] = None,
    last_activity_end_date: Optional[str] = None,
    follow_up_status: Optional[str] = None,
    priority: Optional[str] = None,
    time_zone: str = "Asia/Saigon",
) -> List[Dict]:
    """Build the full email conversation summary list before pagination."""
    lst_mail = (
        MailHistory.objects.filter(user__id=user_id)
        .exclude(subject="unsubscribe")
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

    for excluded_domain in EXCLUDED_TRACKING_DOMAINS:
        lst_mail = lst_mail.exclude(main_target_mail__icontains=excluded_domain)

    # Apply search filter
    if search_key:
        lst_mail = lst_mail.filter(email__icontains=search_key.strip())

    # Apply date range filter
    if last_activity_start_date and last_activity_end_date:
        start_dt = datetime.strptime(
            last_activity_start_date.strip(), "%Y-%m-%d %H:%M:%S"
        )
        end_dt = datetime.strptime(last_activity_end_date.strip(), "%Y-%m-%d %H:%M:%S")
        lst_mail = lst_mail.filter(last_sent_date__range=[start_dt, end_dt])

    # Get note and priority data
    all_note_priority = EmailHistoryNote.objects.filter(user__id=user_id).values(
        "main_target_email",
        "user_note",
        "priority",
        "is_replied",
        "follow_up_date",
    )
    note_priority_map = {item["main_target_email"]: item for item in all_note_priority}

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

    return results


def get_tracking_email_conversations(
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
    follow_up_start_date: Optional[str] = None,
    follow_up_end_date: Optional[str] = None,
    priority: Optional[str] = None,
    time_zone: str = "Asia/Saigon",
    source: Optional[str] = None,
) -> Tuple[Dict, List[Dict]]:
    """Get email tracking conversations with tab-specific filters."""
    results = _get_email_conversation_results(
        user_id=user_id,
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

    try:
        tz = pytz.timezone(time_zone)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("Asia/Saigon")

    today = datetime.now(tz)

    if source == "replied":
        results = [item for item in results if item["email_status"] == "REPLIED"]
    elif source == "unresponsive":
        filtered_results = []
        for item in results:
            if item["email_status"] != "SENT" or item["email_sent"] < 3:
                continue
            if not item["last_sent_date"]:
                continue
            last_sent_date = datetime.strptime(
                item["last_sent_date"], "%Y-%m-%d %H:%M:%S"
            )
            if last_sent_date <= today.replace(tzinfo=None) - timedelta(days=1):
                filtered_results.append(item)
        results = filtered_results
    elif source == "prospected":
        filtered_results = []
        for item in results:
            is_unresponsive = False
            if (
                item["email_status"] == "SENT"
                and item["email_sent"] >= 3
                and item["last_sent_date"]
            ):
                last_sent_date = datetime.strptime(
                    item["last_sent_date"], "%Y-%m-%d %H:%M:%S"
                )
                is_unresponsive = last_sent_date <= today.replace(
                    tzinfo=None
                ) - timedelta(days=1)
            if item["email_status"] != "REPLIED" and not is_unresponsive:
                filtered_results.append(item)
        results = filtered_results

    if follow_up_start_date and follow_up_end_date:
        follow_up_start = datetime.strptime(
            follow_up_start_date.strip(), "%Y-%m-%d %H:%M:%S"
        ).date()
        follow_up_end = datetime.strptime(
            follow_up_end_date.strip(), "%Y-%m-%d %H:%M:%S"
        ).date()
        filtered_results = []
        for item in results:
            if not item["follow_up_date"]:
                continue
            follow_up_date = datetime.strptime(
                item["follow_up_date"], "%Y-%m-%d %H:%M:%S"
            ).date()
            if follow_up_start <= follow_up_date <= follow_up_end:
                filtered_results.append(item)
        results = filtered_results

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


def check_processing_sequence_emails(list_email: List[str]) -> List[str]:
    """Return emails that are currently being processed by active sequences."""
    all_email_targets = SequenceEmail.objects.filter(
        sequence_status="PROCESSING"
    ).values_list("email_targets", flat=True)

    processing_emails = {
        email.strip().lower()
        for email_list in all_email_targets
        if isinstance(email_list, list)
        for email in email_list
        if isinstance(email, str) and email.strip()
    }

    return [
        email
        for email in list_email
        if isinstance(email, str) and email.strip().lower() in processing_emails
    ]


def _is_valid_email(email: str) -> bool:
    _, parsed_email = parseaddr(email or "")
    return bool(parsed_email and EMAIL_REGEX.match(parsed_email.strip().lower()))


def _get_sequence_target_emails(sequence: SequenceEmail) -> List[str]:
    email_targets = sequence.email_targets or []
    normalized_targets = []

    for target in email_targets:
        if isinstance(target, str):
            email = target.strip().lower()
        elif isinstance(target, dict):
            email = str(target.get("email", "")).strip().lower()
        else:
            email = ""

        if email and _is_valid_email(email):
            normalized_targets.append(email)

    return list(dict.fromkeys(normalized_targets))


def _get_step_email_type(step_number: int) -> str:
    return "first_email" if step_number == 1 else "follow_up"


def _build_email_prompt(
    source: str,
    email_type: str,
    recipient_email: str,
    company_name: Optional[str] = None,
    event_name: Optional[str] = None,
) -> str:
    return (
        f"source={source};email_type={email_type};recipient={recipient_email};"
        f"company={company_name or ''};event={event_name or ''}"
    )


def create_sequence_email_record(
    user_id: int,
    signature_id: str,
    list_email: List[str],
    custom_sequence: List[int],
    campaign_name: Optional[str] = None,
    source: Optional[str] = None,
    enable_bimonthly: Optional[bool] = None,
    max_email_bimonthly: Optional[int] = None,
    user_hot_trigger: Optional[bool] = None,
    hot_trigger_condition: Optional[List] = None,
    event_id: Optional[str] = None,
) -> Dict[str, str]:
    """Create a draft email sequence with all follow-up steps."""
    user = Users.objects.filter(id=user_id).first()
    if not user:
        raise ValueError("User not found")

    mail_user_account = MailAppAccount.objects.filter(
        user_id=user_id, status="ACTIVE"
    ).first()
    if mail_user_account is None:
        raise ValueError("Mail account not found")

    normalized_emails = [
        email.strip().lower()
        for email in list_email
        if isinstance(email, str) and email.strip()
    ]
    normalized_emails = list(dict.fromkeys(normalized_emails))

    if not normalized_emails:
        raise ValueError(
            "No contacts are currently in the sequence. Please select new companies to send automated emails."
        )

    if not custom_sequence:
        raise ValueError("Please provide all required fields")

    try:
        normalized_steps = [int(step) for step in custom_sequence]
    except (TypeError, ValueError):
        raise ValueError("custom_sequence must contain integers")

    for step_value in normalized_steps[1:]:
        if step_value == 0:
            raise ValueError(
                "You must wait at least 1 day before sending the follow-up email"
            )

    signature = Signature.objects.filter(
        user_gmail=mail_user_account, id=signature_id
    ).first()
    if signature is None:
        raise ValueError("Signature not found")

    source_value = _normalize_sequence_source(source)
    date_now = timezone.now()
    sequence_steps = []
    current_follow_up_date = date_now

    for index, step_offset_days in enumerate(normalized_steps):
        current_follow_up_date = current_follow_up_date + timedelta(
            days=step_offset_days
        )
        sequence_steps.append(
            {
                "step_number": index + 1,
                "follow_up_date": current_follow_up_date,
            }
        )

    sequence_name = f"Sequence_{timezone.now().strftime('%Y%m%d%H%M%S')}_User_{user.user_name or user.id}"
    total_days = sum(normalized_steps)
    day_start_bimonthly = timezone.now() + timedelta(days=total_days)

    new_sequence = SequenceEmail.objects.create(
        user=user,
        signature=signature,
        email_targets=normalized_emails,
        sequence_name=sequence_name,
        start_date=timezone.now(),
        end_date=sequence_steps[-1]["follow_up_date"],
        campaign_name=campaign_name,
        source=source_value,
        event_id=event_id,
        enable_bimonthly_send=bool(enable_bimonthly),
        max_email_bimonthly=max_email_bimonthly,
        user_hot_trigger=bool(user_hot_trigger),
        hot_trigger_condition=hot_trigger_condition or [],
        day_start_bimonthly=day_start_bimonthly,
    )

    SequenceEmailStep.objects.bulk_create(
        [SequenceEmailStep(sequence=new_sequence, **step) for step in sequence_steps]
    )

    return {"id": str(new_sequence.id)}


def preview_sequence_email(
    user_id: int,
    recipient_email: str,
    sequence_id: str,
    source: Optional[str] = None,
    event_id: Optional[str] = None,
) -> List[Dict]:
    """Generate or return cached preview email content for all steps."""
    user = Users.objects.filter(id=user_id).first()
    if not user:
        raise ValueError("User not found")

    email = recipient_email.strip().lower()
    if not _is_valid_email(email):
        raise ValueError("Invalid email")

    sequence_email = SequenceEmail.objects.filter(
        id=sequence_id, user_id=user_id
    ).first()
    if sequence_email is None:
        raise ValueError("Sequence not found")

    source_value = _normalize_sequence_source(source or sequence_email.source)
    sequence_steps = list(
        SequenceEmailStep.objects.filter(sequence__id=sequence_id)
        .order_by("step_number")
        .all()
    )
    if not sequence_steps:
        raise ValueError("Sequence step not found")

    cached_rows = list(
        MailGenHistory.objects.filter(sequence_id=sequence_id, email=email)
        .values("email", "step_number", "subject", "content", "status")
        .order_by("step_number")
    )
    if cached_rows:
        failed_item = next(
            (item for item in cached_rows if item["status"] == "FAILED"), None
        )
        if failed_item:
            raise ValueError(failed_item["content"] or "Preview generation failed")

        response = [
            {
                "email": item["email"],
                "stepNum": item["step_number"],
                "subject": item["subject"] or "",
                "content": item["content"] or "",
            }
            for item in cached_rows
        ]
        existing_steps = {item["stepNum"] for item in response}
        for step in sequence_steps:
            if step.step_number not in existing_steps:
                response.append(
                    {
                        "email": email,
                        "stepNum": step.step_number,
                        "subject": "",
                        "content": "",
                    }
                )
        response.sort(key=lambda item: item["stepNum"])
        return response

    ensure_sequence_step_content_generated(
        sequence_id=sequence_id,
        step_ids=[str(step.id) for step in sequence_steps],
        recipient_emails=[email],
        user=user,
        source=source_value,
        event_id=event_id or sequence_email.event_id,
        persist_step_history=True,
    )

    generated_rows = list(
        MailGenHistory.objects.filter(sequence_id=sequence_id, email=email)
        .values("email", "step_number", "subject", "content", "status")
        .order_by("step_number")
    )

    return [
        {
            "email": item["email"],
            "stepNum": item["step_number"],
            "subject": item["subject"] or "",
            "content": item["content"] or "",
        }
        for item in generated_rows
    ]


def ensure_sequence_step_content_generated(
    sequence_id: str,
    step_ids: List[str],
    recipient_emails: List[str],
    user: Optional[Users] = None,
    source: Optional[str] = None,
    event_id: Optional[str] = None,
    persist_step_history: bool = False,
) -> List[SequenceEmailStepHistory]:
    """Generate MailGenHistory content and optionally create step histories."""
    sequence = (
        SequenceEmail.objects.select_related("signature", "user")
        .filter(id=sequence_id)
        .first()
    )
    if not sequence:
        raise ValueError("Sequence not found")

    source_value = _normalize_sequence_source(source or sequence.source)
    step_map = {
        str(step.id): step
        for step in SequenceEmailStep.objects.filter(
            sequence=sequence, id__in=step_ids
        ).order_by("step_number")
    }
    if not step_map:
        return []

    sender_account = MailAppAccount.objects.filter(
        user=sequence.user, status="ACTIVE"
    ).first()
    sender_email = (
        sender_account.email if sender_account else (sequence.user.email or "")
    )
    created_step_histories: List[SequenceEmailStepHistory] = []

    normalized_recipients = list(
        dict.fromkeys(
            [
                email.strip().lower()
                for email in recipient_emails
                if isinstance(email, str) and email.strip() and _is_valid_email(email)
            ]
        )
    )

    for recipient_email in normalized_recipients:
        for step_id, step in step_map.items():
            generated = MailGenHistory.objects.filter(
                sequence_id=sequence_id,
                email=recipient_email,
                step_number=step.step_number,
                status="COMPLETED",
            ).first()

            if not generated:
                prompt = ""
                try:
                    subject, content, prompt = _generate_preview_content(
                        sequence=sequence,
                        step=step,
                        recipient_email=recipient_email,
                        source=source_value,
                        event_id=event_id or sequence.event_id,
                    )
                except Exception as exc:
                    MailGenHistory.objects.update_or_create(
                        sequence_id=sequence_id,
                        email=recipient_email,
                        step_number=step.step_number,
                        defaults={
                            "status": "FAILED",
                            "subject": "",
                            "content": str(exc),
                            "email_prompt": prompt,
                        },
                    )
                    raise ValueError(str(exc))

                generated, _ = MailGenHistory.objects.update_or_create(
                    sequence_id=sequence_id,
                    email=recipient_email,
                    step_number=step.step_number,
                    defaults={
                        "status": "COMPLETED",
                        "subject": subject,
                        "content": content,
                        "email_prompt": prompt,
                    },
                )

            if persist_step_history:
                step_history, created = SequenceEmailStepHistory.objects.get_or_create(
                    email_step=step,
                    email_target=recipient_email,
                    defaults={
                        "email_sender": sender_email,
                        "subject": generated.subject or "",
                        "content": generated.content or "",
                        "email_prompt": generated.email_prompt or "",
                    },
                )
                if not created:
                    step_history.email_sender = sender_email
                    step_history.subject = generated.subject or step_history.subject
                    step_history.content = generated.content or step_history.content
                    step_history.email_prompt = (
                        generated.email_prompt or step_history.email_prompt
                    )
                    step_history.save(
                        update_fields=[
                            "email_sender",
                            "subject",
                            "content",
                            "email_prompt",
                            "updated_at",
                        ]
                    )
                created_step_histories.append(step_history)

    return created_step_histories


def submit_sequence_email(
    user_id: int,
    sequence_id: str,
    content_emails: List[Dict],
    event_id: Optional[str] = None,
) -> Dict[str, str]:
    """Persist submitted sequence content and mark the sequence as processing."""
    sequence = (
        SequenceEmail.objects.select_related("signature", "user")
        .filter(id=sequence_id, user_id=user_id)
        .first()
    )
    if not sequence:
        raise ValueError("Sequence not found")

    if not content_emails:
        raise ValueError("Please provide content_email")

    steps = {
        step.step_number: step
        for step in SequenceEmailStep.objects.filter(sequence__id=sequence_id).order_by(
            "step_number"
        )
    }
    if not steps:
        raise ValueError("Sequence step not found")

    sender = MailAppAccount.objects.filter(user=sequence.user, status="ACTIVE").first()
    if not sender:
        raise ValueError("Mail account not found")

    bulk_create_email = []
    provided_emails = set()

    for email_payload in content_emails:
        email_target = str(email_payload.get("email", "")).strip().lower()
        if not email_target:
            continue
        provided_emails.add(email_target)

        SequenceEmailStepHistory.objects.filter(
            email_step__sequence=sequence,
            email_target=email_target,
            is_sent=False,
        ).delete()

        for data in email_payload.get("data", []):
            step_number = int(data.get("stepNum", 0) or 0)
            step = steps.get(step_number)
            if not step:
                continue

            prompt_email = (
                MailGenHistory.objects.filter(
                    sequence_id=sequence_id,
                    email=email_target,
                    step_number=step_number,
                )
                .values_list("email_prompt", flat=True)
                .first()
                or ""
            )

            bulk_create_email.append(
                SequenceEmailStepHistory(
                    email_sender=sender.email,
                    email_step=step,
                    email_target=email_target,
                    subject=data.get("subject", ""),
                    content=data.get("content", ""),
                    email_prompt=prompt_email,
                )
            )

    if bulk_create_email:
        SequenceEmailStepHistory.objects.bulk_create(bulk_create_email)

    missing_emails = list(set(_get_sequence_target_emails(sequence)) - provided_emails)
    if missing_emails:
        ensure_sequence_step_content_generated(
            sequence_id=sequence_id,
            step_ids=[str(step.id) for step in steps.values()],
            recipient_emails=missing_emails,
            user=sequence.user,
            source=sequence.source,
            event_id=event_id or sequence.event_id,
            persist_step_history=True,
        )

    sequence.sequence_status = "PROCESSING"
    if event_id:
        sequence.event_id = event_id
    sequence.updated_at = timezone.now()
    sequence.save(update_fields=["sequence_status", "event_id", "updated_at"])

    return {"message": "Submit sequence successful!"}


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
    return {
        "list_signatures": [
            {
                "id": str(s["id"]),
                "signature_name": s["signature_name"],
                "signature_html": s["signature_html"],
                "email": s["user_gmail__email"],
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
            }
            for s in signatures
        ]
    }


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
