"""在调用 ve billing 前校验目标 Action 的最终请求体。"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from .schema import ACTION_SCHEMAS, ApiRequestParamSpec
from .cost_change import COST_CHANGE_ACTIONS
from .preaggregation import LIST_BILL_DETAIL_RESPONSE_FIELD_HINTS
from ..common.errors import BillingQueryError, ErrorCode, ExitCode
from ..utils.errors import invalid_argument as _invalid
from ..utils.billing import TOKEN_PAGE_SIZE_LIMITS


ALLOWED_ACTIONS = frozenset(ACTION_SCHEMAS)
_BILL_CATEGORY_PARENT = {"consume", "refund", "transfer"}
_BILL_CATEGORY = {
    "consume-trial",
    "consume-use",
    "consume-new",
    "consume-renew",
    "consume-formalize",
    "consume-modify",
    "consume-TempUpgrade",
    "consume-RIAdjust",
    "refund-terminate",
    "refund-modify",
    "refund-TempUpgrade",
    "refund-RIAdjust",
    "transfer-manual",
    "transfer-system",
    "consumption-guarantee",
    "refund-DeliveryFailed",
    "transfer-guarantee",
    "consume-Commitment",
    "consume-transfer",
    "refund-transfer",
}
_PAY_STATUS = {"CompletedSettle", "PartSettle", "Unsettle"}
_AMORTIZED_TYPE = {str(value) for value in range(1, 11)}
_COST_TYPE = {0, 1, 2, 4, 5, 6}
_TIME_GRANULARITY = {0, 1}
_CLASSIFY_DIMENSION = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17}
_FILTER_KEY = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17}
_LIST_BILL_DETAIL_UNSUPPORTED_DETAIL_GROUP_TERMS = {2: "产品", 3: "账号"}
_COUPON_STATUSES = {"1", "2", "3", "4", "5"}
_MISSING = object()


def _path_parts(path: str) -> list[str]:
    return [
        part
        for part in re.sub(r"\[([^\]]+)\]", r".\1", path).split(".")
        if part
    ]


def _parameter_spec(action: str, path: str) -> ApiRequestParamSpec | None:
    parts = _path_parts(path)
    fields = ACTION_SCHEMAS[action].request_params
    current: ApiRequestParamSpec | None = None
    for part in parts:
        if part.isdigit():
            continue
        current = next(
            (field for field in fields if part in {field.name, field.python_name}),
            None,
        )
        if current is None:
            return None
        fields = tuple(
            child
            for child in current.children
            if isinstance(child, ApiRequestParamSpec)
        )
    return current


def _json_type(field: ApiRequestParamSpec) -> str:
    return {
        "string": "string",
        "int32": "integer",
        "int64": "integer",
        "bool": "boolean",
        "float": "number",
        "double": "number",
        "object": "object",
    }.get(field.type_name, field.type_name)


def _parameter_contract(field: ApiRequestParamSpec) -> dict[str, Any]:
    scalar: dict[str, Any] = {"type": _json_type(field)}
    enum = _enum_values(field)
    if enum:
        scalar["enum"] = list(enum)
    if field.min_value:
        scalar["minimum"] = int(field.min_value)
    if field.max_value:
        scalar["maximum"] = int(field.max_value)
    if field.min_length and not field.is_array:
        scalar["min_length"] = field.min_length
    if field.max_length and not field.is_array:
        scalar["max_length"] = field.max_length
    if field.reg_pattern:
        scalar["pattern"] = field.reg_pattern
    if field.date_format:
        scalar["format"] = field.date_format
    if field.min_month:
        scalar["min_month"] = field.min_month
    if field.min_date:
        scalar["min_date"] = field.min_date
    if field.max_age_months:
        scalar["max_age_months"] = field.max_age_months
    if field.children:
        scalar["properties"] = {
            child.name: _parameter_contract(child)
            for child in field.children
            if isinstance(child, ApiRequestParamSpec)
        }
    contract: dict[str, Any]
    if field.is_array:
        contract = {"type": "array", "items": scalar}
        if field.max_length:
            contract["max_items"] = field.max_length
        if field.min_length:
            contract["min_items"] = field.min_length
    else:
        contract = scalar
    contract["required"] = field.is_required
    description = field.description.strip()
    if description:
        contract["description"] = description
    return contract


def _path_value(
    action: str,
    body: Mapping[str, Any],
    path: str,
) -> Any:
    current: Any = body
    fields = ACTION_SCHEMAS[action].request_params
    for part in _path_parts(path):
        if part.isdigit():
            if not isinstance(current, list) or int(part) >= len(current):
                return _MISSING
            current = current[int(part)]
            continue
        if not isinstance(current, Mapping):
            return _MISSING
        field = next(
            (candidate for candidate in fields if part in {candidate.name, candidate.python_name}),
            None,
        )
        names = (part,) if field is None else (field.name, field.python_name)
        supplied = next((name for name in names if name in current), None)
        if supplied is None:
            return _MISSING
        current = current[supplied]
        fields = () if field is None else field.children
    return current


def _invalid_parameter(
    action: str,
    body: Mapping[str, Any],
    *,
    path: str,
    violation: str,
    message: str | None = None,
) -> dict[str, Any]:
    field = _parameter_spec(action, path)
    item: dict[str, Any] = {
        "path": path,
        "violation": violation,
        "contract": _parameter_contract(field) if field else {"accepted": False},
    }
    actual = _path_value(action, body, path)
    # Unknown parameters have no action-local schema and may contain credentials.
    # Report that they are not accepted without echoing their supplied value.
    if field is not None and actual is not _MISSING:
        item["actual"] = actual
    if message:
        item["message"] = message
    return item


def _invalid_parameters_from_validation_errors(
    action: str,
    body: Mapping[str, Any],
    errors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        _invalid_parameter(
            action,
            body,
            path=str(error["path"]),
            violation=str(error["type"]),
            message=str(error.get("message") or "") or None,
        )
        for error in errors
    ]


def _attach_invalid_parameter_contracts(
    action: str,
    body: Mapping[str, Any],
    error: BillingQueryError,
) -> BillingQueryError:
    if error.code is not ErrorCode.INVALID_ARGUMENT or "invalid_parameters" in error.details:
        return error
    raw_fields = error.details.get("fields")
    if isinstance(raw_fields, Sequence) and not isinstance(raw_fields, (str, bytes)):
        paths = [str(field) for field in raw_fields]
    elif error.details.get("field") is not None:
        paths = [str(error.details["field"])]
    else:
        paths = []
    if paths:
        error.details["invalid_parameters"] = [
            _invalid_parameter(
                action,
                body,
                path=path,
                violation="constraint_violation",
                message=str(error),
            )
            for path in dict.fromkeys(paths)
        ]
    return error


def normalize_wrapper_request_body(action: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize convenient JSON input without changing the Billing API contract."""

    normalized = dict(body)
    if action not in TOKEN_PAGE_SIZE_LIMITS:
        return normalized
    field = "MaxResults" if "MaxResults" in normalized else "max_results" if "max_results" in normalized else None
    if field is not None:
        value = normalized[field]
        if isinstance(value, int) and not isinstance(value, bool):
            normalized[field] = str(value)
    return normalized


def _parse_month(value: Any, field: str) -> tuple[int, int]:
    if not isinstance(value, str):
        raise _invalid(f"{field} 必须是 YYYY-MM 字符串", field=field, value=value)
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise _invalid(f"{field} 必须是合法月份 YYYY-MM", field=field, value=value) from exc
    return parsed.year, parsed.month


def _parse_day(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise _invalid(f"{field} 必须是 YYYY-MM-DD 字符串", field=field, value=value)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise _invalid(f"{field} 必须是合法日期 YYYY-MM-DD", field=field, value=value) from exc


def _earliest_allowed_month(today: date | None = None) -> tuple[int, int]:
    current = today or date.today()
    total_months = current.year * 12 + current.month - 24
    return (total_months - 1) // 12, (total_months - 1) % 12 + 1


def _month_constraint_floor(field: ApiRequestParamSpec) -> tuple[int, int] | None:
    candidates: list[tuple[int, int]] = []
    if field.min_month:
        candidates.append(_parse_month(field.min_month, field.name))
    if field.max_age_months:
        candidates.append(_earliest_allowed_month())
    if not candidates:
        return None
    return max(candidates)


def _validate_month_constraints(field: ApiRequestParamSpec, value: Any) -> tuple[int, int]:
    month = _parse_month(value, field.name)
    floor = _month_constraint_floor(field)
    if floor and month < floor:
        raise _invalid(
            f"{field.name} 超出支持的时间范围",
            field=field.name,
            value=value,
            min_month=f"{floor[0]:04d}-{floor[1]:02d}",
            max_age_months=field.max_age_months or None,
        )
    return month


def _validate_day_constraints(field: ApiRequestParamSpec, value: Any) -> date:
    day = _parse_day(value, field.name)
    if field.max_age_months:
        floor = _earliest_allowed_month()
        if (day.year, day.month) < floor:
            raise _invalid(
                f"{field.name} 超出支持的时间范围",
                field=field.name,
                value=value,
                min_month=f"{floor[0]:04d}-{floor[1]:02d}",
                max_age_months=field.max_age_months,
            )
    if field.min_date:
        min_day = _parse_day(field.min_date, field.name)
        if day < min_day:
            raise _invalid(
                f"{field.name} 超出支持的时间范围",
                field=field.name,
                value=value,
                min_date=field.min_date,
            )
    return day


def _validate_structured_time_constraints(action: str, body: Mapping[str, Any]) -> dict[str, tuple[int, int] | date]:
    parsed: dict[str, tuple[int, int] | date] = {}
    fields = ACTION_SCHEMAS[action].request_params_by_name
    for name, field in fields.items():
        if name not in body or body[name] is None:
            continue
        if field.date_format == "YYYY-MM":
            parsed[name] = _validate_month_constraints(field, body[name])
        elif field.date_format == "YYYY-MM-DD":
            parsed[name] = _validate_day_constraints(field, body[name])
    return parsed


def _validate_array_domain(body: Mapping[str, Any], field: str, allowed: set[str]) -> None:
    if field not in body or body[field] is None:
        return
    values = body[field]
    invalid = [value for value in values if str(value) not in allowed]
    if invalid:
        raise _invalid(
            f"{field} 包含不支持的值",
            field=field,
            invalid=invalid,
            allowed=sorted(allowed),
        )


def _validate_string_domain(body: Mapping[str, Any], field: str, allowed: set[str]) -> None:
    if field not in body or body[field] is None:
        return
    value = body[field]
    if str(value) not in allowed:
        raise _invalid(
            f"{field} 包含不支持的值",
            field=field,
            invalid=[value],
            allowed=sorted(allowed),
        )


def _is_blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def _validate_tag_kv(body: Mapping[str, Any]) -> None:
    tag_kv = body.get("TagKV")
    if tag_kv is None:
        return
    if not tag_kv:
        raise _invalid("TagKV 不能为空；不筛选标签时不要传 TagKV", field="TagKV")
    for index, item in enumerate(tag_kv):
        key = item.get("Key")
        value = item.get("Value")
        if _is_blank(key) or _is_blank(value):
            raise _invalid(
                "TagKV 每一项必须同时提供非空 Key 和 Value；只知道标签键时先用 GetFilterInfoForCostAnalysis 确认标签键是否真实存在，不直接构造 TagKV 筛选",
                field=f"TagKV[{index}]",
                key_provided=not _is_blank(key),
                value_provided=not _is_blank(value),
            )


def _validate_common(action: str, body: Mapping[str, Any]) -> None:
    parsed_times = _validate_structured_time_constraints(action, body)
    if "AmortizedDay" in parsed_times:
        day = parsed_times["AmortizedDay"]
        if not isinstance(day, date):
            raise TypeError("AmortizedDay parser returned non-date")
        if body.get("AmortizedMonth") and day.strftime("%Y-%m") != body["AmortizedMonth"]:
            raise _invalid("AmortizedDay 必须属于 AmortizedMonth", field="AmortizedDay")
    if "ExpenseDate" in parsed_times:
        day = parsed_times["ExpenseDate"]
        if not isinstance(day, date):
            raise TypeError("ExpenseDate parser returned non-date")
        if body.get("GroupPeriod") not in (1, 2):
            raise _invalid("ExpenseDate 仅在 GroupPeriod=1 或 2 时支持", field="ExpenseDate")
        if body.get("BillPeriod") and day.strftime("%Y-%m") != body["BillPeriod"]:
            raise _invalid("ExpenseDate 必须与 BillPeriod 属于同一个月", field="ExpenseDate")
    for field in ("IgnoreZero", "TagKVFilterMode"):
        if field in body and body[field] is not None and body[field] not in (0, 1):
            raise _invalid(f"{field} 只能是 0 或 1", field=field, value=body[field])
    _validate_array_domain(body, "BillCategoryParent", _BILL_CATEGORY_PARENT)
    _validate_array_domain(body, "BillCategory", _BILL_CATEGORY)
    _validate_string_domain(body, "PayStatus", _PAY_STATUS)
    _validate_array_domain(body, "AmortizedType", _AMORTIZED_TYPE)
    if body.get("TagKVFilterMode") is not None and not body.get("TagKV"):
        raise _invalid("TagKVFilterMode 必须与非空 TagKV 一起使用", field="TagKVFilterMode")
    _validate_tag_kv(body)
    if (
        action == "ListBillDetail"
        and body.get("GroupPeriod") == 2
        and body.get("GroupTerm") in _LIST_BILL_DETAIL_UNSUPPORTED_DETAIL_GROUP_TERMS
    ):
        group_term = body["GroupTerm"]
        raise _invalid(
            f"ListBillDetail 不支持{_LIST_BILL_DETAIL_UNSUPPORTED_DETAIL_GROUP_TERMS[group_term]}+明细粒度；"
            "GroupPeriod=2 时 GroupTerm 只能不传或使用 0（计费项）/1（实例）",
            field="GroupTerm",
            GroupPeriod=body.get("GroupPeriod"),
            GroupTerm=group_term,
        )
    if action == "ListBillDetail" and body.get("Project"):
        if body.get("GroupPeriod", 2) != 2 or body.get("GroupTerm") not in (None, 0):
            raise _invalid("ListBillDetail.Project 只在计费项明细粒度生效", field="Project")
    if action == "ListSplitBillDetail" and body.get("Project") and body.get("GroupPeriod", 2) != 2:
        raise _invalid("ListSplitBillDetail.Project 只在明细粒度生效", field="Project")
    if body.get("SplitDimension"):
        try:
            value = json.loads(body["SplitDimension"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise _invalid("SplitDimension 必须是 JSON object 编码后的字符串", field="SplitDimension") from exc
        if not isinstance(value, dict):
            raise _invalid("SplitDimension 必须编码一个 JSON object", field="SplitDimension")
    if action in TOKEN_PAGE_SIZE_LIMITS:
        max_results = body.get("MaxResults")
        if not isinstance(max_results, str) or not max_results.isdigit():
            raise _invalid("MaxResults 必须是整数字符串", field="MaxResults", value=max_results)
        if not 1 <= int(max_results) <= TOKEN_PAGE_SIZE_LIMITS[action]:
            raise _invalid(
                f"{action}.MaxResults 必须在 1 到 {TOKEN_PAGE_SIZE_LIMITS[action]} 之间",
                field="MaxResults",
                value=max_results,
            )
    if action == "ListResourcePackages":
        begin = _parse_utc_time(body.get("EffectiveTimeBegin"), "EffectiveTimeBegin")
        end = _parse_utc_time(body.get("EffectiveTimeEnd"), "EffectiveTimeEnd")
        if begin and end and begin > end:
            raise _invalid(
                "EffectiveTimeBegin 不能晚于 EffectiveTimeEnd",
                fields=["EffectiveTimeBegin", "EffectiveTimeEnd"],
            )
    if action == "ListPackageUsageDetails":
        begin = _parse_utc_time(body.get("DeductBeginTime"), "DeductBeginTime")
        end = _parse_utc_time(body.get("DeductEndTime"), "DeductEndTime")
        if begin is not None and end is not None and begin >= end:
            raise _invalid(
                "DeductBeginTime 必须早于 DeductEndTime；区间为左闭右开",
                fields=["DeductBeginTime", "DeductEndTime"],
            )
    if action == "ListCoupons":
        begin = _parse_iso_time(body.get("ValidBeginTime"), "ValidBeginTime")
        end = _parse_iso_time(body.get("ValidEndTime"), "ValidEndTime")
        if begin and end and begin > end:
            raise _invalid(
                "ValidBeginTime 不能晚于 ValidEndTime",
                fields=["ValidBeginTime", "ValidEndTime"],
            )
        status = body.get("Status")
        if status is not None:
            values = [item.strip() for item in str(status).split(",") if item.strip()]
            invalid = [item for item in values if item not in _COUPON_STATUSES]
            if not values or invalid:
                raise _invalid(
                    "ListCoupons.Status 只能包含 1、2、3、4、5，多个值用英文逗号分隔",
                    field="Status",
                    invalid=invalid,
                )
    if action == "ListCouponUsageRecords":
        limit = body.get("Limit")
        if limit is not None and not 1 <= limit <= 1000:
            raise _invalid(
                "ListCouponUsageRecords.Limit 必须在 1 到 1000 之间",
                field="Limit",
                value=limit,
            )


def _parse_utc_time(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid(f"{field} 必须是 ISO8601 UTC 字符串", field=field, value=value)
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise _invalid(f"{field} 必须是合法的 ISO8601 UTC 时间 yyyy-MM-ddTHH:mm:ssZ", field=field, value=value) from exc


def _parse_iso_time(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid(f"{field} 必须是 ISO8601 字符串", field=field, value=value)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _invalid(f"{field} 必须是合法的 ISO8601 时间", field=field, value=value) from exc


def _validate_list_cost_analysis_request(body: Mapping[str, Any]) -> None:
    if body["CostType"] not in _COST_TYPE:
        raise _invalid(
            "CostType 仅支持 0、1、2、4、5、6；费用分析不再提供现金支付口径 3、7",
            field="CostType",
            supported_values=sorted(_COST_TYPE),
        )
    if body["TimeGranularity"] not in _TIME_GRANULARITY:
        raise _invalid("TimeGranularity 只能是 0 或 1", field="TimeGranularity")
    if body["ClassifyDimension"] not in _CLASSIFY_DIMENSION:
        raise _invalid("ClassifyDimension 不在支持范围", field="ClassifyDimension")
    begin = _parse_day(body["BeginTimeStr"], "BeginTimeStr")
    end = _parse_day(body["EndTimeStr"], "EndTimeStr")
    if begin > end:
        raise _invalid(
            "BeginTimeStr 不能晚于 EndTimeStr",
            fields=["BeginTimeStr", "EndTimeStr"],
        )
    if body["TimeGranularity"] == 0 and (begin.day != 1 or end.day != 1):
        raise _invalid(
            "按月查询时 BeginTimeStr/EndTimeStr 必须为 YYYY-MM-01",
            fields=["BeginTimeStr", "EndTimeStr"],
        )
    if not 1 <= body["Limit"] <= 300:
        raise _invalid("ListCostAnalysisOpenApi.Limit 必须在 1 到 300 之间", field="Limit")
    if body["Offset"] < 0:
        raise _invalid("Offset 不能小于 0", field="Offset")
    if body["ClassifyDimension"] in (10, 11, 15) and not body.get("ClassifyDimensionValue"):
        raise _invalid("该 ClassifyDimension 必须提供 ClassifyDimensionValue", field="ClassifyDimensionValue")
    for index, item in enumerate(body.get("Filters") or []):
        if item["Operator"] not in (1, 2):
            raise _invalid("Filters.Operator 只能是 1 或 2", field=f"Filters[{index}].Operator")
        if item["FilterKey"] not in _FILTER_KEY:
            raise _invalid("Filters.FilterKey 不在支持范围", field=f"Filters[{index}].FilterKey")
        if len(item["FilterValue"]) > 100:
            raise _invalid("Filters.FilterValue 最多 100 个", field=f"Filters[{index}].FilterValue")


def _validate_filter_info(body: Mapping[str, Any]) -> None:
    if body["TimeGranularity"] not in _TIME_GRANULARITY:
        raise _invalid("TimeGranularity 只能是 0 或 1", field="TimeGranularity")
    begin = _parse_day(body["BeginTimeStr"], "BeginTimeStr")
    end = _parse_day(body["EndTimeStr"], "EndTimeStr")
    if begin > end:
        raise _invalid(
            "BeginTimeStr 不能晚于 EndTimeStr",
            fields=["BeginTimeStr", "EndTimeStr"],
        )
    if body["TimeGranularity"] == 0 and (begin.day != 1 or end.day != 1):
        raise _invalid(
            "按月查询时 BeginTimeStr/EndTimeStr 必须为 YYYY-MM-01",
            fields=["BeginTimeStr", "EndTimeStr"],
        )


def _type_error(path: str, type_name: str) -> dict[str, str]:
    labels = {
        "string": ("string_type", "string"),
        "int32": ("int_type", "integer"),
        "int64": ("int_type", "integer"),
        "bool": ("bool_type", "boolean"),
        "float": ("float_type", "number"),
        "double": ("float_type", "number"),
        "object": ("model_type", "dictionary"),
    }
    error_type, label = labels[type_name]
    message = f"Input should be a valid {label}"
    return {"path": path, "type": error_type, "message": message}


def _strict_type_matches(field: ApiRequestParamSpec, value: Any) -> bool:
    if field.type_name == "string":
        return isinstance(value, str)
    if field.type_name in {"int32", "int64"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if field.type_name == "bool":
        return isinstance(value, bool)
    if field.type_name in {"float", "double"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field.type_name == "object":
        return isinstance(value, Mapping)
    return False


def _enum_values(field: ApiRequestParamSpec) -> tuple[Any, ...]:
    if not field.enum_value:
        return ()
    values: list[Any] = []
    for raw in field.enum_value.split(","):
        raw = raw.strip()
        if field.type_name in {"int32", "int64"}:
            values.append(int(raw))
        elif field.type_name in {"float", "double"}:
            values.append(float(raw))
        else:
            values.append(raw)
    return tuple(values)


def _enum_message(values: tuple[Any, ...]) -> str:
    rendered = [repr(value) for value in values]
    if len(rendered) == 1:
        return f"Input should be {rendered[0]}"
    return f"Input should be {', '.join(rendered[:-1])} or {rendered[-1]}"


def _validate_scalar(field: ApiRequestParamSpec, value: Any, path: str) -> tuple[Any, list[dict[str, str]]]:
    enum = _enum_values(field)
    if field.validation_kind in {"enum", "literal"}:
        matching = next((candidate for candidate in enum if value == candidate), None)
        if matching is None:
            error_type = "literal_error" if field.validation_kind == "literal" else "enum"
            return value, [{"path": path, "type": error_type, "message": _enum_message(enum)}]
        value = matching
    if not _strict_type_matches(field, value):
        if field.type_name == "object":
            object_name = field.object_type_name or field.name
            return value, [{
                "path": path,
                "type": "model_type",
                "message": f"Input should be a valid dictionary or instance of {object_name}",
            }]
        return value, [_type_error(path, field.type_name)]

    errors: list[dict[str, str]] = []
    if enum and field.validation_kind == "strict" and value not in enum:
        error_type = "literal_error" if field.type_name in {"int32", "int64"} else "enum"
        errors.append({"path": path, "type": error_type, "message": _enum_message(enum)})
    if isinstance(value, str):
        if not field.is_array and field.min_length and len(value) < field.min_length:
            errors.append({
                "path": path,
                "type": "string_too_short",
                "message": f"String should have at least {field.min_length} characters",
            })
        elif not field.is_array and field.max_length and len(value) > field.max_length:
            errors.append({
                "path": path,
                "type": "string_too_long",
                "message": f"String should have at most {field.max_length} characters",
            })
        elif field.reg_pattern and re.search(field.reg_pattern, value) is None:
            errors.append({
                "path": path,
                "type": "string_pattern_mismatch",
                "message": f"String should match pattern '{field.reg_pattern}'",
            })
    if field.min_value and value < int(field.min_value):
        errors.append({
            "path": path,
            "type": "greater_than_equal",
            "message": f"Input should be greater than or equal to {field.min_value}",
        })
    if field.max_value and value > int(field.max_value):
        errors.append({
            "path": path,
            "type": "less_than_equal",
            "message": f"Input should be less than or equal to {field.max_value}",
        })
    if field.type_name == "object":
        normalized, nested_errors = _validate_object(field.children, value, path)
        return normalized, errors + nested_errors
    return value, errors


def _validate_value(field: ApiRequestParamSpec, value: Any, path: str) -> tuple[Any, list[dict[str, str]]]:
    if value is None:
        if field.is_required:
            return value, [_type_error(path, field.type_name)]
        return None, []
    if not field.is_array:
        return _validate_scalar(field, value, path)
    if not isinstance(value, list):
        return value, [{"path": path, "type": "list_type", "message": "Input should be a valid list"}]
    if field.min_length and len(value) < field.min_length:
        return value, [{
            "path": path,
            "type": "too_short",
            "message": f"List should have at least {field.min_length} items after validation, not {len(value)}",
        }]
    if field.max_length and len(value) > field.max_length:
        return value, [{
            "path": path,
            "type": "too_long",
            "message": f"List should have at most {field.max_length} items after validation, not {len(value)}",
        }]
    normalized: list[Any] = []
    errors: list[dict[str, str]] = []
    for index, item in enumerate(value):
        item_path = f"{path}.{index}"
        if field.type_name == "object" and not isinstance(item, Mapping):
            object_name = field.object_type_name or field.name
            errors.append({
                "path": item_path,
                "type": "model_type",
                "message": f"Input should be a valid dictionary or instance of {object_name}",
            })
            continue
        validated, item_errors = _validate_scalar(field, item, item_path)
        normalized.append(validated)
        errors.extend(item_errors)
    return normalized, errors


def _validate_object(
    fields: tuple[ApiRequestParamSpec, ...],
    body: Mapping[str, Any],
    prefix: str = "",
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    normalized: dict[str, Any] = {}
    errors: list[dict[str, str]] = []
    consumed: set[str] = set()
    for field in fields:
        supplied_name = field.name if field.name in body else field.python_name if field.python_name in body else None
        path = f"{prefix}.{field.name}" if prefix else field.name
        if supplied_name is None:
            if field.is_required:
                errors.append({"path": path, "type": "missing", "message": "Field required"})
            continue
        consumed.add(supplied_name)
        value, field_errors = _validate_value(field, body[supplied_name], path)
        errors.extend(field_errors)
        if not field_errors and value is not None:
            normalized[field.name] = value
    for name in body:
        if name not in consumed:
            path = f"{prefix}.{name}" if prefix else str(name)
            errors.append({"path": path, "type": "extra_forbidden", "message": "Extra inputs are not permitted"})
    return normalized, errors


def normalize_request_aliases(action: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize supplied aliases before wrapper checks, without adding defaults."""

    def normalize(fields: Sequence[ApiRequestParamSpec], value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
        aliases = {name: field for field in fields for name in (field.name, field.python_name)}
        result: dict[str, Any] = {}
        for name, item in value.items():
            field = aliases.get(name)
            canonical = field.name if field else name
            path = f"{prefix}.{canonical}" if prefix else canonical
            if canonical in result:
                raise _invalid("同一请求参数不能同时提供多种名称", field=path)
            if field and field.children:
                if field.is_array and isinstance(item, list):
                    item = [normalize(field.children, child, f"{path}.{index}") if isinstance(child, Mapping) else child
                            for index, child in enumerate(item)]
                elif isinstance(item, Mapping):
                    item = normalize(field.children, item, path)
            result[canonical] = item
        return result

    return normalize(ACTION_SCHEMAS[action].request_params, body)


def validate_request_body(action: str, body: Mapping[str, Any]) -> dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        raise BillingQueryError(
            ErrorCode.UNSUPPORTED_ACTION,
            f"不支持的 Billing Action：{action}",
            ExitCode.INVALID_ARGUMENT,
            {"allowed": sorted(ALLOWED_ACTIONS)},
        )
    if not isinstance(body, Mapping):
        raise _invalid("请求 body 必须是 JSON object")
    compatible_body = normalize_wrapper_request_body(action, body)
    normalized, errors = _validate_object(ACTION_SCHEMAS[action].request_params, compatible_body)
    # 归因筛选可以省略，但显式 null 不能按通用可选字段规则被删除并扩大范围。
    if action in COST_CHANGE_ACTIONS:
        filter_key = "filters" if action == "QueryCostChangeDrivers" else "Filters"
        filters = compatible_body.get(filter_key, compatible_body.get("filters"))
        filter_spec = ACTION_SCHEMAS[action].request_params_by_name[filter_key]
        if isinstance(filters, Mapping):
            for name, value in filters.items():
                field = filter_spec.children_by_name.get(name)
                if field is not None and value is None and not field.is_required:
                    errors.append(_type_error(f"{filter_key}.{name}", "string"))
    if errors:
        if action == "ListBillDetail":
            invalid_fields = [
                item["path"]
                for item in errors
                if item["type"] == "extra_forbidden"
                and "." not in item["path"]
                and item["path"] in LIST_BILL_DETAIL_RESPONSE_FIELD_HINTS
            ]
            if invalid_fields:
                suggestions = {
                    field: dict(LIST_BILL_DETAIL_RESPONSE_FIELD_HINTS[field])
                    for field in invalid_fields
                }
                raise BillingQueryError(
                    ErrorCode.RESPONSE_FIELDS_IN_REQUEST_BODY,
                    "检测到响应字段或其常见误写被放入 ListBillDetail 请求 body",
                    ExitCode.INVALID_ARGUMENT,
                    {
                        "invalid_request_fields": invalid_fields,
                        "request_projection_supported": False,
                        "possible_response_fields": suggestions,
                        "instruction": (
                            "删除这些 body 字段；响应字段不作为请求参数发送。"
                            "如需对应数据，读取 GroupPeriod/GroupTerm 的 field_decisions "
                            "选择可保留字段的粒度。"
                        ),
                        "request_contract_command": (
                            "python3 scripts/cost.py schema --action ListBillDetail "
                            "--section request --field GroupPeriod"
                        ),
                        "validation_errors": errors,
                        "invalid_parameters": _invalid_parameters_from_validation_errors(
                            action,
                            compatible_body,
                            errors,
                        ),
                    },
                )
        raise _invalid(
            "请求不符合目标 Action 契约",
            validation_errors=errors,
            invalid_parameters=_invalid_parameters_from_validation_errors(
                action,
                compatible_body,
                errors,
            ),
        )
    try:
        _validate_common(action, normalized)
        if action == "ListCostAnalysisOpenApi":
            _validate_list_cost_analysis_request(normalized)
        elif action == "GetFilterInfoForCostAnalysis":
            _validate_filter_info(normalized)
    except BillingQueryError as exc:
        _attach_invalid_parameter_contracts(action, normalized, exc)
        raise
    return normalized
