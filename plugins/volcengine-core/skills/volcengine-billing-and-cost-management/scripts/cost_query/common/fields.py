"""费用分析使用的字段规范名、类型和金额语义。"""

from __future__ import annotations

import re
from enum import Enum
from typing import Mapping


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    PERIOD = "period"
    JSON = "json"


def canonical_name(value: str) -> str:
    """把 Go/Python 常见字段风格统一为 snake_case。"""

    value = value.strip().replace("-", "_").replace(" ", "_")
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value.lower()


FIELD_TYPES = {
    # keys and dimensions
    "bill_id": FieldType.STRING,
    "bill_detail_id": FieldType.STRING,
    "split_bill_detail_id": FieldType.STRING,
    "cost_id": FieldType.STRING,
    "bill_period": FieldType.PERIOD,
    "expense_date": FieldType.DATE,
    "amortized_month": FieldType.PERIOD,
    "amortized_day": FieldType.DATE,
    "product": FieldType.STRING,
    "product_zh": FieldType.STRING,
    "instance_no": FieldType.STRING,
    "instance_name": FieldType.STRING,
    "element": FieldType.STRING,
    "element_code": FieldType.STRING,
    "project": FieldType.STRING,
    "project_display_name": FieldType.STRING,
    "region": FieldType.STRING,
    "region_code": FieldType.STRING,
    "zone": FieldType.STRING,
    "zone_code": FieldType.STRING,
    "billing_mode": FieldType.STRING,
    "bill_category": FieldType.STRING,
    "pay_status": FieldType.STRING,
    "amortized_type": FieldType.STRING,
    "business_mode": FieldType.STRING,
    "owner_id": FieldType.STRING,
    "payer_id": FieldType.STRING,
    "subject_name": FieldType.STRING,
    "split_item_id": FieldType.STRING,
    "split_item_name": FieldType.STRING,
    "tag": FieldType.JSON,
    "tag_kv": FieldType.JSON,
    "currency": FieldType.STRING,
    "currency_settlement": FieldType.STRING,
    # monetary values
    "original_amount": FieldType.DECIMAL,
    "preferential_amount": FieldType.DECIMAL,
    "discount_amount": FieldType.DECIMAL,
    "coupon_amount": FieldType.DECIMAL,
    "saving_plan_original_amount": FieldType.DECIMAL,
    "round_amount": FieldType.DECIMAL,
    "payable_amount": FieldType.DECIMAL,
    "paid_amount": FieldType.DECIMAL,
    "credit_carried_amount": FieldType.DECIMAL,
    "unpaid_amount": FieldType.DECIMAL,
    "daily_amortized_original_amount": FieldType.DECIMAL,
    "daily_amortized_preferential_amount": FieldType.DECIMAL,
    "daily_amortized_discount_amount": FieldType.DECIMAL,
    "daily_amortized_payable_amount": FieldType.DECIMAL,
    "daily_amortized_paid_amount": FieldType.DECIMAL,
    "now_amortized_payable_amount": FieldType.DECIMAL,
    "before_amortized_payable_amount": FieldType.DECIMAL,
    "unamortized_payable_amount": FieldType.DECIMAL,
    # non-money numeric values
    "split_item_amount": FieldType.DECIMAL,
    "split_item_ratio": FieldType.DECIMAL,
    "amount": FieldType.DECIMAL,
}

CURRENCY_FIELDS = ("currency", "currency_settlement")

# 明确经过公开 Billing 响应契约审核的金额字段及其币种字段。定价币种金额使用
# Currency；Settle 口径金额使用 CurrencySettlement。不要用后缀猜测新增金额字段。
AMOUNT_CURRENCY_FIELDS: Mapping[str, str] = {
    "amount": "currency",
    "before_amortized_coupon_amount": "currency",
    "before_amortized_discount_bill_amount": "currency",
    "before_amortized_original_bill_amount": "currency",
    "before_amortized_payable_amount": "currency",
    "before_amortized_point_deduct_amount": "currency",
    "before_amortized_posttax_amount": "currency",
    "before_amortized_pre_tax_payable_amount": "currency",
    "before_amortized_pre_tax_real_value": "currency",
    "before_amortized_preferential_bill_amount": "currency",
    "before_amortized_pretax_amount": "currency",
    "before_amortized_real_value": "currency",
    "before_amortized_round_amount": "currency",
    "before_amortized_saving_plan_original_amount": "currency",
    "before_amortized_settle_payable_amount": "currency_settlement",
    "before_amortized_settle_posttax_amount": "currency_settlement",
    "before_amortized_settle_pre_tax_payable_amount": "currency_settlement",
    "before_amortized_settle_pre_tax_real_value": "currency_settlement",
    "before_amortized_settle_pretax_amount": "currency_settlement",
    "before_amortized_settle_real_value": "currency_settlement",
    "before_amortized_settle_tax_amount": "currency_settlement",
    "before_amortized_tax_amount": "currency",
    "coupon_amount": "currency",
    "coupon_deduction_amount": "currency",
    "credit_carried_amount": "currency",
    "daily_amortized_coupon_amount": "currency",
    "daily_amortized_discount_bill_amount": "currency",
    "daily_amortized_original_amount": "currency",
    "daily_amortized_original_bill_amount": "currency",
    "daily_amortized_paid_amount": "currency",
    "daily_amortized_payable_amount": "currency",
    "daily_amortized_point_deduct_amount": "currency",
    "daily_amortized_posttax_amount": "currency",
    "daily_amortized_pre_tax_payable_amount": "currency",
    "daily_amortized_pre_tax_real_value": "currency",
    "daily_amortized_preferential_amount": "currency",
    "daily_amortized_preferential_bill_amount": "currency",
    "daily_amortized_pretax_amount": "currency",
    "daily_amortized_real_value": "currency",
    "daily_amortized_round_amount": "currency",
    "daily_amortized_saving_plan_original_amount": "currency",
    "daily_amortized_settle_payable_amount": "currency_settlement",
    "daily_amortized_settle_posttax_amount": "currency_settlement",
    "daily_amortized_settle_pre_tax_payable_amount": "currency_settlement",
    "daily_amortized_settle_pre_tax_real_value": "currency_settlement",
    "daily_amortized_settle_pretax_amount": "currency_settlement",
    "daily_amortized_settle_real_value": "currency_settlement",
    "daily_amortized_settle_tax_amount": "currency_settlement",
    "daily_amortized_tax_amount": "currency",
    "discount_amount": "currency",
    "discount_bill_amount": "currency",
    "now_amortized_coupon_amount": "currency",
    "now_amortized_discount_bill_amount": "currency",
    "now_amortized_original_bill_amount": "currency",
    "now_amortized_paid_amount": "currency",
    "now_amortized_payable_amount": "currency",
    "now_amortized_point_deduct_amount": "currency",
    "now_amortized_posttax_amount": "currency",
    "now_amortized_pre_tax_payable_amount": "currency",
    "now_amortized_pre_tax_real_value": "currency",
    "now_amortized_preferential_bill_amount": "currency",
    "now_amortized_pretax_amount": "currency",
    "now_amortized_real_value": "currency",
    "now_amortized_round_amount": "currency",
    "now_amortized_saving_plan_original_amount": "currency",
    "now_amortized_settle_payable_amount": "currency_settlement",
    "now_amortized_settle_posttax_amount": "currency_settlement",
    "now_amortized_settle_pre_tax_payable_amount": "currency_settlement",
    "now_amortized_settle_pre_tax_real_value": "currency_settlement",
    "now_amortized_settle_pretax_amount": "currency_settlement",
    "now_amortized_settle_real_value": "currency_settlement",
    "now_amortized_settle_tax_amount": "currency_settlement",
    "now_amortized_tax_amount": "currency",
    "original_amount": "currency",
    "original_bill_amount": "currency",
    "paid_amount": "currency",
    "payable_amount": "currency",
    "point_deduct_amount": "currency",
    "posttax_amount": "currency",
    "pre_tax_payable_amount": "currency",
    "pre_tax_real_value": "currency",
    "preferential_amount": "currency",
    "preferential_bill_amount": "currency",
    "pretax_amount": "currency",
    "pretax_real_value": "currency",
    "real_value": "currency",
    "round_amount": "currency",
    "round_bill_amount": "currency",
    "saving_plan_deduction_discount_amount": "currency",
    "saving_plan_deduction_discount_total_amount": "currency",
    "saving_plan_original_amount": "currency",
    "settle_payable_amount": "currency_settlement",
    "settle_posttax_amount": "currency_settlement",
    "settle_pre_tax_payable_amount": "currency_settlement",
    "settle_pre_tax_real_value": "currency_settlement",
    "settle_pretax_amount": "currency_settlement",
    "settle_pretax_real_value": "currency_settlement",
    "settle_real_value": "currency_settlement",
    "settle_tax": "currency_settlement",
    "settle_tax_amount": "currency_settlement",
    "tax": "currency",
    "tax_amount": "currency",
    "un_amortized_saving_plan_original_amount": "currency",
    "unamortized_coupon_amount": "currency",
    "unamortized_discount_bill_amount": "currency",
    "unamortized_original_bill_amount": "currency",
    "unamortized_payable_amount": "currency",
    "unamortized_point_deduct_amount": "currency",
    "unamortized_posttax_amount": "currency",
    "unamortized_pre_tax_payable_amount": "currency",
    "unamortized_pre_tax_real_value": "currency",
    "unamortized_preferential_bill_amount": "currency",
    "unamortized_pretax_amount": "currency",
    "unamortized_real_value": "currency",
    "unamortized_round_amount": "currency",
    "unamortized_settle_payable_amount": "currency_settlement",
    "unamortized_settle_posttax_amount": "currency_settlement",
    "unamortized_settle_pre_tax_payable_amount": "currency_settlement",
    "unamortized_settle_pre_tax_real_value": "currency_settlement",
    "unamortized_settle_pretax_amount": "currency_settlement",
    "unamortized_settle_real_value": "currency_settlement",
    "unamortized_settle_tax_amount": "currency_settlement",
    "unamortized_tax_amount": "currency",
    "unpaid_amount": "currency",
}

MONEY_FIELDS = frozenset(AMOUNT_CURRENCY_FIELDS)


def is_settlement_money_field(column: str) -> bool:
    canonical = canonical_name(column)
    return AMOUNT_CURRENCY_FIELDS.get(canonical) == "currency_settlement"


def money_currency_field(column: str) -> str | None:
    return AMOUNT_CURRENCY_FIELDS.get(canonical_name(column))


def declared_type(column: str) -> FieldType | None:
    canonical = canonical_name(column)
    registered = FIELD_TYPES.get(canonical)
    if registered is not None:
        return registered
    if canonical in AMOUNT_CURRENCY_FIELDS:
        return FieldType.DECIMAL
    return None


def is_money_field(column: str) -> bool:
    """判断字段是否是必须按币种隔离的金额，而不是普通数值。"""

    canonical = canonical_name(column)
    return canonical in MONEY_FIELDS


def is_aggregatable_metric_field(column: str) -> bool:
    """判断字段是否可用于 SUM/AVG 或期间差额等金额聚合。"""

    return is_money_field(column)
