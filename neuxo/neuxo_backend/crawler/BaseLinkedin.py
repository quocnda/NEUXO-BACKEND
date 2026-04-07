from __future__ import annotations

import copy
import re
from typing import Any, ClassVar, Literal

from apify_client import ApifyClient
import requests
from django.db.models import Q
from django.utils import timezone
from . import DEFAULT_MAP_ACTOR_TO_ID
from neuxo_backend.models import LinkedinCompany, LinkedinPersonalEmail, ApifyToken

ActorName = Literal[
    "LINKEDIN_GET_LEADS",
    "LINKEDIN_GET_PROFILE_PERSON",
    "LINKEDIN_GET_POST",
    "LINKEDIN_GET_JOB",
]


class BaseLinkedin:
    STATUS_ACTIVE = "ACTIVE"
    STATUS_UNAVAILABLE = "UNAVAILABLE"

    _COMMON_DOMAIN_PARTS = {
        "http",
        "https",
        "www",
        "com",
        "org",
        "net",
        "io",
        "co",
        "gov",
        "edu",
        "sg",
        "uk",
        "us",
        "vn",
        "au",
        "ca",
        "de",
        "fr",
        "jp",
    }

    DEFAULT_RUN_INPUT: ClassVar[dict[str, Any]] = {}

    def __init__(
        self, actor_name: ActorName | None = None, apify_token: str | None = None
    ) -> None:
        self.actor_name = actor_name
        self.apify_token = apify_token or self._select_apify_token()

    @staticmethod
    def _parse_apify_datetime(value: Any):
        text = BaseLinkedin._safe_str(value)
        if not text:
            return None

        try:
            return timezone.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _get_usage_status_from_token(cls, token_value: str) -> tuple[str | None, Any]:
        url = f"https://api.apify.com/v2/users/me/limits?token={token_value}"
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None, None

        data = payload.get("data", {})
        limits = data.get("limits", {})
        current = data.get("current", {})
        monthly_cycle = data.get("monthlyUsageCycle", {})

        max_monthly_usage_usd = limits.get("maxMonthlyUsageUsd")
        monthly_usage_usd = current.get("monthlyUsageUsd")
        cycle_end_at = cls._parse_apify_datetime(monthly_cycle.get("endAt"))

        try:
            usage_value = float(monthly_usage_usd)
            limit_value = float(max_monthly_usage_usd)
        except (TypeError, ValueError):
            return None, cycle_end_at

        if usage_value < limit_value:
            return cls.STATUS_ACTIVE, None
        return cls.STATUS_UNAVAILABLE, cycle_end_at

    @classmethod
    def _refresh_apify_token_statuses(cls) -> None:
        tokens = ApifyToken.objects.exclude(token__isnull=True).exclude(token="")
        now = timezone.now()

        for token_obj in tokens:
            current_status = (token_obj.status or "").upper()

            if current_status == cls.STATUS_ACTIVE:
                next_status, next_time_available = cls._get_usage_status_from_token(
                    token_obj.token
                )
                if not next_status:
                    continue
                token_obj.status = next_status
                token_obj.next_time_available = next_time_available
                token_obj.save(
                    update_fields=["status", "next_time_available", "updated_at"]
                )
                continue

            if current_status in {cls.STATUS_UNAVAILABLE, "INACTIVE"}:
                if (
                    token_obj.next_time_available
                    and token_obj.next_time_available >= now
                ):
                    next_status, _ = cls._get_usage_status_from_token(token_obj.token)
                    if next_status == cls.STATUS_ACTIVE:
                        token_obj.status = cls.STATUS_ACTIVE
                        token_obj.next_time_available = None
                        token_obj.save(
                            update_fields=[
                                "status",
                                "next_time_available",
                                "updated_at",
                            ]
                        )

    @classmethod
    def _select_apify_token(cls) -> str:
        cls._refresh_apify_token_statuses()

        active_token = (
            ApifyToken.objects.filter(status__iexact=cls.STATUS_ACTIVE)
            .exclude(token__isnull=True)
            .exclude(token="")
            .order_by("updated_at", "created_at")
            .first()
        )
        if not active_token:
            raise ValueError("No active Apify token available in ApifyToken table")
        return active_token.token

    @classmethod
    def _default_run_input(cls) -> dict[str, Any]:
        return copy.deepcopy(cls.DEFAULT_RUN_INPUT)

    def run_actor(
        self,
        actor_name: ActorName | None = None,
        run_input: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        selected_actor = actor_name or self.actor_name
        if not selected_actor:
            raise ValueError("actor_name is required")

        actor_id = DEFAULT_MAP_ACTOR_TO_ID.get(selected_actor)
        if not actor_id:
            raise ValueError(f"actor_id not found for actor_name: {selected_actor}")

        if not self.apify_token:
            self.apify_token = self._select_apify_token()

        client = ApifyClient(self.apify_token)
        run = client.actor(actor_id).call(run_input=run_input)
        return list(client.dataset(run["defaultDatasetId"]).iterate_items())

    def _run_actor(
        self,
        actor_name: ActorName | None = None,
        run_input: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.run_actor(actor_name=actor_name, run_input=run_input)

    @staticmethod
    def _safe_str(value: Any, max_length: int | None = None) -> str | None:
        if value is None:
            return None
        result = str(value).strip()
        if not result:
            return None
        if max_length is not None:
            return result[:max_length]
        return result

    @staticmethod
    def _dict_get(data: dict[str, Any], path: list[str]) -> Any:
        current: Any = data
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

    @staticmethod
    def _normalize_url(url: str | None) -> str:
        if not url:
            return ""
        return url.strip().rstrip("/")

    @staticmethod
    def _get_linkedin_uid(url: str | None) -> str | None:
        if not url:
            return None
        uid = (
            url.split("company/")[-1]
            if "company/" in url
            else url.split("in/")[-1]
            if "in/" in url
            else None
        )
        if uid:
            return uid.replace("/", "").strip()
        return None

    @classmethod
    def _extract_website_terms(cls, website: str | None) -> list[str]:
        if not website:
            return []

        normalized = website.strip().lower()
        if not normalized:
            return []

        if "://" in normalized:
            normalized = normalized.split("://", 1)[1]

        normalized = normalized.split("/", 1)[0]
        normalized = normalized.split("?", 1)[0]
        normalized = normalized.split("#", 1)[0]
        normalized = normalized.lstrip(".")

        if normalized.startswith("www."):
            normalized = normalized[4:]

        raw_terms: list[str] = []
        for label in normalized.split("."):
            if not label:
                continue
            for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", label):
                if len(token) < 3:
                    continue
                if token in cls._COMMON_DOMAIN_PARTS:
                    continue
                raw_terms.append(token)

        if raw_terms:
            unique_terms = list(dict.fromkeys(raw_terms))
            return sorted(unique_terms, key=len, reverse=True)

        fallback = re.sub(r"[^a-z0-9]+", "", normalized)
        return [fallback] if fallback else []

    @staticmethod
    def _extract_linkedin_company_url(url: str | None) -> str | None:
        normalized = BaseLinkedin._normalize_url(url)
        if not normalized:
            return None
        match = re.search(
            r"(https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[^/?#]+)",
            normalized,
            re.IGNORECASE,
        )
        if not match:
            return None
        return BaseLinkedin._normalize_url(match.group(1))

    @staticmethod
    def _extract_linkedin_person_url(url: str | None) -> str | None:
        normalized = BaseLinkedin._normalize_url(url)
        if not normalized:
            return None
        match = re.search(
            r"(https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[^/?#]+)",
            normalized,
            re.IGNORECASE,
        )
        if not match:
            return None
        return BaseLinkedin._normalize_url(match.group(1))

    def _find_company(
        self,
        company_linkedin_url: str | None = None,
        company_website: str | None = None,
    ) -> LinkedinCompany | None:
        uid_linkedin = self._get_linkedin_uid(company_linkedin_url)
        company_website = self._normalize_url(company_website)

        company_query = Q()
        has_company_lookup = False
        if uid_linkedin:
            company_query |= Q(linkedin_url=company_linkedin_url) | Q(
                linkedin_url=f"{company_linkedin_url}"
            )
            has_company_lookup = True
        if company_website:
            company_query |= Q(website=company_website) | Q(
                website=f"{company_website}/"
            )
            has_company_lookup = True

        if not has_company_lookup:
            return None
        return LinkedinCompany.objects.filter(company_query).first()

    @staticmethod
    def _find_person_by_linkedin_url(
        person_url: str | None,
    ) -> LinkedinPersonalEmail | None:
        normalized_person_url = BaseLinkedin._normalize_url(person_url)
        if not normalized_person_url:
            return None

        return (
            LinkedinPersonalEmail.objects.filter(
                Q(linkedin_url=normalized_person_url)
                | Q(linkedin_url=f"{normalized_person_url}/")
            )
            .select_related("company")
            .first()
        )

    def _resolve_company_and_person_for_post(
        self,
        post: dict[str, Any],
    ) -> tuple[LinkedinCompany | None, LinkedinPersonalEmail | None]:
        author_profile_url = self._safe_str(post.get("authorProfileUrl"))
        input_url = self._safe_str(post.get("inputUrl"))

        input_company_url = self._extract_linkedin_company_url(input_url)
        if input_company_url:
            company_url_candidates = [input_company_url]
            author_universal_name = self._safe_str(
                self._dict_get(post, ["author", "universalName"])
            )
            if author_universal_name:
                company_url_candidates.append(
                    self._normalize_url(
                        f"https://www.linkedin.com/company/{author_universal_name}"
                    )
                )

            for company_url in company_url_candidates:
                if not company_url:
                    continue
                company = self._find_company(company_linkedin_url=company_url)
                if company is not None:
                    return company, None
            return None, None

        input_person_url = self._extract_linkedin_person_url(input_url)
        if input_person_url:
            person_url_candidates = [
                input_person_url,
                self._extract_linkedin_person_url(author_profile_url),
            ]

            for person_url in person_url_candidates:
                person = self._find_person_by_linkedin_url(person_url)
                if person is not None and person.company is not None:
                    return person.company, person
            return None, None

        company_url_candidates = [self._extract_linkedin_company_url(input_url)]
        author_universal_name = self._safe_str(
            self._dict_get(post, ["author", "universalName"])
        )
        if author_universal_name:
            company_url_candidates.append(
                self._normalize_url(
                    f"https://www.linkedin.com/company/{author_universal_name}"
                )
            )

        for company_url in company_url_candidates:
            if not company_url:
                continue
            company = self._find_company(company_linkedin_url=company_url)
            if company is not None:
                return company, None

        person_url_candidates = [
            self._extract_linkedin_person_url(input_url),
            self._extract_linkedin_person_url(author_profile_url),
        ]

        for person_url in person_url_candidates:
            person = self._find_person_by_linkedin_url(person_url)
            if person is not None and person.company is not None:
                return person.company, person

        return None, None

    def _resolve_company_for_post(self, post: dict[str, Any]) -> LinkedinCompany | None:
        company, _ = self._resolve_company_and_person_for_post(post)
        return company

    @staticmethod
    def _first_csv_item(value: Any) -> str | None:
        text = BaseLinkedin._safe_str(value)
        if not text:
            return None
        first_item = text.split(",", 1)[0].strip()
        return first_item or None
