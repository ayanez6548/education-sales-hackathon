from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.base import BaseHTTPMiddleware

from app.adapters.llm import build_llm_adapter
from app.adapters.telegram import build_telegram_adapter
from app.bootstrap import prepare_database
from app.config import Settings, get_settings
from app.database import get_engine, get_session, get_session_factory
from app.domain.states import AttentionMode
from app.logging_utils import configure_logging
from app.models import (
    AppEvent,
    Contact,
    Conversation,
    Course,
    IdempotencyKey,
    LeadProfile,
    Message,
    OperatorProfile,
)
from app.schemas import (
    CourseOut,
    DemoInboundRequest,
    LoginRequest,
    MetricsOut,
    OperatorOut,
    SendMessageRequest,
    TokenResponse,
)
from app.security import (
    create_access_token,
    decode_supabase_token,
    decode_token,
    has_operator_role,
    verify_password,
)
from app.services.control import close_conversation, load_conversation, resume_ai, takeover
from app.services.inbox import ingest_telegram_text
from app.services.metrics import collect_metrics
from app.services.outbound import create_outbound, send_pending_outbound
from app.services.presence import mark_connected, mark_disconnected
from app.services.serialize import conversation_detail, conversation_summary, course_out, message_out
from app.worker import drain_once, process_available_work

logger = logging.getLogger(__name__)
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)
_worker_thread: threading.Thread | None = None


class RequestLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if request.url.path.startswith("/webhooks/") or request.url.path.startswith("/api/demo/"):
            key = request.client.host if request.client else "unknown"
            now = time.time()
            bucket = _rate_buckets[key]
            while bucket and now - bucket[0] > 10:
                bucket.popleft()
            if len(bucket) >= 40:
                return JSONResponse({"detail": "Demasiadas solicitudes"}, status_code=429)
            bucket.append(now)
        if request.method in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > settings.max_input_chars * 8 + 2048:
                return JSONResponse({"detail": "Cuerpo demasiado grande"}, status_code=413)
        return await call_next(request)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    settings.validate_runtime()
    app = FastAPI(title="Education Sales Hackathon", version="0.1.0")
    app.add_middleware(RequestLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Telegram-Bot-Api-Secret-Token"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        prepare_database(settings)
        logger.info(
            "API started env=%s demo_mode=%s telegram=%s llm=%s auth=%s db=%s",
            settings.app_env,
            settings.demo_mode,
            settings.telegram_adapter,
            settings.llm_adapter,
            settings.auth_adapter,
            "sqlite" if settings.is_sqlite else "postgres",
        )
        if settings.embed_worker:
            global _worker_thread
            _worker_thread = threading.Thread(target=_embedded_worker, args=(settings,), daemon=True)
            _worker_thread.start()

    app.include_router  # keep attribute for tests
    _register_routes(app)
    if settings.static_directory:
        app.mount("/", StaticFiles(directory=settings.static_directory, html=True), name="dashboard")
    return app


def _embedded_worker(settings: Settings) -> None:
    llm = build_llm_adapter(settings)
    telegram = build_telegram_adapter(settings)
    from app.database import get_session_factory

    while True:
        session = get_session_factory()()
        try:
            worked = process_available_work(session, settings, llm, telegram)
        except Exception:
            session.rollback()
            logger.exception("embedded worker error")
            worked = False
        finally:
            session.close()
        if not worked:
            time.sleep(settings.job_poll_seconds)


def _register_routes(app: FastAPI) -> None:
    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(settings: Settings = Depends(get_settings)) -> dict[str, str]:
        try:
            with get_engine().connect() as conn:
                conn.exec_driver_sql("SELECT 1")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail="base de datos no lista") from exc
        return {"status": "ok", "adapter_mode": "demo" if settings.demo_mode else "live"}

    @app.post("/api/auth/login", response_model=TokenResponse)
    def login(body: LoginRequest, session: Session = Depends(get_session), settings: Settings = Depends(get_settings)):
        if settings.auth_adapter != "demo":
            raise HTTPException(status_code=400, detail="El inicio local solo está disponible con AUTH_ADAPTER=demo")
        operator = session.execute(select(OperatorProfile).where(OperatorProfile.email == body.email)).scalar_one_or_none()
        if operator is None or not operator.enabled or not verify_password(body.password, operator.password_hash):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        token = create_access_token(settings, operator.auth_user_id, {"email": operator.email, "role": operator.role})
        return TokenResponse(
            access_token=token,
            operator=OperatorOut(
                id=operator.id,
                email=operator.email,
                display_name=operator.display_name,
                role=operator.role,
            ),
        )

    @app.get("/api/me")
    def me(operator: OperatorProfile = Depends(get_current_operator)) -> dict[str, Any]:
        return {
            "id": str(operator.id),
            "email": operator.email,
            "display_name": operator.display_name,
            "role": operator.role,
        }

    @app.post("/webhooks/telegram")
    def telegram_webhook(
        request_body: dict[str, Any],
        request: Request,
        session: Session = Depends(get_session),
        settings: Settings = Depends(get_settings),
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, str]:
        if settings.telegram_adapter == "live":
            if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
                raise HTTPException(status_code=401, detail="Secreto de webhook inválido")
        try:
            result = _ingest_update(session, settings, request_body)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("telegram webhook persist failed")
            raise HTTPException(status_code=503, detail="No se pudo persistir la actualización") from None
        logger.info("telegram update stored duplicate=%s", result.duplicate)
        return {"status": "ok"}

    @app.post("/api/demo/telegram/inbound")
    def demo_inbound(
        body: DemoInboundRequest,
        session: Session = Depends(get_session),
        settings: Settings = Depends(get_settings),
        operator: OperatorProfile = Depends(get_current_operator),
    ) -> dict[str, Any]:
        if settings.telegram_adapter != "demo":
            raise HTTPException(status_code=400, detail="Esta ruta solo existe con TELEGRAM_ADAPTER=demo")
        update_id = body.update_id or str(uuid.uuid4().int)[:16]
        message_id = str(int(time.time() * 1000) % 10_000_000)
        result = ingest_telegram_text(
            session,
            settings,
            update_id=update_id,
            telegram_user_id=body.telegram_user_id,
            telegram_chat_id=body.telegram_chat_id,
            display_name=body.display_name,
            text=body.text,
            telegram_message_id=message_id,
        )
        session.commit()
        if settings.embed_worker:
            drain_once(settings)
        _ = operator
        return {
            "conversation_id": str(result.conversation_id),
            "duplicate": result.duplicate,
            "adapter": "SIMULATED: DemoTelegramAdapter",
        }

    @app.get("/api/conversations")
    def list_conversations(
        q: str | None = None,
        attention_mode: str | None = None,
        commercial_state: str | None = None,
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.contact), selectinload(Conversation.assigned_operator))
            .order_by(Conversation.last_activity_at.desc())
        )
        if attention_mode:
            stmt = stmt.where(Conversation.attention_mode == attention_mode)
        if commercial_state:
            stmt = stmt.where(Conversation.commercial_state == commercial_state)
        rows = list(session.execute(stmt).scalars())
        if q:
            needle = q.lower()
            rows = [
                item
                for item in rows
                if needle in (item.contact.display_name or "").lower()
                or needle in (item.contact.preferred_name or "").lower()
                or needle in item.contact.telegram_chat_id
            ]
        _ = operator
        return [conversation_summary(item).model_dump(mode="json") for item in rows]

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(
        conversation_id: uuid.UUID,
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
    ) -> dict[str, Any]:
        item = session.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.contact).selectinload(Contact.lead_profile).selectinload(LeadProfile.interested_course),
                selectinload(Conversation.assigned_operator),
            )
            .where(Conversation.id == conversation_id)
        ).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        item.unread_count = 0
        session.commit()
        _ = operator
        return conversation_detail(item).model_dump(mode="json")

    @app.get("/api/conversations/{conversation_id}/messages")
    def list_messages(
        conversation_id: uuid.UUID,
        after_seq: int = 0,
        limit: int = Query(default=50, le=200),
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
    ) -> dict[str, Any]:
        load_conversation(session, conversation_id)
        rows = session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.seq > after_seq)
            .order_by(Message.seq.asc())
            .limit(limit)
        ).scalars().all()
        _ = operator
        return {"items": [message_out(item).model_dump(mode="json") for item in rows]}

    @app.post("/api/conversations/{conversation_id}/takeover")
    def takeover_route(
        conversation_id: uuid.UUID,
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        cached = _idempotent_get(session, operator.id, idempotency_key)
        if cached:
            return cached
        conversation = load_conversation(session, conversation_id)
        takeover(session, conversation, operator)
        session.commit()
        payload = {"attention_mode": conversation.attention_mode, "control_version": conversation.control_version}
        _idempotent_store(session, operator.id, idempotency_key, payload)
        session.commit()
        return payload

    @app.post("/api/conversations/{conversation_id}/resume")
    def resume_route(
        conversation_id: uuid.UUID,
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        cached = _idempotent_get(session, operator.id, idempotency_key)
        if cached:
            return cached
        conversation = load_conversation(session, conversation_id)
        resume_ai(session, conversation, operator)
        payload = {"attention_mode": conversation.attention_mode, "control_version": conversation.control_version}
        _idempotent_store(session, operator.id, idempotency_key, payload)
        session.commit()
        return payload

    @app.post("/api/conversations/{conversation_id}/close")
    def close_route(
        conversation_id: uuid.UUID,
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        cached = _idempotent_get(session, operator.id, idempotency_key)
        if cached:
            return cached
        conversation = load_conversation(session, conversation_id)
        close_conversation(session, conversation, operator)
        payload = {"attention_mode": conversation.attention_mode, "control_version": conversation.control_version}
        _idempotent_store(session, operator.id, idempotency_key, payload)
        session.commit()
        return payload

    @app.post("/api/conversations/{conversation_id}/messages")
    def send_operator_message(
        conversation_id: uuid.UUID,
        body: SendMessageRequest,
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
        settings: Settings = Depends(get_settings),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        cached = _idempotent_get(session, operator.id, idempotency_key)
        if cached:
            return cached
        conversation = session.execute(
            select(Conversation)
            .options(selectinload(Conversation.contact))
            .where(Conversation.id == conversation_id)
        ).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
        takeover(session, conversation, operator)
        text = body.body.strip()[: settings.max_output_chars]
        key = idempotency_key or f"human:{conversation.id}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
        message = create_outbound(
            session,
            conversation,
            text,
            "human",
            operator_id=operator.id,
            dedupe_key=f"human:{operator.id}:{key}",
            control_version=conversation.control_version,
            expected_inbound_seq=conversation.last_inbound_seq,
            expected_attention_mode=AttentionMode.HUMAN_ACTIVE,
            send_gate="human",
        )
        telegram = build_telegram_adapter(settings)
        send_pending_outbound(session, telegram, settings)
        session.commit()
        payload = message_out(message).model_dump(mode="json")
        _idempotent_store(session, operator.id, idempotency_key, payload)
        session.commit()
        return payload

    @app.get("/api/courses", response_model=list[CourseOut])
    def courses(
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
    ) -> list[CourseOut]:
        _ = operator
        rows = session.execute(select(Course).where(Course.active.is_(True)).order_by(Course.name)).scalars()
        return [course_out(item) for item in rows]

    @app.get("/api/metrics", response_model=MetricsOut)
    def metrics(
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
    ) -> MetricsOut:
        _ = operator
        return collect_metrics(session)

    @app.get("/api/events")
    def events(
        after_id: int = 0,
        request: Request = None,
        session: Session = Depends(get_session),
        operator: OperatorProfile = Depends(get_current_operator),
        settings: Settings = Depends(get_settings),
    ) -> StreamingResponse:
        operator_id = operator.id
        authorization = request.headers.get("authorization")
        session.close()
        mark_connected(operator_id)

        def read_batch(last):
            with get_session_factory()() as db:
                # Revalidate access on an open connection, including token expiry.
                try:
                    get_current_operator(session=db, settings=settings, authorization=authorization)
                except HTTPException:
                    return None
                rows = db.scalars(
                    select(AppEvent).where(AppEvent.id > last).order_by(AppEvent.id.asc()).limit(100)
                ).all()
                return [{
                    "id": row.id,
                    "conversation_id": str(row.conversation_id) if row.conversation_id else None,
                    "event_type": row.event_type,
                    "payload": row.payload,
                } for row in rows]

        async def gen():
            last = after_id
            try:
                while not await request.is_disconnected():
                    rows = await asyncio.to_thread(read_batch, last)
                    if rows is None:
                        return
                    for row in rows:
                        last = row["id"]
                        yield f"id: {last}\nevent: {row['event_type']}\ndata: {json.dumps(row, default=str)}\n\n"
                    yield ": keep-alive\n\n"
                    await asyncio.sleep(0.7)
            finally:
                mark_disconnected(operator_id)

        return StreamingResponse(gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
        })



def get_current_operator(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
) -> OperatorProfile:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Autenticación requerida")
    token = authorization.split(" ", 1)[1]
    if settings.auth_adapter == "supabase":
        claims = _safe_decode(lambda: decode_supabase_token(settings, token))
        subject = str(claims.get("sub") or "")
        operator = session.execute(
            select(OperatorProfile).where(OperatorProfile.auth_user_id == subject)
        ).scalar_one_or_none()
    else:
        claims = _safe_decode(lambda: decode_token(settings, token))
        subject = str(claims.get("sub") or "")
        operator = session.execute(
            select(OperatorProfile).where(OperatorProfile.auth_user_id == subject)
        ).scalar_one_or_none()
        if operator is None:
            email = claims.get("email")
            if email:
                operator = session.execute(select(OperatorProfile).where(OperatorProfile.email == email)).scalar_one_or_none()
    if operator is None or not operator.enabled or not has_operator_role(operator.role):
        raise HTTPException(status_code=403, detail="No tienes un perfil de operador habilitado")
    return operator


def _safe_decode(fn) -> dict[str, Any]:
    try:
        return fn()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Token inválido") from exc


def _ingest_update(session: Session, settings: Settings, payload: dict[str, Any]):
    update_id = str(payload.get("update_id") or "")
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    text = message.get("text") or ""
    if not update_id or not text or not chat.get("id"):
        from app.services.inbox import InboundResult

        return InboundResult(uuid.UUID(int=0), None, True, None)
    display = " ".join(part for part in [user.get("first_name"), user.get("last_name")] if part) or user.get("username")
    return ingest_telegram_text(
        session,
        settings,
        update_id=update_id,
        telegram_user_id=str(user.get("id") or chat.get("id")),
        telegram_chat_id=str(chat.get("id")),
        display_name=display,
        text=text,
        telegram_message_id=str(message.get("message_id") or update_id),
    )


def _idempotent_get(session: Session, operator_id: uuid.UUID, key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    row = session.execute(
        select(IdempotencyKey).where(IdempotencyKey.operator_id == operator_id, IdempotencyKey.key == key)
    ).scalar_one_or_none()
    return row.response_json if row else None


def _idempotent_store(session: Session, operator_id: uuid.UUID, key: str | None, payload: dict[str, Any]) -> None:
    if not key:
        return
    session.add(IdempotencyKey(operator_id=operator_id, key=key, response_json=payload))


app = create_app()
