from __future__ import annotations

from sqlalchemy import inspect, text

from app.config import DATA_DIR, Settings
from app.database import Base, configure_engine, get_engine, get_session_factory, is_sqlite_url
from app.models import AppEvent  # noqa: F401
from app.seed import seed_all


_SQLITE_OUTBOUND_COLUMNS = {
    "send_gate": "VARCHAR(16) DEFAULT 'ai'",
    "expected_control_version": "INTEGER DEFAULT 1",
    "expected_inbound_seq": "INTEGER",
    "expected_attention_mode": "VARCHAR(32) DEFAULT 'ai_active'",
    "leased_until": "DATETIME",
    "leased_by": "VARCHAR(80)",
    "available_at": "DATETIME",
}


def _ensure_sqlite_outbound_columns(engine) -> None:
    inspector = inspect(engine)
    if "outbound_messages" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("outbound_messages")}
    with engine.begin() as conn:
        for name, ddl in _SQLITE_OUTBOUND_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE outbound_messages ADD COLUMN {name} {ddl}"))


def prepare_database(settings: Settings) -> None:
    configure_engine(settings.database_url)
    if is_sqlite_url(settings.database_url):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(get_engine())
        _ensure_sqlite_outbound_columns(get_engine())
    session = get_session_factory()()
    try:
        seed_all(session, settings)
        session.commit()
    finally:
        session.close()
