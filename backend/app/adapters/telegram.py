"""Telegram adapters. DemoTelegramAdapter is labeled and stores outbound rows without the Bot API."""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class TelegramSendResult:
    status: str
    telegram_message_id: str | None
    error: str | None = None
    retry_after_seconds: float | None = None


class TelegramAdapter(Protocol):
    label: str

    def send_message(self, chat_id: str, text: str) -> TelegramSendResult:
        ...


class DemoTelegramAdapter:
    """SIMULATED Telegram sender. Does not call api.telegram.org."""

    label = "SIMULATED: DemoTelegramAdapter"

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> TelegramSendResult:
        message_id = "demo-" + uuid.uuid4().hex
        self.sent.append({"chat_id": chat_id, "text": text, "telegram_message_id": message_id})
        logger.info("DemoTelegramAdapter stored outbound chat=%s id=%s", chat_id, message_id)
        return TelegramSendResult(status="sent", telegram_message_id=message_id)


class LiveTelegramAdapter:
    label = "LIVE: Telegram Bot API"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    def send_message(self, chat_id: str, text: str) -> TelegramSendResult:
        payload = {"chat_id": chat_id, "text": text}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(f"{self.base}/sendMessage", json=payload)
        except httpx.TimeoutException:
            return TelegramSendResult(status="unknown", telegram_message_id=None, error="timeout")
        except httpx.HTTPError as exc:
            return TelegramSendResult(status="failed", telegram_message_id=None, error=type(exc).__name__)
        if response.status_code == 429:
            try:
                delay = float(response.json().get("parameters", {}).get("retry_after", 1))
            except (ValueError, TypeError):
                delay = 1.0
            return TelegramSendResult("failed", None, "rate_limited", max(1.0, delay))
        if response.status_code >= 500:
            return TelegramSendResult(status="failed", telegram_message_id=None, error=f"http {response.status_code}")
        if response.status_code >= 400:
            return TelegramSendResult(status="failed", telegram_message_id=None, error=f"http {response.status_code}")
        data = response.json()
        if not data.get("ok"):
            return TelegramSendResult(status="failed", telegram_message_id=None, error="telegram_rejected_request")
        message_id = str(data["result"]["message_id"])
        return TelegramSendResult(status="sent", telegram_message_id=message_id)


def build_telegram_adapter(settings: Settings) -> TelegramAdapter:
    if settings.telegram_adapter == "demo":
        logger.warning("Using %s — outbound messages are not delivered to Telegram", DemoTelegramAdapter.label)
        return DemoTelegramAdapter()
    if settings.telegram_adapter == "live":
        return LiveTelegramAdapter(settings)
    raise RuntimeError(f"Unsupported TELEGRAM_ADAPTER={settings.telegram_adapter}")
