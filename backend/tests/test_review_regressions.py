"""Regression coverage from independent review of handover and delivery failures."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app import database
from app.adapters.llm import DemoLLMAdapter
from app.adapters.telegram import DemoTelegramAdapter, TelegramSendResult
from app.config import Settings
from app.models import Conversation, Message, OperatorProfile, OutboundMessage, ProcessingJob, utcnow
from app.seed import seed_all
from app.services.control import takeover
from app.services.inbox import ingest_telegram_text
from app.services.jobs import claim_job
from app.services.orchestrator import process_ai_job
from app.worker import process_available_work


@pytest.fixture
def review_store(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///" + (tmp_path / "review.db").as_posix(),
        embed_worker=False,
        worker_id="review-worker",
    )
    engine = database.configure_engine(settings.database_url)
    database.Base.metadata.create_all(engine)
    factory = database.get_session_factory()
    with factory() as session:
        seed_all(session, settings)
        session.commit()
    yield settings, factory
    engine.dispose()


def receive(session, settings, text, index=1):
    result = ingest_telegram_text(
        session, settings, update_id=f"review-{index}",
        telegram_user_id="review-user", telegram_chat_id="review-chat",
        display_name="Prospecto de prueba", text=text, telegram_message_id=f"incoming-{index}",
    )
    session.commit()
    return result.conversation_id


def test_demo_message_ids_are_unique_across_adapter_instances():
    first = DemoTelegramAdapter().send_message("chat", "Uno")
    second = DemoTelegramAdapter().send_message("chat", "Dos")
    assert first.telegram_message_id != second.telegram_message_id


def test_two_demo_turns_survive_recreated_adapters(review_store):
    settings, factory = review_store
    with factory() as session:
        conversation_id = receive(session, settings, "Quiero aprender Python", 1)
        process_available_work(session, settings, DemoLLMAdapter(), DemoTelegramAdapter())
        receive(session, settings, "Cuanto cuesta Python?", 2)
        process_available_work(session, settings, DemoLLMAdapter(), DemoTelegramAdapter())
        replies = session.scalars(select(Message).where(
            Message.conversation_id == conversation_id, Message.authorship == "ai",
        )).all()
        assert len(replies) == 2
        assert all(reply.delivery_status == "sent" for reply in replies)
        assert len({reply.telegram_message_id for reply in replies}) == 2


def test_takeover_is_possible_while_model_is_generating(review_store):
    settings, factory = review_store
    with factory() as session:
        conversation_id = receive(session, settings, "Quiero aprender Python")
        job = claim_job(session, settings)
        session.commit()

        class TakeoverDuringInference:
            label = "review callback"

            def complete(self, request):
                with factory() as human_session:
                    conversation = human_session.get(Conversation, conversation_id)
                    operator = human_session.scalars(select(OperatorProfile)).first()
                    takeover(human_session, conversation, operator)
                    human_session.commit()
                return DemoLLMAdapter().complete(request)

        result = process_ai_job(session, settings, TakeoverDuringInference(), job)
        session.commit()
        session.expire_all()
        assert result == "discarded"
        assert session.get(Conversation, conversation_id).attention_mode == "human_active"
        assert not session.scalars(select(OutboundMessage)).all()


def test_takeover_discards_already_queued_ai_and_persists_outcome(review_store):
    settings, factory = review_store
    with factory() as session:
        conversation_id = receive(session, settings, "Quiero aprender Python")
        job = claim_job(session, settings)
        session.commit()
        assert process_ai_job(session, settings, DemoLLMAdapter(), job) == "completed"
        session.commit()
        conversation = session.get(Conversation, conversation_id)
        operator = session.scalars(select(OperatorProfile)).first()
        takeover(session, conversation, operator)
        session.commit()
        telegram = DemoTelegramAdapter()
        process_available_work(session, settings, DemoLLMAdapter(), telegram)
        session.expire_all()
        outbound = session.scalars(select(OutboundMessage)).one()
        assert outbound.status == "discarded"
        assert not telegram.sent
    with factory() as verification:
        assert verification.scalars(select(OutboundMessage)).one().status == "discarded"


def test_ambiguous_send_is_durable_and_not_retried(review_store):
    settings, factory = review_store

    class AmbiguousTelegram:
        label = "review timeout"
        calls = 0

        def send_message(self, chat_id, text):
            self.calls += 1
            return TelegramSendResult("unknown", None, "timeout")

    telegram = AmbiguousTelegram()
    with factory() as session:
        receive(session, settings, "Quiero aprender Python")
        process_available_work(session, settings, DemoLLMAdapter(), telegram)
    with factory() as session:
        assert session.scalars(select(OutboundMessage)).one().status == "unknown"
        process_available_work(session, settings, DemoLLMAdapter(), telegram)
    assert telegram.calls == 1


def test_expired_job_lease_can_be_claimed_by_another_worker(review_store):
    settings, factory = review_store
    with factory() as session:
        receive(session, settings, "Quiero aprender Python")
        job = claim_job(session, settings)
        session.commit()
        job.leased_until = utcnow() - timedelta(seconds=5)
        session.commit()
        recovered = claim_job(session, settings.model_copy(update={"worker_id": "replacement"}))
        session.commit()
        assert recovered.id == job.id
        assert recovered.leased_by == "replacement"
        assert recovered.attempts == 2


def test_sqlite_dates_are_serialized_as_utc(review_store):
    from app.services.serialize import message_out, conversation_summary
    settings, factory = review_store
    with factory() as session:
        conversation_id = receive(session, settings, "Quiero aprender Python")
        session.expire_all()
        message = session.scalars(select(Message)).one()
        conversation = session.get(Conversation, conversation_id)
        assert message_out(message).model_dump(mode="json")["created_at"].endswith("Z")
        assert conversation_summary(conversation).model_dump(mode="json")["last_activity_at"].endswith("Z")


def test_explicit_frustration_transfers_with_spanish_summary(review_store):
    settings, factory = review_store
    with factory() as session:
        conversation_id = receive(session, settings, "Estoy frustrado, quiero hablar con un asesor.")
        process_available_work(session, settings, DemoLLMAdapter(), DemoTelegramAdapter())
        session.expire_all()
        conversation = session.get(Conversation, conversation_id)
        assert conversation.attention_mode == "human_pending"
        assert conversation.commercial_state == "frustrated"
        assert "Frustrado" in conversation.operator_summary
        assert "frustrated" not in conversation.operator_summary
