"""JSON persistence and credential redaction shared by RCA business commands."""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict

REDACTED = "[REDACTED]"


class JsonWriteError(RuntimeError):
    """Raised when JSON files cannot be written."""


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(str(tmp_path), str(path))
    except Exception as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise JsonWriteError(f"failed to write JSON file {path}: {exc}") from exc


class OutputSanitizer:
    """Recursively removes credentials from business outputs.

    Business RCA identifiers such as AccountID, product, region, instance_no,
    charge_item_code, periods, and amounts are intentionally preserved.
    """

    SENSITIVE_KEYS = {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "jwt",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "ak",
        "sk",
        "secret",
        "secret_key",
        "tcc_secret",
        "tccsecret",
    }
    SENSITIVE_KEY_PARTS = (
        "authorization",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "bearer",
        "jwt",
        "cookie",
        "secret",
        "tcc",
    )
    VALUE_PATTERNS = (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
        re.compile(r"(?i)\b(Authorization\s*[:=]\s*)([^\s,;}{]+)"),
        re.compile(r"(?i)\b((?:api[_-]?key|access[_-]?token|refresh[_-]?token|jwt|tcc[_-]?secret)\s*[:=]\s*)([^\s,;}{]+)"),
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
        re.compile(r"(?i)\b(cookie\s*[:=]\s*)([^\n]+)"),
    )

    def sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: Dict[str, Any] = {}
            for key, item in value.items():
                if self._is_sensitive_key(str(key)):
                    sanitized[key] = REDACTED
                else:
                    sanitized[key] = self.sanitize(item)
            return sanitized
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [self.sanitize(item) for item in value]
        if isinstance(value, str):
            return self._sanitize_string(value)
        return value

    def _is_sensitive_key(self, key: str) -> bool:
        key_lower = key.lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", key_lower).strip("_")
        if normalized in self.SENSITIVE_KEYS:
            return True
        if normalized.endswith("_ak") or normalized.endswith("_sk"):
            return True
        return any(part in normalized for part in self.SENSITIVE_KEY_PARTS)

    def _sanitize_string(self, value: str) -> str:
        sanitized = value
        sanitized = self.VALUE_PATTERNS[0].sub("Bearer " + REDACTED, sanitized)
        for pattern in self.VALUE_PATTERNS[1:3]:
            sanitized = pattern.sub(lambda match: match.group(1) + REDACTED, sanitized)
        sanitized = self.VALUE_PATTERNS[3].sub(REDACTED, sanitized)
        sanitized = self.VALUE_PATTERNS[4].sub(lambda match: match.group(1) + REDACTED, sanitized)
        return sanitized


def build_error(error_code: str, error_message: str, retryable: bool = False) -> Dict[str, Any]:
    return {
        "error_code": error_code,
        "error_message": OutputSanitizer().sanitize(error_message),
        "retryable": retryable,
    }
