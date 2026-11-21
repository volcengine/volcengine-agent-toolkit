"""归因接口的响应完整性校验；不包含分析编排或业务计算。"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Mapping, Sequence

from ..common.errors import BillingQueryError, ErrorCode, ExitCode


COST_CHANGE_ACTIONS = frozenset({
    "QueryCostChangeDimensions",
    "QueryCostChangeAmountComponents",
    "QueryCostChangeDrivers",
})


def _invalid_analysis(path: str) -> BillingQueryError:
    return BillingQueryError(
        ErrorCode.RESPONSE_INVALID,
        f"归因响应缺少必要字段或字段值无效：{path}",
        ExitCode.QUERY_FAILED,
        {"field": path},
    )


def _require_numbers(value: Mapping[str, Any], names: Sequence[str], prefix: str = "") -> None:
    for name in names:
        number = value.get(name)
        try:
            valid = number.is_finite() if isinstance(number, Decimal) else (
                not isinstance(number, bool) and isinstance(number, (int, float)) and math.isfinite(number)
            )
        except OverflowError:
            valid = False
        if not valid:
            raise _invalid_analysis(f"{prefix}{name}")


def _required_items(value: Mapping[str, Any], name: str, prefix: str = "") -> Sequence[Mapping[str, Any]]:
    if name not in value:
        raise _invalid_analysis(f"{prefix}{name}")
    items = value[name]
    if items is None:
        return ()
    if not isinstance(items, list) or any(not isinstance(item, Mapping) for item in items):
        raise _invalid_analysis(f"{prefix}{name}")
    return items


def validate_cost_change_result(action: str, payload: Mapping[str, Any]) -> None:
    drivers = action == "QueryCostChangeDrivers"
    totals = ("total_diff", "base_amount", "current_amount") if drivers else ("totalDiff", "baseAmount", "currentAmount")
    _require_numbers(payload, totals)
    list_key = "contributions" if drivers else "candidates"
    for index, item in enumerate(_required_items(payload, list_key)):
        prefix = f"{list_key}.{index}."
        if not isinstance(item.get("dimension"), str):
            raise _invalid_analysis(prefix + "dimension")
        if drivers:
            _require_numbers(item, ("contribution", "base_amount", "current_amount"), prefix)
            if item.get("dimension_name") is not None and not isinstance(item["dimension_name"], str):
                raise _invalid_analysis(prefix + "dimension_name")
            continue
        _require_numbers(item, ("coverageRatio",), prefix)
        for value_index, value in enumerate(_required_items(item, "values", prefix)):
            value_prefix = f"{prefix}values.{value_index}."
            if not isinstance(value.get("valueKey"), str):
                raise _invalid_analysis(value_prefix + "valueKey")
            if value.get("valueName") is not None and not isinstance(value["valueName"], str):
                raise _invalid_analysis(value_prefix + "valueName")
            _require_numbers(value, ("deltaAmount", "baseAmount", "currentAmount", "contributionRatio"), value_prefix)
