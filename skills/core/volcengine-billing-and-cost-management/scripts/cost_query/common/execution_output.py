"""Stable Agent-facing execution envelope for task commands."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Literal, Mapping

from .errors import BillingQueryError
from .json_output import dumps as json_dumps


OUTPUT_PROTOCOL_VERSION = "1.0"
AUTO_STDOUT_BYTE_LIMIT = 64 * 1024
ExecutionStatus = Literal["success", "partial", "error"]
ExecutionResult = dict[str, Any] | list[Any] | None
VALID_STATUSES = frozenset({"success", "partial", "error"})


def build_envelope(
    *,
    status: ExecutionStatus,
    message: str,
    result: ExecutionResult,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the only public task envelope and validate its invariants."""

    if status not in VALID_STATUSES:
        raise ValueError(f"unsupported execution status: {status}")
    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("execution message must be non-empty")
    if status == "error" and result is not None:
        raise ValueError("error envelope result must be null")
    if status != "error" and result is None:
        raise ValueError("success/partial envelope result must not be null")
    if result is not None and not isinstance(result, (dict, list)):
        raise ValueError("execution result must be an object, array, or null")

    machine_meta = dict(meta or {})
    existing_version = machine_meta.get("output_protocol_version")
    if existing_version not in (None, OUTPUT_PROTOCOL_VERSION):
        raise ValueError(
            f"output_protocol_version must be {OUTPUT_PROTOCOL_VERSION!r}, got {existing_version!r}"
        )
    machine_meta["output_protocol_version"] = OUTPUT_PROTOCOL_VERSION
    return {
        "status": status,
        "message": normalized_message,
        "result": result,
        "_meta": machine_meta,
    }


def error_envelope(error: BillingQueryError) -> dict[str, Any]:
    """Project a handled task error without changing its exit code."""

    return build_envelope(
        status="error",
        message=str(error),
        result=None,
        meta={"error": error.error_dict()},
    )


def compact_size(value: Mapping[str, Any]) -> int:
    """Return strict compact UTF-8 JSON size for stdout budgeting."""

    return len(json_dumps(value, sort_keys=True).encode("utf-8"))


def automatic_result_path(prefix: str, suffix: str) -> Path:
    """Create a task result directory whose files survive subprocess exit."""

    directory = Path(tempfile.mkdtemp(prefix=f"volcengine-billing-and-cost-management-{prefix}-"))
    return (directory / f"result{suffix}").resolve()


def write_json_result(path: Path, result: Mapping[str, Any] | list[Any], *, overwrite: bool) -> Path:
    """Atomically write a complete business result and return its absolute path."""

    resolved = path.expanduser().resolve()
    if resolved.exists() and not overwrite:
        raise FileExistsError(str(resolved))
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix=f".{resolved.name}.", dir=str(resolved.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(json_dumps(result, compact=False))
            file.write("\n")
        os.replace(staged, resolved)
    except Exception:
        try:
            os.unlink(staged)
        except OSError:
            pass
        raise
    return resolved
