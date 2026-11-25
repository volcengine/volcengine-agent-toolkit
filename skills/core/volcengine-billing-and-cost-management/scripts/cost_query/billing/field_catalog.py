"""把 Action 响应契约投影为当前 CSV 可用的 Agent 字段语义目录。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..common.fields import (
    CURRENCY_FIELDS,
    FieldType,
    canonical_name,
    declared_type,
    is_aggregatable_metric_field,
    money_currency_field,
)
from ..common.version import VERSION
from .guidance import field_guidance
from .field_grain import evaluate_field_grain
from .exposure import is_public_response_field
from .schema import ACTION_SCHEMAS, ApiElementSpec


FIELD_CATALOG_SCHEMA_VERSION = "1.1"

# 通用语义增强层。接口大表中的同名字段可以直接沉淀到这里。
COMMON_FIELD_SEMANTICS: Mapping[str, Mapping[str, Any]] = {
    "Product": {
        "label": "产品编码",
        "aliases": ["产品", "商品", "产品编码", "商品编码"],
        "role": "dimension",
        "description": "使用的产品或服务编码。",
    },
    "ProductZh": {
        "label": "产品中文名称",
        "aliases": ["产品名称", "商品名称", "产品中文名", "商品中文名"],
        "role": "dimension",
        "description": "使用的产品或服务的中文名称。",
    },
    "OriginalBillAmount": {
        "label": "原价",
        "aliases": ["原价", "原始金额", "优惠前金额", "费用", "金额"],
        "role": "metric",
        "aggregations": ["sum"],
    },
    "PreferentialBillAmount": {
        "label": "优惠金额",
        "aliases": ["优惠金额", "优惠"],
        "role": "metric",
        "aggregations": ["sum"],
    },
    "DiscountBillAmount": {
        "label": "折后金额",
        "aliases": ["折后金额", "折扣后金额", "费用", "金额"],
        "role": "metric",
        "aggregations": ["sum"],
    },
    "PayableAmount": {
        "label": "应付金额",
        "aliases": ["应付金额", "应付费用", "应付", "费用", "金额"],
        "role": "metric",
        "aggregations": ["sum"],
        "notes": ["解释或对账时同时确认账期和结算类型。"],
    },
    "Currency": {
        "label": "币种",
        "aliases": ["币种", "计价币种"],
        "role": "currency",
    },
    "CurrencySettlement": {
        "label": "结算币种",
        "aliases": ["结算币种"],
        "role": "currency",
    },
    "BillPeriod": {
        "label": "账期",
        "aliases": ["账期", "账单月份", "账单月"],
        "role": "dimension",
    },
    "AmortizedMonth": {
        "label": "分摊月",
        "aliases": ["分摊月", "成本月"],
        "role": "dimension",
    },
    "AmortizedDay": {
        "label": "分摊日",
        "aliases": ["分摊日", "成本日"],
        "role": "dimension",
    },
    "PayerID": {
        "label": "Payer 账号 ID",
        "aliases": ["Payer账号", "Payer账号ID", "支付账号", "支付账号ID", "付款账号", "还款账号", "支付结算账号"],
        "role": "dimension",
        "description": "账单还款的对象，也是资源的支付结算账号；财务托管场景下为托管主账号，代销或代售场景下为代销/代售伙伴账号。",
    },
    "OwnerID": {
        "label": "使用账号 ID",
        "aliases": ["使用账号", "使用账号ID", "资源归属账号"],
        "role": "dimension",
    },
    "InstanceNo": {
        "label": "实例 ID",
        "aliases": ["实例", "实例ID", "资源实例"],
        "role": "dimension",
        "description": "账单对应的实例 ID。",
    },
    "InstanceName": {
        "label": "实例名称",
        "aliases": ["实例名称", "资源名称"],
        "role": "dimension",
        "description": "账单对应的实例名称。",
    },
    "Project": {
        "label": "项目编码",
        "aliases": ["项目", "项目编码"],
        "role": "dimension",
    },
    "ProjectDisplayName": {
        "label": "项目名称",
        "aliases": ["项目名称", "项目显示名"],
        "role": "dimension",
    },
    "Region": {
        "label": "地域名称",
        "aliases": ["地域", "地域名称"],
        "role": "dimension",
    },
    "RegionCode": {
        "label": "地域编码",
        "aliases": ["地域编码"],
        "role": "dimension",
    },
    "Element": {
        "label": "计费项名称",
        "aliases": ["计费项", "计费项名称"],
        "role": "dimension",
    },
    "ElementCode": {
        "label": "计费项编码",
        "aliases": ["计费项编码"],
        "role": "dimension",
    },
    "SplitItemID": {
        "label": "分拆项 ID",
        "aliases": ["分拆项", "分拆项ID", "资源粒度ID"],
        "role": "dimension",
    },
    "SplitItemName": {
        "label": "分拆项名称",
        "aliases": ["分拆项名称", "资源粒度名称"],
        "role": "dimension",
    },
    "Tag": {
        "label": "标签",
        "aliases": ["标签", "资源标签"],
        "role": "attribute",
    },
    "BusinessMode": {
        "label": "业务类型",
        "aliases": ["业务类型", "BusinessMode"],
        "role": "dimension",
        "description": "业务类型响应值为中文名称，例如普通业务、财务托管、代销业务、代售业务、财务管理、代买业务。",
    },
    "BusinessModeCode": {
        "label": "业务类型 Code",
        "aliases": ["业务类型Code", "BusinessModeCode"],
        "role": "dimension",
        "description": "业务类型 Code：0 普通业务、1 财务托管、2 代销业务、3 代售业务、4 财务管理、5 代买业务。",
    },
    "BusinessModeName": {
        "label": "业务类型名称",
        "aliases": ["业务类型名称", "BusinessModeName"],
        "role": "dimension",
        "description": "业务类型名称。",
    },
    "OriginalOrderNo": {
        "label": "原订单号",
        "aliases": ["原订单号", "原始订单号"],
        "role": "identifier",
        "description": "退订等场景下的原始订单号。",
    },
    "SettlementType": {
        "label": "结算类型",
        "aliases": ["结算类型", "是否结算", "扣款类型"],
        "role": "dimension",
        "description": "标记账单是否需要结算扣款，响应值为非结算、结算、Quota结算。",
        "notes": [
            "结算账单：用户正常使用产品或服务产生的费用账单，需支付结算。",
            "非结算账单：开通试用实例等场景下无需支付结算。",
            "Quota结算：代销或代售业务场景下，终端客户使用云服务，由伙伴和终端客户线下支付结算。",
        ],
    },
}

# Action 特有语义增强层。用户后续提供的每接口大表可在这里覆盖同名字段。
BILL_RECONCILIATION_FIELD_SEMANTICS: Mapping[str, Mapping[str, Any]] = {
    "PaidAmount": {
        "label": "现金支付金额",
        "aliases": ["现金支付", "现金支付金额", "实付现金", "费用", "金额"],
        "role": "metric",
        "aggregations": ["sum"],
        "notes": ["不代表所有支付方式合计。"],
    },
    "UnpaidAmount": {
        "label": "已出账未还款金额",
        "aliases": ["未还款金额", "已出账未还款", "账单欠款", "费用", "金额"],
        "role": "metric",
        "aggregations": ["sum"],
        "notes": ["不代表账户当前实时欠费状态。"],
    },
    "CreditCarriedAmount": {
        "label": "信控额度金额",
        "aliases": ["信控额度", "信控额度金额", "信控抵扣"],
        "role": "metric",
        "aggregations": ["sum"],
    },
}

ACTION_FIELD_SEMANTICS: Mapping[str, Mapping[str, Mapping[str, Any]]] = {
    "ListFinancialRelation": {
        "MajorAccountID": {"label": "主账号 ID", "role": "identifier", "aggregation_policy": "none"},
        "SubAccountID": {"label": "子账号 ID", "role": "identifier", "aggregation_policy": "none"},
        "RelationID": {"label": "财务关系 ID", "role": "identifier", "aggregation_policy": "none"},
        "Relation": {"label": "财务关系类型", "role": "attribute", "aggregation_policy": "none"},
        "Status": {"label": "财务关系状态", "role": "attribute", "aggregation_policy": "none"},
        "Filiation": {"label": "主子相对视角", "role": "attribute", "aggregation_policy": "none"},
        "UpdateTime": {"label": "关系更新时间", "role": "time", "aggregation_policy": "none"},
    },
    "ListCoupons": {
        "CouponID": {"label": "代金券 ID", "aliases": ["券ID", "代金券"], "role": "identifier"},
        "RemainingAmount": {"label": "代金券余额", "aliases": ["券余额", "余额"], "role": "attribute", "type": "decimal", "aggregation_policy": "none", "notes": ["单位元。"]},
        "TotalAmount": {"label": "代金券面额", "aliases": ["券面额", "面额"], "role": "attribute", "type": "decimal", "aggregation_policy": "none", "notes": ["单位元。"]},
        "AmountLimit": {"label": "使用金额门槛", "aliases": ["使用门槛", "金额门槛"], "role": "attribute", "type": "decimal", "aggregation_policy": "none", "notes": ["单位元。"]},
        "BeginTime": {"label": "生效时间", "aliases": ["生效时间"], "role": "time", "type": "datetime"},
        "ExpiredTime": {"label": "到期时间", "aliases": ["到期时间", "失效时间"], "role": "time", "type": "datetime"},
        "Status": {"label": "代金券状态", "aliases": ["券状态", "状态"], "role": "attribute"},
    },
    "ListCouponUsageRecords": {
        "CouponID": {"label": "代金券 ID", "aliases": ["券ID", "代金券"], "role": "identifier"},
        "ChangeAmount": {"label": "核销变动金额", "aliases": ["核销金额", "抵扣金额", "退回金额"], "role": "metric", "type": "decimal", "force_aggregations": ["sum"], "notes": ["单位元；按 ChangeType 区分抵扣和退回。"]},
        "CreatedTime": {"label": "核销变动时间", "aliases": ["核销时间", "使用时间"], "role": "time", "type": "datetime"},
        "SubBusinessID": {"label": "关联业务单号", "aliases": ["账单明细号", "订单号"], "role": "identifier", "notes": ["PayType=post 时为账单明细号；PayType=pre 时为订单号。"]},
        "BillingCycle": {"label": "核销账期", "aliases": ["账期"], "role": "time"},
        "ChangeType": {"label": "核销变更类型", "aliases": ["变更类型"], "role": "attribute"},
    },
    "ListResourcePackages": {
        "InstanceNo": {"label": "资源包实例 ID", "aliases": ["资源包ID", "资源包实例"], "role": "identifier"},
        "TotalAmount": {"label": "资源包总量", "aliases": ["总量"], "role": "attribute", "type": "decimal", "aggregation_policy": "none", "unit_field": "Unit"},
        "AvailableAmount": {"label": "资源包余量", "aliases": ["余量", "剩余量"], "role": "attribute", "type": "decimal", "aggregation_policy": "none", "unit_field": "Unit"},
        "Unit": {"label": "资源包单位", "aliases": ["单位"], "role": "unit"},
        "EffectiveTime": {"label": "生效时间", "aliases": ["生效时间"], "role": "time", "type": "datetime"},
        "ExpiryTime": {"label": "到期时间", "aliases": ["到期时间", "失效时间"], "role": "time", "type": "datetime"},
        "Status": {"label": "资源包状态", "aliases": ["状态"], "role": "attribute"},
    },
    "ListPackageUsageDetails": {
        "InstanceNo": {"label": "资源包实例 ID", "aliases": ["资源包ID"], "role": "identifier"},
        "DeductionInstanceNo": {"label": "被抵扣实例 ID", "aliases": ["消费实例"], "role": "identifier"},
        "BeforeAmount": {"label": "抵扣前余量", "aliases": ["抵扣前余量"], "role": "attribute", "type": "decimal", "aggregation_policy": "none", "unit_field": "Unit"},
        "DeductionAmount": {"label": "资源包抵扣量", "aliases": ["抵扣量"], "role": "metric", "type": "decimal", "force_aggregations": ["sum"], "unit_field": "Unit"},
        "AfterAmount": {"label": "抵扣后余量", "aliases": ["抵扣后余量"], "role": "attribute", "type": "decimal", "aggregation_policy": "none", "unit_field": "Unit"},
        "DeductionUseAmount": {"label": "被抵扣用量", "aliases": ["抵扣用量"], "role": "metric", "type": "decimal", "force_aggregations": ["sum"], "unit_field": "DeductionInstanceUnit"},
        "Unit": {"label": "资源包单位", "aliases": ["资源包单位"], "role": "unit"},
        "DeductionInstanceUnit": {"label": "被抵扣用量单位", "aliases": ["用量单位"], "role": "unit"},
        "BeginTime": {"label": "消费开始时间", "aliases": ["消费开始时间"], "role": "time", "type": "datetime"},
        "EndTime": {"label": "消费结束时间", "aliases": ["消费结束时间"], "role": "time", "type": "datetime"},
        "DeductionTime": {"label": "抵扣执行时间", "aliases": ["抵扣时间"], "role": "time", "type": "datetime"},
    },
    "QueryBalanceAcct": {
        "AccountID": {
            "label": "账户 ID",
            "aliases": ["账户", "账户ID"],
            "role": "identifier",
        },
        "AvailableBalance": {
            "label": "可用余额",
            "aliases": ["可用余额", "账户可用余额"],
            "role": "attribute",
            "type": "decimal",
            "currency_field": "Currency",
            "aggregation_policy": "none",
        },
        "ArrearsBalance": {
            "label": "欠费金额",
            "aliases": ["欠费金额"],
            "role": "attribute",
            "type": "decimal",
            "currency_field": "Currency",
            "aggregation_policy": "none",
        },
        "CashBalance": {
            "label": "现金余额",
            "aliases": ["现金余额"],
            "role": "attribute",
            "type": "decimal",
            "currency_field": "Currency",
            "aggregation_policy": "none",
        },
        "CreditLimit": {
            "label": "信控额度",
            "aliases": ["信控额度"],
            "role": "attribute",
            "type": "decimal",
            "currency_field": "Currency",
            "aggregation_policy": "none",
        },
        "FreezeAmount": {
            "label": "冻结金额",
            "aliases": ["冻结金额"],
            "role": "attribute",
            "type": "decimal",
            "currency_field": "Currency",
            "aggregation_policy": "none",
        },
        "Currency": {
            "label": "结算币种",
            "aliases": ["币种", "结算币种"],
            "role": "currency",
            "description": "账号当前结算币种。",
        },
    },
    "ListBill": BILL_RECONCILIATION_FIELD_SEMANTICS,
    "ListBillOverviewByProd": BILL_RECONCILIATION_FIELD_SEMANTICS,
    "ListBillOverviewByCategory": BILL_RECONCILIATION_FIELD_SEMANTICS,
    "ListCostAnalysisOpenApi": {
        "ClassifyItem": {
            "label": "分类项",
            "aliases": ["分类项", "分组项", "维度值"],
            "role": "dimension",
            "description": "由请求 ClassifyDimension 决定的分类维度值。",
        },
        "TimeStr": {
            "label": "费用时间",
            "aliases": ["时间", "月份", "日期", "费用时间"],
            "role": "dimension",
            "description": "由请求 TimeGranularity 决定的月或日。",
        },
        "Amount": {
            "label": "费用分析金额",
            "aliases": ["费用", "金额", "成本", "账单金额"],
            "role": "metric",
            "aggregations": ["sum"],
            "description": "费用分析金额，具体账单或成本口径由请求 CostType 决定。",
            "notes": ["解释前读取 metadata.queries[].request_body.CostType。"],
        },
        "Currency": {
            "label": "币种",
            "aliases": ["币种", "计价币种"],
            "role": "currency",
            "description": "ListCostAnalysisOpenApi 不返回币种；按该接口固定 CNY 口径补充。",
            "source": "derived_contract_default",
            "original_response_field": False,
            "notes": ["ListCostAnalysisOpenApi 不返回币种；按该接口固定 CNY 口径补充。"],
        },
    },
    "GetFilterInfoForCostAnalysis": {
        "Catalog": {
            "label": "筛选目录",
            "aliases": ["筛选类型", "目录"],
            "role": "dimension",
            "description": "筛选候选值所属目录。",
        },
        "Value": {
            "label": "筛选候选值",
            "aliases": ["候选值", "筛选值"],
            "role": "attribute",
        },
    },
}

PROVENANCE_SEMANTICS: Mapping[str, Mapping[str, Any]] = {
    "_action": {
        "label": "来源 Action",
        "aliases": ["接口", "来源接口", "Action"],
        "role": "provenance",
        "description": "产生该行数据的 Billing Action。",
    },
    "_query_id": {
        "label": "子查询 ID",
        "aliases": ["查询分片", "子查询", "账期分片"],
        "role": "provenance",
        "description": "多账期或分片查询的来源标识。",
    },
}


def _output_elements(action: str) -> Mapping[str, ApiElementSpec]:
    schema = ACTION_SCHEMAS.get(action)
    if schema is None:
        return {}
    if action == "ListCostAnalysisOpenApi":
        cost_data = schema.response_elements_by_name.get("CostData")
        if cost_data is None:
            return {}
        result = {child.name: child for child in cost_data.children if child.name != "Costs"}
        costs = cost_data.children_by_name.get("Costs")
        if costs is not None:
            result.update(costs.children_by_name)
        return result
    if action == "GetFilterInfoForCostAnalysis":
        result: dict[str, ApiElementSpec] = {}
        for element in schema.response_elements:
            result.update(element.children_by_name)
        return result
    list_element = schema.response_elements_by_name.get("List")
    if list_element is not None:
        nested = list_element.children_by_name.get("List")
        return nested.children_by_name if nested is not None else list_element.children_by_name
    return schema.response_elements_by_name


def output_field_names(action: str) -> tuple[str, ...]:
    """返回 query_billing 扁平结果可能使用的公开业务字段名。"""

    return tuple(_output_elements(action))


def _field_type(column: str, element: ApiElementSpec | None) -> str:
    registered = declared_type(column)
    if registered is not None:
        return registered.value
    if element is not None:
        if element.type_name in {"int32", "int64"}:
            return FieldType.INTEGER.value
        if element.type_name in {"float", "double"}:
            return FieldType.DECIMAL.value
        if element.type_name == "object":
            return FieldType.JSON.value
        return element.type_name
    return "unknown"


def _infer_role(column: str, field_type: str) -> str:
    canonical = canonical_name(column)
    if canonical in CURRENCY_FIELDS:
        return "currency"
    lowered = column.casefold()
    if field_type in {"decimal", "string"} and ("amount" in lowered or money_currency_field(column) is not None):
        return "metric"
    if lowered.endswith("id") or lowered.endswith("no"):
        return "identifier"
    if any(token in lowered for token in ("period", "date", "day", "month", "time")):
        return "dimension"
    return "attribute"


def _fallback_label(column: str, description: str) -> str:
    if description:
        first = description.replace("；", "。").split("。", 1)[0].strip()
        if 0 < len(first) <= 24:
            return first
    return column


def _aggregations(
    canonical: str,
    field_type: str,
    role: str,
    semantics: Mapping[str, Any],
) -> list[str]:
    if semantics.get("aggregation_policy") == "none":
        return []
    if "force_aggregations" in semantics:
        return [str(item) for item in semantics["force_aggregations"]]
    if role == "metric" and is_aggregatable_metric_field(canonical):
        return ["sum", "avg", "count"]
    return ["count"]


def _known_field(
    action: str,
    column: str,
    element: ApiElementSpec | None,
) -> dict[str, Any]:
    canonical = canonical_name(column)
    common_semantics = next(
        (value for name, value in COMMON_FIELD_SEMANTICS.items() if canonical_name(name) == canonical),
        {},
    )
    action_semantics = next(
        (value for name, value in ACTION_FIELD_SEMANTICS.get(action, {}).items() if canonical_name(name) == canonical),
        {},
    )
    semantics = {
        **common_semantics,
        **action_semantics,
    }
    guidance: Mapping[str, Any] = {}
    if element is not None:
        guidance = field_guidance(element, column, "response", action_name=action)
    description = str(semantics.get("description") or guidance.get("summary") or (element.description if element else "")).strip()
    field_type = str(semantics.get("type") or _field_type(column, element))
    role = str(semantics.get("role") or _infer_role(column, field_type))
    if role == "metric" and field_type == FieldType.STRING.value:
        field_type = FieldType.DECIMAL.value
    label = str(semantics.get("label") or _fallback_label(column, description))
    aliases = list(dict.fromkeys(str(item) for item in semantics.get("aliases", []) if str(item)))
    if label != column and label not in aliases:
        aliases.insert(0, label)
    result: dict[str, Any] = {
        "field": column,
        "contract_known": element is not None or bool(semantics),
        "label": label,
        "aliases": aliases,
        "role": role,
        "type": field_type,
        "description": description,
        "aggregations": _aggregations(canonical, field_type, role, semantics),
        "currency_field": semantics.get("currency_field"),
        "unit_field": semantics.get("unit_field"),
        "notes": list(dict.fromkeys([
            *(str(item) for item in semantics.get("notes", [])),
            *(str(item) for item in guidance.get("notes", [])),
        ])),
    }
    for key in ("source", "original_response_field"):
        if key in semantics:
            result[key] = semantics[key]
    for key in ("accepted_values", "value_for_csv_filter"):
        if key in guidance:
            result[key] = guidance[key]
    return result


def _available_currency_columns(columns: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for column in columns:
        canonical = canonical_name(column)
        if canonical in CURRENCY_FIELDS and canonical not in result:
            result[canonical] = column
    return result


def build_field_catalog(
    *,
    action: str | None,
    columns: Sequence[str],
    source_csv: Path,
    source_metadata: Path | None,
    request_bodies: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    elements = _output_elements(action) if action else {}
    elements_by_canonical = {canonical_name(name): element for name, element in elements.items()}
    available_currency = _available_currency_columns(columns)
    fields: list[dict[str, Any]] = []
    unknown_fields: list[str] = []
    for column in columns:
        if not is_public_response_field(action, column):
            continue
        if column in PROVENANCE_SEMANTICS:
            semantics = PROVENANCE_SEMANTICS[column]
            field = {
                "field": column,
                "contract_known": True,
                "label": semantics["label"],
                "aliases": list(semantics["aliases"]),
                "role": semantics["role"],
                "type": "string",
                "description": semantics["description"],
                "aggregations": [],
                "currency_field": None,
                "notes": [],
            }
        else:
            field = _known_field(
                action or "",
                column,
                elements.get(column) or elements_by_canonical.get(canonical_name(column)),
            )
            if not field["contract_known"]:
                field.update({
                    "label": column,
                    "aliases": [],
                    "role": "unknown",
                    "type": "unknown",
                    "description": "",
                    "aggregations": [],
                    "currency_field": None,
                    "notes": [],
                })
                unknown_fields.append(column)
        if field["role"] == "metric":
            currency_canonical = money_currency_field(column)
            field["currency_field"] = available_currency.get(currency_canonical) if currency_canonical else None
        grain = evaluate_field_grain(action or "", column, request_bodies)
        if grain:
            field["grain_availability"] = grain
            if grain["status"] == "not_preserved":
                field["notes"] = list(dict.fromkeys([
                    *field["notes"],
                    grain["unavailable_meaning"],
                ]))
        fields.append(field)
    return {
        "schema_version": FIELD_CATALOG_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_version": VERSION,
        "source_action": action,
        "source_csv": str(source_csv.resolve()),
        "source_metadata": str(source_metadata.resolve()) if source_metadata else None,
        "field_count": len(fields),
        "unknown_field_count": len(unknown_fields),
        "unknown_fields": unknown_fields,
        "fields": fields,
    }
