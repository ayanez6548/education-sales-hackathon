from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ApiModel(BaseModel):
    @field_validator("*", mode="after")
    @classmethod
    def normalize_utc_dates(cls, value):
        # SQLite returns naive UTC values; retain the same instant in JSON responses.
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class LoginRequest(ApiModel):
    email: str
    password: str


class OperatorOut(ApiModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    operator: OperatorOut


class CourseOut(ApiModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    contents: str
    requirements: str
    modality: str
    duration: str
    schedule: str
    price_amount: int
    price_currency: str
    authorized_link: str | None
    is_fictional_demo: bool


class LeadProfileOut(ApiModel):
    interest_area: str | None = None
    experience_level: str | None = None
    learning_goal: str | None = None
    availability: str | None = None
    preferred_modality: str | None = None
    budget_note: str | None = None
    interested_course_id: uuid.UUID | None = None
    interested_course_name: str | None = None


class ConversationSummary(ApiModel):
    id: uuid.UUID
    contact_name: str
    preferred_name: str | None
    attention_mode: str
    attention_label: str
    commercial_state: str | None
    commercial_label: str
    commercial_confidence: float | None
    last_activity_at: datetime
    unread_count: int
    assigned_operator_id: uuid.UUID | None
    assigned_operator_name: str | None
    control_version: int


class ConversationDetail(ConversationSummary):
    operator_summary: str | None
    transfer_reason: str | None
    commercial_reason: str | None
    classified_at: datetime | None
    lead_profile: LeadProfileOut
    telegram_chat_id: str
    closed_at: datetime | None


class MessageOut(ApiModel):
    id: uuid.UUID
    seq: int
    direction: str
    authorship: str
    authorship_label: str
    body: str
    delivery_status: str
    delivery_status_label: str
    created_at: datetime
    operator_id: uuid.UUID | None = None


class SendMessageRequest(ApiModel):
    body: str = Field(min_length=1, max_length=4000)


class DemoInboundRequest(ApiModel):
    text: str = Field(min_length=1, max_length=4000)
    telegram_user_id: str = "10001"
    telegram_chat_id: str = "10001"
    display_name: str = "Prospecto Demo"
    update_id: str | None = None


class MetricsOut(ApiModel):
    active_conversations: int
    human_pending: int
    hot_leads: int
    enrollment_requests: int
    median_first_response_ms: int | None
    definitions: dict[str, str]


class EventOut(ApiModel):
    id: int
    conversation_id: uuid.UUID | None
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
