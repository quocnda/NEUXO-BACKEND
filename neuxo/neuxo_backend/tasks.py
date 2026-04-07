from __future__ import annotations

import email
import imaplib
import logging
import os
import re
import smtplib
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import getaddresses, parsedate_to_datetime

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.utils.html import strip_tags

from neuxo_backend.models import (
    EmailTracker,
    LinkedinPersonalEmail,
    MailAppAccount,
    MailHistory,
    SequenceEmail,
    SequenceEmailStep,
    SequenceEmailStepHistory,
)
from users.utils.crypto_hash import decrypt_password

logger = logging.getLogger(__name__)

INBOX_FOLDER = "INBOX"
DEFAULT_SENT_CANDIDATES = (
    '"[Gmail]/Sent Mail"',
    '"[Google Mail]/Sent Mail"',
    "Sent",
)


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""

    decoded_parts = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="ignore"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts).strip()


def _parse_email_date(value: str | None) -> datetime:
    if not value:
        return timezone.now()

    try:
        parsed = parsedate_to_datetime(value)
        if parsed is None:
            return timezone.now()
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, dt_timezone.utc)
        return parsed.astimezone(dt_timezone.utc)
    except Exception:
        return timezone.now()


def _extract_addresses(header_value: str | None) -> list[str]:
    addresses = []
    for _, addr in getaddresses([header_value or ""]):
        if addr:
            addresses.append(addr.lower().strip())
    return addresses


def _extract_message_bodies(message: email.message.Message) -> tuple[str, str]:
    text_body = ""
    html_body = ""

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition.lower():
                continue

            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            if not payload:
                continue

            try:
                decoded = payload.decode(charset, errors="ignore")
            except Exception:
                decoded = payload.decode("utf-8", errors="ignore")

            if content_type == "text/plain" and not text_body:
                text_body = decoded
            elif content_type == "text/html" and not html_body:
                html_body = decoded
    else:
        payload = message.get_payload(decode=True)
        if payload:
            charset = message.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="ignore")
            except Exception:
                decoded = payload.decode("utf-8", errors="ignore")

            if message.get_content_type() == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    if not text_body and html_body:
        text_body = strip_tags(html_body)

    return text_body.strip(), html_body.strip()


def _discover_sent_folder(mail: imaplib.IMAP4_SSL) -> str:
    status, folders = mail.list()
    if status != "OK":
        return DEFAULT_SENT_CANDIDATES[0]

    for raw_folder in folders or []:
        folder_text = raw_folder.decode(errors="ignore")
        if "\\Sent" in folder_text:
            match = re.findall(r'"([^"]+)"$', folder_text)
            if match:
                return f'"{match[-1]}"'

    for candidate in DEFAULT_SENT_CANDIDATES:
        for raw_folder in folders or []:
            folder_text = raw_folder.decode(errors="ignore").lower()
            if candidate.replace('"', "").lower() in folder_text:
                return candidate

    return DEFAULT_SENT_CANDIDATES[0]


def _message_cache_key(account_id: str, folder_name: str) -> str:
    normalized = folder_name.replace('"', "").replace("/", "_").replace(" ", "_")
    return f"email_crawl:cursor:{account_id}:{normalized}"


def _lock_key(account_id: str) -> str:
    return f"email_crawl:lock:{account_id}"


def _task_state_key(account_id: str) -> str:
    return f"email_crawl:state:{account_id}"


def _build_mail_history_payload(
    account: MailAppAccount,
    account_email: str,
    message: email.message.Message,
    folder_name: str,
    uid: bytes,
) -> dict:
    from_header = _decode_header_value(message.get("From"))
    to_header = _decode_header_value(message.get("To"))
    subject = _decode_header_value(message.get("Subject"))
    message_id = (message.get("Message-ID") or "").strip()
    in_reply_to = (message.get("In-Reply-To") or "").strip()
    references = (message.get("References") or "").strip()
    text_body, html_body = _extract_message_bodies(message)
    sent_at = _parse_email_date(message.get("Date"))

    from_addresses = _extract_addresses(from_header)
    to_addresses = _extract_addresses(to_header)
    is_sent = any(addr == account_email for addr in from_addresses)

    if is_sent:
        main_target_mail = next(
            (addr for addr in to_addresses if addr != account_email), ""
        )
        mail_type = "SEND"
        mail_send = account_email
        mail_received = ", ".join(to_addresses)
    else:
        main_target_mail = next(
            (addr for addr in from_addresses if addr != account_email), ""
        )
        mail_type = "RECIEVE"
        mail_send = ", ".join(from_addresses)
        mail_received = ", ".join(to_addresses) or account_email

    if not main_target_mail:
        combined = to_addresses if is_sent else from_addresses
        main_target_mail = next((addr for addr in combined if addr), "")

    durable_message_id = (
        message_id or f"{folder_name}:{uid.decode(errors='ignore')}:{account.id}"
    )
    first_reference = ""
    if references:
        first_reference = references.split()[0].strip()

    return {
        "user_id": account.user_id,
        "mail_send": mail_send,
        "mail_recieved": mail_received,
        "content": text_body[:10000],
        "html_mail_content": html_body[:50000],
        "time_send": sent_at,
        "subject": subject[:1000],
        "main_target_mail": main_target_mail,
        "name_target_mail": main_target_mail,
        "type": mail_type,
        "message_id": durable_message_id,
        "status_mail": "SUCCESS",
        "email_ref_first_id": in_reply_to or first_reference or durable_message_id,
        "email_reply_id": in_reply_to or first_reference,
    }


def _upsert_message(
    account: MailAppAccount,
    account_email: str,
    folder_name: str,
    uid: bytes,
    raw_message: bytes,
) -> None:
    parsed_message = email.message_from_bytes(raw_message)
    payload = _build_mail_history_payload(
        account=account,
        account_email=account_email,
        message=parsed_message,
        folder_name=folder_name,
        uid=uid,
    )

    MailHistory.objects.update_or_create(
        user_id=account.user_id,
        message_id=payload["message_id"],
        defaults=payload,
    )


def _process_folder_batch(
    mail: imaplib.IMAP4_SSL,
    account: MailAppAccount,
    account_email: str,
    folder_name: str,
    cursor: int,
    batch_size: int,
) -> tuple[int, bool]:
    status, _ = mail.select(folder_name, readonly=True)
    if status != "OK":
        logger.warning(
            "Unable to select folder %s for account %s", folder_name, account.id
        )
        return cursor, False

    status, data = mail.search(None, "ALL")
    if status != "OK":
        return cursor, False

    message_uids = list(reversed((data[0] or b"").split()))
    if not message_uids:
        return cursor, False

    batch_uids = message_uids[cursor : cursor + batch_size]
    if not batch_uids:
        return cursor, False

    for uid in batch_uids:
        fetch_status, msg_data = mail.fetch(uid, "(RFC822)")
        if fetch_status != "OK":
            continue
        for response_part in msg_data:
            if not isinstance(response_part, tuple):
                continue
            _upsert_message(
                account=account,
                account_email=account_email,
                folder_name=folder_name,
                uid=uid,
                raw_message=response_part[1],
            )
            break

    next_cursor = cursor + len(batch_uids)
    has_more = next_cursor < len(message_uids)
    return next_cursor, has_more


def _set_task_state(account_id: str, state: dict) -> None:
    cache.set(_task_state_key(account_id), state, timeout=60 * 60 * 24)


def _clear_task_state(account_id: str) -> None:
    cache.delete(_task_state_key(account_id))


def _mark_bounced_messages_from_payload(
    payload: dict,
    body_text: str,
    body_html: str,
) -> int:
    main_target_mail = (payload.get("main_target_mail") or "").lower().strip()
    if main_target_mail != "mailer-daemon@googlemail.com":
        return 0

    reference_ids = []
    for candidate in (
        payload.get("email_reply_id"),
        payload.get("email_ref_first_id"),
    ):
        normalized = (candidate or "").strip()
        if normalized and normalized not in reference_ids:
            reference_ids.append(normalized)

    if not reference_ids:
        return 0

    error_message = (body_text or body_html or "").strip()
    if not error_message:
        return 0

    bounced_emails = {
        email_address.lower().strip()
        for email_address in re.findall(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            error_message,
        )
        if email_address
    }
    bounced_emails.discard("mailer-daemon@googlemail.com")

    mail_histories = MailHistory.objects.filter(message_id__in=reference_ids)
    if bounced_emails:
        mail_histories = mail_histories.filter(main_target_mail__in=bounced_emails)

    updated_count = mail_histories.update(
        status_mail="ERROR",
        error_message=error_message[:10000],
        updated_at=timezone.now(),
    )
    if updated_count:
        logger.info(
            "Marked %s bounced message(s) as ERROR for references=%s",
            updated_count,
            reference_ids,
        )
    return updated_count


def _crawl_latest_inbox_messages(
    account: MailAppAccount,
    batch_size: int,
) -> dict:
    account_email = (account.email or "").lower().strip()
    if not account_email:
        return {"processed_count": 0, "error_count": 0, "reason": "missing_email"}

    password = _resolve_account_password(account)
    mail = None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(account_email, password)

        status, _ = mail.select(INBOX_FOLDER, readonly=True)
        if status != "OK":
            return {
                "processed_count": 0,
                "error_count": 0,
                "reason": "inbox_unavailable",
            }

        status, data = mail.search(None, "ALL")
        if status != "OK":
            return {"processed_count": 0, "error_count": 0, "reason": "search_failed"}

        message_uids = list(reversed((data[0] or b"").split()))
        batch_uids = message_uids[: max(batch_size, 0)]
        if not batch_uids:
            return {"processed_count": 0, "error_count": 0}

        processed_count = 0
        error_count = 0
        for uid in batch_uids:
            fetch_status, msg_data = mail.fetch(uid, "(RFC822)")
            if fetch_status != "OK":
                continue

            for response_part in msg_data:
                if not isinstance(response_part, tuple):
                    continue

                parsed_message = email.message_from_bytes(response_part[1])
                payload = _build_mail_history_payload(
                    account=account,
                    account_email=account_email,
                    message=parsed_message,
                    folder_name=INBOX_FOLDER,
                    uid=uid,
                )
                text_body, html_body = _extract_message_bodies(parsed_message)

                MailHistory.objects.update_or_create(
                    user_id=account.user_id,
                    message_id=payload["message_id"],
                    defaults=payload,
                )
                error_count += _mark_bounced_messages_from_payload(
                    payload=payload,
                    body_text=text_body,
                    body_html=html_body,
                )
                processed_count += 1
                break

        return {"processed_count": processed_count, "error_count": error_count}
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                logger.exception(
                    "Failed to logout IMAP session for recent inbox crawl account %s",
                    account.id,
                )


@shared_task(
    bind=True,
    autoretry_for=(imaplib.IMAP4.error, OSError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def crawl_mail_account_task(self, account_id: str) -> dict:
    account = MailAppAccount.objects.filter(id=account_id, status="ACTIVE").first()
    if not account:
        return {"status": "skipped", "reason": "account_not_found"}

    lock_key = _lock_key(account_id)
    task_identifier = getattr(self.request, "id", None) or f"manual-{account_id}"
    if not cache.add(
        lock_key, task_identifier, timeout=settings.CELERY_TASK_TIME_LIMIT
    ):
        return {"status": "skipped", "reason": "already_running"}

    account_email = (account.email or "").lower().strip()
    mail = None
    try:
        # password = decrypt_password(account.password_app or "")
        password = account.password_app or ""
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(account_email, password)

        batch_size = settings.CELERY_EMAIL_CRAWL_BATCH_SIZE
        print(
            "Starting email crawl for account %s with batch size %d",
            account_email,
            batch_size,
        )
        sent_folder = _discover_sent_folder(mail)
        print(f"Discovered sent folder for account {account_email}: {sent_folder}")
        sent_cursor_key = _message_cache_key(account_id, sent_folder)
        inbox_cursor_key = _message_cache_key(account_id, INBOX_FOLDER)

        sent_cursor = int(cache.get(sent_cursor_key) or 0)
        inbox_cursor = int(cache.get(inbox_cursor_key) or 0)
        print(
            f"Starting crawl for account {account_email} with sent_cursor={sent_cursor}, inbox_cursor={inbox_cursor}"
        )

        sent_cursor, sent_has_more = _process_folder_batch(
            mail=mail,
            account=account,
            account_email=account_email,
            folder_name=sent_folder,
            cursor=sent_cursor,
            batch_size=batch_size,
        )
        cache.set(sent_cursor_key, sent_cursor, timeout=60 * 60 * 24 * 30)

        inbox_cursor, inbox_has_more = _process_folder_batch(
            mail=mail,
            account=account,
            account_email=account_email,
            folder_name=INBOX_FOLDER,
            cursor=inbox_cursor,
            batch_size=batch_size,
        )
        cache.set(inbox_cursor_key, inbox_cursor, timeout=60 * 60 * 24 * 30)

        state = {
            "status": "running" if sent_has_more or inbox_has_more else "completed",
            "sent_cursor": sent_cursor,
            "inbox_cursor": inbox_cursor,
            "updated_at": timezone.now().isoformat(),
        }
        _set_task_state(account_id, state)

        if sent_has_more or inbox_has_more:
            print(
                "Batch completed for account %s, scheduling next batch with sent_cursor=%d, inbox_cursor=%d",
                account_email,
                sent_cursor,
                inbox_cursor,
            )
            crawl_mail_account_task.apply_async(
                args=[account_id],
                countdown=settings.CELERY_EMAIL_CRAWL_COUNTDOWN,
            )
            return state

        _clear_task_state(account_id)
        return state
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                logger.exception(
                    "Failed to logout IMAP session for account %s", account_id
                )
        cache.delete(lock_key)


@shared_task
def enqueue_mail_account_crawl(account_id: str) -> dict:
    crawl_mail_account_task.delay(account_id)
    return {"status": "queued", "account_id": account_id}


@shared_task(
    bind=True,
    autoretry_for=(imaplib.IMAP4.error, OSError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def crawl_recent_sequence_mail_history_task(
    self,
    sequence_id: str,
    account_id: str,
    batch_size: int,
) -> dict:
    account = MailAppAccount.objects.filter(id=account_id, status="ACTIVE").first()
    if not account:
        return {
            "status": "skipped",
            "reason": "account_not_found",
            "sequence_id": sequence_id,
        }

    result = _crawl_latest_inbox_messages(account=account, batch_size=batch_size)
    result.update(
        {
            "status": "processed",
            "sequence_id": sequence_id,
            "account_id": account_id,
            "batch_size": batch_size,
        }
    )
    return result


def _sequence_lock_key(sequence_id: str) -> str:
    return f"email_sequence:lock:{sequence_id}"


def _sequence_retry_countdown() -> int:
    return int(os.getenv("CELERY_SEQUENCE_RETRY_COUNTDOWN", "900"))


def _build_tracking_base_url() -> str:
    return (
        os.getenv("PUBLIC_SERVER")
        or os.getenv("BACKEND_PUBLIC_URL")
        or "http://127.0.0.1:8000/api"
    ).rstrip("/")


def _get_sequence_target_emails(sequence: SequenceEmail) -> list[str]:
    normalized = []
    for target in sequence.email_targets or []:
        if isinstance(target, str):
            email_target = target.strip().lower()
        elif isinstance(target, dict):
            email_target = str(target.get("email", "")).strip().lower()
        else:
            email_target = ""

        if email_target:
            normalized.append(email_target)

    return list(dict.fromkeys(normalized))


def _resolve_account_password(account: MailAppAccount) -> str:
    try:
        return decrypt_password(account.password_app or "")
    except Exception:
        return account.password_app or ""


def _get_sequence_excluded_emails(sequence: SequenceEmail) -> set[str]:
    campaign_id = str(sequence.id)
    lst_mail = (
        MailHistory.objects.filter(campaign_id=campaign_id)
        .values("main_target_mail")
        .annotate(
            email_sent=Count("id", filter=Q(type="SEND")),
            success_count=Count("id", filter=Q(status_mail="SUCCESS")),
            seen_count=Count("id", filter=Q(status_mail="SEEN")),
            last_sent_date=Max("time_send"),
            replied_or_error_count=Count(
                "id", filter=Q(type="RECIEVE") | Q(status_mail="ERROR")
            ),
        )
    )

    replied_or_error = set(
        lst_mail.filter(replied_or_error_count__gt=0).values_list(
            "main_target_mail", flat=True
        )
    )
    unresponsive = set(
        lst_mail.filter(
            email_sent__gte=3,
            seen_count=0,
            success_count__gt=0,
            last_sent_date__lte=timezone.now() - timedelta(days=1),
        ).values_list("main_target_mail", flat=True)
    )
    return {email for email in replied_or_error | unresponsive if email}


def _prepare_sequence_step_histories(
    sequence: SequenceEmail,
    step: SequenceEmailStep,
) -> tuple[list[str], bool]:
    target_emails = _get_sequence_target_emails(sequence)
    excluded_emails = _get_sequence_excluded_emails(sequence)
    send_targets = sorted(set(target_emails) - excluded_emails)

    if sequence.source != "EVENT":
        valid_targets = set(
            LinkedinPersonalEmail.objects.filter(email__in=send_targets).values_list(
                "email", flat=True
            )
        )
    else:
        valid_targets = set(send_targets)

    invalid_targets = set(send_targets) - valid_targets
    all_excluded = excluded_emails | invalid_targets
    if all_excluded:
        SequenceEmailStepHistory.objects.filter(
            email_step=step, email_target__in=all_excluded, is_sent=False
        ).delete()

    final_targets = sorted(valid_targets)
    if not final_targets:
        SequenceEmailStep.objects.filter(id=step.id).update(
            status="COMPLETED",
            updated_at=timezone.now(),
        )
        return [], True

    existing_targets = set(
        SequenceEmailStepHistory.objects.filter(email_step=step).values_list(
            "email_target", flat=True
        )
    )
    missing_targets = sorted(set(final_targets) - existing_targets)
    if missing_targets:
        from neuxo_backend.controller.email_controller import (
            ensure_sequence_step_content_generated,
        )

        ensure_sequence_step_content_generated(
            sequence_id=str(sequence.id),
            step_ids=[str(step.id)],
            recipient_emails=missing_targets,
            user=sequence.user,
            source=sequence.source,
            event_id=sequence.event_id,
            persist_step_history=True,
        )

    return final_targets, False


def _attach_signature_and_tracking(
    content: str,
    signature_html: str,
    tracking_id: str,
) -> str:
    tracking_url = f"{_build_tracking_base_url()}/email/tracking/{tracking_id}"
    tracking_pixel = (
        f'<img src="{tracking_url}" width="1" height="1" alt="" '
        'style="display:none!important;" />'
    )
    html_parts = [content or ""]
    if signature_html and signature_html not in (content or ""):
        html_parts.append(signature_html)
    html_parts.append(tracking_pixel)
    return "<br><br>".join([part for part in html_parts if part is not None])


def _send_sequence_email(
    sequence: SequenceEmail,
    step_history: SequenceEmailStepHistory,
    account: MailAppAccount,
    password: str,
) -> bool:
    tracking_id = str(uuid.uuid4())
    tracking_html = _attach_signature_and_tracking(
        content=step_history.content or "",
        signature_html=sequence.signature.signature_html if sequence.signature else "",
        tracking_id=tracking_id,
    )

    previous_sent = list(
        MailHistory.objects.filter(
            campaign_id=str(sequence.id),
            main_target_mail=step_history.email_target,
            type="SEND",
        )
        .order_by("time_send", "created_at")
        .values_list("message_id", flat=True)
    )
    root_message_id = previous_sent[0] if previous_sent else None
    parent_message_id = previous_sent[-1] if previous_sent else None
    message_id = f"<{uuid.uuid4()}@{account.email.split('@')[-1]}>"

    message = MIMEMultipart("alternative")
    message["From"] = account.email
    message["To"] = step_history.email_target
    message["Subject"] = step_history.subject or ""
    message["Message-ID"] = message_id
    message["Campaign-ID"] = str(sequence.id)
    if parent_message_id:
        message["In-Reply-To"] = parent_message_id
    if root_message_id:
        message["References"] = root_message_id

    message.attach(MIMEText(strip_tags(tracking_html), "plain", "utf-8"))
    message.attach(MIMEText(tracking_html, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=40) as server:
            server.starttls()
            server.login(account.email, password)
            server.sendmail(
                account.email, [step_history.email_target], message.as_string()
            )

        mail_history = MailHistory.objects.create(
            user_id=sequence.user_id,
            mail_send=account.email,
            mail_recieved=step_history.email_target,
            content=strip_tags(step_history.content or ""),
            html_mail_content=tracking_html,
            time_send=timezone.now(),
            subject=step_history.subject or "",
            main_target_mail=step_history.email_target,
            name_target_mail=step_history.email_target,
            type="SEND",
            message_id=message_id,
            status_mail="SUCCESS",
            email_ref_first_id=root_message_id or message_id,
            email_reply_id=parent_message_id,
            campaign_id=str(sequence.id),
        )
        EmailTracker.objects.create(
            tracking_id=tracking_id,
            message_id=message_id,
            mail_history=mail_history,
            status="SENT",
        )
        SequenceEmailStepHistory.objects.filter(id=step_history.id).update(
            is_sent=True,
            updated_at=timezone.now(),
        )
        return True
    except Exception as exc:
        MailHistory.objects.create(
            user_id=sequence.user_id,
            mail_send=account.email,
            mail_recieved=step_history.email_target,
            content=strip_tags(step_history.content or ""),
            html_mail_content=tracking_html,
            time_send=timezone.now(),
            subject=step_history.subject or "",
            main_target_mail=step_history.email_target,
            name_target_mail=step_history.email_target,
            type="SEND",
            message_id=message_id,
            status_mail="ERROR",
            error_message=str(exc),
            email_ref_first_id=root_message_id or message_id,
            email_reply_id=parent_message_id,
            campaign_id=str(sequence.id),
        )
        logger.exception(
            "Failed to send sequence email for sequence %s recipient %s",
            sequence.id,
            step_history.email_target,
        )
        return False


def _finalize_sequence_state(sequence: SequenceEmail) -> None:
    pending_steps = SequenceEmailStep.objects.filter(
        sequence=sequence, status="PENDING", is_paused=False
    ).order_by("follow_up_date", "step_number")

    next_step = pending_steps.first()
    if not next_step:
        SequenceEmail.objects.filter(id=sequence.id).update(
            sequence_status="COMPLETED",
            updated_at=timezone.now(),
        )
        return

    eta = (
        next_step.follow_up_date
        if next_step.follow_up_date and next_step.follow_up_date > timezone.now()
        else None
    )
    if eta:
        process_sequence_task.apply_async(args=[str(sequence.id)], eta=eta)
    else:
        process_sequence_task.apply_async(
            args=[str(sequence.id)],
            countdown=_sequence_retry_countdown(),
        )


@shared_task(
    bind=True,
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_sequence_task(self, sequence_id: str) -> dict:
    sequence = (
        SequenceEmail.objects.select_related("signature", "user")
        .filter(id=sequence_id)
        .first()
    )
    if not sequence or sequence.sequence_status != "PROCESSING":
        return {"status": "skipped", "reason": "sequence_not_processing"}

    lock_key = _sequence_lock_key(sequence_id)
    task_identifier = getattr(self.request, "id", None) or f"manual-{sequence_id}"
    if not cache.add(
        lock_key, task_identifier, timeout=settings.CELERY_TASK_TIME_LIMIT
    ):
        return {"status": "skipped", "reason": "already_running"}

    try:
        account = MailAppAccount.objects.filter(
            user=sequence.user, status="ACTIVE"
        ).first()
        if not account:
            return {"status": "skipped", "reason": "mail_account_not_found"}

        password = _resolve_account_password(account)
        due_steps = list(
            SequenceEmailStep.objects.filter(
                sequence=sequence,
                status="PENDING",
                is_paused=False,
                follow_up_date__lte=timezone.now(),
            ).order_by("follow_up_date", "step_number")
        )
        if not due_steps:
            _finalize_sequence_state(sequence)
            return {"status": "scheduled_next", "sequence_id": sequence_id}

        sent_count = 0
        for step in due_steps:
            final_targets, completed_early = _prepare_sequence_step_histories(
                sequence, step
            )
            if completed_early:
                continue

            pending_histories = list(
                SequenceEmailStepHistory.objects.filter(
                    email_step=step,
                    is_sent=False,
                    email_target__in=final_targets,
                ).order_by("created_at")[:50]
            )

            if not pending_histories:
                SequenceEmailStep.objects.filter(id=step.id).update(
                    status="COMPLETED",
                    updated_at=timezone.now(),
                )
                continue

            for history in pending_histories:
                if _send_sequence_email(sequence, history, account, password):
                    sent_count += 1

            remaining_count = SequenceEmailStepHistory.objects.filter(
                email_step=step,
                is_sent=False,
                email_target__in=final_targets,
            ).count()
            if remaining_count == 0:
                SequenceEmailStep.objects.filter(id=step.id).update(
                    status="COMPLETED",
                    updated_at=timezone.now(),
                )

        sequence.refresh_from_db(fields=["sequence_status"])
        if sequence.sequence_status == "PROCESSING":
            _finalize_sequence_state(sequence)

        if sent_count > 0:
            crawl_recent_sequence_mail_history_task.apply_async(
                args=[sequence_id, str(account.id), sent_count],
                countdown=3 * 60,
            )

        return {
            "status": "processed",
            "sequence_id": sequence_id,
            "sent_count": sent_count,
        }
    finally:
        cache.delete(lock_key)


@shared_task
def enqueue_sequence_processing(sequence_id: str) -> dict:
    process_sequence_task.delay(sequence_id)
    return {"status": "queued", "sequence_id": sequence_id}
