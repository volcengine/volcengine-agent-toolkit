"""开发态 Billing Pydantic 契约及发布静态契约转换。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Mapping, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .registry import UPSTREAM_ACTION_CONTRACTS, UPSTREAM_BILLING_API_CONTRACT
from ..exposure import is_public_response_field


TYPE_NAMES = {1: "string", 2: "int32", 3: "int64", 4: "bool", 5: "float", 6: "double", 7: "object"}


def _metadata(field: FieldInfo) -> Mapping[str, Any]:
    extra = field.json_schema_extra
    if not isinstance(extra, Mapping) or not isinstance(extra.get("billing"), Mapping):
        raise TypeError(f"字段 {field.alias} 缺少 billing metadata")
    return extra["billing"]


def _nested_model(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for argument in get_args(annotation):
        nested = _nested_model(argument)
        if nested is not None:
            return nested
    return None


def _validation_kind(annotation: Any) -> str:
    if get_origin(annotation) is Literal:
        return "literal"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "enum"
    for argument in get_args(annotation):
        kind = _validation_kind(argument)
        if kind != "strict":
            return kind
    return "strict"


def _field_payload(python_name: str, field: FieldInfo, *, request: bool, action: str) -> dict[str, Any]:
    metadata = _metadata(field)
    type_code = int(metadata["type_code"])
    nested = _nested_model(field.annotation) if type_code == 7 else None
    children = [
        _field_payload(name, child, request=request, action=action)
        for name, child in (nested.model_fields.items() if nested else ())
    ]
    if not request:
        children = [child for child in children if is_public_response_field(action, child["name"])]
    payload = {
        "python_name": python_name,
        "name": str(field.alias),
        "object_type_name": nested.__name__ if nested else "",
        "validation_kind": _validation_kind(field.annotation),
        "type_code": type_code,
        "type_name": TYPE_NAMES.get(type_code, f"unknown:{type_code}"),
        "description": field.description or "",
        "is_public": bool(metadata["is_public"]),
        "is_array": bool(metadata["is_array"]),
        "children": children,
    }
    if request:
        payload.update(
            location_multi=list(metadata.get("location_multi") or ()),
            is_required=field.is_required(),
            default_value=str(metadata.get("default_value") or ""),
            split_type=int(metadata.get("split_type") or 0),
            is_enum=bool(metadata.get("is_enum")),
            enum_value=str(metadata.get("enum_value") or ""),
            reg_pattern=str(metadata.get("reg_pattern") or ""),
            max_length=int(metadata.get("max_length") or 0),
            min_length=int(metadata.get("min_length") or 0),
            max_value=str(metadata.get("max_value") or ""),
            min_value=str(metadata.get("min_value") or ""),
            date_format=str(metadata.get("date_format") or ""),
            min_month=str(metadata.get("min_month") or ""),
            min_date=str(metadata.get("min_date") or ""),
            max_age_months=int(metadata.get("max_age_months") or 0),
        )
    return payload


def build_static_contract_payload() -> dict[str, Any]:
    actions = {}
    for action_name, contract in UPSTREAM_ACTION_CONTRACTS.items():
        response_elements = []
        for name, field in contract.response_model.model_fields.items():
            payload = _field_payload(name, field, request=False, action=action_name)
            if is_public_response_field(action_name, payload["name"]):
                response_elements.append(payload)
        actions[action_name] = {
            "action": contract.action,
            "name_zh": contract.name_zh,
            "description": contract.description,
            "timeout_ms": contract.timeout_ms,
            "response_data_path": contract.response_data_path,
            "error_code_path": contract.error_code_path,
            "error_message_path": contract.error_message_path,
            "request_params": [
                _field_payload(name, field, request=True, action=action_name)
                for name, field in contract.request_model.model_fields.items()
            ],
            "response_elements": response_elements,
        }
    return {
        "service_code": UPSTREAM_BILLING_API_CONTRACT.service_code,
        "api_version": UPSTREAM_BILLING_API_CONTRACT.api_version,
        "source_file": UPSTREAM_BILLING_API_CONTRACT.source_file,
        "source_sha256": UPSTREAM_BILLING_API_CONTRACT.source_sha256,
        "actions": actions,
    }

__all__ = [
    "build_static_contract_payload",
]
