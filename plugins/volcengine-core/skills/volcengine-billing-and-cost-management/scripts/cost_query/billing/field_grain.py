"""Action × 响应字段 × 服务端粒度的保留能力矩阵。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..common.errors import BillingQueryError, ErrorCode, ExitCode
from ..common.fields import canonical_name


@dataclass(frozen=True)
class FieldGrainRule:
    field: str
    role: str
    required_request: Mapping[str, Any]
    available_request_values: Mapping[str, tuple[Any, ...]]
    available_when: str
    unavailable_meaning: str

    def guidance(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "required_request": dict(self.required_request),
            "available_request_values": {
                name: list(values) for name, values in self.available_request_values.items()
            },
            "available_when": self.available_when,
            "unavailable_meaning": self.unavailable_meaning,
            "planning_instruction": (
                f"用户明确需要 {self.field} 时，首次查询前先用 available_request_values 检查候选请求；"
                "候选值已合法则保持原值，只有不合法时才应用 required_request 作为修复补丁。"
            ),
        }


def _detail_identifier(field: str, label: str) -> FieldGrainRule:
    return FieldGrainRule(
        field=field,
        role="detail_identifier",
        required_request={"GroupPeriod": 2},
        available_request_values={"GroupPeriod": (2,)},
        available_when=f"GroupPeriod=2（明细）时 {label} 才具有逐条明细语义。",
        unavailable_meaning=(
            f"GroupPeriod=0/1 或省略时，{label} 可能为空或不返回；"
            "这表示服务端汇总粒度未保留该字段，不表示业务数据不存在。"
        ),
    )


def _list_bill_detail_rule(
    field: str,
    *,
    role: str,
    required_request: Mapping[str, Any],
    available_request_values: Mapping[str, tuple[Any, ...]],
    available_when: str,
    unavailable_meaning: str,
) -> FieldGrainRule:
    return FieldGrainRule(
        field=field,
        role=role,
        required_request=required_request,
        available_request_values=available_request_values,
        available_when=available_when,
        unavailable_meaning=unavailable_meaning,
    )


ACTION_FIELD_GRAIN_RULES: Mapping[str, Mapping[str, FieldGrainRule]] = {
    "ListBillDetail": {
        **{
            field: _list_bill_detail_rule(
                field,
                role=role,
                required_request={"GroupTerm": 0},
                available_request_values={"GroupTerm": (0,)},
                available_when=f"GroupTerm=0（计费项）时保留{label}，可搭配账期、天或明细三个 GroupPeriod。",
                unavailable_meaning=f"GroupTerm=1/2/3 时不返回{label}；需要按实例、产品或账号展示时，应先查计费项维度再本地聚合。",
            )
            for field, role, label in (
                ("Count", "usage", "用量"),
                ("Price", "unit_price", "单价"),
                ("PriceUnit", "unit_price", "单价单位"),
            )
        },
        **{
            field: _list_bill_detail_rule(
                field,
                role="detail_identifier",
                required_request={"GroupPeriod": 2, "GroupTerm": 0},
                available_request_values={"GroupPeriod": (2,), "GroupTerm": (0,)},
                available_when=f"GroupPeriod=2 且 GroupTerm=0（计费项明细）时保留{label}。",
                unavailable_meaning=f"非计费项明细粒度不返回{label}；字段缺失不表示业务数据不存在。",
            )
            for field, label in (("BillID", "账单号"), ("BillDetailId", "账单明细号"))
        },
        "InstanceNo": _list_bill_detail_rule(
            "InstanceNo",
            role="instance_identifier",
            required_request={"GroupTerm": 0},
            available_request_values={"GroupTerm": (0, 1)},
            available_when="GroupTerm=0（计费项）或 1（实例）时保留实例号。",
            unavailable_meaning="GroupTerm=2（产品）或 3（账号）时不返回实例号。",
        ),
    },
    "ListSplitBillDetail": {
        "BillID": _detail_identifier("BillID", "账单/订单 ID"),
        "BillDetailId": _detail_identifier("BillDetailId", "账单明细 ID"),
        "SplitBillDetailId": _detail_identifier("SplitBillDetailId", "分账账单明细 ID"),
        "SplitItemID": _detail_identifier("SplitItemID", "分拆项 ID"),
    },
}


def field_grain_rule(action: str, field: str) -> FieldGrainRule | None:
    canonical = canonical_name(field)
    return next(
        (rule for name, rule in ACTION_FIELD_GRAIN_RULES.get(action, {}).items() if canonical_name(name) == canonical),
        None,
    )


def field_grain_guidance(action: str, field: str) -> dict[str, Any] | None:
    rule = field_grain_rule(action, field)
    return rule.guidance() if rule else None


def action_field_grain_guidance(action: str) -> dict[str, Any] | None:
    rules = ACTION_FIELD_GRAIN_RULES.get(action)
    if not rules:
        return None
    detail_rules = [rule for rule in rules.values() if rule.role == "detail_identifier"]
    detail_request_patch = dict(detail_rules[0].required_request) if detail_rules else {}
    return {
        "kind": "action_response_field_grain_matrix",
        "dimensions": ["Action", "GroupPeriod", "GroupTerm", "response_field"],
        "default_group_period": 0,
        "detail_request_patch": detail_request_patch,
        "detail_identifier_fields": [rule.field for rule in detail_rules],
        "protected_fields": list(rules),
        "rules": [
            {"field": rule.field, **rule.guidance()}
            for rule in rules.values()
        ],
        "planning_rule": (
            "用户明确要求任一 detail_identifier_fields 时，首次请求必须带 GroupPeriod=2。"
            "用户明确要求任一 protected_fields 时，先用对应 available_request_values 检查候选请求；"
            "候选值已合法则保持原值，只有不合法时才应用 required_request 作为修复补丁；"
            "多个字段必须同时满足各自允许值约束。"
            "字段为空或缺失不能解释为没有业务数据。"
        ),
    }


def _request_value(body: Mapping[str, Any], name: str) -> Any:
    if name in body:
        return body[name]
    if name in {"GroupPeriod", "GroupTerm"}:
        return 0
    return None


def _rule_dimensions(rule: FieldGrainRule) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*rule.required_request, *rule.available_request_values)))


def _matches_rule(rule: FieldGrainRule, body: Mapping[str, Any]) -> bool:
    return all(
        _request_value(body, name) in values
        for name, values in rule.available_request_values.items()
    )


def evaluate_field_grain(
    action: str,
    field: str,
    request_bodies: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    rule = field_grain_rule(action, field)
    if rule is None:
        return None
    guidance = rule.guidance()
    if not request_bodies:
        return {**guidance, "status": "unknown", "actual_requests": []}
    dimensions = _rule_dimensions(rule)
    actual = [{name: _request_value(body, name) for name in dimensions} for body in request_bodies]
    matches = [_matches_rule(rule, body) for body in request_bodies]
    status = "available" if all(matches) else "not_preserved" if not any(matches) else "mixed"
    return {**guidance, "status": status, "actual_requests": actual}


def field_grain_warnings(
    action: str,
    fields: Sequence[str],
    request_bodies: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    for field in fields:
        evaluation = evaluate_field_grain(action, field, request_bodies)
        if evaluation is None or evaluation["status"] == "available":
            continue
        if any(row.get(field) not in (None, "") for row in rows):
            continue
        warnings.append(
            f"{action}.{field} 在当前请求粒度下状态为 {evaluation['status']}；"
            f"{evaluation['unavailable_meaning']} 如需该字段，首次查询使用 "
            f"{evaluation['required_request']} 并传 --require-field {field}。"
        )
    return list(dict.fromkeys(warnings))


def resolve_response_fields(
    requested_fields: Sequence[str],
    available_fields: Sequence[str],
) -> tuple[str, ...]:
    canonical_fields: dict[str, list[str]] = {}
    for field in available_fields:
        canonical_fields.setdefault(canonical_name(field), []).append(field)
    resolved: list[str] = []
    for requested in requested_fields:
        if requested in available_fields:
            target = requested
        else:
            candidates = canonical_fields.get(canonical_name(requested), [])
            if not candidates:
                raise BillingQueryError(
                    ErrorCode.UNSUPPORTED_FIELD,
                    f"目标 Action 响应不存在字段：{requested}",
                    ExitCode.INVALID_ARGUMENT,
                    {"field": requested, "available_fields": list(available_fields)},
                )
            if len(candidates) != 1:
                raise BillingQueryError(
                    ErrorCode.INVALID_ARGUMENT,
                    f"响应字段不唯一：{requested}",
                    ExitCode.INVALID_ARGUMENT,
                    {"field": requested, "candidates": candidates},
                )
            target = candidates[0]
        if target not in resolved:
            resolved.append(target)
    return tuple(resolved)


def validate_required_response_fields(
    action: str,
    body: Mapping[str, Any],
    requested_fields: Sequence[str],
    available_fields: Sequence[str],
) -> tuple[str, ...]:
    resolved = resolve_response_fields(requested_fields, available_fields)
    for field in resolved:
        rule = field_grain_rule(action, field)
        if rule is None:
            continue
        actual = {name: _request_value(body, name) for name in _rule_dimensions(rule)}
        if not _matches_rule(rule, body):
            raise BillingQueryError(
                ErrorCode.RESPONSE_FIELD_NOT_PRESERVED,
                f"当前请求粒度不会保留响应字段 {field}",
                ExitCode.INVALID_ARGUMENT,
                {
                    "action": action,
                    "field": field,
                    "required_request": dict(rule.required_request),
                    "actual_request": actual,
                    "instruction": (
                        f"把请求 body 补为 {dict(rule.required_request)} 后再查询；"
                        "汇总粒度下字段为空不表示业务数据不存在。"
                    ),
                },
            )
    return resolved
