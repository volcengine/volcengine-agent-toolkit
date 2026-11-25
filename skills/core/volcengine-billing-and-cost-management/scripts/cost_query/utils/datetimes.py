"""Shared tolerant datetime parsing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_iso_datetime_utc(value: Any) -> datetime | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
