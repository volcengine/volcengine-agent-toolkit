#!/usr/bin/env python3
"""Query Volcengine CloudTrail and safely manage trails/backfill tasks.

Read operations execute immediately. Mutations perform read-only preflight and emit a
confirmation plan unless --confirm is present. stdout contains only structured output;
diagnostics are written to stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

VERSION = "2021-09-01"
MAX_LOOKUP_RESULTS = 50
MAX_LOOKBACK = timedelta(days=90)
DEFAULT_LOOKBACK = timedelta(days=3)
WINDOW_BOUNDARY_TOLERANCE_SECONDS = 300
WINDOW_BOUNDARY_SAFETY_MARGIN_SECONDS = 60
READINESS_DELAYS = (0.0, 0.5, 1.5)
MAX_BACKFILL_PAGES = 1000
ACTIVE_TASK_STATES = {"PENDING", "RUNNING"}
TERMINAL_TASK_STATES = {"FAILED", "STOPPED", "COMPLETED"}
TASK_STATES = ACTIVE_TASK_STATES | TERMINAL_TASK_STATES
ENABLED_LOGGING_STATES = {"Enable", "Enabled"}
DISABLED_LOGGING_STATES = {"Disable", "Disabled"}
SERVICE_NAME_RE = re.compile(r"^[a-z0-9_]+$")
LOOKUP_KEYS = {
    "EventSource",
    "EventName",
    "IdentityType",
    "IdentityName",
    "EventID",
    "RequestID",
    "AccessKeyID",
    "Region",
    "ResourceType",
    "ResourceID",
    "ApiVersion",
    "ErrorCode",
    "ReadOnly",
}
WRITE_ACTIONS = {
    "CreateTrail",
    "UpdateTrail",
    "DeleteTrail",
    "StartLogging",
    "StopLogging",
    "CreateBackfillDeliveryTask",
    "StopBackfillDeliveryTask",
}
ALLOWED_ACTIONS = {
    "LookupEvents",
    "DescribeTrails",
    "CreateTrail",
    "UpdateTrail",
    "DeleteTrail",
    "StartLogging",
    "StopLogging",
    "CreateBackfillDeliveryTask",
    "ListBackfillDeliveryTasks",
    "DescribeBackfillDeliveryTask",
    "StopBackfillDeliveryTask",
}
EVENT_FIELDS = (
    "EventTime",
    "EventName",
    "EventSource",
    "UserName",
    "SourceIPAddress",
    "Region",
    "ErrorCode",
    "RequestID",
    "EventID",
    "RelatedResources",
)
RAW_EVENT_FIELD_ORDER = (
    "EventVersion",
    "EventCategory",
    "EventID",
    "RequestID",
    "EventTime",
    "EventType",
    "UserIdentity",
    "EventSource",
    "EventSourceDisplay",
    "EventName",
    "EventNameDisplay",
    "Region",
    "SourceIPAddress",
    "UserAgent",
    "RequestParameters",
    "ResponseElements",
    "ReadOnly",
    "Resources",
    "ApiVersion",
    "RelatedResources",
    "OperationType",
    "ErrorCode",
)
LOCAL_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
EVENT_FIELD_MEANINGS = {
    "EventTime": "事件发生时间",
    "EventName": "审计事件名称",
    "EventSource": "触发事件的云服务",
    "UserName": "用户名",
    "SourceIPAddress": "来源 IP",
    "Region": "操作地域",
    "ErrorCode": "错误码，空值表示无错误",
    "RequestID": "业务 RequestID",
    "EventID": "审计事件唯一 ID",
    "RelatedResources": "结构化关联资源",
    "EventDetail": "服务端返回的原始事件详情",
    "ReadOnly": "是否只读操作",
    "ApiVersion": "API 版本",
    "AccessKeyID": "发起请求使用的 AccessKey ID",
    "EventType": "事件类型",
    "EventVersion": "审计日志格式版本",
    "EventCategory": "事件类别",
    "UserIdentity": "发起操作的身份",
    "AccountID": "账号 ID",
    "AccountId": "账号 ID",
    "Type": "身份类型",
    "PrincipalID": "主体 ID",
    "TRN": "身份或资源的 TRN",
    "EventSourceDisplay": "云服务中文展示名",
    "EventNameDisplay": "事件中文展示名",
    "UserAgent": "浏览器/客户端信息",
    "RequestParameters": "请求入参",
    "ResponseElements": "服务端返回结果",
    "Result": "API 业务结果",
    "User": "IAM 用户对象",
    "MobilePhoneIsVerify": "手机号是否已验证",
    "EmailIsVerify": "邮箱是否已验证",
    "Id": "资源或对象 ID",
    "Resources": "关联资源 TRN",
    "ServiceCode": "云服务代码",
    "IntegratedTrn": "关联资源完整 TRN",
    "ResourceType": "资源类型",
    "ResourceID": "资源 ID",
    "SourceType": "关联资源来源",
    "OperationType": "操作类型",
}
EVENT_VALUE_MEANINGS = {
    ("EventCategory", "Management"): "管理类/控制面事件",
    ("EventType", "ConsoleOperation"): "控制台操作",
    ("ReadOnly", "true"): "读操作",
    ("ReadOnly", "false"): "写操作",
    ("OperationType", "Create"): "创建操作",
    ("OperationType", "Update"): "更新操作",
    ("OperationType", "Delete"): "删除操作",
}
EVENT_SOURCE_NAMES = {
    "iam": "访问控制 IAM 服务",
}
EVENT_NAME_MEANINGS = {
    "CreateUser": "创建 IAM 用户",
}
PARAMETER_FLAG_OVERRIDES = {"TrailNames": "TrailNames.N"}

INDEXED_ARRAY_PARAMETERS = {"TrailNames", "EventSources"}


def delivery_target_summary(body: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    if "TosBucketRegion" in body or "TosBucketName" in body:
        region = body.get("TosBucketRegion") or "<未提供地域>"
        bucket = body.get("TosBucketName") or "<未提供桶名>"
        tos_segments = [
            {"Label": "地域", "Field": "TosBucketRegion", "Value": region},
            {"Label": "存储桶", "Field": "TosBucketName", "Value": bucket},
        ]
        tos_summary_parts = [
            f"地域（TosBucketRegion）为 {region}",
            f"存储桶（TosBucketName）为 {bucket}",
        ]
        if body.get("TosAccountId"):
            tos_segments.append(
                {"Label": "资源账号", "Field": "TosAccountId", "Value": body["TosAccountId"]}
            )
            tos_summary_parts.insert(
                0, f"资源账号（TosAccountId）为 {body['TosAccountId']}"
            )
        if body.get("TosWriteRoleTrn"):
            tos_segments.append(
                {"Label": "写入角色", "Field": "TosWriteRoleTrn", "Value": body["TosWriteRoleTrn"]}
            )
        target = {
            "Type": "TOS",
            "Summary": "TOS 投递目标：" + "，".join(tos_summary_parts),
            "Segments": tos_segments,
        }
        targets.append(target)
    if "TlsProjectRegion" in body or "TlsProjectName" in body or "TlsTopicName" in body:
        region = body.get("TlsProjectRegion") or "<未提供地域>"
        project = body.get("TlsProjectName") or "<未提供项目>"
        topic = body.get("TlsTopicName") or "<未提供主题>"
        tls_segments = [
            {"Label": "地域", "Field": "TlsProjectRegion", "Value": region},
            {"Label": "日志项目", "Field": "TlsProjectName", "Value": project},
            {"Label": "日志主题", "Field": "TlsTopicName", "Value": topic},
        ]
        tls_summary_parts = [
            f"地域（TlsProjectRegion）为 {region}",
            f"日志项目（TlsProjectName）为 {project}",
            f"日志主题（TlsTopicName）为 {topic}",
        ]
        if body.get("TlsAccountId"):
            tls_segments.append(
                {"Label": "资源账号", "Field": "TlsAccountId", "Value": body["TlsAccountId"]}
            )
            tls_summary_parts.insert(
                0, f"资源账号（TlsAccountId）为 {body['TlsAccountId']}"
            )
        if body.get("TlsWriteRoleTrn"):
            tls_segments.append(
                {"Label": "写入角色", "Field": "TlsWriteRoleTrn", "Value": body["TlsWriteRoleTrn"]}
            )
        target = {
            "Type": "TLS",
            "Summary": "TLS 投递目标：" + "，".join(tls_summary_parts),
            "Segments": tls_segments,
        }
        targets.append(target)
    return targets


def role_trn_account_id(role_trn: str) -> str | None:
    match = re.fullmatch(r"trn:iam::([0-9]+):role/.+", role_trn)
    return match.group(1) if match else None


def validate_kms_key_trn(value: str) -> None:
    if not re.fullmatch(r"trn:kms:[^:]+:[^:]+:keyrings/[^/]+/keys/[^/]+", value):
        raise CloudTrailError("TosSSEKMSKeyID 必须是合法 KMS key TRN")


def cross_account_delivery_guidance(
    body: dict[str, Any], source_account_id: str
) -> list[dict[str, Any]]:
    guidance: list[dict[str, Any]] = []
    for prefix, label in (("Tos", "TOS"), ("Tls", "TLS")):
        account_id = str(body.get(f"{prefix}AccountId") or "")
        role_trn = str(body.get(f"{prefix}WriteRoleTrn") or "")
        role_account_id = role_trn_account_id(role_trn) if role_trn else None
        cross_account = (
            account_id and account_id != source_account_id
        ) or (
            bool(role_account_id)
            and role_account_id != source_account_id
            and source_account_id != "unknown"
        )
        if not cross_account:
            continue
        guidance.append(
            {
                "TargetType": label,
                "ResourceAccountId": account_id or "<未提供>",
                "WriteRoleTrn": role_trn or "<未提供>",
                "CrossAccount": cross_account,
                "PreparationDefault": "agent-managed",
                "PreparationSteps": [
                    f"切换到 {label} 资源账号并确认目标投递资源存在；不存在时按用户给定名称创建",
                    "创建或复用投递角色，并绑定服务预置策略 CloudTrailDeliveryPolicy",
                    "配置角色信任策略，允许创建跟踪账号的 ServiceRoleForCloudTrail 执行 sts:AssumeRole",
                    "把目标账号 ID 与写入角色 TRN 写入 CreateTrail/UpdateTrail 请求",
                ],
                "RequiredBeforeCreate": [
                    f"{label} 资源账号内的投递资源存在",
                    "投递角色已绑定 CloudTrailDeliveryPolicy",
                    "投递角色信任源账号 ServiceRoleForCloudTrail",
                ],
                "TrustPolicyTemplate": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": ["sts:AssumeRole"],
                            "Principal": {
                                "IAM": [
                                    f"trn:iam::{source_account_id}:role/ServiceRoleForCloudTrail"
                                ]
                            },
                        }
                    ]
                },
            }
        )
    return guidance


def event_scope_summary(body: dict[str, Any]) -> str:
    include_all = body.get("IncludeAllEventSources")
    event_sources = body.get("EventSources")
    if include_all is True:
        return "全部事件源"
    if event_sources:
        return "仅跟踪 " + "、".join(str(item) for item in event_sources)
    if include_all is False:
        return "未覆盖全部事件源，事件源列表未在本次预案中提供"
    return "未在本次请求中修改事件源范围"


def delivery_target_lines(body: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for target in delivery_target_summary(body):
        lines.append(str(target["Type"]) + " 投递目标：")
        for segment in target.get("Segments", []):
            lines.append(
                f"  - {segment['Label']}（{segment['Field']}）：{segment['Value']}"
            )
    return lines


def user_facing_summary(
    action: str,
    body: dict[str, Any],
    args: argparse.Namespace,
    auth: dict[str, str],
) -> list[str]:
    title = {
        "CreateTrail": "创建操作审计跟踪",
        "UpdateTrail": "更新操作审计跟踪",
        "StartLogging": "开启操作审计跟踪",
        "StopLogging": "停止操作审计跟踪",
        "DeleteTrail": "删除操作审计跟踪",
        "CreateBackfillDeliveryTask": "创建操作审计历史补投",
        "StopBackfillDeliveryTask": "停止操作审计历史补投",
    }.get(action, f"{action} 操作预案")
    source_account = auth.get("AccountId", "unknown")
    target_accounts = sorted(
        {
            str(body.get(field))
            for field in ("TosAccountId", "TlsAccountId")
            if body.get(field) and str(body.get(field)) != source_account
        }
    )
    lines = [title]
    if target_accounts:
        lines.append(f"源账号 {source_account} -> 目标账号 {'、'.join(target_accounts)}")
    else:
        lines.append(f"账号 {source_account}")
    if "TrailName" in body:
        lines.append(f"跟踪名 {body['TrailName']}")
    if "TaskID" in body:
        lines.append(f"任务 ID {body['TaskID']}")
    if "TrailType" in body:
        lines.append(
            "组织级 Trail"
            if body["TrailType"] == 1
            else "单账号 Trail"
        )
    if "EventRW" in body:
        rw = {"All": "全部读写", "Read": "只读事件", "Write": "写事件"}.get(
            str(body["EventRW"]), str(body["EventRW"])
        )
        lines.append(f"{event_scope_summary(body)} · {rw}")
    elif "IncludeAllEventSources" in body or "EventSources" in body:
        lines.append(event_scope_summary(body))
    targets = delivery_target_summary(body)
    if targets:
        rendered_targets = []
        for target in targets:
            segments = {item["Field"]: item["Value"] for item in target.get("Segments", [])}
            if target["Type"] == "TOS":
                rendered_targets.append(
                    f"TOS {segments.get('TosBucketRegion', '<region>')} / {segments.get('TosBucketName', '<bucket>')}"
                )
            elif target["Type"] == "TLS":
                rendered_targets.append(
                    "TLS "
                    f"{segments.get('TlsProjectRegion', '<region>')} / "
                    f"{segments.get('TlsProjectName', '<project>')} / "
                    f"{segments.get('TlsTopicName', '<topic>')}"
                )
        lines.append("投递至 " + "；".join(rendered_targets))
    if action == "CreateBackfillDeliveryTask":
        lines.append(
            f"补投窗口 {epoch_rfc3339(int(body['StartTime']))} -> {epoch_rfc3339(int(body['EndTime']))}"
        )
    create_auto_start = action == "CreateTrail" and not getattr(args, "no_auto_start", False)
    action_text = {
        "CreateTrail": "创建 -> 校验 -> 开启" if create_auto_start else "创建 -> 校验",
        "UpdateTrail": "更新 -> 校验",
        "StartLogging": "开启 -> 校验",
        "StopLogging": "停止 -> 校验",
        "DeleteTrail": "删除 -> 校验",
        "CreateBackfillDeliveryTask": "创建补投 -> 校验",
        "StopBackfillDeliveryTask": "停止补投 -> 校验",
    }.get(action, action)
    lines.append(f"将执行：{action_text}")
    reminders = []
    if create_auto_start:
        reminders.append("创建成功后会直接开启记录，不再二次确认。")
    if target_accounts:
        reminders.append("跨账号投递默认先准备目标账号 IAM 角色和 TOS/TLS 目标配置。")
    if action == "StopLogging":
        reminders.append("停止后新的审计事件将不再记录或投递。")
    if reminders:
        lines.append("特殊提醒：" + " ".join(reminders))
    lines.append("下一步动作：回复「确认执行」继续。")
    return lines


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def add_bool_argument(
    parser: argparse.ArgumentParser,
    name: str,
    *,
    dest: str | None = None,
    help: str = "",
) -> None:
    resolved_dest = dest or name.removeprefix("--").replace("-", "_")
    group = parser.add_mutually_exclusive_group()
    kwargs: dict[str, Any] = {
        "dest": resolved_dest,
        "action": "store_true",
        "default": None,
        "help": help,
    }
    group.add_argument(name, **kwargs)
    negative = "--no-" + name.removeprefix("--")
    group.add_argument(negative, dest=resolved_dest, action="store_false")



class CloudTrailError(RuntimeError):
    """A user-actionable validation or API error."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        detail: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or ""
        self.context = context or {}


class ApiResult(dict[str, Any]):
    """Business Result plus safe response metadata from one API call."""

    def __init__(
        self, value: dict[str, Any] | None = None, *, metadata: dict[str, Any] | None = None
    ) -> None:
        super().__init__(value or {})
        self.metadata = metadata or {}


def api_metadata(value: Any) -> dict[str, Any]:
    metadata = getattr(value, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


class TrailList(list[dict[str, Any]]):
    def __init__(self, values: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
        super().__init__(values)
        self.metadata = metadata


class ActionAvailability(Enum):
    AVAILABLE = "available"
    UNREGISTERED = "unregistered"
    ERROR = "error"


def eprint(*values: Any) -> None:
    print(*values, file=sys.stderr, flush=True)


def parse_time(value: str) -> int:
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        parsed_date = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE)
        return int(parsed_date.timestamp())
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"无效时间 {value!r}；请使用 Unix 秒、RFC3339、YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TIMEZONE)
    return int(parsed.timestamp())


def parse_requested_time(value: Any, field: str, command_hint: str) -> int:
    text = str(value)
    if (
        field == "EndTime"
        and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text)
    ):
        parsed_date = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE)
        return int(
            parsed_date.replace(hour=23, minute=59, second=59).timestamp()
        )
    try:
        return parse_time(text)
    except (argparse.ArgumentTypeError, TypeError, ValueError) as exc:
        raise CloudTrailError(
            f"{field} 无法解析；请使用 Unix 秒、带时区 RFC3339、YYYY-MM-DD 或本地时间 YYYY-MM-DD HH:MM:SS",
            code="InvalidTime",
            context={
                "Field": field,
                "Reason": str(exc),
                "RequestedValue": value,
                "AllowedFormat": "Unix seconds, RFC3339, YYYY-MM-DD, or Asia/Shanghai local datetime",
                "SuggestedCommand": command_hint,
            },
        ) from exc


def parse_lookback_days(value: Any) -> int:
    try:
        days = int(str(value))
    except (TypeError, ValueError) as exc:
        raise CloudTrailError(
            "--lookback-days 必须是 1 到 90 的整数",
            code="InvalidLookbackDays",
            context={
                "Field": "lookback_days",
                "Reason": "not-an-integer",
                "RequestedValue": value,
                "AllowedRange": {"Minimum": 1, "Maximum": 90},
                "SuggestedCommand": "events lookup --lookback-days 3",
            },
        ) from exc
    if not 1 <= days <= 90:
        raise CloudTrailError(
            "--lookback-days 必须在 1 到 90 之间",
            code="InvalidLookbackDays",
            context={
                "Field": "lookback_days",
                "Reason": "out-of-range",
                "RequestedValue": value,
                "AllowedRange": {"Minimum": 1, "Maximum": 90},
                "SuggestedCommand": "events lookup --lookback-days 90",
            },
        )
    return days


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def epoch_rfc3339(value: int) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def add_cli_parameters(command: list[str], body: dict[str, Any]) -> None:
    for key, value in body.items():
        if key in INDEXED_ARRAY_PARAMETERS:
            values = value if isinstance(value, list) else [value]
            for index, item in enumerate(values, start=1):
                command.extend([f"--{key}.{index}", str(item)])
            continue
        flag = PARAMETER_FLAG_OVERRIDES.get(key, key)
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, (list, dict)):
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            rendered = str(value)
        command.extend([f"--{flag}", rendered])


def ve_command(
    action: str, body: dict[str, Any], args: argparse.Namespace, *, force: bool = False
) -> list[str]:
    command = ["ve", "cloudtrail", action]
    if force:
        if action != "CreateBackfillDeliveryTask":
            raise CloudTrailError("只有 CreateBackfillDeliveryTask 允许 --force 兜底")
        command.extend(["--force", "--version", VERSION, "--method", "GET"])
        add_cli_parameters(command, body)
    else:
        command.extend(["--version", VERSION])
        add_cli_parameters(command, body)
    if args.profile:
        command.extend(["--profile", args.profile])
    if args.region:
        command.extend(["--region", args.region])
    return command


def response_result(data: Any, action: str) -> ApiResult:
    if not isinstance(data, dict):
        raise CloudTrailError(f"[{action}] 响应顶层必须是 JSON object", code="InvalidResponseShape")
    metadata = data.get("ResponseMetadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise CloudTrailError(
            f"[{action}] ResponseMetadata 必须是 JSON object",
            code="InvalidResponseShape",
        )
    error = metadata.get("Error")
    if error:
        if not isinstance(error, dict):
            raise CloudTrailError(
                f"[{action}] ResponseMetadata.Error 必须是 JSON object",
                code="InvalidResponseShape",
            )
        code = str(error.get("Code", "Unknown"))
        detail = str(error.get("Message", ""))
        guidance = (
            "；当前 Trail 尚未具备可开启的事件范围配置"
            if code == "MissingEventSelector"
            else (
                "；在 Action/Version/Endpoint 已确认正确时通常表示账号未完成历史补投开白，"
                "请联系运营确认后再试"
            )
            if action == "CreateBackfillDeliveryTask"
            and code == "InvalidActionOrVersion"
            else ""
        )
        raise CloudTrailError(
            f"[{action}] Code={code} Message={detail}{guidance}",
            code=code,
            detail=detail,
        )
    result = data.get("Result")
    if result is not None and not isinstance(result, dict):
        raise CloudTrailError(f"[{action}] Result 必须是 JSON object", code="InvalidResponseShape")
    value = result if isinstance(result, dict) else {
        key: item for key, item in data.items() if key != "ResponseMetadata"
    }
    return ApiResult(value, metadata=metadata)


def api_response(value: Any) -> dict[str, Any]:
    return {"Result": dict(value), "ResponseMetadata": api_metadata(value)}


def call_ve(
    action: str,
    body: dict[str, Any],
    args: argparse.Namespace,
    *,
    force: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ApiResult:
    if action not in ALLOWED_ACTIONS:
        raise CloudTrailError(f"Action 不在 CloudTrail allowlist：{action}")
    if action in WRITE_ACTIONS and not getattr(args, "confirm", False):
        raise CloudTrailError(f"拒绝执行未确认的写操作 {action}")
    command = ve_command(action, body, args, force=force)
    try:
        proc = runner(command, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise CloudTrailError("未找到 ve；请先安装 @volcengine/cli 并完成鉴权") from exc
    except subprocess.TimeoutExpired as exc:
        raise CloudTrailError(
            f"[{action}] 调用超时；脚本不会重试，请核对实际状态",
            code="ClientTimeout",
        ) from exc
    stdout = proc.stdout.strip()
    if proc.returncode == 0 and stdout:
        try:
            return response_result(json.loads(stdout), action)
        except json.JSONDecodeError as exc:
            raise CloudTrailError(
                f"[{action}] 响应不是合法 JSON；脚本不会重试",
                code="InvalidResponseJSON",
            ) from exc
    if proc.returncode == 0:
        raise CloudTrailError(
            f"[{action}] 成功退出但响应为空；无法安全判断结果，脚本不会重试",
            code="EmptyResponse",
        )
    if (
        action == "CreateBackfillDeliveryTask"
        and re.search(r"\bInvalidActionOrVersion\b", proc.stderr)
    ):
        raise CloudTrailError(
            "[CreateBackfillDeliveryTask] Code=InvalidActionOrVersion："
            "已确认 Action/Version/Endpoint 正确时通常表示账号未完成历史补投开白；"
            "请联系运营确认，不要重复创建",
            code="InvalidActionOrVersion",
            detail=proc.stderr,
        )
    message = f"[{action}] 退出码={proc.returncode}: {proc.stderr.strip()[:500]}"
    raise CloudTrailError(f"{message}（脚本未自动重试）")


def action_availability(
    action: str,
    args: argparse.Namespace,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ActionAvailability:
    command = ["ve", "cloudtrail", action, "--help"]
    if args.profile:
        command.extend(["--profile", args.profile])
    try:
        proc = runner(command, capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ActionAvailability.ERROR
    if proc.returncode != 0:
        return ActionAvailability.ERROR
    first_nonempty = next(
        (line.strip() for line in proc.stdout.splitlines() if line.strip()), ""
    )
    if first_nonempty == action:
        return ActionAvailability.AVAILABLE
    if first_nonempty == "cloudtrail" and "Available Actions:" in proc.stdout:
        return ActionAvailability.UNREGISTERED
    return ActionAvailability.ERROR


def parse_available_actions(help_text: str) -> list[str]:
    lines = help_text.splitlines()
    actions: list[str] = []
    in_block = False
    seen_separator = False
    for line in lines:
        stripped = line.strip()
        if not in_block:
            in_block = stripped == "Available Actions:"
            continue
        if not seen_separator:
            if set(stripped) <= {"-", " "} and "-" in stripped:
                seen_separator = True
            continue
        if not stripped or stripped.startswith(("Use \"", "System Flags:")):
            break
        token = stripped.split()[0]
        if token and token != "help":
            actions.append(token)
    return actions


def list_service_actions(service: str, args: argparse.Namespace) -> list[str]:
    if not SERVICE_NAME_RE.fullmatch(service):
        raise CloudTrailError(f"非法服务名：{service!r}；只允许小写字母、数字和下划线")
    try:
        proc = subprocess.run(
            ["ve", service, "--help"], capture_output=True, text=True, timeout=20, check=False
        )
    except FileNotFoundError as exc:
        raise CloudTrailError("未找到 ve；请先安装 @volcengine/cli 并完成鉴权") from exc
    except subprocess.TimeoutExpired as exc:
        raise CloudTrailError(f"读取 {service} 本地元数据超时") from exc
    if proc.returncode != 0:
        raise CloudTrailError(
            f"读取 {service} 本地元数据失败：{proc.stderr.strip()[:300]}"
        )
    return parse_available_actions(proc.stdout)


def docs_search(query: str, args: argparse.Namespace, *, limit: int = 5) -> list[dict[str, Any]]:
    command = ["ve", "docs", "search", query, "--limit", str(limit), "--output", "json"]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError as exc:
        raise CloudTrailError("未找到 ve；请先安装 @volcengine/cli") from exc
    except subprocess.TimeoutExpired as exc:
        raise CloudTrailError("ve docs search 超时") from exc
    if proc.returncode != 0:
        raise CloudTrailError(f"ve docs search 失败：{proc.stderr.strip()[:300]}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CloudTrailError("ve docs search 返回的不是合法 JSON") from exc
    documents = payload.get("documents", []) if isinstance(payload, dict) else []
    return documents if isinstance(documents, list) else []


def cmd_events_resolve(args: argparse.Namespace) -> dict[str, Any]:
    if not args.service and not args.doc_search:
        raise CloudTrailError("resolve 至少需要 --service 或 --doc-search")
    result: dict[str, Any] = {"Resolve": True}
    if args.service:
        actions = list_service_actions(args.service, args)
        candidates = actions
        if args.keyword:
            needle = args.keyword.lower()
            candidates = [action for action in actions if needle in action.lower()]
        if args.action:
            candidates = [args.action] if args.action in actions else []
        result.update(
            {
                "Service": args.service,
                "EventSourceCandidate": args.service,
                "EventNameCandidates": candidates,
                "ActionMetadataAvailable": bool(actions),
                "Source": "local ve metadata",
            }
        )
    if args.doc_search:
        documents = docs_search(args.doc_search, args, limit=args.doc_limit)
        result["DocSearch"] = {
            "Query": args.doc_search,
            "Documents": [
                {
                    "Title": doc.get("title"),
                    "Url": doc.get("url"),
                    "ServiceCodes": doc.get("service_codes"),
                    "Snippet": (doc.get("snippet") or "")[:280],
                }
                for doc in documents
            ],
        }
    candidates = result.get("EventNameCandidates", [])
    if len(candidates) == 1:
        status, resolved, allowed, mode = (
            "action-unique",
            candidates[0],
            False,
            "audit-support-review",
        )
    elif len(candidates) > 1:
        status, resolved, allowed = "ambiguous", None, False
        mode = "semantic-review"
    else:
        status, resolved, allowed = "unresolved", None, False
        mode = "external-skill-fallback"
    recommendation: dict[str, str] = {}
    if args.resource_id:
        recommendation["ResourceID"] = args.resource_id
        if args.operation == "read":
            recommendation["ReadOnly"] = "true"
        elif args.operation == "write":
            recommendation["ReadOnly"] = "false"
    result.update(
        {
            "ResolutionStatus": status,
            "ResolvedEventName": resolved,
            "EventNameFilterAllowed": allowed,
            "RecommendedLookupMode": mode,
            "RecommendedLookupConditions": recommendation,
            "SemanticReviewRequired": status == "ambiguous",
            "AuditSupportEvidenceRequired": status == "action-unique",
            "SemanticReviewGuidance": (
                "先结合用户原话、动作语义、资源类型与读写属性排除不符合场景的候选；"
                "仍无法唯一确认时，可选择已安装的外部 skill 补证，但外部补证不是必经步骤"
            )
            if status == "ambiguous"
            else None,
            "AfterExternalFallback": (
                "resource-id-broad" if args.resource_id else "request-more-context"
            )
            if status != "unique"
            else None,
            "ExternalFallback": (
                None
                if status == "unique"
                else {
                    "Required": False,
                    "UseOnlyIfInstalled": [
                        "volcengine-api",
                        "volcengine-knowledge-search",
                    ],
                    "Purpose": "可选补证；不得因候选不唯一而自动调用",
                    "Condition": (
                        "语义判断后仍无法唯一确认"
                        if status == "ambiguous"
                        else (
                            "本地 Action 候选唯一，但仍需确认 CloudTrail 审计支持范围"
                            if status == "action-unique"
                            else "本地 resolve 未得到候选"
                        )
                    ),
                }
            ),
            "NextWithoutExternalFallback": (
                "resource-id-broad" if args.resource_id else "request-more-context"
            )
            if status != "unique"
            else None,
        }
    )
    return result


def auth_context(args: argparse.Namespace, *, verify: bool = True) -> dict[str, str]:
    context = {
        "Profile": args.profile or "current/default ve profile",
        "Region": args.region or "profile/CLI default",
    }
    if not verify:
        return {**context, "Identity": "not checked before whitelist confirmation"}
    command = ["ve", "sts", "GetCallerIdentity"]
    if args.profile:
        command.extend(["--profile", args.profile])
    if args.region:
        command.extend(["--region", args.region])
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise CloudTrailError("无法验证当前 ve 鉴权身份，拒绝生成写操作预案") from exc
    if proc.returncode != 0:
        raise CloudTrailError(
            "无法验证当前 ve 鉴权身份，拒绝生成写操作预案："
            + proc.stderr.strip()[:500]
        )
    try:
        identity = response_result(json.loads(proc.stdout), "GetCallerIdentity")
    except (json.JSONDecodeError, CloudTrailError) as exc:
        raise CloudTrailError("GetCallerIdentity 未返回可解析身份，拒绝生成写操作预案") from exc
    account_id = str(identity.get("AccountId") or identity.get("AccountID") or "")
    if not re.fullmatch(r"[0-9]+", account_id):
        raise CloudTrailError(
            "GetCallerIdentity 未返回有效 AccountId，拒绝生成写操作预案",
            code="InvalidIdentityResponse",
        )
    return {
        **context,
        "AccountId": account_id,
        "IdentityId": str(identity.get("IdentityId") or "unknown"),
        "IdentityType": str(identity.get("IdentityType") or "unknown"),
        "Trn": str(identity.get("Trn") or identity.get("TRN") or "unknown"),
    }


def verify_after_write(
    callback: Callable[[], Any], predicate: Callable[[Any], bool]
) -> dict[str, Any]:
    last_observation: Any = None
    last_error: CloudTrailError | None = None
    for delay in READINESS_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            last_observation = callback()
            last_error = None
            if predicate(last_observation):
                return {"Verification": last_observation, "StateVerified": True}
        except CloudTrailError as exc:
            last_error = exc
    result: dict[str, Any] = {
        "Verification": last_observation,
        "StateVerified": False,
        "VerificationNote": (
            "写操作已受理，但只读观察尚未达到目标状态；不要重试写操作，只重试验证"
        ),
    }
    if last_error is not None:
        result["VerificationError"] = str(last_error)
    return result


def plan(
    action: str,
    target: dict[str, Any],
    body: dict[str, Any],
    args: argparse.Namespace,
    *,
    impact: str,
    verify: str,
    recovery: str,
    precheck: Any = None,
    warning: str | None = None,
    verify_identity: bool = True,
    verified_auth_context: dict[str, str] | None = None,
    explain: bool = False,
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    auth = (
        verified_auth_context
        if verified_auth_context is not None
        else auth_context(args, verify=verify_identity)
    )
    result: dict[str, Any] = {
        "DryRun": True,
        "Action": action,
        "Version": VERSION,
        "AuthContext": auth,
        "Target": target,
        "Request": body,
        "Impact": impact,
        "AsyncSemantics": "控制面成功不代表规则编译或投递运行态立即收敛",
        "Recovery": recovery,
    }
    if explain:
        result["RequestExplain"] = explain_request(body)
        delivery_targets = delivery_target_summary(body)
        if delivery_targets:
            result["DeliveryTargets"] = delivery_targets
        summary = user_facing_summary(action, body, args, auth)
        if summary:
            result["UserFacingSummary"] = summary
            result["操作摘要"] = [
                line
                for line in summary
                if not line.startswith("特殊提醒：")
                and not line.startswith("下一步动作：")
            ]
            reminders = [
                line.removeprefix("特殊提醒：")
                for line in summary
                if line.startswith("特殊提醒：")
            ]
            if warning:
                reminders.append(warning)
            result["特殊提醒"] = reminders or ["无"]
            result["下一步动作"] = (
                "回复「确认执行」继续。"
                if requires_confirmation
                else "按提示补齐前置条件后重试。"
            )
        account_id = auth.get("AccountId", "unknown")
        cross_account = cross_account_delivery_guidance(body, account_id)
        if cross_account:
            result["CrossAccountDelivery"] = cross_account
    if precheck is not None:
        result["Precheck"] = precheck
    if warning:
        result["Warning"] = warning
    return result


def response_metadata_fields(*responses: Any) -> dict[str, Any]:
    items = [api_metadata(item) for item in responses if api_metadata(item)]
    if not items:
        return {}
    return {"ResponseMetadata": items[0] if len(items) == 1 else items}


def normalized_equal(observed: Any, expected: Any) -> bool:
    if isinstance(observed, bool) or isinstance(expected, bool):
        return observed is expected
    if isinstance(expected, list):
        return list(observed or []) == expected
    return str(observed) == str(expected)


def matching_trail(
    trails: Any, trail_name: str, expected: dict[str, Any] | None = None
) -> bool:
    if not isinstance(trails, list):
        return False
    for trail in trails:
        if not isinstance(trail, dict) or trail.get("TrailName") != trail_name:
            continue
        return all(
            normalized_equal(trail.get(field), value)
            for field, value in (expected or {}).items()
            if field != "TrailName"
        )
    return False


def write_result(
    action: str, result: ApiResult, verification: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    return {
        "DryRun": False,
        "WriteAccepted": True,
        "Action": action,
        "Result": result,
        "ApiResponse": api_response(result),
        **response_metadata_fields(result),
        **extra,
        **verification,
    }


def describe_trails(args: argparse.Namespace, trail_name: str | None = None) -> list[dict[str, Any]]:
    body: dict[str, Any] = {}
    if trail_name:
        body["TrailNames"] = [trail_name]
    if getattr(args, "include_organization_trail", False):
        body["IncludeOrganizationTrail"] = 1
    result = call_ve("DescribeTrails", body, args)
    trails = result.get("Trails", [])
    if not isinstance(trails, list):
        raise CloudTrailError("DescribeTrails 响应缺少合法 Trails 列表")
    return TrailList(trails, api_metadata(result))


def find_trail(args: argparse.Namespace, trail_name: str) -> dict[str, Any] | None:
    for trail in describe_trails(args, trail_name):
        if trail.get("TrailName") == trail_name:
            return trail
    return None


def require_trail(args: argparse.Namespace, trail_name: str) -> dict[str, Any]:
    trail = find_trail(args, trail_name)
    if trail is None:
        raise CloudTrailError(f"Trail {trail_name!r} 不存在或当前身份不可见")
    return trail


def parse_conditions(items: list[str]) -> list[dict[str, str]]:
    conditions: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise CloudTrailError(f"查询条件必须是 Key=Value：{item!r}")
        key, value = item.split("=", 1)
        if key not in LOOKUP_KEYS or not value:
            raise CloudTrailError(f"不支持的查询条件：{item!r}")
        if key == "ReadOnly" and value not in {"true", "false"}:
            raise CloudTrailError("ReadOnly 必须是字符串 true 或 false")
        if key in conditions:
            raise CloudTrailError(f"查询条件重复：{key}")
        conditions[key] = value
    return [{"LookupConditionKey": key, "LookupConditionValue": value} for key, value in conditions.items()]


def validate_lookup_arguments(
    args: argparse.Namespace, lookback_days: int | None, lookback_days_raw: Any
) -> None:
    if lookback_days is not None and (
        args.start_time is not None
        or args.end_time is not None
        or args.next_token
        or args.query_fingerprint
    ):
        raise CloudTrailError(
            "--lookback-days 仅用于首屏查询，不能与绝对时间或续页参数同时使用",
            code="LookupWindowConflict",
            context={
                "Reason": "relative-and-absolute-or-continuation-conflict",
                "RequestedLookbackDays": lookback_days_raw,
                "RequestedStartTime": args.start_time,
                "RequestedEndTime": args.end_time,
                "HasNextToken": bool(args.next_token),
                "AllowedCombinations": [
                    "--lookback-days <1..90>",
                    "--start-time <time> --end-time <time>",
                    "--start-time <time> --end-time <time> --next-token <token> --query-fingerprint <sha256>",
                ],
                "SuggestedCommand": "events lookup --lookback-days 3",
            },
        )
    if args.next_token and (
        args.start_time is None
        or args.end_time is None
        or not args.query_fingerprint
    ):
        raise CloudTrailError(
            "使用 --next-token 时必须同时重传原查询的 --start-time、--end-time、"
            "筛选条件和 --query-fingerprint"
        )
    if args.query_fingerprint and not args.next_token:
        raise CloudTrailError("--query-fingerprint 只能与 --next-token 一起使用")
    if args.operation != "any" and not args.resource_id:
        raise CloudTrailError("--operation 只能与 --resource-id 一起使用")
    if args.signin_action and args.resource_id:
        raise CloudTrailError("--signin-action 与 --resource-id 不能同时使用")
    if args.signin_action and args.operation != "any":
        raise CloudTrailError("登录查询不能使用 --operation")


def lookup_time_window(
    args: argparse.Namespace, now_epoch: int, lookback_days: int | None
) -> tuple[int, int]:
    start_input = args.start_time
    end_input = args.end_time
    if lookback_days is not None:
        end = now_epoch
        start = end - lookback_days * 24 * 60 * 60
        if lookback_days == 90:
            start += WINDOW_BOUNDARY_SAFETY_MARGIN_SECONDS
    else:
        end = (
            parse_requested_time(
                end_input, "EndTime", "events lookup --lookback-days 3"
            )
            if end_input is not None
            else now_epoch
        )
        start = (
            parse_requested_time(
                start_input, "StartTime", "events lookup --lookback-days 3"
            )
            if start_input is not None
            else end - int(DEFAULT_LOOKBACK.total_seconds())
        )
    return validate_lookup_time_window(start, end, now_epoch)


def validate_lookup_time_window(start: int, end: int, now_epoch: int) -> tuple[int, int]:
    if end <= start:
        raise CloudTrailError(
            "EndTime 必须晚于 StartTime",
            code="LookupWindowEmpty" if end == start else "LookupWindowReversed",
            context={
                "Reason": "empty-window" if end == start else "reversed-window",
                "RequestedStartTime": start,
                "RequestedEndTime": end,
                "AllowedRange": {"MinimumSeconds": 1, "MaximumDays": 90},
                "SuggestedCommand": "events lookup --lookback-days 3",
            },
        )
    if end > now_epoch:
        raise CloudTrailError(
            "EndTime 不能晚于当前时间",
            code="LookupEndInFuture",
            context={
                "Reason": "end-in-future",
                "RequestedEndTime": end,
                "CurrentTime": now_epoch,
                "AllowedRange": {"LatestEndTime": now_epoch},
                "SuggestedCommand": "events lookup --lookback-days 3",
            },
        )
    if end - start > int(MAX_LOOKBACK.total_seconds()):
        overflow = end - start - int(MAX_LOOKBACK.total_seconds())
        if 0 < overflow <= WINDOW_BOUNDARY_TOLERANCE_SECONDS:
            start = end - int(MAX_LOOKBACK.total_seconds()) + WINDOW_BOUNDARY_SAFETY_MARGIN_SECONDS
        else:
            raise CloudTrailError(
                "查询时间跨度不得超过 90 天；最近 90 天请直接使用 --lookback-days 90",
                code="LookupWindowTooLarge",
                context={
                    "RequestedWindowSeconds": end - start,
                    "MaximumWindowSeconds": int(MAX_LOOKBACK.total_seconds()),
                    "Reason": "window-too-large",
                    "AllowedRange": {"MaximumDays": 90},
                    "Correction": {"UseLookbackDays": 90},
                    "SuggestedCommand": "events lookup --lookback-days 90",
                },
            )
    earliest = now_epoch - int(MAX_LOOKBACK.total_seconds())
    if start < earliest:
        drift = earliest - start
        if 0 < drift <= WINDOW_BOUNDARY_TOLERANCE_SECONDS:
            start = earliest + WINDOW_BOUNDARY_SAFETY_MARGIN_SECONDS
        else:
            raise CloudTrailError(
                "StartTime 不得早于最近 90 天；请使用 --lookback-days 90 避免边界漂移",
                code="LookupStartBeforeRetention",
                context={
                    "RequestedStartTime": start,
                    "EarliestAllowedStartTime": earliest,
                    "ExceededBySeconds": earliest - start,
                    "Reason": "before-retention",
                    "AllowedRange": {
                        "EarliestStartTime": earliest,
                        "LatestEndTime": now_epoch,
                    },
                    "Correction": {"UseLookbackDays": 90},
                    "SuggestedCommand": "events lookup --lookback-days 90",
                },
            )
    return start, end


def validate_lookup_limit(args: argparse.Namespace) -> None:
    if args.max_results < 1 or args.max_results > MAX_LOOKUP_RESULTS:
        raise CloudTrailError("单次查询条数必须在 1 到 50 之间；请缩小时间或筛选条件")
    has_explicit_boundary = any(
        (
            args.start_time is not None,
            args.end_time is not None,
            bool(args.condition),
            bool(args.signin_action),
            bool(args.resource_id),
            bool(args.event_source),
            bool(args.event_name),
            bool(args.iam_user_name),
        )
    )
    if args.all and not has_explicit_boundary:
        raise CloudTrailError("有界全量查询必须显式指定时间范围或筛选条件")


def add_derived_lookup_condition(derived: dict[str, str], key: str, value: str) -> None:
    if key in derived and derived[key] != value:
        raise CloudTrailError(f"查询参数冲突：{key}")
    derived[key] = value


def derived_lookup_conditions(args: argparse.Namespace) -> dict[str, str]:
    derived: dict[str, str] = {}
    if args.signin_action:
        add_derived_lookup_condition(derived, "EventSource", "signin")
        if args.signin_action == "login":
            add_derived_lookup_condition(derived, "EventName", "ConsoleSignIn")
        elif args.signin_action == "logout":
            add_derived_lookup_condition(derived, "EventName", "ConsoleSignOut")
    if args.resource_id:
        add_derived_lookup_condition(derived, "ResourceID", args.resource_id)
        if args.operation == "write":
            add_derived_lookup_condition(derived, "ReadOnly", "false")
        elif args.operation == "read":
            add_derived_lookup_condition(derived, "ReadOnly", "true")
    if args.event_source:
        add_derived_lookup_condition(derived, "EventSource", args.event_source)
    if args.event_name:
        add_derived_lookup_condition(derived, "EventName", args.event_name)
    if args.iam_user_name:
        if re.fullmatch(r"[0-9]+", args.iam_user_name):
            raise CloudTrailError("IAM 子用户 ID 不能直接作为 IdentityName；请先解析用户名")
        add_derived_lookup_condition(derived, "IdentityType", "IAMUser")
        add_derived_lookup_condition(derived, "IdentityName", args.iam_user_name)
    return derived


def lookup_conditions(args: argparse.Namespace) -> dict[str, str]:
    conditions = {
        item["LookupConditionKey"]: item["LookupConditionValue"]
        for item in parse_conditions(args.condition)
    }
    for key, value in derived_lookup_conditions(args).items():
        if key in conditions and conditions[key] != value:
            raise CloudTrailError(f"查询条件冲突：{key}")
        conditions[key] = value
    return conditions


def attach_lookup_next_token(args: argparse.Namespace, body: dict[str, Any]) -> None:
    fingerprint = calculate_query_fingerprint(body)
    if args.next_token and args.query_fingerprint != fingerprint:
        raise CloudTrailError("续页查询条件与生成 NextToken 的原查询不一致")
    if args.next_token:
        body["NextToken"] = args.next_token


def lookup_body(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    now_epoch = int(now.timestamp())
    lookback_days_raw = getattr(args, "lookback_days", None)
    lookback_days = (
        parse_lookback_days(lookback_days_raw)
        if lookback_days_raw is not None
        else None
    )
    validate_lookup_arguments(args, lookback_days, lookback_days_raw)
    start, end = lookup_time_window(args, now_epoch, lookback_days)
    validate_lookup_limit(args)
    conditions = lookup_conditions(args)
    body: dict[str, Any] = {
        "StartTime": start,
        "EndTime": end,
        "MaxResults": MAX_LOOKUP_RESULTS if args.all else args.max_results,
        "LookupConditions": [
            {"LookupConditionKey": key, "LookupConditionValue": value}
            for key, value in conditions.items()
        ],
    }
    attach_lookup_next_token(args, body)
    return body


def calculate_query_fingerprint(body: dict[str, Any]) -> str:
    stable_body = {key: value for key, value in body.items() if key != "NextToken"}
    encoded = json.dumps(
        stable_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {field: event.get(field) for field in EVENT_FIELDS if event.get(field) not in (None, "", [])}


def field_meaning(field: str, value: Any, path: tuple[str, ...], parent: dict[str, Any]) -> str:
    if isinstance(value, str):
        specific = EVENT_VALUE_MEANINGS.get((field, value))
        if specific:
            return specific
    if field == "RequestID" and parent.get("EventName") == "CreateUser":
        return "本次创建用户请求的业务 RequestID"
    if field == "Type" and path == ("UserIdentity",) and value == "Root":
        return "主账号身份"
    if field == "PrincipalID" and path == ("UserIdentity",):
        return "主体 ID"
    if field == "UserName" and path == ("UserIdentity",):
        return "操作者名称"
    if field == "UserName" and path[-1:] == ("RequestParameters",):
        return "被操作的 IAM 用户名"
    if field == "UserName" and (
        path[-2:] == ("ResponseElements", "Result")
        or path[-3:] == ("ResponseElements", "Result", "User")
    ):
        return "创建成功的用户名"
    if field == "AccountID" and path == ("UserIdentity",):
        return "操作者所属账号"
    if field == "AccountId" and path[-3:] == ("ResponseElements", "Result", "User"):
        return "用户所属账号"
    if field == "TRN" and path == ("UserIdentity",):
        return "操作者身份 TRN"
    if field == "EventSource":
        return EVENT_SOURCE_NAMES.get(str(value), EVENT_FIELD_MEANINGS[field])
    if field == "EventName":
        return EVENT_NAME_MEANINGS.get(str(value), EVENT_FIELD_MEANINGS[field])
    if field == "DisplayName" and path[-1:] == ("RequestParameters",):
        return "展示名" + ("，空" if value == "" else "")
    if field == "Description" and path[-1:] == ("RequestParameters",):
        return "用户描述" + ("，空" if value == "" else "")
    if field == "MobilePhoneIsVerify" and value is False:
        return "手机号未验证"
    if field == "EmailIsVerify" and value is False:
        return "邮箱未验证"
    if field == "Id" and path[-3:] == ("ResponseElements", "Result", "User"):
        return "新建 IAM 用户内部 ID"
    if field == "ResourceType" and value == "user":
        return "资源类型：IAM 用户"
    if field == "SourceType" and value == "request":
        return "从请求参数识别"
    return EVENT_FIELD_MEANINGS.get(field, "原始审计日志字段")


def ordered_event_items(value: dict[str, Any]) -> list[tuple[str, Any]]:
    ordered_keys = [field for field in RAW_EVENT_FIELD_ORDER if field in value]
    ordered_keys.extend(field for field in value if field not in ordered_keys)
    return [(field, value[field]) for field in ordered_keys]


def jsonc_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def annotated_jsonc(
    value: Any, indent: int = 2, path: tuple[str, ...] = ()
) -> list[str]:
    pad = " " * indent
    if isinstance(value, dict):
        lines = ["{"]
        items = ordered_event_items(value)
        for index, (key, item) in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            comment = field_meaning(key, item, path, value)
            if isinstance(item, (dict, list)):
                nested = annotated_jsonc(item, indent + 2, (*path, key))
                if len(nested) == 1:
                    lines.append(
                        f'{pad}{json.dumps(key, ensure_ascii=False)}: {nested[0]}{comma} // {comment}'
                    )
                else:
                    lines.append(f'{pad}{json.dumps(key, ensure_ascii=False)}: {nested[0]} // {comment}')
                    lines.extend(nested[1:-1])
                    lines.append(f"{nested[-1]}{comma}")
            else:
                lines.append(
                    f'{pad}{json.dumps(key, ensure_ascii=False)}: {jsonc_scalar(item)}{comma} // {comment}'
                )
        lines.append(" " * (indent - 2) + "}")
        return lines
    if isinstance(value, list):
        if not value:
            return ["[]"]
        if all(not isinstance(item, (dict, list)) for item in value):
            rendered = json.dumps(value, ensure_ascii=False)
            return [rendered]
        lines = ["["]
        for index, item in enumerate(value):
            comma = "," if index < len(value) - 1 else ""
            nested = annotated_jsonc(item, indent + 2, path)
            if len(nested) == 1:
                lines.append(f"{pad}{nested[0]}{comma}")
            else:
                lines.append(f"{pad}{nested[0]}")
                lines.extend(nested[1:-1])
                lines.append(f"{nested[-1]}{comma}")
        lines.append(" " * (indent - 2) + "]")
        return lines
    return [jsonc_scalar(value)]


def annotated_event_log(event: dict[str, Any]) -> str:
    display_event = event_detail_object(event) or event
    return "◆ " + "\n".join(annotated_jsonc(display_event, indent=2))


def event_detail_object(event: dict[str, Any]) -> dict[str, Any] | None:
    detail = event.get("EventDetail")
    if isinstance(detail, dict):
        return detail
    if not isinstance(detail, str) or not detail.strip():
        return None
    try:
        parsed = json.loads(detail)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def cmd_events_lookup(args: argparse.Namespace) -> dict[str, Any]:
    identity = auth_context(args)
    body = lookup_body(args)
    result = call_ve("LookupEvents", body, args)
    events = result.get("Trails", [])
    events = sorted(events if isinstance(events, list) else [], key=lambda x: x.get("EventTime", ""), reverse=True)
    rendered_events = events if args.raw else [event_summary(event) for event in events]
    annotated_logs = [annotated_event_log(event) for event in events] if args.raw else []
    next_token = result.get("NextToken") or ""
    output = {
        "Conclusion": "当前查询范围内无记录" if not events else f"查询到 {len(events)} 条候选审计事件",
        "AuthContext": identity,
        "Query": body,
        "Events": rendered_events,
        "ApiResponse": {
            "Result": {
                "NextToken": next_token,
                "Trails": rendered_events,
            },
            "ResponseMetadata": api_metadata(result),
        },
        "RawEventOutput": bool(args.raw),
        "HasMore": bool(next_token),
        "NextToken": next_token,
        "QueryFingerprint": calculate_query_fingerprint(body),
        "ResolvedWindow": {
            "Mode": "relative" if getattr(args, "lookback_days", None) is not None else "absolute",
            "RequestedLookbackDays": getattr(args, "lookback_days", None),
            "StartTime": body["StartTime"],
            "EndTime": body["EndTime"],
            "StartTimeRFC3339": epoch_rfc3339(body["StartTime"]),
            "EndTimeRFC3339": epoch_rfc3339(body["EndTime"]),
            "StartTimeLocal": datetime.fromtimestamp(
                body["StartTime"], LOCAL_TIMEZONE
            ).isoformat(),
            "EndTimeLocal": datetime.fromtimestamp(
                body["EndTime"], LOCAL_TIMEZONE
            ).isoformat(),
        },
        **response_metadata_fields(result),
        "PaginationNote": (
            "仍有更多结果；未自动翻页。可缩小范围，或显式传 --next-token 查询下一页。"
            if next_token
            else "当前条件下本次返回已到末页。"
        ),
    }
    if args.raw:
        output["AnnotatedEventLogs"] = annotated_logs
    return output


class TrailFieldSpec:
    def __init__(
        self, argument: str, api_field: str, flag: str, group: str, meaning: str
    ) -> None:
        self.argument = argument
        self.api_field = api_field
        self.flag = flag
        self.group = group
        self.meaning = meaning


TRAIL_FIELD_SPECS = (
    TrailFieldSpec("trail_name", "TrailName", "--trail-name", "基础配置", "跟踪名称"),
    TrailFieldSpec("trail_type", "TrailType", "--trail-type", "基础配置", "跟踪类型：0=单账号，1=组织"),
    TrailFieldSpec("event_rw", "EventRW", "--event-rw", "基础配置", "管理事件读写范围：All / Read / Write"),
    TrailFieldSpec("include_all_event_sources", "IncludeAllEventSources", "--include-all-event-sources", "基础配置", "是否覆盖全部事件源"),
    TrailFieldSpec("event_sources", "EventSources", "--event-source", "基础配置", "指定管理事件源列表"),
    TrailFieldSpec("tos_account_id", "TosAccountId", "--tos-account-id", "TOS 投递", "目标 TOS 所属账号 ID"),
    TrailFieldSpec("tos_write_role_trn", "TosWriteRoleTrn", "--tos-write-role-trn", "TOS 投递", "跨账号写入角色 TRN"),
    TrailFieldSpec("tos_bucket_region", "TosBucketRegion", "--tos-bucket-region", "TOS 投递", "TOS 存储桶所在地域"),
    TrailFieldSpec("tos_bucket_name", "TosBucketName", "--tos-bucket-name", "TOS 投递", "TOS 存储桶名称"),
    TrailFieldSpec("tos_key_prefix", "TosKeyPrefix", "--tos-key-prefix", "TOS 投递", "投递对象路径前缀"),
    TrailFieldSpec("tos_bucket_project", "TosBucketProject", "--tos-bucket-project", "TOS 投递", "TOS 存储桶所属项目"),
    TrailFieldSpec("tos_sse_algorithm", "TosSSEAlgorithm", "--tos-sse-algorithm", "TOS 投递", "服务端加密算法：AES256 或 kms"),
    TrailFieldSpec("tos_sse_kms_key_id", "TosSSEKMSKeyID", "--tos-sse-kms-key-id", "TOS 投递", "kms 加密密钥 TRN"),
    TrailFieldSpec("tls_account_id", "TlsAccountId", "--tls-account-id", "TLS 投递", "目标 TLS 所属账号 ID"),
    TrailFieldSpec("tls_write_role_trn", "TlsWriteRoleTrn", "--tls-write-role-trn", "TLS 投递", "跨账号写入角色 TRN"),
    TrailFieldSpec("tls_project_region", "TlsProjectRegion", "--tls-project-region", "TLS 投递", "TLS 日志项目所在地域"),
    TrailFieldSpec("tls_project_name", "TlsProjectName", "--tls-project-name", "TLS 投递", "TLS 日志项目名称"),
    TrailFieldSpec("tls_topic_name", "TlsTopicName", "--tls-topic-name", "TLS 投递", "TLS 日志主题名称"),
    TrailFieldSpec("tls_project_topic_project", "TlsProjectTopicProject", "--tls-project-topic-project", "TLS 投递", "TLS 日志主题所属项目"),
)
TRAIL_FIELDS = {spec.argument: spec.api_field for spec in TRAIL_FIELD_SPECS}
SPECIAL_TRAIL_ARGUMENTS = {
    "trail_name",
    "event_rw",
    "event_sources",
    "include_all_event_sources",
}
FIELD_LABELS = {spec.api_field: (spec.group, spec.meaning) for spec in TRAIL_FIELD_SPECS}
FIELD_GROUP_ORDER = ("基础配置", "TOS 投递", "TLS 投递", "其他")


def explain_request(body: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for field, value in body.items():
        group, label = FIELD_LABELS.get(field, ("其他", field))
        grouped.setdefault(group, []).append(
            {"Field": field, "Value": value, "Meaning": label}
        )
    return {group: grouped[group] for group in FIELD_GROUP_ORDER if group in grouped}


def validate_cross_account_delivery(body: dict[str, Any], source_account_id: str) -> None:
    if not re.fullmatch(r"[0-9]+", source_account_id):
        raise CloudTrailError("当前身份缺少有效账号 ID，拒绝校验投递配置")
    for prefix, label in (("Tos", "TOS"), ("Tls", "TLS")):
        account_id = body.get(f"{prefix}AccountId")
        role_trn = body.get(f"{prefix}WriteRoleTrn")
        if account_id is not None and not re.fullmatch(r"[0-9]+", str(account_id)):
            raise CloudTrailError(f"{label} 投递目标账号 ID 必须是数字")
        role_account_id = role_trn_account_id(str(role_trn)) if role_trn else None
        if role_trn and role_account_id is None:
            raise CloudTrailError(f"{label} 写入角色必须是合法 IAM role TRN")
        if account_id is not None and role_account_id is not None and str(account_id) != role_account_id:
            raise CloudTrailError(f"{label} 目标账号 ID 必须与写入角色 TRN 中的账号一致")
        if account_id is not None and str(account_id) != source_account_id and not role_trn:
            raise CloudTrailError(
                f"跨账号 {label} 投递必须同时提供 {prefix}WriteRoleTrn；"
                "agent 应先在资源账号准备或解析投递角色与信任策略，再继续创建跟踪"
            )
        if (
            role_account_id is not None
            and role_account_id != source_account_id
            and account_id is None
        ):
            raise CloudTrailError(
                f"跨账号 {label} 投递必须同时提供 {prefix}AccountId；"
                "agent 应先在资源账号准备或解析投递角色与信任策略，再继续创建跟踪"
            )


def validate_event_scope(body: dict[str, Any], *, require_selector: bool) -> None:
    include_all = body.get("IncludeAllEventSources")
    sources = body.get("EventSources")
    if include_all is True and sources:
        raise CloudTrailError("IncludeAllEventSources=true 时不能同时指定 EventSources")
    if require_selector and include_all is False and not sources:
        raise CloudTrailError(
            "IncludeAllEventSources=false 时必须提供至少一个 EventSource"
        )


def validate_sse_config(body: dict[str, Any], source_account_id: str) -> None:
    algorithm = str(body.get("TosSSEAlgorithm") or "")
    key_id = str(body.get("TosSSEKMSKeyID") or "")
    target_account = str(body.get("TosAccountId") or source_account_id)
    if algorithm != "kms" and key_id:
        raise CloudTrailError("仅 TosSSEAlgorithm=kms 时允许提供 TosSSEKMSKeyID")
    if algorithm == "kms":
        if not key_id:
            raise CloudTrailError("TosSSEAlgorithm=kms 时必须提供 KMS key ID")
        validate_kms_key_trn(key_id)
    if target_account != source_account_id and algorithm:
        raise CloudTrailError("跨账号 TOS 投递不支持 SSE 加密")


def trail_body(args: argparse.Namespace, *, create: bool) -> dict[str, Any]:
    body: dict[str, Any] = {"TrailName": args.trail_name}
    if getattr(args, "event_rw", None) is not None:
        body["EventRW"] = args.event_rw
    event_sources = getattr(args, "event_sources", None) or []
    if event_sources:
        body["EventSources"] = event_sources
    for argument, field in TRAIL_FIELDS.items():
        if argument in SPECIAL_TRAIL_ARGUMENTS:
            continue
        value = getattr(args, argument, None)
        if value is not None:
            body[field] = value
    if create:
        include_all = getattr(args, "include_all_event_sources", None)
        body["IncludeAllEventSources"] = include_all if include_all is not None else not event_sources
    elif getattr(args, "include_all_event_sources", None) is not None:
        body["IncludeAllEventSources"] = args.include_all_event_sources
    elif event_sources:
        body["IncludeAllEventSources"] = False
    validate_event_scope(body, require_selector=create)
    if create:
        tos = any(field.startswith("Tos") and field in body for field in TRAIL_FIELDS.values())
        tls = any(field.startswith("Tls") and field in body for field in TRAIL_FIELDS.values())
        if not tos and not tls:
            raise CloudTrailError("CreateTrail 至少需要一个 TOS 或 TLS 投递目标")
        if tos and not {"TosBucketRegion", "TosBucketName"} <= body.keys():
            raise CloudTrailError("TOS 目标必须同时提供 bucket region 和 bucket name")
        if tls and not {"TlsProjectRegion", "TlsProjectName", "TlsTopicName"} <= body.keys():
            raise CloudTrailError("TLS 目标必须同时提供 project region、project name 和 topic name")
    elif len(body) == 1:
        raise CloudTrailError("UpdateTrail 至少需要一个明确的更新字段")
    return body


TOS_UPDATE_FIELDS = tuple(
    spec.api_field for spec in TRAIL_FIELD_SPECS if spec.api_field.startswith("Tos")
)
TLS_UPDATE_FIELDS = tuple(
    spec.api_field for spec in TRAIL_FIELD_SPECS if spec.api_field.startswith("Tls")
)


def complete_update_patch(
    patch: dict[str, Any], current: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an API-safe patch and its final effective state.

    The service ignores TOS-only changes unless region/name is present, and TLS-only
    changes unless region/project/topic is present. Add only the current anchor fields
    required to make an explicitly requested patch effective.
    """
    request = dict(patch)
    effective = dict(current)
    effective.update(patch)
    if any(field in patch for field in TOS_UPDATE_FIELDS):
        for field in ("TosBucketRegion", "TosBucketName"):
            if field not in request and current.get(field) not in (None, ""):
                request[field] = current[field]
        if not request.get("TosBucketRegion") or not request.get("TosBucketName"):
            raise CloudTrailError(
                "更新 TOS 配置时必须提供或保留 TosBucketRegion 与 TosBucketName"
            )
    if any(field in patch for field in TLS_UPDATE_FIELDS):
        for field in ("TlsProjectRegion", "TlsProjectName", "TlsTopicName"):
            if field not in request and current.get(field) not in (None, ""):
                request[field] = current[field]
        if not all(
            request.get(field)
            for field in ("TlsProjectRegion", "TlsProjectName", "TlsTopicName")
        ):
            raise CloudTrailError(
                "更新 TLS 配置时必须提供或保留 region、project name 与 topic name"
            )
    if (
        request.get("IncludeAllEventSources") is False
        and not request.get("EventSources")
        and current.get("EventSources")
    ):
        request["EventSources"] = list(current["EventSources"])
    effective.update(request)
    return request, effective


def cmd_trails_list(args: argparse.Namespace) -> dict[str, Any]:
    identity = auth_context(args)
    trails = describe_trails(args, args.trail_name)
    return {
        "AuthContext": identity,
        "Count": len(trails),
        "Trails": trails,
        "ApiResponse": {"Result": {"Trails": list(trails)}, "ResponseMetadata": api_metadata(trails)},
        **response_metadata_fields(trails),
    }


def cmd_trails_create(args: argparse.Namespace) -> dict[str, Any]:
    body = trail_body(args, create=True)
    identity = auth_context(args)
    source_account_id = identity["AccountId"]
    validate_cross_account_delivery(body, source_account_id)
    validate_sse_config(body, source_account_id)
    if find_trail(args, args.trail_name):
        raise CloudTrailError(f"Trail {args.trail_name!r} 已存在")
    auto_start = not args.no_auto_start
    impact = (
        "创建管理事件 Trail 和投递配置"
        + ("；创建成功并校验后自动 StartLogging" if auto_start else "；本次不自动 StartLogging")
    )
    if body.get("TrailType") == 1:
        impact += "；这是组织级 Trail，将影响组织范围"
    preview = plan(
        "CreateTrail", {"TrailName": args.trail_name}, body, args,
        impact=impact,
        verify="",
        recovery="确认无活跃补投任务后再单独发起删除预案",
        precheck={"TrailAbsent": True, "HasDeliveryTarget": True, "AutoStartLogging": auto_start},
        verified_auth_context=identity,
        explain=True,
        requires_confirmation=True,
    )
    if not args.confirm:
        return preview
    create_result = call_ve("CreateTrail", body, args)
    create_verification = verify_after_write(
        lambda: describe_trails(args, args.trail_name),
        lambda trails: matching_trail(
            trails,
            args.trail_name,
            {
                **{
                    field: value
                    for field, value in body.items()
                    if field not in {"TosBucketProject", "TlsProjectTopicProject"}
                },
            },
        ),
    )
    start_result: ApiResult | None = None
    start_verification: dict[str, Any] | None = None
    if auto_start and create_verification.get("StateVerified"):
        start_result = call_ve("StartLogging", {"TrailName": args.trail_name}, args)
        start_verification = verify_after_write(
            lambda: describe_trails(args, args.trail_name),
            lambda trails: any(
                trail.get("TrailName") == args.trail_name
                and trail.get("LoggingStatus") in ENABLED_LOGGING_STATES
                for trail in trails
            ),
        )
    elif auto_start:
        start_verification = {
            "StateVerified": False,
            "VerificationNote": "CreateTrail 尚未通过只读校验，未自动执行 StartLogging",
        }
    combined_verification: dict[str, Any] = create_verification
    if auto_start:
        combined_verification = {
            "Verification": {
                "CreateTrail": create_verification.get("Verification"),
                "StartLogging": (start_verification or {}).get("Verification"),
            },
            "StateVerified": bool(
                create_verification.get("StateVerified")
                and (start_verification or {}).get("StateVerified")
            ),
        }
        notes = [
            note
            for note in (
                create_verification.get("VerificationNote"),
                (start_verification or {}).get("VerificationNote"),
            )
            if note
        ]
        if notes:
            combined_verification["VerificationNote"] = "；".join(str(note) for note in notes)
    return write_result(
        "CreateTrail",
        create_result,
        combined_verification,
        AutoStartLogging=auto_start,
        AutoStart=(
            None
            if not auto_start
            else {
                "Submitted": start_result is not None,
                "ApiResponse": api_response(start_result) if start_result is not None else None,
                **(response_metadata_fields(start_result) if start_result is not None else {}),
                **(start_verification or {}),
            }
        ),
    )



def cmd_trails_update(args: argparse.Namespace) -> dict[str, Any]:
    patch = trail_body(args, create=False)
    identity = auth_context(args)
    current = require_trail(args, args.trail_name)
    body, effective = complete_update_patch(patch, current)
    source_account_id = identity["AccountId"]
    validate_event_scope(effective, require_selector=True)
    validate_cross_account_delivery(effective, source_account_id)
    validate_sse_config(effective, source_account_id)
    changes = {
        key: {"Before": current.get(key), "After": value}
        for key, value in body.items()
        if key != "TrailName" and not normalized_equal(current.get(key), value)
    }
    organization = current.get("TrailType") == 1 or effective.get("TrailType") == 1
    impact = "更新明确给出的投递字段；未提供字段保持不变"
    if organization:
        impact += "；这是组织级 Trail 更新，将影响组织范围"
    preview = plan(
        "UpdateTrail", {"TrailName": args.trail_name}, body, args,
        impact=impact,
        verify="",
        recovery="根据预案中的 Before 值再次执行 trails update",
        precheck={"Current": current, "Changes": changes, "RequestedPatch": patch},
        verified_auth_context=identity,
        explain=True,
        requires_confirmation=True,
    )
    if not args.confirm:
        return preview
    if not changes:
        return {
            "DryRun": False,
            "WriteAccepted": False,
            "StateVerified": True,
            "Action": "UpdateTrail",
            "NoOp": True,
            "Verification": [current],
        }
    result = call_ve("UpdateTrail", body, args)
    verification = verify_after_write(
        lambda: describe_trails(args, args.trail_name),
        lambda trails: matching_trail(trails, args.trail_name, effective),
    )
    return write_result("UpdateTrail", result, verification)


def logging_change(args: argparse.Namespace, action: str) -> dict[str, Any]:
    identity = auth_context(args)
    current = require_trail(args, args.trail_name)
    stopping = action == "StopLogging"
    preview = plan(
        action, {"TrailName": args.trail_name}, {"TrailName": args.trail_name}, args,
        impact=("关闭审计日志记录和投递能力" if stopping else "提交开启审计日志记录和投递"),
        verify="",
        recovery=(
            "如需重新开启，单独发起开启预案并确认"
            if stopping
            else "如需回滚关闭，单独发起停止预案并确认"
        ),
        precheck={"CurrentTrail": current},
        warning=("高风险：停止后新的审计事件将不再记录或投递" if stopping else None),
        verified_auth_context=identity,
        explain=True,
        requires_confirmation=True,
    )
    if not args.confirm:
        return preview
    already_target = (
        current.get("LoggingStatus") in DISABLED_LOGGING_STATES
        if stopping
        else current.get("LoggingStatus") in ENABLED_LOGGING_STATES
    )
    if already_target:
        return {
            "DryRun": False,
            "WriteAccepted": False,
            "StateVerified": True,
            "Action": action,
            "NoOp": True,
            "Verification": [current],
        }
    result = call_ve(action, {"TrailName": args.trail_name}, args)
    target_states = DISABLED_LOGGING_STATES if stopping else ENABLED_LOGGING_STATES
    verification = verify_after_write(
        lambda: describe_trails(args, args.trail_name),
        lambda trails: any(
            trail.get("TrailName") == args.trail_name
            and trail.get("LoggingStatus") in target_states
            for trail in trails
        ),
    )
    return write_result(action, result, verification)


def list_backfills(args: argparse.Namespace, page_number: int = 1, page_size: int = 100) -> dict[str, Any]:
    eprint("NOTICE: 正在只读查询历史补投任务；已有任务记录可作为账号已开白依据。")
    return call_ve("ListBackfillDeliveryTasks", {"PageNumber": page_number, "PageSize": page_size}, args)


def active_backfills_for_trail(args: argparse.Namespace, trail_name: str) -> list[dict[str, Any]]:
    page_number = 1
    seen = 0
    while page_number <= MAX_BACKFILL_PAGES:
        result = list_backfills(args, page_number, 100)
        if "Tasks" not in result or "Total" not in result:
            raise CloudTrailError("补投任务分页响应缺少 Tasks 或 Total")
        page_tasks = result["Tasks"]
        if not isinstance(page_tasks, list):
            raise CloudTrailError("补投任务分页响应中的 Tasks 必须是列表")
        try:
            total = int(result["Total"])
        except (TypeError, ValueError) as exc:
            raise CloudTrailError("补投任务分页响应中的 Total 无效") from exc
        if total < 0:
            raise CloudTrailError("补投任务分页响应中的 Total 不一致")
        active = [
            task
            for task in page_tasks
            if isinstance(task, dict)
            and task.get("TrailName") == trail_name
            and task.get("TaskStatus") in ACTIVE_TASK_STATES
        ]
        if active:
            return active
        seen += len(page_tasks)
        if seen > total:
            raise CloudTrailError("补投任务分页响应中的 Tasks 数量超过 Total")
        if seen >= total:
            return []
        if not page_tasks:
            raise CloudTrailError("补投任务分页尚未完成但服务端返回空页")
        page_number += 1
    raise CloudTrailError("补投任务分页超过安全页数，拒绝继续")


def active_backfill_any(args: argparse.Namespace) -> list[dict[str, Any]]:
    page_number = 1
    seen = 0
    while page_number <= MAX_BACKFILL_PAGES:
        result = list_backfills(args, page_number, 100)
        tasks = result.get("Tasks")
        if not isinstance(tasks, list) or "Total" not in result:
            raise CloudTrailError("补投任务分页响应不完整")
        try:
            total = int(result["Total"])
        except (TypeError, ValueError) as exc:
            raise CloudTrailError("补投任务分页响应中的 Total 无效") from exc
        if total < 0:
            raise CloudTrailError("补投任务分页响应中的 Total 不一致")
        active = [
            task
            for task in tasks
            if isinstance(task, dict) and task.get("TaskStatus") in ACTIVE_TASK_STATES
        ]
        if active:
            return active
        seen += len(tasks)
        if seen > total:
            raise CloudTrailError("补投任务分页响应中的 Tasks 数量超过 Total")
        if seen >= total:
            return []
        if not tasks:
            raise CloudTrailError("补投任务分页尚未完成但服务端返回空页")
        page_number += 1
    raise CloudTrailError("补投任务分页超过安全页数，拒绝继续")


def cmd_trails_delete(args: argparse.Namespace) -> dict[str, Any]:
    identity = auth_context(args)
    current = require_trail(args, args.trail_name)
    try:
        active = active_backfills_for_trail(args, args.trail_name)
    except CloudTrailError as exc:
        raise CloudTrailError(f"补投任务预检失败，拒绝删除 Trail：{exc}") from exc
    if active:
        raise CloudTrailError("存在 PENDING/RUNNING 补投任务；请先单独确认并停止任务，再删除 Trail")
    body = {"TrailName": args.trail_name}
    impact = "永久删除 Trail 控制面配置；删除流程不会自动停止任何补投任务"
    if current.get("TrailType") == 1:
        impact += "；这是组织级 Trail 删除，将影响组织范围"
    preview = plan(
        "DeleteTrail", {"TrailName": args.trail_name}, body, args,
        impact=impact,
        verify="",
        recovery="按已保存的当前配置重新创建 Trail，并单独确认是否开启",
        precheck={"CurrentTrail": current, "ActiveBackfillTasks": []},
        verified_auth_context=identity,
        explain=True,
        requires_confirmation=True,
    )
    if not args.confirm:
        return preview
    result = call_ve("DeleteTrail", body, args)
    verification = verify_after_write(
        lambda: describe_trails(args, args.trail_name),
        lambda trails: not matching_trail(trails, args.trail_name),
    )
    return write_result("DeleteTrail", result, verification)


def cmd_backfill_list(args: argparse.Namespace) -> dict[str, Any]:
    identity = auth_context(args)
    result = list_backfills(args, args.page_number, args.page_size)
    return {
        "WhitelistNotice": "历史补投能力需要联系运营开白",
        "AuthContext": identity,
        "ApiResponse": api_response(result),
        **result,
        **response_metadata_fields(result),
    }


def describe_backfill(args: argparse.Namespace, task_id: str) -> dict[str, Any]:
    eprint("NOTICE: 正在只读查询历史补投任务详情。")
    return call_ve("DescribeBackfillDeliveryTask", {"TaskID": task_id}, args)


def cmd_backfill_describe(args: argparse.Namespace) -> dict[str, Any]:
    identity = auth_context(args)
    task = describe_backfill(args, args.task_id)
    return {
        "WhitelistNotice": "历史补投能力需要联系运营开白",
        "AuthContext": identity,
        "Task": task,
        "ApiResponse": api_response(task),
        **response_metadata_fields(task),
    }


def infer_whitelist_from_existing_backfill(args: argparse.Namespace) -> dict[str, Any] | None:
    try:
        result = list_backfills(args, 1, 100)
    except CloudTrailError:
        return None
    tasks = result.get("Tasks")
    if not isinstance(tasks, list):
        return None
    try:
        total = int(result.get("Total", len(tasks)))
    except (TypeError, ValueError):
        total = len(tasks)
    if total <= 0 and not tasks:
        return None
    return {
        "WhitelistConfirmed": True,
        "ConfirmationSource": "existing-backfill-task",
        "ExistingBackfillTaskCount": max(total, len(tasks)),
        "SampleTaskIDs": [
            str(task.get("TaskID"))
            for task in tasks[:3]
            if isinstance(task, dict) and task.get("TaskID")
        ],
    }


def require_whitelist(args: argparse.Namespace, action: str, target: dict[str, Any], body: dict[str, Any]) -> dict[str, Any] | None:
    if args.whitelist_confirmed:
        args.whitelist_evidence = {"WhitelistConfirmed": True, "ConfirmationSource": "user-confirmed"}
        return None
    evidence = infer_whitelist_from_existing_backfill(args)
    if evidence is not None:
        args.whitelist_evidence = evidence
        return None
    if args.confirm:
        raise CloudTrailError("补投写操作前需要确认账号已完成运营开白，或账号内已有历史补投任务记录")
    return plan(
        action, target, body, args,
        impact="历史补投写操作；当前账号未发现历史补投任务记录，需确认账号已完成运营开白",
        verify="确认开白后重新运行当前命令并添加 --whitelist-confirmed",
        recovery="无；尚未执行写操作",
        precheck={"WhitelistConfirmed": False},
        warning="请先联系运营完成历史补投能力开白",
        verify_identity=False,
        explain=True,
        requires_confirmation=False,
    )


def backfill_time_body(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    now_epoch = int(now.timestamp())
    start = parse_requested_time(
        args.start_time,
        "StartTime",
        "backfill create --start-time <rfc3339> --end-time <rfc3339>",
    )
    end = parse_requested_time(
        args.end_time,
        "EndTime",
        "backfill create --start-time <rfc3339> --end-time <rfc3339>",
    )
    if end <= start:
        raise CloudTrailError(
            "EndTime 必须晚于 StartTime",
            code="BackfillWindowEmpty" if end == start else "BackfillWindowReversed",
            context={
                "Reason": "empty-window" if end == start else "reversed-window",
                "RequestedStartTime": start,
                "RequestedEndTime": end,
                "AllowedRange": {"MinimumSeconds": 1, "MaximumDays": 90},
                "SuggestedCommand": "backfill create --start-time <recent-start> --end-time <recent-end>",
            },
        )
    if end >= now_epoch:
        raise CloudTrailError(
            "EndTime 必须早于当前时间",
            code="BackfillEndNotPast",
            context={
                "Reason": "end-not-before-now",
                "RequestedEndTime": end,
                "CurrentTime": now_epoch,
                "AllowedRange": {"LatestEndTimeExclusive": now_epoch},
                "SuggestedCommand": "backfill create --start-time <recent-start> --end-time <past-end>",
            },
        )
    earliest = now_epoch - int(MAX_LOOKBACK.total_seconds())
    if start < earliest:
        drift = earliest - start
        if 0 < drift <= WINDOW_BOUNDARY_TOLERANCE_SECONDS:
            start = earliest + WINDOW_BOUNDARY_SAFETY_MARGIN_SECONDS
        else:
            raise CloudTrailError(
                "StartTime 不得早于当前时间往前 90 天",
                code="BackfillStartBeforeRetention",
                context={
                    "Reason": "before-retention",
                    "RequestedStartTime": start,
                    "EarliestAllowedStartTime": earliest,
                    "AllowedRange": {"EarliestStartTime": earliest, "LatestEndTimeExclusive": now_epoch},
                    "SuggestedCommand": "backfill create --start-time <within-last-90-days> --end-time <past-end>",
                },
            )
    if end - start > int(MAX_LOOKBACK.total_seconds()):
        overflow = end - start - int(MAX_LOOKBACK.total_seconds())
        if 0 < overflow <= WINDOW_BOUNDARY_TOLERANCE_SECONDS:
            start = end - int(MAX_LOOKBACK.total_seconds()) + WINDOW_BOUNDARY_SAFETY_MARGIN_SECONDS
        else:
            raise CloudTrailError(
                "单个补投任务的时间跨度不得超过 90 天",
                code="BackfillWindowTooLarge",
                context={
                    "Reason": "window-too-large",
                    "RequestedWindowSeconds": end - start,
                    "AllowedRange": {"MaximumDays": 90},
                    "SuggestedCommand": "backfill create --start-time <within-last-90-days> --end-time <past-end>",
                },
            )
    if not args.enable_tos and not args.enable_tls:
        raise CloudTrailError("EnableTOS 与 EnableTLS 至少一项为 true")
    return {
        "TrailName": args.trail_name,
        "StartTime": start,
        "EndTime": end,
        "EnableTOS": bool(args.enable_tos),
        "EnableTLS": bool(args.enable_tls),
    }


def management_trail(trail: dict[str, Any]) -> bool:
    return trail.get("IncludeAllEventSources") is True or bool(trail.get("EventSources"))


def backfill_matches_request(
    task: dict[str, Any], body: dict[str, Any]
) -> bool:
    if task.get("TrailName") != body.get("TrailName"):
        return False
    try:
        start = parse_backfill_task_time(task.get("StartTime"))
        end = parse_backfill_task_time(task.get("EndTime"))
    except (argparse.ArgumentTypeError, ValueError):
        return False
    if start != body.get("StartTime") or end != body.get("EndTime"):
        return False
    tos_enabled = bool((task.get("TosConfig") or {}).get("Enabled"))
    tls_enabled = bool((task.get("TlsConfig") or {}).get("Enabled"))
    return tos_enabled == body.get("EnableTOS") and tls_enabled == body.get("EnableTLS")


def parse_backfill_task_time(value: Any) -> int:
    text = str(value or "")
    if re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", text):
        return int(datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp())
    return parse_time(text)


def find_matching_backfill(
    args: argparse.Namespace, body: dict[str, Any]
) -> dict[str, Any] | None:
    page_number = 1
    seen = 0
    while page_number <= MAX_BACKFILL_PAGES:
        result = list_backfills(args, page_number, 100)
        tasks = result.get("Tasks")
        if not isinstance(tasks, list) or "Total" not in result:
            raise CloudTrailError("补投任务核对响应不完整")
        try:
            total = int(result["Total"])
        except (TypeError, ValueError) as exc:
            raise CloudTrailError("补投任务核对中的 Total 无效") from exc
        if total < 0:
            raise CloudTrailError("补投任务核对中的 Total 不一致")
        for task in tasks:
            if isinstance(task, dict) and backfill_matches_request(task, body):
                return task
        seen += len(tasks)
        if seen > total:
            raise CloudTrailError("补投任务核对中的 Tasks 数量超过 Total")
        if seen >= total:
            return None
        if not tasks:
            raise CloudTrailError("补投任务核对尚未完成但服务端返回空页")
        page_number += 1
    raise CloudTrailError("补投任务核对超过安全页数")


def cmd_backfill_create(args: argparse.Namespace) -> dict[str, Any]:
    body = backfill_time_body(args)
    blocked = require_whitelist(args, "CreateBackfillDeliveryTask", {"TrailName": args.trail_name}, body)
    if blocked:
        return blocked
    whitelist_evidence = getattr(args, "whitelist_evidence", {"WhitelistConfirmed": True})
    identity = auth_context(args)
    trail = require_trail(args, args.trail_name)
    if trail.get("LoggingStatus") not in {"Enable", "Enabled"}:
        raise CloudTrailError("目标 Trail 未启用，不能创建补投任务")
    if not management_trail(trail):
        raise CloudTrailError("目标 Trail 不符合历史补投要求")
    if args.enable_tos and not (trail.get("TosBucketRegion") and trail.get("TosBucketName")):
        raise CloudTrailError("目标 Trail 未配置可见的 TOS 投递目标")
    if args.enable_tls and not (
        trail.get("TlsProjectRegion")
        and trail.get("TlsProjectName")
        and trail.get("TlsTopicName")
    ):
        raise CloudTrailError("目标 Trail 未配置可见的 TLS 投递目标")
    try:
        active_tasks = active_backfill_any(args)
    except CloudTrailError as exc:
        raise CloudTrailError(f"补投任务预检失败，拒绝创建：{exc}") from exc
    if active_tasks:
        raise CloudTrailError("当前账号已有 PENDING/RUNNING 补投任务；一个账号同时只允许一个运行中任务")
    preview = plan(
        "CreateBackfillDeliveryTask", {"TrailName": args.trail_name}, body, args,
        impact="创建指定历史窗口的管理事件补投任务并写入所选投递目标",
        verify="",
        recovery="若任务仍为 PENDING/RUNNING，单独确认后执行 backfill stop",
        precheck={
            **whitelist_evidence,
            "Trail": trail,
            "WindowSeconds": body["EndTime"] - body["StartTime"],
            "ActiveBackfillTasks": [],
        },
        verified_auth_context=identity,
        explain=True,
        requires_confirmation=True,
    )
    if not args.confirm:
        return preview
    availability = action_availability("CreateBackfillDeliveryTask", args)
    if availability is ActionAvailability.ERROR:
        raise CloudTrailError(
            "无法确认 CreateBackfillDeliveryTask 的 CLI 可用状态，已阻断创建"
        )
    force = availability is ActionAvailability.UNREGISTERED
    try:
        result = call_ve("CreateBackfillDeliveryTask", body, args, force=force)
    except CloudTrailError as exc:
        matched = find_matching_backfill(args, body)
        if matched is None:
            raise CloudTrailError(
                f"补投创建结果不确定，且未发现匹配任务：{exc}；不要直接重试创建",
                code="BackfillCreateUncertain",
            ) from exc
        result = ApiResult(
            {"TaskID": matched.get("TaskID"), "RecoveredFromUncertainResult": True}
        )
    task_id = result.get("TaskID")
    verification = (
        verify_after_write(
            lambda: describe_backfill(args, task_id),
            lambda task: isinstance(task, dict)
            and task.get("TaskID") == task_id
            and task.get("TaskStatus") in TASK_STATES,
        )
        if task_id
        else (
            {
                "Verification": matched,
                "StateVerified": True,
                "VerificationNote": "响应未包含 TaskID；通过全页核对找到精确匹配任务",
            }
            if (matched := find_matching_backfill(args, body)) is not None
            else {
                "Verification": None,
                "StateVerified": False,
                "VerificationNote": "响应未包含 TaskID，且全页核对未找到匹配任务；不要重试创建",
            }
        )
    )
    return write_result(
        "CreateBackfillDeliveryTask",
        result,
        verification,
        UsedForceFallback=force,
    )


def cmd_backfill_stop(args: argparse.Namespace) -> dict[str, Any]:
    body = {"TaskID": args.task_id}
    blocked = require_whitelist(args, "StopBackfillDeliveryTask", {"TaskID": args.task_id}, body)
    if blocked:
        return blocked
    whitelist_evidence = getattr(args, "whitelist_evidence", {"WhitelistConfirmed": True})
    identity = auth_context(args)
    task = describe_backfill(args, args.task_id)
    if task.get("TaskStatus") not in ACTIVE_TASK_STATES:
        raise CloudTrailError("只允许停止 PENDING 或 RUNNING 状态的补投任务")
    preview = plan(
        "StopBackfillDeliveryTask", {"TaskID": args.task_id}, body, args,
        impact="停止正在等待或运行的历史补投任务；已投递数据不会回滚",
        verify="",
        recovery="不能恢复原任务；如仍需补投，重新创建边界明确的新任务",
        precheck={**whitelist_evidence, "CurrentTask": task},
        verified_auth_context=identity,
        explain=True,
        requires_confirmation=True,
    )
    if not args.confirm:
        return preview
    result = call_ve("StopBackfillDeliveryTask", body, args)
    verification = verify_after_write(
        lambda: describe_backfill(args, args.task_id),
        lambda task: isinstance(task, dict)
        and task.get("TaskID") == args.task_id
        and task.get("TaskStatus") in TERMINAL_TASK_STATES,
    )
    return write_result("StopBackfillDeliveryTask", result, verification)


def add_trail_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--trail-name", required=True)
    parser.add_argument("--trail-type", type=int, choices=(0, 1))
    parser.add_argument(
        "--event-source",
        dest="event_sources",
        action="append",
        default=[],
        help="管理事件源；可重复。未指定时创建默认覆盖全部事件源",
    )
    add_bool_argument(
        parser,
        "--include-all-event-sources",
        help="是否覆盖全部管理事件源；指定 --event-source 时默认 false，否则创建默认 true",
    )
    parser.add_argument("--tos-account-id")
    parser.add_argument("--tos-write-role-trn")
    parser.add_argument("--tos-bucket-region")
    parser.add_argument("--tos-bucket-name")
    parser.add_argument("--tos-key-prefix")
    parser.add_argument("--tos-bucket-project")
    parser.add_argument("--tos-sse-algorithm", choices=("", "AES256", "kms"))
    parser.add_argument("--tos-sse-kms-key-id")
    parser.add_argument("--tls-account-id")
    parser.add_argument("--tls-write-role-trn")
    parser.add_argument("--tls-project-region")
    parser.add_argument("--tls-project-name")
    parser.add_argument("--tls-topic-name")
    parser.add_argument("--tls-project-topic-project")
    parser.add_argument("--confirm", action="store_true", help="执行写操作；缺省只预览")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="仅在用户明确指定时传入")
    parser.add_argument("--region", help="仅在用户明确指定时传入")
    parser.add_argument("--format", choices=("json", "md", "table"), default="json")
    groups = parser.add_subparsers(dest="group", required=True)

    events = groups.add_parser("events")
    event_commands = events.add_subparsers(dest="event_command", required=True)
    lookup = event_commands.add_parser("lookup")
    lookup.add_argument("--signin-action", choices=("login", "logout", "other"))
    lookup.add_argument("--operation", choices=("read", "write", "any"), default="any")
    lookup.add_argument("--resource-id")
    lookup.add_argument("--iam-user-name")
    lookup.add_argument("--event-source")
    lookup.add_argument("--event-name")
    lookup.add_argument("--condition", action="append", default=[])
    lookup.add_argument("--start-time")
    lookup.add_argument("--end-time")
    lookup.add_argument("--lookback-days")
    lookup.add_argument("--max-results", type=int, default=10)
    lookup.add_argument("--all", action="store_true", help="有界全量：只取首个 50 条响应")
    lookup.add_argument("--raw", action="store_true", help="输出原始审计事件，并为每个字段附含义")
    lookup.add_argument("--next-token", help="显式查询下一页；不会自动翻页")
    lookup.add_argument(
        "--query-fingerprint", help="续页时原样传回上一页输出的 QueryFingerprint"
    )
    lookup.set_defaults(handler=cmd_events_lookup)

    resolve = event_commands.add_parser("resolve")
    resolve.add_argument("--service")
    resolve.add_argument("--keyword")
    resolve.add_argument("--action")
    resolve.add_argument("--doc-search")
    resolve.add_argument("--doc-limit", type=positive_int, default=5)
    resolve.add_argument("--resource-id")
    resolve.add_argument("--operation", choices=("read", "write", "any"), default="any")
    resolve.set_defaults(handler=cmd_events_resolve)

    trails = groups.add_parser("trails")
    trail_commands = trails.add_subparsers(dest="trail_command", required=True)
    trail_list = trail_commands.add_parser("list")
    trail_list.add_argument("--trail-name")
    trail_list.add_argument("--include-organization-trail", action="store_true")
    trail_list.set_defaults(handler=cmd_trails_list)
    trail_create = trail_commands.add_parser("create")
    add_trail_fields(trail_create)
    trail_create.add_argument("--event-rw", choices=("All", "Read", "Write"), required=True)
    trail_create.add_argument(
        "--no-auto-start",
        action="store_true",
        help="兼容参数，已无效果；创建始终不会隐式 StartLogging",
    )
    trail_create.set_defaults(handler=cmd_trails_create)
    trail_update = trail_commands.add_parser("update")
    add_trail_fields(trail_update)
    trail_update.add_argument("--event-rw", choices=("All", "Read", "Write"))
    trail_update.set_defaults(handler=cmd_trails_update)
    for name, handler in (("start", lambda a: logging_change(a, "StartLogging")), ("stop", lambda a: logging_change(a, "StopLogging")), ("delete", cmd_trails_delete)):
        sub = trail_commands.add_parser(name)
        sub.add_argument("--trail-name", required=True)
        sub.add_argument("--confirm", action="store_true")
        sub.set_defaults(handler=handler)

    backfill = groups.add_parser("backfill")
    backfill_commands = backfill.add_subparsers(dest="backfill_command", required=True)
    backfill_list = backfill_commands.add_parser("list")
    backfill_list.add_argument("--page-number", type=positive_int, default=1)
    backfill_list.add_argument("--page-size", type=int, choices=range(1, 101), default=10)
    backfill_list.set_defaults(handler=cmd_backfill_list)
    backfill_describe = backfill_commands.add_parser("describe")
    backfill_describe.add_argument("--task-id", required=True)
    backfill_describe.set_defaults(handler=cmd_backfill_describe)
    backfill_create = backfill_commands.add_parser("create")
    backfill_create.add_argument("--trail-name", required=True)
    backfill_create.add_argument("--start-time", required=True)
    backfill_create.add_argument("--end-time", required=True)
    backfill_create.add_argument("--enable-tos", action="store_true")
    backfill_create.add_argument("--enable-tls", action="store_true")
    backfill_create.add_argument("--whitelist-confirmed", action="store_true")
    backfill_create.add_argument("--confirm", action="store_true")
    backfill_create.set_defaults(handler=cmd_backfill_create)
    backfill_stop = backfill_commands.add_parser("stop")
    backfill_stop.add_argument("--task-id", required=True)
    backfill_stop.add_argument("--whitelist-confirmed", action="store_true")
    backfill_stop.add_argument("--confirm", action="store_true")
    backfill_stop.set_defaults(handler=cmd_backfill_stop)
    return parser


def render(value: Any, output_format: str) -> str:
    if isinstance(value, dict) and value.get("RawEventOutput") and value.get("AnnotatedEventLogs"):
        annotated = value["AnnotatedEventLogs"]
        if isinstance(annotated, list):
            return "\n\n".join(str(item) for item in annotated)
        return str(annotated)
    if isinstance(value, dict) and value.get("DryRun") and value.get("UserFacingSummary"):
        user_preview = {
            "操作摘要": value.get("操作摘要", []),
            "特殊提醒": value.get("特殊提醒", ["无"]),
            "下一步动作": value.get("下一步动作", "回复「确认执行」继续。"),
        }
        if output_format == "json":
            return json.dumps(user_preview, ensure_ascii=False, indent=2, sort_keys=False)
        if output_format == "md":
            return (
                "## 操作摘要\n"
                + "\n".join(f"- {item}" for item in user_preview["操作摘要"])
                + "\n\n## 特殊提醒\n"
                + "\n".join(f"- {item}" for item in user_preview["特殊提醒"])
                + "\n\n## 下一步动作\n"
                + str(user_preview["下一步动作"])
            )
        return "\n".join(
            [
                "操作摘要：",
                *[f"- {item}" for item in user_preview["操作摘要"]],
                "特殊提醒：",
                *[f"- {item}" for item in user_preview["特殊提醒"]],
                "下一步动作：",
                str(user_preview["下一步动作"]),
            ]
        )
    safe = value
    if output_format == "json":
        return json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True)
    if not isinstance(safe, dict):
        return str(safe)
    rows = [(key, json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)) for key, item in safe.items()]
    if output_format == "md":
        escaped_rows = [(key, item.replace("|", "\\|")) for key, item in rows]
        return "| Field | Value |\n| --- | --- |\n" + "\n".join(
            f"| {key} | {item} |" for key, item in escaped_rows
        )
    width = max(len(key) for key, _ in rows) if rows else 5
    return "\n".join(f"{key:<{width}}  {value}" for key, value in rows)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        print(render(result, args.format))
        if result.get("WriteAccepted") and result.get("StateVerified") is False:
            return 3
        return 0
    except (CloudTrailError, ValueError) as exc:
        eprint(f"ERROR: {exc}")
        code = getattr(exc, "code", None)
        context = getattr(exc, "context", {})
        if code or context:
            eprint(
                json.dumps(
                    {"Code": code, "Retryable": False, **context},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
