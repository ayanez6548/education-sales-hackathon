"""Test polling acknowledgment boundaries without contacting Telegram."""
from pathlib import Path

import pytest

from app.config import Settings
from app.telegram_polling import forward_updates, load_offset, save_offset


def update(update_id: int, chat_type: str = "private") -> dict:
    return {"update_id": update_id, "message": {"text": "Me interesa Python", "chat": {"id": 10, "type": chat_type}}}


class Response:
    def __init__(self, accepted=True):
        self.accepted = accepted

    def raise_for_status(self):
        if not self.accepted:
            raise RuntimeError("Backend unavailable")

    def json(self):
        return {"status": "ok"}


class Client:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(len(self.calls) != self.fail_at)


def settings():
    return Settings(_env_file=None, telegram_webhook_secret="test-webhook-secret")


def test_polling_advances_only_after_persistence(tmp_path: Path):
    client = Client()
    cursor = tmp_path / "cursor.json"
    assert forward_updates(client, settings(), [update(10), update(11)], cursor) == 12
    assert load_offset(cursor) == 12
    assert len(client.calls) == 2
    assert client.calls[0][1]["headers"]["X-Telegram-Bot-Api-Secret-Token"] == "test-webhook-secret"


def test_failed_update_does_not_advance_cursor(tmp_path: Path):
    client = Client(fail_at=2)
    cursor = tmp_path / "cursor.json"
    with pytest.raises(RuntimeError):
        forward_updates(client, settings(), [update(10), update(11)], cursor)
    assert load_offset(cursor) == 11
    retry = Client()
    forward_updates(retry, settings(), [update(10), update(11)], cursor)
    assert len(retry.calls) == 1
    assert load_offset(cursor) == 12


def test_already_confirmed_updates_are_not_forwarded(tmp_path: Path):
    cursor = tmp_path / "cursor.json"
    save_offset(cursor, 12)
    client = Client()
    forward_updates(client, settings(), [update(11)], cursor)
    assert not client.calls
    assert load_offset(cursor) == 12


def test_local_trial_does_not_ingest_group_messages(tmp_path: Path):
    client = Client()
    cursor = tmp_path / "cursor.json"
    forward_updates(client, settings(), [update(11, "group")], cursor)
    assert not client.calls
    assert load_offset(cursor) == 12
