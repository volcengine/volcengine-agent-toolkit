"""基于代金券库存和账单抵扣字段生成第二层消费原因。"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Mapping, Sequence

from .comparison import compare_bill_periods
from ..common.json_output import dumps as json_dumps
from ..utils.datetimes import parse_iso_datetime_utc as _time
from ..utils.decimals import decimal_value, exact_sum
from ..utils.rows import row_decimal as _decimal, row_text as _text


COUPON_COMPARISON_DIMENSIONS = ("Product", "ConfigName", "InstanceNo", "ElementCode", "BillingMode", "Currency")


def _int(row: Mapping[str, Any], field: str) -> int | None:
    value = row.get(field)
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _limits(coupon: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = coupon.get("ProductLimitList")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _billing_mode_kind(bill: Mapping[str, Any]) -> str:
    mode = _text(bill, "BillingMode")
    if mode == "1":
        return "pre"
    if mode == "2":
        return "post"
    return "unknown"


def _configuration_match(limit: Mapping[str, Any], bill: Mapping[str, Any]) -> tuple[Any, list[str]]:
    kind = _int(limit, "ConfigurationType")
    mode = _billing_mode_kind(bill)
    if kind == 1:
        return True, ["全部配置"]
    if kind == 2:
        return mode == "pre" if mode != "unknown" else "unknown", ["全部预付费配置"]
    if kind == 3:
        return mode == "post" if mode != "unknown" else "unknown", ["全部后付费配置"]
    if kind == 4:
        expected_name = _text(limit, "ConfigurationName")
        actual_name = _text(bill, "ConfigName")
        if expected_name and actual_name:
            return expected_name == actual_name, []
        return "unknown", []
    return "unknown", []


def _charge_item_match(limit: Mapping[str, Any], bill: Mapping[str, Any]) -> tuple[Any, list[str]]:
    kind = _int(limit, "ChargeItemType")
    if kind == 0:
        return True, ["全部计费项"]
    if kind == 1:
        expected = _text(limit, "ChargeItemCode")
        actual = _text(bill, "ElementCode")
        if expected and actual:
            return expected == actual, []
        return "unknown", []
    return "unknown", []


def _pay_type_match(coupon: Mapping[str, Any], bill: Mapping[str, Any]) -> Any:
    limit = _text(coupon, "PayTypeLimit")
    mode = _billing_mode_kind(bill)
    if limit == "all":
        return True
    if limit in {"pre", "post"} and mode != "unknown":
        return limit == mode
    return "unknown"


def _amount_limit_match(coupon: Mapping[str, Any], bill: Mapping[str, Any]) -> Any:
    threshold = _decimal(coupon, "AmountLimit")
    eligible = _decimal(bill, "DiscountBillAmount")
    if threshold is None:
        return "unknown"
    if threshold <= 0:
        return True
    if eligible is None:
        return "unknown"
    return eligible >= threshold


def _scope_match(coupon: Mapping[str, Any], bill: Mapping[str, Any]) -> dict[str, Any]:
    bill_product = _text(bill, "Product")
    best: dict[str, Any] | None = None
    has_unknown_candidate = False
    for limit in _limits(coupon):
        product = _text(limit, "ProductCode")
        product_match: Any = product == bill_product if product and bill_product else "unknown"
        configuration_match, config_wildcards = _configuration_match(limit, bill)
        charge_item_match, item_wildcards = _charge_item_match(limit, bill)
        pay_type_match = _pay_type_match(coupon, bill)
        amount_limit_match = _amount_limit_match(coupon, bill)
        checks = {
            "product": product_match,
            "configuration": configuration_match,
            "charge_item": charge_item_match,
            "pay_type": pay_type_match,
            "amount_limit": amount_limit_match,
            "billing_method": "not_mapped",
            "order_type": "not_mapped",
            "used_wildcards": [*config_wildcards, *item_wildcards],
            "scope": dict(limit),
        }
        values = (product_match, configuration_match, charge_item_match, pay_type_match, amount_limit_match)
        checks["matched"] = all(value is True for value in values)
        checks["match_status"] = "matched" if checks["matched"] else "not_matched" if any(value is False for value in values) else "unknown"
        has_unknown_candidate = has_unknown_candidate or checks["match_status"] == "unknown"
        if checks["matched"]:
            return checks
        if best is None or sum(value is True for value in values) > sum(
            best.get(key) is True for key in ("product", "configuration", "charge_item", "pay_type", "amount_limit")
        ):
            best = checks
    if best is not None:
        best["match_status"] = "unknown" if has_unknown_candidate else "not_matched"
        return best
    return {
        "product": "unknown",
        "configuration": "unknown",
        "charge_item": "unknown",
        "pay_type": _pay_type_match(coupon, bill),
        "amount_limit": _amount_limit_match(coupon, bill),
        "billing_method": "not_mapped",
        "order_type": "not_mapped",
        "used_wildcards": [],
        "scope": {},
        "matched": False,
        "match_status": "unknown",
    }


def _time_match(coupon: Mapping[str, Any], bill: Mapping[str, Any]) -> dict[str, Any]:
    consumption = _time(bill.get("ExpenseBeginTime"))
    begin = _time(coupon.get("BeginTime"))
    expired = _time(coupon.get("ExpiredTime"))
    if not consumption:
        return {"matched": "unknown", "reason": "missing_bill_consumption_time"}
    if begin and consumption < begin:
        return {"matched": False, "reason": "not_effective", "consumption_time": consumption.isoformat(), "begin_time": begin.isoformat()}
    if expired and consumption > expired:
        return {"matched": False, "reason": "expired", "consumption_time": consumption.isoformat(), "expired_time": expired.isoformat()}
    if begin or expired:
        return {"matched": True, "reason": "within_validity", "consumption_time": consumption.isoformat()}
    return {"matched": "unknown", "reason": "missing_coupon_validity"}


def _bill_identity(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        field: _text(row, field)
        for field in (
            "BillID", "BillDetailId", "BillPeriod", "Product", "ProductZh", "ConfigName", "InstanceNo", "Element",
            "ElementCode", "BillingMode", "Region", "Zone", "Unit", "ExpenseBeginTime", "ExpenseEndTime", "Currency",
        )
    }


def _coupon_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: row.get(field)
        for field in (
            "CouponID", "CouponName", "Status", "RemainingAmount", "TotalAmount", "AmountLimit",
            "BeginTime", "ExpiredTime", "PayTypeLimit", "UsageLimit", "VoidReason",
        )
    }


def _declined(current: Mapping[str, Any], previous: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if previous is None or _text(current, "Currency") != "CNY" or _text(previous, "Currency") != "CNY":
        return None
    current_coupon = _decimal(current, "CouponAmount")
    previous_coupon = _decimal(previous, "CouponAmount")
    current_payable = _decimal(current, "PayableAmount")
    previous_payable = _decimal(previous, "PayableAmount")
    if None in (current_coupon, previous_coupon, current_payable, previous_payable):
        return None
    if current_coupon >= previous_coupon or current_payable <= previous_payable:
        return None
    return {
        "analysis_period_coupon_amount": str(current_coupon),
        "comparison_period_coupon_amount": str(previous_coupon),
        "analysis_period_payable_amount": str(current_payable),
        "comparison_period_payable_amount": str(previous_payable),
        "currency": "CNY",
    }


def _current_unredeemed(current: Mapping[str, Any]) -> dict[str, Any] | None:
    if _text(current, "Currency") != "CNY":
        return None
    coupon = _decimal(current, "CouponAmount")
    payable = _decimal(current, "PayableAmount")
    eligible = _decimal(current, "DiscountBillAmount")
    if coupon is None or payable is None or eligible is None:
        return None
    if coupon != 0 or payable <= 0 or eligible <= 0:
        return None
    return {
        "analysis_period_coupon_amount": str(coupon),
        "analysis_period_payable_amount": str(payable),
        "analysis_period_eligible_amount": str(eligible),
        "currency": "CNY",
    }


def _reason(
    reason_type: str,
    coupon: Mapping[str, Any],
    bill: Mapping[str, Any],
    scope: Mapping[str, Any],
    time: Mapping[str, Any],
    decline: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "reason_type": reason_type,
        "coupon": _coupon_identity(coupon),
        "affected_bill": _bill_identity(bill),
        "scope_match": dict(scope),
        "time_match": dict(time),
        "evidence": dict(decline),
    }


def _deduplicate(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in sorted(items, key=lambda item: json_dumps(item, sort_keys=True)):
        key = json_dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _usage_record_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: row.get(field)
        for field in (
            "CouponID", "ProductCode", "ProductName", "ChangeAmount", "CreatedTime",
            "PayType", "SubBusinessID", "ChangeType", "BillingCycle",
        )
    }


def _usage_summaries(
    *,
    coupons: Sequence[Mapping[str, Any]],
    usage_records: Sequence[Mapping[str, Any]],
    bill_details: Sequence[Mapping[str, Any]],
    analysis_period: str,
    comparison_period: str | None,
    queried_coupon_ids: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    coupon_by_id = {_text(coupon, "CouponID"): coupon for coupon in coupons if _text(coupon, "CouponID")}
    coupon_ids = {str(value).strip() for value in queried_coupon_ids if str(value).strip()}
    coupon_ids.update(_text(record, "CouponID") for record in usage_records if _text(record, "CouponID"))
    periods = [analysis_period, *([comparison_period] if comparison_period else [])]
    amounts: dict[tuple[str, str, int], list[Decimal]] = {}
    counts: dict[tuple[str, str, int], int] = {}
    links: dict[str, list[dict[str, Any]]] = {coupon_id: [] for coupon_id in coupon_ids}
    insufficient: list[dict[str, Any]] = []
    invalid_amounts: set[tuple[str, str, int]] = set()
    bills_by_detail_id: dict[str, list[Mapping[str, Any]]] = {}
    prepaid_bills_by_bill_id: dict[str, list[Mapping[str, Any]]] = {}
    for bill in bill_details:
        detail_id = _text(bill, "BillDetailId")
        if detail_id:
            bills_by_detail_id.setdefault(detail_id, []).append(bill)
        bill_id = _text(bill, "BillID")
        if bill_id and _billing_mode_kind(bill) == "pre":
            prepaid_bills_by_bill_id.setdefault(bill_id, []).append(bill)

    for record in usage_records:
        coupon_id = _text(record, "CouponID")
        cycle = _text(record, "BillingCycle")
        change_type = _int(record, "ChangeType")
        amount = _decimal(record, "ChangeAmount")
        if not coupon_id or not cycle or change_type not in {2, 3} or amount is None or amount < 0:
            for affected_coupon in ([coupon_id] if coupon_id else coupon_ids):
                for affected_period in ([cycle] if cycle else periods):
                    for affected_type in ([change_type] if change_type in {2, 3} else [2, 3]):
                        invalid_amounts.add((affected_coupon, affected_period, affected_type))
            insufficient.append({
                "candidate": "coupon_usage_record",
                "record": _usage_record_identity(record),
                "missing_evidence": [
                    field
                    for field, valid in (
                        ("CouponID", bool(coupon_id)),
                        ("BillingCycle", bool(cycle)),
                        ("ChangeType=2_or_3", change_type in {2, 3}),
                        ("non_negative_finite_ChangeAmount", amount is not None and amount >= 0),
                    )
                    if not valid
                ],
            })
            continue
        key = (coupon_id, cycle, change_type)
        amounts.setdefault(key, []).append(amount)
        counts[key] = counts.get(key, 0) + 1

        pay_type = _text(record, "PayType")
        sub_business_id = _text(record, "SubBusinessID")
        if pay_type in {"pre", "post"} and sub_business_id:
            link_field = "BillDetailId" if pay_type == "post" else "BillID"
            matched_bills = (
                bills_by_detail_id.get(sub_business_id, [])
                if pay_type == "post"
                else prepaid_bills_by_bill_id.get(sub_business_id, [])
            )
            for bill in matched_bills:
                if _billing_mode_kind(bill) != pay_type:
                    continue
                links.setdefault(coupon_id, []).append({
                    "usage_record": _usage_record_identity(record),
                    "affected_bill": _bill_identity(bill),
                    "link_field": link_field,
                    "event_type": "redemption" if change_type == 2 else "return",
                    "target_bill_link_verified": True,
                    "target_bill_redemption_verified": change_type == 2,
                })

    summaries: list[dict[str, Any]] = []
    reasons: list[dict[str, Any]] = []
    for coupon_id in sorted(coupon_ids):
        period_summaries: dict[str, dict[str, Any]] = {}
        for period in periods:
            redeemed_values = amounts.get((coupon_id, period, 2), [])
            returned_values = amounts.get((coupon_id, period, 3), [])
            period_summaries[period] = {
                "redeemed_amount": None if (coupon_id, period, 2) in invalid_amounts else str(exact_sum(redeemed_values)),
                "returned_amount": None if (coupon_id, period, 3) in invalid_amounts else str(exact_sum(returned_values)),
                "redemption_record_count": counts.get((coupon_id, period, 2), 0),
                "return_record_count": counts.get((coupon_id, period, 3), 0),
            }
        coupon_links = sorted(
            links.get(coupon_id, []),
            key=lambda item: json_dumps(item, sort_keys=True),
        )
        summaries.append({
            "coupon": _coupon_identity(coupon_by_id[coupon_id]) if coupon_id in coupon_by_id else {"CouponID": coupon_id},
            "periods": period_summaries,
            "target_bill_links": coupon_links,
        })
        if comparison_period:
            current = decimal_value(period_summaries[analysis_period]["redeemed_amount"])
            previous = decimal_value(period_summaries[comparison_period]["redeemed_amount"])
            if current is not None and previous is not None and current < previous:
                reasons.append({
                    "reason_type": "coupon_redemption_declined",
                    "coupon": _coupon_identity(coupon_by_id[coupon_id]) if coupon_id in coupon_by_id else {"CouponID": coupon_id},
                    "evidence": {
                        "source": "ListCouponUsageRecords",
                        "analysis_period": analysis_period,
                        "analysis_period_redeemed_amount": str(current),
                        "comparison_period": comparison_period,
                        "comparison_period_redeemed_amount": str(previous),
                        "analysis_period_record_count": period_summaries[analysis_period]["redemption_record_count"],
                        "comparison_period_record_count": period_summaries[comparison_period]["redemption_record_count"],
                    },
                    "target_bill_redemption_verified": any(
                        item["target_bill_redemption_verified"]
                        and item["affected_bill"].get("BillPeriod") == analysis_period
                        for item in coupon_links
                    ),
                })
    return summaries, reasons, insufficient


def analyze_coupon_attribution(
    *,
    coupons: Sequence[Mapping[str, Any]],
    bill_details: Sequence[Mapping[str, Any]],
    usage_records: Sequence[Mapping[str, Any]] | None = None,
    usage_record_coupon_ids: Sequence[str] = (),
    analysis_period: str,
    comparison_period: str | None = None,
    candidate_coupon_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """组合代金券库存、实际核销记录和账单明细生成可验证的抵扣证据。"""

    reasons: list[dict[str, Any]] = []
    bill_observations: list[dict[str, Any]] = []
    follow_up_candidates: list[dict[str, Any]] = []
    insufficient: list[dict[str, Any]] = []
    candidates = set(candidate_coupon_ids)
    declines = {}
    comparison_fields = COUPON_COMPARISON_DIMENSIONS
    if comparison_period:
        comparisons, issues = compare_bill_periods(
            bill_details,
            analysis_period=analysis_period,
            comparison_period=comparison_period,
            dimensions=COUPON_COMPARISON_DIMENSIONS,
            optional_dimensions=("Region", "Zone", "Unit"),
            amounts=("CouponAmount", "PayableAmount"),
        )
        insufficient.extend(issues)
        if comparisons:
            comparison_fields = comparisons[0].fields
        for comparison in comparisons:
            if comparison.missing_evidence:
                insufficient.append({
                    "candidate": "coupon_deduction_declined",
                    "affected_bill": comparison.current.identity,
                    "missing_evidence": list(comparison.missing_evidence),
                })
                continue
            decline = _declined(comparison.current.bill(), comparison.previous.bill())
            if decline is not None:
                key = tuple(comparison.current.identity[field] for field in comparison.fields)
                declines[key] = (comparison, {**decline, **comparison.evidence()})
    current_bills = sorted(
        (row for row in bill_details if _text(row, "BillPeriod") == analysis_period),
        key=lambda row: json_dumps(dict(row), sort_keys=True),
    )
    for bill in current_bills:
        group_decline = declines.get(tuple(_text(bill, field) for field in comparison_fields))
        decline = group_decline[1] if group_decline else None
        current_unredeemed = _current_unredeemed(bill)
        if decline is None and current_unredeemed is None:
            continue
        status_evidence = current_unredeemed or decline or {}
        matching_coupon_ids = []
        for coupon in coupons:
            coupon_id = _text(coupon, "CouponID")
            scope = _scope_match(coupon, bill)
            time = _time_match(coupon, bill)
            explicit_candidate = coupon_id in candidates
            if not scope["matched"]:
                if explicit_candidate and current_unredeemed is not None and scope["match_status"] == "not_matched":
                    reasons.append(_reason("coupon_not_applicable", coupon, bill, scope, time, status_evidence))
                elif explicit_candidate and scope["match_status"] == "unknown":
                    insufficient.append({
                        "candidate": "coupon_applicability",
                        "coupon": _coupon_identity(coupon),
                        "affected_bill": _bill_identity(bill),
                        "missing_evidence": ["complete applicability rules for every possible matching scope"],
                    })
                continue
            matching_coupon_ids.append(coupon_id)
            if coupon_id:
                follow_up_candidates.append({
                    "candidate_type": "scope_matching_coupon",
                    "coupon": _coupon_identity(coupon),
                    "affected_bill": _bill_identity(bill),
                    "scope_match": dict(scope),
                    "time_match": dict(time),
                    "follow_up_reason": "代金券与目标消费的已核实适用范围匹配，可继续核查实际核销记录。",
                })
            if time.get("reason") == "not_effective":
                reasons.append(_reason("coupon_not_effective", coupon, bill, scope, time, status_evidence))
                continue
            if time.get("reason") == "expired":
                reasons.append(_reason("coupon_expired", coupon, bill, scope, time, status_evidence))
                continue
            remaining = _decimal(coupon, "RemainingAmount")
            status = _int(coupon, "Status")
            if remaining == 0 and status in {2, 4}:
                reasons.append(_reason("coupon_used_up", coupon, bill, scope, time, status_evidence))
        if not matching_coupon_ids and decline is None:
            insufficient.append({
                "candidate": "coupon_not_redeemed",
                "affected_bill": _bill_identity(bill),
                "observed": decline or current_unredeemed,
                "missing_evidence": ["matching ListCoupons scope or explicit candidate coupon"],
            })
    for comparison, decline in declines.values():
        bill_observations.append({
            "observation_type": "coupon_deduction_declined",
            "affected_bill": comparison.current.identity,
            "evidence": {**decline, "source": "bill_detail.CouponAmount"},
        })

    usage_summaries: list[dict[str, Any]] = []
    if usage_records is not None:
        queried_usage_ids = {
            str(value).strip()
            for value in usage_record_coupon_ids
            if str(value).strip()
        }
        queried_usage_ids.update(
            _text(record, "CouponID")
            for record in usage_records
            if _text(record, "CouponID")
        )
        usage_summaries, usage_reasons, usage_issues = _usage_summaries(
            coupons=coupons,
            usage_records=usage_records,
            bill_details=bill_details,
            analysis_period=analysis_period,
            comparison_period=comparison_period,
            queried_coupon_ids=usage_record_coupon_ids,
        )
        reasons.extend(usage_reasons)
        insufficient.extend(usage_issues)
        candidate_ids = {
            str(item.get("coupon", {}).get("CouponID") or "").strip()
            for item in follow_up_candidates
        }
        for coupon_id in sorted(candidate_ids - queried_usage_ids - {""}):
            insufficient.append({
                "candidate": "coupon_usage_records",
                "coupon_id": coupon_id,
                "missing_evidence": ["complete ListCouponUsageRecords result for this CouponID"],
            })
    elif bill_observations or follow_up_candidates:
        insufficient.append({
            "candidate": "coupon_usage_records",
            "missing_evidence": ["complete ListCouponUsageRecords result for each candidate CouponID"],
        })
    supported = _deduplicate(reasons)
    bill_observations.sort(key=lambda item: json_dumps(item, sort_keys=True))
    follow_up_candidates = _deduplicate(follow_up_candidates)
    insufficient.sort(key=lambda item: json_dumps(item, sort_keys=True))
    return {
        "cause_layer": "secondary_consumption_driver",
        "analysis_period": analysis_period,
        "comparison_period": comparison_period,
        "supported_reasons": supported,
        "bill_observations": bill_observations,
        "follow_up_candidates": follow_up_candidates,
        "coupon_usage_summaries": usage_summaries,
        "insufficient_evidence": insufficient,
        "summary": {
            "coupon_count": len(coupons),
            "bill_detail_count": len(bill_details),
            "coupon_usage_record_count": len(usage_records or []),
            "supported_reason_count": len(supported),
            "insufficient_candidate_count": len(insufficient),
        },
        "contract_limits": [
            "ListCoupons provides current inventory, status and applicability rules",
            "ListCouponUsageRecords provides actual redemption and return events for a required CouponID",
            "bill-detail CouponAmount change and coupon-level redemption change are reported separately",
            "a postpaid usage record links by SubBusinessID=BillDetailId; a prepaid record links by SubBusinessID=BillID on a prepaid bill",
            "BillingMethod and OrderTypeLimit are not mapped without an explicit bill-side contract",
            "AssignedOwnerIDList is hidden from agent output and is not used for matching",
            "coupon evidence does not replace the account-level arrears decision",
        ],
    }
