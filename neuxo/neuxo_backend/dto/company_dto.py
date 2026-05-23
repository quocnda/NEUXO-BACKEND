from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class ValidationErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    errors: list[dict[str, Any]] = Field(default_factory=list)


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class ShowingColumn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    is_show: bool
    can_arrange: bool = False


class UpdateShowingColumnItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    is_show: bool
    can_arrange: bool | None = None


class UpdateShowingColumnsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name_columns: list[UpdateShowingColumnItem] = Field(min_length=1)


class UpdateShowingColumnsData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    columns: list[ShowingColumn]


class UpdateShowingColumnsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: UpdateShowingColumnsData


class MatchingCompanyExternal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    linkedin: str | None = None
    website: str | None = None
    email: str | None = None
    twitter: str | None = None


class MatchingCompanyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_id: UUID | str | int | None = None
    company: str | None = None
    external: MatchingCompanyExternal | None = None
    label: str | None = None
    trigger: list[str] = Field(default_factory=list)
    trigger_time: str | None = None
    updated_at: str | None = None
    funding_amount: str | int | float | None = None
    contacts: bool | None = None
    company_size: str | int | None = None
    category: str | None = None
    followers: int | None = None
    headquarters: str | None = None
    country: str | None = None
    organization_type: str | None = None
    industry: str | None = None
    note: str | None = None
    avatar_url: str | None = None
    short_description: str | None = None
    watchlist: bool | None = None
    lst_email: list[str] = Field(default_factory=list)
    status_mail: str | None = None
    is_in_watchlist: int | None = None

    @field_validator("trigger", "lst_email", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value


class MatchingCompanyPagination(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    limit: int
    total_page: int
    total_item: int


class MatchingCompanyMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    columns: list[ShowingColumn] = Field(default_factory=list)


class MatchingCompanyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    meta: MatchingCompanyMeta
    pagination: MatchingCompanyPagination
    data: list[MatchingCompanyItem]


class SalesListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: list[str]


class CountryCompanyData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    list_country: list[str] = Field(default_factory=list)
    industry: list[str] = Field(default_factory=list)
    organization_type: list[str] = Field(default_factory=list)
    trigger: list[str] = Field(default_factory=list)


class CountryCompanyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: CountryCompanyData


class ColumnFieldResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    columns: list[ShowingColumn]


class CompanyDetailFundingItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    date: str | None = None
    amount: str | None = None
    category: str | None = None
    project_url: str | None = None


class CompanyDetailHiringItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    category__name: str | None = None
    linkedin_url: str | None = None
    label__name: str | None = None
    created_at: str | None = None


class CompanyDetailEventItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    event_url: str | None = None
    start_date: str | None = None


class CompanyDetailContactItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID | str | int | None = None
    first_name: str | None = None
    last_name: str | None = None
    linkedin_url: str | None = None
    role: str | None = None
    twitter_url: str | None = None
    created_at: str | None = None
    avatar_linkedin_url: str | None = None
    name: str | None = None


class CompanyDetailNewsItem(BaseModel):
    model_config = ConfigDict(extra="allow")


class CompanyDetailData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    assignee: str | None = None
    name: str | None = None
    linkedin_url: str | None = None
    twitter_url: str | None = None
    website: str | None = None
    size: str | None = None
    industry: str | None = None
    organization_type: str | None = None
    headquarters: str | None = None
    followers: int | None = None
    category: list[str] = Field(default_factory=list)
    short_description: str | None = None
    label: list[str] = Field(default_factory=list)
    country: str | None = None
    avatar_url: str | None = None
    is_blacklist: bool | None = None
    note_watchlist: str | None = None
    watchlist: bool | None = None
    is_in_watchlist: int | None = None
    funding: list[CompanyDetailFundingItem] = Field(default_factory=list)
    hiring: list[CompanyDetailHiringItem] = Field(default_factory=list)
    event: list[CompanyDetailEventItem] = Field(default_factory=list)
    news: list[CompanyDetailNewsItem] = Field(default_factory=list)
    contacts: list[CompanyDetailContactItem] = Field(default_factory=list)

    @field_validator("category", "label", mode="before")
    @classmethod
    def normalize_detail_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value


class CompanyDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: CompanyDetailData


class CompanyNoteItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_id: UUID | str | int
    note: str


class AddCompanyNoteRequest(RootModel[list[CompanyNoteItem]]):
    pass


class AddCompanyNoteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: str
