from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.domain.locks import lock_conversation
from app.domain.states import AttentionMode
from app.events import emit_app_event, emit_audit
from app.models import Contact, Conversation, LeadProfile, Message, TelegramUpdate, utcnow
from app.services.control import reopen_closed
from app.services.jobs import enqueue_ai_job
from app.services.outbound import next_seq

logger = logging.getLogger(__name__)


@dataclass
class InboundResult:
    conversation_id: uuid.UUID
    message_id: uuid.UUID | None
    duplicate: bool
    job_id: uuid.UUID | None


def ingest_telegram_text(
    session: Session,
    settings: Settings,
    *,
    update_id: str,
    telegram_user_id: str,
    telegram_chat_id: str,
    display_name: str | None,
    text: str,
    telegram_message_id: str,
) -> InboundResult:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = session.get(TelegramUpdate, update_id)
    if existing is not None:
        conversation = _latest_conversation_for_chat(session, telegram_chat_id)
        return InboundResult(conversation.id, None, True, None)

    session.add(TelegramUpdate(update_id=update_id, payload_digest=digest))
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        conversation = _latest_conversation_for_chat(session, telegram_chat_id)
        return InboundResult(conversation.id, None, True, None)

    clipped = text[: settings.max_input_chars]
    contact = _get_or_create_contact(session, telegram_user_id, telegram_chat_id, display_name)
    conversation = _open_conversation(session, contact)
    lock_conversation(session, conversation.id)
    session.refresh(conversation)

    if conversation.attention_mode == AttentionMode.CLOSED:
        reopen_closed(session, conversation)

    duplicate_msg = session.execute(
        select(Message).where(
            Message.telegram_chat_id == telegram_chat_id,
            Message.telegram_message_id == telegram_message_id,
        )
    ).scalar_one_or_none()
    if duplicate_msg is not None:
        return InboundResult(conversation.id, duplicate_msg.id, True, None)

    seq = next_seq(session, conversation.id)
    message = Message(
        conversation_id=conversation.id,
        seq=seq,
        direction="inbound",
        authorship="prospect",
        body=clipped,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        delivery_status="accepted",
        created_at=utcnow(),
    )
    session.add(message)
    conversation.last_inbound_seq = seq
    conversation.last_activity_at = utcnow()
    conversation.unread_count += 1
    session.flush()

    job_id = None
    if conversation.attention_mode == AttentionMode.AI_ACTIVE:
        job = enqueue_ai_job(session, conversation.id, conversation.control_version, seq)
        job_id = job.id

    emit_audit(
        session,
        "inbound_message",
        actor_type="prospect",
        actor_id=telegram_user_id,
        conversation_id=conversation.id,
        details={"seq": seq},
    )
    emit_app_event(
        session,
        "message.created",
        {"message_id": str(message.id), "seq": seq, "authorship": "prospect"},
        conversation.id,
    )
    emit_app_event(
        session,
        "conversation.updated",
        {"unread_count": conversation.unread_count, "attention_mode": conversation.attention_mode},
        conversation.id,
    )
    return InboundResult(conversation.id, message.id, False, job_id)


def _get_or_create_contact(
    session: Session, telegram_user_id: str, telegram_chat_id: str, display_name: str | None
) -> Contact:
    contact = session.execute(select(Contact).where(Contact.telegram_user_id == telegram_user_id)).scalar_one_or_none()
    if contact is None:
        contact = Contact(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            display_name=display_name,
        )
        session.add(contact)
        session.flush()
        session.add(LeadProfile(contact_id=contact.id))
        session.flush()
        return contact
    contact.telegram_chat_id = telegram_chat_id
    if display_name:
        contact.display_name = display_name
    return contact


def _open_conversation(session: Session, contact: Contact) -> Conversation:
    item = session.execute(
        select(Conversation)
        .options(selectinload(Conversation.contact))
        .where(Conversation.contact_id == contact.id)
        .order_by(Conversation.created_at.desc())
    ).scalars().first()
    if item is None:
        item = Conversation(contact_id=contact.id, attention_mode=AttentionMode.AI_ACTIVE)
        session.add(item)
        session.flush()
        session.refresh(item, attribute_names=["contact"])
    return item


def _latest_conversation_for_chat(session: Session, telegram_chat_id: str) -> Conversation:
    contact = session.execute(select(Contact).where(Contact.telegram_chat_id == telegram_chat_id)).scalar_one()
    return session.execute(
        select(Conversation).where(Conversation.contact_id == contact.id).order_by(Conversation.created_at.desc())
    ).scalars().first()
