from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ProcessingJob, utcnow

logger = logging.getLogger(__name__)


def enqueue_ai_job(
    session: Session,
    conversation_id: uuid.UUID,
    control_version: int,
    inbound_seq: int,
    payload: dict | None = None,
) -> ProcessingJob:
    job = ProcessingJob(
        job_type="ai_reply",
        conversation_id=conversation_id,
        payload=payload or {},
        expected_control_version=control_version,
        expected_inbound_seq=inbound_seq,
        status="pending",
        available_at=utcnow(),
    )
    session.add(job)
    session.flush()
    return job


def claim_job(session: Session, settings: Settings) -> ProcessingJob | None:
    now = utcnow()
    session.execute(
        update(ProcessingJob)
        .where(
            ProcessingJob.status.in_(("pending", "leased")),
            ProcessingJob.attempts >= settings.job_max_attempts,
            or_(ProcessingJob.leased_until.is_(None), ProcessingJob.leased_until <= now),
        )
        .values(status="failed", last_error="attempt_limit_reached", completed_at=now, leased_until=None)
    )
    dialect = session.get_bind().dialect.name
    recoverable = or_(
        ProcessingJob.status == "pending",
        (ProcessingJob.status == "leased") & (ProcessingJob.leased_until.is_not(None)) & (ProcessingJob.leased_until < now),
    )
    if dialect == "postgresql":
        candidate_id = session.execute(
            select(ProcessingJob.id)
            .where(recoverable, ProcessingJob.available_at <= now, ProcessingJob.attempts < settings.job_max_attempts)
            .order_by(ProcessingJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).scalar_one_or_none()
    else:
        candidate_id = session.execute(
            select(ProcessingJob.id)
            .where(recoverable, ProcessingJob.available_at <= now, ProcessingJob.attempts < settings.job_max_attempts)
            .order_by(ProcessingJob.created_at)
            .limit(1)
        ).scalar_one_or_none()
    if candidate_id is None:
        return None
    claimed = session.execute(
        update(ProcessingJob)
        .where(ProcessingJob.id == candidate_id, recoverable, ProcessingJob.attempts < settings.job_max_attempts)
        .values(
            status="leased",
            leased_by=settings.worker_id,
            leased_until=now + timedelta(seconds=settings.job_lease_seconds),
            attempts=ProcessingJob.attempts + 1,
        )
    )
    if claimed.rowcount != 1:
        return None
    session.expire_all()
    return session.get(ProcessingJob, candidate_id)


def recover_expired_leases(session: Session) -> int:
    now = utcnow()
    result = session.execute(
        update(ProcessingJob)
        .where(ProcessingJob.status == "leased", ProcessingJob.leased_until.is_not(None), ProcessingJob.leased_until < now)
        .values(status="pending", leased_by=None)
    )
    return result.rowcount or 0


def mark_job(session: Session, job: ProcessingJob, status: str, error: str | None = None) -> None:
    job.status = status
    job.last_error = error
    if status in {"completed", "discarded", "failed"}:
        job.completed_at = utcnow()
        job.leased_until = None
