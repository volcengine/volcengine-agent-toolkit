"""面向 Agent 的 Billing 字段暴露策略。"""

from __future__ import annotations

from typing import Any, Mapping

from ..common.fields import canonical_name


BILL_RECONCILIATION_ACTIONS = frozenset(
    {
        "ListBill",
        "ListBillOverviewByProd",
        "ListBillOverviewByCategory",
    }
)
RECONCILIATION_FIELD_ROOTS = frozenset(
    {"paid_amount", "unpaid_amount", "credit_carried_amount"}
)
PRIVATE_RESPONSE_FIELDS = {
    "ListFinancialRelation": frozenset({"AuthInfo"}),
    "QueryBalanceAcct": frozenset({"AccountID"}),
    "ListResourcePackages": frozenset({"OwnerID", "UserName", "SubjectNo"}),
    "ListPackageUsageDetails": frozenset(
        {"OwnerID", "UserName", "DeductionAccountID", "DeductionUserName", "SubjectNo"}
    ),
    "ListCoupons": frozenset({"AccountID", "AssignedOwnerIDList"}),
    "ListCouponUsageRecords": frozenset({"AccountID", "UserAccountID"}),
}


def is_reconciliation_field(field_name: str) -> bool:
    """识别核销字段及 Daily/Now/Before/Unamortized 等派生字段族。"""

    canonical = canonical_name(field_name)
    return any(
        canonical == root or canonical.endswith(f"_{root}")
        for root in RECONCILIATION_FIELD_ROOTS
    )


def is_public_response_field(action: str | None, field_name: str) -> bool:
    if field_name in PRIVATE_RESPONSE_FIELDS.get(action or "", frozenset()):
        return False
    return action in BILL_RECONCILIATION_ACTIONS or not is_reconciliation_field(field_name)


def public_row(action: str | None, row: Mapping[str, Any]) -> dict[str, Any]:
    """剔除目标 Action 不再公开的响应字段，不产生 warning。"""

    return {
        key: value
        for key, value in row.items()
        if is_public_response_field(action, key)
    }
