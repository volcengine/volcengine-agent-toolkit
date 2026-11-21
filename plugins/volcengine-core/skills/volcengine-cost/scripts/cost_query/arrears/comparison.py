"""Aggregate comparable bill-period groups before attributing a deduction decline."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from ..utils.decimals import decimal_value, exact_sum
from ..utils.rows import row_text as text


__all__ = ["BillComparison", "BillGroup", "compare_bill_periods"]


@dataclass(frozen=True)
class BillGroup:
    identity: dict[str, str]
    rows: tuple[Mapping[str, Any], ...]
    totals: dict[str, Decimal | None]

    def bill(self) -> dict[str, str]:
        return {
            **self.identity,
            **{field: str(amount) for field, amount in self.totals.items() if amount is not None},
        }


@dataclass(frozen=True)
class BillComparison:
    current: BillGroup
    previous: BillGroup | None
    fields: tuple[str, ...]
    missing_evidence: tuple[str, ...]

    def evidence(self) -> dict[str, Any]:
        return {
            "comparison_axis": "BillPeriod",
            "group_by": list(self.fields),
            "analysis_period": self.current.identity["BillPeriod"],
            "comparison_period": self.previous.identity["BillPeriod"] if self.previous else None,
            "analysis_period_row_count": len(self.current.rows),
            "comparison_period_row_count": len(self.previous.rows) if self.previous else 0,
        }


def compare_bill_periods(
    rows: Sequence[Mapping[str, Any]],
    *,
    analysis_period: str,
    comparison_period: str,
    dimensions: Sequence[str],
    amounts: Sequence[str],
    optional_dimensions: Sequence[str] = (),
) -> tuple[list[BillComparison], list[dict[str, Any]]]:
    """Missing identity never acts as a wildcard; uncertain rows block compatible groups.

    The window is the selected BillPeriod input scope, rather than an individual
    consumption interval. Callers retain query-scope/completeness restrictions.
    """
    if analysis_period == comparison_period:
        raise ValueError("analysis-period 与 comparison-period 必须是不同账期")
    relevant = [row for row in rows if text(row, "BillPeriod") in {analysis_period, comparison_period}]
    fields = tuple(dict.fromkeys([
        *dimensions,
        *(field for field in optional_dimensions if any(text(row, field) for row in relevant)),
    ]))
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = {}
    unidentified: list[Mapping[str, Any]] = []
    for row in relevant:
        if any(not text(row, field) for field in fields):
            unidentified.append(row)
            continue
        key = (text(row, "BillPeriod"), *(text(row, field) for field in fields))
        grouped.setdefault(key, []).append(row)

    groups: dict[tuple[str, ...], BillGroup] = {}
    for key, members in sorted(grouped.items()):
        totals: dict[str, Decimal | None] = {}
        for field in amounts:
            values = [decimal_value(row.get(field)) for row in members]
            totals[field] = (
                exact_sum([value for value in values if value is not None])
                if all(value is not None for value in values)
                else None
            )
        groups[key] = BillGroup(dict(zip(("BillPeriod", *fields), key)), tuple(members), totals)

    comparisons = []
    for key, current in groups.items():
        if key[0] != analysis_period:
            continue
        previous = groups.get((comparison_period, *key[1:]))
        missing = []
        if previous is None:
            missing.append("matching comparison-period bill group")
        for group in (current, previous):
            if group is not None:
                missing.extend(
                    f"{group.identity['BillPeriod']}:{field}"
                    for field, amount in group.totals.items() if amount is None
                )
        for row in unidentified:
            if all(not text(row, field) or text(row, field) == current.identity[field] for field in fields):
                missing.extend(f"{text(row, 'BillPeriod')}:{field}" for field in fields if not text(row, field))
        comparisons.append(BillComparison(current, previous, fields, tuple(sorted(set(missing)))))

    unidentified_evidence = {
        tuple((field, text(row, field)) for field in ("BillPeriod", *fields))
        for row in unidentified
    }
    issues = []
    for identity in sorted(unidentified_evidence):
        affected = dict(identity)
        issues.append({
            "candidate": "bill_period_comparison",
            "affected_bill": affected,
            "missing_evidence": [
                f"{affected['BillPeriod']}:{field}" for field in fields if not affected[field]
            ],
        })
    return comparisons, issues
