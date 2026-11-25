#!/usr/bin/env python3
"""查询公开只读 ve billing Action，并输出 JSON 清单与 CSV 产物。"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from cost_query.billing.account_status import account_snapshot_projection
from cost_query.billing.financial_relations import financial_identity_message, verify_financial_relation_identity
from cost_query.billing.schema import ACTION_SCHEMAS
from cost_query.billing.client import FixtureBillingClient, VeBillingClient
from cost_query.billing.artifacts import (
    preflight_output,
    query_result_context,
    result_records,
    write_outputs,
)
from cost_query.billing.field_catalog import output_field_names
from cost_query.billing.field_grain import validate_required_response_fields
from cost_query.billing.fetch import (
    FetchConfig,
    NON_PAGED_ACTIONS,
    TOKEN_PAGED_ACTIONS,
    QueryResult,
    aggregate_coverage,
    collect_query,
)
from cost_query.billing.query_contract import CONTRACT_SECTIONS, describe_query
from cost_query.billing.validation import ALLOWED_ACTIONS, normalize_request_aliases, normalize_wrapper_request_body
from cost_query.common.errors import BillingQueryError, ErrorCode, ExitCode
from cost_query.common.execution_output import (
    AUTO_STDOUT_BYTE_LIMIT,
    build_envelope,
    compact_size,
    error_envelope,
)
from cost_query.common.json_output import dumps as json_dumps
from cost_query.utils.arguments import BillingArgumentParser as Parser
from cost_query.utils.billing import TOKEN_PAGE_SIZE_LIMITS


OFFSET_PAGE_SIZE_DEFAULTS = {
    "ListFinancialRelation": 100,
    "ListCoupons": 10,
    "ListCouponUsageRecords": 10,
}


def build_parser(prog: str = "query_billing.py") -> argparse.ArgumentParser:
    parser = Parser(
        prog=prog,
        description="查询 Billing 数据；小结果内联返回，大结果或显式输出时生成 CSV、metadata 和字段目录。",
        epilog=f"Agent 能力发现：{prog} describe [--section SECTION]。",
        allow_abbrev=False,
    )
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body", help="JSON object 请求体。")
    source.add_argument("--body-file", help="包含 JSON object 的 UTF-8 文件。")
    parser.add_argument("--period", action="append", default=[], help="可重复；覆盖 BillPeriod 或 AmortizedMonth。")
    parser.add_argument("--period-field", choices=("BillPeriod", "AmortizedMonth"), help="多账期替换字段；默认按 Action 自动选择。")
    parser.add_argument(
        "--out",
        help=(
            "CSV 结果文件路径；提供时强制使用 artifact 交付。省略时按 64 KiB 阈值自动选择 inline 或临时 artifact。"
        ),
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--pagination",
        choices=("full", "page"),
        help="分页 Action 必填：full 自动翻页获取全量，page 只获取指定页；一次性返回的 Action 会忽略该参数并给出 warning。",
    )
    parser.add_argument("--page-offset", type=int, help="Offset 分页 Action 的页偏移；token 分页 Action 直接在 body 提供 NextToken。")
    parser.add_argument("--page-size", type=int, help="每次请求的 Limit 或 MaxResults；也可在 body 中提供。")
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--max-rows", type=int, default=300000)
    parser.add_argument("--retry-count", type=int, default=2)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--region", help="用户明确指定的地域；省略时继承 ve 当前配置。")
    parser.add_argument("--profile")
    parser.add_argument(
        "--require-field",
        action="append",
        default=[],
        help=(
            "本次业务必须保留的响应字段；可重复。查询前按 Action × GroupPeriod × GroupTerm "
            "字段矩阵校验，避免先查汇总粒度再因主键为空重查。"
        ),
    )
    parser.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    parser.add_argument("--fixture-dir", help="测试用本地响应目录；指定后不调用 ve。")
    return parser


def build_describe_parser(prog: str = "query_billing.py describe") -> argparse.ArgumentParser:
    parser = Parser(
        prog=prog,
        description="输出供 Agent 规划 page/full、重试和结果解释的机器可读契约。",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--section",
        choices=("all", *CONTRACT_SECTIONS),
        default="all",
        help="只加载指定契约分区；默认 all。",
    )
    parser.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    return parser


def _load_body(args: argparse.Namespace) -> dict[str, Any]:
    try:
        text = args.body if args.body is not None else Path(args.body_file).read_text(encoding="utf-8")
        parsed = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            f"请求 body 不是有效 JSON：{exc}",
            ExitCode.INVALID_ARGUMENT,
        ) from exc
    if not isinstance(parsed, Mapping):
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            "请求 body 必须是 JSON object",
            ExitCode.INVALID_ARGUMENT,
        )
    return dict(parsed)


def _period_field(action: str, requested: str | None) -> str:
    if requested:
        if requested not in ACTION_SCHEMAS[action].request_params_by_name:
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                f"{action} 不支持 period field {requested}",
                ExitCode.INVALID_ARGUMENT,
            )
        return requested
    fields = ACTION_SCHEMAS[action].request_params_by_name
    if action.startswith("ListAmortizedCostBill"):
        return "AmortizedMonth"
    if "BillPeriod" in fields:
        return "BillPeriod"
    raise BillingQueryError(
        ErrorCode.INVALID_ARGUMENT,
        f"{action} 不支持 --period；请直接在 body 中提供接口时间参数",
        ExitCode.INVALID_ARGUMENT,
    )


def _query_bodies(action: str, body: Mapping[str, Any], periods: Sequence[str], field: str | None) -> list[tuple[str, dict[str, Any]]]:
    if not periods:
        query_id = str(body.get("AmortizedMonth", body.get("BillPeriod", "single")))
        return [(query_id, dict(body))]
    period_field = _period_field(action, field)
    return [
        (period, {**body, period_field: period})
        for period in periods
    ]


def _pagination_config(args: argparse.Namespace, body: Mapping[str, Any]) -> FetchConfig:
    if args.action in NON_PAGED_ACTIONS:
        ignored_args = []
        if args.pagination is not None:
            ignored_args.append(f"--pagination {args.pagination}")
        if args.page_size is not None:
            ignored_args.append(f"--page-size {args.page_size}")
        if args.page_offset is not None:
            ignored_args.append(f"--page-offset {args.page_offset}")
        return FetchConfig(
            pagination="none",
            max_pages=args.max_pages,
            max_rows=args.max_rows,
            retry_count=args.retry_count,
            retry_backoff_seconds=args.retry_backoff,
            ignored_pagination_args=tuple(ignored_args),
        )
    if args.pagination is None:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            f"{args.action} 是分页 Action，必须显式提供 --pagination page 或 --pagination full",
            ExitCode.INVALID_ARGUMENT,
        )
    if args.action in TOKEN_PAGED_ACTIONS:
        if args.page_offset is not None:
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                f"{args.action} 使用 NextToken 分页，不支持 --page-offset",
                ExitCode.INVALID_ARGUMENT,
            )
        body_size = body.get("MaxResults", body.get("max_results"))
        if body_size is not None and (not isinstance(body_size, str) or not body_size.isdigit()):
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                "body.MaxResults 必须是整数字符串",
                ExitCode.INVALID_ARGUMENT,
            )
        parsed_body_size = int(body_size) if body_size is not None else None
        if args.page_size is not None and parsed_body_size is not None and args.page_size != parsed_body_size:
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                "--page-size 与 body.MaxResults 冲突",
                ExitCode.INVALID_ARGUMENT,
                {"page_size": args.page_size, "body_max_results": parsed_body_size},
            )
        page_size = args.page_size if args.page_size is not None else parsed_body_size
        page_size = TOKEN_PAGE_SIZE_LIMITS[args.action] if page_size is None else page_size
        if not 1 <= page_size <= TOKEN_PAGE_SIZE_LIMITS[args.action]:
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                f"{args.action} page_size 必须在 1 到 {TOKEN_PAGE_SIZE_LIMITS[args.action]} 之间",
                ExitCode.INVALID_ARGUMENT,
            )
        next_token = body.get("NextToken")
        if args.pagination == "full" and next_token not in (None, "", "0"):
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                "full 模式必须从空 NextToken 开始",
                ExitCode.INVALID_ARGUMENT,
                {"next_token": next_token},
            )
        return FetchConfig(
            pagination=args.pagination,
            page_size=page_size,
            max_pages=args.max_pages,
            max_rows=args.max_rows,
            retry_count=args.retry_count,
            retry_backoff_seconds=args.retry_backoff,
        )
    default_size = OFFSET_PAGE_SIZE_DEFAULTS.get(args.action, 300)
    body_limit = body.get("Limit")
    body_offset = body.get("Offset")
    if args.page_size is not None and body_limit is not None and args.page_size != body_limit:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            "--page-size 与 body.Limit 冲突",
            ExitCode.INVALID_ARGUMENT,
            {"page_size": args.page_size, "body_limit": body_limit},
        )
    if args.page_offset is not None and body_offset is not None and args.page_offset != body_offset:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            "--page-offset 与 body.Offset 冲突",
            ExitCode.INVALID_ARGUMENT,
            {"page_offset": args.page_offset, "body_offset": body_offset},
        )
    page_size = args.page_size if args.page_size is not None else body_limit
    page_offset = args.page_offset if args.page_offset is not None else body_offset
    page_size = default_size if page_size is None else page_size
    page_offset = 0 if page_offset is None else page_offset
    if args.pagination == "full" and page_offset != 0:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            "full 模式必须从 Offset=0 开始",
            ExitCode.INVALID_ARGUMENT,
            {"offset": page_offset},
        )
    if args.pagination == "full" and body.get("NeedRecordNum") not in (None, 1):
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            "full 模式要求 NeedRecordNum=1",
            ExitCode.INVALID_ARGUMENT,
        )
    return FetchConfig(
        pagination=args.pagination,
        page_offset=page_offset,
        page_size=page_size,
        max_pages=args.max_pages,
        max_rows=args.max_rows,
        retry_count=args.retry_count,
        retry_backoff_seconds=args.retry_backoff,
    )


def _create_automatic_output_path(action: str) -> Path:
    try:
        root = Path(tempfile.gettempdir()) / "volcengine-billing-and-cost-management"
        root.mkdir(parents=True, exist_ok=True)
        run_directory = Path(
            tempfile.mkdtemp(prefix=f"{action.lower()}-", dir=str(root))
        )
    except OSError as exc:
        raise BillingQueryError(
            ErrorCode.OUTPUT_FAILED,
            f"创建自动输出目录失败：{exc}",
            ExitCode.OUTPUT_FAILED,
        ) from exc
    return run_directory / "result.csv"


def _request_scope(body: Mapping[str, Any]) -> dict[str, Any]:
    scope_fields = (
        "BillPeriod",
        "AmortizedMonth",
        "AmortizedDay",
        "ExpenseDate",
        "BeginTimeStr",
        "EndTimeStr",
        "Limit",
        "Offset",
    )
    return {field: body[field] for field in scope_fields if field in body}


def _raise_if_all_queries_failed(action: str, results: Sequence[QueryResult]) -> None:
    # A successful empty response is usable evidence; a response that immediately
    # failed validation or pagination without yielding rows is not.
    if any(_has_usable_response(result) for result in results):
        return
    failed_queries = []
    error_codes: list[str] = []
    for result in results:
        error = dict(result.error or {
            "code": ErrorCode.ACTION_FAILED.value,
            "message": "查询未返回可用响应",
        })
        error_codes.append(str(error.get("code", ErrorCode.ACTION_FAILED.value)))
        failed_queries.append({
            "query_id": result.query_id,
            "request_scope": _request_scope(result.request_body),
            "error": error,
        })
    unique_codes = set(error_codes)
    if len(unique_codes) == 1:
        try:
            code = ErrorCode(error_codes[0])
        except ValueError:
            code = ErrorCode.ACTION_FAILED
    else:
        code = ErrorCode.ALL_QUERIES_FAILED
    first_error = failed_queries[0]["error"] if failed_queries else {}
    first_message = str(first_error.get("message", ""))
    message = f"所有 Billing 查询均失败（{len(failed_queries)} 个分片）"
    if len(failed_queries) == 1 and first_message:
        message = f"{message}：{first_message}"
    raise BillingQueryError(
        code,
        message,
        ExitCode.QUERY_FAILED,
        {
            "action": action,
            "failed_query_count": len(failed_queries),
            "failed_queries": failed_queries,
            "artifacts_written": False,
        },
        cause=(first_error.get("cause") if len(failed_queries) == 1 else None),
    )


def _has_usable_response(result: QueryResult) -> bool:
    return bool(result.rows or (result.page_fetched and result.error is None))


def _query_status(coverage: Mapping[str, Any], results: Sequence[QueryResult]) -> tuple[str, ExitCode]:
    if coverage["requested_scope"] == "page" and coverage["requested_scope_fulfilled"]:
        return "success", ExitCode.SUCCESS
    if coverage["is_complete"]:
        return "success", ExitCode.SUCCESS
    if coverage["is_provisional"] and coverage["requested_scope_fulfilled"]:
        return "success", ExitCode.SUCCESS
    if any(_has_usable_response(result) for result in results):
        return "partial", ExitCode.PARTIAL_RESULT
    return "error", ExitCode.QUERY_FAILED


def _query_message(
    *,
    action: str,
    status: str,
    row_count: int,
    coverage: Mapping[str, Any],
    context: Mapping[str, Any],
    result_file: str | None = None,
) -> str:
    if status == "partial":
        queries = coverage.get("queries") if isinstance(coverage.get("queries"), list) else []
        failed = coverage.get("failed_queries") if isinstance(coverage.get("failed_queries"), list) else []
        failed_ids = [str(item.get("query_id")) for item in failed if isinstance(item, Mapping)]
        successful_ids = [
            str(item.get("query_id"))
            for item in queries
            if isinstance(item, Mapping) and item not in failed
        ]
        message = f"{action} 查询部分完成，共返回 {row_count} 条可用记录"
        if successful_ids:
            message += "；成功范围：" + "、".join(successful_ids)
        if failed_ids:
            message += "；失败或未完成范围：" + "、".join(failed_ids)
        message += "。结果不能作为本次请求的完整数据。"
    elif row_count == 0:
        if action == "ListFinancialRelation" and context.get("no_financial_relations"):
            message = "财务关系查询成功，当前账号没有财务关系。"
        elif action == "ListFinancialRelation":
            message = "财务关系查询成功，本次指定条件或页范围内没有财务关系记录。"
        else:
            message = f"{action} 查询成功，本次请求范围内没有记录。"
    else:
        message = f"{action} 查询成功，共返回 {row_count} 条记录。"

    if coverage.get("requested_scope") == "page" and not (
        action == "ListFinancialRelation" and context.get("no_financial_relations")
    ):
        message += "结果只覆盖请求页，不代表完整数据范围。"
    freshness = context.get("freshness") if isinstance(context.get("freshness"), Mapping) else {}
    if freshness.get("partial_period") is True:
        message += "查询包含当前账期，数据尚未完结，仅代表本次查询可见范围。"
    for note in freshness.get("notes") or []:
        if freshness.get("partial_period") is True and isinstance(note, str) and "当前月" in note:
            continue
        if isinstance(note, str) and note and note not in message:
            message += note if note.endswith("。") else note + "。"
    warnings = context.get("warnings") if isinstance(context.get("warnings"), list) else []
    if warnings:
        normalized_warnings = [str(item).rstrip("。") for item in warnings]
        message += "查询提示：" + "；".join(normalized_warnings) + "。"
    if result_file:
        message += f"完整业务结果已写入 {result_file}。"
    identity = context.get("identity_verification")
    if isinstance(identity, Mapping):
        message += financial_identity_message(identity)
    return message


def _inline_meta(
    *,
    action: str,
    row_count: int,
    coverage: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "action": action,
        "row_count": row_count,
        "coverage": dict(coverage),
        "freshness": dict(context.get("freshness") or {}),
        "warnings": list(context.get("warnings") or []),
        **({"identity_verification": context["identity_verification"]} if "identity_verification" in context else {}),
        **({"queried_coupon_ids": context["queried_coupon_ids"]} if "queried_coupon_ids" in context else {}),
        **(
            {"analysis_summary": context["analysis_summary"]}
            if "analysis_summary" in context
            else {}
        ),
    }


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.timeout is not None and args.timeout <= 0:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            "--timeout 必须大于 0",
            ExitCode.INVALID_ARGUMENT,
        )
    body = normalize_wrapper_request_body(args.action, normalize_request_aliases(args.action, _load_body(args)))
    required_fields = validate_required_response_fields(
        args.action,
        body,
        args.require_field,
        output_field_names(args.action),
    )
    config = _pagination_config(args, body)
    config.validate()
    output = Path(args.out) if args.out else None
    if output is not None:
        preflight_output(
            output=output,
            overwrite=args.overwrite,
        )
    if args.fixture_dir:
        client = FixtureBillingClient(Path(args.fixture_dir))
    else:
        client = VeBillingClient(
            region=args.region,
            profile=args.profile,
            timeout_seconds=args.timeout,
        )
    results = [
        collect_query(
            client=client,
            action=args.action,
            query_id=query_id,
            base_body=query_body,
            config=config,
        )
        for query_id, query_body in _query_bodies(args.action, body, args.period, args.period_field)
    ]
    _raise_if_all_queries_failed(args.action, results)
    coverage = aggregate_coverage(results)
    status, code = _query_status(coverage, results)
    if status == "error":
        raise BillingQueryError(
            ErrorCode.ALL_QUERIES_FAILED,
            f"{args.action} 查询没有可交付的有效结果",
            ExitCode.QUERY_FAILED,
            {"coverage": coverage},
        )
    if args.action == "QueryBalanceAcct":
        account_result, message, account_evidence = account_snapshot_projection(
            [row for result in results for row in result.rows],
            query_complete=status == "success",
        )
        account_meta = {
            "action": args.action,
            **account_evidence,
        }
        if output is not None:
            metadata = write_outputs(
                action=args.action,
                results=results,
                output=output,
                overwrite=args.overwrite,
                backend=client.backend_name,
                required_fields=required_fields,
                execution_evidence=account_evidence,
            )
            csv_path = metadata["artifacts"]["csv"]
            message += f"业务结果已写入 {csv_path}。"
            account_meta = {
                **account_meta,
                "evidence_file": metadata["artifacts"]["metadata"],
                "field_catalog": metadata["artifacts"]["fields"],
            }
            account_result = {
                "file": csv_path,
                "metadata": metadata["artifacts"]["metadata"],
                "fields": metadata["artifacts"]["fields"],
            }
        return int(code), build_envelope(
            status=status,
            message=message,
            result=account_result,
            meta=account_meta,
        )

    records = result_records(results)
    context = query_result_context(args.action, results)
    if args.action == "ListCouponUsageRecords":
        context["queried_coupon_ids"] = list(dict.fromkeys(
            result.request_body["CouponID"] for result in results if result.request_body.get("CouponID")
        ))
    if args.action == "ListFinancialRelation":
        context["identity_verification"] = verify_financial_relation_identity(client, records)
        context["no_financial_relations"] = (
            not records and coverage.get("is_complete") is True
            and all(
                not any(result.request_body.get(field) for field in ("AccountIDSearchList", "Relation", "Status"))
                for result in results
            )
        )
    inline_meta = _inline_meta(
        action=args.action,
        row_count=len(records),
        coverage=coverage,
        context=context,
    )
    inline_envelope = build_envelope(
        status=status,
        message=_query_message(
            action=args.action,
            status=status,
            row_count=len(records),
            coverage=coverage,
            context=context,
        ),
        result=records,
        meta=inline_meta,
    )
    if output is None and compact_size(inline_envelope) <= AUTO_STDOUT_BYTE_LIMIT:
        return int(code), inline_envelope
    if output is None:
        output = _create_automatic_output_path(args.action)
    assert output is not None
    metadata = write_outputs(
        action=args.action,
        results=results,
        output=output,
        overwrite=args.overwrite,
        backend=client.backend_name,
        required_fields=required_fields,
        execution_evidence={"identity_verification": context["identity_verification"]} if "identity_verification" in context else None,
    )
    csv_path = metadata["artifacts"]["csv"]
    payload = build_envelope(
        status=status,
        message=_query_message(
            action=args.action,
            status=status,
            row_count=metadata["row_count"],
            coverage=coverage,
            context=context,
            result_file=csv_path,
        ),
        result={
            "file": csv_path,
            "metadata": metadata["artifacts"]["metadata"],
            "fields": metadata["artifacts"]["fields"],
        },
        meta={
            "action": args.action,
            "row_count": metadata["row_count"],
            "evidence_file": metadata["artifacts"]["metadata"],
            "field_catalog": metadata["artifacts"]["fields"],
        },
    )
    return int(code), payload


def main(argv: Sequence[str] | None = None, *, prog: str = "query_billing.py") -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    compact = True
    try:
        if arguments and arguments[0] == "describe":
            describe_args = build_describe_parser(f"{prog} describe").parse_args(arguments[1:])
            print(json_dumps(describe_query(describe_args.section), compact=describe_args.compact))
            return int(ExitCode.SUCCESS)
        args = build_parser(prog).parse_args(arguments)
        code, payload = run(args)
        print(json_dumps(payload, compact=args.compact))
        return code
    except BillingQueryError as exc:
        print(json_dumps(error_envelope(exc), compact=compact))
        return int(exc.exit_code)
    except Exception as exc:
        error = BillingQueryError(
            ErrorCode.ACTION_FAILED,
            f"查询脚本内部错误：{exc}",
            ExitCode.QUERY_FAILED,
        )
        print(json_dumps(error_envelope(error), compact=compact))
        return int(error.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
