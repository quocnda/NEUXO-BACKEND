from __future__ import annotations

from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlacklistIdsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ids: list[str] = Field(min_length=1)

    @field_validator("ids", mode="before")
    @classmethod
    def normalize_ids(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            normalized: list[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    normalized.append(text)
            return normalized
        return value


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class BlacklistPagination(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    limit: int
    total_page: int
    total_item: int


class BlacklistExternal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    linkedin: str | None = None
    website: str | None = None
    twitter: str | None = None


class BlacklistCompanyItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID | str | int | None = None
    company_id: UUID | str | int | None = None
    name: str | None = None
    company: str | None = None
    website: str | None = None
    industry: str | None = None
    linkedin_url: str | None = None
    headquarters: str | None = None
    category: str | None = None
    labels: list[str] = Field(default_factory=list)
    label: str | None = None
    size: str | int | None = None
    company_size: str | int | None = None
    organization_type: str | None = None
    short_description: str | None = None
    note_of_user: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    link_twitter: str | None = None
    followers: int | None = None
    linkedin_funding_amt: float | int | None = None
    funding_amount: float | int | None = None
    country: str | None = None
    trigger: list[str] = Field(default_factory=list)
    trigger_time: str | None = None
    external: BlacklistExternal | None = None

    @field_validator("labels", "trigger", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value


class BlacklistMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    columns: list[Any] = Field(default_factory=list)


class BlacklistGetResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    meta: BlacklistMeta
    pagination: BlacklistPagination
    data: list[BlacklistCompanyItem]
