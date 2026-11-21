"""Action 级完整采集、分页、重试和 coverage。"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Mapping, Sequence

from .schema import ACTION_SCHEMAS, ApiElementSpec
from .exposure import public_row
from .client import BillingClient, action_result
from .cost_change import COST_CHANGE_ACTIONS, validate_cost_change_result
from ..common.errors import BillingQueryError, ErrorCode, ExitCode
from .validation import validate_request_body
from ..utils.billing import TOKEN_PAGE_SIZE_LIMITS


PAGED_LIST_ACTIONS = frozenset(
    {
        "ListBillOverviewByProd",
        "ListBill",
        "ListBillDetail",
        "ListSplitBillDetail",
        "ListAmortizedCostBillMonthly",
        "ListAmortizedCostBillDaily",
        "ListAmortizedCostBillDetail",
        "ListCoupons",
        "ListCouponUsageRecords",
        "ListFinancialRelation",
    }
)
PAGED_ANALYSIS_ACTIONS = frozenset({"ListCostAnalysisOpenApi"})
TOKEN_PAGED_ACTIONS = frozenset(TOKEN_PAGE_SIZE_LIMITS)
NON_PAGED_ACTIONS = frozenset(
    {
        "GetFilterInfoForCostAnalysis",
        "ListBillOverviewByCategory",
        "QueryBalanceAcct",
        *COST_CHANGE_ACTIONS,
    }
)
ANALYSIS_SYNTHETIC_TOTAL_LABEL = "总费用"
ANALYSIS_DEFAULT_CURRENCY = "CNY"


@dataclass(frozen=True)
class FetchConfig:
    pagination: str = "full"
    page_offset: int = 0
    page_size: int = 300
    max_pages: int = 1000
    max_rows: int = 300000
    retry_count: int = 2
    retry_backoff_seconds: float = 0.5
    ignored_pagination_args: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.pagination not in ("full", "page", "none"):
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                "pagination 只能是 full、page 或非分页 Action 使用的 none",
                ExitCode.INVALID_ARGUMENT,
            )
        bounds = (
            ("page_size", self.page_size, 1, 1000),
            ("max_pages", self.max_pages, 1, 10000),
            ("max_rows", self.max_rows, 1, 3000000),
            ("retry_count", self.retry_count, 0, 10),
        )
        for name, value, minimum, maximum in bounds:
            if not minimum <= value <= maximum:
                raise BillingQueryError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"{name} 必须在 {minimum} 到 {maximum} 之间",
                    ExitCode.INVALID_ARGUMENT,
                    {"parameter": name, "value": value},
                )
        if not 0 <= self.retry_backoff_seconds <= 60:
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                "retry_backoff_seconds 必须在 0 到 60 之间",
                ExitCode.INVALID_ARGUMENT,
            )
        if self.page_offset < 0:
            raise BillingQueryError(
                ErrorCode.INVALID_ARGUMENT,
                "page_offset 不能小于 0",
                ExitCode.INVALID_ARGUMENT,
            )


@dataclass
class QueryResult:
    query_id: str
    action: str
    request_body: dict[str, Any]
    rows: list[dict[str, Any]] = field(default_factory=list)
    items_collected: int = 0
    pages_fetched: int = 0
    expected_total: int | None = None
    is_complete: bool = False
    is_provisional: bool = False
    provisional_reason: str | None = None
    stop_reason: str | None = None
    last_observed_total: int | None = None
    initial_total_boundary_reached: bool = False
    retries: int = 0
    warnings: list[str] = field(default_factory=list)
    analysis_summary_rows: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, Any] | None = None
    requested_scope: str = "full"
    page_fetched: bool = False

    def coverage(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "action": self.action,
            "pages_fetched": self.pages_fetched,
            "rows_collected": len(self.rows),
            "items_collected": self.items_collected,
            "expected_total": self.expected_total,
            "first_observed_total": self.expected_total,
            "total_stability": (
                "drifted"
                if self.stop_reason in ("total_changed", "rows_exceeded_first_total")
                else "stable" if self.expected_total is not None else "unknown"
            ),
            "is_complete": self.is_complete,
            "is_provisional": self.is_provisional,
            "provisional_reason": self.provisional_reason,
            "stop_reason": self.stop_reason,
            "last_observed_total": self.last_observed_total,
            "initial_total_boundary_reached": self.initial_total_boundary_reached,
            "requested_scope": self.requested_scope,
            "page_fetched": self.page_fetched,
            "retries": self.retries,
            "warnings": list(dict.fromkeys(self.warnings)),
            **(
                {"analysis_summary_row_count": len(self.analysis_summary_rows)}
                if self.analysis_summary_rows
                else {}
            ),
            "error": self.error,
        }


def _error_dict(exc: BillingQueryError) -> dict[str, Any]:
    return exc.error_dict()


def request_includes_current_period(body: Mapping[str, Any]) -> bool:
    current_month = date.today().strftime("%Y-%m")
    return any(
        isinstance(body.get(field), str)
        and str(body[field])[:7] == current_month
        for field in (
            "BillPeriod",
            "AmortizedMonth",
            "AmortizedDay",
            "ExpenseDate",
            "BeginTimeStr",
            "EndTimeStr",
            "CurrentPeriod",
            "BasePeriod",
            "current_period",
            "base_period",
        )
    )


def _mark_current_period_provisional(
    result: QueryResult,
    *,
    reason: str,
    stop_reason: str,
    expected_total: int,
    current_total: int | None,
    items_collected: int,
) -> None:
    result.is_provisional = True
    result.provisional_reason = reason
    result.stop_reason = stop_reason
    result.last_observed_total = current_total
    result.initial_total_boundary_reached = items_collected >= expected_total
    result.warnings.append(
        "当前月分页期间 Total 发生漂移；已达到首次观测的 Total 边界，"
        "本次结果可用于临时分析，但不是最终账期全量。"
    )


def _query_with_retry(
    client: BillingClient,
    action: str,
    body: Mapping[str, Any],
    config: FetchConfig,
    sleeper: Callable[[float], None],
) -> tuple[Mapping[str, Any], int]:
    retries = 0
    while True:
        try:
            return client.query(action, body), retries
        except BillingQueryError as exc:
            if exc.code not in (ErrorCode.RATE_LIMITED, ErrorCode.TIMEOUT) or retries >= config.retry_count:
                raise
            delay = config.retry_backoff_seconds * (2**retries)
            retries += 1
            if delay:
                sleeper(delay)


def _is_type(element: ApiElementSpec, value: Any) -> bool:
    if value is None:
        return True
    if element.type_code == 1:
        return isinstance(value, str)
    if element.type_code in (2, 3):
        return isinstance(value, int) and not isinstance(value, bool)
    if element.type_code == 4:
        return isinstance(value, bool)
    if element.type_code in (5, 6):
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) and (not isinstance(value, Decimal) or value.is_finite())
    if element.type_code == 7:
        return isinstance(value, Mapping)
    return False


def _validate_element(element: ApiElementSpec, value: Any, path: str) -> None:
    values: Sequence[Any]
    if element.is_array:
        if not isinstance(value, list):
            raise BillingQueryError(
                ErrorCode.RESPONSE_INVALID,
                f"{path} 应为 {element.type_name}[]",
                ExitCode.QUERY_FAILED,
            )
        values = value
    else:
        values = (value,)
    for item in values:
        if not _is_type(element, item):
            raise BillingQueryError(
                ErrorCode.RESPONSE_INVALID,
                f"{path} 类型不符合响应契约",
                ExitCode.QUERY_FAILED,
                {"actual": type(item).__name__},
            )
        if item is None or element.type_code != 7:
            continue
        children = element.children_by_name
        for name, child_value in item.items():
            child = children.get(name)
            if child is not None:
                _validate_element(child, child_value, f"{path}.{name}")


def validate_response_payload(action: str, payload: Mapping[str, Any]) -> None:
    if action in COST_CHANGE_ACTIONS:
        validate_cost_change_result(action, payload)
        return
    elements = ACTION_SCHEMAS[action].response_elements_by_name
    for name, value in payload.items():
        element = elements.get(name)
        if element is not None:
            _validate_element(element, value, name)


def _page_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    from ..common.json_output import dumps

    raw = dumps(list(rows), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _is_analysis_summary_group(group: Any) -> bool:
    return (
        isinstance(group, Mapping)
        and str(group.get("ClassifyItem", "")).strip() == ANALYSIS_SYNTHETIC_TOTAL_LABEL
    )


def _with_analysis_default_currency(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    if "Amount" in result and "Currency" not in result:
        result["Currency"] = ANALYSIS_DEFAULT_CURRENCY
    return result


def _flatten_cost_data(
    payload: Mapping[str, Any],
    *,
    summary_rows: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("CostData") or []:
        if _is_analysis_summary_group(group) != summary_rows:
            continue
        common = {key: value for key, value in group.items() if key != "Costs"}
        costs = group.get("Costs") or []
        if not costs:
            rows.append(_with_analysis_default_currency(common))
            continue
        for cost in costs:
            rows.append(_with_analysis_default_currency({**common, **cost}))
    return rows


def _analysis_page_items(payload: Mapping[str, Any]) -> int:
    # The service can return a synthetic aggregate row while Total counts real classify items.
    return sum(
        1
        for group in payload.get("CostData") or []
        if not _is_analysis_summary_group(group)
    )


def extract_analysis_summary_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _flatten_cost_data(payload, summary_rows=True)


def _flatten_filter_catalog(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category, values in payload.items():
        if not isinstance(values, list):
            rows.append({"Catalog": category, "Value": values})
            continue
        for value in values:
            if isinstance(value, Mapping):
                rows.append({"Catalog": category, **dict(value)})
            else:
                rows.append({"Catalog": category, "Value": value})
    return rows


def _flatten_category_overview(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("List") or []:
        if isinstance(group, Mapping) and isinstance(group.get("List"), list):
            parent = {key: value for key, value in group.items() if key != "List"}
            rows.extend({**parent, **dict(item)} for item in group["List"])
        elif isinstance(group, Mapping):
            rows.append(dict(group))
    return rows


def extract_rows(action: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if action in PAGED_LIST_ACTIONS or action in TOKEN_PAGED_ACTIONS:
        return [public_row(action, row) for row in payload.get("List") or []]
    if action in PAGED_ANALYSIS_ACTIONS:
        return [public_row(action, row) for row in _flatten_cost_data(payload)]
    if action == "GetFilterInfoForCostAnalysis":
        return [public_row(action, row) for row in _flatten_filter_catalog(payload)]
    if action == "ListBillOverviewByCategory":
        return [public_row(action, row) for row in _flatten_category_overview(payload)]
    return [public_row(action, payload)]


def _is_paged(action: str) -> bool:
    return action in PAGED_LIST_ACTIONS or action in PAGED_ANALYSIS_ACTIONS or action in TOKEN_PAGED_ACTIONS


def _collect_token_query(
    *,
    client: BillingClient,
    action: str,
    normalized: Mapping[str, Any],
    config: FetchConfig,
    result: QueryResult,
    sleeper: Callable[[float], None],
) -> QueryResult:
    rows: list[dict[str, Any]] = []
    seen_tokens: set[str] = set()
    digests: set[str] = set()
    token = str(normalized.get("NextToken") or "")
    page_budget = 1 if config.pagination == "page" else config.max_pages
    for _ in range(page_budget):
        remaining = config.max_rows - len(rows)
        if remaining <= 0:
            result.warnings.append("查询因 max_rows 截断")
            break
        body = dict(normalized)
        body["MaxResults"] = str(min(config.page_size, remaining))
        body["NextToken"] = token
        try:
            response, retries = _query_with_retry(client, action, body, config, sleeper)
            result.retries += retries
            payload = action_result(action, response)
            validate_response_payload(action, payload)
        except BillingQueryError as exc:
            result.error = _error_dict(exc)
            break

        page_rows = extract_rows(action, payload)
        result.pages_fetched += 1
        result.page_fetched = True
        if page_rows:
            digest = _page_digest(page_rows)
            if digest in digests:
                result.error = _error_dict(BillingQueryError(
                    ErrorCode.PAGINATION_INCOMPLETE,
                    "检测到重复 token 分页",
                    ExitCode.PARTIAL_RESULT,
                    {"next_token": token},
                ))
                break
            digests.add(digest)
            rows.extend(page_rows[:remaining])
        result.items_collected += len(page_rows)

        raw_next_token = payload.get("NextToken")
        next_token = "" if raw_next_token is None else str(raw_next_token)
        terminal = next_token in ("", "0") or not page_rows
        if config.pagination == "page":
            result.is_complete = terminal and token in ("", "0")
            break
        if terminal:
            if not page_rows and next_token not in ("", "0"):
                result.warnings.append("响应列表为空，按契约视为 token 分页结束。")
            result.is_complete = True
            break
        if next_token == token or next_token in seen_tokens:
            result.error = _error_dict(BillingQueryError(
                ErrorCode.PAGINATION_INCOMPLETE,
                "NextToken 未推进或重复",
                ExitCode.PARTIAL_RESULT,
                {"next_token": next_token},
            ))
            break
        seen_tokens.add(next_token)
        token = next_token

    result.rows = rows
    result.expected_total = None
    if config.pagination == "full" and not result.is_complete and result.error is None:
        result.warnings.append("查询因 max_pages 或 max_rows 截断")
    return result


def collect_query(
    *,
    client: BillingClient,
    action: str,
    query_id: str,
    base_body: Mapping[str, Any],
    config: FetchConfig,
    sleeper: Callable[[float], None] = time.sleep,
) -> QueryResult:
    config.validate()
    paged = _is_paged(action)
    if paged and config.pagination == "none":
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            f"{action} 是分页 Action，必须选择 page 或 full",
            ExitCode.INVALID_ARGUMENT,
        )
    prepared = dict(base_body)
    if action in TOKEN_PAGED_ACTIONS:
        prepared["MaxResults"] = str(config.page_size)
        if config.pagination == "full":
            prepared["NextToken"] = ""
        else:
            prepared.setdefault("NextToken", "")
    elif paged:
        effective_limit = config.page_size
        effective_offset = config.page_offset if config.pagination == "page" else 0
        prepared["Limit"] = effective_limit
        prepared["Offset"] = effective_offset
        if "NeedRecordNum" in ACTION_SCHEMAS[action].request_params_by_name:
            if config.pagination == "full":
                prepared["NeedRecordNum"] = 1
            else:
                prepared.setdefault("NeedRecordNum", 1)
    normalized = validate_request_body(action, prepared)
    result = QueryResult(
        query_id=query_id,
        action=action,
        request_body=dict(normalized),
        requested_scope=config.pagination if paged else "none",
    )
    if not paged:
        ignored_args = list(config.ignored_pagination_args)
        if config.pagination != "none" and not ignored_args:
            ignored_args.append(f"pagination={config.pagination}")
        if ignored_args:
            result.warnings.append(
                f"{action} 一次请求即返回完整结果，已忽略分页参数：{', '.join(ignored_args)}。"
            )
    current_period = request_includes_current_period(normalized)
    if action in TOKEN_PAGED_ACTIONS:
        return _collect_token_query(
            client=client,
            action=action,
            normalized=normalized,
            config=config,
            result=result,
            sleeper=sleeper,
        )
    if not paged:
        try:
            response, retries = _query_with_retry(client, action, normalized, config, sleeper)
            payload = action_result(action, response)
            validate_response_payload(action, payload)
            result.rows = extract_rows(action, payload)
            result.items_collected = len(result.rows)
            result.pages_fetched = 1
            result.page_fetched = True
            result.expected_total = len(result.rows)
            result.is_complete = True
            result.retries = retries
            if payload.get("Warning"):
                result.warnings.append(str(payload["Warning"]))
        except BillingQueryError as exc:
            result.error = _error_dict(exc)
        return result

    rows: list[dict[str, Any]] = []
    items_collected = 0
    digests: set[str] = set()
    expected_total: int | None = None
    offset = config.page_offset if config.pagination == "page" else 0
    page_budget = 1 if config.pagination == "page" else config.max_pages
    for _ in range(page_budget):
        remaining = config.max_rows - len(rows)
        if remaining <= 0:
            result.warnings.append("查询因 max_rows 截断")
            break
        body = dict(normalized)
        request_limit = min(config.page_size, remaining)
        body["Limit"] = request_limit
        body["Offset"] = offset
        if "NeedRecordNum" in ACTION_SCHEMAS[action].request_params_by_name:
            body["NeedRecordNum"] = 1
        try:
            response, retries = _query_with_retry(client, action, body, config, sleeper)
            result.retries += retries
            payload = action_result(action, response)
            validate_response_payload(action, payload)
        except BillingQueryError as exc:
            result.error = _error_dict(exc)
            break
        if action in PAGED_ANALYSIS_ACTIONS:
            result.analysis_summary_rows.extend(extract_analysis_summary_rows(payload))
        page_rows = extract_rows(action, payload)
        page_items = _analysis_page_items(payload) if action in PAGED_ANALYSIS_ACTIONS else len(page_rows)
        result.pages_fetched += 1
        result.page_fetched = True
        if payload.get("Warning"):
            result.warnings.append(str(payload["Warning"]))
        returned_limit = payload.get("Limit")
        returned_offset = payload.get("Offset")
        if returned_limit is not None and returned_limit != request_limit:
            result.error = _error_dict(BillingQueryError(
                ErrorCode.PAGINATION_INCOMPLETE, "响应 Limit 与请求不一致", ExitCode.PARTIAL_RESULT,
                {"action": action, "requested_limit": request_limit, "returned_limit": returned_limit},
            ))
            break
        # ListFinancialRelation can return Offset=-1 even for a nonempty page.
        # Treat only this action/value as an absent echo, keeping the raw payload
        # untouched. Requests still advance by Limit and all coverage guards apply.
        offset_not_echoed = action == "ListFinancialRelation" and returned_offset == -1
        if offset_not_echoed:
            note = "ListFinancialRelation 响应 Offset=-1，未回显页偏移；按请求 Offset 推进分页并核验 Total、重复页和提前结束。"
            if note not in result.warnings:
                result.warnings.append(note)
        if returned_offset is not None and returned_offset != offset and not offset_not_echoed:
            result.error = _error_dict(BillingQueryError(
                ErrorCode.PAGINATION_INCOMPLETE, "响应 Offset 与请求不一致", ExitCode.PARTIAL_RESULT,
                {"action": action, "requested_offset": offset, "returned_offset": returned_offset},
            ))
            break
        raw_total = payload.get("Total")
        page_total = raw_total if isinstance(raw_total, int) and raw_total >= 0 else None
        total_changed = False
        if page_total is None:
            result.warnings.append("响应 Total 缺失或为 -1")
        elif expected_total is None:
            expected_total = page_total
        elif expected_total != page_total:
            total_changed = True
            if config.pagination != "full" or not current_period:
                result.stop_reason = "total_changed"
                result.last_observed_total = page_total
                result.error = _error_dict(BillingQueryError(ErrorCode.PAGINATION_INCOMPLETE, "分页过程中 Total 发生变化", ExitCode.PARTIAL_RESULT, {"first_total": expected_total, "current_total": page_total}))
                break
        if page_total is not None:
            result.last_observed_total = page_total
        if page_rows:
            digest = _page_digest(page_rows)
            if digest in digests:
                result.error = _error_dict(BillingQueryError(ErrorCode.PAGINATION_INCOMPLETE, "检测到重复分页", ExitCode.PARTIAL_RESULT, {"offset": offset}))
                break
            digests.add(digest)
            rows.extend(page_rows)
            if len(rows) > config.max_rows:
                del rows[config.max_rows :]
                result.warnings.append("查询因 max_rows 截断")
                break
        items_collected += page_items
        if config.pagination == "page":
            result.is_complete = (
                expected_total is not None
                and offset == 0
                and items_collected == expected_total
            )
            break
        if total_changed:
            result.stop_reason = "total_changed"
            result.initial_total_boundary_reached = (
                expected_total is not None and items_collected >= expected_total
            )
            if expected_total is not None and result.initial_total_boundary_reached:
                _mark_current_period_provisional(
                    result,
                    reason="current_period_total_drift",
                    stop_reason="total_changed",
                    expected_total=expected_total,
                    current_total=page_total,
                    items_collected=items_collected,
                )
            else:
                result.error = _error_dict(BillingQueryError(
                    ErrorCode.PAGINATION_INCOMPLETE,
                    "分页过程中 Total 发生变化，且尚未达到首次观测的 Total 边界",
                    ExitCode.PARTIAL_RESULT,
                    {
                        "first_total": expected_total,
                        "current_total": page_total,
                        "items_collected": items_collected,
                    },
                ))
            break
        if expected_total is not None:
            if items_collected == expected_total:
                result.is_complete = True
                break
            if items_collected > expected_total:
                result.stop_reason = "rows_exceeded_first_total"
                result.initial_total_boundary_reached = True
                if current_period:
                    _mark_current_period_provisional(
                        result,
                        reason="current_period_total_drift",
                        stop_reason="rows_exceeded_first_total",
                        expected_total=expected_total,
                        current_total=page_total,
                        items_collected=items_collected,
                    )
                else:
                    result.error = _error_dict(BillingQueryError(
                        ErrorCode.PAGINATION_INCOMPLETE,
                        "已采集行数超过 Total",
                        ExitCode.PARTIAL_RESULT,
                        {"first_total": expected_total, "items_collected": items_collected},
                    ))
                break
            if page_items == 0 or page_items < request_limit:
                result.error = _error_dict(BillingQueryError(ErrorCode.PAGINATION_INCOMPLETE, "分页提前结束，尚未达到 Total", ExitCode.PARTIAL_RESULT))
                break
        elif page_items < request_limit:
            result.is_complete = True
            break
        offset += request_limit
    result.rows = rows
    result.items_collected = items_collected
    result.expected_total = expected_total
    if (
        config.pagination == "full"
        and not result.is_complete
        and not result.is_provisional
        and result.error is None
    ):
        result.warnings.append("查询因 max_pages 或 max_rows 截断")
    return result


def aggregate_coverage(results: Sequence[QueryResult]) -> dict[str, Any]:
    known = all(result.expected_total is not None for result in results)
    query_coverage = [result.coverage() for result in results]
    provisional_queries = [item for item in query_coverage if item["is_provisional"]]
    failed_queries = [
        item
        for item in query_coverage
        if (
            item["error"] is not None
            or not item["page_fetched"]
            or (
                item["requested_scope"] == "full"
                and not item["is_complete"]
                and not item["is_provisional"]
            )
        )
    ]
    return {
        "pages_fetched": sum(result.pages_fetched for result in results),
        "rows_collected": sum(len(result.rows) for result in results),
        "expected_total": sum(result.expected_total or 0 for result in results) if known else None,
        "is_complete": all(result.is_complete for result in results),
        "is_provisional": bool(provisional_queries) and not failed_queries,
        "consistency": (
            "current_period_total_drift"
            if provisional_queries
            else "incomplete" if failed_queries else "stable"
        ),
        "requested_scope": (
            results[0].requested_scope
            if results and all(item.requested_scope == results[0].requested_scope for item in results)
            else "mixed"
        ),
        "requested_scope_fulfilled": all(
            result.page_fetched and result.error is None
            if result.requested_scope == "page"
            else result.is_complete or result.is_provisional
            for result in results
        ),
        "queries": query_coverage,
        "provisional_queries": provisional_queries,
        "failed_queries": failed_queries,
    }
