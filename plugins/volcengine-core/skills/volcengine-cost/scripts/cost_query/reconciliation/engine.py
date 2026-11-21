"""双侧聚合、可比性检查、受控 Join 与守恒式下钻。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..common.errors import BillingQueryError, ErrorCode, ExitCode
from ..common.fields import FieldType, canonical_name, money_currency_field
from ..common.cost_rules import (
    FieldRef,
    FieldResolver,
    atomic_write_csv,
    atomic_write_json,
    ensure_money_grouping,
    load_cost_csv as load_csv,
    load_cost_metadata as load_metadata,
    require_decimal,
    require_registered_money_metric,
    typed_value,
)
from ..utils.decimals import format_decimal as _format_decimal
from ..utils.errors import invalid_argument as invalid_plan
from .profiles import (
    NONSTANDARD_DIMENSIONS,
    RECONCILIATION_METRIC_CANONICAL,
    RECONCILIATION_METRICS,
    PairProfile,
    find_profile,
)


FILTER_OPERATORS = frozenset(
    {"eq", "ne", "in", "not-in", "gt", "gte", "lt", "lte", "between", "contains"}
)
MISSING_DIMENSION = "__MISSING__"
_EXECUTION_SCOPE_FIELDS = frozenset({"limit", "offset", "need_record_num"})
_GRAIN_FIELDS = frozenset({"group_period", "group_term"})
_TIME_FIELDS = frozenset({"bill_period", "expense_date", "amortized_month", "amortized_day", "begin_time_str", "end_time_str"})
MISMATCH_INTERPRETATION_RULES = (
    "对账不平只证明给定口径下两侧聚合结果存在差异，不证明业务根因",
    "不要根据 BillingMode、计费项、产品、Project/Tag 或单侧缺失记录推断某费用不参与分账",
    "ListBillDetail <> ListSplitBillDetail 不平时，账单明细是金额对账依据，分账账单仅供归属参考",
    "分账差异可提示可能受数据时效、分账生成延迟或项目/标签归属更新延迟影响，但这不是确认根因",
    "用户需要确认业务原因、修正分账归属或追查分账链路时，建议提工单处理",
)


def normalize_filter_operator(operator: str) -> str:
    if operator not in FILTER_OPERATORS:
        raise invalid_plan(
            "不支持的 filter operator",
            operator=operator,
            supported_operators=sorted(FILTER_OPERATORS),
        )
    return operator


@dataclass(frozen=True)
class FilterItem:
    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class ReconcileRequest:
    left: Path
    right: Path
    group_by: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ("PayableAmount",)
    filters: tuple[FilterItem, ...] = ()
    left_metadata: Path | None = None
    right_metadata: Path | None = None
    left_fields: Path | None = None
    right_fields: Path | None = None
    mode: str = "reconciliation"


@dataclass(frozen=True)
class DrillDownRequest:
    parent: Path
    row: tuple[tuple[str, str], ...]
    by: tuple[str, ...]
    side: str = "both"


@dataclass
class SourceArtifact:
    name: str
    csv: Path
    metadata_path: Path | None
    fields_path: Path | None
    metadata: dict[str, Any]
    fields: dict[str, Any]
    columns: list[str]
    rows: list[dict[str, str]]
    action: str | None
    resolver: FieldResolver
    warnings: list[str] = field(default_factory=list)


@dataclass
class Check:
    code: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": self.status,
            "message": self.message,
            **({"details": self.details} if self.details else {}),
        }


@dataclass
class PreflightResult:
    verdict: str
    profile: PairProfile | None
    left: SourceArtifact | None
    right: SourceArtifact | None
    group_by: tuple[str, ...]
    metrics: tuple[str, ...]
    checks: list[Check]
    claim_scope: str
    mode: str = "reconciliation"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "completed",
            "operation": "reconciliation_preflight",
            "verdict": self.verdict,
            "claim_scope": self.claim_scope,
            "mode": self.mode,
            "profile": self.profile.to_dict() if self.profile else None,
            "left": _source_summary(self.left),
            "right": _source_summary(self.right),
            "requested_group_by": list(self.group_by),
            "metrics": list(self.metrics),
            "tolerance": "0",
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass
class NormalizedSide:
    name: str
    rows: list[dict[str, str]]
    columns: list[str]
    key_columns: list[str]
    metric_columns: list[str]
    display_by_canonical: dict[str, str]
    plan: dict[str, Any]
    fields: list[dict[str, str]]
    implicit_group_by: list[dict[str, str]]
    input_row_count: int
    filtered_row_count: int
    warnings: list[str]


def _filter_value(value: Any, ref: FieldRef) -> Any:
    if ref.field_type in (FieldType.DECIMAL, FieldType.INTEGER):
        return require_decimal(str(value), ref.requested)
    if ref.field_type is FieldType.DATE:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    if ref.field_type is FieldType.PERIOD:
        return datetime.strptime(str(value), "%Y-%m").date()
    return str(value)


def _match_filter(row: Mapping[str, str], ref: FieldRef, item: FilterItem) -> bool:
    raw = row.get(ref.column, "")
    current = typed_value(raw, ref)
    op = item.operator
    if op == "contains":
        if ref.field_type not in (FieldType.STRING, FieldType.JSON):
            raise invalid_plan("contains 只适用于字符串或 JSON 单元格", field=ref.requested)
        return str(item.value) in raw
    if op in ("in", "not-in"):
        expected = [_filter_value(value, ref) for value in item.value]
        matched = current in expected
        return matched if op == "in" else not matched
    if op == "between":
        if current is None:
            return False
        lower, upper = (_filter_value(value, ref) for value in item.value)
        return lower <= current <= upper
    expected = _filter_value(item.value, ref)
    if op == "eq":
        return current == expected
    if op == "ne":
        return current != expected
    if current is None:
        return False
    if op == "gt":
        return current > expected
    if op == "gte":
        return current >= expected
    if op == "lt":
        return current < expected
    if op == "lte":
        return current <= expected
    raise invalid_plan("不支持的 filter operator", operator=op)


def _source_summary(source: SourceArtifact | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "action": source.action,
        "csv": str(source.csv.resolve()),
        "metadata": str(source.metadata_path.resolve()) if source.metadata_path else None,
        "fields": str(source.fields_path.resolve()) if source.fields_path else None,
        "row_count": len(source.rows),
        "request_scopes": _request_scopes(source),
    }


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise invalid_plan(f"{label} 不存在", path=str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise invalid_plan(f"{label} 不是有效 JSON object", path=str(path)) from exc
    if not isinstance(value, dict):
        raise invalid_plan(f"{label} 顶层必须是 JSON object", path=str(path))
    return value


def _load_source(
    name: str,
    csv_path: Path,
    explicit_metadata: Path | None,
    explicit_fields: Path | None = None,
    *,
    observational: bool = False,
) -> SourceArtifact:
    metadata_path, metadata, warnings = load_metadata(csv_path, explicit_metadata)
    if not observational and (warnings or metadata_path is None or metadata is None):
        raise invalid_plan(
            "正式对账要求 cost.py query 生成且格式受支持的 metadata",
            side=name,
            csv=str(csv_path),
        )
    metadata = metadata or {}
    fields_value = metadata.get("artifacts", {}).get("fields") if isinstance(metadata.get("artifacts"), Mapping) else None
    sibling_fields = csv_path.with_name(f"{csv_path.stem}.fields.json")
    if explicit_fields is not None:
        fields_path = explicit_fields
    else:
        declared_fields = Path(str(fields_value)) if fields_value else sibling_fields
        fields_path = sibling_fields if sibling_fields.is_file() else declared_fields
    if observational and explicit_fields is None and not fields_path.is_file():
        fields_path = None
        fields = {}
    else:
        fields = _read_json_object(fields_path, f"{name} fields artifact")
    columns, rows = load_csv(csv_path)
    action = metadata.get("action")
    if (not isinstance(action, str) or not action) and not observational:
        raise invalid_plan("metadata 缺少 action", side=name, path=str(metadata_path))
    action = action if isinstance(action, str) and action else None
    row_actions = {row.get("_action", "") for row in rows if row.get("_action", "")}
    if action and row_actions and row_actions != {action}:
        raise invalid_plan("CSV _action 与 metadata.action 冲突", side=name, metadata_action=action, csv_actions=sorted(row_actions))
    fields_action = fields.get("source_action")
    if action and fields_action and fields_action != action:
        raise invalid_plan("fields source_action 与 metadata.action 冲突", side=name, metadata_action=action, fields_action=fields_action)
    declared = metadata.get("artifacts") if isinstance(metadata.get("artifacts"), Mapping) else {}
    if not observational and not declared.get("csv"):
        raise invalid_plan("正式对账 metadata 缺少对应 CSV 的来源引用", side=name)
    bindings = (
        ("metadata.artifacts.csv", declared.get("csv"), csv_path),
        ("metadata.artifacts.metadata", declared.get("metadata"), metadata_path),
        ("metadata.artifacts.fields", declared.get("fields"), fields_path),
        ("fields.source_csv", fields.get("source_csv"), csv_path),
        ("fields.source_metadata", fields.get("source_metadata"), metadata_path),
    )
    for label, value, actual in bindings:
        if value is None:
            continue
        matches = False
        if isinstance(value, str) and value and actual is not None:
            expected = Path(value).expanduser()
            if not expected.is_absolute():
                expected = actual.parent / expected
            matches = expected.resolve() == actual.resolve()
            # Whole bundles can be relocated after their original directory is removed.
            if not matches and not expected.exists() and expected.name == actual.name:
                matches = actual.parent.resolve() == csv_path.parent.resolve()
        if not matches:
            if not observational:
                raise invalid_plan("对账输入的 CSV、metadata 和 fields 来源不一致", side=name, reference=label)
            warnings.append(f"{name} {label} 与实际输入不一致，仅比较已提供文件")
    return SourceArtifact(
        name=name,
        csv=csv_path,
        metadata_path=metadata_path,
        fields_path=fields_path,
        metadata=metadata,
        fields=fields,
        columns=columns,
        rows=rows,
        action=action,
        resolver=FieldResolver(columns, rows),
        warnings=warnings,
    )


def _check(code: str, status: str, message: str, **details: Any) -> Check:
    return Check(code, status, message, details)


def _coverage_check(source: SourceArtifact) -> Check:
    coverage = source.metadata.get("coverage") if isinstance(source.metadata.get("coverage"), Mapping) else {}
    failed = coverage.get("failed_queries") or []
    requested_scope = coverage.get("requested_scope")
    requested_scope_fulfilled = coverage.get("requested_scope_fulfilled")
    is_complete = coverage.get("is_complete")
    is_provisional = coverage.get("is_provisional")
    freshness = source.metadata.get("freshness") if isinstance(source.metadata.get("freshness"), Mapping) else {}
    if (
        is_complete is True
        and is_provisional is not True
        and requested_scope == "full"
        and requested_scope_fulfilled is True
        and not failed
    ):
        return _check("COVERAGE_COMPLETE", "pass", f"{source.name} coverage 完整")

    provisional_queries = coverage.get("provisional_queries")
    supported_provisional = (
        is_complete is not True
        and is_provisional is True
        and requested_scope == "full"
        and requested_scope_fulfilled is True
        and coverage.get("consistency") == "current_period_total_drift"
        and freshness.get("partial_period") is True
        and isinstance(provisional_queries, list)
        and bool(provisional_queries)
        and not failed
        and all(
            isinstance(query, Mapping)
            and query.get("requested_scope") == "full"
            and query.get("is_provisional") is True
            and query.get("provisional_reason") == "current_period_total_drift"
            and query.get("stop_reason") in {"total_changed", "rows_exceeded_first_total"}
            and query.get("initial_total_boundary_reached") is True
            and query.get("page_fetched") is True
            and query.get("error") is None
            for query in provisional_queries
        )
    )
    if supported_provisional:
        return _check(
            "COVERAGE_PROVISIONAL",
            "warn",
            f"{source.name} coverage 为当前期受限 provisional 快照；允许观察性计算，不能声称最终账期全量",
            provisional_queries=provisional_queries,
        )

    return _check(
        "COVERAGE_INCOMPLETE",
        "block",
        f"{source.name} coverage 不满足完整 full 结果或受支持 provisional 快照条件，不能执行对账",
        is_complete=is_complete,
        is_provisional=is_provisional,
        requested_scope=requested_scope,
        requested_scope_fulfilled=requested_scope_fulfilled,
        consistency=coverage.get("consistency"),
        partial_period=freshness.get("partial_period"),
        failed_queries=failed,
    )


def _request_scopes(source: SourceArtifact) -> list[dict[str, Any]]:
    scopes: list[dict[str, Any]] = []
    for query in source.metadata.get("queries") or []:
        if not isinstance(query, Mapping) or not isinstance(query.get("request_body"), Mapping):
            continue
        scope = {
            canonical_name(str(key)): value
            for key, value in query["request_body"].items()
            if canonical_name(str(key)) not in _EXECUTION_SCOPE_FIELDS | _GRAIN_FIELDS
        }
        scopes.append(scope)
    return scopes


def _scope_value(value: Any) -> str:
    if isinstance(value, Mapping):
        normalized = {str(key): _scope_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, list):
        return json.dumps(sorted(_scope_value(item) for item in value), ensure_ascii=False, separators=(",", ":"))
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _scope_check(left: SourceArtifact, right: SourceArtifact) -> Check:
    if left.warnings or right.warnings:
        return _check("REQUEST_SCOPE_UNVERIFIED", "warn", "输入来源关联未确认，只解释已提供文件的范围")
    left_scopes = _request_scopes(left)
    right_scopes = _request_scopes(right)
    if not left_scopes or not right_scopes:
        return _check("REQUEST_SCOPE_MISSING", "block", "metadata 缺少可比较的 query.request_body")
    left_values: dict[str, set[str]] = {}
    right_values: dict[str, set[str]] = {}
    for target, scopes in ((left_values, left_scopes), (right_values, right_scopes)):
        for scope in scopes:
            for key, value in scope.items():
                target.setdefault(key, set()).add(_scope_value(value))
    differing: dict[str, Any] = {}
    all_fields = sorted(set(left_values) | set(right_values))
    for key in all_fields:
        if left_values.get(key, set()) != right_values.get(key, set()):
            differing[key] = {
                "left": sorted(left_values.get(key, set())),
                "right": sorted(right_values.get(key, set())),
            }
    if differing:
        return _check("REQUEST_SCOPE_MISMATCH", "block", "两侧业务请求范围不等价", fields=differing)
    return _check("REQUEST_SCOPE_MATCH", "pass", "两侧账期、账号及业务筛选范围等价")


def _freshness_check(left: SourceArtifact, right: SourceArtifact) -> Check:
    partial = []
    notes: list[str] = []
    for source in (left, right):
        freshness = source.metadata.get("freshness") if isinstance(source.metadata.get("freshness"), Mapping) else {}
        if freshness.get("partial_period"):
            partial.append(source.name)
        notes.extend(str(item) for item in freshness.get("notes") or [])
    if partial:
        return _check(
            "CURRENT_PERIOD",
            "warn",
            "查询包含当前月份，可能存在出账或分账延迟；差异是暂态观察结果，不能直接判定为账务异常",
            sides=partial,
            notes=list(dict.fromkeys(notes)),
        )
    return _check("CLOSED_PERIOD", "pass", "两侧未标记为当前未完结月份")


def _resolve_fields(source: SourceArtifact, fields: Sequence[str], kind: str) -> tuple[list[FieldRef], list[Check]]:
    refs: list[FieldRef] = []
    checks: list[Check] = []
    for requested in fields:
        try:
            refs.append(source.resolver.resolve(requested))
        except BillingQueryError as exc:
            checks.append(_check(f"{kind.upper()}_FIELD_MISSING", "block", f"{source.name} 缺少字段 {requested}", error=exc.error_dict()))
    return refs, checks


def _currency_blank_check(source: SourceArtifact, metric_refs: Sequence[FieldRef]) -> Check:
    currency_columns = []
    for ref in metric_refs:
        expected = money_currency_field(ref.canonical)
        candidates = source.resolver.canonical_columns.get(expected or "", [])
        if len(candidates) != 1:
            return _check(
                "CURRENCY_FIELD_MISSING",
                "block",
                f"{source.name} 金额字段 {ref.column} 缺少唯一币种字段",
                expected_currency_field=expected,
                candidates=candidates,
            )
        currency_columns.append(candidates[0])
    blank = {column: sum(1 for row in source.rows if not row.get(column, "")) for column in set(currency_columns)}
    blank = {key: value for key, value in blank.items() if value}
    if blank:
        return _check("CURRENCY_VALUE_MISSING", "block", f"{source.name} 存在空币种，无法确定金额单位", blank_counts=blank)
    return _check("CURRENCY_READY", "pass", f"{source.name} 金额币种字段完整", currency_fields=sorted(set(currency_columns)))


def _nonstandard_check(
    profile: PairProfile,
    group_by: Sequence[str],
    filters: Sequence[FilterItem],
) -> Check:
    requested = sorted(
        ({canonical_name(item) for item in group_by} | {canonical_name(item.field) for item in filters})
        & NONSTANDARD_DIMENSIONS
    )
    if not requested:
        return _check("STANDARD_DIMENSIONS", "pass", "聚合维度均为标准共同出账维度")
    return _check(
        "NONSTANDARD_DIMENSION",
        "warn",
        f"双侧分组或过滤使用非标准维度 {', '.join(requested)}；Project/Tag 在账单和分账侧的来源与语义可能不同，"
        "同名值不保证对应同一业务归属。金额差额仅为观察结果，不证明标准对账不一致或多算；"
        "核验账务一致性可按 Product、InstanceNo 等共同出账维度对账，再单侧展开归属",
        dimensions=requested,
        profile=profile.name,
    )


def _dimension_policy_check(profile: PairProfile, group_by: Sequence[str]) -> Check:
    unsupported = sorted(
        canonical_name(item)
        for item in group_by
        if canonical_name(item) not in profile.standard_dimensions | NONSTANDARD_DIMENSIONS
    )
    if unsupported:
        return _check(
            "UNREGISTERED_DIMENSION",
            "block",
            "聚合维度未登记为该 Action Pair 的共同语义",
            dimensions=unsupported,
            allowed=sorted(profile.standard_dimensions | NONSTANDARD_DIMENSIONS),
        )
    return _check("DIMENSION_POLICY_READY", "pass", "聚合维度符合 Action Pair 关系目录")


def _metrics_check(metrics: Sequence[str]) -> Check:
    unsupported = sorted(item for item in metrics if canonical_name(item) not in RECONCILIATION_METRIC_CANONICAL)
    if unsupported:
        return _check(
            "UNSUPPORTED_RECONCILIATION_METRIC",
            "block",
            "对账仅支持已登记的可加和金额字段",
            fields=unsupported,
            allowed=list(RECONCILIATION_METRICS),
        )
    return _check("METRICS_READY", "pass", "金额字段可加和，使用 Decimal 且 tolerance=0")


def _amount_values_check(source: SourceArtifact, refs: Sequence[FieldRef]) -> Check:
    missing = 0
    try:
        for row in source.rows:
            for ref in refs:
                value = row.get(ref.column, "")
                if value == "":
                    missing += 1
                else:
                    _decimal(value, ref.column)
    except BillingQueryError as exc:
        return _check("AMOUNT_VALUE_INVALID", "block", f"{source.name} 含无法计算的金额", error=exc.error_dict())
    if missing:
        return _check("AMOUNT_VALUE_MISSING", "warn", f"{source.name} 有 {missing} 个缺失金额，受影响分组保持未知，不补零")
    return _check("AMOUNT_VALUES_READY", "pass", f"{source.name} 金额值均可解析为有限 Decimal")


def _verdict(checks: Sequence[Check]) -> tuple[str, str]:
    if any(check.status == "block" for check in checks):
        return "block", "blocked"
    if any(check.status == "warn" for check in checks):
        nonstandard = any(check.code == "NONSTANDARD_DIMENSION" for check in checks)
        provisional = any(check.code in {"CURRENT_PERIOD", "COVERAGE_PROVISIONAL"} for check in checks)
        return "warn", "provisional" if provisional and not nonstandard else "observational"
    return "pass", "full_dataset"


def preflight(request: ReconcileRequest) -> PreflightResult:
    if request.mode not in {"reconciliation", "observational"}:
        raise invalid_plan("未知比较模式", mode=request.mode)
    observational = request.mode == "observational"
    checks: list[Check] = []
    try:
        left = _load_source("left", request.left, request.left_metadata, request.left_fields, observational=observational)
        right = _load_source("right", request.right, request.right_metadata, request.right_fields, observational=observational)
    except BillingQueryError as exc:
        checks.append(_check(
            "ARTIFACT_INVALID",
            "block",
            "输入产物无效；没有可用于正式对账的有效双侧输入；尚未执行来源关系、范围、维度或金额检查。",
            error=exc.error_dict(),
            recovery_options=[
                {
                    "action": "inspect_artifact_set",
                    "description": "核对两侧 CSV、同名 .meta.json 和 .fields.json 是否齐全、可读且属于对应查询。",
                },
                {
                    "action": "regenerate_query_artifacts",
                    "description": "正式对账需要补齐证据；若重新查询，应说明它是新快照，不能冒充用户指定的原文件。",
                },
                {
                    "action": "rerun_preflight",
                    "description": "输入修复后按任务继续：需要结果时直接 reconcile run（内置检查），只需诊断时用 reconcile preflight；无需依次调用两者。",
                },
            ],
            retry_policy="不要继续 reconcile run；不要对相同无效输入重复 reconcile run；修复输入或明确选择适用模式后再执行。不要据此判断范围不一致、维度检查结果或金额差额。",
        ))
        return PreflightResult("block", None, None, None, request.group_by, request.metrics, checks, "blocked", request.mode)
    profile = find_profile(left.action, right.action) if left.action and right.action else None
    if profile is None:
        checks.append(_check("ACTION_PAIR_UNSUPPORTED", "warn" if observational else "block", "两侧 Action Pair 未登记或缺少来源证据，不能形成标准对账结论", left_action=left.action, right_action=right.action))
        group_by = request.group_by
    else:
        checks.append(_check("ACTION_PAIR_SUPPORTED", "pass", "Action Pair 已登记", profile=profile.name))
        group_by = request.group_by or profile.default_group_by
        if not observational:
            checks.append(_dimension_policy_check(profile, group_by))
        checks.append(_nonstandard_check(profile, group_by, request.filters))
    if observational:
        checks.append(_check("OBSERVATIONAL_COMPARISON", "warn", "按指定输入范围计算；同名分组键不保证业务实体相同，数值差异不证明多算或标准对账不一致"))
        if not group_by:
            checks.append(_check("GROUP_BY_REQUIRED", "block", "无法推导共同维度时，观察性比较须显式指定 --group-by"))
        for source in (left, right):
            if source.metadata_path is None or source.fields_path is None:
                checks.append(_check("SOURCE_EVIDENCE_LIMITED", "warn", f"{source.name} 缺少完整查询证据，只解释实际文件，来源、范围完整性或时效未完全验证"))
    for source in (left, right):
        checks.extend(_check("SOURCE_ARTIFACT_WARNING", "warn", warning) for warning in source.warnings)
    comparability = [_coverage_check(left), _coverage_check(right), _scope_check(left, right)]
    for check in comparability:
        if observational and check.status == "block":
            check.status = "warn"
            check.message += "；仅比较已交付文件，保留此限制，不形成正式对账结论"
    checks.extend(comparability)
    if left.metadata_path and right.metadata_path:
        checks.append(_freshness_check(left, right))
    checks.append(_metrics_check(request.metrics))
    left_group, left_group_checks = _resolve_fields(left, group_by, "group_by")
    right_group, right_group_checks = _resolve_fields(right, group_by, "group_by")
    left_metrics, left_metric_checks = _resolve_fields(left, request.metrics, "metric")
    right_metrics, right_metric_checks = _resolve_fields(right, request.metrics, "metric")
    filter_fields = tuple(dict.fromkeys(item.field for item in request.filters))
    left_filters, left_filter_checks = _resolve_fields(left, filter_fields, "filter")
    right_filters, right_filter_checks = _resolve_fields(right, filter_fields, "filter")
    checks.extend((
        *left_group_checks,
        *right_group_checks,
        *left_metric_checks,
        *right_metric_checks,
        *left_filter_checks,
        *right_filter_checks,
    ))
    if len(left_group) == len(group_by) and len(right_group) == len(group_by):
        checks.append(_check("GROUP_BY_FIELDS_READY", "pass", "两侧聚合维度字段均存在"))
    if len(left_filters) == len(filter_fields) and len(right_filters) == len(filter_fields):
        checks.append(_check("FILTER_FIELDS_READY", "pass", "公共本地 Filter 字段在两侧均存在"))
    if len(left_metrics) == len(request.metrics):
        checks.append(_currency_blank_check(left, left_metrics))
        checks.append(_amount_values_check(left, left_metrics))
    if len(right_metrics) == len(request.metrics):
        checks.append(_currency_blank_check(right, right_metrics))
        checks.append(_amount_values_check(right, right_metrics))
    verdict, claim_scope = _verdict(checks)
    if observational and verdict != "block":
        claim_scope = "observational"
    return PreflightResult(verdict, profile, left, right, tuple(group_by), request.metrics, checks, claim_scope, request.mode)


def _normalize_side(
    source: SourceArtifact,
    group_by: Sequence[str],
    metrics: Sequence[str],
    filters: Sequence[FilterItem],
    parent_constraints: Mapping[str, str] | None = None,
) -> NormalizedSide:
    group_refs = [source.resolver.resolve(item) for item in group_by]
    metric_refs = [source.resolver.resolve(item) for item in metrics]
    for ref in metric_refs:
        require_registered_money_metric(ref, "对账 metric")
    group_refs, implicit_group_by = ensure_money_grouping(source.resolver, metric_refs, group_refs)
    rows = [dict(row) for row in source.rows]
    if parent_constraints:
        constraint_refs = {canonical_name(field): source.resolver.resolve(field) for field in parent_constraints}
        rows = [
            row
            for row in rows
            if all(
                (row.get(constraint_refs[key].column, "") or MISSING_DIMENSION) == value
                for key, value in parent_constraints.items()
            )
        ]
    filter_refs = [(item, source.resolver.resolve(item.field)) for item in filters]
    filtered = [row for row in rows if all(_match_filter(row, ref, item) for item, ref in filter_refs)]
    display_by_canonical = {ref.canonical: ref.column for ref in group_refs}
    key_columns = [ref.canonical for ref in group_refs]
    buckets: dict[tuple[str, ...], list[tuple[Decimal, int]]] = {}
    missing_values: set[tuple[tuple[str, ...], int]] = set()
    for row in filtered:
        key = tuple(row.get(ref.column, "") for ref in group_refs)
        values = buckets.setdefault(key, [(Decimal("0"), 0) for _ in metric_refs])
        for index, ref in enumerate(metric_refs):
            raw = row.get(ref.column, "")
            if raw == "":
                missing_values.add((key, index))
                continue
            total, count = values[index]
            values[index] = (total + _decimal(raw, ref.requested), count + 1)
    output_rows: list[dict[str, str]] = []
    missing_aggregate_values = 0
    for key in sorted(buckets):
        record = {
            ref.column: (
                MISSING_DIMENSION
                if value == "" and ref.canonical in {group_ref.canonical for group_ref in group_refs}
                else value
            )
            for ref, value in zip(group_refs, key)
        }
        for index, (ref, (value, count)) in enumerate(zip(metric_refs, buckets[key])):
            if count == 0 or (key, index) in missing_values:
                record[ref.column] = ""
                missing_aggregate_values += 1
            else:
                record[ref.column] = _format_decimal(value)
        output_rows.append(record)
    normalized: list[dict[str, str]] = []
    for row in output_rows:
        record: dict[str, str] = {}
        for column, value in row.items():
            canonical = canonical_name(column)
            record[canonical] = value
        normalized.append(record)
    metric_columns = [canonical_name(ref.column) for ref in metric_refs]
    plan = {
        "operation": "aggregate_for_reconciliation",
        "group_by": [ref.column for ref in group_refs],
        "metrics": [ref.column for ref in metric_refs],
        "filters": [
            {"field": item.field, "operator": item.operator, "value": item.value}
            for item in filters
        ],
    }
    fields = [
        *[item.to_dict() for item in group_refs],
        *[item.to_dict() for item in metric_refs],
        *[ref.to_dict() for _, ref in filter_refs],
        *[item.to_dict() for item in implicit_group_by],
    ]
    warnings = (
        [f"{missing_aggregate_values} 个 SUM 聚合结果因存在缺失金额而保持未知"]
        if missing_aggregate_values
        else []
    )
    return NormalizedSide(
        name=source.name,
        rows=normalized,
        columns=[canonical_name(item) for item in [*plan["group_by"], *plan["metrics"]]],
        key_columns=key_columns,
        metric_columns=metric_columns,
        display_by_canonical=display_by_canonical,
        plan=plan,
        fields=fields,
        implicit_group_by=[item.to_dict() for item in implicit_group_by],
        input_row_count=len(rows),
        filtered_row_count=len(filtered),
        warnings=warnings,
    )


def _decimal(value: str, field: str) -> Decimal:
    return require_decimal(
        value,
        field,
        invalid_message="对账金额不是合法 Decimal",
        non_finite_message="对账金额不是有限 Decimal",
    )


def _index_rows(side: NormalizedSide) -> dict[tuple[str, ...], dict[str, str]]:
    index: dict[tuple[str, ...], dict[str, str]] = {}
    duplicates: list[list[str]] = []
    for row in side.rows:
        key = tuple(row.get(column, "") for column in side.key_columns)
        if key in index:
            duplicates.append(list(key))
        index[key] = row
    if duplicates:
        raise invalid_plan("双侧聚合后有效 Join Key 仍不唯一", side=side.name, duplicate_keys=duplicates[:20])
    return index


def _join_normalized(
    left: NormalizedSide,
    right: NormalizedSide,
    metrics: Sequence[str],
    claim_scope: str,
    *,
    observed_empty_groups: bool = False,
) -> tuple[list[str], list[dict[str, str]], dict[str, int]]:
    if left.key_columns != right.key_columns:
        raise invalid_plan("双侧聚合后的有效 Join Key 不一致", left=left.key_columns, right=right.key_columns)
    left_index = _index_rows(left)
    right_index = _index_rows(right)
    keys = sorted(set(left_index) | set(right_index))
    key_display = [left.display_by_canonical.get(column, right.display_by_canonical.get(column, column)) for column in left.key_columns]
    metric_canonical = [canonical_name(item) for item in metrics]
    columns = list(key_display)
    for metric, canonical in zip(metrics, metric_canonical):
        columns.extend((f"left_{metric}", f"right_{metric}", f"difference_{metric}", f"status_{metric}"))
    columns.extend(("status", "claim_scope"))
    rows: list[dict[str, str]] = []
    counts = {status: 0 for status in ("matched", "mismatched", "left_only", "right_only", "inconclusive")}
    for key in keys:
        left_row = left_index.get(key)
        right_row = right_index.get(key)
        record = {name: value for name, value in zip(key_display, key)}
        metric_statuses: list[str] = []
        for metric, canonical in zip(metrics, metric_canonical):
            left_value = left_row.get(canonical, "") if left_row else ""
            right_value = right_row.get(canonical, "") if right_row else ""
            if left_row is None:
                status = "right_only"
                if observed_empty_groups:
                    left_value = "0"
                difference = right_value if observed_empty_groups and right_value != "" and MISSING_DIMENSION not in key else ""
            elif right_row is None:
                status = "left_only"
                if observed_empty_groups:
                    right_value = "0"
                difference = _format_decimal(-_decimal(left_value, canonical)) if observed_empty_groups and left_value != "" and MISSING_DIMENSION not in key else ""
            elif left_value == "" or right_value == "" or MISSING_DIMENSION in key:
                status = "inconclusive"
                difference = ""
            else:
                difference_value = _decimal(right_value, canonical) - _decimal(left_value, canonical)
                difference = _format_decimal(difference_value)
                status = "matched" if difference_value == 0 else "mismatched"
            if claim_scope in {"observational", "blocked"} and status in {"matched", "mismatched"}:
                status = "inconclusive"
            record[f"left_{metric}"] = left_value
            record[f"right_{metric}"] = right_value
            record[f"difference_{metric}"] = difference
            record[f"status_{metric}"] = status
            metric_statuses.append(status)
        overall = _overall_status(metric_statuses)
        record["status"] = overall
        record["claim_scope"] = claim_scope
        counts[overall] += 1
        rows.append(record)
    return columns, rows, counts


def _overall_status(statuses: Sequence[str]) -> str:
    for candidate in ("inconclusive", "left_only", "right_only", "mismatched"):
        if candidate in statuses:
            return candidate
    return "matched"


def _normalized_output_paths(output: Path) -> tuple[Path, Path, Path]:
    return (
        output.with_name(f"{output.stem}.left.csv"),
        output.with_name(f"{output.stem}.right.csv"),
        output.with_name(f"{output.stem}.meta.json"),
    )


def _display_normalized(side: NormalizedSide, metrics: Sequence[str]) -> tuple[list[str], list[dict[str, str]]]:
    key_names = [side.display_by_canonical.get(item, item) for item in side.key_columns]
    metric_names = list(metrics)
    columns = [*key_names, *metric_names]
    rows = [
        {
            **{name: row.get(canonical, "") for name, canonical in zip(key_names, side.key_columns)},
            **{name: row.get(canonical_name(name), "") for name in metric_names},
        }
        for row in side.rows
    ]
    return columns, rows


def _source_payload(source: SourceArtifact) -> dict[str, Any]:
    return {
        **_source_summary(source),
        "source_metadata": source.metadata,
    }


def run_reconciliation(
    request: ReconcileRequest,
    output: Path,
    *,
    overwrite: bool = False,
    parent_constraints: Mapping[str, str] | None = None,
    operation: str = "reconciliation",
    parent_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if request.mode == "observational" and operation == "reconciliation":
        operation = "comparison"
    result = preflight(request)
    if result.verdict == "block" or result.left is None or result.right is None:
        raise BillingQueryError(
            ErrorCode.INVALID_ARGUMENT,
            "对账 preflight 未通过",
            ExitCode.INVALID_ARGUMENT,
            {"preflight": result.to_dict()},
        )
    left_normalized = _normalize_side(result.left, result.group_by, result.metrics, request.filters, parent_constraints)
    right_normalized = _normalize_side(result.right, result.group_by, result.metrics, request.filters, parent_constraints)
    columns, rows, counts = _join_normalized(left_normalized, right_normalized, result.metrics, result.claim_scope, observed_empty_groups=request.mode == "observational")
    left_output, right_output, metadata_output = _normalized_output_paths(output)
    if not overwrite:
        existing = [str(path) for path in (output, left_output, right_output, metadata_output) if path.exists()]
        if existing:
            raise BillingQueryError(ErrorCode.OUTPUT_EXISTS, f"输出文件已存在：{existing[0]}", ExitCode.OUTPUT_FAILED, {"paths": existing})
    left_columns, left_rows = _display_normalized(left_normalized, result.metrics)
    right_columns, right_rows = _display_normalized(right_normalized, result.metrics)
    atomic_write_csv(left_output, left_columns, left_rows, overwrite=True)
    atomic_write_csv(right_output, right_columns, right_rows, overwrite=True)
    atomic_write_csv(output, columns, rows, overwrite=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "operation": operation,
        "profile": result.profile.to_dict() if result.profile else None,
        "preflight": result.to_dict(),
        "claim_scope": result.claim_scope,
        "inputs": {"left": _source_payload(result.left), "right": _source_payload(result.right)},
        "plan": {
            "group_by": list(result.group_by),
            "effective_join_keys": [
                left_normalized.display_by_canonical.get(key, key)
                for key in left_normalized.key_columns
            ],
            "metrics": list(result.metrics),
            "filters": [{"field": item.field, "operator": item.operator, "value": item.value} for item in request.filters],
            "tolerance": "0",
            "difference_formula": "right_amount - left_amount",
            "mode": request.mode,
            "empty_group_policy": "zero_with_presence_status_in_input_files" if request.mode == "observational" else "unknown",
            "parent_constraints": dict(parent_constraints or {}),
        },
        "normalization": {
            "left": _normalized_payload(left_normalized, left_output),
            "right": _normalized_payload(right_normalized, right_output),
        },
        "result": {
            "csv": str(output.resolve()),
            "metadata": str(metadata_output.resolve()),
            "row_count": len(rows),
            "columns": columns,
            "status_counts": counts,
        },
        "interpretation": {
            "mode": request.mode,
            "overcharge_claim_allowed": False,
            "mismatch_rules": list(MISMATCH_INTERPRETATION_RULES),
            "authoritative_sources": {
                "billing_amount_reconciliation": ["ListBill", "ListBillDetail"],
                "split_bill_detail": "费用归属参考，不作为账单金额对账依据",
            },
        },
        "warnings": [check.message for check in result.checks if check.status == "warn"] + left_normalized.warnings + right_normalized.warnings,
        **({"parent": dict(parent_context)} if parent_context else {}),
    }
    atomic_write_json(metadata_output, payload, overwrite=True)
    return {
        "status": "completed",
        "operation": operation,
        "verdict": result.verdict,
        "claim_scope": result.claim_scope,
        "row_count": len(rows),
        "status_counts": counts,
        "warnings": payload["warnings"],
        "artifacts": {
            "csv": str(output.resolve()),
            "left_normalized": str(left_output.resolve()),
            "right_normalized": str(right_output.resolve()),
            "metadata": str(metadata_output.resolve()),
        },
    }


def _normalized_payload(side: NormalizedSide, output: Path) -> dict[str, Any]:
    return {
        "csv": str(output.resolve()),
        "input_row_count": side.input_row_count,
        "filtered_row_count": side.filtered_row_count,
        "output_row_count": len(side.rows),
        "plan": side.plan,
        "fields": side.fields,
        "implicit_group_by": side.implicit_group_by,
        "warnings": side.warnings,
    }


def _load_parent(request: DrillDownRequest) -> tuple[dict[str, Any], dict[str, str]]:
    metadata_path = request.parent.with_name(f"{request.parent.stem}.meta.json")
    metadata = _read_json_object(metadata_path, "父级对账 metadata")
    if metadata.get("operation") not in {"reconciliation", "comparison", "drill_down"}:
        raise invalid_plan("--from 不是 cost.py reconcile 产生的对账或下钻结果", operation=metadata.get("operation"))
    columns, rows = load_csv(request.parent)
    resolver = FieldResolver(columns, rows)
    selectors = [(resolver.resolve(field), value) for field, value in request.row]
    matches = [row for row in rows if all(row.get(ref.column, "") == value for ref, value in selectors)]
    if len(matches) != 1:
        raise invalid_plan("--row 必须唯一命中一条父级对账结果", match_count=len(matches), selectors=dict(request.row))
    return metadata, matches[0]


def _parent_constraints(metadata: Mapping[str, Any], parent_row: Mapping[str, str]) -> dict[str, str]:
    constraints: dict[str, str] = {}
    for field in metadata.get("plan", {}).get("group_by") or []:
        canonical = canonical_name(str(field))
        candidates = [key for key in parent_row if canonical_name(key) == canonical]
        if len(candidates) == 1:
            constraints[canonical] = parent_row[candidates[0]]
    for field in metadata.get("plan", {}).get("effective_join_keys") or []:
        canonical = canonical_name(str(field))
        candidates = [key for key in parent_row if canonical_name(key) == canonical]
        if len(candidates) == 1:
            constraints[canonical] = parent_row[candidates[0]]
    return constraints


def _filter_items(value: Sequence[Mapping[str, Any]]) -> tuple[FilterItem, ...]:
    result: list[FilterItem] = []
    for item in value:
        missing = [key for key in ("field", "operator", "value") if key not in item]
        if missing:
            raise invalid_plan("filter object 缺少必填字段", missing_fields=missing)
        field = item["field"]
        operator = item["operator"]
        if not isinstance(field, str) or not field.strip():
            raise invalid_plan("filter.field 必须是非空字符串")
        if not isinstance(operator, str):
            raise invalid_plan("filter.operator 必须是字符串")
        parsed_operator = normalize_filter_operator(operator)
        filter_value = item["value"]
        if parsed_operator in ("in", "not-in") and not isinstance(filter_value, list):
            raise invalid_plan(f"{parsed_operator} 的 value 必须是数组", field=field)
        if parsed_operator == "between" and (not isinstance(filter_value, list) or len(filter_value) != 2):
            raise invalid_plan("between 的 value 必须是两个元素的数组", field=field)
        if parsed_operator not in ("in", "not-in", "between") and isinstance(filter_value, (list, dict)):
            raise invalid_plan(f"{parsed_operator} 的 value 必须是标量", field=field)
        result.append(FilterItem(field, parsed_operator, filter_value))
    return tuple(result)


def _conservation(
    parent_row: Mapping[str, str],
    metrics: Sequence[str],
    child_rows: Sequence[Mapping[str, str]],
    side: str,
    parent_side: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    sides = ("left", "right") if side == "both" else (side,)
    for current_side in sides:
        for metric in metrics:
            parent_field = metric if parent_side == current_side else f"{current_side}_{metric}"
            parent_value = parent_row.get(parent_field, "")
            child_field = f"{current_side}_{metric}" if side == "both" else metric
            child_values = [row.get(child_field, "") for row in child_rows]
            if parent_value == "" or any(value == "" for value in child_values):
                checks.append({"side": current_side, "metric": metric, "status": "inconclusive", "parent": parent_value, "child_sum": None})
                continue
            child_sum = sum((_decimal(value, child_field) for value in child_values), Decimal("0"))
            delta = child_sum - _decimal(parent_value, f"{current_side}_{metric}")
            checks.append({
                "side": current_side,
                "metric": metric,
                "status": "matched" if delta == 0 else "mismatched",
                "parent": parent_value,
                "child_sum": _format_decimal(child_sum),
                "difference": _format_decimal(delta),
            })
    return {
        "status": "matched" if checks and all(item["status"] == "matched" for item in checks) else "inconclusive",
        "checks": checks,
    }


def drill_down(request: DrillDownRequest, output: Path, *, overwrite: bool = False) -> dict[str, Any]:
    if request.side not in {"both", "left", "right"}:
        raise invalid_plan("--side 只能是 both、left 或 right")
    metadata, parent_row = _load_parent(request)
    parent_side = metadata.get("side")
    if parent_side in {"left", "right"} and request.side != parent_side:
        raise invalid_plan("单侧下钻结果只能继续展开同一侧", parent_side=parent_side, requested_side=request.side)
    plan = metadata.get("plan") if isinstance(metadata.get("plan"), Mapping) else {}
    current_group = tuple(str(item) for item in plan.get("group_by") or [])
    by = tuple(item for item in request.by if canonical_name(item) not in {canonical_name(value) for value in current_group})
    if not by:
        raise invalid_plan("--by 必须增加至少一个更细维度")
    group_by = (*current_group, *by)
    inputs = metadata.get("inputs") if isinstance(metadata.get("inputs"), Mapping) else {}
    metrics = tuple(str(item) for item in plan.get("metrics") or [])
    filters = _filter_items(plan.get("filters") or [])
    constraints = _parent_constraints(metadata, parent_row)
    observational = plan.get("mode") == "observational"
    if request.side == "both":
        child_request = ReconcileRequest(
            left=Path(str(inputs["left"]["csv"])),
            right=Path(str(inputs["right"]["csv"])),
            left_metadata=Path(inputs["left"]["metadata"]) if inputs["left"]["metadata"] else None,
            right_metadata=Path(inputs["right"]["metadata"]) if inputs["right"]["metadata"] else None,
            left_fields=Path(inputs["left"]["fields"]) if inputs["left"]["fields"] else None,
            right_fields=Path(inputs["right"]["fields"]) if inputs["right"]["fields"] else None,
            group_by=group_by,
            metrics=metrics,
            filters=filters,
            mode="observational" if observational else "reconciliation",
        )
        manifest = run_reconciliation(
            child_request,
            output,
            overwrite=overwrite,
            parent_constraints=constraints,
            operation="drill_down",
            parent_context={"csv": str(request.parent.resolve()), "row": dict(request.row), "constraints": constraints},
        )
        _, child_rows = load_csv(output)
    else:
        manifest, child_rows = _drill_one_side(metadata, parent_row, constraints, group_by, by, metrics, filters, request.side, output, overwrite)
    conservation = _conservation(parent_row, metrics, child_rows, request.side, parent_side=parent_side)
    metadata_output = output.with_name(f"{output.stem}.meta.json")
    child_metadata = _read_json_object(metadata_output, "下钻 metadata")
    child_metadata["conservation"] = conservation
    if conservation["status"] != "matched" or metadata.get("claim_scope") == "inconclusive":
        child_metadata["claim_scope"] = "inconclusive"
        warning = (
            "下钻子项未通过父级金额守恒检查，不能据此归因父级差异"
            if conservation["status"] != "matched"
            else "父级结果仍缺少有效守恒证据，本次下钻继承其限制，不能升级为正式对账结论"
        )
        child_metadata.setdefault("warnings", []).append(warning)
        columns, child_rows = load_csv(output)
        for column in ("status", "claim_scope", *(f"status_{metric}" for metric in metrics)):
            if column not in columns:
                columns.append(column)
        for row in child_rows:
            row.update(status="inconclusive", claim_scope="inconclusive")
            for metric in metrics:
                row[f"status_{metric}"] = "inconclusive"
        atomic_write_csv(output, columns, child_rows, overwrite=True)
        counts = {status: 0 for status in ("matched", "mismatched", "left_only", "right_only", "inconclusive")}
        counts["inconclusive"] = len(child_rows)
        child_metadata["result"].update(columns=columns, status_counts=counts)
        manifest.update(verdict="warn", status_counts=counts)
    atomic_write_json(metadata_output, child_metadata, overwrite=True)
    return {**manifest, "conservation": conservation, "claim_scope": child_metadata.get("claim_scope"), "warnings": child_metadata.get("warnings", [])}


def _drill_one_side(
    metadata: Mapping[str, Any],
    parent_row: Mapping[str, str],
    constraints: Mapping[str, str],
    group_by: Sequence[str],
    by: Sequence[str],
    metrics: Sequence[str],
    filters: Sequence[FilterItem],
    side: str,
    output: Path,
    overwrite: bool,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    source_info = metadata["inputs"][side]
    source = _load_source(
        side,
        Path(str(source_info["csv"])),
        Path(source_info["metadata"]) if source_info["metadata"] else None,
        Path(source_info["fields"]) if source_info["fields"] else None,
        observational=metadata.get("plan", {}).get("mode") == "observational",
    )
    normalized = _normalize_side(source, group_by, metrics, filters, constraints)
    columns, rows = _display_normalized(normalized, metrics)
    metadata_output = output.with_name(f"{output.stem}.meta.json")
    if not overwrite:
        existing = [str(path) for path in (output, metadata_output) if path.exists()]
        if existing:
            raise BillingQueryError(ErrorCode.OUTPUT_EXISTS, f"输出文件已存在：{existing[0]}", ExitCode.OUTPUT_FAILED)
    atomic_write_csv(output, columns, rows, overwrite=True)
    nonstandard = sorted({canonical_name(item) for item in by} & NONSTANDARD_DIMENSIONS)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "operation": "drill_down",
        "side": side,
        "claim_scope": (
            "observational" if metadata.get("plan", {}).get("mode") == "observational"
            else "attribution_breakdown" if nonstandard
            else metadata.get("claim_scope", "full_dataset")
        ),
        "inputs": metadata["inputs"],
        "plan": {**dict(metadata.get("plan") or {}), "group_by": list(group_by), "parent_constraints": dict(constraints)},
        "parent": {"row": dict(parent_row), "constraints": dict(constraints)},
        "normalization": {side: _normalized_payload(normalized, output)},
        "result": {"csv": str(output.resolve()), "metadata": str(metadata_output.resolve()), "row_count": len(rows), "columns": columns},
        "warnings": source.warnings + (
            ["Project/Tag 仅用于分账侧归属展开，不表示与账单明细同名字段语义一致"]
            if nonstandard
            else []
        ),
    }
    atomic_write_json(metadata_output, payload, overwrite=True)
    return ({
        "status": "completed",
        "operation": "drill_down",
        "side": side,
        "row_count": len(rows),
        "warnings": payload["warnings"],
        "artifacts": {"csv": str(output.resolve()), "metadata": str(metadata_output.resolve())},
    }, rows)
