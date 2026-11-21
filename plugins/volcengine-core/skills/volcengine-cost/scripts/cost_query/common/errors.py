"""Billing 预封装脚本的稳定错误和退出码。"""

from __future__ import annotations

from enum import Enum, IntEnum
from typing import Any, Mapping

from ..utils.redaction import redact_diagnostic, redact_text


class ExitCode(IntEnum):
    SUCCESS = 0
    INVALID_ARGUMENT = 2
    DEPENDENCY_ERROR = 4
    QUERY_FAILED = 5
    PARTIAL_RESULT = 6
    OUTPUT_FAILED = 7


class ErrorCode(str, Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNSUPPORTED_FIELD = "UNSUPPORTED_FIELD"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    RESPONSE_FIELDS_IN_REQUEST_BODY = "RESPONSE_FIELDS_IN_REQUEST_BODY"
    RESPONSE_FIELD_NOT_PRESERVED = "RESPONSE_FIELD_NOT_PRESERVED"
    VE_CLI_NOT_FOUND = "VE_CLI_NOT_FOUND"
    VE_CLI_UPGRADE_REQUIRED = "VE_CLI_UPGRADE_REQUIRED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SOURCE_NOT_ENABLED = "SOURCE_NOT_ENABLED"
    ALL_QUERIES_FAILED = "ALL_QUERIES_FAILED"
    ACTION_FAILED = "ACTION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    PAGINATION_INCOMPLETE = "PAGINATION_INCOMPLETE"
    OUTPUT_EXISTS = "OUTPUT_EXISTS"
    OUTPUT_FAILED = "OUTPUT_FAILED"


class BillingQueryError(RuntimeError):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        exit_code: ExitCode,
        details: Mapping[str, Any] | None = None,
        cause: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(redact_text(message))
        self.code = code
        self.exit_code = exit_code
        self.details = dict(details or {})
        self.cause = dict(cause or {})

    def error_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code.value,
            "message": str(self),
        }
        if self.details:
            result["details"] = self.details
        if self.cause:
            result["cause"] = self.cause
        return redact_diagnostic(result)
