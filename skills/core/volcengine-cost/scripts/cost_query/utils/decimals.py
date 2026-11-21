"""Shared Decimal presentation helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Sequence


def decimal_value(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def exact_sum(values: Sequence[Decimal]) -> Decimal:
    """Retain source precision even when the default Decimal context is too small."""

    if not values:
        return Decimal(0)
    lowest_exponent = min(value.as_tuple().exponent for value in values)
    highest_place = max(value.adjusted() for value in values)
    with localcontext() as context:
        context.prec = max(
            28,
            highest_place - lowest_exponent + len(str(len(values))) + 2,
        )
        return sum(values, Decimal(0))


def format_decimal(value: Decimal) -> str:
    return format(value, "f")
