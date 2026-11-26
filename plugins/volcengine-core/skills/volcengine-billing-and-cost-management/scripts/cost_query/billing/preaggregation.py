"""ListBillDetail 预聚合的紧凑组参提示和错误恢复映射。"""

from __future__ import annotations

from typing import Any, Mapping


LIST_BILL_DETAIL_COMBINATIONS = (
    {
        "when": "需要计费项明细、逐条用量或单价、BillDetailId、Project 筛选或分账关联",
        "request_patch": {"GroupPeriod": 2, "GroupTerm": 0},
        "preservation_priority": ["Element", "Count", "Price", "BillDetailId", "Project"],
        "tradeoff": "数据量较大；需要汇总时在完整明细上按需汇总或处理。",
    },
    {
        "when": "只需要实例级明细，且不需要用量、单价或单价单位",
        "request_patch": {"GroupPeriod": 2, "GroupTerm": 1},
        "preservation_priority": ["InstanceNo", "InstanceName"],
        "may_lose": ["Count", "Price", "PriceUnit", "BillDetailId"],
        "tradeoff": "需要用量、单价、账单明细 ID 或项目筛选时改用计费项明细；需要归属时比较分账。",
    },
    {
        "when": "只需要产品账期汇总、产品金额或产品 TopN",
        "request_patch": {"GroupPeriod": 0, "GroupTerm": 2},
        "preservation_priority": ["Product", "ProductZh", "PayableAmount"],
        "may_lose": ["InstanceNo", "BillDetailId", "明细用量和单价证据"],
        "tradeoff": "服务端预聚合数据量较小，但不适合明细核查或血缘关联。",
    },
    {
        "when": "只需要账号账期汇总",
        "request_patch": {"GroupPeriod": 0, "GroupTerm": 3},
        "preservation_priority": ["PayerID", "OwnerID", "PayableAmount"],
        "may_lose": ["Product", "InstanceNo", "BillDetailId", "明细用量和单价证据"],
        "tradeoff": "服务端预聚合数据量较小，但不保留产品和明细证据。",
    },
)


LIST_BILL_DETAIL_CONCEPTS: Mapping[str, str] = {
    "用量": "Count",
    "单价": "Price",
    "用量单位": "Unit",
    "单价单位": "PriceUnit",
    "产品名称": "ProductZh",
    "实例ID": "InstanceNo",
    "计费项": "Element",
    "账单明细ID": "BillDetailId",
    "应付金额": "PayableAmount",
    "项目": "Project",
}


# 仅用于把明显误放进 body 的响应列转换成可恢复提示；不会自动改写请求。
LIST_BILL_DETAIL_RESPONSE_FIELD_HINTS: Mapping[str, Mapping[str, str]] = {
    "Usage": {"concept": "用量", "response_field": "Count"},
    "Measure": {"concept": "用量", "response_field": "Count"},
    "Count": {"concept": "用量", "response_field": "Count"},
    "UnitPrice": {"concept": "单价", "response_field": "Price"},
    "Price": {"concept": "单价", "response_field": "Price"},
    "UsageUnit": {"concept": "用量单位", "response_field": "Unit"},
    "Unit": {"concept": "用量单位", "response_field": "Unit"},
    "UnitPriceUnit": {"concept": "单价单位", "response_field": "PriceUnit"},
    "PriceUnit": {"concept": "单价单位", "response_field": "PriceUnit"},
    "ProductName": {"concept": "产品名称", "response_field": "ProductZh"},
    "ProductZh": {"concept": "产品名称", "response_field": "ProductZh"},
    "DetailID": {"concept": "账单明细ID", "response_field": "BillDetailId"},
    "BillDetailID": {"concept": "账单明细ID", "response_field": "BillDetailId"},
    "BillDetailId": {"concept": "账单明细ID", "response_field": "BillDetailId"},
    "PayableAmount": {"concept": "应付金额", "response_field": "PayableAmount"},
    "Element": {"concept": "计费项", "response_field": "Element"},
}


def list_bill_detail_preaggregation_guidance() -> dict[str, Any]:
    return {
        "kind": "advisory",
        "request_projection_supported": False,
        "field_semantics": "retention_guidance_not_response_guarantee",
        "body_rule": "body 只能包含 request contract 声明的请求、筛选和粒度参数；不要放期望返回字段。",
        "recommended_combinations": [dict(item) for item in LIST_BILL_DETAIL_COMBINATIONS],
        "time_modifier": {
            "when": "用户需要按天汇总",
            "request_patch": {"GroupPeriod": 1},
            "group_term_rule": "按计费项/实例/产品/账号目标选择 GroupTerm=0/1/2/3。",
        },
        "common_response_fields": dict(LIST_BILL_DETAIL_CONCEPTS),
        "decision_rules": [
            "只需要产品或账号金额汇总时，优先对应服务端汇总粒度。",
            "需要 BillDetailId、逐条审计证据或项目筛选时，使用计费项明细，再按用户目标在本地按需汇总或处理。",
            "只需要用量、单价或单价单位时选择 GroupTerm=0，并按账期、天或明细目标另选 GroupPeriod。",
            "用户表达不在 common_response_fields 或涉及长尾字段时，按需查询 response contract，不猜字段名。",
            "查询后以实际 fields artifact 为准；本 guidance 不保证服务端每行一定返回非空字段。",
        ],
    }
