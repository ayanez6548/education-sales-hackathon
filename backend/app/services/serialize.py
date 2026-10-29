from __future__ import annotations

from app.domain.states import attention_label, commercial_label
from app.models import Conversation, Course, Message
from app.schemas import ConversationDetail, ConversationSummary, CourseOut, LeadProfileOut, MessageOut

AUTHORSHIP_LABELS = {
    "prospect": "Prospecto",
    "ai": "Asistente",
    "human": "Asesor",
    "system": "Sistema",
}

DELIVERY_LABELS = {
    "accepted": "Aceptado",
    "pending": "Pendiente",
    "sent": "Enviado",
    "failed": "Fallido",
    "unknown": "Resultado incierto",
    "discarded": "Descartado",
}


def course_out(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        slug=course.slug,
        name=course.name,
        description=course.description,
        contents=course.contents,
        requirements=course.requirements,
        modality=course.modality,
        duration=course.duration,
        schedule=course.schedule,
        price_amount=course.price_amount,
        price_currency=course.price_currency,
        authorized_link=course.authorized_link,
        is_fictional_demo=course.is_fictional_demo,
    )


def conversation_summary(item: Conversation) -> ConversationSummary:
    contact = item.contact
    operator = item.assigned_operator
    name = contact.preferred_name or contact.display_name or f"Chat {contact.telegram_chat_id}"
    return ConversationSummary(
        id=item.id,
        contact_name=name,
        preferred_name=contact.preferred_name,
        attention_mode=item.attention_mode,
        attention_label=attention_label(item.attention_mode),
        commercial_state=item.commercial_state,
        commercial_label=commercial_label(item.commercial_state),
        commercial_confidence=item.commercial_confidence,
        last_activity_at=item.last_activity_at,
        unread_count=item.unread_count,
        assigned_operator_id=item.assigned_operator_id,
        assigned_operator_name=operator.display_name if operator else None,
        control_version=item.control_version,
    )


def conversation_detail(item: Conversation) -> ConversationDetail:
    base = conversation_summary(item)
    profile = item.contact.lead_profile
    course_name = None
    if profile and profile.interested_course is not None:
        course_name = profile.interested_course.name
    lead = LeadProfileOut(
        interest_area=profile.interest_area if profile else None,
        experience_level=profile.experience_level if profile else None,
        learning_goal=profile.learning_goal if profile else None,
        availability=profile.availability if profile else None,
        preferred_modality=profile.preferred_modality if profile else None,
        budget_note=profile.budget_note if profile else None,
        interested_course_id=profile.interested_course_id if profile else None,
        interested_course_name=course_name,
    )
    return ConversationDetail(
        **base.model_dump(),
        operator_summary=item.operator_summary,
        transfer_reason=item.transfer_reason,
        commercial_reason=item.commercial_reason,
        classified_at=item.classified_at,
        lead_profile=lead,
        telegram_chat_id=item.contact.telegram_chat_id,
        closed_at=item.closed_at,
    )


def message_out(item: Message) -> MessageOut:
    return MessageOut(
        id=item.id,
        seq=item.seq,
        direction=item.direction,
        authorship=item.authorship,
        authorship_label=AUTHORSHIP_LABELS.get(item.authorship, item.authorship),
        body=item.body,
        delivery_status=item.delivery_status,
        delivery_status_label=DELIVERY_LABELS.get(item.delivery_status, item.delivery_status),
        created_at=item.created_at,
        operator_id=item.operator_id,
    )
