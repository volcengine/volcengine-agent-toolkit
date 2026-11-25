"""Redact credentials at public diagnostic boundaries."""

from __future__ import annotations

import re
from typing import Any, Mapping


_SENSITIVE_NAMES = (
    "access[_-]?key(?:[_-]?id|[_-]?secret)?",
    "secret[_-]?(?:access[_-]?)?key",
    "(?:x[_-](?:amz[_-])?)?security[_-]?token",
    "(?:session|refresh|access)[_-]?token",
    "authorization",
    "(?:set[_-]?)?cookie",
    "api[_-]?key",
    "ak|sk|jwt|token",
)
_KEY = "(?:(?:volcengine|volcstack|ve|volc)[_-])?(?:" + "|".join(_SENSITIVE_NAMES) + ")"
_SENSITIVE_KEY = re.compile(_KEY, re.IGNORECASE)
_JSON_VALUE = re.compile(
    rf'''(["']{_KEY}["']\s*:\s*)(["'])((?:\\.|(?!\2).)*)(\2)''',
    re.IGNORECASE,
)
_PLAIN_VALUE = re.compile(
    rf"(\b{_KEY}\b\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+",
    re.IGNORECASE,
)
_COOKIE_HEADER = re.compile(r"(\b(?:set[_-]?)?cookie\s*[:=]\s*)[^\r\n]+", re.IGNORECASE)


def redact_text(value: str) -> str:
    redacted = _JSON_VALUE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>{match.group(4)}",
        value,
    )
    redacted = _COOKIE_HEADER.sub(lambda match: f"{match.group(1)}<redacted>", redacted)
    return _PLAIN_VALUE.sub(lambda match: f"{match.group(1)}<redacted>", redacted)


def redact_diagnostic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: "<redacted>" if isinstance(key, str) and _SENSITIVE_KEY.fullmatch(key)
            else redact_diagnostic(child)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_diagnostic(child) for child in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
