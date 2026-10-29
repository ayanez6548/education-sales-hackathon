from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppEvent, AuditEvent, utcnow


def emit_app_event(
    session: Session,
    event_type: str,
    payload: dict[str, Any],
    conversation_id: uuid.UUID | None = None,
) -> AppEvent:
    event = AppEvent(event_type=event_type, payload=payload, conversation_id=conversation_id)
    session.add(event)
    session.flush()
    return event


def emit_audit(
    session: Session,
    action: str,
    *,
    actor_type: str,
    actor_id: str | None = None,
    conversation_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            conversation_id=conversation_id,
            details=details or {},
            created_at=utcnow(),
        )
    )
