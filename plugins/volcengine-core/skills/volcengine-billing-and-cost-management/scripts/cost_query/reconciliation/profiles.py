"""允许对账的数据源关系、共同维度与金额目录。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..common.fields import canonical_name


RECONCILIATION_METRICS = (
    "PayableAmount",
    "OriginalBillAmount",
    "SavingPlanOriginalAmount",
    "PreferentialBillAmount",
    "DiscountBillAmount",
)
RECONCILIATION_METRIC_CANONICAL = frozenset(canonical_name(item) for item in RECONCILIATION_METRICS)
NONSTANDARD_DIMENSIONS = frozenset({"project", "tag"})


@dataclass(frozen=True)
class PairProfile:
    name: str
    actions: frozenset[str]
    default_group_by: tuple[str, ...]
    standard_dimensions: frozenset[str]
    relationship: str

    def supports(self, left_action: str, right_action: str) -> bool:
        return frozenset((left_action, right_action)) == self.actions

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "actions": sorted(self.actions),
            "description": self.relationship,
            "default_group_by": list(self.default_group_by),
            "standard_dimensions": sorted(self.standard_dimensions),
            "nonstandard_dimensions": sorted(NONSTANDARD_DIMENSIONS),
            "metrics": list(RECONCILIATION_METRICS),
        }


PAIR_PROFILES = (
    PairProfile(
        name="product_overview_to_bill",
        actions=frozenset(("ListBillOverviewByProd", "ListBill")),
        default_group_by=("Product",),
        standard_dimensions=frozenset(
            canonical_name(item)
            for item in ("Product", "PayerID", "OwnerID", "BillingMode", "SettlementType", "Currency")
        ),
        relationship="产品总览与账单流水按共同出账维度聚合比较",
    ),
    PairProfile(
        name="bill_to_bill_detail",
        actions=frozenset(("ListBill", "ListBillDetail")),
        default_group_by=("BillID",),
        standard_dimensions=frozenset(
            canonical_name(item)
            for item in ("BillID", "Product", "PayerID", "OwnerID", "BillingMode", "SettlementType", "Currency")
        ),
        relationship="一条账单对应多条账单明细，比较前按共同维度分别聚合",
    ),
    PairProfile(
        name="bill_detail_to_split_detail",
        actions=frozenset(("ListBillDetail", "ListSplitBillDetail")),
        default_group_by=("Product", "InstanceNo"),
        standard_dimensions=frozenset(
            canonical_name(item)
            for item in (
                "BillID",
                "BillDetailId",
                "Product",
                "PayerID",
                "OwnerID",
                "BillingMode",
                "SettlementType",
                "Currency",
                "InstanceNo",
                "Element",
            )
        ),
        relationship="一条账单明细对应多条分账明细，比较前按共同维度分别聚合",
    ),
)


def find_profile(left_action: str, right_action: str) -> PairProfile | None:
    return next(
        (profile for profile in PAIR_PROFILES if profile.supports(left_action, right_action)),
        None,
    )


def profiles_contract() -> Mapping[str, object]:
    return {
        "selection": {
            "mode": "automatic_from_artifacts",
            "source": "左右查询产物记录的 Action",
            "accepted_arguments": [],
            "note": "Agent 不传 relationship 或 profile；未登记的 Action Pair 在正式对账模式阻断，observational 只解释指定文件。",
        },
        "pairs": [profile.to_dict() for profile in PAIR_PROFILES],
        "metric_rule": "五个金额字段可加和，使用 Decimal，tolerance 固定为 0。",
        "currency_rule": "金额对账强制把对应 Currency 加入有效 Join Key。",
        "project_tag_rule": (
            "ListBillDetail 与 ListSplitBillDetail 的 Project/Tag 来源语义不同；"
            "双侧比较必须显式允许并降级为 observational，推荐先按实例等共同维度对账，"
            "再在分账侧展开 Project/Tag。"
        ),
    }
