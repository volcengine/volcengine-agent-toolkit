"""公开只读 ve billing Client、fixture Client 和响应解包。"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .schema import ACTION_SCHEMAS
from .call_options import ACTION_CLI_OPTIONS
from .cost_change import COST_CHANGE_ACTIONS
from ..common.errors import BillingQueryError, ErrorCode, ExitCode
from .validation import validate_request_body
from ..utils.redaction import redact_text


def _path_value(value: Any, path: str) -> Any:
    current = value
    if not path:
        return current
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


_REQUEST_ID = re.compile(
    r"(?i)(?:request[_-]?id|log[_-]?id)\s*[:=]\s*[\[\(]?([0-9A-Za-z_-]{8,})"
)
_RAW_ERROR_LIMIT = 4000


def _redact_error_text(value: str) -> str:
    return redact_text(value)


def _safe_error_text(value: str, limit: int = 1000) -> str:
    compact = " ".join(_redact_error_text(value).strip().split())
    return compact[:limit]


def _safe_raw_error(value: str, name: str) -> dict[str, Any]:
    redacted = _redact_error_text(value).strip()
    if not redacted:
        return {}
    truncated = len(redacted) > _RAW_ERROR_LIMIT
    return {
        name: redacted[:_RAW_ERROR_LIMIT],
        f"{name}_truncated": truncated,
        **({f"{name}_original_length": len(redacted)} if truncated else {}),
    }


def _response_request_id(response: Mapping[str, Any] | None) -> str | None:
    if response is None:
        return None
    for path in (
        "ResponseMetadata.RequestId",
        "ResponseMetadata.RequestID",
        "RequestId",
        "RequestID",
        "LogID",
    ):
        value = _path_value(response, path)
        if value:
            return str(value)
    return None


def _text_request_id(*values: str) -> str | None:
    for value in values:
        match = _REQUEST_ID.search(value)
        if match:
            return match.group(1)
    return None


def _ve_cause(
    *,
    returncode: int | None = None,
    stdout: str = "",
    stderr: str = "",
    response: Mapping[str, Any] | None = None,
    remote_code: str | None = None,
    remote_message: str | None = None,
) -> dict[str, Any]:
    request_id = _response_request_id(response) or _text_request_id(stderr, stdout)
    return {
        "source": "ve-billing-cli",
        **({"returncode": returncode} if returncode is not None else {}),
        **({"remote_code": remote_code} if remote_code else {}),
        **({"remote_message": _safe_error_text(remote_message, limit=2000)} if remote_message else {}),
        **({"request_id": request_id} if request_id else {}),
        **_safe_raw_error(stdout, "raw_stdout"),
        **_safe_raw_error(stderr, "raw_stderr"),
    }


def _parse_stdout_json_object(stdout: str, *, precise_numbers: bool = True) -> Mapping[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text, parse_float=Decimal if precise_numbers else float)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, Mapping):
        return parsed

    start = text.find("{")
    if start < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder(parse_float=Decimal if precise_numbers else float).raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, Mapping):
        return parsed
    return None


def classify_remote_error(code: str, message: str) -> ErrorCode:
    text = f"{code} {message}".lower()
    if any(marker in text for marker in ("ratelimit", "rate limit", "throttl", "flowlimit", "too many requests", "429")):
        return ErrorCode.RATE_LIMITED
    if any(marker in text for marker in (
        "invalidaccesskey",
        "signature",
        "credential",
        "authentication",
        "unauthorized",
        "refresh token",
        "refresh_token",
        "session token",
        "session_token",
        "ve login",
    )):
        return ErrorCode.AUTHENTICATION_FAILED
    if any(marker in text for marker in ("accessdenied", "permission", "forbidden", "无权限")):
        return ErrorCode.PERMISSION_DENIED
    if any(marker in text for marker in ("未开通", "not enabled", "not open")):
        return ErrorCode.SOURCE_NOT_ENABLED
    return ErrorCode.ACTION_FAILED


def raise_for_api_error(
    action: str,
    response: Mapping[str, Any],
    *,
    returncode: int | None = None,
    stdout: str = "",
    stderr: str = "",
) -> None:
    schema = ACTION_SCHEMAS[action]
    code = (
        _path_value(response, schema.error_code_path)
        if schema.error_code_path
        else None
    )
    message = (
        _path_value(response, schema.error_message_path)
        if schema.error_message_path
        else None
    )
    if code is None and message is None:
        code = _path_value(response, "ResponseMetadata.Error.Code")
        message = _path_value(response, "ResponseMetadata.Error.Message")
    if not code and not message and action in COST_CHANGE_ACTIONS:
        status_code = _path_value(response, "Result.BaseResp.StatusCode")
        if status_code not in (None, 0):
            code = status_code
            message = _path_value(response, "Result.BaseResp.StatusMessage") or "归因服务返回业务错误"
    if not code and not message:
        return
    normalized = classify_remote_error(str(code or ""), str(message or ""))
    raise BillingQueryError(
        normalized,
        f"{action} 调用失败：{_safe_error_text(str(message or code))}",
        ExitCode.QUERY_FAILED,
        {"action": action, "remote_code": str(code or "UNKNOWN")},
        cause=_ve_cause(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            response=response,
            remote_code=str(code or "UNKNOWN"),
            remote_message=str(message or code or ""),
        ),
    )


def action_result(action: str, response: Mapping[str, Any]) -> Mapping[str, Any]:
    raise_for_api_error(action, response)
    result = _path_value(response, ACTION_SCHEMAS[action].response_data_path)
    if not isinstance(result, Mapping):
        raise BillingQueryError(
            ErrorCode.RESPONSE_INVALID,
            f"{action} 响应缺少业务对象",
            ExitCode.QUERY_FAILED,
            {"data_path": ACTION_SCHEMAS[action].response_data_path or "$"},
        )
    return result


class BillingClient:
    backend_name = "billing-client"

    def query(self, action: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

    def get_caller_identity(self) -> Mapping[str, Any] | None:
        """Return identity for this client's credentials, when supported."""
        return None


Runner = Callable[..., subprocess.CompletedProcess[str]]


class VeBillingClient(BillingClient):
    backend_name = "ve-billing-cli"

    def __init__(
        self,
        *,
        region: str | None,
        profile: str | None,
        timeout_seconds: float | None,
        executable: str = "ve",
        runner: Runner = subprocess.run,
    ) -> None:
        if not shutil.which(executable):
            raise BillingQueryError(
                ErrorCode.VE_CLI_NOT_FOUND,
                "ve 未安装或不在 PATH 中",
                ExitCode.DEPENDENCY_ERROR,
            )
        self.region = region
        self.profile = profile
        self.timeout_seconds = timeout_seconds
        self.executable = executable
        self.runner = runner

    def query(self, action: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        normalized = validate_request_body(action, body)
        command = [
            self.executable,
            "billing",
            action,
            *ACTION_CLI_OPTIONS.get(action, ()),
            "--body",
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
        ]
        if self.region:
            command.extend(["---region", self.region])
        if self.profile:
            command.extend(["---profile", self.profile])
        timeout = self.timeout_seconds
        if timeout is None:
            timeout = ACTION_SCHEMAS[action].timeout_ms / 1000
        try:
            completed = self.runner(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BillingQueryError(
                ErrorCode.TIMEOUT,
                f"{action} 调用超时",
                ExitCode.QUERY_FAILED,
                {"timeout_seconds": timeout},
                cause={
                    "source": "ve-billing-cli",
                    "timeout_seconds": timeout,
                    **_safe_raw_error(str(exc.stdout or ""), "raw_stdout"),
                    **_safe_raw_error(str(exc.stderr or ""), "raw_stderr"),
                },
            ) from exc
        except OSError as exc:
            raise BillingQueryError(
                ErrorCode.ACTION_FAILED,
                f"无法执行 ve billing：{_safe_error_text(str(exc))}",
                ExitCode.QUERY_FAILED,
                cause={"source": "ve-billing-cli", "native_error": _safe_error_text(str(exc))},
            ) from exc
        stdout = completed.stdout.strip()
        if action in COST_CHANGE_ACTIONS and completed.returncode and re.search(
            r"(?:unknown (?:flag|option)|unrecognized (?:arguments?|options?)|"
            r"no such option|flag provided but not defined)[^\n]*?(?<![\w-])--?force(?![\w-])",
            completed.stderr + "\n" + completed.stdout,
            re.IGNORECASE,
        ):
            raise BillingQueryError(
                ErrorCode.VE_CLI_UPGRADE_REQUIRED,
                "当前 ve CLI 不支持 --force，请升级到支持 --force 的版本后重试；不要移除 --force 或回退接口。",
                ExitCode.DEPENDENCY_ERROR,
                cause=_ve_cause(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr),
            )
        response = _parse_stdout_json_object(stdout)
        if completed.returncode != 0:
            if response is not None:
                raise_for_api_error(
                    action,
                    response,
                    returncode=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                )
            message = _safe_error_text(completed.stderr or stdout)
            code = classify_remote_error("", message)
            raise BillingQueryError(
                code,
                f"{action} 调用失败：{message or 've 返回非零退出码'}",
                ExitCode.QUERY_FAILED,
                {"returncode": completed.returncode},
                cause=_ve_cause(
                    returncode=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                ),
            )
        if response is None:
            raise BillingQueryError(
                ErrorCode.RESPONSE_INVALID,
                f"{action} 返回空或非 JSON object",
                ExitCode.QUERY_FAILED,
            )
        raise_for_api_error(
            action,
            response,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        return response

    def get_caller_identity(self) -> Mapping[str, Any]:
        command = [self.executable, "sts", "GetCallerIdentity"]
        if self.region:
            command.extend(["---region", self.region])
        if self.profile:
            command.extend(["---profile", self.profile])
        try:
            completed = self.runner(
                command, capture_output=True, text=True,
                timeout=self.timeout_seconds if self.timeout_seconds is not None else 5,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BillingQueryError(ErrorCode.TIMEOUT, "当前查询身份核验超时", ExitCode.QUERY_FAILED) from exc
        except OSError as exc:
            raise BillingQueryError(ErrorCode.ACTION_FAILED, "无法执行当前查询身份核验", ExitCode.QUERY_FAILED) from exc
        response = _parse_stdout_json_object(completed.stdout)
        if completed.returncode != 0:
            remote_error = ((response or {}).get("ResponseMetadata") or {}).get("Error") or {}
            code = classify_remote_error(
                str(remote_error.get("Code") or ""),
                str(remote_error.get("Message") or completed.stderr),
            )
            # Identity failures do not need raw stdout, Trn or local profile details.
            raise BillingQueryError(code, "当前查询身份核验失败", ExitCode.QUERY_FAILED)
        if response is None:
            raise BillingQueryError(ErrorCode.RESPONSE_INVALID, "身份核验未返回 JSON 对象", ExitCode.QUERY_FAILED)
        return response


class FixtureBillingClient(BillingClient):
    backend_name = "fixture"

    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir
        self.calls: list[dict[str, Any]] = []
        if not fixture_dir.is_dir():
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                f"fixture 目录不存在：{fixture_dir}",
                ExitCode.INVALID_ARGUMENT,
            )

    def _candidates(self, action: str, body: Mapping[str, Any]) -> Sequence[Path]:
        if "NextToken" in body:
            raw_token = str(body.get("NextToken") or "")
            safe_token = "start" if raw_token in ("", "0") else re.sub(r"[^0-9A-Za-z_.-]", "_", raw_token)
            return (
                self.fixture_dir / f"{action}__token-{safe_token}.json",
                self.fixture_dir / f"{action}.json",
            )
        offset = int(body.get("Offset", 0))
        period = body.get("AmortizedMonth", body.get("BillPeriod", body.get("BeginTimeStr", "single")))
        safe_period = re.sub(r"[^0-9A-Za-z_.-]", "_", str(period))
        return (
            self.fixture_dir / f"{action}__period-{safe_period}__offset-{offset}.json",
            self.fixture_dir / f"{action}__offset-{offset}.json",
            self.fixture_dir / f"{action}.json",
        )

    def get_caller_identity(self) -> Mapping[str, Any] | None:
        path = self.fixture_dir / "GetCallerIdentity.json"
        if not path.is_file():
            return None
        parsed = json.loads(path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, Mapping) else None

    def query(self, action: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        normalized = validate_request_body(action, body)
        self.calls.append({"action": action, "body": normalized})
        path = next((path for path in self._candidates(action, normalized) if path.is_file()), None)
        if path is None:
            raise BillingQueryError(
                ErrorCode.ACTION_FAILED,
                f"缺少 fixture：{self._candidates(action, normalized)[0].name}",
                ExitCode.QUERY_FAILED,
            )
        parsed = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
        sentinel = parsed.get("__error__") if isinstance(parsed, Mapping) else None
        if isinstance(sentinel, Mapping):
            try:
                code = ErrorCode(str(sentinel.get("code", "ACTION_FAILED")))
            except ValueError:
                code = ErrorCode.ACTION_FAILED
            raise BillingQueryError(
                code,
                str(sentinel.get("message", "fixture simulated error")),
                ExitCode.QUERY_FAILED,
                {"retryable": bool(sentinel.get("retryable"))},
            )
        if not isinstance(parsed, Mapping):
            raise BillingQueryError(
                ErrorCode.RESPONSE_INVALID,
                f"fixture 顶层必须是 JSON object：{path.name}",
                ExitCode.QUERY_FAILED,
            )
        raise_for_api_error(action, parsed)
        return parsed
