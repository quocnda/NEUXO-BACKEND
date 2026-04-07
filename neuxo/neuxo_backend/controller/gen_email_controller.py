"""
Gen-Email Controller - Business Logic for AI-powered email generation.

This module provides simplified email generation using AI (OpenAI/Gemini)
for personalized outreach campaigns.
"""

import json
import os
import re
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class EmailGenerator:
    """
    AI-powered email generator for personalized outreach.
    Supports multiple email types: first_email, follow_up, and custom templates.
    """

    def __init__(
        self,
        sender_name: str,
        recipient_name: str,
        recipient_email: str,
        company_name: Optional[str] = None,
        event_name: Optional[str] = None,
        event_location: Optional[str] = None,
        event_dates: Optional[str] = None,
    ):
        self.sender_name = sender_name
        self.recipient_name = recipient_name
        self.recipient_email = recipient_email
        self.company_name = company_name
        self.event_name = event_name
        self.event_location = event_location
        self.event_dates = event_dates
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

    def _get_llm(self):
        """Initialize and return the OpenAI LLM client."""
        try:
            from openai import OpenAI

            return OpenAI(api_key=self.openai_api_key)
        except ImportError:
            raise Exception("OpenAI package not installed. Run: pip install openai")

    def _build_system_prompt(
        self, email_type: str, custom_instructions: str = ""
    ) -> str:
        """Build the system prompt based on email type."""

        base_instructions = """
### **Role**
You are an expert Sales Outreach Specialist generating personalized professional emails.

### **Output Format**
Return a JSON object with exactly these keys:
- "subject": the email subject line
- "content": the email body (no signature)

Only respond with valid JSON. No explanations or additional text.

### **Language Guidelines**
- Use simple, natural, conversational language
- Keep sentences short and clear
- Avoid overly formal or sales-y wording
- Do not include email signatures
"""

        if email_type == "first_email":
            context = f"""
### **Context**
- Sender: {self.sender_name}
- Recipient: {self.recipient_name or "the recipient"}
- Recipient Email: {self.recipient_email}
- Company: {self.company_name or "their company"}
- Event: {self.event_name or "the upcoming event"}
- Event Location: {self.event_location or ""}
- Event Dates: {self.event_dates or ""}

### **Email Type: First Outreach**
Generate a warm, professional first-contact email for networking at an event.

### **Instructions**
1. Subject: Keep it short, mention company name or event
2. Body:
   - Start with "Hey {self.recipient_name or ""},"
   - Mention the event and ask if they're attending
   - Express genuine interest in connecting
   - Suggest a quick chat/coffee
   - Keep it under 100 words
"""
        elif email_type == "follow_up":
            context = f"""
### **Context**
- Sender: {self.sender_name}
- Recipient: {self.recipient_name or "the recipient"}
- Event: {self.event_name or "the event"}

### **Email Type: Follow-up**
Generate a friendly follow-up email after initial outreach.

### **Instructions**
1. Subject: Reference the event or previous message
2. Body:
   - Start with "Hey {self.recipient_name or ""},"
   - Reference previous outreach briefly
   - Reiterate interest in connecting
   - Keep it under 75 words
"""
        else:
            context = f"""
### **Context**
- Sender: {self.sender_name}
- Recipient: {self.recipient_name or "the recipient"}
- Company: {self.company_name or ""}
- Event: {self.event_name or ""}

### **Custom Email**
{custom_instructions}
"""
        return base_instructions + context

    def generate(
        self, email_type: str = "first_email", custom_instructions: str = ""
    ) -> dict:
        """
        Generate an email using AI.

        Args:
            email_type: Type of email (first_email, follow_up, custom)
            custom_instructions: Additional instructions for custom emails

        Returns:
            dict with 'subject' and 'content' keys
        """
        if not self.openai_api_key:
            raise Exception("OPENAI_API_KEY environment variable not set")

        try:
            client = self._get_llm()
            system_prompt = self._build_system_prompt(email_type, custom_instructions)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the email now."},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON response
            # Try to extract JSON if wrapped in markdown code blocks
            json_match = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL
            )
            if json_match:
                content = json_match.group(1)

            result = json.loads(content)

            return {
                "subject": result.get("subject", ""),
                "content": result.get("content", ""),
                "success": True,
            }

        except json.JSONDecodeError as e:
            return {
                "subject": "",
                "content": content,  # Return raw content if JSON parsing fails
                "success": False,
                "error": f"Failed to parse AI response as JSON: {str(e)}",
            }
        except Exception as e:
            return {
                "subject": "",
                "content": "",
                "success": False,
                "error": str(e),
            }


def generate_email_for_campaign(
    sender_name: str,
    recipient_name: str,
    recipient_email: str,
    company_name: Optional[str] = None,
    event_name: Optional[str] = None,
    event_location: Optional[str] = None,
    event_dates: Optional[str] = None,
    email_type: str = "first_email",
    custom_instructions: str = "",
) -> dict:
    """
    Convenience function to generate an email.

    Args:
        sender_name: Name of the email sender
        recipient_name: Name of the recipient
        recipient_email: Email address of the recipient
        company_name: Name of the recipient's company (optional)
        event_name: Name of the event (optional)
        event_location: Location of the event (optional)
        event_dates: Dates of the event (optional)
        email_type: Type of email (first_email, follow_up, custom)
        custom_instructions: Additional instructions for custom emails

    Returns:
        dict with 'subject', 'content', 'success', and optionally 'error' keys
    """
    generator = EmailGenerator(
        sender_name=sender_name,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        company_name=company_name,
        event_name=event_name,
        event_location=event_location,
        event_dates=event_dates,
    )

    return generator.generate(
        email_type=email_type, custom_instructions=custom_instructions
    )


def validate_email_content(subject: str, content: str) -> dict:
    """
    Validate generated email content for common issues.

    Args:
        subject: Email subject line
        content: Email body content

    Returns:
        dict with 'valid' boolean and optional 'warnings' list
    """
    warnings = []

    # Check subject length
    if len(subject) > 60:
        warnings.append("Subject line is longer than 60 characters")

    if len(subject) < 5:
        warnings.append("Subject line is too short")

    # Check content length
    word_count = len(content.split())
    if word_count > 200:
        warnings.append(f"Email body is {word_count} words - consider shortening")

    if word_count < 20:
        warnings.append("Email body seems too short")

    # Check for common spam trigger words
    spam_words = ["FREE", "URGENT", "ACT NOW", "LIMITED TIME", "CLICK HERE", "BUY NOW"]
    content_upper = content.upper()
    for word in spam_words:
        if word in content_upper:
            warnings.append(f"Contains potential spam trigger word: {word}")

    return {
        "valid": len(warnings) == 0,
        "warnings": warnings,
        "word_count": word_count,
    }
