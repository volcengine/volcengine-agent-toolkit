#!/usr/bin/env python3
"""对已查询的代金券库存和账单明细做本地确定性归因。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from cost_query.arrears.coupon import analyze_coupon_attribution
from cost_query.arrears.input_evidence import apply_input_evidence_policy, load_attribution_input
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


def _queried_coupon_ids(inputs: list[Any]) -> list[str]:
    result: list[str] = []
    for item in inputs:
        metadata_path = item.metadata_path
        if metadata_path is None:
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for query in metadata.get("queries") or []:
            if not isinstance(query, dict) or not isinstance(query.get("request_body"), dict):
                continue
            coupon_id = query["request_body"].get("CouponID")
            if coupon_id not in (None, ""):
                result.append(str(coupon_id))
    return list(dict.fromkeys(result))


def describe() -> dict[str, Any]:
    return {
        "purpose": "组合 ListCoupons 库存、ListCouponUsageRecords 实际核销记录和账单明细生成代金券抵扣证据，不发起网络请求。",
        "inputs": ["coupons", "usage-records", "bill-details", "analysis-period", "comparison-period", "candidate-coupon"],
        "supported_reasons": [
            "coupon_used_up", "coupon_expired", "coupon_not_effective",
            "coupon_not_applicable", "coupon_redemption_declined",
        ],
        "evidence_policy": {
            "inventory_and_scope": "ListCoupons",
            "actual_redemption_and_return": "ListCouponUsageRecords",
            "bill_deduction_observation": "ListBillDetail.CouponAmount",
            "target_bill_link": "PayType=post 时 SubBusinessID=BillDetailId；PayType=pre 时 SubBusinessID=预付费账单 BillID",
        },
        "input_completeness_policy": {
            "complete_query_results": "status=success 且机器证据完整时可输出 supported_reasons",
            "incomplete_query_results": "status=partial，只输出 insufficient_evidence",
            "manual_files_without_metadata": "insufficient_evidence，不输出 supported_reasons",
        },
    }


def build_parser(prog: str = "attribute_coupons.py") -> Parser:
    parser = Parser(prog=prog, description="基于已查询证据分析代金券原因，不发起网络请求。")
    parser.add_argument("--coupons", type=Path, required=True)
    parser.add_argument(
        "--usage-records",
        type=Path,
        action="append",
        default=[],
        help="指定券的 ListCouponUsageRecords 完整查询产物；多张券时重复传入。",
    )
    parser.add_argument("--bill-details", type=Path, required=True)
    parser.add_argument("--analysis-period", required=True)
    parser.add_argument("--comparison-period")
    parser.add_argument("--candidate-coupon", action="append", default=[])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None, prog: str = "attribute_coupons.py") -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments == ["describe"]:
        print(json_dumps(describe()))
        return 0
    try:
        args = build_parser(prog).parse_args(arguments)
        coupons = load_attribution_input(args.coupons, input_name="coupons")
        bill_details = load_attribution_input(args.bill_details, input_name="bill_details")
        usage_inputs = [
            load_attribution_input(path, input_name=f"usage_records_{index + 1}")
            for index, path in enumerate(args.usage_records)
        ]
        usage_records = (
            [row for item in usage_inputs for row in item.rows]
            if usage_inputs
            else None
        )
        result = analyze_coupon_attribution(
            coupons=coupons.rows,
            bill_details=bill_details.rows,
            usage_records=usage_records,
            usage_record_coupon_ids=_queried_coupon_ids(usage_inputs),
            analysis_period=args.analysis_period,
            comparison_period=args.comparison_period,
            candidate_coupon_ids=args.candidate_coupon,
        )
        result, status = apply_input_evidence_policy(
            result,
            [coupons, bill_details, *usage_inputs],
        )
        supported_count = len(result.get("supported_reasons") or [])
        insufficient_count = len(result.get("insufficient_evidence") or [])
        message = (
            f"代金券核查完成，确认 {supported_count} 个有证据支持的原因，"
            f"{insufficient_count} 个候选仍缺少必要证据。"
        )
        if status == "partial":
            message = "代金券归因仅部分完成；至少一份必需输入存在已知采集缺口。" + message
        meta = {
            "operation": "coupon_attribution",
            "input_evidence": result.get("input_evidence") or [],
        }
        envelope = build_envelope(status=status, message=message, result=result, meta=meta)
        output_path = args.out
        if output_path is None and compact_size(envelope) > AUTO_STDOUT_BYTE_LIMIT:
            output_path = automatic_result_path("coupon", ".json")
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
            f"代金券归因输入或结果无效：{exc}",
            ExitCode.INVALID_ARGUMENT,
        )
        print(json_dumps(error_envelope(error)))
        return int(error.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
