from __future__ import annotations

from typing import Any, ClassVar, Literal

from django.db.models import Q

from neuxo_backend.models import LinkedinPersonalEmail
from .BaseLinkedin import BaseLinkedin

ActorName = Literal[
    "LINKEDIN_GET_LEADS",
    "LINKEDIN_GET_PROFILE_PERSON",
    "LINKEDIN_GET_POST",
    "LINKEDIN_GET_JOB",
]


class LinkedinLeadService(BaseLinkedin):
    ACTOR_NAME: ClassVar[ActorName] = "LINKEDIN_GET_LEADS"
    DEFAULT_RUN_INPUT: ClassVar[dict[str, Any]] = {
        "companyDomain": [],
        "includeEmails": True,
        "seniority": ["CXO", "CEO", "Founder", "Vice President"],
        "totalResults": 100,
        "contactEmailStatus": "verified",
    }

    def run_get_leads_by_company_url(
        self, company_urls: list[str]
    ) -> list[dict[str, Any]]:
        run_input = self._default_run_input()
        run_input["companyDomain"] = company_urls
        return self.run_actor(actor_name="LINKEDIN_GET_LEADS", run_input=run_input)

    def upsert_person_lead(self, lead: dict[str, Any]) -> LinkedinPersonalEmail:
        """
        Insert or update a LinkedinPersonalEmail by normalized linkedin profile URL.
        Also resolves FK `company` by organization linkedin URL (or website fallback).
        """
        linkedin_url = self._normalize_url(str(lead.get("linkedinUrl") or ""))
        if not linkedin_url:
            raise ValueError("lead.linkedinUrl is required")

        company = self._find_company(
            company_linkedin_url=str(lead.get("organizationLinkedinUrl") or ""),
            company_website=str(lead.get("organizationWebsite") or ""),
        )

        defaults: dict[str, Any] = {
            "linkedin_url": linkedin_url,
            "first_name": lead.get("firstName") or "",
            "last_name": lead.get("lastName") or "",
            "role": lead.get("position") or None,
            "email": lead.get("email") or "",
        }

        if company is not None:
            defaults["company"] = company

        existing_person = LinkedinPersonalEmail.objects.filter(
            Q(linkedin_url=linkedin_url) | Q(linkedin_url=f"{linkedin_url}/")
        ).first()

        if existing_person:
            for field, value in defaults.items():
                setattr(existing_person, field, value)
            existing_person.save(update_fields=list(defaults.keys()))
            person = existing_person
        else:
            person = LinkedinPersonalEmail.objects.create(**defaults)
        return person

    def run_get_leads_and_upsert_by_company_url(
        self, company_urls: list[str]
    ) -> list[LinkedinPersonalEmail]:
        leads = self.run_get_leads_by_company_url(company_urls)
        persons: list[LinkedinPersonalEmail] = []
        for lead in leads:
            if lead.get("linkedinUrl"):
                persons.append(self.upsert_person_lead(lead))
        return persons
