"""
Prompt Engine - central prompt templates for email generation/evaluation.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


def get_company_preview_prompts(
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
) -> Tuple[str, str]:
    system_prompt = f"""
You are a Sales Outreach Specialist generating personalized outreach emails.

The client name is {recipient_name or "unknown"} and the client company is {company_name or "unknown company"}.
The sender is {sender_name} from Neuxo.
The email type is {email_type}.
The trigger group is {trigger_group}.

Company Profile:
{company_profile}

Person Profile:
{person_profile}

Trigger List:
{trigger_text or "{}"}

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
- Avoid mentioning Neuxo in the subject line.
- Use short paragraph breaks.
"""

    if email_type == "first-email":
        user_prompt = """
Write the first outreach email. Follow the legacy intent:
- If trigger group is hiring, funding, or event, anchor the email to that trigger.
- Otherwise use a general warm outreach mentioning a relevant trigger or recent initiative.
- Keep roughly 5-7 sentences.
- Mention Neuxo as a Web3 development studio in Vietnam with AI/blockchain experience and tie in one or two relevant strengths.
- End with a soft CTA.
"""
    elif email_type == "follow-up-2":
        user_prompt = """
Write a concise follow-up email in 2-3 sentences.
- Build on the previous message naturally and do not repeat the whole introduction.
- Highlight one relevant case study, ecosystem, or reason Neuxo is relevant.
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

    return system_prompt, user_prompt


def get_event_preview_prompts(
    sender_name: str,
    recipient_name: str,
    company_name: str,
    company_profile: str,
    person_profile: str,
    event_name: str,
    event_dates: str,
    event_location: str,
    list_events: List[str],
) -> Tuple[str, str]:
    system_prompt = f"""
You are a Sales Outreach Specialist generating personalized event outreach emails.
The sender is {sender_name} from Neuxo.
The recipient is {recipient_name or "unknown"} from {company_name or "unknown company"}.
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
- Briefly introduce Neuxo as a software house in Vietnam working with web3 / AI / blockchain clients.
- End with a soft invitation to exchange ideas.
"""

    return system_prompt, user_prompt


def get_email_evaluation_system_prompt(
    content: str, expected_word_count: str, requirements: str
) -> str:
    return f"""
You are a Professional Email Quality Evaluator.
Return valid JSON with PART_1, PART_2, COMMENT.

Email Content: {content}
Expected Word Count: {expected_word_count}
Requirements: {requirements}

Scoring:
- PART_1: score word count fit out of 100
- PART_2: score requirement fit out of 100
- COMMENT: concise actionable fixes if needed
"""
