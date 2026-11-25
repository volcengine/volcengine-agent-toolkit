"""Typed accessors for row-shaped mappings."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from .decimals import decimal_value


def row_text(row: Mapping[str, Any], field: str) -> str:
    value = row.get(field)
    return "" if value is None else str(value).strip()


def row_decimal(row: Mapping[str, Any], field: str) -> Decimal | None:
    return decimal_value(row.get(field))
