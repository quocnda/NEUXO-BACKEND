from __future__ import annotations

import email
import imaplib
import logging
import re
from datetime import datetime, timezone as dt_timezone
from email.header import decode_header
from email.utils import getaddresses, parsedate_to_datetime

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags

from neuxo_backend.models import MailAppAccount, MailHistory
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
        main_target_mail = next((addr for addr in to_addresses if addr != account_email), "")
        mail_type = "SEND"
        mail_send = account_email
        mail_received = ", ".join(to_addresses)
    else:
        main_target_mail = next((addr for addr in from_addresses if addr != account_email), "")
        mail_type = "RECIEVE"
        mail_send = ", ".join(from_addresses)
        mail_received = ", ".join(to_addresses) or account_email

    if not main_target_mail:
        combined = to_addresses if is_sent else from_addresses
        main_target_mail = next((addr for addr in combined if addr), "")

    durable_message_id = message_id or f"{folder_name}:{uid.decode(errors='ignore')}:{account.id}"
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
        logger.warning("Unable to select folder %s for account %s", folder_name, account.id)
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
    if not cache.add(lock_key, task_identifier, timeout=settings.CELERY_TASK_TIME_LIMIT):
        return {"status": "skipped", "reason": "already_running"}

    account_email = (account.email or "").lower().strip()
    mail = None
    try:
        # password = decrypt_password(account.password_app or "")
        password = account.password_app or ""
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(account_email, password)

        batch_size = settings.CELERY_EMAIL_CRAWL_BATCH_SIZE
        print('Starting email crawl for account %s with batch size %d', account_email, batch_size)
        sent_folder = _discover_sent_folder(mail)
        print(f"Discovered sent folder for account {account_email}: {sent_folder}")
        sent_cursor_key = _message_cache_key(account_id, sent_folder)
        inbox_cursor_key = _message_cache_key(account_id, INBOX_FOLDER)

        sent_cursor = int(cache.get(sent_cursor_key) or 0)
        inbox_cursor = int(cache.get(inbox_cursor_key) or 0)
        print(f"Starting crawl for account {account_email} with sent_cursor={sent_cursor}, inbox_cursor={inbox_cursor}")
        
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
            print('Batch completed for account %s, scheduling next batch with sent_cursor=%d, inbox_cursor=%d', account_email, sent_cursor, inbox_cursor)
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
                logger.exception("Failed to logout IMAP session for account %s", account_id)
        cache.delete(lock_key)


@shared_task
def enqueue_mail_account_crawl(account_id: str) -> dict:
    crawl_mail_account_task.delay(account_id)
    return {"status": "queued", "account_id": account_id}
