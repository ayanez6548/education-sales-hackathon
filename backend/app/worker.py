from __future__ import annotations

import logging
import time
from datetime import timedelta

from sqlalchemy.orm import Session

from app.adapters.llm import LLMAdapter, build_llm_adapter
from app.adapters.telegram import TelegramAdapter, build_telegram_adapter
from app.config import Settings, get_settings
from app.database import get_session_factory
from app.logging_utils import configure_logging
from app.services.jobs import claim_job
from app.models import ProcessingJob, utcnow
from app.services.orchestrator import process_ai_job
from app.services.outbound import send_pending_outbound

logger = logging.getLogger(__name__)


def process_available_work(
    session: Session,
    settings: Settings,
    llm: LLMAdapter,
    telegram: TelegramAdapter,
) -> bool:
    job = claim_job(session, settings)
    # Durable leases allow another worker to recover after a process interruption.
    session.commit()
    did_work = job is not None
    if job is not None:
        job_id = job.id
        try:
            result = process_ai_job(session, settings, llm, job)
            logger.info("job %s %s", job_id, result)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning("job %s failed type=%s", job_id, type(exc).__name__)
            current = session.get(ProcessingJob, job_id)
            if current is not None and current.status == "leased" and current.leased_by == settings.worker_id:
                current.status = "failed" if current.attempts >= settings.job_max_attempts else "pending"
                current.last_error = type(exc).__name__
                current.available_at = utcnow() + timedelta(seconds=min(60, 2 ** current.attempts))
                current.leased_until = None
                session.commit()
    sent = send_pending_outbound(session, telegram, settings)
    # Unknown, discarded and failed outcomes must survive even when no send succeeds.
    session.commit()
    return did_work or sent > 0


def drain_once(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    llm = build_llm_adapter(settings)
    telegram = build_telegram_adapter(settings)
    session = get_session_factory()()
    try:
        while process_available_work(session, settings, llm, telegram):
            continue
    finally:
        session.close()


def run_forever() -> None:
    configure_logging()
    settings = get_settings()
    settings.validate_runtime()
    llm = build_llm_adapter(settings)
    telegram = build_telegram_adapter(settings)
    logger.info("Worker started id=%s llm=%s telegram=%s", settings.worker_id, llm.label, telegram.label)
    while True:
        session = get_session_factory()()
        try:
            worked = process_available_work(session, settings, llm, telegram)
        except Exception:
            session.rollback()
            logger.exception("worker loop error")
            worked = False
        finally:
            session.close()
        if not worked:
            time.sleep(settings.job_poll_seconds)


if __name__ == "__main__":
    from app.database import configure_engine
    from app.bootstrap import prepare_database

    configure_engine()
    prepare_database(get_settings())
    run_forever()
