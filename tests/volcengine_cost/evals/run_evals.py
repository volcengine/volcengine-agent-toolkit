#!/usr/bin/env python3
"""执行 volcengine-cost 的确定性离线场景门禁。

本 runner 不调用真实 Billing，也不替代目标 Agent 宿主中的回答质量评测。它把
evals.json 的每条场景绑定到公开 CLI 的真实执行路径，检查契约、退出码、coverage、
字段语义和产物，防止文档预期与可执行能力漂移。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "core" / "volcengine-cost" / "scripts"))

from cost_query.billing.fetch import QueryResult, aggregate_coverage  # noqa: E402
from cost_query.arrears.resource_package import analyze_resource_package_attribution  # noqa: E402
from cost_query.arrears.coupon import analyze_coupon_attribution  # noqa: E402
from cost_query.common.cost_rules import (  # noqa: E402
    FieldResolver,
    atomic_write_csv,
    ensure_money_grouping,
    evidence_from_metadata,
    format_decimal,
    load_cost_csv,
    load_cost_metadata,
    parse_decimal,
    public_columns,
    public_rows,
    require_decimal,
    require_registered_money_metric,
    resolve_money_currency,
    typed_value,
)


ROOT = Path(__file__).resolve().parents[3] / "skills" / "core" / "volcengine-cost"
EVALS_PATH = Path(__file__).with_name("evals.json")
SCRIPTS = ROOT / "scripts"
RESOURCE_PACKAGE_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "resource_package" / "used_up"
COUPON_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "coupon" / "expired"


class EvalFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvalFailure(message)


def run_tool(script: str, *arguments: str, expected: int = 0) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    require(
        completed.returncode == expected,
        f"{script} exit={completed.returncode}, expected={expected}, stdout={completed.stdout!r}, stderr={completed.stderr!r}",
    )
    stream = completed.stdout if completed.returncode == 0 or completed.stdout.strip() else completed.stderr
    try:
        payload = json.loads(stream)
    except json.JSONDecodeError as exc:
        raise EvalFailure(f"{script} did not return JSON: {stream!r}") from exc
    return payload, completed


def task_error(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    meta = payload.get("_meta")
    require(isinstance(meta, Mapping) and isinstance(meta.get("error"), Mapping), f"missing error evidence: {payload}")
    return meta["error"]


def task_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result")
    if isinstance(result, list):
        return [dict(row) for row in result if isinstance(row, Mapping)]
    if isinstance(result, Mapping) and {"file", "metadata", "fields"}.issubset(result):
        path = Path(str(result["file"]))
        require(path.is_absolute() and path.is_file(), f"invalid result.file: {result}")
        return read_csv(path)
    raise EvalFailure(f"task result is not a row list or file: {result!r}")


def task_machine_meta(payload: Mapping[str, Any]) -> dict[str, Any]:
    meta = payload.get("_meta")
    require(isinstance(meta, Mapping), f"missing _meta: {payload}")
    result = dict(meta)
    evidence_file = result.get("evidence_file")
    if isinstance(evidence_file, str):
        evidence = json.loads(Path(evidence_file).read_text(encoding="utf-8"))
        require(isinstance(evidence, dict), f"invalid evidence file: {evidence_file}")
        return {**evidence, **result}
    return result


def paid_amount_actions() -> set[str]:
    actions: set[str] = set()
    for action in ("ListBill", "ListBillOverviewByProd", "ListBillOverviewByCategory"):
        payload, _ = run_tool(
            "cost.py", "schema", "--action", action, "--section", "response"
        )
        if any(path.endswith(".PaidAmount") for path in schema_paths(payload, "response")):
            actions.add(action)
    return actions


def schema_paths(payload: Mapping[str, Any], section: str) -> set[str]:
    root = payload[f"{section}_json_schema"]["properties"]
    paths: set[str] = set()

    def visit(properties: Mapping[str, Any], prefix: str = "") -> None:
        for name, schema in properties.items():
            path = f"{prefix}.{name}" if prefix else name
            paths.add(path)
            if schema.get("type") == "array":
                item_properties = schema.get("items", {}).get("properties", {})
                if item_properties:
                    visit(item_properties, f"{path}[]")
            nested_properties = schema.get("properties", {})
            if nested_properties:
                visit(nested_properties, path)

    visit(root)
    return paths


def schema_field(payload: Mapping[str, Any], section: str, field: str) -> Mapping[str, Any]:
    properties = payload[f"{section}_json_schema"]["properties"]
    if field in properties:
        return properties[field]
    list_properties = properties.get("List", {}).get("items", {}).get("properties", {})
    if field in list_properties:
        return list_properties[field]
    nested_list_properties = (
        list_properties.get("List", {})
        .get("items", {})
        .get("properties", {})
    )
    if field in nested_list_properties:
        return nested_list_properties[field]
    raise EvalFailure(f"{field} not found in {section} schema")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _load_processing_input(
    input_path: Path,
    action: str | None,
    metadata_path: Path | None = None,
) -> tuple[list[str], list[dict[str, str]], dict[str, Any] | None, Path | None, list[str]]:
    loaded_metadata_path, source_metadata, metadata_warnings = load_cost_metadata(input_path, metadata_path)
    columns, rows = load_cost_csv(input_path)
    source_action = action or (source_metadata.get("action") if source_metadata else None)
    if source_action == "ListCostAnalysisOpenApi" and "Amount" in columns and "Currency" not in columns:
        columns = [*columns, "Currency"]
        rows = [{**row, "Currency": "CNY"} for row in rows]
        metadata_warnings = [*metadata_warnings, "ListCostAnalysisOpenApi 响应不包含 Currency；Amount 按默认币种 CNY 处理。"]
    if source_action:
        columns = public_columns(str(source_action), columns)
        rows = public_rows(str(source_action), rows)
    return columns, rows, source_metadata, loaded_metadata_path, metadata_warnings


def direct_sum(
    input_path: Path,
    output_path: Path,
    *,
    metric: str,
    group_by: Sequence[str] = (),
    action: str | None = None,
    metadata_path: Path | None = None,
    filters: Sequence[tuple[str, str, Any]] = (),
    order_by_metric_desc: bool = False,
    limit: int | None = None,
    alias: str | None = None,
) -> dict[str, Any]:
    columns, rows, source_metadata, loaded_metadata_path, metadata_warnings = _load_processing_input(input_path, action, metadata_path)
    resolver = FieldResolver(columns, rows)
    metric_ref = resolver.resolve(metric)
    require_registered_money_metric(metric_ref, "sum")
    group_refs = [resolver.resolve(field) for field in group_by]
    group_refs, implicit_group_by = ensure_money_grouping(resolver, [metric_ref], group_refs)
    filter_refs = [(resolver.resolve(field), operator, value) for field, operator, value in filters]

    buckets: dict[tuple[str, ...], tuple[Decimal, int, int]] = {}
    filtered_count = 0
    for row in rows:
        if not all(_matches(row, ref, operator, value) for ref, operator, value in filter_refs):
            continue
        filtered_count += 1
        key = tuple(row.get(ref.column, "") for ref in group_refs)
        total, amount_count, row_count = buckets.get(key, (Decimal("0"), 0, 0))
        amount = parse_decimal(row.get(metric_ref.column, ""), metric_ref.column, allow_empty=True)
        if amount is None:
            buckets[key] = (total, amount_count, row_count + 1)
            continue
        buckets[key] = (total + amount, amount_count + 1, row_count + 1)

    metric_column = alias or metric_ref.column
    result_rows = [
        {
            **{ref.column: key[index] for index, ref in enumerate(group_refs)},
            metric_column: format_decimal(total) if amount_count else "",
            "row_count": str(row_count),
        }
        for key, (total, amount_count, row_count) in buckets.items()
    ]
    if order_by_metric_desc:
        present = [row for row in result_rows if row[metric_column] != ""]
        missing = [row for row in result_rows if row[metric_column] == ""]
        present.sort(key=lambda row: require_decimal(row[metric_column], metric_column), reverse=True)
        result_rows = present + missing
    else:
        result_rows.sort(key=lambda row: tuple(row.get(ref.column, "") for ref in group_refs))
    if limit is not None:
        result_rows = result_rows[:limit]

    output_columns = [ref.column for ref in group_refs] + [metric_column, "row_count"]
    atomic_write_csv(output_path, output_columns, result_rows, overwrite=True)
    warnings = list(metadata_warnings)
    missing_groups = sum(1 for _, amount_count, _ in buckets.values() if amount_count == 0)
    if missing_groups:
        warnings.append(f"{missing_groups} 个 SUM 聚合结果因输入值全部缺失而保持为空")
    metadata = {
        "schema_version": "1.0",
        "operation": "direct_sum",
        "input": {"csv": str(input_path.resolve()), "metadata": str(loaded_metadata_path.resolve()) if loaded_metadata_path else None},
        "output": {"csv": str(output_path.resolve()), "row_count": len(result_rows), "columns": output_columns},
        "calculation": {
            "metrics": [metric_ref.column],
            "group_by": [ref.column for ref in group_refs],
            "filtered_row_count": filtered_count,
            "implicit_group_by": [ref.to_dict() for ref in implicit_group_by],
            "missing_amount_count": sum(row_count - amount_count for _, amount_count, row_count in buckets.values()),
            "non_empty_amount_count": sum(amount_count for _, amount_count, _ in buckets.values()),
        },
        "evidence": evidence_from_metadata(source_metadata),
        "warnings": warnings,
    }
    write_json(output_path.with_suffix(".meta.json"), metadata)
    return {"status": "success", "evidence": metadata["evidence"], "calculation": metadata["calculation"]}


def direct_compare_periods(
    input_path: Path,
    output_path: Path,
    *,
    period_field: str,
    previous: str,
    current: str,
    metric: str,
    group_by: Sequence[str],
    action: str | None = None,
) -> dict[str, Any]:
    columns, rows, source_metadata, loaded_metadata_path, metadata_warnings = _load_processing_input(input_path, action)
    resolver = FieldResolver(columns, rows)
    period_ref = resolver.resolve(period_field)
    metric_ref = resolver.resolve(metric)
    require_registered_money_metric(metric_ref, "compare")
    group_refs = [resolver.resolve(field) for field in group_by]
    group_refs, implicit_group_by = ensure_money_grouping(resolver, [metric_ref], group_refs)
    buckets: dict[tuple[str, ...], dict[str, tuple[Decimal, int]]] = defaultdict(dict)
    for row in rows:
        period = row.get(period_ref.column, "")
        if period not in {previous, current}:
            continue
        key = tuple(row.get(ref.column, "") for ref in group_refs)
        total, count = buckets[key].get(period, (Decimal("0"), 0))
        amount = parse_decimal(row.get(metric_ref.column, ""), metric_ref.column, allow_empty=True)
        if amount is None:
            buckets[key][period] = (total, count)
            continue
        buckets[key][period] = (total + amount, count + 1)
    rows_out: list[dict[str, str]] = []
    deltas_by_currency: dict[tuple[str, ...], Decimal] = defaultdict(lambda: Decimal("0"))
    currency_ref = resolve_money_currency(resolver, metric_ref)
    currency_columns = [currency_ref.column] if currency_ref is not None else []
    for key, values in buckets.items():
        prev_total, prev_count = values.get(previous, (Decimal("0"), 0))
        curr_total, curr_count = values.get(current, (Decimal("0"), 0))
        delta = curr_total - prev_total if prev_count and curr_count else None
        row = {ref.column: key[index] for index, ref in enumerate(group_refs)}
        row.update(
            {
                "previous_period": previous,
                "current_period": current,
                "previous_value": format_decimal(prev_total) if prev_count else "",
                "current_value": format_decimal(curr_total) if curr_count else "",
                "delta": format_decimal(delta) if delta is not None else "",
                "delta_rate": _format_rate(delta / prev_total) if delta is not None and prev_total != 0 else "",
                "abs_delta": format_decimal(abs(delta)) if delta is not None else "",
                "delta_contribution_rate": "",
                "presence": "both" if prev_count and curr_count else "current_only" if curr_count else "previous_only",
            }
        )
        if delta is not None:
            partition = tuple(row[column] for column in currency_columns)
            deltas_by_currency[partition] += delta
        rows_out.append(row)
    for row in rows_out:
        if row["delta"] == "":
            continue
        partition = tuple(row[column] for column in currency_columns)
        denominator = deltas_by_currency[partition]
        row["delta_contribution_rate"] = _format_rate(require_decimal(row["delta"], "delta") / denominator) if denominator else ""
    rows_out.sort(key=lambda row: require_decimal(row["delta"], "delta") if row["delta"] else Decimal("-Infinity"), reverse=True)
    output_columns = [ref.column for ref in group_refs] + [
        "previous_period",
        "current_period",
        "previous_value",
        "current_value",
        "delta",
        "delta_rate",
        "abs_delta",
        "delta_contribution_rate",
        "presence",
    ]
    atomic_write_csv(output_path, output_columns, rows_out, overwrite=True)
    metadata = {
        "schema_version": "1.0",
        "operation": "direct_compare_periods",
        "input": {"csv": str(input_path.resolve()), "metadata": str(loaded_metadata_path.resolve()) if loaded_metadata_path else None},
        "output": {"csv": str(output_path.resolve()), "row_count": len(rows_out), "columns": output_columns},
        "calculation": {
            "metrics": [metric_ref.column],
            "group_by": [ref.column for ref in group_refs],
            "period_field": period_ref.column,
            "previous": previous,
            "current": current,
            "implicit_group_by": [ref.to_dict() for ref in implicit_group_by],
        },
        "evidence": evidence_from_metadata(source_metadata),
        "warnings": metadata_warnings,
    }
    write_json(output_path.with_suffix(".meta.json"), metadata)
    return {"status": "success", "evidence": metadata["evidence"], "calculation": metadata["calculation"]}


def _format_rate(value: Decimal) -> str:
    formatted = value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    return format(formatted, "f").rstrip("0").rstrip(".") or "0"


def _matches(row: Mapping[str, str], ref, operator: str, value: Any) -> bool:
    current = typed_value(row.get(ref.column, ""), ref)
    if operator == "eq":
        return current == value
    if operator == "in":
        return current in set(value)
    raise EvalFailure(f"unsupported eval helper filter operator: {operator}")


def write_reconciliation_artifact(
    root: Path,
    name: str,
    action: str,
    columns: list[str],
    rows: list[dict[str, str]],
    *,
    request_extra: dict[str, Any] | None = None,
) -> Path:
    source = root / f"{name}.csv"
    fields = root / f"{name}.fields.json"
    metadata = root / f"{name}.meta.json"
    request_body = {
        "BillPeriod": "2026-07",
        "Limit": 300,
        "Offset": 0,
        "NeedRecordNum": 1,
        **(request_extra or {}),
    }
    query_result = QueryResult(
        query_id="2026-07",
        action=action,
        request_body=request_body,
        rows=list(rows),
        items_collected=len(rows),
        pages_fetched=1,
        expected_total=len(rows),
        is_complete=True,
        last_observed_total=len(rows),
        requested_scope="full",
        page_fetched=True,
    )
    write_csv(
        source,
        ["_action", "_query_id", *columns],
        [{"_action": action, "_query_id": "2026-07", **row} for row in rows],
    )
    write_json(fields, {
        "schema_version": "1.0",
        "source_action": action,
        "fields": [{"field": column} for column in ["_action", "_query_id", *columns]],
    })
    write_json(metadata, {
        "schema_version": "1.0",
        "action": action,
        "coverage": aggregate_coverage([query_result]),
        "freshness": {"partial_period": False, "notes": []},
        "queries": [{
            "query_id": query_result.query_id,
            "request_body": query_result.request_body,
            "coverage": query_result.coverage(),
        }],
        "artifacts": {
            "csv": str(source.resolve()),
            "fields": str(fields.resolve()),
            "metadata": str(metadata.resolve()),
        },
    })
    return source


def reconciliation_fixture(root: Path) -> tuple[Path, Path]:
    common = ["BillDetailId", "Product", "InstanceNo", "Project", "PayableAmount", "Currency"]
    left = write_reconciliation_artifact(
        root, "bill-detail", "ListBillDetail", common,
        [
            {"BillDetailId": "d-1", "Product": "ECS", "InstanceNo": "i-1", "Project": "billing-project", "PayableAmount": "100", "Currency": "CNY"},
            {"BillDetailId": "d-2", "Product": "ECS", "InstanceNo": "i-2", "Project": "billing-project", "PayableAmount": "50", "Currency": "CNY"},
        ],
        request_extra={"GroupPeriod": 2, "GroupTerm": 0},
    )
    right = write_reconciliation_artifact(
        root, "split-detail", "ListSplitBillDetail", [*common, "SplitItemID"],
        [
            {"BillDetailId": "d-1", "SplitItemID": "s-1", "Product": "ECS", "InstanceNo": "i-1", "Project": "project-a", "PayableAmount": "60", "Currency": "CNY"},
            {"BillDetailId": "d-1", "SplitItemID": "s-2", "Product": "ECS", "InstanceNo": "i-1", "Project": "project-b", "PayableAmount": "30", "Currency": "CNY"},
            {"BillDetailId": "d-2", "SplitItemID": "s-3", "Product": "ECS", "InstanceNo": "i-2", "Project": "project-a", "PayableAmount": "50", "Currency": "CNY"},
        ],
        request_extra={"GroupPeriod": 2},
    )
    return left, right


def bill_detail_response(rows: list[dict[str, Any]], *, total: int, limit: int, offset: int) -> dict[str, Any]:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": {"Warning": "", "List": rows, "Total": total, "Limit": limit, "Offset": offset},
    }


def cost_analysis_response(cost_data: list[dict[str, Any]], *, total: int, limit: int, offset: int) -> dict[str, Any]:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": {"CostData": cost_data, "Total": total, "Limit": limit, "Offset": offset},
    }


def bill_response(rows: list[dict[str, Any]], *, total: int, limit: int, offset: int) -> dict[str, Any]:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": {"List": rows, "Total": total, "Limit": limit, "Offset": offset},
    }


def split_bill_response(rows: list[dict[str, Any]], *, total: int, limit: int, offset: int, warning: str = "") -> dict[str, Any]:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": {"Warning": warning, "List": rows, "Total": total, "Limit": limit, "Offset": offset},
    }


def amortized_response(rows: list[dict[str, Any]], *, total: int, limit: int, offset: int, warning: str = "") -> dict[str, Any]:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": {"Warning": warning, "List": rows, "Total": total, "Limit": limit, "Offset": offset},
    }


def filter_info_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ResponseMetadata": {"Error": None},
        "Result": payload,
    }


def balance_response(**overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "AccountID": 2100000000,
        "ArrearsBalance": "328.500000",
        "AvailableBalance": "-328.500000",
        "CashBalance": "0.000000",
        "CreditLimit": "0.000000",
        "FreezeAmount": "0.000000",
        "Currency": "CNY",
    }
    result.update(overrides)
    return {
        "ResponseMetadata": {"Error": None, "RequestId": "request-balance-eval"},
        "Result": result,
    }


def verifier_01_monthly_product_payable(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListCostAnalysisOpenApi__period-2026-01-01__offset-0.json",
        cost_analysis_response(
            [{"ClassifyDimension": 3, "ClassifyItem": "ECS", "Costs": [{"TimeStr": "2026-01", "Amount": "10"}]}],
            total=1, limit=300, offset=0,
        ),
    )
    output = root / "trend.csv"
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListCostAnalysisOpenApi",
        "--body", '{"BeginTimeStr":"2026-01-01","EndTimeStr":"2026-06-01","TimeGranularity":0,"CostType":2,"ClassifyDimension":3}',
        "--pagination", "full", "--fixture-dir", str(fixture), "--out", str(output),
    )
    metadata = json.loads((root / "trend.meta.json").read_text())
    require(manifest["status"] == "success" and metadata["coverage"]["is_complete"], "full trend is not complete")
    request = metadata["queries"][0]["request_body"]
    require((request["CostType"], request["TimeGranularity"], request["ClassifyDimension"]) == (2, 0, 3), "wrong trend plan")
    return {"action": manifest["_meta"]["action"], "status": manifest["status"]}


def verifier_02_full_bill_detail(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    row = lambda index: {"BillDetailId": f"detail-{index}", "ProductZh": "云服务器", "PayableAmount": str(index), "Currency": "CNY"}
    write_json(fixture / "ListBillDetail__period-2026-07__offset-0.json", bill_detail_response([row(1), row(2)], total=3, limit=2, offset=0))
    write_json(fixture / "ListBillDetail__period-2026-07__offset-2.json", bill_detail_response([row(3)], total=3, limit=2, offset=2))
    output = root / "detail.csv"
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListBillDetail", "--body", '{"BillPeriod":"2026-07"}',
        "--pagination", "full", "--page-size", "2", "--fixture-dir", str(fixture), "--out", str(output),
    )
    metadata = json.loads((root / "detail.meta.json").read_text(encoding="utf-8"))
    require(metadata["coverage"]["is_complete"] and manifest["_meta"]["row_count"] == 3, "full pagination is incomplete")
    require(Path(manifest["result"]["file"]).is_file(), "query result file is missing")
    return {"rows": manifest["_meta"]["row_count"], "coverage": "complete"}


def verifier_03_second_page(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListBillDetail__period-2026-07__offset-100.json",
        bill_detail_response([{"BillDetailId": "detail-101", "PayableAmount": "1", "Currency": "CNY"}], total=300, limit=100, offset=100),
    )
    output = root / "page.csv"
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListBillDetail", "--body", '{"BillPeriod":"2026-07"}',
        "--pagination", "page", "--page-size", "100", "--page-offset", "100",
        "--fixture-dir", str(fixture), "--out", str(output),
    )
    require(manifest["status"] == "success", "page query failed")
    metadata = json.loads((root / "page.meta.json").read_text(encoding="utf-8"))
    require(metadata["coverage"]["is_complete"] is False, "second page must not claim complete dataset")
    return {"status": manifest["status"], "is_complete": False}


def verifier_04_cash_cost_boundary(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    error, _ = run_tool(
        "cost.py", "query", "--action", "ListCostAnalysisOpenApi",
        "--body", '{"BeginTimeStr":"2026-04-01","EndTimeStr":"2026-06-01","TimeGranularity":0,"CostType":7,"ClassifyDimension":3,"Limit":10,"Offset":0}',
        "--pagination", "full", "--fixture-dir", str(fixture), "--out", str(root / "never.csv"), expected=2,
    )
    require(task_error(error)["code"] == "INVALID_ARGUMENT", "cash cost type was not rejected")
    actions = paid_amount_actions()
    require(actions == {"ListBill", "ListBillOverviewByProd", "ListBillOverviewByCategory"}, f"PaidAmount exposure drifted: {actions}")
    return {"rejected_cost_type": 7, "paid_actions": sorted(actions)}


def verifier_05_product_top10(root: Path) -> dict[str, Any]:
    source = root / "bill.csv"
    write_csv(source, ["ProductZh", "PayableAmount", "Currency"], [
        {"ProductZh": "云服务器", "PayableAmount": "10.10", "Currency": "CNY"},
        {"ProductZh": "云服务器", "PayableAmount": "2.20", "Currency": "CNY"},
        {"ProductZh": "对象存储", "PayableAmount": "5", "Currency": "CNY"},
        {"ProductZh": "云服务器", "PayableAmount": "3", "Currency": "USD"},
    ])
    output = root / "top10.csv"
    manifest = direct_sum(
        source,
        output,
        action="ListBill",
        metric="payable_amount",
        group_by=["product_zh"],
        order_by_metric_desc=True,
        limit=10,
        alias="payable",
    )
    metadata = json.loads((root / "top10.meta.json").read_text())
    require([item["field"] for item in metadata["calculation"]["implicit_group_by"]] == ["Currency"], "currency was not implicitly grouped")
    rows = read_csv(output)
    require(rows[0]["payable"] == "12.30" and rows[0]["Currency"] == "CNY", "TopN aggregation mismatch")
    return {"status": manifest["status"], "implicit_group_by": "Currency"}


def verifier_06_no_metadata(root: Path) -> dict[str, Any]:
    source = root / "source.csv"
    write_csv(source, ["Product", "PayableAmount", "Currency"], [{"Product": "ECS", "PayableAmount": "1", "Currency": "CNY"}])
    rows = read_csv(source)
    totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        totals[(row["Product"], row["Currency"])] += require_decimal(row["PayableAmount"], "PayableAmount")
    require(totals[("ECS", "CNY")] == Decimal("1"), "one-off CSV sum mismatch")
    require(not (root / "result.csv").exists(), "one-off CSV sum unexpectedly created a derived artifact")
    return {"claim_scope": "input_file_only", "processing": "short_python", "derived_artifact": False}


def verifier_12_latest_cash_boundary(root: Path) -> dict[str, Any]:
    actions = paid_amount_actions()
    require(actions == {"ListBill", "ListBillOverviewByProd", "ListBillOverviewByCategory"}, "PaidAmount boundary drifted")
    return {"paid_actions": sorted(actions)}


def verifier_15_response_field_correction(root: Path) -> dict[str, Any]:
    bad, _ = run_tool(
        "cost.py", "schema", "--action", "ListBillOverviewByProd", "--section", "response",
        "--field", "ProductName", "--field", "OriginalAmount", "--field", "DiscountAmount", "--field", "PaidAmount", expected=2,
    )
    require(task_error(bad)["code"] == "INVALID_ARGUMENT", "invalid field set was accepted")
    good, _ = run_tool(
        "cost.py", "schema", "--action", "ListBillOverviewByProd", "--section", "response",
        "--field", "ProductZh", "--field", "PayableAmount", "--field", "OriginalBillAmount",
        "--field", "DiscountBillAmount", "--field", "PaidAmount",
    )
    paths = schema_paths(good, "response")
    expected = {f"List[].{field}" for field in ("ProductZh", "PayableAmount", "OriginalBillAmount", "DiscountBillAmount", "PaidAmount")}
    require(expected <= paths, f"corrected response fields drifted: {paths}")
    return {"invalid_fields_rejected": True, "corrected_fields": sorted(expected)}


def verifier_16_compact_bill_detail_request_guidance(root: Path) -> dict[str, Any]:
    request_payload, _ = run_tool(
        "cost.py", "schema", "--action", "ListBillDetail",
        "--section", "request", "--include-guidance"
    )
    require(request_payload["section"] == "request", "request contract section drifted")
    require("preaggregation_guidance" in request_payload, "single planning contract missing preaggregation guidance")
    require("field_grain_guidance" in request_payload, "single planning contract missing field grain guidance")
    require("business_constraints" in request_payload, "single planning contract missing business guidance")
    decision = request_payload["agent_decisions"]["GroupPeriod"]
    require("details_command" not in decision, "loaded decision card requested another schema call")
    require(set(decision["values"]) == {"0", "1", "2"}, "GroupPeriod values drifted")
    require(any(item["value"] == 2 for item in decision["choose"]), "detail selection rule missing")
    require("GroupTerm" in decision["related_request_fields"], "related GroupTerm missing")

    fixture = root / "fixture"
    fixture.mkdir()
    error, _ = run_tool(
        "cost.py", "query", "--action", "ListBillDetail",
        "--body", '{"BillPeriod":"2026-07","Usage":true,"UnitPrice":true}',
        "--pagination", "page", "--page-size", "1",
        "--fixture-dir", str(fixture), expected=2,
    )
    execution_error = task_error(error)
    require(execution_error["code"] == "RESPONSE_FIELDS_IN_REQUEST_BODY", "recoverable error code drifted")
    require(execution_error["details"]["possible_response_fields"]["Usage"]["response_field"] == "Count", "usage recovery missing")
    require(execution_error["details"]["possible_response_fields"]["UnitPrice"]["response_field"] == "Price", "price recovery missing")
    return {
        "field_decisions": True,
        "single_describe": "request_with_guidance",
        "recoverable_error": "RESPONSE_FIELDS_IN_REQUEST_BODY",
    }


def verifier_17_compare_periods(root: Path) -> dict[str, Any]:
    source = root / "analysis.csv"
    write_csv(source, ["ClassifyItem", "TimeStr", "Amount"], [
        {"ClassifyItem": "ECS", "TimeStr": "2026-06", "Amount": "10"},
        {"ClassifyItem": "ECS", "TimeStr": "2026-07", "Amount": "15"},
        {"ClassifyItem": "TOS", "TimeStr": "2026-06", "Amount": "5"},
        {"ClassifyItem": "TOS", "TimeStr": "2026-07", "Amount": "1"},
    ])
    write_json(
        root / "analysis.meta.json",
        {"action": "ListCostAnalysisOpenApi", "coverage": {"is_complete": True}, "freshness": {"partial_period": False}},
    )
    output = root / "drivers.csv"
    manifest = direct_compare_periods(
        source,
        output,
        action="ListCostAnalysisOpenApi",
        period_field="TimeStr",
        previous="2026-06",
        current="2026-07",
        metric="Amount",
        group_by=["ClassifyItem"],
    )
    metadata = json.loads((root / "drivers.meta.json").read_text(encoding="utf-8"))
    rows = read_csv(output)
    require(manifest["status"] == "success", "operation mismatch")
    require(metadata["evidence"]["claim_scope"] == "full_dataset", "evidence not inherited")
    require(metadata["calculation"]["implicit_group_by"][0]["field"] == "Currency", "analysis default currency missing")
    require(rows[0]["ClassifyItem"] == "ECS" and rows[0]["delta"] == "5", f"delta ordering mismatch: {rows}")
    require(rows[0]["delta_rate"] == "0.5", f"delta_rate mismatch: {rows[0]}")
    require(rows[0]["delta_contribution_rate"] == "5", f"contribution mismatch: {rows[0]}")
    require(rows[1]["delta_contribution_rate"] == "-4", f"negative contribution mismatch: {rows[1]}")
    require(rows[0]["presence"] == "both", "presence missing")
    return {"operation": metadata["operation"], "first_delta": rows[0]["delta"], "claim_scope": metadata["evidence"]["claim_scope"]}


def verifier_18_default_compact_result(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListBill__period-2026-07__offset-0.json",
        {
            "ResponseMetadata": {"Error": None},
            "Result": {
                "List": [{
                    "BillID": "bill-1",
                    "ProductZh": "云服务器",
                    "PayableAmount": "10",
                    "Currency": "CNY",
                    "PayerID": "payer-sensitive",
                    "PayerUserName": "payer-name-sensitive",
                    "OwnerID": "owner-sensitive",
                }],
                "Total": 8, "Limit": 1, "Offset": 0,
            },
        },
    )
    common = (
        "cost.py", "query", "--action", "ListBill",
        "--body", '{"BillPeriod":"2026-07"}',
        "--pagination", "page", "--page-size", "1",
        "--fixture-dir", str(fixture),
    )
    manifest, _ = run_tool(*common)
    require(isinstance(manifest["result"], list), "small result was not inlined")
    require(manifest["result"][0]["PayerID"] == "payer-sensitive", "complete inline row missing field")
    require("coverage" not in {key: value for key, value in manifest.items() if key != "_meta"}, "coverage leaked into public fields")
    return {
        "reused_confirmed_contract": True,
        "result_location": "inline",
        "artifacts": [],
        "stdout_has_coverage": False,
    }


def verifier_19_bill_sample_amounts(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListBill__period-2026-07__offset-0.json",
        bill_response(
            [
                {"BillID": "bill-1", "ProductZh": "云服务器", "PayableAmount": "10.50", "PaidAmount": "3.25", "UnpaidAmount": "7.25", "Currency": "CNY"},
                {"BillID": "bill-2", "ProductZh": "对象存储", "PayableAmount": "5.50", "PaidAmount": "5.50", "UnpaidAmount": "0", "Currency": "CNY"},
            ],
            total=42,
            limit=20,
            offset=0,
        ),
    )
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListBill",
        "--body", '{"BillPeriod":"2026-07"}',
        "--pagination", "page", "--page-size", "20", "--page-offset", "0",
        "--fixture-dir", str(fixture),
    )
    require(manifest["status"] == "success", "sample query failed")
    require(isinstance(manifest["result"], list), "sample should stay inline")
    totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {name: Decimal("0") for name in ("payable", "paid", "unpaid")}
    )
    for row in manifest["result"]:
        totals[row["Currency"]]["payable"] += require_decimal(row["PayableAmount"], "PayableAmount")
        totals[row["Currency"]]["paid"] += require_decimal(row["PaidAmount"], "PaidAmount")
        totals[row["Currency"]]["unpaid"] += require_decimal(row["UnpaidAmount"], "UnpaidAmount")
    amounts = totals["CNY"]
    require(tuple(format_decimal(amounts[name]) for name in ("payable", "paid", "unpaid")) == ("16.00", "8.75", "7.25"), f"sample sums mismatch: {amounts}")
    require(not list(root.glob("*.csv")), "inline sample unexpectedly created CSV files")
    return {"status": manifest["status"], "sample_rows": manifest["_meta"]["row_count"], "payable": "16.00", "is_complete": False, "processing": "inline"}


def verifier_20_multi_month_partial(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListBill__period-2026-06__offset-0.json",
        bill_response(
            [{"BillID": "june-1", "BillPeriod": "2026-06", "PayableAmount": "1", "Currency": "CNY"}],
            total=1,
            limit=300,
            offset=0,
        ),
    )
    write_json(
        fixture / "ListBill__period-2026-07__offset-0.json",
        {"__error__": {"code": "TIMEOUT", "message": "fixture timeout"}},
    )
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListBill",
        "--body", '{"BillPeriod":"2026-01"}',
        "--period", "2026-06", "--period", "2026-07",
        "--pagination", "full", "--fixture-dir", str(fixture),
        "--out", str(root / "multi.csv"), expected=6,
    )
    require(manifest["status"] == "partial", "multi-month query should be partial")
    require(manifest["_meta"]["row_count"] == 1, "successful month row should be preserved")
    meta = json.loads((root / "multi.meta.json").read_text(encoding="utf-8"))
    coverage = meta["coverage"]
    failed = coverage["failed_queries"]
    require(coverage["is_complete"] is False and failed[0]["query_id"] == "2026-07", f"failed month missing: {coverage}")
    require(meta["coverage"]["failed_queries"] == failed, "metadata failed queries not preserved")
    return {"status": manifest["status"], "failed_queries": failed, "preserved_rows": manifest["_meta"]["row_count"]}


def verifier_21_bill_id_local_filter_plan(root: Path) -> dict[str, Any]:
    bad, _ = run_tool(
        "cost.py", "query", "--action", "ListBill",
        "--body", '{"BillPeriod":"2026-07","BillID":"bill-target"}',
        "--pagination", "page", "--page-size", "1",
        "--fixture-dir", str(root), expected=2,
    )
    require(task_error(bad)["code"] == "INVALID_ARGUMENT", "BillID in request body should be rejected")
    response, _ = run_tool(
        "cost.py", "schema", "--action", "ListBill",
        "--section", "response", "--field", "BillID", "--field", "BillPeriod",
        "--field", "ProductZh", "--field", "PayStatus", "--field", "PayableAmount",
    )
    paths = schema_paths(response, "response")
    require({"List[].BillID", "List[].BillPeriod", "List[].ProductZh", "List[].PayStatus", "List[].PayableAmount"} <= paths, "required response fields missing")
    rows = [
        {"BillID": "bill-other", "BillPeriod": "2026-07", "ProductZh": "TOS", "PayStatus": "已结清", "PayableAmount": "1", "Currency": "CNY"},
        {"BillID": "bill-target", "BillPeriod": "2026-07", "ProductZh": "ECS", "PayStatus": "未结清", "PayableAmount": "9", "Currency": "CNY"},
    ]
    matched = [row for row in rows if row["BillID"] == "bill-target"]
    require(len(matched) == 1 and matched[0]["ProductZh"] == "ECS", f"BillID filter mismatch: {matched}")
    require(not list(root.glob("*.csv")), "one-off BillID filter unexpectedly created derived files")
    return {"request_filter_supported": False, "local_filter_rows": len(matched), "fields": sorted(paths), "processing": "inline_or_short_python"}


def verifier_23_split_project_attribution(root: Path) -> dict[str, Any]:
    response, _ = run_tool(
        "cost.py", "schema", "--action", "ListSplitBillDetail", "--section", "response",
        "--field", "Project", "--field", "ProjectDisplayName", "--field", "SplitItemID",
        "--field", "SplitItemName", "--field", "PayableAmount",
    )
    paths = schema_paths(response, "response")
    require({"List[].Project", "List[].ProjectDisplayName", "List[].SplitItemID", "List[].SplitItemName", "List[].PayableAmount"} <= paths, "split response fields missing")
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListSplitBillDetail__period-2026-07__offset-0.json",
        split_bill_response(
            [
                {"Project": "p1", "ProjectDisplayName": "项目一", "SplitItemID": "s1", "SplitItemName": "资源一", "PayableAmount": "10", "Currency": "CNY"},
                {"Project": "p1", "ProjectDisplayName": "项目一", "SplitItemID": "s2", "SplitItemName": "资源二", "PayableAmount": "5", "Currency": "CNY"},
                {"Project": "p2", "ProjectDisplayName": "项目二", "SplitItemID": "s3", "SplitItemName": "资源三", "PayableAmount": "2", "Currency": "CNY"},
            ],
            total=3,
            limit=300,
            offset=0,
        ),
    )
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListSplitBillDetail",
        "--body", '{"BillPeriod":"2026-07","GroupPeriod":2}',
        "--pagination", "full", "--fixture-dir", str(fixture),
    )
    require(manifest["status"] == "success", "split full query incomplete")
    require(isinstance(manifest["result"], list), "small project summary should use inline rows")
    totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for row in manifest["result"]:
        totals[(row["ProjectDisplayName"], row["Currency"])] += require_decimal(row["PayableAmount"], "PayableAmount")
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    require(ranked[0] == (("项目一", "CNY"), Decimal("15")), f"project summary mismatch: {ranked}")
    require(not list(root.glob("*.csv")), "inline project summary unexpectedly created derived files")
    return {"action": manifest["_meta"]["action"], "top_project": ranked[0][0][0], "payable": format_decimal(ranked[0][1]), "processing": "inline"}


def verifier_24_tag_key_requires_value(root: Path) -> dict[str, Any]:
    error, _ = run_tool(
        "cost.py", "query", "--action", "ListSplitBillDetail",
        "--body", '{"BillPeriod":"2026-07","Limit":10,"TagKV":[{"Key":"volc-Key"}]}',
        "--pagination", "page", "--page-size", "10", "--fixture-dir", str(root),
        "--out", str(root / "invalid_tag.csv"), expected=2,
    )
    query_error = task_error(error)
    require(query_error["code"] == "INVALID_ARGUMENT", "Key-only TagKV should be rejected")
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "GetFilterInfoForCostAnalysis__period-2026-07-01__offset-0.json",
        filter_info_response({"TagKeyList": ["ByteUser", "volc-Key"], "ProductList": []}),
    )
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "GetFilterInfoForCostAnalysis",
        "--body", '{"TimeGranularity":0,"BeginTimeStr":"2026-07-01","EndTimeStr":"2026-07-01"}',
        "--fixture-dir", str(fixture),
    )
    tag_keys = [
        row["Value"]
        for row in manifest["result"]
        if row.get("Catalog") == "TagKeyList"
    ]
    require("volc-Key" in tag_keys, "tag key not discovered")
    require(isinstance(manifest["result"], list), "filter catalog should be inline without artifacts")
    return {"key_only_rejected": True, "discovered_tag_keys": tag_keys, "requires_value": True}


def verifier_29_secret_body_rejected(root: Path) -> dict[str, Any]:
    error, _ = run_tool(
        "cost.py", "query", "--action", "ListBill",
        "--body", '{"BillPeriod":"2026-07","AccessKey":"AKLTSECRET","SecretKey":"SKSECRET"}',
        "--pagination", "page", "--page-size", "1",
        "--fixture-dir", str(root), expected=2,
    )
    serialized = json.dumps(error, ensure_ascii=False)
    require(task_error(error)["code"] == "INVALID_ARGUMENT", "secret fields should be rejected as contract extras")
    require("SKSECRET" not in serialized and "AKLTSECRET" not in serialized, "secret value leaked in error payload")
    return {"rejected": True, "secret_values_leaked": False, "auth_surface": "ve-cli-profile-or-env"}


def verifier_30_page_and_missing_field_boundaries(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListBill__period-2026-07__offset-0.json",
        bill_response(
            [{"BillID": "bill-1", "ProductZh": "ECS", "PayableAmount": "10", "Currency": "CNY"}],
            total=10,
            limit=1,
            offset=0,
        ),
    )
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListBill",
        "--body", '{"BillPeriod":"2026-07"}',
        "--pagination", "page", "--page-size", "1", "--fixture-dir", str(fixture), "--out", str(root / "first_page.csv"),
    )
    metadata = json.loads((root / "first_page.meta.json").read_text(encoding="utf-8"))
    require(manifest["status"] == "success" and metadata["coverage"]["is_complete"] is False, "first page boundary mismatch")
    partial_meta = root / "partial_source.meta.json"
    write_json(partial_meta, {"action": "ListBill", "coverage": {"is_complete": False, "failed_queries": [{"query_id": "page-only"}]}, "freshness": {"partial_period": False}})
    source = root / "partial_source.csv"
    write_csv(source, ["ProductZh", "PayableAmount", "Currency"], [{"ProductZh": "ECS", "PayableAmount": "10", "Currency": "CNY"}])
    analysis = direct_sum(
        source,
        root / "partial_result.csv",
        metadata_path=partial_meta,
        action="ListBill",
        metric="PayableAmount",
        group_by=["ProductZh"],
        alias="payable",
    )
    require(analysis["evidence"]["claim_scope"] == "partial_dataset", "partial evidence not preserved")
    return {"page_status": manifest["status"], "full_total_allowed": False, "missing_field_zero": False, "claim_scope": analysis["evidence"]["claim_scope"]}


def verifier_31_reconciliation_preflight_and_run(root: Path) -> dict[str, Any]:
    left, right = reconciliation_fixture(root)
    preflight, _ = run_tool(
        "cost.py", "reconcile", "preflight",
        "--left", str(left), "--right", str(right),
        "--group-by", "Product,InstanceNo", "--metric", "PayableAmount",
    )
    require(preflight["verdict"] == "pass", f"reconciliation preflight failed: {preflight}")
    output = root / "reconciliation.csv"
    manifest, _ = run_tool(
        "cost.py", "reconcile", "run",
        "--left", str(left), "--right", str(right),
        "--group-by", "Product,InstanceNo", "--metric", "PayableAmount",
        "--out", str(output),
    )
    with output.open(encoding="utf-8") as file:
        rows = {row["InstanceNo"]: row for row in csv.DictReader(file)}
    require(rows["i-1"]["difference_PayableAmount"] == "-10", f"difference mismatch: {rows}")
    require(rows["i-2"]["status"] == "matched", f"matched bucket missing: {rows}")
    require(manifest["_meta"]["status_counts"]["mismatched"] == 1, "mismatched count drifted")
    metadata = json.loads((root / "reconciliation.meta.json").read_text(encoding="utf-8"))
    require(metadata["plan"]["effective_join_keys"] == ["Product", "InstanceNo", "Currency"], "currency join key missing")
    return {"verdict": preflight["verdict"], "difference": "-10", "join_keys": metadata["plan"]["effective_join_keys"]}


def verifier_32_project_semantic_warning(root: Path) -> dict[str, Any]:
    left, right = reconciliation_fixture(root)
    warned, _ = run_tool(
        "cost.py", "reconcile", "preflight",
        "--left", str(left), "--right", str(right), "--group-by", "Project",
    )
    require(warned["verdict"] == "warn" and warned["claim_scope"] == "observational", f"Project warning drifted: {warned}")
    output = root / "project-comparison.csv"
    manifest, _ = run_tool(
        "cost.py", "reconcile", "run",
        "--left", str(left), "--right", str(right), "--group-by", "Project", "--out", str(output),
    )
    require("来源与语义可能不同" in manifest["message"], "Project limitation missing from Agent-visible message")
    metadata = json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8"))
    require(metadata["plan"]["mode"] == "reconciliation", "nonstandard dimension must not switch mode")
    return {"default": "warn", "claim_scope": "observational", "mode": "reconciliation"}


def verifier_34_reconciliation_mismatch_boundary(root: Path) -> dict[str, Any]:
    left, right = reconciliation_fixture(root)
    output = root / "reconciliation.csv"
    manifest, _ = run_tool(
        "cost.py", "reconcile", "run",
        "--left", str(left), "--right", str(right),
        "--group-by", "Product,InstanceNo", "--metric", "PayableAmount",
        "--out", str(output),
    )
    require(manifest["_meta"]["status_counts"]["mismatched"] == 1, "fixture should produce one mismatch")
    metadata = json.loads((root / "reconciliation.meta.json").read_text(encoding="utf-8"))
    return {
        "mismatch_rows": manifest["_meta"]["status_counts"]["mismatched"],
        "root_cause_inference_allowed": False,
        "split_bill_role": metadata["interpretation"]["authoritative_sources"]["split_bill_detail"],
    }


def verifier_35_split_identifier_requires_detail_grain(root: Path) -> dict[str, Any]:
    response, _ = run_tool(
        "cost.py", "schema", "--action", "ListSplitBillDetail",
        "--section", "response", "--field", "SplitItemID", "--include-guidance",
    )
    schema_field(response, "response", "SplitItemID")

    aggregate_error, _ = run_tool(
        "cost.py", "query", "--action", "ListSplitBillDetail",
        "--body", '{"BillPeriod":"2026-07"}',
        "--require-field", "SplitItemID",
        "--pagination", "full", "--fixture-dir", str(root),
        "--out", str(root / "must-not-exist.csv"), expected=2,
    )
    aggregate = task_error(aggregate_error)
    require(aggregate["code"] == "RESPONSE_FIELD_NOT_PRESERVED", "aggregate grain was not blocked")
    require(aggregate["details"]["required_request"] == {"GroupPeriod": 2}, "recovery patch missing")
    require(not (root / "must-not-exist.csv").exists(), "blocked query wrote artifacts")

    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "ListSplitBillDetail__period-2026-07__offset-0.json",
        split_bill_response(
            [{"BillDetailId": "detail-1", "SplitBillDetailId": "split-1", "SplitItemID": "item-1", "PayableAmount": "1", "Currency": "CNY"}],
            total=1, limit=300, offset=0,
        ),
    )
    output = root / "split-detail.csv"
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListSplitBillDetail",
        "--body", '{"BillPeriod":"2026-07","GroupPeriod":2}',
        "--require-field", "SplitItemID",
        "--pagination", "full", "--fixture-dir", str(fixture),
        "--out", str(output),
    )
    metadata = json.loads((root / "split-detail.meta.json").read_text(encoding="utf-8"))
    fields = json.loads((root / "split-detail.fields.json").read_text(encoding="utf-8"))
    split_item = next(item for item in fields["fields"] if item["field"] == "SplitItemID")
    require(manifest["status"] == "success", "detail query did not complete")
    require(metadata["required_response_fields"] == ["SplitItemID"], "required field evidence missing")
    require(split_item["grain_availability"]["status"] == "available", "detail field not marked available")
    return {"aggregate_blocked": True, "required_request": {"GroupPeriod": 2}, "detail_status": "available"}


def verifier_36_hierarchical_bill_detail_analysis(root: Path) -> dict[str, Any]:
    response, _ = run_tool("cost.py", "schema", "--action", "ListBillDetail", "--section", "response")
    paths = schema_paths(response, "response")
    required_fields = {"List[].ConfigName", "List[].InstanceNo", "List[].ExpenseDate", "List[].PayableAmount"}
    require(required_fields.issubset(paths), f"hierarchical analysis fields missing: {sorted(required_fields - paths)}")
    return {
        "action": "ListBillDetail",
        "required_fields": sorted(required_fields),
        "local_analysis": ["group_by_config", "top_instance_per_config", "peak_time_for_instance"],
        "cost_analysis_used": False,
    }


def verifier_39_current_period_total_drift_is_provisional(root: Path) -> dict[str, Any]:
    period = date.today().strftime("%Y-%m")
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / f"ListBill__period-{period}__offset-0.json",
        bill_response(
            [
                {"BillID": "bill-1", "BillPeriod": period, "PayableAmount": "1", "Currency": "CNY"},
                {"BillID": "bill-2", "BillPeriod": period, "PayableAmount": "2", "Currency": "CNY"},
            ],
            total=3, limit=2, offset=0,
        ),
    )
    write_json(
        fixture / f"ListBill__period-{period}__offset-2.json",
        bill_response(
            [
                {"BillID": "bill-3", "BillPeriod": period, "PayableAmount": "3", "Currency": "CNY"},
                {"BillID": "bill-4", "BillPeriod": period, "PayableAmount": "4", "Currency": "CNY"},
            ],
            total=3, limit=2, offset=2,
        ),
    )
    output = root / "current-bill.csv"
    manifest, completed = run_tool(
        "cost.py", "query", "--action", "ListBill",
        "--body", json.dumps({"BillPeriod": period}),
        "--pagination", "full", "--page-size", "2",
        "--fixture-dir", str(fixture), "--out", str(output),
    )
    require(completed.returncode == 0, f"provisional query was not successful: {manifest}")
    require(manifest["status"] == "success", f"current-period query failed: {manifest}")
    metadata = json.loads((root / "current-bill.meta.json").read_text(encoding="utf-8"))
    coverage = metadata["coverage"]
    require(coverage["requested_scope_fulfilled"] is True, f"first Total boundary not fulfilled: {coverage}")
    require(coverage["is_complete"] is False and coverage["is_provisional"] is True, f"coverage classification drifted: {coverage}")
    require(coverage["rows_collected"] == 4 and coverage["expected_total"] == 3, f"overrun evidence missing: {coverage}")
    require(coverage["failed_queries"] == [], f"provisional query leaked into failed queries: {coverage}")
    require(metadata["freshness"]["partial_period"] is True, f"current-period freshness missing: {manifest}")
    return {
        "status": manifest["status"],
        "rows_collected": coverage["rows_collected"],
        "first_total": coverage["expected_total"],
        "stop_reason": coverage["provisional_queries"][0]["stop_reason"],
        "final_bill_claim_allowed": False,
    }


def verifier_42_automatic_query_result_location(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    rows = [
        {
            "BillCategoryParent": f"category-{index}",
            "PayableAmount": str(index),
            "Currency": "CNY",
        }
        for index in range(25)
    ]
    write_json(
        fixture / "ListBillOverviewByCategory.json",
        {
            "ResponseMetadata": {"Error": None},
            "Result": {
                "List": [
                    {
                        "PayerID": "payer-1",
                        "OwnerID": "owner-1",
                        "List": rows,
                    }
                ]
            },
        },
    )
    env = dict(os.environ)
    env["TMPDIR"] = str(root)
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "cost.py"),
            "query",
            "--action",
            "ListBillOverviewByCategory",
            "--body",
            '{"BillPeriod":"2026-07"}',
            "--fixture-dir",
            str(fixture),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    require(completed.returncode == 0, f"automatic query failed: {completed.stderr}")
    manifest = json.loads(completed.stdout)
    require(isinstance(manifest["result"], list), "small result should be inline")
    require(len(manifest["result"]) == 25, "row count was incorrectly used as an inline limit")

    rows[0]["OwnerCustomerName"] = "x" * (64 * 1024)
    write_json(
        fixture / "ListBillOverviewByCategory.json",
        {
            "ResponseMetadata": {"Error": None},
            "Result": {"List": [{"PayerID": "payer-1", "OwnerID": "owner-1", "List": rows}]},
        },
    )
    large = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "cost.py"),
            "query",
            "--action",
            "ListBillOverviewByCategory",
            "--body",
            '{"BillPeriod":"2026-07"}',
            "--fixture-dir",
            str(fixture),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    require(large.returncode == 0, f"large automatic query failed: {large.stderr}")
    large_manifest = json.loads(large.stdout)
    large_result = large_manifest["result"]
    require(
        isinstance(large_result, Mapping)
        and set(large_result) == {"file", "metadata", "fields"},
        "result above 64 KiB should expose its complete file result",
    )
    for artifact in ("file", "metadata", "fields"):
        require(Path(large_result[artifact]).is_file(), f"{artifact} artifact missing")
    return {
        "result_location": "inline",
        "row_count": manifest["_meta"]["row_count"],
        "large_result_location": "file",
        "thresholds": {"rows": None, "bytes": 65536},
    }


def verifier_43_current_account_status_only(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(fixture / "QueryBalanceAcct.json", balance_response())
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "QueryBalanceAcct",
        "--body", "{}", "--fixture-dir", str(fixture),
    )
    require(set(manifest) == {"status", "message", "result", "_meta"}, "balance response does not use unified envelope")
    row = manifest["result"]
    require(row["AvailableBalance"] == "-328.500000", "AvailableBalance precision drifted")
    require(row["Currency"] == "CNY", "balance currency missing")
    require(manifest["_meta"]["account_status"] == "in_arrears", "tool account decision missing")
    require(manifest["_meta"]["balance_check"]["status"] == "pass", "balance formula verification missing")
    require({"queried_at", "snapshot_time"}.isdisjoint(manifest["_meta"]), "account query invented time fields")
    return {
        "action": "QueryBalanceAcct",
        "status": "current_arrears",
        "available_balance": row["AvailableBalance"],
        "additional_billing_query_required": False,
    }


def verifier_44_arrears_balance_does_not_override_status(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "QueryBalanceAcct.json",
        balance_response(
            ArrearsBalance="100.000000",
            AvailableBalance="50.000000",
            CashBalance="150.000000",
        ),
    )
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "QueryBalanceAcct",
        "--body", "{}", "--fixture-dir", str(fixture),
    )
    row = manifest["result"]
    available = require_decimal(row["AvailableBalance"], "AvailableBalance")
    arrears = require_decimal(row["ArrearsBalance"], "ArrearsBalance")
    require(available >= 0 and arrears > 0, f"eval fixture lost the intended status split: {row}")
    require(manifest["_meta"]["account_status"] == "not_in_arrears", "ArrearsBalance overrode tool account status")
    require(manifest["_meta"]["balance_check"]["status"] == "pass", "non-arrears formula check failed")
    return {
        "available_balance": row["AvailableBalance"],
        "arrears_balance": row["ArrearsBalance"],
        "account_status": "current_not_in_arrears",
        "arrears_balance_overrode_status": False,
    }


def verifier_45_missing_available_balance_is_unknown(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    response = balance_response()
    del response["Result"]["AvailableBalance"]
    write_json(fixture / "QueryBalanceAcct.json", response)
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "QueryBalanceAcct",
        "--body", "{}", "--fixture-dir", str(fixture),
    )
    row = manifest["result"]
    require("AvailableBalance" not in row, f"missing AvailableBalance was synthesized: {row}")
    require(manifest["_meta"]["account_status"] == "unknown", "missing balance was given an account decision")
    require("AvailableBalance" in manifest["_meta"]["balance_check"]["missing_fields"], "missing balance was not reported")
    return {
        "available_balance_present": False,
        "account_status": "cannot_confirm",
        "fallback_to_arrears_or_unpaid": False,
    }


def verifier_46_unpaid_product_composition(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    rows = [
        {"BillPeriod": "2026-09", "Product": "ECS", "ProductZh": "云服务器", "UnpaidAmount": "12.340000", "Currency": "CNY"},
        {"BillPeriod": "2026-09", "Product": "TOS", "ProductZh": "对象存储", "UnpaidAmount": "0.000000", "Currency": "CNY"},
        {"BillPeriod": "2026-09", "Product": "CDN", "ProductZh": "内容分发网络", "UnpaidAmount": "1.000001", "Currency": "CNY"},
    ]
    write_json(
        fixture / "ListBillOverviewByProd__period-2026-09__offset-0.json",
        bill_response(rows, total=3, limit=300, offset=0),
    )
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListBillOverviewByProd",
        "--body", '{"BillPeriod":"2026-09"}', "--pagination", "full",
        "--page-size", "300", "--fixture-dir", str(fixture),
        "--require-field", "BillPeriod", "--require-field", "Product",
        "--require-field", "ProductZh",
        "--require-field", "UnpaidAmount", "--require-field", "Currency",
    )
    require(manifest["status"] == "success", f"unpaid composition query incomplete: {manifest}")
    positive = [
        row for row in manifest["result"]
        if require_decimal(row["UnpaidAmount"], "UnpaidAmount") > 0
    ]
    total = sum((require_decimal(row["UnpaidAmount"], "UnpaidAmount") for row in positive), Decimal("0"))
    require(len(positive) == 2 and format_decimal(total) == "13.340001", f"positive unpaid Decimal aggregation drifted: {positive}")
    return {
        "status": manifest["status"],
        "positive_product_count": len(positive),
        "unpaid_total": format_decimal(total),
        "claim": "billed_unpaid_composition",
    }


def verifier_48_balance_failure_and_recharge_delay_boundary(root: Path) -> dict[str, Any]:
    fixture = root / "fixture"
    fixture.mkdir()
    write_json(
        fixture / "QueryBalanceAcct.json",
        {"__error__": {"code": "PERMISSION_DENIED", "message": "denied"}},
    )
    failure, completed = run_tool(
        "cost.py", "query", "--action", "QueryBalanceAcct",
        "--body", "{}", "--fixture-dir", str(fixture), expected=5,
    )
    require(completed.stdout.strip(), "failed balance query did not return stdout envelope")
    require(failure["status"] == "error" and failure["result"] is None, "failed balance query returned a business result")
    require(task_error(failure)["code"] == "PERMISSION_DENIED", f"permission error was not preserved: {failure}")
    return {
        "query_status": "failed",
        "account_status": "cannot_confirm",
        "fallback_to_bill_unpaid": False,
    }


def verifier_49_resource_package_token_queries(root: Path) -> dict[str, Any]:
    catalog, _ = run_tool("cost.py", "schema", "--list-actions")
    actions = {item["action"]: item for item in catalog["actions"]}
    require("ListResourcePackages" in actions and "ListPackageUsageDetails" in actions, "resource package actions missing")

    packages_csv = root / "packages.csv"
    packages, _ = run_tool(
        "cost.py", "query", "--action", "ListResourcePackages",
        "--body", '{"ResourceType":"Package","Product":"TOS","MaxResults":"20"}',
        "--pagination", "full", "--fixture-dir", str(RESOURCE_PACKAGE_FIXTURES),
        "--out", str(packages_csv),
    )
    package_rows = read_csv(packages_csv)
    package_meta = json.loads(packages_csv.with_suffix(".meta.json").read_text(encoding="utf-8"))
    require(packages["status"] == "success" and len(package_rows) == 2, "package inventory collection incomplete")
    require(package_meta["coverage"]["pages_fetched"] == 2, "package token pages not fully collected")
    require({"OwnerID", "UserName", "SubjectNo"}.isdisjoint(package_rows[0]), "private inventory fields leaked")

    usage_csv = root / "usage.csv"
    usage, _ = run_tool(
        "cost.py", "query", "--action", "ListPackageUsageDetails",
        "--body", '{"ResourceType":"Package","DeductBeginTime":"2026-08-01T00:00:00Z","DeductEndTime":"2026-10-01T00:00:00Z","MaxResults":"50"}',
        "--pagination", "full", "--fixture-dir", str(RESOURCE_PACKAGE_FIXTURES),
        "--out", str(usage_csv),
    )
    usage_rows = read_csv(usage_csv)
    require(usage["status"] == "success" and len(usage_rows) == 2, "usage detail collection incomplete")
    match_keys = {"InstanceNo", "DeductionProduct", "DeductionElementCode", "DeductionInstanceNo", "DeductionRegionCode"}
    require(match_keys <= set(usage_rows[0]), f"usage match keys missing: {sorted(match_keys - set(usage_rows[0]))}")
    require(
        {"OwnerID", "UserName", "DeductionAccountID", "DeductionUserName", "SubjectNo"}.isdisjoint(usage_rows[0]),
        "private usage fields leaked",
    )
    return {
        "actions": ["ListResourcePackages", "ListPackageUsageDetails"],
        "package_pages": package_meta["coverage"]["pages_fetched"],
        "package_rows": len(package_rows),
        "usage_rows": len(usage_rows),
        "private_fields_exposed": False,
    }


def verifier_50_resource_package_attribution(root: Path) -> dict[str, Any]:
    def fixture_rows(name: str) -> list[dict[str, Any]]:
        return json.loads((RESOURCE_PACKAGE_FIXTURES / name).read_text(encoding="utf-8"))["Result"]["List"]

    packages = [
        *fixture_rows("ListResourcePackages__token-start.json"),
        *fixture_rows("ListResourcePackages__token-p2.json"),
    ]
    usage = [
        *fixture_rows("ListPackageUsageDetails__token-start.json"),
        *fixture_rows("ListPackageUsageDetails__token-u2.json"),
    ]
    bills = json.loads((RESOURCE_PACKAGE_FIXTURES / "bill-details.json").read_text(encoding="utf-8"))["rows"]
    result = analyze_resource_package_attribution(
        packages=packages,
        usage_details=usage,
        bill_details=bills,
        analysis_period="2026-09",
        comparison_period="2026-08",
    )
    reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
    require(
        {"resource_package_used_up", "resource_package_deduction_declined"} <= set(reasons),
        f"supported package reasons missing: {sorted(reasons)}",
    )
    used_up = reasons["resource_package_used_up"]
    require(used_up["package"]["InstanceNo"] == "tos-pack-001", "wrong package attributed")
    require(used_up["package"]["AvailableAmount"] == "0", "used-up balance evidence missing")
    require(used_up["evidence"]["bill_count"] == "1.2", "bill usage evidence missing")
    require(used_up["evidence"]["bill_deduction_count"] == "0.2", "bill deduction evidence missing")
    decline = reasons["resource_package_deduction_declined"]["evidence"]
    require(decline["comparison_period_deduction_use_amount"] == "4.8", "comparison deduction mismatch")
    require(decline["analysis_period_deduction_use_amount"] == "0.2", "analysis deduction mismatch")
    require(decline["analysis_period_payable_amount"] == "860.00", "payable evidence mismatch")

    no_link = analyze_resource_package_attribution(
        packages=packages,
        usage_details=[],
        bill_details=bills,
        analysis_period="2026-09",
        comparison_period="2026-08",
    )
    require(no_link["supported_reasons"] == [], "package reason emitted without usage link")
    require(no_link["insufficient_evidence"], "missing usage link was not reported")
    require(
        "package configuration name/code is not treated as an applicability wildcard" in result["contract_limits"],
        "wildcard contract boundary missing",
    )
    return {
        "supported_reasons": sorted(reasons),
        "package_instance": used_up["package"]["InstanceNo"],
        "deduction_change": {"2026-08": "4.8", "2026-09": "0.2"},
        "analysis_payable_amount": "860.00",
        "missing_link_policy": "insufficient_evidence",
    }


def verifier_51_coupon_query_and_scope_contract(root: Path) -> dict[str, Any]:
    catalog, _ = run_tool("cost.py", "schema", "--list-actions")
    actions = {item["action"]: item for item in catalog["actions"]}
    require("ListCoupons" in actions, "ListCoupons missing from action catalog")
    require("ListCouponUsageRecords" in actions, "ListCouponUsageRecords missing from action catalog")

    output = root / "coupons.csv"
    manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListCoupons",
        "--body", '{"ProductCode":"TOS"}', "--pagination", "full", "--page-size", "1",
        "--fixture-dir", str(COUPON_FIXTURES), "--out", str(output),
    )
    rows = read_csv(output)
    metadata = json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8"))
    require(manifest["status"] == "success" and len(rows) == 2, "coupon full query incomplete")
    require(metadata["coverage"]["pages_fetched"] == 2 and metadata["coverage"]["is_complete"], "coupon pagination evidence incomplete")
    require({"AccountID", "AssignedOwnerIDList"}.isdisjoint(rows[0]), "coupon account fields leaked")
    limits = json.loads(rows[0]["ProductLimitList"])
    require(limits[0]["ConfigurationType"] == 1, "all-configuration contract value missing")
    require(limits[0]["ChargeItemType"] == 0, "all-charge-item contract value missing")

    usage_output = root / "coupon-usage.csv"
    usage_manifest, _ = run_tool(
        "cost.py", "query", "--action", "ListCouponUsageRecords",
        "--body", '{"CouponID":"cpn-tos-expired"}', "--pagination", "full", "--page-size", "1",
        "--fixture-dir", str(COUPON_FIXTURES), "--out", str(usage_output),
    )
    usage_rows = read_csv(usage_output)
    usage_metadata = json.loads(usage_output.with_suffix(".meta.json").read_text(encoding="utf-8"))
    require(usage_manifest["status"] == "success" and len(usage_rows) == 2, "coupon usage full query incomplete")
    require(usage_metadata["coverage"]["pages_fetched"] == 2, "coupon usage pagination evidence incomplete")
    require({"AccountID", "UserAccountID"}.isdisjoint(usage_rows[0]), "coupon usage account fields leaked")
    return {
        "actions": ["ListCoupons", "ListCouponUsageRecords"],
        "pages": metadata["coverage"]["pages_fetched"],
        "rows": len(rows),
        "usage_pages": usage_metadata["coverage"]["pages_fetched"],
        "usage_rows": len(usage_rows),
        "configuration_type": limits[0]["ConfigurationType"],
        "charge_item_type": limits[0]["ChargeItemType"],
        "private_fields_exposed": False,
    }


def verifier_52_coupon_attribution(root: Path) -> dict[str, Any]:
    coupons = [
        *json.loads((COUPON_FIXTURES / "ListCoupons__offset-0.json").read_text(encoding="utf-8"))["List"],
        *json.loads((COUPON_FIXTURES / "ListCoupons__offset-1.json").read_text(encoding="utf-8"))["List"],
    ]
    bills = json.loads((COUPON_FIXTURES / "bill-details.json").read_text(encoding="utf-8"))["rows"]
    usage_records = [
        *json.loads((COUPON_FIXTURES / "ListCouponUsageRecords__offset-0.json").read_text(encoding="utf-8"))["List"],
        *json.loads((COUPON_FIXTURES / "ListCouponUsageRecords__offset-1.json").read_text(encoding="utf-8"))["List"],
    ]
    result = analyze_coupon_attribution(
        coupons=coupons,
        usage_records=usage_records,
        bill_details=bills,
        analysis_period="2026-09",
        comparison_period="2026-08",
    )
    reasons = {item["reason_type"]: item for item in result["supported_reasons"]}
    require({"coupon_expired", "coupon_redemption_declined"} <= set(reasons), f"coupon reasons missing: {sorted(reasons)}")
    expired = reasons["coupon_expired"]
    require(expired["coupon"]["CouponID"] == "cpn-tos-expired", "wrong coupon attributed")
    require(expired["time_match"]["reason"] == "expired", "consumption time did not prove expiry")
    bill_decline = result["bill_observations"][0]["evidence"]
    require(bill_decline["comparison_period_coupon_amount"] == "500.00", "comparison coupon amount mismatch")
    require(bill_decline["analysis_period_coupon_amount"] == "0.00", "analysis coupon amount mismatch")
    require(bill_decline["analysis_period_payable_amount"] == "1200.00", "analysis payable mismatch")
    require("coupon_ids" not in result["bill_observations"][0], "bill observation attributed to coupon candidates")
    redemption_decline = reasons["coupon_redemption_declined"]["evidence"]
    require(redemption_decline["comparison_period_redeemed_amount"] == "500.0", "comparison redemption mismatch")
    require(redemption_decline["analysis_period_redeemed_amount"] == "0", "analysis redemption mismatch")

    prepaid_bill = dict(
        bills[1],
        BillID="order-pre-001",
        BillDetailId="bill-detail-pre-001",
        BillingMode="1",
    )
    prepaid_record = {
        "CouponID": "cpn-tos-expired",
        "ProductCode": "TOS",
        "ChangeAmount": "88.000001",
        "CreatedTime": "2026-09-05T01:00:00+08:00",
        "PayType": "pre",
        "SubBusinessID": "order-pre-001",
        "ChangeType": 2,
        "BillingCycle": "2026-09",
    }
    prepaid_result = analyze_coupon_attribution(
        coupons=[dict(coupons[0], PayTypeLimit="pre")],
        usage_records=[prepaid_record],
        bill_details=[prepaid_bill],
        analysis_period="2026-09",
    )
    prepaid_link = prepaid_result["coupon_usage_summaries"][0]["target_bill_links"][0]
    require(prepaid_link["link_field"] == "BillID", "prepaid coupon did not link by BillID")
    require(prepaid_link["affected_bill"]["BillID"] == "order-pre-001", "prepaid BillID link mismatch")
    require(prepaid_link["target_bill_redemption_verified"], "prepaid redemption link not verified")

    no_match = analyze_coupon_attribution(
        coupons=[coupons[1]],
        bill_details=bills,
        analysis_period="2026-09",
        comparison_period="2026-08",
    )
    require(no_match["supported_reasons"] == [] and no_match["insufficient_evidence"], "unmatched coupon did not remain insufficient")
    return {
        "supported_reasons": sorted(reasons),
        "coupon_id": expired["coupon"]["CouponID"],
        "coupon_change": {"2026-08": "500.00", "2026-09": "0.00"},
        "payable_change": {"2026-08": "700.00", "2026-09": "1200.00"},
        "redemption_change": {"2026-08": "500.0", "2026-09": "0"},
        "candidate_count": len(result["follow_up_candidates"]),
        "prepaid_link_field": prepaid_link["link_field"],
        "missing_match_policy": "insufficient_evidence",
    }


def verifier_53_artifact_invalid_recovery(root: Path) -> dict[str, Any]:
    payload, _ = run_tool(
        "cost.py",
        "reconcile", "preflight",
        "--left", str(root / "missing-left.csv"),
        "--right", str(root / "missing-right.csv"),
    )
    require(payload["verdict"] == "block", "invalid artifacts must block preflight")
    require(payload["claim_scope"] == "blocked", "invalid artifacts must block claims")
    checks = payload.get("checks")
    require(isinstance(checks, list) and len(checks) == 1, f"unexpected invalid-artifact checks: {checks}")
    check = checks[0]
    require(check.get("code") == "ARTIFACT_INVALID", f"wrong check: {check}")
    require("没有可用于正式对账的有效双侧输入" in check.get("message", ""), "missing invalid-input meaning")
    require("尚未执行来源关系、范围、维度或金额检查" in check.get("message", ""), "missing evidence boundary")
    details = check.get("details")
    require(isinstance(details, Mapping), f"missing recovery details: {check}")
    recovery = details.get("recovery_options")
    require(
        [item.get("action") for item in recovery] == [
            "inspect_artifact_set", "regenerate_query_artifacts", "rerun_preflight",
        ],
        f"unexpected recovery options: {recovery}",
    )
    retry_policy = str(details.get("retry_policy", ""))
    require("不要继续 reconcile run" in retry_policy, "missing stop instruction")
    require("不要据此判断范围不一致" in retry_policy, "missing scope-claim boundary")
    return {
        "verdict": payload["verdict"],
        "claim_scope": payload["claim_scope"],
        "check_code": check["code"],
        "recovery_actions": [item["action"] for item in recovery],
        "run_allowed": False,
    }


def verifier_54_bill_and_amortized_time_semantics(root: Path) -> dict[str, Any]:
    catalog, _ = run_tool("cost.py", "schema", "--list-actions")
    actions = {item["action"]: item for item in catalog["actions"]}
    bill_limits = " ".join(actions["ListBillDetail"]["important_limits"])
    daily = actions["ListAmortizedCostBillDaily"]
    require("BillPeriod 决定账单归属" in bill_limits, "bill period ownership guidance missing")
    require("可能晚于出账账期甚至位于未来" in bill_limits, "future usage-period guidance missing")
    require("AmortizedDay/AmortizedMonth" in " ".join(daily["important_limits"]), "daily amortized axis missing")

    bill_contract, _ = run_tool(
        "cost.py", "schema", "--action", "ListBillDetail", "--section", "request", "--include-guidance",
    )
    bill_constraints = " ".join(bill_contract["business_constraints"])
    require("不能据此从账期合计中排除" in bill_constraints, "bill aggregation boundary missing")
    require("不要根据 ExpenseBeginTime/ExpenseEndTime 手工分配" in bill_constraints, "manual amortization boundary missing")

    cost_contract, _ = run_tool(
        "cost.py", "schema", "--action", "ListAmortizedCostBillDaily", "--section", "request", "--include-guidance",
    )
    cost_constraints = " ".join(cost_contract["business_constraints"])
    require("实际使用周期" in cost_constraints, "actual usage amortization guidance missing")
    require("BillPeriod 表示原始账务账期" in cost_constraints, "original bill period role missing")
    return {
        "bill_axis": "BillPeriod",
        "bill_usage_fields": ["ExpenseBeginTime", "ExpenseEndTime"],
        "amortized_axes": ["AmortizedMonth", "AmortizedDay"],
        "manual_amortization_allowed": False,
    }


def verifier_55_local_parameter_contract_and_result_composition(root: Path) -> dict[str, Any]:
    retry, _ = run_tool("cost.py", "query", "describe", "--section", "retry")
    retry_contract = retry["retry"]
    require("parameter_error_observation" in retry_contract, "parameter error observation missing")
    for removed in ("plan_invariants", "repair_policy", "local_error_policy"):
        require(removed not in retry_contract, f"workflow policy must stay out of tool contract: {removed}")

    output, _ = run_tool("cost.py", "query", "describe", "--section", "output")
    require("artifact_reuse_policy" not in output["output"], "tool contract must not control Agent re-query decisions")

    error_payload, _ = run_tool(
        "cost.py", "query",
        "--action", "ListBillDetail",
        "--body", '{"BillPeriod":"2026-08","Limit":301,"GroupPeriod":9}',
        "--pagination", "page",
        "--fixture-dir", str(root),
        expected=2,
    )
    error = task_error(error_payload)
    details = error["details"]
    invalid = details["invalid_parameters"]
    require([item["path"] for item in invalid] == ["Limit", "GroupPeriod"], f"wrong invalid parameters: {invalid}")
    require(invalid[0]["contract"]["type"] == "integer", f"Limit contract missing: {invalid}")
    require(invalid[1]["contract"]["enum"] == [0, 1, 2], f"GroupPeriod contract missing: {invalid}")
    require("next_action" not in details, "parameter error must not prescribe the Agent's next action")

    reconcile, _ = run_tool("cost.py", "reconcile", "describe", "--section", "preflight")
    arguments = {item["name"]: item for item in reconcile["preflight"]["arguments"]}
    require(arguments["--left-result"]["properties"] == ["file", "metadata", "fields"], "left query result input missing")
    require(arguments["--right-result"]["properties"] == ["file", "metadata", "fields"], "right query result input missing")
    return {
        "invalid_parameters": [item["path"] for item in invalid],
        "local_contracts": True,
        "agent_next_action_prescribed": False,
        "query_result_accepted_by_reconcile": True,
    }


VERIFIERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "case_01": verifier_01_monthly_product_payable,
    "case_02": verifier_02_full_bill_detail,
    "case_03": verifier_03_second_page,
    "case_04": verifier_04_cash_cost_boundary,
    "case_05": verifier_05_product_top10,
    "case_06": verifier_06_no_metadata,
    "case_12": verifier_12_latest_cash_boundary,
    "case_15": verifier_15_response_field_correction,
    "case_16": verifier_16_compact_bill_detail_request_guidance,
    "case_17": verifier_17_compare_periods,
    "case_18": verifier_18_default_compact_result,
    "case_19": verifier_19_bill_sample_amounts,
    "case_20": verifier_20_multi_month_partial,
    "case_21": verifier_21_bill_id_local_filter_plan,
    "case_23": verifier_23_split_project_attribution,
    "case_24": verifier_24_tag_key_requires_value,
    "case_29": verifier_29_secret_body_rejected,
    "case_30": verifier_30_page_and_missing_field_boundaries,
    "case_31": verifier_31_reconciliation_preflight_and_run,
    "case_32": verifier_32_project_semantic_warning,
    "case_34": verifier_34_reconciliation_mismatch_boundary,
    "case_35": verifier_35_split_identifier_requires_detail_grain,
    "case_36": verifier_36_hierarchical_bill_detail_analysis,
    "case_39": verifier_39_current_period_total_drift_is_provisional,
    "case_42": verifier_42_automatic_query_result_location,
    "case_43": verifier_43_current_account_status_only,
    "case_44": verifier_44_arrears_balance_does_not_override_status,
    "case_45": verifier_45_missing_available_balance_is_unknown,
    "case_46": verifier_46_unpaid_product_composition,
    "case_48": verifier_48_balance_failure_and_recharge_delay_boundary,
    "case_49": verifier_49_resource_package_token_queries,
    "case_50": verifier_50_resource_package_attribution,
    "case_51": verifier_51_coupon_query_and_scope_contract,
    "case_52": verifier_52_coupon_attribution,
    "case_53": verifier_53_artifact_invalid_recovery,
    "case_54": verifier_54_bill_and_amortized_time_semantics,
    "case_55": verifier_55_local_parameter_contract_and_result_composition,
}


def load_cases() -> list[dict[str, Any]]:
    payload = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
    require(payload.get("schema_version") == "1.0", "eval schema_version must be 1.0")
    require(payload.get("skill_name") == "volcengine-cost", "eval skill_name mismatch")
    cases = payload.get("evals")
    require(isinstance(cases, list) and cases, "evals must be a non-empty array")
    ids = [item.get("id") for item in cases]
    require(all(isinstance(item, int) and item > 0 for item in ids), f"eval ids must be positive integers: {ids}")
    require(ids == sorted(set(ids)), f"eval ids must be unique and ordered: {ids}")
    verifiers = [item.get("verifier") for item in cases]
    require(len(set(verifiers)) == len(verifiers), "eval verifier names must be unique")
    require(set(verifiers) == set(VERIFIERS), f"eval verifier mismatch: declared={verifiers}, implemented={sorted(VERIFIERS)}")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic volcengine-cost release evals.")
    parser.add_argument("--list", action="store_true", help="只校验 schema 并列出 case。")
    args = parser.parse_args()
    try:
        cases = load_cases()
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    if args.list:
        print(json.dumps({"status": "listed", "case_count": len(cases), "cases": [{"id": item["id"], "verifier": item["verifier"]} for item in cases]}, ensure_ascii=False, indent=2))
        return 0
    results = []
    failed = 0
    for case in cases:
        try:
            with tempfile.TemporaryDirectory(prefix=f"volcengine-cost-eval-{case['id']:02d}-") as directory:
                evidence = VERIFIERS[case["verifier"]](Path(directory))
            results.append({"id": case["id"], "verifier": case["verifier"], "status": "passed", "evidence": evidence})
        except Exception as exc:
            failed += 1
            results.append({"id": case["id"], "verifier": case.get("verifier"), "status": "failed", "error": str(exc)})
    payload = {
        "status": "passed" if failed == 0 else "failed",
        "skill": "volcengine-cost",
        "case_count": len(cases),
        "passed": len(cases) - failed,
        "failed": failed,
        "results": results,
        "scope": "deterministic_offline_tool_gate",
        "agent_host_scoring": "not_included",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
