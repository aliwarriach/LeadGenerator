import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.activity import ActivityTypeLiteral
from app.schemas.lead import PipelineStageLiteral


class DashboardStatsResponse(BaseModel):
    discovered_total: int
    discovered_this_week: int
    no_website_total: int
    no_website_pct: float
    audits_completed_total: int
    audits_completed_this_week: int
    active_deals: int


class DiscoveryVolumeDay(BaseModel):
    day: date
    has_website: int
    no_website: int


class DiscoveryVolumeResponse(BaseModel):
    days: list[DiscoveryVolumeDay]
    total: int


class LeadStageMixEntry(BaseModel):
    stage: PipelineStageLiteral
    count: int


class LeadStageMixResponse(BaseModel):
    items: list[LeadStageMixEntry]
    total: int


class DashboardActivityEntry(BaseModel):
    id: int
    lead_id: uuid.UUID
    lead_name: str
    type: ActivityTypeLiteral
    description: str
    created_at: datetime


class DashboardActivityResponse(BaseModel):
    items: list[DashboardActivityEntry]
