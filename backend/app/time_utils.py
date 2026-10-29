from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Settings


def to_display_tz(value: datetime, settings: Settings) -> datetime:
    tz = ZoneInfo(settings.timezone_name)
    if value.tzinfo is None:
        return value.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return value.astimezone(tz)
