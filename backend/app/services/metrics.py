from __future__ import annotations

from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.states import AttentionMode, CommercialState
from app.models import Conversation, EnrollmentRequest, Message
from app.schemas import MetricsOut

DEFINITIONS = {
    "active_conversations": "Conversaciones cuyo modo de atención no es cerrada.",
    "human_pending": "Solicitudes pendientes de atención humana.",
    "hot_leads": "Prospectos clasificados como lead caliente. Independiente del modo de atención.",
    "enrollment_requests": "Solicitudes de inscripción registradas. No son ventas pagadas ni matrículas confirmadas.",
    "median_first_response_ms": (
        "Mediana del tiempo, en milisegundos, desde el primer mensaje del prospecto "
        "hasta la primera respuesta saliente enviada con estado enviado."
    ),
}


def collect_metrics(session: Session) -> MetricsOut:
    active = session.execute(
        select(func.count()).select_from(Conversation).where(Conversation.attention_mode != AttentionMode.CLOSED)
    ).scalar_one()
    pending = session.execute(
        select(func.count()).select_from(Conversation).where(Conversation.attention_mode == AttentionMode.HUMAN_PENDING)
    ).scalar_one()
    hot = session.execute(
        select(func.count()).select_from(Conversation).where(Conversation.commercial_state == CommercialState.HOT_LEAD)
    ).scalar_one()
    enrollments = session.execute(select(func.count()).select_from(EnrollmentRequest)).scalar_one()
    return MetricsOut(
        active_conversations=int(active or 0),
        human_pending=int(pending or 0),
        hot_leads=int(hot or 0),
        enrollment_requests=int(enrollments or 0),
        median_first_response_ms=_median_first_response(session),
        definitions=DEFINITIONS,
    )


def _median_first_response(session: Session) -> int | None:
    conversations = session.execute(select(Conversation.id)).scalars().all()
    samples: list[float] = []
    for conversation_id in conversations:
        first_in = session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.direction == "inbound")
            .order_by(Message.seq.asc())
            .limit(1)
        ).scalar_one_or_none()
        first_out = session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.direction == "outbound",
                Message.delivery_status == "sent",
            )
            .order_by(Message.seq.asc())
            .limit(1)
        ).scalar_one_or_none()
        if first_in and first_out:
            samples.append((first_out.created_at - first_in.created_at).total_seconds() * 1000)
    if not samples:
        return None
    return int(median(samples))
