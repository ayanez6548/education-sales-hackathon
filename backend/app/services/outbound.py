from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.adapters.telegram import TelegramAdapter
from app.config import Settings, get_settings
from app.domain.locks import lock_conversation
from app.domain.states import AttentionMode
from app.events import emit_app_event
from app.models import Conversation, Message, OutboundMessage, utcnow

logger = logging.getLogger(__name__)

MAX_OUTBOUND_ATTEMPTS = 5
CLAIMABLE_STATUSES = ("pending", "failed")


def next_seq(session: Session, conversation_id: uuid.UUID) -> int:
    current = session.execute(
        select(Message.seq).where(Message.conversation_id == conversation_id).order_by(Message.seq.desc())
    ).scalars().first()
    return (current or 0) + 1


def create_outbound(
    session: Session,
    conversation: Conversation,
    body: str,
    authorship: str,
    *,
    operator_id: uuid.UUID | None = None,
    dedupe_key: str,
    control_version: int,
    expected_inbound_seq: int | None = None,
    expected_attention_mode: str | None = None,
    send_gate: str | None = None,
) -> Message:
    existing = session.execute(select(OutboundMessage).where(OutboundMessage.dedupe_key == dedupe_key)).scalar_one_or_none()
    if existing:
        return session.get(Message, existing.message_id)  # type: ignore[return-value]

    gate = send_gate or {"ai": "ai", "human": "human", "system": "system"}.get(authorship, "ai")
    mode = expected_attention_mode or conversation.attention_mode
    message = Message(
        conversation_id=conversation.id,
        seq=next_seq(session, conversation.id),
        direction="outbound",
        authorship=authorship,
        body=body,
        telegram_chat_id=conversation.contact.telegram_chat_id,
        delivery_status="pending",
        operator_id=operator_id,
        created_at=utcnow(),
    )
    session.add(message)
    session.flush()
    outbound = OutboundMessage(
        message_id=message.id,
        conversation_id=conversation.id,
        dedupe_key=dedupe_key,
        telegram_chat_id=conversation.contact.telegram_chat_id,
        body=body,
        status="pending",
        send_gate=gate,
        expected_control_version=control_version,
        expected_inbound_seq=expected_inbound_seq,
        expected_attention_mode=mode,
        available_at=utcnow(),
    )
    session.add(outbound)
    conversation.last_activity_at = utcnow()
    emit_app_event(
        session,
        "message.created",
        {"message_id": str(message.id), "seq": message.seq, "authorship": authorship, "control_version": control_version},
        conversation.id,
    )
    return message


def enqueue_system_message(session: Session, conversation: Conversation, body: str) -> Message:
    key = f"system:{conversation.id}:{conversation.control_version}:handover"
    return create_outbound(
        session,
        conversation,
        body,
        "system",
        dedupe_key=key,
        control_version=conversation.control_version,
        expected_inbound_seq=conversation.last_inbound_seq,
        expected_attention_mode=conversation.attention_mode,
        send_gate="system",
    )


def retry_delay_seconds(attempts: int, retry_after_seconds: float | None) -> float:
    if retry_after_seconds is not None and retry_after_seconds > 0:
        return float(retry_after_seconds)
    return float(min(2 ** max(attempts, 1), 60))


def claim_outbound(session: Session, settings: Settings) -> OutboundMessage | None:
    now = utcnow()
    dialect = session.get_bind().dialect.name
    due = or_(OutboundMessage.available_at.is_(None), OutboundMessage.available_at <= now)
    recoverable = and_(
        due,
        or_(
            OutboundMessage.status.in_(CLAIMABLE_STATUSES),
            (OutboundMessage.status == "sending")
            & (OutboundMessage.leased_until.is_not(None))
            & (OutboundMessage.leased_until < now),
        ),
    )
    stmt = (
        select(OutboundMessage.id)
        .where(recoverable, OutboundMessage.attempts < MAX_OUTBOUND_ATTEMPTS)
        .order_by(OutboundMessage.created_at)
        .limit(1)
    )
    if dialect == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    candidate_id = session.execute(stmt).scalar_one_or_none()
    if candidate_id is None:
        return None
    result = session.execute(
        update(OutboundMessage)
        .where(OutboundMessage.id == candidate_id, recoverable)
        .values(
            status="sending",
            leased_by=settings.worker_id,
            leased_until=now + timedelta(seconds=settings.job_lease_seconds),
            attempts=OutboundMessage.attempts + 1,
        )
    )
    if result.rowcount != 1:
        return None
    return session.get(OutboundMessage, candidate_id)


def outbound_still_valid(conversation: Conversation, outbound: OutboundMessage, message: Message) -> tuple[bool, str]:
    if outbound.send_gate == "ai" or message.authorship == "ai":
        if conversation.control_version != outbound.expected_control_version:
            return False, "control_version_mismatch"
        if conversation.attention_mode != AttentionMode.AI_ACTIVE:
            return False, "attention_mode_mismatch"
        if conversation.attention_mode != outbound.expected_attention_mode:
            return False, "expected_attention_mode_mismatch"
        if (
            outbound.expected_inbound_seq is not None
            and conversation.last_inbound_seq != outbound.expected_inbound_seq
        ):
            return False, "stale_inbound_turn"
        return True, "ok"
    if outbound.send_gate == "human" or message.authorship == "human":
        if conversation.attention_mode != AttentionMode.HUMAN_ACTIVE:
            return False, "attention_mode_mismatch"
        if conversation.control_version != outbound.expected_control_version:
            return False, "control_version_mismatch"
        return True, "ok"
    if conversation.attention_mode == AttentionMode.CLOSED:
        return False, "conversation_closed"
    return True, "ok"


def send_pending_outbound(
    session: Session,
    adapter: TelegramAdapter,
    settings: Settings | None = None,
    limit: int = 20,
) -> int:
    settings = settings or get_settings()
    sent = 0
    for _ in range(limit):
        outbound = claim_outbound(session, settings)
        if outbound is None:
            break
        lock_conversation(session, outbound.conversation_id)
        conversation = session.execute(
            select(Conversation)
            .options(selectinload(Conversation.contact))
            .where(Conversation.id == outbound.conversation_id)
        ).scalar_one()
        session.refresh(outbound)
        message = session.get(Message, outbound.message_id)
        if message is None:
            outbound.status = "failed"
            outbound.last_error = "missing_message"
            session.commit()
            continue
        valid, reason = outbound_still_valid(conversation, outbound, message)
        if not valid:
            outbound.status = "discarded"
            outbound.last_error = reason
            outbound.leased_until = None
            message.delivery_status = "discarded"
            message.delivery_error = reason
            emit_app_event(
                session,
                "message.delivery",
                {"message_id": str(message.id), "delivery_status": "discarded", "reason": reason},
                outbound.conversation_id,
            )
            logger.info("discarded outbound %s reason=%s", outbound.id, reason)
            session.commit()
            continue
        result = adapter.send_message(outbound.telegram_chat_id, outbound.body)
        if result.status == "sent":
            outbound.status = "sent"
            outbound.sent_at = utcnow()
            outbound.leased_until = None
            message.delivery_status = "sent"
            message.telegram_message_id = result.telegram_message_id
            message.telegram_chat_id = outbound.telegram_chat_id
            sent += 1
        elif result.status == "unknown":
            outbound.status = "unknown"
            outbound.last_error = result.error
            outbound.leased_until = None
            message.delivery_status = "unknown"
            message.delivery_error = result.error
        else:
            if outbound.attempts >= MAX_OUTBOUND_ATTEMPTS:
                outbound.status = "failed"
                message.delivery_status = "failed"
            else:
                delay = retry_delay_seconds(outbound.attempts, result.retry_after_seconds)
                outbound.status = "pending"
                outbound.available_at = utcnow() + timedelta(seconds=delay)
                message.delivery_status = "pending"
            outbound.last_error = result.error
            outbound.leased_until = None
            message.delivery_error = result.error
        emit_app_event(
            session,
            "message.delivery",
            {"message_id": str(message.id), "delivery_status": message.delivery_status},
            outbound.conversation_id,
        )
        session.commit()
    return sent


def load_conversation_with_contact(session: Session, conversation_id: uuid.UUID) -> Conversation | None:
    return session.execute(
        select(Conversation)
        .options(selectinload(Conversation.contact), selectinload(Conversation.assigned_operator))
        .where(Conversation.id == conversation_id)
    ).scalar_one_or_none()
