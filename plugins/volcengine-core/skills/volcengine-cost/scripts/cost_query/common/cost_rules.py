"""Reusable financial rules for cost CSV analysis.

This module contains the invariants that generated analysis scripts must reuse.
It intentionally does not implement generic dataframe operations.
"""

from __future__ import annotations

import json
import os
import tempfile
import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Mapping, NamedTuple, Sequence, TypedDict

from .errors import BillingQueryError, ErrorCode, ExitCode
from .fields import (
    FieldType,
    canonical_name,
    declared_type,
    is_aggregatable_metric_field,
    is_money_field,
    money_currency_field,
)
from ..utils.errors import invalid_argument as invalid_cost_rule
from ..utils.decimals import format_decimal


__all__ = [
    "CostCsv",
    "CostEvidence",
    "FieldDescriptor",
    "FieldRef",
    "FieldResolver",
    "FieldType",
    "LoadedCostMetadata",
    "MoneyGrouping",
    "atomic_write_csv",
    "atomic_write_json",
    "ensure_money_grouping",
    "evidence_from_metadata",
    "format_decimal",
    "load_cost_csv",
    "load_cost_metadata",
    "parse_decimal",
    "public_columns",
    "public_rows",
    "require_decimal",
    "require_registered_money_metric",
    "resolve_money_currency",
    "typed_value",
]


class FieldDescriptor(TypedDict):
    """Serializable public description of a resolved field."""

    field: str
    field_type: Literal["string", "integer", "decimal", "date", "period", "json"]


class CostCsv(NamedTuple):
    """CSV columns and rows; supports named access and tuple unpacking."""

    columns: list[str]
    rows: list[dict[str, str]]


class LoadedCostMetadata(NamedTuple):
    """Discovered metadata path, payload, and non-fatal loading warnings."""

    path: Path | None
    metadata: dict[str, Any] | None
    warnings: list[str]


class MoneyGrouping(NamedTuple):
    """Final grouping fields and currency fields added by the money rules."""

    group_refs: list[FieldRef]
    implicit_currency_refs: list[FieldRef]


class _RequiredCostEvidence(TypedDict):
    claim_scope: Literal["full_dataset", "provisional_current_period", "partial_dataset", "input_file_only"]
    coverage_status: Literal["complete", "provisional", "partial", "unknown"]
    freshness_status: Literal["known", "partial", "unknown"]
    provenance_status: Literal["known", "unknown"]


class CostEvidence(_RequiredCostEvidence, total=False):
    """Conclusion scope and provenance inherited from query metadata."""

    failed_queries: list[Any]
    source_action: str | None


@dataclass(frozen=True)
class FieldRef:
    requested: str
    column: str
    canonical: str
    field_type: FieldType
    type_source: Literal["registry", "inferred"]

    def to_dict(self) -> FieldDescriptor:
        return {
            "field": self.column,
            "field_type": self.field_type.value,
        }


class FieldResolver:
    def __init__(self, columns: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
        if not columns:
            raise invalid_cost_rule("输入 CSV 缺少表头")
        if len(set(columns)) != len(columns):
            raise invalid_cost_rule("输入 CSV 包含重复列名")
        self.columns = tuple(columns)
        self.rows = rows
        self.canonical_columns: dict[str, list[str]] = {}
        for column in columns:
            self.canonical_columns.setdefault(canonical_name(column), []).append(column)

    def resolve(self, requested: str) -> FieldRef:
        requested = requested.strip()
        if not requested:
            raise invalid_cost_rule("字段名不能为空")
        if requested in self.columns:
            column = requested
        else:
            candidates = self.canonical_columns.get(canonical_name(requested), [])
            if not candidates:
                raise BillingQueryError(
                    ErrorCode.UNSUPPORTED_FIELD,
                    f"输入 CSV 中不存在字段：{requested}",
                    ExitCode.INVALID_ARGUMENT,
                    {"field": requested, "columns": list(self.columns)},
                )
            if len(candidates) > 1:
                raise BillingQueryError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"字段 {requested} 匹配到多个 CSV 列",
                    ExitCode.INVALID_ARGUMENT,
                    {"field": requested, "candidates": candidates, "code": "AMBIGUOUS_FIELD"},
                )
            column = candidates[0]
        canonical = canonical_name(column)
        registered = declared_type(column)
        return FieldRef(
            requested,
            column,
            canonical,
            registered or self._infer_type(column),
            "registry" if registered else "inferred",
        )

    def _infer_type(self, column: str) -> FieldType:
        values = [row.get(column, "") for row in self.rows if row.get(column, "") != ""]
        if not values:
            return FieldType.STRING
        try:
            for value in values:
                parse_decimal(value, column)
            return FieldType.DECIMAL
        except BillingQueryError:
            return FieldType.STRING


def parse_decimal(
    value: Any,
    field_name: str,
    *,
    allow_empty: bool = False,
    invalid_message: str = "字段包含非 Decimal 值",
    non_finite_message: str = "字段包含非有限 Decimal 值",
) -> Decimal | None:
    if value is None or value == "":
        if allow_empty:
            return None
        raise invalid_cost_rule(invalid_message, field=field_name, value=value)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise invalid_cost_rule(invalid_message, field=field_name, value=value) from exc
    if not parsed.is_finite():
        raise invalid_cost_rule(non_finite_message, field=field_name, value=value)
    return parsed


def require_decimal(
    value: str,
    field_name: str,
    *,
    invalid_message: str = "字段包含非 Decimal 值",
    non_finite_message: str = "字段包含非有限 Decimal 值",
) -> Decimal:
    parsed = parse_decimal(
        value,
        field_name,
        invalid_message=invalid_message,
        non_finite_message=non_finite_message,
    )
    assert parsed is not None
    return parsed


def typed_value(value: str, ref: FieldRef) -> Decimal | date | str | None:
    if value == "":
        return None
    if ref.field_type in (FieldType.DECIMAL, FieldType.INTEGER):
        return require_decimal(value, ref.requested)
    if ref.field_type is FieldType.DATE:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError as exc:
            raise invalid_cost_rule("字段包含非法日期", field=ref.requested, value=value) from exc
    if ref.field_type is FieldType.PERIOD:
        try:
            return datetime.strptime(value, "%Y-%m").date()
        except ValueError as exc:
            raise invalid_cost_rule("字段包含非法账期", field=ref.requested, value=value) from exc
    return value


def require_registered_money_metric(field_ref: FieldRef, operation: str) -> None:
    if not is_aggregatable_metric_field(field_ref.canonical):
        raise invalid_cost_rule(
            f"{operation} 只适用于明确注册的金额字段",
            field=field_ref.column,
            field_type=field_ref.field_type.value,
        )


def resolve_money_currency(
    resolver: FieldResolver,
    metric_ref: FieldRef,
    *,
    duplicate_message: str = "金额字段存在多个等价币种列",
) -> FieldRef | None:
    canonical = money_currency_field(metric_ref.canonical)
    if canonical is None:
        return None
    candidates = resolver.canonical_columns.get(canonical, [])
    if len(candidates) == 1:
        return resolver.resolve(candidates[0])
    if len(candidates) > 1:
        raise invalid_cost_rule(duplicate_message, field=metric_ref.requested, candidates=candidates)
    return None


def ensure_money_grouping(
    resolver: FieldResolver,
    metric_refs: Sequence[FieldRef],
    group_refs: Sequence[FieldRef],
) -> MoneyGrouping:
    resolved_group_refs = list(group_refs)
    implicit_group_by: list[FieldRef] = []
    group_columns = {ref.column for ref in resolved_group_refs}
    for ref in metric_refs:
        if not is_money_field(ref.canonical):
            continue
        currency = resolve_money_currency(resolver, ref, duplicate_message="金额聚合存在多个等价币种列")
        if currency is None:
            expected = money_currency_field(ref.canonical)
            raise invalid_cost_rule("金额 SUM/AVG 缺少匹配币种列", field=ref.requested, expected_currency_field=expected)
        if currency.column not in group_columns:
            resolved_group_refs.append(currency)
            implicit_group_by.append(currency)
            group_columns.add(currency.column)
    return MoneyGrouping(resolved_group_refs, implicit_group_by)


def evidence_from_metadata(metadata: Mapping[str, Any] | None) -> CostEvidence:
    if metadata is None:
        return {
            "claim_scope": "input_file_only",
            "coverage_status": "unknown",
            "freshness_status": "unknown",
            "provenance_status": "unknown",
        }
    coverage = metadata.get("coverage") if isinstance(metadata.get("coverage"), Mapping) else {}
    freshness = metadata.get("freshness") if isinstance(metadata.get("freshness"), Mapping) else {}
    complete = coverage.get("is_complete") is True
    provisional = coverage.get("is_provisional") is True
    failed_queries = coverage.get("failed_queries", [])
    source_action = metadata.get("action")
    if not isinstance(failed_queries, list):
        raise invalid_cost_rule(
            "metadata.coverage.failed_queries 必须是数组",
            actual_type=type(failed_queries).__name__,
        )
    if source_action is not None and not isinstance(source_action, str):
        raise invalid_cost_rule(
            "metadata.action 必须是字符串",
            actual_type=type(source_action).__name__,
        )
    return {
        "claim_scope": (
            "full_dataset"
            if complete
            else "provisional_current_period" if provisional else "partial_dataset"
        ),
        "coverage_status": "complete" if complete else "provisional" if provisional else "partial",
        "freshness_status": "partial" if freshness.get("partial_period") else "known",
        "provenance_status": "known",
        "failed_queries": failed_queries,
        "source_action": source_action,
    }


def public_columns(action: str | None, columns: Sequence[str]) -> list[str]:
    from ..billing.exposure import is_public_response_field

    return [column for column in columns if is_public_response_field(action, column)]


def public_rows(action: str | None, rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    from ..billing.exposure import public_row

    return [public_row(action, row) for row in rows]


def load_cost_csv(path: Path) -> CostCsv:
    if path.suffix.lower() != ".csv":
        raise invalid_cost_rule("只接受 CSV 数据输入", path=str(path))
    if not path.is_file():
        raise invalid_cost_rule("输入 CSV 不存在", path=str(path))
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return CostCsv(columns, rows)


def load_cost_metadata(
    input_path: Path,
    explicit: Path | None = None,
) -> LoadedCostMetadata:
    path = explicit or input_path.with_name(f"{input_path.stem}.meta.json")
    if not path.exists():
        if explicit:
            raise invalid_cost_rule("显式指定的 metadata 不存在", path=str(path))
        return LoadedCostMetadata(None, None, [])
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise invalid_cost_rule("metadata 不是有效 JSON object", path=str(path)) from exc
    if not isinstance(value, dict):
        raise invalid_cost_rule("metadata 顶层必须是 JSON object", path=str(path))
    coverage = value.get("coverage")
    if not isinstance(coverage, Mapping) or not isinstance(coverage.get("is_complete"), bool):
        if explicit:
            raise invalid_cost_rule("metadata 缺少 coverage.is_complete", path=str(path))
        return LoadedCostMetadata(None, None, ["自动发现的 metadata 格式不受支持，按无 metadata 处理"])
    return LoadedCostMetadata(path, value, [])


def atomic_write_csv(
    path: Path,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    *,
    overwrite: bool = False,
) -> None:
    if path.suffix.lower() != ".csv":
        raise invalid_cost_rule("输出文件必须使用 .csv 扩展名")
    if path.exists() and not overwrite:
        raise BillingQueryError(ErrorCode.OUTPUT_EXISTS, f"输出文件已存在：{path}", ExitCode.OUTPUT_FAILED)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(columns), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def atomic_write_json(
    path: Path,
    value: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> None:
    if path.exists() and not overwrite:
        raise BillingQueryError(ErrorCode.OUTPUT_EXISTS, f"输出文件已存在：{path}", ExitCode.OUTPUT_FAILED)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, allow_nan=False, indent=2)
            file.write("\n")
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise
