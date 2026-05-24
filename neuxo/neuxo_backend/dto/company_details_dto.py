from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from neuxo_backend.dto.company_dto import (
    CompanyDetailContactItem,
    CompanyDetailEventItem,
    CompanyDetailFundingItem,
    CompanyDetailHiringItem,
    CompanyDetailNewsItem,
)


class AddTwitterForCompanyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url_twitter: str | None = None


class AddTwitterForCompanyData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    link_twitter: str | None = None


class AddTwitterForCompanyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: AddTwitterForCompanyData


class AddContactForCompanyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    linkedin_url: str
    twitter_url: str | None = None


class AddEmailForContactRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str


class UpdateEmailForContactRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str


class SeenNotifyForCompanyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ids: str


class CompanyEventsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: list[CompanyDetailEventItem] = Field(default_factory=list)


class CompanyJobsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: list[CompanyDetailHiringItem] = Field(default_factory=list)


class CompanyContactsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: list[CompanyDetailContactItem] = Field(default_factory=list)


class CompanyFundingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: list[CompanyDetailFundingItem] = Field(default_factory=list)


class CompanyTriggerInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    assignee: str | None = None
    name: str | None = None
    linkedin_url: str | None = None
    website: str | None = None
    link_twitter: str | None = None
    size: str | None = None
    industry: str | None = None
    organization_type: str | None = None
    headquarters: str | None = None
    followers: int | None = None
    category: list[str] = Field(default_factory=list)
    short_description: str | None = None
    label: list[str] = Field(default_factory=list)
    country: str | None = None
    avatar_linkedin_url: str | None = None
    is_blacklist: bool | None = None

    @field_validator("category", "label", mode="before")
    @classmethod
    def normalize_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value


class CompanyTriggerData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_information: CompanyTriggerInfo | None = None
    funding: list[CompanyDetailFundingItem] = Field(default_factory=list)
    hiring: list[CompanyDetailHiringItem] = Field(default_factory=list)
    event: list[CompanyDetailEventItem] = Field(default_factory=list)
    news: list[CompanyDetailNewsItem] = Field(default_factory=list)
    contacts: list[CompanyDetailContactItem] = Field(default_factory=list)


class CompanyTriggerResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: CompanyTriggerData


class ContactExperienceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID | str | int | None = None
    linkedin_company_url: str | None = None
    linkedin_company_logo: str | None = None
    title: str | None = None
    company_name: str | None = None
    time_period: str | None = None
    created_at: str | None = None


class ContactEmailItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID | str | int | None = None
    email: str | None = None


class CompanyContactDetailItem(CompanyDetailContactItem):
    experiences: list[ContactExperienceItem] = Field(default_factory=list)
    emails: list[ContactEmailItem] = Field(default_factory=list)


class CompanyContactDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: list[CompanyContactDetailItem] = Field(default_factory=list)


class CompanyNotifyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    new_notify: int
