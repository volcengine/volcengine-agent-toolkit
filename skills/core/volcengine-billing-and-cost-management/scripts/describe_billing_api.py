#!/usr/bin/env python3
"""按需查询面向 Agent 的 Billing Action 能力与静态契约。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Iterable, List, Sequence

from cost_query.common.version import VERSION
from cost_query.billing.schema import (
    ACTION_SCHEMAS,
    BILLING_API_SCHEMA,
    ApiElementSpec,
    ApiRequestParamSpec,
)
from cost_query.billing.guidance import (
    action_selection_summary,
    field_guidance,
    request_overview,
    response_interpretation,
)
from cost_query.billing.request_field_decisions import request_field_decision
from cost_query.common.json_output import dumps as json_dumps
from cost_query.utils.text import normalize_field_path as _normalize_path


class ContractQueryError(ValueError):
    """表示 Action 或字段查询不在当前契约中。"""


def _type_name(element: ApiElementSpec) -> str:
    return f"{element.type_name}[]" if element.is_array else element.type_name


def _constraints(element: ApiRequestParamSpec) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for value, target in (
        (element.default_value, "default"),
        (element.enum_value, "enum"),
        (element.reg_pattern, "pattern"),
        (element.min_value, "minimum"),
        (element.max_value, "maximum"),
    ):
        if value not in (None, "", []):
            result[target] = value
    for value, target in (
        (element.date_format, "date_format"),
        (element.min_month, "min_month"),
        (element.min_date, "min_date"),
        (element.max_age_months, "max_age_months"),
    ):
        if value not in (None, "", [], 0):
            result[target] = value
    if element.min_length > 0:
        result["min_length"] = element.min_length
    if element.max_length > 0:
        result["max_length"] = element.max_length
    return result


def _field(
    element: ApiElementSpec,
    path: str,
    section: str,
    compact: bool,
    include_raw: bool,
    action_name: str,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": path,
        "type": _type_name(element),
        "agent_guidance": field_guidance(
            element,
            path,
            section,
            action_name=action_name,
        ),
    }
    if include_raw:
        result["raw_description"] = element.description
    if section == "request":
        request_element = element
        if not isinstance(request_element, ApiRequestParamSpec):
            raise TypeError(f"{path} 不是请求字段")
        result["required"] = request_element.is_required
        constraints = _constraints(request_element)
        if constraints:
            result["constraints"] = constraints
    if compact and element.children:
        result["children"] = [child.name for child in element.children]
        result["child_count"] = len(element.children)
    return result


def _flatten_fields(
    elements: Iterable[ApiElementSpec],
    section: str,
    include_raw: bool,
    action_name: str,
    prefix: str = "",
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for element in elements:
        path = f"{prefix}.{element.name}" if prefix else element.name
        result.append(
            _field(
                element,
                path,
                section,
                compact=False,
                include_raw=include_raw,
                action_name=action_name,
            )
        )
        if element.children:
            child_prefix = f"{path}[]" if element.is_array else path
            result.extend(
                _flatten_fields(
                    element.children,
                    section,
                    include_raw,
                    action_name,
                    child_prefix,
                )
            )
    return result


def _compact_fields(
    elements: Iterable[ApiElementSpec],
    section: str,
    include_raw: bool,
    action_name: str,
) -> List[Dict[str, Any]]:
    return [
        _field(
            element,
            element.name,
            section,
            compact=True,
            include_raw=include_raw,
            action_name=action_name,
        )
        for element in elements
    ]


def _filter_fields(
    fields: Sequence[Dict[str, Any]],
    query: str,
) -> List[Dict[str, Any]]:
    normalized = _normalize_path(query)
    return [
        field
        for field in fields
        if _normalize_path(field["path"]) == normalized
        or field["path"].rsplit(".", 1)[-1].casefold() == normalized
    ]


def _filter_fields_with_descendants(
    fields: Sequence[Dict[str, Any]],
    query: str,
) -> List[Dict[str, Any]]:
    matches = _filter_fields(fields, query)
    if not matches:
        return []
    normalized_roots = {
        _normalize_path(field["path"])
        for field in matches
    }
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for field in fields:
        normalized_path = _normalize_path(field["path"])
        if any(
            normalized_path == root or normalized_path.startswith(f"{root}.")
            for root in normalized_roots
        ):
            path = field["path"]
            if path not in seen:
                result.append(field)
                seen.add(path)
    return result


def list_actions() -> Dict[str, Any]:
    return {
        "contract_schema_version": "1.0",
        "tool": "describe_billing_api",
        "tool_version": VERSION,
        "service_code": BILLING_API_SCHEMA.service_code,
        "api_version": BILLING_API_SCHEMA.api_version,
        "usage": (
            "先根据 purpose/data_grain/result_kind/use_when/avoid_when/important_limits 选择 Action；"
            "选定后再调用 "
            "describe，只加载当前任务需要的入参或出参字段。"
        ),
        "actions": [
            action_selection_summary(action)
            for action in ACTION_SCHEMAS.values()
        ],
    }


def describe_action(
    action_name: str,
    section: str = "all",
    field_query: str | Sequence[str] = "",
    expand: bool = False,
    include_raw: bool = False,
    include_overview: bool = False,
    include_interpretation: bool = False,
) -> Dict[str, Any]:
    if action_name not in ACTION_SCHEMAS:
        raise ContractQueryError(
            f"未知 Action: {action_name}; 可用值: {', '.join(ACTION_SCHEMAS)}"
        )
    action = ACTION_SCHEMAS[action_name]
    field_queries = (
        [field_query]
        if isinstance(field_query, str) and field_query
        else [value for value in field_query if value]
        if not isinstance(field_query, str)
        else []
    )
    result: Dict[str, Any] = {
        "contract_schema_version": "1.0",
        "tool": "describe_billing_api",
        "tool_version": VERSION,
        "action": action_name,
        "api_version": BILLING_API_SCHEMA.api_version,
    }
    if not field_queries:
        result["capability"] = action_selection_summary(action)
    if section in ("all", "transport"):
        result["transport"] = {
            "timeout_ms": action.timeout_ms,
            "response_data_path": action.response_data_path,
            "error_code_path": action.error_code_path,
            "error_message_path": action.error_message_path,
        }
    for section_name, elements in (
        ("request", action.request_params),
        ("response", action.response_elements),
    ):
        if section not in ("all", section_name):
            continue
        full_fields = _flatten_fields(
            elements,
            section_name,
            include_raw,
            action_name,
        )
        if field_queries:
            fields = []
            seen_paths: set[str] = set()
            missing_fields: list[str] = []
            for query in field_queries:
                matches = (
                    _filter_fields_with_descendants(full_fields, query)
                    if expand
                    else _filter_fields(full_fields, query)
                )
                if not matches:
                    missing_fields.append(query)
                    continue
                for field in matches:
                    if field["path"] not in seen_paths:
                        seen_paths.add(field["path"])
                        fields.append(field)
            if missing_fields:
                raise ContractQueryError(
                    f"{action_name}.{section_name} 中不存在字段: {', '.join(missing_fields)}"
                )
        elif expand or section_name == "request":
            fields = full_fields
        else:
            fields = _compact_fields(
                elements,
                section_name,
                include_raw,
                action_name,
            )
        result[section_name] = {
            "expanded": bool(expand or field_queries or section_name == "request"),
            "fields": fields,
        }
        if field_queries:
            result[section_name]["requested_fields"] = field_queries
            if section_name == "request":
                decisions = {
                    field["path"]: decision
                    for field in fields
                    if (
                        decision := request_field_decision(
                            action_name,
                            field["path"].rsplit(".", 1)[-1],
                        )
                    )
                }
                if decisions:
                    result[section_name]["field_decisions"] = decisions
        if section_name == "request":
            if include_overview or not field_queries:
                result[section_name]["overview"] = request_overview(
                    action,
                    field_queries,
                )
        if section_name == "response":
            if include_interpretation or not field_queries:
                result[section_name]["interpretation"] = response_interpretation(
                    action
                )
    return result


def find_field(
    field_query: str,
    section: str,
    include_raw: bool = False,
) -> Dict[str, Any]:
    matches: List[Dict[str, Any]] = []
    signatures = set()
    for action in ACTION_SCHEMAS.values():
        elements = (
            action.request_params
            if section == "request"
            else action.response_elements
        )
        fields = _flatten_fields(
            elements,
            section,
            include_raw=True,
            action_name=action.action,
        )
        for field in _filter_fields(fields, field_query):
            signature_field = dict(field)
            match_field = dict(field)
            if not include_raw:
                match_field.pop("raw_description", None)
            match = {"action": action.action, **match_field}
            matches.append(match)
            signature = {
                key: value
                for key, value in signature_field.items()
                if key != "path"
            }
            signatures.add(
                json.dumps(signature, ensure_ascii=False, sort_keys=True)
            )
    if not matches:
        raise ContractQueryError(
            f"所有 Action 的 {section} 中均不存在字段: {field_query}"
        )
    return {
        "contract_schema_version": "1.0",
        "tool": "describe_billing_api",
        "tool_version": VERSION,
        "field": field_query,
        "section": section,
        "matches": matches,
        "uniform_in_current_contracts": len(signatures) == 1,
        "contract_variant_count": len(signatures),
        "shared_definition": field_query == "BillingMode" and section == "request",
        "agent_note": (
            "同名字段在不同 Action 中仍可能存在必填性、格式或语义差异；"
            "组参时使用目标 Action 的匹配项，不把跨接口同名当作永久统一契约。"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "按 Action 或字段渐进加载面向 Agent 的 Billing 能力与 "
            "静态 Billing 契约，输出 JSON。"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser(
        "list",
        help="列出允许的 Action 及选用/避用建议。",
    )
    list_parser.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)

    describe = subparsers.add_parser("describe", help="查询一个 Action 的契约。")
    describe.add_argument("action")
    describe.add_argument(
        "--section",
        choices=("all", "transport", "request", "response"),
        default="all",
    )
    describe.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    describe.add_argument(
        "--field",
        action="append",
        default=[],
        help="按字段加载契约；可重复传入多个 --field。",
    )
    describe.add_argument(
        "--include-raw",
        action="store_true",
        help="同时返回上游原始描述；默认只返回精炼的 Agent guidance。",
    )
    describe.add_argument(
        "--expand",
        action="store_true",
        help="递归展开全部响应字段；入参始终展开。",
    )
    describe.add_argument(
        "--include",
        action="append",
        choices=("overview", "interpretation"),
        default=[],
        help="字段查询时显式附加 Action 级背景；默认字段查询只返回字段级最小契约。",
    )

    find = subparsers.add_parser(
        "find",
        help="跨 Action 查找同名字段并确认是否复用公共定义。",
    )
    find.add_argument("field")
    find.add_argument(
        "--section",
        choices=("request", "response"),
        default="request",
    )
    find.add_argument("--compact", action="store_true", default=True, help=argparse.SUPPRESS)
    find.add_argument(
        "--include-raw",
        action="store_true",
        help="同时返回上游原始描述。",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(arguments)
    try:
        if args.command == "list":
            result = list_actions()
        elif args.command == "describe":
            if args.field and args.section == "transport":
                raise ContractQueryError("transport section 不支持 --field")
            result = describe_action(
                args.action,
                section=args.section,
                field_query=args.field,
                expand=args.expand,
                include_raw=args.include_raw,
                include_overview="overview" in args.include,
                include_interpretation="interpretation" in args.include,
            )
        else:
            result = find_field(
                args.field,
                args.section,
                include_raw=args.include_raw,
            )
    except ContractQueryError as exc:
        print(
            json_dumps(
                {"status": "error", "message": str(exc)},
                compact=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json_dumps(result, compact=args.compact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
