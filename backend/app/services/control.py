from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.locks import lock_conversation
from app.domain.states import AttentionMode, RESUME_FROM, TAKEOVER_FROM
from app.events import emit_app_event, emit_audit
from app.models import Conversation, OperatorProfile, ProcessingJob, utcnow
from app.services.outbound import enqueue_system_message
from app.services.presence import connected_count


class ControlConflict(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=409, detail=detail)


def load_conversation(session: Session, conversation_id: uuid.UUID) -> Conversation:
    item = session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return item


def assigned_to_other(conversation: Conversation, operator: OperatorProfile) -> bool:
    return (
        conversation.assigned_operator_id is not None
        and conversation.assigned_operator_id != operator.id
        and conversation.attention_mode == AttentionMode.HUMAN_ACTIVE
    )


def ensure_not_owned_by_other(conversation: Conversation, operator: OperatorProfile) -> None:
    if assigned_to_other(conversation, operator):
        raise ControlConflict("Otro asesor tiene el control de esta conversación")


def takeover(session: Session, conversation: Conversation, operator: OperatorProfile) -> Conversation:
    lock_conversation(session, conversation.id)
    session.refresh(conversation)
    if conversation.attention_mode == AttentionMode.CLOSED:
        raise HTTPException(status_code=409, detail="La conversación está cerrada")
    if assigned_to_other(conversation, operator):
        raise ControlConflict("Otro asesor ya tomó el control")
    if (
        conversation.attention_mode == AttentionMode.HUMAN_ACTIVE
        and conversation.assigned_operator_id == operator.id
    ):
        return conversation
    if conversation.attention_mode not in TAKEOVER_FROM and conversation.attention_mode != AttentionMode.HUMAN_ACTIVE:
        raise HTTPException(status_code=409, detail="No se puede tomar el control en este estado")
    conversation.attention_mode = AttentionMode.HUMAN_ACTIVE
    conversation.assigned_operator_id = operator.id
    conversation.control_version += 1
    conversation.last_activity_at = utcnow()
    _discard_open_ai_jobs(session, conversation)
    emit_audit(
        session,
        "takeover",
        actor_type="operator",
        actor_id=str(operator.id),
        conversation_id=conversation.id,
        details={"control_version": conversation.control_version},
    )
    emit_app_event(
        session,
        "conversation.updated",
        {"attention_mode": conversation.attention_mode, "assigned_operator_id": str(operator.id)},
        conversation.id,
    )
    return conversation


def resume_ai(session: Session, conversation: Conversation, operator: OperatorProfile) -> Conversation:
    lock_conversation(session, conversation.id)
    session.refresh(conversation)
    ensure_not_owned_by_other(conversation, operator)
    if conversation.attention_mode not in RESUME_FROM:
        raise HTTPException(status_code=409, detail="No se puede reanudar la IA en este estado")
    conversation.attention_mode = AttentionMode.AI_ACTIVE
    conversation.assigned_operator_id = None
    conversation.control_version += 1
    conversation.last_activity_at = utcnow()
    emit_audit(
        session,
        "resume_ai",
        actor_type="operator",
        actor_id=str(operator.id),
        conversation_id=conversation.id,
        details={"control_version": conversation.control_version},
    )
    emit_app_event(session, "conversation.updated", {"attention_mode": conversation.attention_mode}, conversation.id)
    return conversation


def close_conversation(session: Session, conversation: Conversation, operator: OperatorProfile) -> Conversation:
    lock_conversation(session, conversation.id)
    session.refresh(conversation)
    ensure_not_owned_by_other(conversation, operator)
    if conversation.attention_mode == AttentionMode.CLOSED:
        return conversation
    conversation.attention_mode = AttentionMode.CLOSED
    conversation.closed_at = utcnow()
    conversation.control_version += 1
    conversation.last_activity_at = utcnow()
    _discard_open_ai_jobs(session, conversation)
    emit_audit(
        session,
        "close",
        actor_type="operator",
        actor_id=str(operator.id),
        conversation_id=conversation.id,
        details={"control_version": conversation.control_version},
    )
    emit_app_event(session, "conversation.updated", {"attention_mode": conversation.attention_mode}, conversation.id)
    return conversation


def transfer_to_human(
    session: Session,
    conversation: Conversation,
    reason: str,
    *,
    notify: bool,
) -> None:
    if conversation.attention_mode != AttentionMode.AI_ACTIVE:
        return
    conversation.attention_mode = AttentionMode.HUMAN_PENDING
    conversation.transfer_reason = reason[:280]
    conversation.control_version += 1
    conversation.last_activity_at = utcnow()
    _discard_open_ai_jobs(session, conversation, keep_current=True)
    if notify:
        if connected_count() == 0:
            body = (
                "Registré tu solicitud de asesor. Quedó pendiente en el tablero; "
                "no puedo prometerte un tiempo de respuesta."
            )
        else:
            body = "Te conecto con un asesor. La atención automática queda en pausa."
        enqueue_system_message(session, conversation, body)
    emit_audit(
        session,
        "transfer_human_pending",
        actor_type="system",
        conversation_id=conversation.id,
        details={"reason": reason[:280]},
    )
    emit_app_event(
        session,
        "conversation.updated",
        {"attention_mode": conversation.attention_mode, "transfer_reason": conversation.transfer_reason},
        conversation.id,
    )


def reopen_closed(session: Session, conversation: Conversation) -> None:
    conversation.attention_mode = AttentionMode.HUMAN_PENDING
    conversation.closed_at = None
    conversation.control_version += 1
    conversation.transfer_reason = "Nuevo mensaje en conversación cerrada"
    conversation.last_activity_at = utcnow()
    emit_app_event(
        session,
        "conversation.updated",
        {"attention_mode": conversation.attention_mode, "reopened": True},
        conversation.id,
    )


def _discard_open_ai_jobs(session: Session, conversation: Conversation, keep_current: bool = False) -> None:
    jobs = session.execute(
        select(ProcessingJob).where(
            ProcessingJob.conversation_id == conversation.id,
            ProcessingJob.status.in_(("pending", "leased")),
            ProcessingJob.job_type == "ai_reply",
        )
    ).scalars()
    for job in jobs:
        job.status = "discarded"
        job.completed_at = utcnow()
        job.last_error = "control_changed"
