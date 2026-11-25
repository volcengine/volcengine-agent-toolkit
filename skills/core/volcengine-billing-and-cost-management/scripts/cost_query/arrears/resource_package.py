"""基于已查询数据生成资源包原因证据，不发起网络请求。"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from .comparison import compare_bill_periods
from ..common.json_output import dumps as json_dumps
from ..utils.datetimes import parse_iso_datetime_utc as _time
from ..utils.decimals import decimal_value, exact_sum
from ..utils.rows import row_decimal as _decimal, row_text as _text


PACKAGE_TERMINAL_STATUSES = {"UsedUp", "Expired", "Refunded", "FailedToCreate"}
PACKAGE_COMPARISON_DIMENSIONS = ("Product", "ConfigName", "InstanceNo", "ElementCode", "Region", "BillingMode", "Unit", "Currency")


def _bill_identity(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        field: _text(row, field)
        for field in (
            "BillPeriod",
            "Product",
            "ProductZh",
            "ConfigName",
            "InstanceNo",
            "Element",
            "ElementCode",
            "Region",
            "Zone",
            "BillingMode",
            "Unit",
            "Currency",
        )
    }


def _package_identity(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        field: _text(row, field)
        for field in (
            "InstanceNo",
            "InstanceName",
            "Product",
            "ProductName",
            "Status",
            "PackageType",
            "AvailableAmount",
            "TotalAmount",
            "Unit",
            "EffectiveTime",
            "ExpiryTime",
            "ConfigurationCode",
            "ConfigurationName",
            "RegionCode",
            "ZoneCode",
        )
    }


def _usage_matches_bill(
    usage: Mapping[str, Any],
    bill: Mapping[str, Any],
    *,
    require_time_overlap: bool = False,
) -> tuple[bool, dict[str, Any]]:
    checks: dict[str, Any] = {}
    pairs = (
        ("product", "DeductionProduct", "Product", True),
        ("charge_item", "DeductionElementCode", "ElementCode", True),
        ("instance", "DeductionInstanceNo", "InstanceNo", True),
        ("region", "DeductionRegionCode", "Region", True),
    )
    enough_identity = True
    for name, usage_field, bill_field, required in pairs:
        left = _text(usage, usage_field)
        right = _text(bill, bill_field)
        if not left or not right:
            checks[name] = "unknown"
            if required:
                enough_identity = False
            continue
        checks[name] = left == right
        if left != right:
            return False, checks

    usage_begin = _time(usage.get("BeginTime"))
    usage_end = _time(usage.get("EndTime"))
    bill_begin = _time(bill.get("ExpenseBeginTime"))
    bill_end = _time(bill.get("ExpenseEndTime"))
    if usage_begin and bill_end and usage_begin > bill_end:
        checks["consumption_time"] = "historical_link"
        if require_time_overlap:
            return False, checks
    if usage_end and bill_begin and usage_end < bill_begin:
        checks["consumption_time"] = "historical_link"
        if require_time_overlap:
            return False, checks
    if "consumption_time" not in checks:
        checks["consumption_time"] = True if (usage_begin or usage_end) and (bill_begin or bill_end) else "unknown"
    return enough_identity, checks


def _uncovered_payg_bill(row: Mapping[str, Any]) -> bool:
    count = _decimal(row, "Count")
    deducted = _decimal(row, "DeductionCount")
    payable = _decimal(row, "PayableAmount")
    return (
        _text(row, "BillingMode") == "2"
        and count is not None
        and deducted is not None
        and payable is not None
        and count > 0
        and deducted < count
        and payable > 0
    )


def _linked_usage(
    package: Mapping[str, Any],
    bill: Mapping[str, Any],
    usage_details: Sequence[Mapping[str, Any]],
) -> list[tuple[Mapping[str, Any], dict[str, Any]]]:
    instance_no = _text(package, "InstanceNo")
    if not instance_no:
        return []
    linked = []
    for usage in usage_details:
        if _text(usage, "InstanceNo") != instance_no:
            continue
        matches, checks = _usage_matches_bill(usage, bill)
        if matches:
            linked.append((usage, checks))
    return sorted(linked, key=lambda item: (
        _text(item[0], "BeginTime"), _text(item[0], "EndTime"),
        json_dumps(dict(item[0]), sort_keys=True),
    ))


def _scope_evidence(checks: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "product": checks.get("product", "unknown"),
        "charge_item": checks.get("charge_item", "unknown"),
        "instance": checks.get("instance", "unknown"),
        "region": checks.get("region", "unknown"),
        "consumption_time": checks.get("consumption_time", "unknown"),
        "configuration": "not_declared_by_package_contract",
        "charge_mode": "not_declared_by_package_contract",
        "wildcards": "not_declared_by_package_contract",
    }


def _reason(
    reason_type: str,
    package: Mapping[str, Any],
    bill: Mapping[str, Any],
    checks: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "reason_type": reason_type,
        "package": _package_identity(package),
        "affected_bill": _bill_identity(bill),
        "scope_match": _scope_evidence(checks),
        "evidence": dict(evidence),
    }


def _status_reasons(
    packages: Sequence[Mapping[str, Any]],
    usage_details: Sequence[Mapping[str, Any]],
    bills: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reasons: list[dict[str, Any]] = []
    insufficient: list[dict[str, Any]] = []
    for bill in bills:
        if not _uncovered_payg_bill(bill):
            continue
        same_product = [item for item in packages if _text(item, "Product") == _text(bill, "Product")]
        if not same_product:
            continue
        for package in same_product:
            linked = _linked_usage(package, bill, usage_details)
            if not linked:
                insufficient.append({
                    "candidate": "resource_package_scope",
                    "package": _package_identity(package),
                    "affected_bill": _bill_identity(bill),
                    "missing_evidence": ["matching package usage detail for product and charge item"],
                })
                continue
            usage, checks = linked[-1]
            status = _text(package, "Status")
            available = _decimal(package, "AvailableAmount")
            bill_begin = _time(bill.get("ExpenseBeginTime"))
            effective = _time(package.get("EffectiveTime"))
            expiry = _time(package.get("ExpiryTime"))
            evidence = {
                "bill_count": _text(bill, "Count"),
                "bill_deduction_count": _text(bill, "DeductionCount"),
                "bill_payable_amount": _text(bill, "PayableAmount"),
                "linked_usage_deduction_amount": _text(usage, "DeductionAmount"),
                "linked_usage_after_amount": _text(usage, "AfterAmount"),
            }
            if effective and bill_begin and bill_begin < effective:
                reasons.append(_reason("resource_package_not_effective", package, bill, checks, evidence))
            elif expiry and bill_begin and bill_begin > expiry:
                reasons.append(_reason("resource_package_expired", package, bill, checks, evidence))
            elif status == "UsedUp" or (available == 0 and status not in PACKAGE_TERMINAL_STATUSES):
                reasons.append(_reason("resource_package_used_up", package, bill, checks, evidence))
            elif status in PACKAGE_TERMINAL_STATUSES:
                insufficient.append({
                    "candidate": "resource_package_status",
                    "package": _package_identity(package),
                    "affected_bill": _bill_identity(bill),
                    "missing_evidence": ["status-specific time or remaining-amount evidence"],
                })
    return reasons, insufficient


def _deduction_sums(
    package: Mapping[str, Any],
    bill: Mapping[str, Any],
    usage_details: Sequence[Mapping[str, Any]],
    periods: set[str],
    period_bills: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Decimal], list[str]]:
    values: dict[str, list[Decimal]] = defaultdict(list)
    missing = []
    windows: dict[str, list[tuple[datetime, datetime]]] = {}
    for period in sorted(periods):
        intervals = []
        for source_bill in period_bills[period]:
            begin = _time(source_bill.get("ExpenseBeginTime"))
            end = _time(source_bill.get("ExpenseEndTime"))
            if begin is None or end is None or end <= begin:
                missing.append(f"{period}:valid bill ExpenseBeginTime/ExpenseEndTime")
            else:
                intervals.append((begin, end))
        merged: list[tuple[datetime, datetime]] = []
        for begin, end in sorted(intervals):
            if merged and begin <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((begin, end))
        windows[period] = merged
    if missing:
        return {}, sorted(set(missing))
    pairs = (
        ("DeductionProduct", "Product"), ("DeductionElementCode", "ElementCode"),
        ("DeductionInstanceNo", "InstanceNo"), ("DeductionRegionCode", "Region"),
    )
    for usage in usage_details:
        package_id = _text(usage, "InstanceNo")
        if package_id and package_id != _text(package, "InstanceNo"):
            continue
        if any(_text(usage, left) and _text(usage, left) != _text(bill, right) for left, right in pairs):
            continue
        identity_missing = [left for left, _ in pairs if not _text(usage, left)]
        if not package_id:
            identity_missing.append("InstanceNo")
        if identity_missing:
            missing.extend(f"usage:{field}" for field in identity_missing)
            continue
        begin = _time(usage.get("BeginTime"))
        end = _time(usage.get("EndTime"))
        if begin is None or end is None or end <= begin:
            missing.append("usage:valid consumption BeginTime/EndTime")
            continue
        overlapping = {
            period for period, intervals in windows.items()
            if any(begin < window_end and end > window_begin for window_begin, window_end in intervals)
        }
        if not overlapping:
            continue
        assigned = {
            period for period, intervals in windows.items()
            if any(begin >= window_begin and end <= window_end for window_begin, window_end in intervals)
        }
        if len(assigned) != 1 or overlapping != assigned:
            missing.append("usage:consumption interval has no unique full bill-period assignment")
            continue
        period = next(iter(assigned))
        if _text(usage, "DeductionInstanceUnit") != _text(bill, "Unit"):
            missing.append("usage:matching DeductionInstanceUnit")
            continue
        amount = decimal_value(usage.get("DeductionUseAmount"))
        if amount is None:
            missing.append("usage:DeductionUseAmount")
            continue
        values[period].append(amount)
    return {period: exact_sum(amounts) for period, amounts in values.items()}, sorted(set(missing))


def _decline_reasons(
    packages: Sequence[Mapping[str, Any]],
    usage_details: Sequence[Mapping[str, Any]],
    bills: Sequence[Mapping[str, Any]],
    analysis_period: str,
    comparison_period: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not comparison_period:
        return [], []
    reasons = []
    comparisons, insufficient = compare_bill_periods(
        bills,
        analysis_period=analysis_period,
        comparison_period=comparison_period,
        dimensions=PACKAGE_COMPARISON_DIMENSIONS,
        optional_dimensions=("Zone",),
        amounts=("Count", "DeductionCount", "PayableAmount"),
    )
    for comparison in comparisons:
        bill = comparison.current.bill()
        if comparison.missing_evidence:
            insufficient.append({
                "candidate": "resource_package_deduction_declined",
                "affected_bill": comparison.current.identity,
                "missing_evidence": list(comparison.missing_evidence),
            })
            continue
        if not _uncovered_payg_bill(bill):
            continue
        current_payable = _decimal(bill, "PayableAmount")
        previous_payable = comparison.previous.totals["PayableAmount"]
        if current_payable is None or previous_payable is None or current_payable <= previous_payable:
            continue
        for package in packages:
            if _text(package, "Product") != _text(bill, "Product"):
                continue
            sums, missing = _deduction_sums(
                package, bill, usage_details, {analysis_period, comparison_period},
                {analysis_period: comparison.current.rows, comparison_period: comparison.previous.rows},
            )
            # Usage has no bill ConfigName/Currency key: refuse an ambiguous
            # assignment to several bill groups with the same consumption keys.
            usage_keys = ("Product", "InstanceNo", "ElementCode", "Region")
            related_groups = {
                tuple(_text(row, field) for field in comparison.fields)
                for row in bills
                if _text(row, "BillPeriod") in {analysis_period, comparison_period}
                and all(_text(row, field) == bill[field] for field in usage_keys)
            }
            if len(related_groups) > 1:
                missing.append("unique bill group for package usage consumption keys")
            if missing:
                insufficient.append({
                    "candidate": "resource_package_deduction_declined",
                    "package": _package_identity(package),
                    "affected_bill": comparison.current.identity,
                    "missing_evidence": missing,
                })
                continue
            current = sums.get(analysis_period)
            previous = sums.get(comparison_period)
            if current is None or previous is None or current >= previous:
                continue
            linked = _linked_usage(package, bill, usage_details)
            if not linked:
                continue
            _, checks = linked[-1]
            reasons.append(_reason(
                "resource_package_deduction_declined",
                package,
                bill,
                checks,
                {
                    "analysis_period_deduction_use_amount": str(current),
                    "comparison_period_deduction_use_amount": str(previous),
                    "analysis_period_payable_amount": str(current_payable),
                    "comparison_period_payable_amount": str(previous_payable),
                    "deduction_instance_unit": _text(bill, "Unit"),
                    **comparison.evidence(),
                },
            ))
    return reasons, insufficient


def _explicit_noncoverage_reasons(
    packages: Sequence[Mapping[str, Any]],
    bills: Sequence[Mapping[str, Any]],
    analysis_period: str,
    candidate_instance_nos: Sequence[str],
) -> list[dict[str, Any]]:
    candidates = set(candidate_instance_nos)
    if not candidates:
        return []
    reasons = []
    for package in packages:
        if _text(package, "InstanceNo") not in candidates:
            continue
        for bill in bills:
            if _text(bill, "BillPeriod") != analysis_period or not _uncovered_payg_bill(bill):
                continue
            package_product = _text(package, "Product")
            bill_product = _text(bill, "Product")
            package_region = _text(package, "RegionCode")
            bill_region = _text(bill, "Region")
            mismatch = None
            checks: dict[str, Any] = {
                "product": "unknown",
                "charge_item": "unknown",
                "instance": "unknown",
                "region": "unknown",
                "consumption_time": "unknown",
            }
            if package_product and bill_product:
                checks["product"] = package_product == bill_product
                if package_product != bill_product:
                    mismatch = ("product", package_product, bill_product)
            if mismatch is None and package_region and bill_region:
                checks["region"] = package_region == bill_region
                if package_region != bill_region:
                    mismatch = ("region", package_region, bill_region)
            if mismatch is None:
                continue
            dimension, package_value, bill_value = mismatch
            reasons.append(_reason(
                "resource_package_not_covering",
                package,
                bill,
                checks,
                {
                    "candidate_selected_explicitly": True,
                    "mismatch_dimension": dimension,
                    "package_value": package_value,
                    "bill_value": bill_value,
                },
            ))
    return reasons


def _deduplicate(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in sorted(items, key=lambda item: json_dumps(item, sort_keys=True)):
        key = (
            item.get("reason_type"),
            item.get("package", {}).get("InstanceNo"),
            tuple(sorted(item.get("affected_bill", {}).items())),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def analyze_resource_package_attribution(
    *,
    packages: Sequence[Mapping[str, Any]],
    usage_details: Sequence[Mapping[str, Any]],
    bill_details: Sequence[Mapping[str, Any]],
    analysis_period: str,
    comparison_period: str | None = None,
    candidate_instance_nos: Sequence[str] = (),
) -> dict[str, Any]:
    """生成 supported/insufficient 资源包证据，不把资源包原因替代账户欠费事实。"""

    relevant_bills = [row for row in bill_details if _text(row, "BillPeriod") in {analysis_period, comparison_period}]
    status_reasons, insufficient = _status_reasons(packages, usage_details, relevant_bills)
    decline_reasons, comparison_insufficient = _decline_reasons(
        packages,
        usage_details,
        relevant_bills,
        analysis_period,
        comparison_period,
    )
    insufficient.extend(comparison_insufficient)
    noncoverage_reasons = _explicit_noncoverage_reasons(
        packages,
        relevant_bills,
        analysis_period,
        candidate_instance_nos,
    )
    supported = _deduplicate([*status_reasons, *decline_reasons, *noncoverage_reasons])
    insufficient.sort(key=lambda item: json_dumps(item, sort_keys=True))
    return {
        "cause_layer": "secondary_consumption_driver",
        "analysis_period": analysis_period,
        "comparison_period": comparison_period,
        "supported_reasons": supported,
        "insufficient_evidence": insufficient,
        "summary": {
            "package_count": len(packages),
            "usage_detail_count": len(usage_details),
            "bill_detail_count": len(relevant_bills),
            "supported_reason_count": len(supported),
            "insufficient_candidate_count": len(insufficient),
        },
        "contract_limits": [
            "package.json does not expose explicit all-configuration or all-charge-item scope fields",
            "package configuration name/code is not treated as an applicability wildcard",
            "charge-mode applicability is not inferred from package inventory",
            "resource-package evidence does not replace the account-level arrears decision",
        ],
    }
