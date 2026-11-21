#!/usr/bin/env python3
"""Unified CLI facade for the volcengine-cost skill."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import subprocess
import sys
from typing import Sequence

from cost_query.common.errors import BillingQueryError, ErrorCode, ExitCode
from cost_query.common.execution_output import error_envelope
from cost_query.common.json_output import dumps as json_dumps
from cost_query.utils.arguments import BillingArgumentParser as Parser
from cost_query.utils.redaction import redact_text


MIN_PYTHON_VERSION = (3, 10)

DELEGATED_COMMANDS = {
    "query": (
        "query_billing",
        "执行只读 Billing 查询，输出 JSON 执行清单、CSV、metadata 和字段目录。",
    ),
    "reconcile": (
        "reconcile_cost",
        "对两份账单查询产物做金额一致性检查、差异定位和守恒式下钻。",
    ),
    "resource-package": (
        "attribute_resource_packages",
        "基于已查询的库存、抵扣和账单明细生成资源包欠费原因证据；describe 查看输入与边界。",
    ),
    "coupon": (
        "attribute_coupons",
        "组合代金券库存、核销记录和账单明细生成代金券抵扣证据；describe 查看边界。",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(
        prog="cost.py",
        description="火山引擎费用查询、字段契约和账务对账的统一入口。",
        epilog=(
            "常用路径：复用已确认的 Action 和字段口径，缺少执行依据时再用 schema；"
            "用 query 拉取账单数据；"
            "需要跨账单来源核对金额时用 reconcile；查询后按分析原则处理数据；"
            "资源包原因使用 resource-package；"
            "代金券原因使用 coupon；"
            "怀疑本地依赖问题时用 check；身份是否可用以实际只读接口结果为准。"
        ),
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema = subparsers.add_parser(
        "schema",
        help="选择 Billing Action、查看请求/响应字段、枚举、粒度规则、字段级决策和费用规则 helper。",
        allow_abbrev=False,
    )
    schema.add_argument("--action", help="Billing Action，例如 ListBillDetail。")
    schema.add_argument(
        "--list-actions",
        action="store_true",
        help="列出允许的 Billing Action 及选用/避用建议。",
    )
    schema.add_argument(
        "--section",
        choices=("request", "response", "both", "cost_rules"),
        default=None,
        help="输出 request、response、两者，或费用分析可复用规则 helper；默认 both。",
    )
    schema.add_argument(
        "--field",
        action="append",
        default=[],
        help=(
            "只输出指定请求/响应字段；多个字段用逗号分隔，也可重复传入；"
            "cost_rules section 下可指定公开函数或类型。"
        ),
    )
    schema.add_argument(
        "--include-guidance",
        action="store_true",
        help="附加 Action 级业务约束、预聚合和字段粒度指引；默认只返回结构契约和字段级决策。",
    )
    # Keep the hidden flag for callers of older versions; JSON is compact by default.
    schema.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)

    for command, (_, help_text) in DELEGATED_COMMANDS.items():
        subparsers.add_parser(command, help=help_text, allow_abbrev=False)

    check = subparsers.add_parser(
        "check",
        help="检查本地只读查询工具的最低运行条件。",
        allow_abbrev=False,
    )
    check.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    return parser


def _check() -> dict[str, object]:
    checks: list[dict[str, object]] = []

    python_ok = sys.version_info >= (*MIN_PYTHON_VERSION, 0)
    checks.append(
        {
            "name": "python",
            "status": "pass" if python_ok else "fail",
            "required": ">=3.10",
            "version": sys.version.split()[0],
            "executable": sys.executable,
            **({} if python_ok else {"message": "Python 版本低于 SKILL.md 声明的最低要求"}),
        }
    )

    command_modules_check = _check_command_modules()
    checks.append(command_modules_check)

    ve_path = shutil.which("ve")
    ve_check = _check_ve_cli(ve_path)
    checks.append(ve_check)

    credential_check = {
        "name": "credentials",
        "status": "skip",
        "verified": False,
        "message": "check 仅检查本地依赖；当前身份以实际只读接口或 STS GetCallerIdentity 的结果为准",
    }
    checks.append(credential_check)

    status = _overall_status(checks)
    return {
        "status": status,
        "commands": ["schema", *DELEGATED_COMMANDS, "check"],
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "required": ">=3.10",
        },
        "dependencies": {
            "python": checks[0],
            "command_modules": command_modules_check,
            "ve_cli": ve_check,
            "credentials": credential_check,
        },
        "checks": checks,
        "ve_cli": {
            "available": ve_path is not None,
            "path": ve_path,
            **({"version": ve_check["version"]} if "version" in ve_check else {}),
            "required_for": ["cost.py query without --fixture-dir"],
        },
    }


def _overall_status(checks: Sequence[dict[str, object]]) -> str:
    statuses = [str(check.get("status")) for check in checks]
    if "fail" in statuses:
        return "failed"
    # Skipped checks (such as credentials) are outside this dependency check's scope.
    if "warn" in statuses:
        return "degraded"
    return "ok"


def _check_command_modules() -> dict[str, object]:
    modules = ("describe_billing_api", *(module for module, _ in DELEGATED_COMMANDS.values()))
    failures = []
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError as exc:
            failures.append({"module": module, "missing": getattr(exc, "name", None) or str(exc)})
    if failures:
        return {
            "name": "command_modules",
            "status": "fail",
            "modules": list(modules),
            "failures": failures,
            "message": "部分 cost.py 子命令模块无法导入",
        }
    return {
        "name": "command_modules",
        "status": "pass",
        "modules": list(modules),
    }


def _check_ve_cli(ve_path: str | None) -> dict[str, object]:
    if not ve_path:
        return {
            "name": "ve_cli",
            "status": "warn",
            "required_for": ["cost.py query without --fixture-dir"],
            "message": "ve 不在 PATH 中；schema、本地分析和 fixture 查询仍可用，真实 Billing 查询不可用",
        }
    try:
        completed = subprocess.run(
            [ve_path, "version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "name": "ve_cli",
            "status": "warn",
            "path": ve_path,
            "required_for": ["cost.py query without --fixture-dir"],
            "message": f"ve 已发现但无法执行 version：{_safe_text(str(exc))}",
        }
    version_match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", completed.stdout)
    version = version_match.group(0) if version_match else None
    status = "pass" if completed.returncode == 0 and not completed.stderr.strip() else "warn"
    if not version_match:
        status = "warn"
    return {
        "name": "ve_cli",
        "status": status,
        "path": ve_path,
        **({"version": version} if version else {}),
        "required_for": ["cost.py query without --fixture-dir"],
        **({"returncode": completed.returncode} if completed.returncode != 0 else {}),
        **({"stderr": _safe_text(completed.stderr)} if completed.stderr.strip() else {}),
    }


def _safe_text(value: str, limit: int = 500) -> str:
    return " ".join(redact_text(value).strip().split())[:limit]


def _dependency_error(exc: ImportError) -> BillingQueryError:
    missing = getattr(exc, "name", None) or str(exc)
    return BillingQueryError(
        ErrorCode.ACTION_FAILED,
        f"缺少运行依赖：{missing}；请先运行 cost.py check 查看环境状态",
        ExitCode.DEPENDENCY_ERROR,
        {"missing": missing},
    )


def _list_actions() -> dict[str, object]:
    try:
        import describe_billing_api
    except ImportError as exc:
        raise _dependency_error(exc) from exc
    payload = describe_billing_api.list_actions()
    payload.pop("contract_schema_version", None)
    payload.pop("schema_version", None)
    payload.pop("tool", None)
    payload.pop("tool_version", None)
    payload.pop("command", None)
    payload.pop("api_version", None)
    payload.pop("service_code", None)
    payload["usage"] = (
        "仅在无法确定 Action 时，根据 purpose/data_grain/result_kind/use_when/avoid_when/important_limits "
        "从本目录选择 Action；选定后若没有适用的请求契约，使用 "
        "cost.py schema --action <Action> --section request --include-guidance 一次加载请求规则和业务指引。"
    )
    return payload


def _cost_rules_schema(field_queries: Sequence[str]) -> dict[str, object]:
    from cost_query.common.cost_rules_contract import schema_contract

    return schema_contract(field_queries)


def _expand_field_queries(values: Sequence[str]) -> list[str]:
    fields: list[str] = []
    for value in values:
        for field in value.split(","):
            normalized = field.strip()
            if not normalized:
                raise BillingQueryError(
                    ErrorCode.INVALID_ARGUMENT,
                    "--field 中的字段名不能为空",
                    ExitCode.INVALID_ARGUMENT,
                )
            if normalized not in fields:
                fields.append(normalized)
    return fields


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    try:
        command = arguments[0] if arguments else None
        if command in DELEGATED_COMMANDS:
            module_name, _ = DELEGATED_COMMANDS[command]
            try:
                module = importlib.import_module(module_name)
            except ImportError as exc:
                raise _dependency_error(exc) from exc
            return module.main(arguments[1:], prog=f"cost.py {command}")
        args = build_parser().parse_args(arguments)
        if args.command == "check":
            payload = _check()
            print(json_dumps(payload))
            return (
                int(ExitCode.DEPENDENCY_ERROR)
                if payload["status"] == "failed"
                else int(ExitCode.SUCCESS)
            )
        if args.command == "schema":
            field_queries = _expand_field_queries(args.field)
            if args.section == "cost_rules":
                if args.action or args.list_actions:
                    raise BillingQueryError(
                        ErrorCode.INVALID_ARGUMENT,
                        "schema --section cost_rules 不需要 --action 或 --list-actions",
                        ExitCode.INVALID_ARGUMENT,
                    )
                payload = _cost_rules_schema(field_queries)
            elif args.list_actions:
                conflicts = [
                    option
                    for option, supplied in (
                        ("--action", args.action is not None),
                        ("--section", args.section is not None),
                        ("--field", bool(field_queries)),
                        ("--include-guidance", args.include_guidance),
                    )
                    if supplied
                ]
                if conflicts:
                    raise BillingQueryError(
                        ErrorCode.INVALID_ARGUMENT,
                        f"schema --list-actions 不能与 {', '.join(conflicts)} 同时使用",
                        ExitCode.INVALID_ARGUMENT,
                    )
                payload = _list_actions()
            else:
                if not args.action:
                    raise BillingQueryError(
                        ErrorCode.INVALID_ARGUMENT,
                        "schema 必须指定 --action，或使用 --list-actions",
                        ExitCode.INVALID_ARGUMENT,
                    )
                try:
                    from cost_query.billing.json_schema import schema_contract
                except ImportError as exc:
                    raise _dependency_error(exc) from exc
                payload = schema_contract(
                    args.action,
                    section=args.section or "both",
                    field_queries=field_queries,
                    include_guidance=args.include_guidance,
                )
            print(json_dumps(payload))
            return int(ExitCode.SUCCESS)
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            f"未知命令：{args.command}",
            ExitCode.INVALID_ARGUMENT,
        )
    except BillingQueryError as exc:
        print(json_dumps(error_envelope(exc)))
        return int(exc.exit_code)
    except ValueError as exc:
        error = BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            str(exc),
            ExitCode.INVALID_ARGUMENT,
        )
        print(json_dumps(error_envelope(error)))
        return int(error.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
