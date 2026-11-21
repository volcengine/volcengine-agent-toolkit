"""Shared constructors for identical local validation errors."""

from __future__ import annotations

from typing import Any

from ..common.errors import BillingQueryError, ErrorCode, ExitCode


def invalid_argument(message: str, **details: Any) -> BillingQueryError:
    return BillingQueryError(
        ErrorCode.INVALID_ARGUMENT,
        message,
        ExitCode.INVALID_ARGUMENT,
        details,
    )
