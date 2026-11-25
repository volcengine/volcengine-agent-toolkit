"""Standard JSON Schema views for Billing Action contracts."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .field_grain import field_grain_guidance
from .guidance import request_overview, response_interpretation
from .request_field_decisions import request_field_decision
from .schema import ACTION_SCHEMAS, ApiActionSpec, ApiElementSpec, ApiRequestParamSpec
from ..utils.text import normalize_field_path as _normalize


def _schema_type(element: ApiElementSpec) -> str:
    return {
        "string": "string",
        "int32": "integer",
        "int64": "integer",
        "bool": "boolean",
        "float": "number",
        "double": "number",
        "object": "object",
    }.get(element.type_name, "string")


def _coerce_enum_value(element: ApiElementSpec, value: str) -> Any:
    if element.type_name in {"int32", "int64"}:
        try:
            return int(value)
        except ValueError:
            return value
    if element.type_name in {"float", "double"}:
        try:
            return float(value)
        except ValueError:
            return value
    if element.type_name == "bool":
        lowered = value.casefold()
        if lowered in {"true", "1"}:
            return True
        if lowered in {"false", "0"}:
            return False
    return value


def _enum_values(element: ApiRequestParamSpec) -> list[Any]:
    if not element.enum_value:
        return []
    return [
        _coerce_enum_value(element, item.strip())
        for item in element.enum_value.split(",")
        if item.strip()
    ]


def _element_json_schema(element: ApiElementSpec) -> dict[str, Any]:
    if element.children:
        body: dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                child.name: _element_json_schema(child)
                for child in element.children
            },
        }
        required = [
            child.name for child in element.children
            if isinstance(child, ApiRequestParamSpec) and child.is_required
        ]
        if required:
            body["required"] = required
    else:
        body = {"type": _schema_type(element)}
    if element.description:
        body["description"] = element.description.strip()
    if isinstance(element, ApiRequestParamSpec):
        enum = _enum_values(element)
        if enum:
            body["enum"] = enum
        if element.reg_pattern:
            body["pattern"] = element.reg_pattern
        if element.min_length > 0 and not element.is_array:
            body["minLength"] = element.min_length
        if element.max_length > 0:
            if element.is_array:
                body["maxItems"] = element.max_length
            else:
                body["maxLength"] = element.max_length
        if element.min_value:
            body["minimum"] = _coerce_enum_value(element, element.min_value)
        if element.max_value:
            body["maximum"] = _coerce_enum_value(element, element.max_value)
        if element.default_value not in (None, ""):
            body["default"] = _coerce_enum_value(element, element.default_value)
    if element.is_array:
        item_schema = dict(body)
        item_schema.pop("maxItems", None)
        schema = {"type": "array", "items": item_schema}
        if isinstance(element, ApiRequestParamSpec) and element.min_length > 0:
            schema["minItems"] = element.min_length
        if isinstance(element, ApiRequestParamSpec) and element.max_length > 0:
            schema["maxItems"] = element.max_length
        return schema
    return body


def _leaf(path: str) -> str:
    return path.rsplit(".", 1)[-1].replace("[]", "")


def _matches(element: ApiElementSpec, query: str) -> bool:
    return element.name.casefold() == query.casefold()


def _selected_top_level(
    elements: Iterable[ApiElementSpec],
    field_queries: Sequence[str],
) -> list[ApiElementSpec]:
    if not field_queries:
        return list(elements)
    selected: list[ApiElementSpec] = []
    missing = set(field_queries)
    for element in elements:
        for query in field_queries:
            if _matches(element, query):
                selected.append(element)
                missing.discard(query)
                break
    return selected


def _field_filtered_response_properties(
    elements: Iterable[ApiElementSpec],
    field_queries: Sequence[str],
) -> tuple[dict[str, Any], list[str]]:
    properties: dict[str, Any] = {}
    missing = {_normalize(query): query for query in field_queries}

    def select(element: ApiElementSpec, path: str) -> dict[str, Any] | None:
        matches = [
            query for query in field_queries
            if _normalize(query) == _normalize(path)
            or ("." not in query and _matches(element, query))
        ]
        if matches:
            for query in matches:
                missing.pop(_normalize(query), None)
            for child in element.children:
                select(child, f"{path}.{child.name}")
            return _element_json_schema(element)
        children = {}
        for child in element.children:
            selected = select(child, f"{path}.{child.name}")
            if selected is not None:
                children[child.name] = selected
        if not children:
            return None
        schema = _element_json_schema(element)
        body = schema["items"] if element.is_array else schema
        body["properties"] = children
        return schema

    for element in elements:
        selected = select(element, element.name)
        if selected is not None:
            properties[element.name] = selected
    return properties, list(missing.values())


def _request_json_schema(
    action: ApiActionSpec,
    field_queries: Sequence[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    selected = _selected_top_level(action.request_params, field_queries)
    selected_names = {element.name for element in selected}
    missing = [
        query
        for query in field_queries
        if query.casefold() not in {name.casefold() for name in selected_names}
    ]
    schema: dict[str, Any] = {
        "title": f"{action.action} request",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            element.name: _element_json_schema(element)
            for element in selected
        },
    }
    required = [
        element.name
        for element in selected
        if isinstance(element, ApiRequestParamSpec) and element.is_required
    ]
    if required:
        schema["required"] = required
    return schema, [element.name for element in selected], missing


def _response_json_schema(
    action: ApiActionSpec,
    field_queries: Sequence[str],
) -> tuple[dict[str, Any], list[str]]:
    if field_queries:
        properties, missing = _field_filtered_response_properties(
            action.response_elements,
            field_queries,
        )
    else:
        properties = {
            element.name: _element_json_schema(element)
            for element in action.response_elements
        }
        missing = []
    return {
        "title": f"{action.action} response",
        "type": "object",
        "additionalProperties": True,
        "properties": properties,
    }, missing


def _business_constraints(
    action: ApiActionSpec,
    *,
    include_guidance: bool,
) -> list[str]:
    if not include_guidance:
        return []
    constraints: list[str] = []
    constraints.extend(request_overview(action).get("conditional_rules", []))
    constraints.extend(response_interpretation(action).get("interpretation_rules", []))
    return constraints


def _request_planning_guidance(
    action: ApiActionSpec,
    request_fields: Sequence[str],
    *,
    include_guidance: bool,
) -> dict[str, Any]:
    if not include_guidance:
        return {}
    overview = request_overview(action, request_fields)
    return {
        key: overview[key]
        for key in ("preaggregation_guidance", "field_grain_guidance")
        if key in overview
    }


def _response_field_decisions(
    action_name: str,
    field_queries: Sequence[str],
) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for query in field_queries:
        field = _leaf(query)
        if decision := field_grain_guidance(action_name, field):
            decisions[field] = decision
    return decisions


def schema_contract(
    action_name: str,
    *,
    section: str = "both",
    field_queries: Sequence[str] = (),
    include_guidance: bool = False,
) -> dict[str, Any]:
    if action_name not in ACTION_SCHEMAS:
        raise ValueError(f"未知 Action: {action_name}; 可用值: {', '.join(ACTION_SCHEMAS)}")
    action = ACTION_SCHEMAS[action_name]
    result: dict[str, Any] = {
        "action": action_name,
        "section": section,
    }
    section_missing: dict[str, list[str]] = {}
    request_fields: list[str] = []
    if section in {"both", "request"}:
        request_schema, request_fields, request_missing = _request_json_schema(
            action,
            field_queries,
        )
        if request_fields or not field_queries:
            result["request_json_schema"] = request_schema
        if request_missing:
            section_missing["request"] = request_missing
    if section in {"both", "response"}:
        response_schema, response_missing = _response_json_schema(
            action,
            field_queries,
        )
        response_properties = response_schema.get("properties", {})
        if response_properties or not field_queries:
            result["response_json_schema"] = response_schema
        if response_missing:
            section_missing["response"] = response_missing
    if field_queries and "request_json_schema" not in result and "response_json_schema" not in result:
        missing = []
        for values in section_missing.values():
            missing.extend(values)
        raise ValueError(f"{action_name}.{section} 中不存在字段: {', '.join(dict.fromkeys(missing))}")
    if section == "request" and section_missing.get("request"):
        raise ValueError(f"{action_name}.request 中不存在字段: {', '.join(section_missing['request'])}")
    if section == "response" and section_missing.get("response"):
        raise ValueError(f"{action_name}.response 中不存在字段: {', '.join(section_missing['response'])}")
    decisions = {
        field: decision
        for field in request_fields
        if (decision := request_field_decision(action_name, field))
    }
    if decisions:
        result["agent_decisions"] = decisions
    planning_guidance = (
        _request_planning_guidance(
            action,
            request_fields,
            include_guidance=include_guidance,
        )
        if section in {"both", "request"}
        else {}
    )
    result.update(planning_guidance)
    if section in {"both", "response"} and field_queries:
        response_decisions = _response_field_decisions(action_name, field_queries)
        if response_decisions:
            result["response_field_decisions"] = response_decisions
    constraints = _business_constraints(action, include_guidance=include_guidance)
    if constraints:
        result["business_constraints"] = constraints
    return result
