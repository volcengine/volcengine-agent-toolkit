"""Field-level request decision cards for agent contract loading."""

from __future__ import annotations

from typing import Any, Mapping


REQUEST_FIELD_DECISIONS: Mapping[str, Mapping[str, Mapping[str, Any]]] = {
    "ListBillDetail": {
        "GroupPeriod": {
            "values": {
                "0": "账期汇总",
                "1": "按天汇总",
                "2": "明细粒度",
            },
            "choose": [
                {
                    "when": "用户只要账期汇总、产品金额、账号金额或 TopN。",
                    "value": 0,
                },
                {
                    "when": "用户要按天级汇总、日粒度金额或每天费用变化。",
                    "value": 1,
                },
                {
                    "when": "用户要逐条用量、单价、BillID、BillDetailId、审计证据或明细核查。",
                    "value": 2,
                },
            ],
            "related_request_fields": ["GroupTerm"],
            "warning": (
                "GroupPeriod 控制服务端返回粒度，不支持指定返回字段；"
                "响应字段是否保留取决于粒度。"
            ),
        },
        "GroupTerm": {
            "values": {
                "0": "计费项",
                "1": "实例",
                "2": "产品",
                "3": "账号",
            },
            "choose": [
                {
                    "when": "用户要计费项、用量、单价、单价单位，或需要实例号后本地聚合。",
                    "value": 0,
                },
                {
                    "when": "用户只要实例维度结果且不需要用量、单价、单价单位。",
                    "value": 1,
                    "with_request": {"GroupPeriod": 2},
                },
                {
                    "when": "用户只要产品汇总、产品金额或产品 TopN。",
                    "value": 2,
                    "with_request": {"GroupPeriod": 0},
                },
                {
                    "when": "用户只要账号汇总。",
                    "value": 3,
                    "with_request": {"GroupPeriod": 0},
                },
            ],
            "unsupported_combinations": [
                {"GroupPeriod": 2, "GroupTerm": 2, "reason": "账单明细不存在产品+明细粒度。"},
                {"GroupPeriod": 2, "GroupTerm": 3, "reason": "账单明细不存在账号+明细粒度。"},
            ],
            "related_request_fields": ["GroupPeriod"],
        },
    },
    "ListSplitBillDetail": {
        "GroupPeriod": {
            "values": {
                "0": "账期汇总",
                "1": "按天汇总",
                "2": "明细粒度",
            },
            "choose": [
                {
                    "when": "用户只要分账账期汇总。",
                    "value": 0,
                },
                {
                    "when": "用户要按天分账趋势或日粒度分账金额。",
                    "value": 1,
                },
                {
                    "when": "用户要账单/订单 ID、账单明细 ID、分账明细 ID、分拆项 ID 或项目筛选。",
                    "value": 2,
                },
            ],
            "warning": (
                "GroupPeriod 控制服务端返回粒度；汇总粒度下明细标识为空或缺失，"
                "不表示业务数据不存在。"
            ),
        },
    },
}


def request_field_decision(action: str, field: str) -> dict[str, Any] | None:
    """Return a compact decision card for a request field when one is known."""

    action_decisions = REQUEST_FIELD_DECISIONS.get(action)
    if not action_decisions:
        return None
    for name, decision in action_decisions.items():
        if name.casefold() == field.casefold():
            return dict(decision)
    return None
