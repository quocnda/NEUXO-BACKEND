"""
LLM Controller - LLM utilities and email generation
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from neuxo_backend.controller.prompt_engine import (
    get_company_preview_prompts,
    get_email_evaluation_system_prompt,
    get_event_preview_prompts,
)
from neuxo_backend.models import (
    EventsList,
    GuestList,
    LinkedinCompany,
    LinkedinPersonalEmail,
    MailHistory,
    Notification,
    SequenceEmail,
    SequenceEmailStep,
)
from users.models import Users

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DB_PATH = DATA_DIR / "cache_campaign.sqlite"
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_EMAIL_PREVIEW_MODEL", "gpt-4o-mini")


def _normalize_sequence_source(source: Optional[str]) -> str:
    source_value = (source or "COMPANY").strip().upper()
    if source_value == "EVENT":
        return "EVENT"
    return "COMPANY"


def _get_sender_display_name(user: Users) -> str:
    full_name = " ".join(
        [part for part in [user.first_name, user.last_name] if part]
    ).strip()
    return full_name or user.user_name or user.email or "NEUXO"


def _get_openai_client() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return ChatOpenAI(
        api_key=api_key,
        model=DEFAULT_OPENAI_MODEL,
        temperature=0.0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _extract_json_from_response(content: str) -> Dict[str, Any]:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    return json.loads(content)


def _call_json_llm(
    system_prompt: str, user_prompt: str, temperature: float = 0.3
) -> Dict[str, Any]:
    client = _get_openai_client()
    response = client.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
        temperature=temperature,
    )
    content = response.content or "{}"
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
                "client_description": str(
                    row.get("Client description", "") or ""
                ).strip(),
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
    ecosystems = sorted(
        {item["ecosystem"] for item in project_rows if item["ecosystem"]}
    )

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


def _campaign_cache_get(
    sequence_id: str, company_id: str
) -> Tuple[Optional[Dict], Optional[List[Dict]]]:
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


def _get_sequence_trigger(
    company: Optional[LinkedinCompany], person: Optional[LinkedinPersonalEmail]
) -> Dict[str, Any]:
    notifications = (
        list(
            Notification.objects.filter(company=company, guest_id__isnull=True)
            .exclude(type="SUB_DOMAIN")
            .order_by("-time_post")[:20]
            .values(
                "title",
                "type",
                "post_url",
                "reference_id",
                "time_post",
            )
        )
        if company
        else []
    )

    if not notifications and person:
        notifications = list(
            Notification.objects.filter(guest_id=str(person.id))
            .exclude(type="SUB_DOMAIN")
            .order_by("-time_post")[:20]
            .values(
                "title",
                "type",
                "post_url",
                "reference_id",
                "time_post",
            )
        )

    if not notifications:
        return {
            "type": "DEFAULT",
            "trigger_details": None,
            "title": "",
            "description": "",
        }

    recent = notifications[:20]
    trigger_types = [item.get("type") or "DEFAULT" for item in recent]
    trigger_details_list = [
        trigger_type
        for trigger_type in trigger_types
        if trigger_type in {"HIRING", "FUNDING", "EVENT"}
    ]
    titles = [item.get("title", "") or "" for item in recent]
    descriptions = [
        item.get("title", "") or item.get("title", "") or "" for item in recent
    ]

    return {
        "type": ", ".join(trigger_types),
        "trigger_details": ", ".join(trigger_details_list) or None,
        "title": ", ".join([value for value in titles if value]),
        "description": ", ".join([value for value in descriptions if value]),
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


def _person_profile_text(
    person: Optional[LinkedinPersonalEmail],
    guest: Optional[GuestList] = None,
    source: str = "COMPANY",
) -> str:
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
    company_labels = (
        [str(label).lower() for label in (company.labels or [])]
        if company and company.labels
        else []
    )
    trigger_text = (
        f"{trigger_dict.get('title', '')} {trigger_dict.get('description', '')}".lower()
    )

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
        if trigger_text and any(
            token
            for token in trigger_text.split()
            if len(token) > 4 and token in haystacks
        ):
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
                "Action": "Insert a paragraph that highlights that specific project and the synergy with your company's related work.",
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
                    f"Reference Neuxo's experience in {ecosystem} or similar ecosystems and connect it to the client's current initiatives."
                ),
                "Action": "Insert a paragraph referencing that ecosystem and how your team's experience with that or a similar ecosystem can support potential collaboration.",
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
                "Project Description": f"The client is working in {company.category}. Highlight Neuxo's relevant domain expertise and use cases in that category.",
                "Action": "Insert a paragraph referring to that category and your company's relevant domain expertise and use cases.",
            }
        )

    default_actions = [
        {
            "Type": "Neuxo worked",
            "Action": "Insert a paragraph referring to mention that Neuxo has worked with major global partners, notably Layer 1 partners such as Hedera and Aptos.",
        },
        {
            "Type": "Neuxo's expertise",
            "Action": "Insert a paragraph highlight Neuxo's expertise about AI or Blockchain(depending on the customer's field) and readiness to collaborate on future projects.",
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
            (f"Hey {recipient_name}," if recipient_name else "Hey,")
            + "\n\nJust following up on my previous email.\n\nLet me know if you're the right person to discuss this. If not, I'd appreciate it if you could point me in the right direction.\n\nThanks and appreciate your support."
        )
        return subject, content, ""

    if email_type == "manual_follow_up_fix_2":
        subject = "don't miss my last message"
        if trigger_group == "hiring":
            content = (
                (f"Hey {recipient_name}," if recipient_name else "Hey,")
                + "\n\nHave you had a chance to view my earlier messages?\n\nIf the open engineering roles have already been filled or outsourcing is not a fit, feel free to let me know. Otherwise, I believe we could support your project with our blockchain and AI talent in the next 3-6 months."
            )
        elif trigger_group in {"funding", "event"}:
            content = (
                (f"Hey {recipient_name}," if recipient_name else "Hey,")
                + "\n\nHave you had a chance to view my earlier messages?\n\nIn case you missed it, feel free to reach me on Telegram @stephenta100m or we can set up a quick virtual coffee chat upfront if that is easier."
            )
        else:
            content = (
                (f"Hey {recipient_name}," if recipient_name else "Hey,")
                + "\n\nI understand there can be concerns around quality, English communication, and time-zone overlap when it comes to outsourcing. At Neuxo we focus on strong engineering quality, clear communication, and dependable overlap with client time zones.\n\nHappy to jump on a quick intro call if helpful."
            )
        return subject, content, ""

    if email_type == "manual_follow_up_2":
        if trigger_group == "hiring":
            subject = "how to solve engineer crunch"
            content = (
                (f"Hey {recipient_name}," if recipient_name else "Hey,")
                + f"\n\nWould like to check in on my last email. Your team's engineering push at {company_name or 'your company'} caught my attention. We've helped clients like 0G Labs, Aethir and Aptos ship dApps and AI agents quickly with our Vietnam engineering team.\n\nIf your firm is scaling fast, we could support with engineering capacity and speed up the rollout. Open to a quick chat next week?"
            )
            return subject, content, ""
        if trigger_group == "funding":
            subject = "is your initiative still on track?"
            content = (
                (f"Hey {recipient_name}," if recipient_name else "Hey,")
                + f"\n\nI appreciate the progress your team has made around fundraising at {company_name or 'your company'} so far. It also feels like your tech team may see growing demand for AI and software developers, which is why I wanted to reach out.\n\nWe do development work for Aptos, Hedera, Aethir and 0G Labs. Let me know if you would be open to a conversation."
            )
            return subject, content, ""

    system_prompt, user_prompt = get_company_preview_prompts(
        email_type=email_type,
        trigger_group=trigger_group,
        sender_name=sender_name,
        recipient_name=recipient_name,
        company_name=company_name,
        company_profile=company_profile,
        person_profile=person_profile,
        trigger_text=trigger_text,
        relevant_information=relevant_information,
        testimonial_text=testimonial_text,
        previous_context=previous_context,
    )

    return (
        None,
        None,
        json.dumps(
            {"system_prompt": system_prompt, "user_prompt": user_prompt},
            ensure_ascii=False,
        ),
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
            (f"Hey {recipient_name}," if recipient_name else "Hey,")
            + "\n\nJust following up on my previous email.\n\nLet me know if you're the right person to discuss this. If not, I'd appreciate it if you could point me to one of your colleagues who might be around the event to catch up.\n\nThanks and appreciate your help."
        )
        return subject, content, ""

    if email_type == "third_email":
        subject = f"connect at {event_name}"
        content = (
            (f"Hey {recipient_name}," if recipient_name else "Hey,")
            + f"\n\nI'll drop by {event_name} this week and would love to catch up while we are both in town.\n\nIf you're open to sharing insights around the evolving web3 landscape, I'd be happy to grab coffee wherever is most convenient for you."
        )
        return subject, content, ""

    if email_type == "fourth_email":
        subject = "don't miss my last message"
        content = (
            (f"Hey {recipient_name}," if recipient_name else "Hey,")
            + "\n\nHave you had a chance to view my earlier messages?\n\nIn case you missed them, feel free to reach me on Telegram @stephenta100m or we can set up a quick virtual coffee chat once the event rush settles down."
        )
        return subject, content, ""

    system_prompt, user_prompt = get_event_preview_prompts(
        sender_name=sender_name,
        recipient_name=recipient_name,
        company_name=company_name,
        company_profile=company_profile,
        person_profile=person_profile,
        event_name=event_name,
        event_dates=event_dates,
        event_location=event_location,
        list_events=list_events,
    )

    return (
        None,
        None,
        json.dumps(
            {"system_prompt": system_prompt, "user_prompt": user_prompt},
            ensure_ascii=False,
        ),
    )


def _evaluate_generated_email(
    content: str, expected_word_count: str, requirements: str
) -> Dict[str, Any]:
    system_prompt = get_email_evaluation_system_prompt(
        content=content,
        expected_word_count=expected_word_count,
        requirements=requirements,
    )
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
    context = _resolve_preview_recipient_context(
        recipient_email, source, event_id=event_id
    )
    projects_data = _load_successful_projects_data()
    testimonial_text = _load_testimonial_description()

    if source == "EVENT":
        guest = (
            GuestList.objects.filter(email__iexact=recipient_email)
            .select_related("company", "event")
            .first()
        )
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
            event_dates=event.start_date.strftime("%Y-%m-%d")
            if event and event.start_date
            else "",
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
        html_content = (
            content.replace("\n", "<br>")
            + separator
            + (signature.signature_html if signature else "")
        )
        return subject, html_content, prompt_email

    person = (
        LinkedinPersonalEmail.objects.filter(email__iexact=recipient_email)
        .select_related("company")
        .first()
    )
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
        trigger_dict, relevant_information = _campaign_cache_get(
            str(sequence.id), str(company.id)
        )
    if not trigger_dict or not relevant_information:
        trigger_dict = _get_sequence_trigger(company, person)
        relevant_information = _classify_relevant_information_heuristic(
            trigger_dict=trigger_dict,
            person=person,
            company=company,
            projects_data=projects_data,
        )
        if company:
            _campaign_cache_set(
                str(sequence.id), str(company.id), trigger_dict, relevant_information
            )

    trigger_group = str(trigger_dict.get("type", "DEFAULT")).lower()
    if trigger_group not in {"hiring", "funding", "event"}:
        trigger_group = "default"

    previous_context = ""
    if (
        MailHistory.objects.filter(
            main_target_mail=recipient_email, type="RECIEVE"
        ).exists()
        or MailHistory.objects.filter(
            main_target_mail=recipient_email, type="SEND"
        ).exists()
    ):
        previous_context = json.dumps(
            [
                {
                    "email_send": item.content or "",
                    "email_reply": "",
                }
                for item in MailHistory.objects.filter(
                    main_target_mail=recipient_email, type="SEND"
                ).order_by("-time_send")[:3]
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
                expected_word_count="100-125 words, maximum 125 words"
                if email_type == "first-email"
                else "Maximum 100 words",
                requirements="Keep the tone simple, natural, concise and non-pushy.",
            )
            part_1 = int(evaluation.get("PART_1", 0) or 0)
            part_2 = int(evaluation.get("PART_2", 0) or 0)
            part_3 = int(evaluation.get("PART_3", 0) or 0)
            if (part_1 >= 80 and part_2 >= 70 and part_3 == 100) or attempt == 2:
                break
            comment = str(evaluation.get("COMMENT", "") or "")
            previous_email = content
        prompt_email = generated_prompt

    html_content = (
        content.replace("\n", "<br>")
        + separator
        + (signature.signature_html if signature else "")
    )
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

    person = (
        LinkedinPersonalEmail.objects.filter(email__iexact=recipient_email)
        .select_related("company")
        .first()
    )

    if person:
        recipient_name = (
            " ".join(
                [part for part in [person.first_name, person.last_name] if part]
            ).strip()
            or recipient_email.split("@")[0]
        )
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
