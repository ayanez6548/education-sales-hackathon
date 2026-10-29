from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.llm import LLMAdapter, LLMRequest, SYSTEM_RULES
from app.catalog import CatalogCourse, match_courses
from app.config import Settings
from app.domain.locks import lock_conversation
from app.domain.states import AttentionMode, CommercialState, commercial_label
from app.domain.validation import LLMDecision, sanitize_reply
from app.events import emit_app_event, emit_audit
from app.models import Contact, Conversation, Course, EnrollmentRequest, LeadProfile, Message, ProcessingJob, utcnow
from app.services.control import transfer_to_human
from app.services.jobs import mark_job
from app.services.outbound import create_outbound

logger = logging.getLogger(__name__)


def process_ai_job(
    session: Session,
    settings: Settings,
    llm: LLMAdapter,
    job: ProcessingJob,
) -> str:
    lock_conversation(session, job.conversation_id)
    conversation = session.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.contact).selectinload(Contact.lead_profile).selectinload(LeadProfile.interested_course),
            selectinload(Conversation.assigned_operator),
        )
        .where(Conversation.id == job.conversation_id)
    ).scalar_one()

    if _is_obsolete(conversation, job):
        mark_job(session, job, "discarded", "obsolete_turn_or_control")
        emit_audit(
            session,
            "ai_discarded",
            actor_type="worker",
            conversation_id=conversation.id,
            details={"job_id": str(job.id), "reason": "obsolete"},
        )
        return "discarded"

    courses = _active_courses(session)
    history = _history(session, conversation.id, settings.max_history_messages)
    profile = _profile_dict(conversation)
    catalog_courses = [
        CatalogCourse(
            slug=item.slug,
            name=item.name,
            description=item.description,
            contents=item.contents,
            requirements=item.requirements,
            modality=item.modality,
            duration=item.duration,
            schedule=item.schedule,
            price_amount=item.price_amount,
            price_currency=item.price_currency,
            authorized_link=item.authorized_link,
            search_aliases=item.search_aliases or [],
        )
        for item in courses
    ]
    inbound = next((item["content"] for item in reversed(history) if item["role"] == "prospect"), "")
    # Release the control lock during inference so an operator can take over immediately.
    expected_attempt = job.attempts
    job_id = job.id
    request = LLMRequest(
        user_text=inbound, history=history, profile=profile,
        courses=catalog_courses, rules=SYSTEM_RULES,
    )
    session.commit()
    failure = None
    try:
        decision = llm.complete(request)
    except Exception as exc:
        failure = type(exc).__name__
        logger.warning("LLM adapter failed type=%s", failure)

    lock_conversation(session, conversation.id)
    session.refresh(conversation)
    session.refresh(job)
    if (job.status != "leased" or job.attempts != expected_attempt
            or job.leased_by != settings.worker_id):
        return "discarded"
    if _is_obsolete(conversation, job):
        mark_job(session, job, "discarded", "obsolete_after_inference")
        return "discarded"
    if failure:
        transfer_to_human(session, conversation, "No se pudo generar la respuesta", notify=True)
        mark_job(session, job, "failed", failure)
        return "failed"
    courses = _active_courses(session)

    apply_decision(session, conversation, courses, decision, settings)

    session.flush()
    if _is_obsolete(conversation, job) or conversation.attention_mode != AttentionMode.AI_ACTIVE:
        mark_job(session, job, "discarded", "control_changed_before_send")
        return "discarded"

    reply = sanitize_reply(decision.reply_text, courses, decision.matched_course_slug)[: settings.max_output_chars]
    create_outbound(
        session,
        conversation,
        reply,
        "ai",
        dedupe_key=f"ai:{conversation.id}:{job.expected_control_version}:{job.expected_inbound_seq}",
        control_version=job.expected_control_version,
        expected_inbound_seq=job.expected_inbound_seq,
        expected_attention_mode=AttentionMode.AI_ACTIVE,
        send_gate="ai",
    )
    conversation.last_ai_turn_seq = job.expected_inbound_seq or conversation.last_inbound_seq
    mark_job(session, job, "completed")
    return "completed"


def apply_decision(
    session: Session,
    conversation: Conversation,
    courses: list[Course],
    decision: LLMDecision,
    settings: Settings,
) -> None:
    contact = conversation.contact
    profile = contact.lead_profile
    if profile is None:
        profile = LeadProfile(contact_id=contact.id)
        session.add(profile)
        session.flush()

    updates = decision.profile_updates
    if updates.preferred_name:
        contact.preferred_name = updates.preferred_name[:120]
    if updates.interest_area:
        profile.interest_area = updates.interest_area[:160]
    if updates.experience_level:
        profile.experience_level = updates.experience_level[:80]
    if updates.learning_goal:
        profile.learning_goal = updates.learning_goal
    if updates.availability:
        profile.availability = updates.availability[:160]
    if updates.preferred_modality:
        profile.preferred_modality = updates.preferred_modality[:80]
    if updates.budget_note:
        profile.budget_note = updates.budget_note[:160]

    matched = None
    if decision.matched_course_slug:
        matched = next((item for item in courses if item.slug == decision.matched_course_slug), None)
        if matched:
            profile.interested_course_id = matched.id
            profile.interest_area = profile.interest_area or matched.name

    if decision.commercial_state:
        conversation.commercial_state = decision.commercial_state.value
        conversation.commercial_confidence = decision.commercial_confidence
        conversation.commercial_reason = decision.commercial_reason
        conversation.classified_at = utcnow()

    if decision.enrollment and decision.enrollment.consent:
        course = next((item for item in courses if item.slug == decision.enrollment.course_slug), None)
        if course is None:
            logger.warning("Rejected enrollment for unknown slug %s", decision.enrollment.course_slug)
        else:
            existing = session.execute(
                select(EnrollmentRequest).where(
                    EnrollmentRequest.contact_id == contact.id,
                    EnrollmentRequest.course_id == course.id,
                    EnrollmentRequest.intent_key == "primary",
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    EnrollmentRequest(
                        contact_id=contact.id,
                        conversation_id=conversation.id,
                        course_id=course.id,
                        consent_given=True,
                        status="registered",
                        notes=decision.enrollment.notes,
                    )
                )
            conversation.commercial_state = CommercialState.HOT_LEAD.value
            conversation.classified_at = utcnow()
            conversation.commercial_reason = "Solicitud de inscripción registrada"
            emit_app_event(session, "enrollment.created", {"course": course.slug}, conversation.id)

    if decision.request_human:
        transfer_to_human(session, conversation, decision.request_human_reason or "Solicitud de asesor", notify=True)
        conversation.operator_summary = _build_summary(conversation, profile, "Solicitud de asesor")
    elif conversation.operator_summary is None and conversation.last_inbound_seq >= 6:
        conversation.operator_summary = _build_summary(conversation, profile, "Resumen automático por historial")

    emit_app_event(
        session,
        "conversation.updated",
        {
            "commercial_state": conversation.commercial_state,
            "attention_mode": conversation.attention_mode,
        },
        conversation.id,
    )
    _ = settings
    _ = match_courses


def _is_obsolete(conversation: Conversation, job: ProcessingJob) -> bool:
    if conversation.control_version != job.expected_control_version:
        return True
    if conversation.attention_mode != AttentionMode.AI_ACTIVE:
        return True
    if job.expected_inbound_seq is not None and (conversation.last_inbound_seq != job.expected_inbound_seq or conversation.last_ai_turn_seq >= job.expected_inbound_seq):
        return True
    return False


def _active_courses(session: Session) -> list[Course]:
    return list(session.execute(select(Course).where(Course.active.is_(True))).scalars())


def _history(session: Session, conversation_id: Any, limit: int) -> list[dict[str, str]]:
    rows = session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.seq.desc())
        .limit(limit)
    ).scalars().all()
    rows = list(reversed(rows))
    return [{"role": item.authorship, "content": item.body} for item in rows]


def _profile_dict(conversation: Conversation) -> dict[str, Any]:
    contact = conversation.contact
    profile = contact.lead_profile
    return {
        "preferred_name": contact.preferred_name,
        "interest_area": profile.interest_area if profile else None,
        "experience_level": profile.experience_level if profile else None,
        "learning_goal": profile.learning_goal if profile else None,
        "availability": profile.availability if profile else None,
        "preferred_modality": profile.preferred_modality if profile else None,
        "budget_note": profile.budget_note if profile else None,
        "interested_course_slug": profile.interested_course.slug if profile and profile.interested_course else None,
    }


def _build_summary(conversation: Conversation, profile: LeadProfile, reason: str) -> str:
    name = conversation.contact.preferred_name or conversation.contact.display_name or "Prospecto"
    interest = profile.interest_area or "interés aún no definido"
    state = commercial_label(conversation.commercial_state)
    return (
        f"{name}. Interés: {interest}. Clasificación: {state}. "
        f"Motivo: {reason}. Experiencia: {profile.experience_level or 'no indicada'}."
    )
