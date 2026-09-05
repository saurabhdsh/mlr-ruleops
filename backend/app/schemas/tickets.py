from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AttachmentIn(BaseModel):
    filename: str
    content_type: str = "text/plain"
    content: str = ""


class TicketCreate(BaseModel):
    title: str
    description: str
    external_id: str | None = None
    source_system: str = "INTERNAL"
    requester_name: str | None = None
    requester: str | None = None
    requester_email: str | None = None
    priority: str = "MEDIUM"
    market_hint: str | None = None
    brand_hint: str | None = None
    therapeutic_area_hint: str | None = None
    language_hint: str | None = None
    due_date: datetime | None = None
    attachments: list[AttachmentIn] = Field(default_factory=list)


class ClarifyRequest(BaseModel):
    note: str
    market: str | None = None
    brand: str | None = None


class TicketOut(BaseModel):
    id: str
    ticket_number: str
    external_id: str | None
    source_system: str
    title: str
    description: str
    requester_name: str
    requester_email: str
    priority: str
    status: str
    market_hint: str | None
    brand_hint: str | None
    change_type: str | None
    risk_level: str | None
    hitl_gate: str | None = None
    autonomy_tier: str | None = None
    expected_target_rule: str | None = None
    match_confidence: float | None = None
    therapeutic_area_hint: str | None = None
    language_hint: str | None = None
    owner_id: str | None
    current_proposal_id: str | None
    created_at: datetime
    updated_at: datetime
    due_date: datetime | None
    is_demo_seed: bool = False

    model_config = {"from_attributes": True}


class WebhookTicket(BaseModel):
    external_id: str
    source_system: str = "WEBHOOK"
    title: str
    description: str
    requester: str | None = None
    priority: str = "MEDIUM"
    market_hint: str | None = None
    brand_hint: str | None = None
    attachments: list[AttachmentIn] = Field(default_factory=list)
