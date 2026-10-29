"""Shared conversation serialization using PostgreSQL advisory locks."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


def conversation_lock_key(conversation_id: uuid.UUID) -> int:
    return conversation_id.int % (2**63)


def lock_conversation(session: Session, conversation_id: uuid.UUID) -> None:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": conversation_lock_key(conversation_id)},
        )
        return
    session.execute(
        text("UPDATE conversations SET id = id WHERE id = :id"),
        {"id": str(conversation_id)},
    )
