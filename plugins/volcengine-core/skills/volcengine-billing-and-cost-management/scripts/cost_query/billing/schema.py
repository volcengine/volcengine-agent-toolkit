"""加载 Billing Action 契约；源码态用模型，发布态用静态 JSON。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple
STATIC_CONTRACT_PATH = Path(__file__).with_name("contracts.json")


@dataclass(frozen=True)
class ApiElementSpec:
    python_name: str
    name: str
    object_type_name: str
    validation_kind: str
    type_code: int
    type_name: str
    description: str
    is_public: bool
    is_array: bool
    children: Tuple["ApiElementSpec", ...] = ()

    @property
    def children_by_name(self) -> Mapping[str, "ApiElementSpec"]:
        return {child.name: child for child in self.children}


@dataclass(frozen=True)
class ApiRequestParamSpec(ApiElementSpec):
    location_multi: Tuple[int, ...] = ()
    is_required: bool = False
    default_value: str = ""
    split_type: int = 0
    is_enum: bool = False
    enum_value: str = ""
    reg_pattern: str = ""
    max_length: int = 0
    min_length: int = 0
    max_value: str = ""
    min_value: str = ""
    date_format: str = ""
    min_month: str = ""
    min_date: str = ""
    max_age_months: int = 0


@dataclass(frozen=True)
class ApiActionSpec:
    action: str
    name_zh: str
    description: str
    timeout_ms: int
    response_data_path: str
    error_code_path: str
    error_message_path: str
    request_params: Tuple[ApiRequestParamSpec, ...]
    response_elements: Tuple[ApiElementSpec, ...]

    @property
    def request_params_by_name(self) -> Mapping[str, ApiRequestParamSpec]:
        return {parameter.name: parameter for parameter in self.request_params}

    @property
    def response_elements_by_name(self) -> Mapping[str, ApiElementSpec]:
        return {element.name: element for element in self.response_elements}

    @property
    def row_fields(self) -> Mapping[str, ApiElementSpec]:
        list_element = self.response_elements_by_name.get("List")
        return list_element.children_by_name if list_element else {}


@dataclass(frozen=True)
class BillingApiSchema:
    service_code: str
    api_version: str
    source_file: str
    source_sha256: str
    actions: Mapping[str, ApiActionSpec]


def _element_from_payload(payload: Mapping[str, Any]) -> ApiElementSpec:
    return ApiElementSpec(
        python_name=str(payload["python_name"]),
        name=str(payload["name"]),
        object_type_name=str(payload.get("object_type_name") or ""),
        validation_kind=str(payload.get("validation_kind") or "strict"),
        type_code=int(payload["type_code"]),
        type_name=str(payload["type_name"]),
        description=str(payload.get("description") or ""),
        is_public=bool(payload["is_public"]),
        is_array=bool(payload["is_array"]),
        children=tuple(_element_from_payload(child) for child in payload.get("children", ())),
    )


def _request_parameter_from_payload(payload: Mapping[str, Any]) -> ApiRequestParamSpec:
    return ApiRequestParamSpec(
        python_name=str(payload["python_name"]),
        name=str(payload["name"]),
        object_type_name=str(payload.get("object_type_name") or ""),
        validation_kind=str(payload.get("validation_kind") or "strict"),
        type_code=int(payload["type_code"]),
        type_name=str(payload["type_name"]),
        description=str(payload.get("description") or ""),
        is_public=bool(payload["is_public"]),
        is_array=bool(payload["is_array"]),
        children=tuple(_request_parameter_from_payload(child) for child in payload.get("children", ())),
        location_multi=tuple(payload.get("location_multi") or ()),
        is_required=bool(payload.get("is_required")),
        default_value=str(payload.get("default_value") or ""),
        split_type=int(payload.get("split_type") or 0),
        is_enum=bool(payload.get("is_enum")),
        enum_value=str(payload.get("enum_value") or ""),
        reg_pattern=str(payload.get("reg_pattern") or ""),
        max_length=int(payload.get("max_length") or 0),
        min_length=int(payload.get("min_length") or 0),
        max_value=str(payload.get("max_value") or ""),
        min_value=str(payload.get("min_value") or ""),
        date_format=str(payload.get("date_format") or ""),
        min_month=str(payload.get("min_month") or ""),
        min_date=str(payload.get("min_date") or ""),
        max_age_months=int(payload.get("max_age_months") or 0),
    )


def _schema_from_payload(payload: Mapping[str, Any]) -> BillingApiSchema:
    actions: Dict[str, ApiActionSpec] = {}
    for action_name, contract in payload["actions"].items():
        actions[action_name] = ApiActionSpec(
            action=str(contract["action"]),
            name_zh=str(contract["name_zh"]),
            description=str(contract["description"]),
            timeout_ms=int(contract["timeout_ms"]),
            response_data_path=str(contract["response_data_path"]),
            error_code_path=str(contract["error_code_path"]),
            error_message_path=str(contract["error_message_path"]),
            request_params=tuple(_request_parameter_from_payload(field) for field in contract["request_params"]),
            response_elements=tuple(_element_from_payload(field) for field in contract["response_elements"]),
        )
    return BillingApiSchema(
        service_code=str(payload["service_code"]),
        api_version=str(payload["api_version"]),
        source_file=str(payload["source_file"]),
        source_sha256=str(payload["source_sha256"]),
        actions=actions,
    )


def _schema_from_models() -> BillingApiSchema:
    from .contracts import build_static_contract_payload

    return _schema_from_payload(build_static_contract_payload())


@lru_cache(maxsize=1)
def load_billing_api_schema() -> BillingApiSchema:
    if STATIC_CONTRACT_PATH.is_file():
        return _schema_from_payload(json.loads(STATIC_CONTRACT_PATH.read_text(encoding="utf-8")))
    return _schema_from_models()


BILLING_API_SCHEMA = load_billing_api_schema()
ACTION_SCHEMAS = BILLING_API_SCHEMA.actions
