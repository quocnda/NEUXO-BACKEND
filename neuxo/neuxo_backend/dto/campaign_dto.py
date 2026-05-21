from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CampaignListQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1)
    start_date: datetime | None = None
    end_date: datetime | None = None
    campaign_status: str | None = None
    search_key: str | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_datetime(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
        return value


class CampaignDetailQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1)
    email_status: str | None = None


class CampaignPagination(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    total_page: int
    total_item: int


class CampaignListItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    campaign_id: str
    campaign_name: str
    day_created: str
    total_email_sent: int
    total_email_replied: int
    total_email_opened: int
    campaign_status: str
    status_choice: list[str] = Field(default_factory=list)


class CampaignListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    pagination: CampaignPagination
    data: list[CampaignListItem]


class UpdateCampaignStatusRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status_campaign: Literal["Resume", "Pause", "Stop", "Remove"]


class EditCampaignNameRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    campaign_name: str


class CampaignEmailDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    sent_count: int
    reply_count: int
    opened_count: int
    status: str


class CampaignDetailStatistics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_targets: int
    total_sent: int
    total_received: int
    total_opened: int
    total_error: int


class CampaignDetailPagination(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int
    total_page: int
    total_item: int


class CampaignDetailData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    campaign_id: str
    campaign_name: str
    campaign_status: str
    status_choice: list[str] = Field(default_factory=list)
    created_at: str
    start_date: str | None = None
    end_date: str | None = None
    statistics: CampaignDetailStatistics
    pagination: CampaignDetailPagination
    email_details: list[CampaignEmailDetail]


class CampaignDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: CampaignDetailData


class CampaignAboutData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    campaign_id: str
    campaign_name: str
    sequence_name: str | None = None
    source: str | None = None
    event_id: str | int | None = None
    created_at: str
    start_date: str | None = None
    end_date: str | None = None
    email_targets_count: int
    enable_bimonthly_send: bool | None = None
    max_email_bimonthly: int | None = None


class CampaignAboutResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: CampaignAboutData


class AdminEmailStatsData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_campaigns: int
    total_emails_sent: int
    total_emails_received: int


class AdminEmailStatsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    data: AdminEmailStatsData


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class ValidationErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    errors: list[dict[str, Any]] = Field(default_factory=list)
