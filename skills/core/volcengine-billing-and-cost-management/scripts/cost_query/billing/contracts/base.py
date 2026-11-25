"""Billing Pydantic 契约的公共基础设施。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo


class BillingContractModel(BaseModel):
    """严格按 API alias 接收和输出字段的基础模型。"""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_by_alias=True,
        validate_by_name=True,
        use_enum_values=True,
    )


@dataclass(frozen=True)
class ActionContract:
    action: str
    name_zh: str
    description: str
    timeout_ms: int
    response_data_path: str
    error_code_path: str
    error_message_path: str
    request_model: Type[BillingContractModel]
    response_model: Type[BillingContractModel]


@dataclass(frozen=True)
class BillingContractRegistry:
    service_code: str
    api_version: str
    source_file: str
    source_sha256: str
    actions: Mapping[str, ActionContract]


def _billing_metadata(
    *,
    type_code: int,
    is_public: bool,
    is_array: bool,
    location_multi: Tuple[int, ...] = (),
    default_value: str = "",
    split_type: int = 0,
    is_enum: bool = False,
    enum_value: str = "",
    reg_pattern: str = "",
    max_length: int = 0,
    min_length: int = 0,
    max_value: str = "",
    min_value: str = "",
    date_format: str = "",
    min_month: str = "",
    min_date: str = "",
    max_age_months: int = 0,
) -> Mapping[str, Any]:
    return {
        "billing": {
            "type_code": type_code,
            "is_public": is_public,
            "is_array": is_array,
            "location_multi": list(location_multi),
            "default_value": default_value,
            "split_type": split_type,
            "is_enum": is_enum,
            "enum_value": enum_value,
            "reg_pattern": reg_pattern,
            "max_length": max_length,
            "min_length": min_length,
            "max_value": max_value,
            "min_value": min_value,
            "date_format": date_format,
            "min_month": min_month,
            "min_date": min_date,
            "max_age_months": max_age_months,
        }
    }


def request_field(
    *,
    alias: str,
    description: str,
    type_code: int,
    is_public: bool,
    is_array: bool,
    required: bool,
    location_multi: Tuple[int, ...] = (),
    default_value: str = "",
    split_type: int = 0,
    is_enum: bool = False,
    enum_value: str = "",
    reg_pattern: str = "",
    max_length: int = 0,
    min_length: int = 0,
    max_value: str = "",
    min_value: str = "",
    ge: Any = None,
    le: Any = None,
    date_format: str = "",
    min_month: str = "",
    min_date: str = "",
    max_age_months: int = 0,
) -> FieldInfo:
    month_fields = {"BillPeriod", "AmortizedMonth"}
    day_fields = {"AmortizedDay", "ExpenseDate", "BeginTimeStr", "EndTimeStr"}
    if not date_format and alias in month_fields:
        date_format = "YYYY-MM"
    elif not date_format and alias in day_fields:
        date_format = "YYYY-MM-DD"
    if not min_month and (alias == "AmortizedMonth" or (alias == "BillPeriod" and "2023-04" in description)):
        min_month = "2023-04"
    if not min_date and alias == "AmortizedDay":
        min_date = "2023-04-01"
    if not max_age_months and alias in (month_fields | day_fields):
        max_age_months = 24

    kwargs = {
        "alias": alias,
        "description": description,
        "json_schema_extra": _billing_metadata(
            type_code=type_code,
            is_public=is_public,
            is_array=is_array,
            location_multi=location_multi,
            default_value=default_value,
            split_type=split_type,
            is_enum=is_enum,
            enum_value=enum_value,
            reg_pattern=reg_pattern,
            max_length=max_length,
            min_length=min_length,
            max_value=max_value,
            min_value=min_value,
            date_format=date_format,
            min_month=min_month,
            min_date=min_date,
            max_age_months=max_age_months,
        ),
    }
    if reg_pattern:
        kwargs["pattern"] = reg_pattern
    if min_length:
        kwargs["min_length"] = min_length
    if max_length:
        kwargs["max_length"] = max_length
    if ge is not None:
        kwargs["ge"] = ge
    if le is not None:
        kwargs["le"] = le
    return Field(... if required else None, **kwargs)


def response_field(
    *,
    alias: str,
    description: str,
    type_code: int,
    is_public: bool,
    is_array: bool,
) -> FieldInfo:
    return Field(
        None,
        alias=alias,
        description=description,
        json_schema_extra=_billing_metadata(
            type_code=type_code,
            is_public=is_public,
            is_array=is_array,
        ),
    )
