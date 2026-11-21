#!/usr/bin/env python3
"""对 Billing CSV 进行可比性检查、双侧聚合对账和守恒式下钻。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from cost_query.common.errors import BillingQueryError, ErrorCode, ExitCode
from cost_query.common.execution_output import build_envelope, error_envelope
from cost_query.common.json_output import dumps as json_dumps
from cost_query.reconciliation.contract import CONTRACT_SECTIONS, describe_reconciliation
from cost_query.reconciliation.engine import (
    FilterItem,
    DrillDownRequest,
    ReconcileRequest,
    drill_down,
    normalize_filter_operator,
    preflight,
    run_reconciliation,
)
from cost_query.utils.arguments import BillingArgumentParser as Parser


def _base_reconcile_parser(prog: str, description: str) -> Parser:
    parser = Parser(prog=prog, description=description, allow_abbrev=False)
    left = parser.add_mutually_exclusive_group(required=True)
    left.add_argument("--left", help="左侧 CSV；正式对账要求 cost.py query 产物。")
    left.add_argument("--left-result", help="左侧 cost.py query 返回的文件型 result JSON object。")
    right = parser.add_mutually_exclusive_group(required=True)
    right.add_argument("--right", help="右侧 CSV；正式对账要求 cost.py query 产物。")
    right.add_argument("--right-result", help="右侧 cost.py query 返回的文件型 result JSON object。")
    parser.add_argument("--left-metadata", help="左侧 metadata；默认查找同名 .meta.json。")
    parser.add_argument("--right-metadata", help="右侧 metadata；默认查找同名 .meta.json。")
    parser.add_argument("--group-by", help="共同聚合维度，逗号分隔；省略时使用 Action Pair 默认值。")
    parser.add_argument("--metric", action="append", default=[], help="可重复的对账金额字段；默认 PayableAmount。")
    parser.add_argument("--filter", action="append", nargs=3, metavar=("FIELD", "OP", "VALUE"), default=[], help="同时作用于左右两侧的本地 Filter。")
    parser.add_argument("--mode", choices=("reconciliation", "observational"), default="reconciliation", help="默认正式对账；observational 按指定范围比较文件，不形成标准对账或多算结论。")
    parser.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    return parser


def build_preflight_parser(prog: str = "reconcile_cost.py preflight") -> Parser:
    return _base_reconcile_parser(prog, "只读检查两侧数据是否可比，不计算差额。")


def build_run_parser(prog: str = "reconcile_cost.py run") -> Parser:
    parser = _base_reconcile_parser(prog, "双侧聚合后执行受控 FULL OUTER JOIN。")
    parser.add_argument("--out", required=True, help="对账结果 CSV。")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def build_drill_parser(prog: str = "reconcile_cost.py drill-down") -> Parser:
    parser = Parser(prog=prog, description="继承父级对账口径，把唯一结果行按更细维度重新分解。", allow_abbrev=False)
    parser.add_argument("--from", dest="parent", required=True, help="父级 reconciliation/drill-down CSV。")
    parser.add_argument("--row", action="append", required=True, metavar="FIELD=VALUE", help="选择唯一父行；可重复。")
    parser.add_argument("--by", required=True, help="新增下钻维度，逗号分隔。")
    parser.add_argument("--side", choices=("both", "left", "right"), default="both", help="默认继续双侧对账；left/right 仅展开单侧。")
    parser.add_argument("--out", required=True, help="下钻结果 CSV。")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    return parser


def build_describe_parser(prog: str = "reconcile_cost.py describe") -> Parser:
    parser = Parser(prog=prog, description="输出对账与下钻机器契约。", allow_abbrev=False)
    parser.add_argument("--section", choices=("all", *CONTRACT_SECTIONS), default="all")
    parser.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    return parser


def build_root_parser(prog: str = "reconcile_cost.py") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="对 Billing CSV 进行可比性检查、双侧聚合对账和守恒式下钻。",
        allow_abbrev=False,
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("describe", "preflight", "run", "drill-down"),
        help="要执行的子命令；每个子命令也支持 --help。",
    )
    return parser


def _csv_items(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    values = tuple(item.strip() for item in value.split(","))
    if not values or any(not item for item in values):
        raise BillingQueryError(ErrorCode.INVALID_ARGUMENT, "逗号分隔字段不能为空", ExitCode.INVALID_ARGUMENT)
    return values


def _filter_value(operator: str, value: str) -> Any:
    operator = normalize_filter_operator(operator)
    if operator in {"in", "not-in", "between"}:
        values = [item.strip() for item in value.split(",")]
        if any(not item for item in values):
            raise BillingQueryError(ErrorCode.INVALID_ARGUMENT, f"{operator} 值不能为空", ExitCode.INVALID_ARGUMENT)
        if operator == "between" and len(values) != 2:
            raise BillingQueryError(ErrorCode.INVALID_ARGUMENT, "between 的值必须是两个逗号分隔项", ExitCode.INVALID_ARGUMENT)
        return values
    return value


def _filters(values: Sequence[Sequence[str]]) -> tuple[FilterItem, ...]:
    return tuple(
        FilterItem(field, normalize_filter_operator(operator), _filter_value(operator, value))
        for field, operator, value in values
    )


def _query_result(value: str, option: str) -> tuple[Path, Path, Path]:
    contract = {
        "type": "object",
        "required": ["file", "metadata", "fields"],
        "properties": {
            "file": {"type": "string", "format": "absolute_path"},
            "metadata": {"type": "string", "format": "absolute_path"},
            "fields": {"type": "string", "format": "absolute_path"},
        },
    }
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            f"{option} 必须是 query result JSON object",
            ExitCode.INVALID_ARGUMENT,
            {
                "invalid_parameters": [{
                    "path": option,
                    "actual": value,
                    "violation": "json_invalid",
                    "contract": contract,
                }],
            },
        ) from exc
    missing = [
        field
        for field in ("file", "metadata", "fields")
        if (
            not isinstance(result.get(field), str)
            or not result[field]
            or not Path(result[field]).is_absolute()
        )
    ] if isinstance(result, Mapping) else ["file", "metadata", "fields"]
    if missing:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            f"{option} 不符合文件型 query result 契约",
            ExitCode.INVALID_ARGUMENT,
            {
                "invalid_parameters": [{
                    "path": option,
                    "actual": result,
                    "violation": "result_contract_invalid",
                    "missing_or_invalid_fields": missing,
                    "contract": contract,
                }],
            },
        )
    return Path(result["file"]), Path(result["metadata"]), Path(result["fields"])


def _source_args(args: argparse.Namespace, side: str) -> tuple[Path, Path | None, Path | None]:
    result_value = getattr(args, f"{side}_result")
    metadata_value = getattr(args, f"{side}_metadata")
    if result_value is not None:
        if metadata_value is not None:
            option = f"--{side}-metadata"
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                f"{option} 不能与 --{side}-result 同时使用",
                ExitCode.INVALID_ARGUMENT,
                {
                    "invalid_parameters": [{
                        "path": option,
                        "actual": metadata_value,
                        "violation": "mutually_exclusive",
                        "contract": {"accepted_with": [f"--{side}"]},
                    }],
                },
            )
        return _query_result(result_value, f"--{side}-result")
    return Path(getattr(args, side)), Path(metadata_value) if metadata_value else None, None


def _request(args: argparse.Namespace) -> ReconcileRequest:
    left, left_metadata, left_fields = _source_args(args, "left")
    right, right_metadata, right_fields = _source_args(args, "right")
    return ReconcileRequest(
        left=left,
        right=right,
        left_metadata=left_metadata,
        right_metadata=right_metadata,
        left_fields=left_fields,
        right_fields=right_fields,
        group_by=_csv_items(args.group_by),
        metrics=tuple(args.metric) if args.metric else ("PayableAmount",),
        filters=_filters(args.filter),
        mode=args.mode,
    )


def _row_selectors(values: Sequence[str]) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for value in values:
        field, separator, expected = value.partition("=")
        if not separator or not field.strip():
            raise BillingQueryError(ErrorCode.INVALID_ARGUMENT, "--row 必须使用 FIELD=VALUE", ExitCode.INVALID_ARGUMENT, {"value": value})
        result.append((field.strip(), expected))
    return tuple(result)


def _task_envelope(command: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), Mapping) else {}
    csv_path = artifacts.get("csv")
    if not isinstance(csv_path, str) or not csv_path:
        raise BillingQueryError(
            ErrorCode.OUTPUT_FAILED,
            "对账执行完成但没有返回业务结果文件",
            ExitCode.OUTPUT_FAILED,
        )
    status_counts = payload.get("status_counts") if isinstance(payload.get("status_counts"), Mapping) else {}
    mismatched = int(status_counts.get("mismatched") or 0)
    matched = int(status_counts.get("matched") or 0)
    operation = str(payload.get("operation") or command)
    claim_scope = str(payload.get("claim_scope") or "unknown")
    if claim_scope == "observational":
        message = (
            f"已按指定输入范围完成观察性比较，{payload.get('row_count')} 个分组；"
            f"差额为右侧减左侧，结果已写入 {csv_path}。数值差异不证明多算或正式对账不一致。"
        )
    elif claim_scope == "inconclusive":
        message = f"{operation} 已生成 {payload.get('row_count')} 个分组，父级金额守恒未确认，不能据此解释父级差异；结果已写入 {csv_path}。"
    else:
        message = (
            f"{operation} 执行成功，{matched} 个分组一致，{mismatched} 个分组存在差异；"
            f"结论范围为 {claim_scope}，逐行结果已写入 {csv_path}。"
        )
    if mismatched:
        message += "金额差异是对账结果，不能直接证明业务根因。"
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    if warnings:
        message += "限制：" + "；".join(str(item) for item in warnings) + "。"
    meta = {
        "operation": operation,
        "verdict": payload.get("verdict"),
        "claim_scope": claim_scope,
        "row_count": payload.get("row_count"),
        "status_counts": dict(status_counts),
        "artifacts": {key: value for key, value in artifacts.items() if key != "csv"},
        **(
            {"conservation": payload["conservation"]}
            if "conservation" in payload
            else {}
        ),
    }
    return build_envelope(
        status="partial" if claim_scope == "inconclusive" else "success",
        message=message,
        result={"file": csv_path},
        meta=meta,
    )


def main(argv: Sequence[str] | None = None, *, prog: str = "reconcile_cost.py") -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    compact = True
    try:
        if arguments and arguments[0] in {"-h", "--help"}:
            build_root_parser(prog).parse_args(arguments)
            return int(ExitCode.SUCCESS)
        if not arguments:
            raise BillingQueryError(ErrorCode.INVALID_ARGUMENT, "必须指定 describe、preflight、run 或 drill-down", ExitCode.INVALID_ARGUMENT)
        command = arguments[0]
        if command == "describe":
            args = build_describe_parser(f"{prog} describe").parse_args(arguments[1:])
            payload = describe_reconciliation(args.section)
        elif command == "preflight":
            args = build_preflight_parser(f"{prog} preflight").parse_args(arguments[1:])
            payload = preflight(_request(args)).to_dict()
        elif command == "run":
            args = build_run_parser(f"{prog} run").parse_args(arguments[1:])
            payload = _task_envelope(
                command,
                run_reconciliation(_request(args), Path(args.out), overwrite=args.overwrite),
            )
        elif command == "drill-down":
            args = build_drill_parser(f"{prog} drill-down").parse_args(arguments[1:])
            payload = _task_envelope(
                command,
                drill_down(
                    DrillDownRequest(
                        parent=Path(args.parent),
                        row=_row_selectors(args.row),
                        by=_csv_items(args.by),
                        side=args.side,
                    ),
                    Path(args.out),
                    overwrite=args.overwrite,
                ),
            )
        else:
            raise BillingQueryError(ErrorCode.INVALID_ARGUMENT, f"未知命令：{command}", ExitCode.INVALID_ARGUMENT)
        print(json_dumps(payload, compact=getattr(args, "compact", compact)))
        return int(ExitCode.SUCCESS)
    except BillingQueryError as exc:
        print(json_dumps(error_envelope(exc), compact=compact))
        return int(exc.exit_code)
    except Exception as exc:
        error = BillingQueryError(ErrorCode.ACTION_FAILED, f"Reconciliation 内部错误：{exc}", ExitCode.QUERY_FAILED)
        print(json_dumps(error_envelope(error), compact=compact))
        return int(error.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
