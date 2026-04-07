from __future__ import annotations
from typing import Any, ClassVar, Literal

from django.utils import timezone

from neuxo_backend.models import (
    LinkedinCompany,
    LinkedinJob,
    LinkedinLocation,
    Notification,
)
from .BaseLinkedin import BaseLinkedin


ActorName = Literal[
    "LINKEDIN_GET_LEADS",
    "LINKEDIN_GET_PROFILE_PERSON",
    "LINKEDIN_GET_POST",
    "LINKEDIN_GET_JOB",
]

class LinkedinJobService(BaseLinkedin):
    ACTOR_NAME: ClassVar[ActorName] = "LINKEDIN_GET_JOB"
    DEFAULT_RUN_INPUT: ClassVar[dict[str, Any]] = {
        "company_names": [],
        "jobs_entries": 20,
        "location": "Worldwide",
        "start_jobs": 0,
    }

    def run_get_jobs_by_company_names(self, company_names: list[str]) -> list[dict[str, Any]]:
        run_input = self._default_run_input()
        run_input["company_names"] = company_names
        return self.run_actor(actor_name="LINKEDIN_GET_JOB", run_input=run_input)

    def _resolve_job_company(self, job: dict[str, Any]) -> LinkedinCompany | None:
        company_url = self._safe_str(job.get("company_url"))
        company_name = self._safe_str(job.get("company_name"), 100)

        company = self._find_company(company_linkedin_url=company_url)
        if company is not None:
            return company

        if company_name:
            return LinkedinCompany.objects.filter(name__iexact=company_name).first()
        return None

    def _upsert_job_notification(self, linkedin_job: LinkedinJob) -> None:
        if linkedin_job.company is None:
            return

        time_post = linkedin_job.updated_at or linkedin_job.last_check or timezone.now()
        notification, created = Notification.objects.get_or_create(
            reference_id=str(linkedin_job.id),
            type="HIRING",
            company=linkedin_job.company,
            defaults={
                "title": linkedin_job.title,
                "post_url": linkedin_job.linkedin_url,
                "time_post": time_post,
            },
        )
        if not created:
            notification.title = linkedin_job.title
            notification.post_url = linkedin_job.linkedin_url
            notification.time_post = time_post
            notification.save(update_fields=["title", "post_url", "time_post"])

    def upsert_linkedin_job(self, job: dict[str, Any]) -> LinkedinJob:
        title = self._safe_str(job.get("job_title"), 1000)
        if not title:
            raise ValueError("job.job_title is required")

        linkedin_url = self._normalize_url(self._safe_str(job.get("job_url")) or self._safe_str(job.get("apply_url")) or "")
        company = self._resolve_job_company(job)

        location_name = self._safe_str(job.get("location"), 100)
        location = None
        if location_name:
            location, _ = LinkedinLocation.objects.get_or_create(name=location_name)

        time_posted = self._safe_str(job.get("time_posted"))
        num_applicants = self._safe_str(job.get("num_applicants"))
        salary_range = self._safe_str(job.get("salary_range"))
        easy_apply_value = job.get("easy_apply")
        easy_apply_text = str(easy_apply_value) if easy_apply_value is not None else None

        seniority_level = self._safe_str(job.get("seniority_level"))
        employment_type = self._safe_str(job.get("employment_type"))
        job_function = self._safe_str(job.get("job_function"))

        short_description_parts = [
            f"Time posted: {time_posted}" if time_posted else None,
            f"Applicants: {num_applicants}" if num_applicants else None,
            f"Seniority: {seniority_level}" if seniority_level else None,
            f"Employment type: {employment_type}" if employment_type else None,
            f"Function: {job_function}" if job_function else None,
            f"Salary range: {salary_range}" if salary_range else None,
            f"Easy apply: {easy_apply_text}" if easy_apply_text else None,
        ]
        short_description = " | ".join(part for part in short_description_parts if part)

        note_parts = [
            f"job_id={self._safe_str(job.get('job_id'))}" if self._safe_str(job.get("job_id")) else None,
            f"company_url={self._safe_str(job.get('company_url'))}" if self._safe_str(job.get("company_url")) else None,
            f"company_logo_url={self._safe_str(job.get('company_logo_url'))}" if self._safe_str(job.get("company_logo_url")) else None,
            f"apply_url={self._safe_str(job.get('apply_url'))}" if self._safe_str(job.get("apply_url")) else None,
        ]
        note = "\n".join(part for part in note_parts if part)

        defaults: dict[str, Any] = {
            "title": title,
            "company": company,
            "location": location,
            "description": self._safe_str(job.get("job_description")),
            "short_description": self._safe_str(short_description),
            "status": "active",
            "note": self._safe_str(note),
        }

        existing = None
        if linkedin_url:
            existing = LinkedinJob.objects.filter(linkedin_url=linkedin_url).first()
        if existing is None and company is not None:
            existing = LinkedinJob.objects.filter(company=company, title=title).first()

        if existing:
            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.linkedin_url = linkedin_url or existing.linkedin_url
            existing.last_check = timezone.now()
            existing.updated_at = timezone.now()
            existing.save(update_fields=[*list(defaults.keys()), "linkedin_url", "last_check", "updated_at"])
            linkedin_job = existing
        else:
            linkedin_job = LinkedinJob.objects.create(linkedin_url=linkedin_url or None, last_check=timezone.now(), **defaults)

        self._upsert_job_notification(linkedin_job)
        return linkedin_job

    def run_get_jobs_and_upsert_by_company_names(self, company_names: list[str]) -> list[LinkedinJob]:
        jobs = self.run_get_jobs_by_company_names(company_names)
        upserted_jobs: list[LinkedinJob] = []
        for job in jobs:
            upserted_jobs.append(self.upsert_linkedin_job(job))
        return upserted_jobs
