"""In-memory operator presence for demo handover copy. Not a substitute for production presence."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

_lock = threading.Lock()
_connected: dict[uuid.UUID, datetime] = {}


def mark_connected(operator_id: uuid.UUID) -> None:
    with _lock:
        _connected[operator_id] = datetime.now(timezone.utc)


def mark_disconnected(operator_id: uuid.UUID) -> None:
    with _lock:
        _connected.pop(operator_id, None)


def connected_count() -> int:
    with _lock:
        return len(_connected)
