"""聚合对账与差异下钻的机器可读公开契约。"""

from __future__ import annotations

from typing import Any

from .profiles import profiles_contract


CONTRACT_SECTIONS = ("summary", "preflight", "run", "drill_down", "profiles", "output", "examples")


def _common_arguments() -> list[dict[str, Any]]:
    return [
        {"name": "--left", "required": "one_of_left", "type": "csv_path", "note": "正式对账要求 query bundle；observational 也接受普通 CSV"},
        {"name": "--left-result", "required": "one_of_left", "type": "query_file_result", "properties": ["file", "metadata", "fields"]},
        {"name": "--right", "required": "one_of_right", "type": "csv_path", "note": "正式对账要求 query bundle；observational 也接受普通 CSV"},
        {"name": "--right-result", "required": "one_of_right", "type": "query_file_result", "properties": ["file", "metadata", "fields"]},
        {"name": "--left-metadata", "required": False, "type": "path", "default": "左侧 CSV 同名 .meta.json"},
        {"name": "--right-metadata", "required": False, "type": "path", "default": "右侧 CSV 同名 .meta.json"},
        {"name": "--group-by", "required": False, "type": "comma_separated_fields", "default": "自动识别的 Action Pair 默认维度"},
        {"name": "--metric", "required": False, "type": "repeatable_field", "default": "PayableAmount"},
        {"name": "--filter", "required": False, "type": "repeatable_triplet", "metavar": ["FIELD", "OP", "VALUE"]},
        {"name": "--mode", "required": False, "type": "enum", "values": ["reconciliation", "observational"], "default": "reconciliation"},
    ]


def reconciliation_contract() -> dict[str, Any]:
    return {
        "summary": {
            "purpose": "对两份完整 full 结果或满足受限 provisional 条件的 Billing CSV 先做可比性检查，再按币种使用 Decimal 精确聚合并执行 FULL OUTER JOIN；支持对差异行做守恒式下钻。",
            "commands": ["preflight", "run", "drill-down", "describe"],
            "input_policy": "正式对账接受 query 文件型 result 或 CSV/meta/fields bundle；observational 允许普通 CSV，缺查询证据时只解释文件快照，不验证来源与全量完整性。",
            "modes": {
                "reconciliation": "默认保留正式对账的来源关系、共同维度、请求范围及 coverage 检查。",
                "observational": "没有满足标准对账要求的输入时，按原文件比较；范围、coverage 或来源证据不足只限制解释，必要字段、金额和币种仍须可计算。claim_scope 固定 observational。非标准维度本身不要求切换 mode。",
            },
            "tolerance": "0",
            "pair_selection": {
                "mode": "automatic_from_artifacts",
                "source": "左右查询产物记录的 Action",
                "accepted_arguments": [],
                "note": "relationship 是关系说明，不是输入参数；不要构造 --relationship。",
            },
            "interpretation_boundary": (
                "对账不平只证明给定口径下两侧聚合结果存在差异，不证明业务根因；不要根据计费模式、计费项、Project/Tag "
                "或单侧缺失记录推断业务根因。账单和账单明细是金额对账依据，分账账单仅供归属参考；"
                "分账差异可提示数据时效或分账/归属更新延迟风险，确需追查建议提工单。"
            ),
        },
        "preflight": {
            "purpose": "可选的独立诊断入口，只检查不生成差额；不是 run 的前置调用步骤。",
            "command": "python3 scripts/cost.py reconcile preflight --left-result '<query-result-json>' --right-result '<query-result-json>' [--group-by FIELDS] [--metric FIELD]",
            "arguments": _common_arguments(),
            "checks": [
                "Action Pair 已登记",
                "两侧 coverage 是完整 full 结果，或满足当前期受限 provisional 条件，且 failed_queries 为空",
                "账期、账号、产品、计费模式等业务筛选范围等价",
                "共同聚合维度和金额字段在两侧实际存在",
                "金额字段对应 Currency 存在且非空",
                "自动识别 Project/Tag 双侧分组或过滤，在结果中提示非标准语义，不要求确认或切换 mode",
            ],
            "verdicts": {
                "pass": "允许正式对账",
                "warn": "允许观察性计算，但结论受 provisional、当前月、时效或非标准维度限制",
                "block": "所选模式的必要条件不满足，禁止本次计算；正式对账被阻断不代表观察性比较也不可计算",
            },
            "coverage_policy": {
                "complete": {
                    "requirements": ["requested_scope=full", "requested_scope_fulfilled=true", "is_complete=true", "failed_queries=[]"],
                    "check_status": "pass",
                },
                "provisional": {
                    "requirements": [
                        "requested_scope=full",
                        "requested_scope_fulfilled=true",
                        "is_complete=false",
                        "is_provisional=true",
                        "consistency=current_period_total_drift",
                        "freshness.partial_period=true",
                        "provisional_queries 非空",
                        "每个 provisional query 已达到首次 Total 边界且只因 total_changed 或 rows_exceeded_first_total 停止",
                        "failed_queries=[]",
                    ],
                    "check_status": "warn",
                    "claim_scope": "provisional",
                    "calculation_allowed": True,
                    "final_period_claim_allowed": False,
                },
                "otherwise": {"check_status": "block", "calculation_allowed": False},
                "observational": {"check_status": "warn", "claim_scope": "observational", "note": "只计算实际文件，保留 incomplete、failed_queries 等限制，不声称全量完整。"},
            },
        },
        "run": {
            "preflight_policy": "内部执行 preflight；需要计算结果时可直接调用 run，无需先单独调用 preflight。",
            "command": "python3 scripts/cost.py reconcile run --left <csv> --right <csv> --group-by Product,InstanceNo --metric PayableAmount --out <csv>",
            "arguments": [
                *_common_arguments(),
                {"name": "--out", "required": True, "type": "csv_path"},
                {"name": "--overwrite", "required": False, "type": "boolean_flag", "default": False},
            ],
            "operations": ["preflight", "left_filter_and_aggregation", "right_filter_and_aggregation", "normalized_key_uniqueness", "full_outer_join", "decimal_difference"],
            "filters": "重复 --filter FIELD OP VALUE；同一组 Filter 同时作用于左右两侧。",
            "metrics": "--metric 可重复；省略时使用 PayableAmount。",
            "nonstandard": "Project/Tag 双侧分组或过滤直接计算，无需确认或切换 mode；工具自动返回 NONSTANDARD_DIMENSION warning 和 claim_scope=observational，并在 message 说明同名值不保证语义相同，差额不证明标准对账不一致或多算。默认模式仍检查来源、范围和完整性。",
        },
        "drill_down": {
            "command": "python3 scripts/cost.py reconcile drill-down --from <reconciliation.csv> --row Product=ECS --by InstanceNo --out <csv>",
            "arguments": [
                {"name": "--from", "required": True, "type": "reconciliation_csv"},
                {"name": "--row", "required": True, "type": "repeatable_field_equals_value"},
                {"name": "--by", "required": True, "type": "comma_separated_fields"},
                {"name": "--side", "required": False, "type": "enum", "values": ["both", "left", "right"], "default": "both"},
                {"name": "--out", "required": True, "type": "csv_path"},
                {"name": "--overwrite", "required": False, "type": "boolean_flag", "default": False},
            ],
            "inheritance": "继承父级输入、mode、Action Pair、时间、筛选、指标和 Currency，只增加父行过滤与更细维度；观察性结果不能升级为正式对账。",
            "sides": {
                "both": "继续双侧聚合对账并校验左右金额守恒",
                "left_or_right": "仅展开指定侧；适合在分账侧按 Project/Tag 解释归属",
            },
            "nonstandard": "Project/Tag 双侧下钻直接计算并在 message 返回语义限制，无需确认或切换 mode；单侧展开仅解释指定侧归属，不表示双侧语义一致。",
            "conservation": "子项 left/right 合计必须分别等于父行 left/right；否则下钻结论为 inconclusive。",
        },
        "profiles": dict(profiles_contract()),
        "output": {
            "run_artifacts": ["<out>.csv", "<out_stem>.left.csv", "<out_stem>.right.csv", "<out_stem>.meta.json"],
            "statuses": ["matched", "mismatched", "left_only", "right_only", "inconclusive"],
            "difference_formula": "right_amount - left_amount",
            "observational": "双侧数值可计算时仍输出 difference，但 matched/mismatched 降为 inconclusive；left_only/right_only 保留。在显式 observational 模式下，文件范围内未出现的组金额计为 0 并保留单侧标记；记录中的缺失金额保持未知。",
            "missing_dimension": "空维度写为 __MISSING__；包含空关键字段的结果为 inconclusive。",
            "mismatch_interpretation": [
                "只报告差异、完整性、时效 warning 和产物路径",
                "不把差异归因为某计费模式不参与分账等未经验证的业务规则",
                "ListBillDetail <> ListSplitBillDetail 不平时，账单明细是对账依据，分账账单是归属参考",
                "可提示可能存在数据时效、分账生成延迟或归属更新延迟；确需确认原因建议提工单",
            ],
        },
        "examples": [
            {
                "purpose": "保留两侧原始范围，按 Project 比较文件金额，不认定多算",
                "argv": ["run", "--mode", "observational", "--left", "bill-detail.csv", "--right", "split-detail.csv", "--group-by", "Project", "--metric", "PayableAmount", "--out", "comparison.csv"],
            },
            {
                "purpose": "账单明细与分账明细按商品、实例对账",
                "argv": ["run", "--left", "bill-detail.csv", "--right", "split-detail.csv", "--group-by", "Product,InstanceNo", "--metric", "PayableAmount", "--out", "reconciliation.csv"],
            },
            {
                "purpose": "把 ECS 差异下钻到实例",
                "argv": ["drill-down", "--from", "reconciliation.csv", "--row", "Product=ECS", "--by", "InstanceNo", "--out", "ecs-instances.csv"],
            },
            {
                "purpose": "只在分账侧按项目展开父行金额",
                "argv": ["drill-down", "--from", "ecs-instances.csv", "--row", "InstanceNo=i-1", "--by", "Project", "--side", "right", "--out", "i-1-projects.csv"],
            },
        ],
    }


def describe_reconciliation(section: str = "all") -> dict[str, Any]:
    contract = reconciliation_contract()
    if section == "all":
        return contract
    return {"section": section, section: contract[section]}
