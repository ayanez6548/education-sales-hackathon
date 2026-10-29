from datetime import timedelta, timezone

from sqlalchemy import select

from app.adapters.telegram import DemoTelegramAdapter, TelegramSendResult
from app.domain.states import AttentionMode
from app.services.control import takeover
from app.services.inbox import ingest_telegram_text
from app.models import Conversation, Message, OutboundMessage, ProcessingJob, utcnow
from app.services.jobs import claim_job
from app.services.orchestrator import process_ai_job
from app.services.outbound import create_outbound, send_pending_outbound
from app.adapters.llm import DemoLLMAdapter


def _ingest(session, settings, text: str, update_id: str, message_id: str):
    return ingest_telegram_text(
        session,
        settings,
        update_id=update_id,
        telegram_user_id="10001",
        telegram_chat_id="10001",
        display_name="Ana",
        text=text,
        telegram_message_id=message_id,
    )


def test_queued_ai_is_not_sent_after_confirmed_takeover(session, settings, operator_a) -> None:
    result = _ingest(session, settings, "Hola, busco excel", "u1", "m1")
    conversation = session.get(Conversation, result.conversation_id)
    assert conversation is not None
    create_outbound(
        session,
        conversation,
        "Respuesta automática que no debe salir tras el takeover",
        "ai",
        dedupe_key="ai-queued-before-takeover",
        control_version=conversation.control_version,
        expected_inbound_seq=conversation.last_inbound_seq,
        expected_attention_mode=AttentionMode.AI_ACTIVE,
        send_gate="ai",
    )
    session.commit()

    takeover(session, conversation, operator_a)
    session.commit()

    adapter = DemoTelegramAdapter()
    send_pending_outbound(session, adapter, settings)
    session.commit()

    outbound = session.execute(select(OutboundMessage)).scalar_one()
    assert outbound.status == "discarded"
    assert adapter.sent == []
    message = session.get(Message, outbound.message_id)
    assert message is not None
    assert message.delivery_status == "discarded"


def test_stale_inbound_turn_discards_ai_outbound(session, settings) -> None:
    first = _ingest(session, settings, "Quiero python", "u-a", "m-a")
    conversation = session.get(Conversation, first.conversation_id)
    assert conversation is not None
    create_outbound(
        session,
        conversation,
        "Respuesta al primer mensaje",
        "ai",
        dedupe_key="ai-first-turn",
        control_version=conversation.control_version,
        expected_inbound_seq=conversation.last_inbound_seq,
        expected_attention_mode=AttentionMode.AI_ACTIVE,
        send_gate="ai",
    )
    session.commit()
    _ingest(session, settings, "Mejor inglés", "u-b", "m-b")
    session.commit()

    adapter = DemoTelegramAdapter()
    send_pending_outbound(session, adapter, settings)
    session.commit()
    outbound = session.execute(select(OutboundMessage).where(OutboundMessage.dedupe_key == "ai-first-turn")).scalar_one()
    assert outbound.status == "discarded"
    assert all("primer mensaje" not in item["text"] for item in adapter.sent)


def test_expired_job_lease_is_reclaimed(session, settings) -> None:
    result = _ingest(session, settings, "Hola", "u-lease", "m-lease")
    queued = session.execute(select(ProcessingJob).where(ProcessingJob.conversation_id == result.conversation_id)).scalar_one()
    queued.status = "leased"
    queued.leased_by = "dead-worker"
    queued.leased_until = utcnow() - timedelta(seconds=5)
    queued.attempts = 1
    session.commit()

    claimed = claim_job(session, settings)
    assert claimed is not None
    assert claimed.id == queued.id
    assert claimed.status == "leased"
    assert claimed.leased_by == settings.worker_id


def test_obsolete_job_is_discarded_after_takeover(session, settings, operator_a) -> None:
    result = _ingest(session, settings, "Quiero python para datos", "u-job", "m-job")
    job = session.execute(select(ProcessingJob).where(ProcessingJob.conversation_id == result.conversation_id)).scalar_one()
    conversation = session.get(Conversation, result.conversation_id)
    takeover(session, conversation, operator_a)
    session.commit()
    session.refresh(job)
    status = process_ai_job(session, settings, DemoLLMAdapter(), job)
    assert status == "discarded"
    assert job.status == "discarded"


def test_rate_limit_schedules_wait_instead_of_immediate_retries(session, settings) -> None:
    result = _ingest(session, settings, "Hola", "u-retry", "m-retry")
    conversation = session.get(Conversation, result.conversation_id)
    assert conversation is not None
    create_outbound(
        session,
        conversation,
        "No debe reintentarse en ráfaga",
        "ai",
        dedupe_key="ai-retry-wait",
        control_version=conversation.control_version,
        expected_inbound_seq=conversation.last_inbound_seq,
        expected_attention_mode=AttentionMode.AI_ACTIVE,
        send_gate="ai",
    )
    session.commit()

    class RateLimitedAdapter:
        label = "test-retry"
        calls = 0

        def send_message(self, chat_id: str, text: str) -> TelegramSendResult:
            self.calls += 1
            return TelegramSendResult("failed", None, "rate_limited", 45)

    adapter = RateLimitedAdapter()
    send_pending_outbound(session, adapter, settings)
    send_pending_outbound(session, adapter, settings)
    session.commit()
    outbound = session.execute(select(OutboundMessage).where(OutboundMessage.dedupe_key == "ai-retry-wait")).scalar_one()
    assert adapter.calls == 1
    assert outbound.status == "pending"
    assert outbound.available_at is not None
    available = outbound.available_at
    if available.tzinfo is None:
        available = available.replace(tzinfo=timezone.utc)
    assert available > utcnow()


def test_demo_llm_then_sender_delivers_when_ai_still_active(session, settings) -> None:
    result = _ingest(session, settings, "Quiero el curso de phyton", "u-ok", "m-ok")
    session.commit()
    claimed = claim_job(session, settings)
    assert claimed is not None
    session.commit()
    status = process_ai_job(session, settings, DemoLLMAdapter(), claimed)
    assert status == "completed"
    adapter = DemoTelegramAdapter()
    sent = send_pending_outbound(session, adapter, settings)
    session.commit()
    assert sent == 1
    assert adapter.sent
    assert "Python" in adapter.sent[0]["text"] or "python" in adapter.sent[0]["text"].lower()
