#!/usr/bin/env python3
"""Run one RCA OpenAPI action through ve billing."""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from runtime_utils import OutputSanitizer, build_error

SERVICE = "billing"
API_VERSION = "2022-01-01"
VALID_ACTIONS = {"QueryCostChangeDimensions", "QueryCostChangeAmountComponents", "QueryCostChangeDrivers"}
ALLOWED_FILTER_KEYS = {"product", "instance_no", "charge_item_code", "project", "region_code"}
ALLOWED_LOCATE_DIMENSIONS = set(ALLOWED_FILTER_KEYS)


class AdapterError(ValueError):
    pass


class OpenAPIError(RuntimeError):
    def __init__(self, error_code, message, retryable=False, request_id=None, remote_code=None):
        sanitizer = OutputSanitizer()
        self.error_code = error_code
        self.message = sanitizer.sanitize(str(message))[:4000]
        self.retryable = retryable
        self.request_id = sanitizer.sanitize(request_id)
        self.remote_code = sanitizer.sanitize(remote_code)
        super().__init__(self.message)


@dataclass(frozen=True)
class OpenAPIConfig:
    environment: str = "online"
    region: Optional[str] = None
    endpoint: Optional[str] = None
    profile: Optional[str] = None
    timeout_seconds: float = 120

    def __post_init__(self):
        if self.environment not in {"online", "boe"}:
            raise AdapterError("environment must be online or boe")
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise AdapterError("timeout_seconds must be a positive finite number")
        for field in ("region", "endpoint", "profile"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip() or value.startswith("-")
                                      or any(ch.isspace() for ch in value)):
                raise AdapterError(f"invalid {field}")
        if self.endpoint:
            parsed = urlsplit(self.endpoint if "://" in self.endpoint else "//" + self.endpoint)
            if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in {"", "/"} or parsed.scheme not in {"", "https", "http"}):
                raise AdapterError("endpoint must be an API host without credentials, path or query")
        if self.environment == "boe" and not self.endpoint:
            raise AdapterError("BOE requires an explicit endpoint; production fallback is disabled")

    def metadata(self):
        return {"service": SERVICE, "version": API_VERSION, "method": "POST", "force": True, **asdict(self)}


def add_runtime_arguments(parser):
    parser.add_argument("--environment", choices=["online", "boe"])
    parser.add_argument("--region")
    parser.add_argument("--endpoint")
    parser.add_argument("--profile")
    parser.add_argument("--timeout-seconds", type=float)


def resolve_config(args):
    runtime_file = getattr(args, "runtime_config_file", None)
    fields = ("environment", "region", "endpoint", "profile", "timeout_seconds")
    if runtime_file:
        if any(getattr(args, key, None) is not None for key in fields):
            raise AdapterError("runtime-config-file cannot be combined with runtime overrides; start a new task")
        try:
            data = json.loads(Path(runtime_file).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or set(data) != set(fields):
                raise ValueError("unexpected config fields")
            return OpenAPIConfig(**data)
        except (OSError, ValueError, TypeError) as exc:
            raise AdapterError("invalid or missing runtime config file") from exc
    values = {}
    for key in fields:
        value = getattr(args, key, None)
        if value is None:
            value = os.environ.get("RCA_OPENAPI_" + key.upper())
        if value is None and key in {"region", "endpoint", "profile"}:
            value = os.environ.get("VOLCENGINE_" + key.upper())
        if value is not None:
            if key == "timeout_seconds":
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise AdapterError("invalid timeout_seconds") from exc
            values[key] = value
    return OpenAPIConfig(**values)


def validate_filters(filters):
    if filters is None:
        return {}
    if not isinstance(filters, dict):
        raise AdapterError("filters must be a JSON object")
    if set(filters) - ALLOWED_FILTER_KEYS:
        raise AdapterError("filters contains unsupported keys")
    if any(not isinstance(value, str) for value in filters.values()):
        raise AdapterError("filter values must be strings")
    return dict(filters)


def build_openapi_payload(action: str, model_args: Dict[str, Any]) -> Dict[str, Any]:
    if action not in VALID_ACTIONS:
        raise AdapterError(f"unsupported action: {action}")
    if not isinstance(model_args, dict):
        raise AdapterError("model arguments must be a JSON object")
    allowed = {"current_period", "base_period", "filters"}
    allowed.add("dimension" if action == "QueryCostChangeDimensions" else "charge_item_code")
    if set(model_args) - allowed:
        raise AdapterError("unsupported model argument; account identity and credentials must come from the runtime")
    for key in ("current_period", "base_period"):
        value = model_args.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-01", value):
            raise AdapterError(f"{key} must match YYYY-MM-01")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise AdapterError(f"{key} must be a valid month") from exc
    filters = validate_filters(model_args.get("filters"))
    current, base = model_args["current_period"], model_args["base_period"]
    if action == "QueryCostChangeDimensions":
        dimension = model_args.get("dimension")
        if not isinstance(dimension, str) or dimension not in ALLOWED_LOCATE_DIMENSIONS:
            raise AdapterError(f"QueryCostChangeDimensions dimension unsupported: {dimension}")
        return {"CurrentPeriod": current, "BasePeriod": base, "CandidateDimensions": [dimension], "Metric": 3, "Filters": filters}
    charge_item = model_args.get("charge_item_code")
    if not isinstance(charge_item, str) or not charge_item.strip():
        raise AdapterError(f"{action} requires charge_item_code")
    if "charge_item_code" in filters and filters["charge_item_code"] != charge_item:
        raise AdapterError("conflicting charge_item_code in filters")
    filters["charge_item_code"] = charge_item
    if action == "QueryCostChangeAmountComponents":
        return {"CurrentPeriod": current, "BasePeriod": base, "Metric": 3, "Filters": filters}
    return {"current_period": current, "base_period": base, "Metric": "original_bill_amount", "filters": filters}


def response_request_id(response):
    if not isinstance(response, dict):
        return None
    metadata = response.get("ResponseMetadata") or {}
    if not isinstance(metadata, dict):
        return None
    return metadata.get("RequestId") or metadata.get("RequestID")


def classify_error(code, message):
    text = (str(code) + " " + str(message)).lower()
    if any(x in text for x in ("throttl", "ratelimit", "rate limit", "flowlimit", "429")):
        return "OPENAPI_RATE_LIMITED", True
    if any(x in text for x in ("accesskey", "signature", "credential", "authentication", "unauthorized", "session token", "refresh token", "401")):
        return "OPENAPI_AUTHENTICATION_FAILED", False
    if any(x in text for x in ("accessdenied", "permission", "forbidden", "403")):
        return "OPENAPI_PERMISSION_DENIED", False
    if any(x in text for x in ("invalidparam", "invalidargument", "missingparameter")):
        return "OPENAPI_INVALID_PARAMETER", False
    if any(x in text for x in ("internalerror", "internalserver", "serviceunavailable", "temporarily unavailable", "502", "503", "504")):
        return "OPENAPI_SERVICE_ERROR", True
    return "OPENAPI_CALL_FAILED", False


def raise_api_error(response):
    metadata = response.get("ResponseMetadata") or {}
    remote = metadata.get("Error") if isinstance(metadata, dict) else None
    if remote:
        if not isinstance(remote, dict):
            raise OpenAPIError("OPENAPI_INVALID_RESPONSE", "malformed OpenAPI Error")
        code, message = remote.get("Code", "UNKNOWN"), remote.get("Message", "OpenAPI failed")
        category, retryable = classify_error(code, message)
        raise OpenAPIError(category, message, retryable, response_request_id(response), code)
    result = response.get("Result")
    base_resp = result.get("BaseResp") if isinstance(result, dict) else None
    if isinstance(base_resp, dict) and base_resp.get("StatusCode") not in (None, 0):
        raise OpenAPIError("OPENAPI_SERVICE_ERROR", base_resp.get("StatusMessage", "RPC failed"),
                           request_id=response_request_id(response), remote_code=base_resp.get("StatusCode"))


def validate_response(action, response):
    def invalid(message):
        return OpenAPIError("OPENAPI_INVALID_RESPONSE", message,
                            request_id=response_request_id(response))

    def check_numbers(obj, fields):
        for field in fields:
            number = obj.get(field)
            try:
                valid = not isinstance(number, bool) and isinstance(number, (int, float)) and math.isfinite(number)
            except OverflowError:
                valid = False
            if not valid:
                raise invalid(f"missing or invalid amount: {field}")

    result = response.get("Result")
    amounts = ("total_diff", "current_amount", "base_amount") if action == "QueryCostChangeDrivers" else ("totalDiff", "currentAmount", "baseAmount")
    list_key = "contributions" if action == "QueryCostChangeDrivers" else "candidates"
    if not isinstance(result, dict):
        raise invalid("OpenAPI response has no Result object")
    check_numbers(result, amounts)
    items = result.get(list_key)
    if list_key not in result or (items is not None and (not isinstance(items, list) or any(not isinstance(item, dict) for item in items))):
        raise invalid(f"invalid {list_key}")
    if action == "QueryCostChangeDrivers":
        for item in items or []:
            if not isinstance(item.get("dimension"), str):
                raise invalid("invalid contribution dimension")
            check_numbers(item, ("contribution", "current_amount", "base_amount"))
    else:
        for item in items or []:
            if not isinstance(item.get("dimension"), str):
                raise invalid("invalid candidate dimension")
            check_numbers(item, ("coverageRatio",))
            values = item.get("values")
            if "values" not in item or (values is not None and (not isinstance(values, list) or any(not isinstance(value, dict) for value in values))):
                raise invalid("invalid candidate values")
            for value in values or []:
                if not isinstance(value.get("valueKey"), str):
                    raise invalid("invalid candidate valueKey")
                check_numbers(value, ("deltaAmount", "baseAmount", "currentAmount", "contributionRatio"))


def call_openapi(action, payload, config, runner=None):
    if action not in VALID_ACTIONS:
        raise AdapterError("unsupported action")
    if not shutil.which("ve"):
        raise OpenAPIError("VE_CLI_NOT_FOUND", "ve is not installed or not on PATH")
    command = ["ve", SERVICE, action, "--force", "--version", API_VERSION,
               "--method", "POST", "--header", "Content-Type=application/json", "--output", "json",
               "--body", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))]
    for field in ("region", "endpoint", "profile"):
        if getattr(config, field):
            command.extend(["--" + field, getattr(config, field)])
    # Runtime routing/profile inputs were captured at init. Do not let later
    # environment changes override saved defaults; authentication stays in ve.
    child_env = dict(os.environ)
    for field in ("region", "endpoint", "profile"):
        child_env.pop("VOLCENGINE_" + field.upper(), None)
    try:
        completed = (runner or subprocess.run)(command, capture_output=True, text=True,
                                               timeout=config.timeout_seconds, check=False, shell=False, env=child_env)
    except subprocess.TimeoutExpired as exc:
        raise OpenAPIError("OPENAPI_TIMEOUT", "ve billing request timed out", retryable=True) from exc
    except OSError as exc:
        raise OpenAPIError("OPENAPI_CALL_FAILED", f"unable to execute ve: {exc}") from exc
    except UnicodeError as exc:
        raise OpenAPIError("OPENAPI_INVALID_RESPONSE", "ve output is not valid text") from exc
    # CLI option parsing errors occur before an OpenAPI request is sent.
    cli_output = (completed.stderr or "") + "\n" + (completed.stdout or "")
    if completed.returncode and re.search(
            r"(?:unknown (?:flag|option)|unrecognized (?:arguments?|options?)|"
            r"no such option|flag provided but not defined)[^\n]*?(?<![\w-])--?force(?![\w-])",
            cli_output, re.IGNORECASE):
        raise OpenAPIError(
            "VE_CLI_UPGRADE_REQUIRED",
            "当前 ve CLI 不支持 --force，请先升级 ve 到支持 --force 泛化调用的版本，"
            "然后重新发起分析。不要移除 --force 或回退旧接口。原始错误：" + cli_output.strip(),
            retryable=False)
    try:
        response = json.loads(completed.stdout)
        if not isinstance(response, dict):
            response = None
    except (ValueError, TypeError):
        response = None
    if response is not None:
        raise_api_error(response)
    if completed.returncode:
        message = completed.stderr or completed.stdout or f"ve exited with {completed.returncode}"
        code, retryable = classify_error("", message)
        raise OpenAPIError(code, message, retryable=retryable, request_id=response_request_id(response))
    if response is None:
        raise OpenAPIError("OPENAPI_INVALID_RESPONSE", "ve returned empty or non-JSON output")
    validate_response(action, response)
    return response


def build_parser():
    parser = argparse.ArgumentParser(description="Call one RCA OpenAPI action through ve billing --force")
    parser.add_argument("Action", choices=sorted(VALID_ACTIONS))
    parser.add_argument("RequestBodyJSON", help="Unified business arguments without AccountID or credentials")
    parser.add_argument("--runtime-config-file", help="Fixed config produced by run_rca_workflow.py init")
    add_runtime_arguments(parser)
    return parser


def cli_main(argv=None):
    args = build_parser().parse_args(argv)
    request_body, model_args, config = None, {}, None
    result, error = None, None
    try:
        config = resolve_config(args)
        try:
            model_args = json.loads(args.RequestBodyJSON)
        except ValueError as exc:
            raise AdapterError("RequestBodyJSON must be valid JSON") from exc
        request_body = build_openapi_payload(args.Action, model_args)
        result = call_openapi(args.Action, request_body, config)
    except OpenAPIError as exc:
        error = {**build_error(exc.error_code, exc.message, exc.retryable),
                 "request_id": exc.request_id, "remote_code": exc.remote_code}
    except (AdapterError, OSError) as exc:
        error = build_error("OPENAPI_INVALID_ARGUMENT", str(exc))
    metadata = config.metadata() if config else {}
    metadata["request_id"] = response_request_id(result) or (error or {}).get("request_id")
    output = {"status": "failed" if error else "success", "action": args.Action,
              "model_args": model_args, "request_body": request_body, "result": result,
              "openapi": metadata, "error": error}
    print(json.dumps(OutputSanitizer().sanitize(output), ensure_ascii=False, indent=2))
    return 1 if error else 0


def main():
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
