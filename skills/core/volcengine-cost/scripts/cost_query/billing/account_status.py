"""Interpret a current account snapshot without changing its source fields."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Mapping, Sequence

from ..common.errors import BillingQueryError, ErrorCode, ExitCode


BALANCE_COMPONENTS = ("CashBalance", "CreditLimit", "FreezeAmount", "ArrearsBalance")
BALANCE_FIELDS = ("AvailableBalance", *BALANCE_COMPONENTS)
STATUS_LABELS = {
    "in_arrears": "账户欠费",
    "not_in_arrears": "账户不欠费",
    "unknown": "无法确认账户欠费状态",
}


def _exact_sum(values: Sequence[Decimal]) -> Decimal:
    lowest_exponent = min(value.as_tuple().exponent for value in values)
    highest_place = max(value.adjusted() for value in values)
    with localcontext() as context:
        context.prec = max(28, highest_place - lowest_exponent + len(str(len(values))) + 2)
        return sum(values, Decimal(0))


def evaluate_account_status(
    rows: Sequence[Mapping[str, Any]],
    *,
    query_complete: bool = True,
) -> dict[str, Any]:
    """Return account status and an exact balance check for one current snapshot.

    A missing component leaves the formula unchecked, while a complete but
    inconsistent formula overrides the sign-based decision with unknown.
    """
    result: dict[str, Any] = {
        "status": "unknown",
        "label": STATUS_LABELS["unknown"],
        "reason": "incomplete_query",
        "basis": "AvailableBalance",
        "balance_check": {
            "status": "not_checked",
            "missing_fields": [],
            "invalid_fields": [],
        },
        "credit_covered": None,
    }
    if not query_complete:
        return result
    if len(rows) != 1:
        result["reason"] = "empty_snapshot" if not rows else "unexpected_snapshot_count"
        return result

    row = rows[0]
    amounts: dict[str, Decimal] = {}
    check = result["balance_check"]
    for field in BALANCE_FIELDS:
        raw = row.get(field)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            check["missing_fields"].append(field)
            continue
        try:
            # The public contract uses strings, avoiding float precision loss.
            amount = Decimal(raw) if isinstance(raw, str) else None
        except InvalidOperation:
            amount = None
        if amount is None or not amount.is_finite():
            check["invalid_fields"].append(field)
            continue
        amounts[field] = amount

    if len(amounts) == len(BALANCE_FIELDS):
        expected = _exact_sum([
            amounts["CashBalance"], amounts["CreditLimit"],
            amounts["FreezeAmount"].copy_negate(), amounts["ArrearsBalance"].copy_negate(),
        ])
        available = amounts["AvailableBalance"]
        check.update({
            "status": "pass" if available == expected else "fail",
            "expected_available_balance": str(expected),
            "actual_available_balance": row["AvailableBalance"],
            "difference": str(_exact_sum([available, expected.copy_negate()])),
        })
        if check["status"] == "fail":
            result["reason"] = "balance_formula_mismatch"
            return result

    available = amounts.get("AvailableBalance")
    if available is None:
        result["reason"] = (
            "available_balance_missing"
            if "AvailableBalance" in check["missing_fields"]
            else "available_balance_invalid"
        )
        return result

    status = "in_arrears" if available < 0 else "not_in_arrears"
    result.update({
        "status": status,
        "label": STATUS_LABELS[status],
        "reason": "available_balance_negative" if available < 0 else "available_balance_nonnegative",
    })
    credit = amounts.get("CreditLimit")
    if credit is not None:
        result["credit_covered"] = (
            available >= 0 and credit > 0
            and _exact_sum([available, credit.copy_negate()]) < 0
        )
    return result


def account_snapshot_projection(
    rows: Sequence[Mapping[str, Any]],
    *,
    query_complete: bool = True,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Return original fields, deterministic message, and machine evidence."""

    decision = evaluate_account_status(rows, query_complete=query_complete)
    if len(rows) > 1:
        raise BillingQueryError(
            ErrorCode.RESPONSE_INVALID,
            "账户余额接口返回了多个账户快照，响应结构不符合契约",
            ExitCode.QUERY_FAILED,
            {"snapshot_count": len(rows)},
        )
    row = rows[0] if len(rows) == 1 else {}

    check = decision["balance_check"]
    if check["invalid_fields"]:
        raise BillingQueryError(
            ErrorCode.RESPONSE_INVALID,
            "账户余额接口返回了不符合金额契约的字段",
            ExitCode.QUERY_FAILED,
            {"invalid_fields": list(check["invalid_fields"])},
        )
    currency = row.get("Currency")
    unit = f" {currency}" if isinstance(currency, str) and currency.strip() else "（币种未返回）"
    formula = (
        f"CashBalance({row.get('CashBalance')}) + CreditLimit({row.get('CreditLimit')}) "
        f"− FreezeAmount({row.get('FreezeAmount')}) − ArrearsBalance({row.get('ArrearsBalance')})"
    )
    if check["status"] == "fail":
        message = (
            "当前授权账户快照查询成功，但余额关系核验不一致，无法确认当前是否欠费。"
            f"AvailableBalance 实际为 {row['AvailableBalance']}{unit}，"
            f"按 {formula} 计算应为 {check['expected_available_balance']}{unit}；"
            f"实际值减计算值的差额为 {check['difference']}{unit}。"
        )
    else:
        reasons = {
            "incomplete_query": "查询未完整完成",
            "empty_snapshot": "查询未返回账户快照",
            "unexpected_snapshot_count": "查询返回多个账户快照",
            "available_balance_missing": "AvailableBalance 缺失",
            "available_balance_invalid": "AvailableBalance 无法解析为有限金额",
        }
        if decision["status"] == "unknown":
            message = f"当前授权账户快照查询成功，但{reasons[decision['reason']]}，无法确认当前是否欠费。"
        else:
            available = row.get("AvailableBalance")
            message = f"当前授权账户快照查询成功。返回结果显示{decision['label']}"
            if available is not None:
                message += f"，可用余额为 {available}{unit}"
            message += "。"
        if check["status"] == "pass":
            message = message.rstrip("。") + "，余额关系核验一致。"
        gaps = []
        if check["missing_fields"]:
            gaps.append("缺少 " + "、".join(check["missing_fields"]))
        if gaps:
            message += "余额关系未核验：" + "；".join(gaps) + "。"
    if decision["credit_covered"]:
        message += "当前资金缺口由信控额度覆盖。"
    compact_check: dict[str, Any] = {"status": check["status"]}
    if check["status"] == "fail":
        compact_check.update(
            {
                "expected_available_balance": check["expected_available_balance"],
                "actual_available_balance": check["actual_available_balance"],
                "difference": check["difference"],
            }
        )
    elif check["status"] == "not_checked" and check["missing_fields"]:
        compact_check["missing_fields"] = list(check["missing_fields"])
    machine_evidence: dict[str, Any] = {
        "account_status": decision["status"],
        "reason": decision["reason"],
        "balance_check": compact_check,
    }
    if decision["credit_covered"] is True:
        machine_evidence["credit_covered"] = True
    return (
        dict(row),
        message,
        machine_evidence,
    )
