#!/usr/bin/env python3
"""对已查询的资源包、抵扣明细和账单明细做本地确定性归因。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from cost_query.arrears.input_evidence import apply_input_evidence_policy, load_attribution_input
from cost_query.arrears.resource_package import analyze_resource_package_attribution
from cost_query.common.errors import BillingQueryError, ErrorCode, ExitCode
from cost_query.common.execution_output import (
    AUTO_STDOUT_BYTE_LIMIT,
    automatic_result_path,
    build_envelope,
    compact_size,
    error_envelope,
    write_json_result,
)
from cost_query.common.json_output import dumps as json_dumps
from cost_query.utils.arguments import BillingArgumentParser as Parser


def build_parser(prog: str = "attribute_resource_packages.py") -> Parser:
    parser = Parser(prog=prog, description="基于已查询证据分析资源包原因，不发起网络请求。")
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--usage-details", type=Path, required=True)
    parser.add_argument("--bill-details", type=Path, required=True)
    parser.add_argument("--analysis-period", required=True)
    parser.add_argument("--comparison-period")
    parser.add_argument("--candidate-instance", action="append", default=[])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def describe() -> dict[str, Any]:
    return {
        "purpose": "基于资源包库存、抵扣明细和账单明细生成资源包第二层消费原因，不发起网络请求。",
        "inputs": ["packages", "usage-details", "bill-details", "analysis-period", "comparison-period", "candidate-instance"],
        "supported_reasons": [
            "resource_package_used_up",
            "resource_package_expired",
            "resource_package_not_effective",
            "resource_package_deduction_declined",
            "resource_package_not_covering (only for an explicitly selected package with product or region mismatch)",
        ],
        "evidence_policy": "缺少匹配抵扣明细时返回 insufficient_evidence，不输出资源包原因。",
        "contract_limits": [
            "package.json 未声明全部配置、全部计费项或计费模式适用范围",
            "ConfigurationName/ConfigurationCode 不是适用范围通配字段",
        ],
        "input_completeness_policy": {
            "complete_query_results": "status=success 且机器证据完整时可输出 supported_reasons",
            "incomplete_query_results": "status=partial，只输出 insufficient_evidence",
            "manual_files_without_metadata": "insufficient_evidence，不输出 supported_reasons",
        },
    }


def main(argv: list[str] | None = None, prog: str = "attribute_resource_packages.py") -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments == ["describe"]:
        print(json_dumps(describe()))
        return 0
    try:
        args = build_parser(prog).parse_args(arguments)
        packages = load_attribution_input(args.packages, input_name="packages")
        usage_details = load_attribution_input(args.usage_details, input_name="usage_details")
        bill_details = load_attribution_input(args.bill_details, input_name="bill_details")
        result = analyze_resource_package_attribution(
            packages=packages.rows,
            usage_details=usage_details.rows,
            bill_details=bill_details.rows,
            analysis_period=args.analysis_period,
            comparison_period=args.comparison_period,
            candidate_instance_nos=args.candidate_instance,
        )
        result, status = apply_input_evidence_policy(result, [packages, usage_details, bill_details])
        supported_count = len(result.get("supported_reasons") or [])
        insufficient_count = len(result.get("insufficient_evidence") or [])
        message = (
            f"资源包归因执行完成，确认 {supported_count} 个有证据支持的原因，"
            f"{insufficient_count} 个候选仍缺少必要证据。"
        )
        if status == "partial":
            message = "资源包归因仅部分完成；至少一份必需输入存在已知采集缺口。" + message
        meta = {
            "operation": "resource_package_attribution",
            "input_evidence": result.get("input_evidence") or [],
        }
        envelope = build_envelope(status=status, message=message, result=result, meta=meta)
        output_path = args.out
        if output_path is None and compact_size(envelope) > AUTO_STDOUT_BYTE_LIMIT:
            output_path = automatic_result_path("resource-package", ".json")
        if output_path is not None:
            try:
                resolved = write_json_result(output_path, result, overwrite=args.overwrite)
            except FileExistsError as exc:
                raise BillingQueryError(
                    ErrorCode.OUTPUT_EXISTS,
                    f"输出文件已存在：{exc}",
                    ExitCode.OUTPUT_FAILED,
                ) from exc
            except OSError as exc:
                raise BillingQueryError(
                    ErrorCode.OUTPUT_FAILED,
                    f"写入结果失败：{exc}",
                    ExitCode.OUTPUT_FAILED,
                ) from exc
            envelope = build_envelope(
                status=status,
                message=message + f"业务结果已写入 {resolved}。",
                result={"file": str(resolved)},
                meta=meta,
            )
        print(json_dumps(envelope))
        return int(ExitCode.PARTIAL_RESULT if status == "partial" else ExitCode.SUCCESS)
    except BillingQueryError as exc:
        print(json_dumps(error_envelope(exc)))
        return int(exc.exit_code)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        error = BillingQueryError(
            ErrorCode.RESPONSE_INVALID,
            f"资源包归因输入或结果无效：{exc}",
            ExitCode.INVALID_ARGUMENT,
        )
        print(json_dumps(error_envelope(error)))
        return int(error.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
