"""
Email Controller - Business Logic Layer
Handles email-related business logic operations
"""
from __future__ import annotations

import operator
import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from email.utils import parseaddr
from functools import reduce
from pathlib import Path
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
import pandas as pd

from neuxo_backend.controller.gen_email_controller import generate_email_for_campaign
from neuxo_backend.models import (
    EmailHistoryNote,
    EmailTemplate,
    EventsList,
    GuestList,
    LinkedinCompany,
    LinkedinPersonalEmail,
    MailGenHistory,
    MailAppAccount,
    MailHistory,
    Notification,
    SequenceEmail,
    SequenceEmailStep,
    SequenceEmailStepHistory,
    Signature,
)
from openai import OpenAI
from users.models import Users

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
    "var-meta.com",
    "hubspot.com",
    "linkedin.com",
]

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DB_PATH = DATA_DIR / "cache_campaign.sqlite"
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_EMAIL_PREVIEW_MODEL", "gpt-4o-mini")


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
            if item["email_status"] == "SENT" and item["email_sent"] >= 3 and item["last_sent_date"]:
                last_sent_date = datetime.strptime(
                    item["last_sent_date"], "%Y-%m-%d %H:%M:%S"
                )
                is_unresponsive = (
                    last_sent_date <= today.replace(tzinfo=None) - timedelta(days=1)
                )
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


def _normalize_sequence_source(source: Optional[str]) -> str:
    source_value = (source or "COMPANY").strip().upper()
    if source_value == "EVENT":
        return "EVENT"
    return "COMPANY"


def _is_valid_email(email: str) -> bool:
    _, parsed_email = parseaddr(email or "")
    return bool(parsed_email and EMAIL_REGEX.match(parsed_email.strip().lower()))


def _get_sender_display_name(user: Users) -> str:
    full_name = " ".join(
        [part for part in [user.first_name, user.last_name] if part]
    ).strip()
    return full_name or user.user_name or user.email or "NEUXO"


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


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return OpenAI(api_key=api_key)


def _extract_json_from_response(content: str) -> Dict[str, Any]:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    return json.loads(content)


def _call_json_llm(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> Dict[str, Any]:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=DEFAULT_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return _extract_json_from_response(content)


def _load_successful_projects_data() -> Dict[str, Any]:
    project_path = DATA_DIR / "Successful_Projects_Updated.xlsx"
    project_df = pd.read_excel(project_path)

    project_rows = []
    for _, row in project_df.iterrows():
        project_rows.append(
            {
                "industry": str(row.get("Industry", "") or "").strip(),
                "name": str(row.get("Project name", "") or "").strip(),
                "keywords": str(row.get("Project keywords", "") or "").strip(),
                "client": str(row.get("Client name", "") or "").strip(),
                "client_description": str(row.get("Client description", "") or "").strip(),
                "overview": str(row.get("Project overview", "") or "").strip(),
                "key_points": str(row.get("Project key points", "") or "").strip(),
                "ecosystem": str(row.get("Ecosystem", "") or "").strip(),
                "country": str(row.get("Country", "") or "").strip(),
                "category": str(row.get("Category", "") or "").strip(),
            }
        )

    description = "\n".join(
        [
            (
                f"Industry: {item['industry']}, Name: {item['name']}, Keywords: {item['keywords']}, "
                f"Client: {item['client']}, Client description: {item['client_description']}, "
                f"Overview: {item['overview']}, Key Points: {item['key_points']}, "
                f"Ecosystem: {item['ecosystem']}, Country: {item['country']}, Category: {item['category']}"
            )
            for item in project_rows
        ]
    )
    countries = sorted({item["country"] for item in project_rows if item["country"]})
    categories = sorted({item["category"] for item in project_rows if item["category"]})
    ecosystems = sorted({item["ecosystem"] for item in project_rows if item["ecosystem"]})

    return {
        "description": description,
        "countries": countries,
        "categories": categories,
        "ecosystems": ecosystems,
        "rows": project_rows,
    }


def _load_testimonial_description() -> str:
    testimonial_path = DATA_DIR / "Testimonial_Projects.xlsx"
    testimonial_df = pd.read_excel(testimonial_path).dropna(how="all")
    return "\n".join(
        [
            (
                f"Team: {row.get('Company', '')}, Contact: {row.get('Contact', '')}, "
                f"Role: {row.get('Role', '')}, Testimonial: {row.get('Testimonial', '')}, "
                f"Industry: {row.get('Industry', '')}"
            )
            for _, row in testimonial_df.iterrows()
        ]
    )


def _load_spam_words() -> str:
    spam_words_path = DATA_DIR / "mail_spam_words.csv"
    spam_words_df = pd.read_csv(spam_words_path)
    spam_words = spam_words_df["words"].dropna().astype(str).str.strip().unique()
    return ", ".join(spam_words)


def _campaign_cache_get(sequence_id: str, company_id: str) -> Tuple[Optional[Dict], Optional[List[Dict]]]:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CACHE_DB_PATH)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_cache (
            sequence_id TEXT,
            company_id TEXT,
            trigger_dict TEXT,
            relevant_information TEXT,
            PRIMARY KEY (sequence_id, company_id)
        )
        """
    )
    cursor.execute(
        """
        SELECT trigger_dict, relevant_information
        FROM campaign_cache
        WHERE sequence_id = ? AND company_id = ?
        """,
        (sequence_id, company_id),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return None, None
    return json.loads(row["trigger_dict"]), json.loads(row["relevant_information"])


def _campaign_cache_set(
    sequence_id: str,
    company_id: str,
    trigger_dict: Dict[str, Any],
    relevant_information: List[Dict[str, Any]],
) -> None:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CACHE_DB_PATH)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_cache (
            sequence_id TEXT,
            company_id TEXT,
            trigger_dict TEXT,
            relevant_information TEXT,
            PRIMARY KEY (sequence_id, company_id)
        )
        """
    )
    cursor.execute(
        """
        INSERT OR REPLACE INTO campaign_cache (
            sequence_id, company_id, trigger_dict, relevant_information
        ) VALUES (?, ?, ?, ?)
        """,
        (
            sequence_id,
            company_id,
            json.dumps(trigger_dict, ensure_ascii=False),
            json.dumps(relevant_information, ensure_ascii=False),
        ),
    )
    connection.commit()
    connection.close()


def _get_sequence_trigger(company: Optional[LinkedinCompany], person: Optional[LinkedinPersonalEmail]) -> Dict[str, Any]:
    notifications = list(
        Notification.objects.filter(company=company, guest_id__isnull=True)
        .exclude(type="SUB_DOMAIN")
        .order_by("-time_post")[:20]
        .values("title", "type", "post_url", "reference_id", "time_post")
    ) if company else []

    if not notifications and person:
        notifications = list(
            Notification.objects.filter(guest_id=str(person.id))
            .exclude(type="SUB_DOMAIN")
            .order_by("-time_post")[:20]
            .values("title", "type", "post_url", "reference_id", "time_post")
        )

    if not notifications:
        return {"type": "DEFAULT", "trigger_details": None, "title": "", "description": ""}

    priority_map = {
        "JOB_CHANGE": 1,
        "HIRING": 2,
        "FUNDING": 3,
        "EVENT": 4,
        "NEWS": 5,
        "LINKEDIN": 6,
        "TWITTER": 7,
    }
    notifications.sort(key=lambda item: priority_map.get(item.get("type"), 99))
    selected = notifications[0]

    trigger_type = selected.get("type") or "DEFAULT"
    trigger_details = None
    if trigger_type == "HIRING":
        trigger_details = "HIRING"
    elif trigger_type == "FUNDING":
        trigger_details = "FUNDING"
    elif trigger_type == "EVENT":
        trigger_details = "EVENT"

    return {
        "type": trigger_type,
        "trigger_details": trigger_details,
        "title": selected.get("title", "") or "",
        "description": selected.get("title", "") or "",
    }


def _company_profile_text(company: Optional[LinkedinCompany]) -> str:
    if not company:
        return "{}"
    return json.dumps(
        {
            "client company name": company.name,
            "size": company.size,
            "description": company.description,
            "industry": company.industry,
            "organization_type": company.organization_type,
            "headquarters": company.headquarters,
            "followers": company.followers,
            "country": company.country,
            "category": company.category,
            "labels": company.labels,
        },
        ensure_ascii=False,
    )


def _person_profile_text(person: Optional[LinkedinPersonalEmail], guest: Optional[GuestList] = None, source: str = "COMPANY") -> str:
    if source == "EVENT":
        data = {
            "email": guest.email if guest else "",
            "name": guest.name if guest else "",
            "role": guest.role if guest else "",
        }
    else:
        data = {
            "email": person.email if person else "",
            "first_name": person.first_name if person else "",
            "last_name": person.last_name if person else "",
            "role": person.role if person else "",
        }
    return json.dumps(data, ensure_ascii=False)


def _classify_relevant_information_heuristic(
    trigger_dict: Dict[str, Any],
    person: Optional[LinkedinPersonalEmail],
    company: Optional[LinkedinCompany],
    projects_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    company_description = (company.description or "").lower() if company else ""
    company_industry = (company.industry or "").lower() if company else ""
    company_country = (company.country or "").lower() if company else ""
    company_category = (company.category or "").lower() if company else ""
    company_labels = [str(label).lower() for label in (company.labels or [])] if company and company.labels else []
    trigger_text = f"{trigger_dict.get('title', '')} {trigger_dict.get('description', '')}".lower()

    scored_rows = []
    for row in projects_data["rows"]:
        score = 0
        haystacks = " ".join(
            [
                row["industry"].lower(),
                row["name"].lower(),
                row["keywords"].lower(),
                row["client"].lower(),
                row["client_description"].lower(),
                row["overview"].lower(),
                row["key_points"].lower(),
                row["ecosystem"].lower(),
                row["country"].lower(),
                row["category"].lower(),
            ]
        )
        if company_category and company_category in haystacks:
            score += 4
        if company_industry and company_industry in haystacks:
            score += 4
        if company_country and company_country in row["country"].lower():
            score += 2
        if any(label in haystacks for label in company_labels):
            score += 3
        if trigger_text and any(token for token in trigger_text.split() if len(token) > 4 and token in haystacks):
            score += 5
        if score > 0:
            scored_rows.append((score, row))

    scored_rows.sort(key=lambda item: item[0], reverse=True)
    results: List[Dict[str, Any]] = []

    if scored_rows:
        best_row = scored_rows[0][1]
        project_description = (
            f"Matched project: {best_row['name']} for {best_row['client']}. "
            f"Overview: {best_row['overview']}. Key points: {best_row['key_points']}. "
            f"Ecosystem: {best_row['ecosystem']}. Category: {best_row['category']}."
        )
        results.append(
            {
                "Type": "Relevant Project",
                "Project Description": project_description,
                "Action": "Insert a paragraph that highlights that specific project and the synergy with your company’s related work.",
            }
        )

    ecosystem = next(
        (
            eco
            for eco in projects_data["ecosystems"]
            if eco and eco.lower() in f"{company_description} {trigger_text}"
        ),
        None,
    )
    if ecosystem:
        results.append(
            {
                "Type": "ECOSYSTEM",
                "Project Description": (
                    f"The client appears aligned with the {ecosystem} ecosystem. "
                    f"Reference Varmeta's experience in {ecosystem} or similar ecosystems and connect it to the client's current initiatives."
                ),
                "Action": "Insert a paragraph referencing that ecosystem and how your team’s experience with that or a similar ecosystem can support potential collaboration.",
            }
        )

    if company_country and len(results) < 2:
        results.append(
            {
                "Type": "Country",
                "Project Description": f"The client is based in {company.country}. Mention geographic proximity or regional innovation opportunities in Web3 and AI.",
                "Action": "Insert a paragraph referring to geographic proximity or regional innovation opportunities in Web3 and AI.",
            }
        )

    if company_category and len(results) < 2:
        results.append(
            {
                "Type": "Category",
                "Project Description": f"The client is working in {company.category}. Highlight Varmeta's relevant domain expertise and use cases in that category.",
                "Action": "Insert a paragraph referring to that category and your company's relevant domain expertise and use cases.",
            }
        )

    default_actions = [
        {
            "Type": "Varmeta worked",
            "Action": "Insert a paragraph referring to mention that Varmeta has worked with major global partners, notably Layer 1 partners such as Hedera and Aptos.",
        },
        {
            "Type": "Varmeta's expertise",
            "Action": "Insert a paragraph highlight Varmeta's expertise about AI or Blockchain(depending on the customer's field) and readiness to collaborate on future projects.",
        },
    ]
    while len(results) < 2:
        results.append(default_actions[len(results)])
    return results[:2]


def _build_company_preview_prompt(
    email_type: str,
    trigger_group: str,
    sender_name: str,
    recipient_name: str,
    company_name: str,
    company_profile: str,
    person_profile: str,
    trigger_text: str,
    relevant_information: List[Dict[str, Any]],
    testimonial_text: str,
    previous_context: str,
) -> Tuple[Optional[str], Optional[str], str]:
    if email_type == "manual_follow_up_1":
        subject = "are you the right contact?"
        content = (
            f"Hey {recipient_name}," if recipient_name else "Hey,"
        ) + "\n\nJust following up on my previous email.\n\nLet me know if you're the right person to discuss this. If not, I'd appreciate it if you could point me in the right direction.\n\nThanks and appreciate your support."
        return subject, content, ""

    if email_type == "manual_follow_up_fix_2":
        subject = "don't miss my last message"
        if trigger_group == "hiring":
            content = (
                f"Hey {recipient_name}," if recipient_name else "Hey,"
            ) + "\n\nHave you had a chance to view my earlier messages?\n\nIf the open engineering roles have already been filled or outsourcing is not a fit, feel free to let me know. Otherwise, I believe we could support your project with our blockchain and AI talent in the next 3-6 months."
        elif trigger_group in {"funding", "event"}:
            content = (
                f"Hey {recipient_name}," if recipient_name else "Hey,"
            ) + "\n\nHave you had a chance to view my earlier messages?\n\nIn case you missed it, feel free to reach me on Telegram @stephenta100m or we can set up a quick virtual coffee chat upfront if that is easier."
        else:
            content = (
                f"Hey {recipient_name}," if recipient_name else "Hey,"
            ) + "\n\nI understand there can be concerns around quality, English communication, and time-zone overlap when it comes to outsourcing. At Varmeta we focus on strong engineering quality, clear communication, and dependable overlap with client time zones.\n\nHappy to jump on a quick intro call if helpful."
        return subject, content, ""

    if email_type == "manual_follow_up_2":
        if trigger_group == "hiring":
            subject = "how to solve engineer crunch"
            content = (
                f"Hey {recipient_name}," if recipient_name else "Hey,"
            ) + f"\n\nWould like to check in on my last email. Your team's engineering push at {company_name or 'your company'} caught my attention. We've helped clients like 0G Labs, Aethir and Aptos ship dApps and AI agents quickly with our Vietnam engineering team.\n\nIf your firm is scaling fast, we could support with engineering capacity and speed up the rollout. Open to a quick chat next week?"
            return subject, content, ""
        if trigger_group == "funding":
            subject = "is your initiative still on track?"
            content = (
                f"Hey {recipient_name}," if recipient_name else "Hey,"
            ) + f"\n\nI appreciate the progress your team has made around fundraising at {company_name or 'your company'} so far. It also feels like your tech team may see growing demand for AI and software developers, which is why I wanted to reach out.\n\nWe do development work for Aptos, Hedera, Aethir and 0G Labs. Let me know if you would be open to a conversation."
            return subject, content, ""

    system_prompt = f"""
You are a Sales Outreach Specialist generating personalized outreach emails.

The client name is {recipient_name or 'unknown'} and the client company is {company_name or 'unknown company'}.
The sender is {sender_name} from Varmeta.
The email type is {email_type}.
The trigger group is {trigger_group}.

Company Profile:
{company_profile}

Person Profile:
{person_profile}

Trigger List:
{trigger_text or '{}'}

Relevant Information:
{json.dumps(relevant_information, ensure_ascii=False)}

Past Testimonial Information:
{testimonial_text}

Previous Context:
{previous_context}

Rules:
- Return valid JSON with keys "Subject" and "Content".
- Do not include a signature.
- Keep tone simple, natural, concise, and non-salesy.
- Avoid mentioning Varmeta in the subject line.
- Use short paragraph breaks.
"""

    if email_type == "first-email":
        user_prompt = """
Write the first outreach email. Follow the legacy intent:
- If trigger group is hiring, funding, or event, anchor the email to that trigger.
- Otherwise use a general warm outreach mentioning a relevant trigger or recent initiative.
- Keep roughly 5-7 sentences.
- Mention Varmeta as a Web3 development studio in Vietnam with AI/blockchain experience and tie in one or two relevant strengths.
- End with a soft CTA.
"""
    elif email_type == "follow-up-2":
        user_prompt = """
Write a concise follow-up email in 2-3 sentences.
- Build on the previous message naturally and do not repeat the whole introduction.
- Highlight one relevant case study, ecosystem, or reason Varmeta is relevant.
- End with an open, non-pushy CTA.
"""
    elif email_type == "follow-up-4":
        user_prompt = """
Write a final short follow-up email in 2-3 sentences.
- Reinforce credibility by referencing the most relevant success story or testimonial.
- Keep it short, compelling, and friendly.
- End with a soft invitation to discuss further.
"""
    else:
        user_prompt = """
Write a short follow-up email that keeps the tone friendly and concise.
- Use the available trigger and relevant information.
- Keep it actionable but non-pushy.
"""

    return None, None, json.dumps(
        {"system_prompt": system_prompt, "user_prompt": user_prompt},
        ensure_ascii=False,
    )


def _build_event_preview_prompt(
    email_type: str,
    sender_name: str,
    recipient_name: str,
    company_name: str,
    company_profile: str,
    person_profile: str,
    event_name: str,
    event_dates: str,
    event_location: str,
    list_events: List[str],
) -> Tuple[Optional[str], Optional[str], str]:
    if email_type == "second_email":
        subject = "are you the right contact?"
        content = (
            f"Hey {recipient_name}," if recipient_name else "Hey,"
        ) + "\n\nJust following up on my previous email.\n\nLet me know if you're the right person to discuss this. If not, I'd appreciate it if you could point me to one of your colleagues who might be around the event to catch up.\n\nThanks and appreciate your help."
        return subject, content, ""

    if email_type == "third_email":
        subject = f"connect at {event_name}"
        content = (
            f"Hey {recipient_name}," if recipient_name else "Hey,"
        ) + f"\n\nI'll drop by {event_name} this week and would love to catch up while we are both in town.\n\nIf you're open to sharing insights around the evolving web3 landscape, I'd be happy to grab coffee wherever is most convenient for you."
        return subject, content, ""

    if email_type == "fourth_email":
        subject = "don't miss my last message"
        content = (
            f"Hey {recipient_name}," if recipient_name else "Hey,"
        ) + "\n\nHave you had a chance to view my earlier messages?\n\nIn case you missed them, feel free to reach me on Telegram @stephenta100m or we can set up a quick virtual coffee chat once the event rush settles down."
        return subject, content, ""

    system_prompt = f"""
You are a Sales Outreach Specialist generating personalized event outreach emails.
The sender is {sender_name} from Varmeta.
The recipient is {recipient_name or 'unknown'} from {company_name or 'unknown company'}.
Main event: {event_name}
Event dates: {event_dates}
Event location: {event_location}
Side events attended: {list_events}

Company Profile:
{company_profile}

Person Profile:
{person_profile}

Rules:
- Return valid JSON with keys "Subject" and "Content".
- Do not include a signature.
- Keep the tone simple, friendly, and relevant to the event.
- Mention the exact event names provided when relevant.
"""

    user_prompt = """
Write the first outreach email for an event attendee.
- Ask whether they will be at the main event and propose a quick coffee/chat.
- Mention interest in their initiative or product if it can be inferred from the company profile; otherwise keep it generic.
- Briefly introduce Varmeta as a software house in Vietnam working with web3 / AI / blockchain clients.
- End with a soft invitation to exchange ideas.
"""

    return None, None, json.dumps(
        {"system_prompt": system_prompt, "user_prompt": user_prompt},
        ensure_ascii=False,
    )


def _evaluate_generated_email(content: str, expected_word_count: str, requirements: str, spam_words: str) -> Dict[str, Any]:
    system_prompt = f"""
You are a Professional Email Quality Evaluator.
Return valid JSON with PART_1, PART_2, PART_3, COMMENT.

Email Content: {content}
Expected Word Count: {expected_word_count}
Requirements: {requirements}
Spam Words: {spam_words}

Scoring:
- PART_1: score word count fit out of 100
- PART_2: score requirement fit out of 100
- PART_3: 100 if no spam words found, else 0
- COMMENT: concise actionable fixes if needed
"""
    return _call_json_llm(system_prompt, "Evaluate the email.", temperature=0)


def _generate_preview_content(
    sequence: SequenceEmail,
    step: SequenceEmailStep,
    recipient_email: str,
    source: str,
    event_id: Optional[str] = None,
) -> Tuple[str, str, str]:
    user = sequence.user
    signature = sequence.signature
    separator = "<br>----<br>"
    sender_name = _get_sender_display_name(user)
    context = _resolve_preview_recipient_context(recipient_email, source, event_id=event_id)
    projects_data = _load_successful_projects_data()
    testimonial_text = _load_testimonial_description()
    spam_words = _load_spam_words()

    if source == "EVENT":
        guest = GuestList.objects.filter(email__iexact=recipient_email).select_related("company", "event").first()
        event = EventsList.objects.filter(id=event_id or sequence.event_id).first()
        list_events = list(
            GuestList.objects.filter(email__iexact=recipient_email, event__isnull=False)
            .exclude(event__name__isnull=True)
            .values_list("event__name", flat=True)
            .distinct()
        )
        if not list_events and event and event.name:
            list_events = [event.name]
        email_type = {
            1: "first_email",
            2: "second_email",
            3: "third_email",
        }.get(step.step_number, "fourth_email")
        subject, content, prompt_email = _build_event_preview_prompt(
            email_type=email_type,
            sender_name=sender_name,
            recipient_name=context.get("recipient_name") or "",
            company_name=context.get("company_name") or "",
            company_profile=_company_profile_text(guest.company if guest else None),
            person_profile=_person_profile_text(None, guest=guest, source="EVENT"),
            event_name=event.name if event else "",
            event_dates=event.start_date.strftime("%Y-%m-%d") if event and event.start_date else "",
            event_location=event.location if event else "",
            list_events=list_events,
        )
        if subject is None or content is None:
            prompt_payload = json.loads(prompt_email)
            answer = _call_json_llm(
                prompt_payload["system_prompt"],
                prompt_payload["user_prompt"],
            )
            subject = str(answer.get("Subject", "")).strip()
            content = str(answer.get("Content", "")).strip()
        html_content = content.replace("\n", "<br>") + separator + (signature.signature_html if signature else "")
        return subject, html_content, prompt_email

    person = LinkedinPersonalEmail.objects.filter(email__iexact=recipient_email).select_related("company").first()
    company = person.company if person else None
    email_type = {
        1: "first-email",
        2: "manual_follow_up_1",
        3: "follow-up-2",
        4: "manual_follow_up_fix_2",
        5: "follow-up-4",
    }.get(step.step_number, "after-5")

    trigger_dict, relevant_information = (None, None)
    if company:
        trigger_dict, relevant_information = _campaign_cache_get(str(sequence.id), str(company.id))
    if not trigger_dict or not relevant_information:
        trigger_dict = _get_sequence_trigger(company, person)
        relevant_information = _classify_relevant_information_heuristic(
            trigger_dict=trigger_dict,
            person=person,
            company=company,
            projects_data=projects_data,
        )
        if company:
            _campaign_cache_set(str(sequence.id), str(company.id), trigger_dict, relevant_information)

    trigger_group = str(trigger_dict.get("type", "DEFAULT")).lower()
    if trigger_group not in {"hiring", "funding", "event"}:
        trigger_group = "default"

    previous_context = ""
    if MailHistory.objects.filter(main_target_mail=recipient_email, type="RECIEVE").exists() or MailHistory.objects.filter(main_target_mail=recipient_email, type="SEND").exists():
        previous_context = json.dumps(
            [
                {
                    "email_send": item.content or "",
                    "email_reply": "",
                }
                for item in MailHistory.objects.filter(main_target_mail=recipient_email, type="SEND").order_by("-time_send")[:3]
            ],
            ensure_ascii=False,
        )

    subject, content, prompt_email = _build_company_preview_prompt(
        email_type=email_type,
        trigger_group=trigger_group,
        sender_name=sender_name,
        recipient_name=context.get("recipient_name") or "",
        company_name=context.get("company_name") or "",
        company_profile=_company_profile_text(company),
        person_profile=_person_profile_text(person),
        trigger_text=json.dumps(trigger_dict, ensure_ascii=False),
        relevant_information=relevant_information,
        testimonial_text=testimonial_text,
        previous_context=previous_context,
    )

    if subject is None or content is None:
        prompt_payload = json.loads(prompt_email)
        previous_email = ""
        comment = ""
        generated_prompt = prompt_email
        for attempt in range(3):
            answer = _call_json_llm(
                prompt_payload["system_prompt"],
                f"{prompt_payload['user_prompt']}\n\nFeedback: {comment}\n\nPrevious email: {previous_email}",
            )
            subject = str(answer.get("Subject", "")).strip()
            content = str(answer.get("Content", "")).strip()
            generated_prompt = json.dumps(
                {
                    "system_prompt": prompt_payload["system_prompt"],
                    "user_prompt": prompt_payload["user_prompt"],
                    "feedback": comment,
                    "previous_email": previous_email,
                },
                ensure_ascii=False,
            )
            evaluation = _evaluate_generated_email(
                content=content,
                expected_word_count="100-125 words, maximum 125 words" if email_type == "first-email" else "Maximum 100 words",
                requirements="Keep the tone simple, natural, concise and non-pushy.",
                spam_words=spam_words,
            )
            part_1 = int(evaluation.get("PART_1", 0) or 0)
            part_2 = int(evaluation.get("PART_2", 0) or 0)
            part_3 = int(evaluation.get("PART_3", 0) or 0)
            if (part_1 >= 80 and part_2 >= 70 and part_3 == 100) or attempt == 2:
                break
            comment = str(evaluation.get("COMMENT", "") or "")
            previous_email = content
        prompt_email = generated_prompt

    html_content = content.replace("\n", "<br>") + separator + (signature.signature_html if signature else "")
    return subject, html_content, prompt_email


def _resolve_preview_recipient_context(
    recipient_email: str,
    source: str,
    event_id: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    normalized_source = _normalize_sequence_source(source)

    if normalized_source == "EVENT":
        guest_query = GuestList.objects.filter(email__iexact=recipient_email)
        if event_id:
            guest_query = guest_query.filter(event_id=event_id)
        guest = guest_query.select_related("company", "event").first()

        if guest:
            return {
                "recipient_name": guest.name or recipient_email.split("@")[0],
                "company_name": guest.company.name if guest.company else None,
                "event_name": guest.event.name if guest.event else None,
                "event_location": guest.event.location if guest.event else None,
                "event_dates": (
                    guest.event.start_date.strftime("%Y-%m-%d")
                    if guest.event and guest.event.start_date
                    else None
                ),
            }

        event = EventsList.objects.filter(id=event_id).first() if event_id else None
        return {
            "recipient_name": recipient_email.split("@")[0],
            "company_name": None,
            "event_name": event.name if event else None,
            "event_location": event.location if event else None,
            "event_dates": (
                event.start_date.strftime("%Y-%m-%d")
                if event and event.start_date
                else None
            ),
        }

    person = LinkedinPersonalEmail.objects.filter(email__iexact=recipient_email).select_related(
        "company"
    ).first()

    if person:
        recipient_name = " ".join(
            [part for part in [person.first_name, person.last_name] if part]
        ).strip() or recipient_email.split("@")[0]
        return {
            "recipient_name": recipient_name,
            "company_name": person.company.name if person.company else None,
            "event_name": None,
            "event_location": None,
            "event_dates": None,
        }

    return {
        "recipient_name": recipient_email.split("@")[0],
        "company_name": None,
        "event_name": None,
        "event_location": None,
        "event_dates": None,
    }


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

    mail_user_account = MailAppAccount.objects.filter(user_id=user_id, status="ACTIVE").first()
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
        current_follow_up_date = current_follow_up_date + timedelta(days=step_offset_days)
        sequence_steps.append(
            {
                "step_number": index + 1,
                "follow_up_date": current_follow_up_date,
            }
        )

    sequence_name = (
        f"Sequence_{timezone.now().strftime('%Y%m%d%H%M%S')}_User_{user.user_name or user.id}"
    )
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

    sequence_email = SequenceEmail.objects.filter(id=sequence_id, user_id=user_id).first()
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
        failed_item = next((item for item in cached_rows if item["status"] == "FAILED"), None)
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
    sequence = SequenceEmail.objects.select_related("signature", "user").filter(id=sequence_id).first()
    if not sequence:
        raise ValueError("Sequence not found")

    owner = user or sequence.user
    source_value = _normalize_sequence_source(source or sequence.source)
    step_map = {
        str(step.id): step
        for step in SequenceEmailStep.objects.filter(sequence=sequence, id__in=step_ids).order_by("step_number")
    }
    if not step_map:
        return []

    sender_account = MailAppAccount.objects.filter(user=sequence.user, status="ACTIVE").first()
    sender_email = sender_account.email if sender_account else (sequence.user.email or "")
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
                    step_history.email_prompt = generated.email_prompt or step_history.email_prompt
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
    sequence = SequenceEmail.objects.select_related("signature", "user").filter(
        id=sequence_id, user_id=user_id
    ).first()
    if not sequence:
        raise ValueError("Sequence not found")

    if not content_emails:
        raise ValueError("Please provide content_email")

    steps = {
        step.step_number: step
        for step in SequenceEmailStep.objects.filter(sequence__id=sequence_id).order_by("step_number")
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
    return { "list_signatures": [
        {
            "id": str(s["id"]),
            "signature_name": s["signature_name"],
            "signature_html": s["signature_html"],
            "email": s["user_gmail__email"],
            "created_at": s["created_at"],
            "updated_at": s["updated_at"],
        }
        for s in signatures
    ]}


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
