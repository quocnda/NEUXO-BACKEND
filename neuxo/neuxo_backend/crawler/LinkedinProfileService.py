from __future__ import annotations

from typing import Any, ClassVar, Literal

from django.db.models import Q

from neuxo_backend.models import LinkedinPersonalEmail, PersonalExperience
from .BaseLinkedin import BaseLinkedin

ActorName = Literal[
    "LINKEDIN_GET_LEADS",
    "LINKEDIN_GET_PROFILE_PERSON",
    "LINKEDIN_GET_POST",
    "LINKEDIN_GET_JOB",
]


class LinkedinProfileService(BaseLinkedin):
    ACTOR_NAME: ClassVar[ActorName] = "LINKEDIN_GET_PROFILE_PERSON"
    DEFAULT_RUN_INPUT: ClassVar[dict[str, Any]] = {
        "query": [],
        "profileScraperMode": "Profile details no email ($4 per 1k)",
    }

    def run_get_profile_person_by_query(
        self, queries: list[str]
    ) -> list[dict[str, Any]]:
        run_input = self._default_run_input()
        run_input["query"] = queries
        return self.run_actor(
            actor_name="LINKEDIN_GET_PROFILE_PERSON", run_input=run_input
        )

    def upsert_person_profile(self, profile: dict[str, Any]) -> LinkedinPersonalEmail:
        linkedin_url = self._normalize_url(str(profile.get("linkedinUrl") or ""))
        if not linkedin_url:
            raise ValueError("profile.linkedinUrl is required")

        current_positions = profile.get("currentPosition") or []
        experiences = profile.get("experience") or []

        current_company_linkedin_url = None
        if current_positions and isinstance(current_positions, list):
            current_company_linkedin_url = self._safe_str(
                (current_positions[0] or {}).get("companyLinkedinUrl")
            )
        if (
            not current_company_linkedin_url
            and experiences
            and isinstance(experiences, list)
        ):
            current_company_linkedin_url = self._safe_str(
                (experiences[0] or {}).get("companyLinkedinUrl")
            )

        company = self._find_company(company_linkedin_url=current_company_linkedin_url)

        defaults: dict[str, Any] = {
            "linkedin_url": linkedin_url,
            "first_name": self._safe_str(profile.get("firstName"), 100),
            "last_name": self._safe_str(profile.get("lastName"), 100),
            "role": self._safe_str(profile.get("headline"), 200),
            "avatar_linkedin_url": self._safe_str(
                self._dict_get(profile, ["profilePicture", "url"])
                or profile.get("photo")
            ),
            "about": self._safe_str(profile.get("about")),
            "education": profile.get("education") or [],
            "urn": self._safe_str(profile.get("objectUrn") or profile.get("id")),
            "is_update": 1,
        }

        existing_person = LinkedinPersonalEmail.objects.filter(
            Q(linkedin_url=linkedin_url) | Q(linkedin_url=f"{linkedin_url}/")
        ).first()

        if existing_person and existing_person.email:
            defaults["email"] = existing_person.email
        else:
            defaults["email"] = (
                self._safe_str(profile.get("email"), 100) or "unknown@example.com"
            )

        if company is not None:
            defaults["company"] = company

        if existing_person:
            for field, value in defaults.items():
                setattr(existing_person, field, value)
            existing_person.save(update_fields=list(defaults.keys()))
            person = existing_person
        else:
            person = LinkedinPersonalEmail.objects.create(**defaults)

        for item in experiences:
            if not isinstance(item, dict):
                continue

            start_text = self._safe_str(
                self._dict_get(item, ["startDate", "text"]), 100
            )
            end_text = self._safe_str(self._dict_get(item, ["endDate", "text"]), 100)
            time_period = self._safe_str(
                f"{start_text or ''} - {end_text or ''}".strip(" -")
                or item.get("duration"),
                255,
            )

            PersonalExperience.objects.update_or_create(
                personal=person,
                linkedin_company_id=self._safe_str(item.get("companyId"), 50),
                linkedin_company_url=self._safe_str(item.get("companyLinkedinUrl")),
                title=self._safe_str(item.get("position")),
                company_name=self._safe_str(item.get("companyName")),
                time_period=time_period,
                defaults={
                    "linkedin_company_logo": self._safe_str(
                        self._dict_get(item, ["companyLogo", "url"])
                    ),
                    "location": self._safe_str(item.get("location")),
                    "employment_type": self._safe_str(item.get("employmentType"), 100),
                    "workplace_type": self._safe_str(item.get("workplaceType"), 100),
                    "duration": self._safe_str(item.get("duration"), 100),
                    "description": self._safe_str(item.get("description")),
                    "start_date_text": start_text,
                    "start_month": self._safe_str(
                        self._dict_get(item, ["startDate", "month"]), 20
                    ),
                    "start_year": self._dict_get(item, ["startDate", "year"]),
                    "end_date_text": end_text,
                    "end_month": self._safe_str(
                        self._dict_get(item, ["endDate", "month"]), 20
                    ),
                    "end_year": self._dict_get(item, ["endDate", "year"]),
                    "is_current": (end_text or "").lower() == "present",
                    "company_universal_name": self._safe_str(
                        item.get("companyUniversalName"), 255
                    ),
                    "experience_group_id": self._safe_str(
                        item.get("experienceGroupId"), 255
                    ),
                    "source_profile_url": linkedin_url,
                    "raw_data": item,
                },
            )

        return person

    def run_get_profiles_and_upsert_by_query(
        self, person_urls: list[str]
    ) -> list[LinkedinPersonalEmail]:
        if not person_urls:
            return []

        normalized_queries = [
            normalized_url
            for url in person_urls
            if (normalized_url := self._normalize_url(url))
        ]
        profiles = self.run_get_profile_person_by_query(normalized_queries)

        persons: list[LinkedinPersonalEmail] = []
        for profile in profiles:
            if profile.get("linkedinUrl"):
                persons.append(self.upsert_person_profile(profile))
        return persons
