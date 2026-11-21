"""供 Agent 按需加载的 Billing Query 执行契约。"""

from __future__ import annotations

from typing import Any

from ..common.errors import ErrorCode, ExitCode
from .validation import ALLOWED_ACTIONS
from .fetch import NON_PAGED_ACTIONS


CONTRACT_SECTIONS = (
    "summary",
    "input",
    "pagination",
    "multi_period",
    "retry",
    "output",
    "errors",
    "examples",
)


def query_contract() -> dict[str, Any]:
    return {
        "summary": {
            "purpose": "校验并执行公开只读 ve billing 请求，处理 page/full、多账期和有限重试，并统一返回 status/message/result；机器证据保留在 _meta 或 sidecar。",
            "read_only": True,
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "contract_usage": "复用已确认且仍适用的 Action 与请求契约；无法确定 Action 时才读取 schema --list-actions，选定 Action 后若缺少请求契约则通过 action_contract_command 一次加载；本契约只描述查询执行方式。",
            "action_contract_command": "python3 scripts/cost.py schema --action <Action> --section request --include-guidance",
            "agent_reference": "通用接口选择、查询执行、结果解释和分析原则见 references/cost-query.md；费用变化与归因见 references/cost-change-analysis.md；账户欠费、已出账未还款构成和欠费原因见 references/arrears-analysis.md；财务托管、主子账号关系与付费归属见 references/financial-relations.md。",
            "freshness_policy": "费用分析在账单明细出具后 T+2 日更新；用户要求最新数据时不得选择 ListCostAnalysisOpenApi。",
            "reconciliation_field_policy": "PaidAmount、UnpaidAmount、CreditCarriedAmount 在 BILL 三 Action（ListBill、ListBillOverviewByProd、ListBillOverviewByCategory）暴露；账单明细、分账、成本和费用分析的相关字段族屏蔽。",
        },
        "input": {
            "arguments": [
                {"name": "--action", "required": True, "type": "enum", "values": sorted(ALLOWED_ACTIONS)},
                {"name": "--body", "required_group": "request_body", "type": "json_object_string"},
                {"name": "--body-file", "required_group": "request_body", "type": "utf8_json_object_path"},
                {"name": "--period", "required": False, "type": "repeatable_yyyy_mm"},
                {"name": "--period-field", "required": False, "type": "enum", "values": ["BillPeriod", "AmortizedMonth"]},
                {
                    "name": "--out",
                    "required": False,
                    "type": "csv_path",
                    "default_behavior": "省略时按完整 stdout envelope 的 64 KiB 阈值直接返回 result 或自动写入临时 CSV；提供时 result.file 使用指定路径。",
                    "constraints": {"extension": ".csv"},
                },
                {
                    "name": "--overwrite",
                    "required": False,
                    "type": "boolean_flag",
                    "default": False,
                    "allowed_when": "已确认主文件及其 metadata/fields 旁路产物均属于本轮任务并允许替换",
                    "not_a_default_retry": True,
                },
                {"name": "--pagination", "required": False, "required_when": "目标 Action 是分页 Action", "type": "enum", "values": ["page", "full"]},
                {"name": "--page-offset", "required": False, "type": "non_negative_integer", "applies_to": "Limit/Offset 分页 Action；NextToken Action 在 body 提供 NextToken"},
                {"name": "--page-size", "required": False, "type": "integer", "minimum": 1, "maximum": 1000, "maps_to": "Limit 或 MaxResults；多数账单 Action 的 Limit 上限 300，财务关系上限 100，代金券核销记录上限 1000，资源包库存上限 20，资源包抵扣明细上限 50"},
                {"name": "--max-pages", "required": False, "type": "integer", "minimum": 1, "maximum": 10000, "default": 1000},
                {"name": "--max-rows", "required": False, "type": "integer", "minimum": 1, "maximum": 3000000, "default": 300000},
                {"name": "--retry-count", "required": False, "type": "integer", "minimum": 0, "maximum": 10, "default": 2},
                {"name": "--retry-backoff", "required": False, "type": "number", "minimum": 0, "maximum": 60, "default": 0.5},
                {"name": "--timeout", "required": False, "type": "positive_number"},
                {"name": "--region", "required": False, "type": "string", "default": None, "description": "用户明确选择时传入；省略时继承 ve 当前地域配置。"},
                {"name": "--profile", "required": False, "type": "string"},
                {"name": "--require-field", "required": False, "type": "repeatable_response_field", "purpose": "声明业务必须保留的响应字段；查询前按 Action + GroupPeriod + GroupTerm 字段矩阵验证请求粒度"},
                {"name": "--fixture-dir", "required": False, "type": "path", "test_only": True},
            ],
            "mutually_exclusive_required": [["--body", "--body-file"]],
            "body_contract_source": "cost.py schema --action <Action> --section request --include-guidance",
            "required_response_field_policy": (
                "用户明确要求明细标识字段时使用 --require-field；如果当前请求粒度不保留该字段，"
                "在调用 ve billing 前返回 RESPONSE_FIELD_NOT_PRESERVED 和 required_request。"
            ),
            "security": "body 只放业务参数，不放 AK/SK/session token。财务关系有记录时以相同凭证、profile 和 region 调用只读 STS GetCallerIdentity 核验当前账号，不读取本地 profile 内容或切换身份。",
        },
        "pagination": {
            "none": {
                "actions": sorted(NON_PAGED_ACTIONS),
                "behavior": "一次请求返回完整业务对象；调用方传入 pagination、page-size 或 page-offset 时忽略这些参数并返回 warning。",
                "public_status": "success",
                "complete_dataset_claim": True,
                "analysis_scope": "归因接口仅保证一次返回该请求的业务对象；不代表候选结果覆盖全部费用对象或账期最终数据。",
            },
            "page": {
                "use_when": ["预览", "抽样", "排障", "用户指定页"],
                "behavior": "只获取指定 Offset 或 NextToken 的一页，按指定页大小请求，不自动缩页。",
                "public_status": "success",
                "preflight_constraint": "page_size 超过 max_rows 时查询前返回 INVALID_ARGUMENT。",
                "truncated_response": "返回展开行数超过 max_rows 时交付 partial/exit 6，requested_scope_fulfilled=false；提高上限重查当前页。",
                "message_requirement": "明确结果只覆盖请求页，不代表完整数据范围。",
                "complete_dataset_claim": False,
            },
            "token_actions": {
                "ListResourcePackages": {"size_field": "MaxResults", "max_page_size": 20, "token_field": "NextToken"},
                "ListPackageUsageDetails": {"size_field": "MaxResults", "max_page_size": 50, "token_field": "NextToken"},
                "full_start": "空 NextToken",
                "complete_when": ["response NextToken is empty", "response NextToken is 0", "response List is empty"],
                "guards": ["repeated token", "non-advancing token", "repeated page", "max_pages", "max_rows"],
                "page_response": "coverage.queries[].next_token/has_more 保留续页信息；页内裁切时两者为 null，不能跳过未交付行继续。",
            },
            "full": {
                "use_when": ["完整 CSV", "准确汇总", "完整性证明"],
                "behavior": "从 Offset=0 自动翻页，检查 Total、空页、重复页、提前结束和安全上限。",
                "requirements": ["Offset=0", "NeedRecordNum=1"],
                "success_condition": "coverage.is_complete=true",
                "dynamic_period_stop": {
                    "triggers": ["total_changed", "rows_exceeded_first_total"],
                    "continue_after_trigger": False,
                },
                "current_period_snapshot_condition": {
                    "current_period": True,
                    "initial_total_boundary_reached": True,
                    "allowed_stop_reasons": ["total_changed", "rows_exceeded_first_total"],
                    "disallowed_anomalies": ["failed_page", "duplicate_page", "limit_mismatch", "offset_mismatch", "safety_limit"],
                },
                "current_period_snapshot_claim": {
                    "analysis_allowed": True,
                    "final_period_claim_allowed": False,
                    "required_disclosures": ["query_time_scope", "period_not_closed"],
                },
            },
            "parameter_precedence": "Limit/Offset 或 MaxResults 可在 body/CLI 中提供；两处同时提供且值不同则拒绝。NextToken 只在 body 中提供，full 必须从空 token 开始。",
        },
        "multi_period": {
            "argument": "--period YYYY-MM，可重复",
            "supported_fields": ["BillPeriod", "AmortizedMonth"],
            "failure_isolation": "一个账期失败不阻断其他账期；成功数据进入 CSV，失败分片进入 coverage.failed_queries。",
            "unsupported_action_policy": "不支持账期替换的 Action 必须在 body 中直接提供时间参数。",
        },
        "retry": {
            "retryable_errors": [ErrorCode.RATE_LIMITED.value, ErrorCode.TIMEOUT.value],
            "strategy": "有限指数退避；总尝试次数为 1 + retry_count。",
            "non_retryable": ["参数", "认证", "权限", "普通业务错误", "响应契约错误", "输出路径冲突"],
            "parameter_error_observation": "参数错误通过 error.details.invalid_parameters 返回错误参数及其局部真实契约；Agent 根据目标和本次证据自主决定后续动作。",
        },
        "output": {
            "output_protocol_version": "1.0",
            "public_fields": ["status", "message", "result"],
            "machine_field": "_meta",
            "result": {
                "small": "完整业务对象或数组直接位于 result。",
                "file": "大结果或显式 --out 使用文件型 result，直接返回 file、metadata、fields 三个绝对路径；该 result 可作为其他原子工具的输入。",
                "selection": "按完整紧凑 envelope 的 64 KiB UTF-8 大小决定是否自动落盘。",
            },
            "output_collision_policy": {
                "preflight_targets": ["primary", "metadata", "fields"],
                "error_code": ErrorCode.OUTPUT_EXISTS.value,
                "remote_call_attempted": False,
                "recovery_actions": ["choose_new_output_path", "retry_with_overwrite"],
                "overwrite_requires_task_ownership": True,
                "overwrite_default_retry": False,
                "replan_required": False,
                "query_expansion_allowed": False,
            },
            "data_artifact": {
                "format": "csv",
                "written_when": ["explicit_out", "stdout_envelope_over_64_kib"],
                "path": "显式 --out，或自动临时路径",
                "sidecars": ["metadata", "fields"],
            },
            "stdout": {
                "applies_to": "所有 query Action，包括 QueryBalanceAcct。",
                "format": "json",
                "required_fields": ["status", "message", "result", "_meta"],
                "status_values": ["success", "partial", "error"],
                "detailed_evidence": "小结果的 coverage/freshness/失败范围保存在 _meta；文件结果在 result 中直接返回 file、metadata、fields，_meta 继续保留兼容指针。Agent 只依赖公开三字段。",
            },
            "account_snapshot": {
                "applies_to": "QueryBalanceAcct",
                "stdout": "与其他 Action 使用相同 envelope；原始账户对象位于 result，确定性账户结论位于 message，金额值保留原始字符串。",
                "formula": "AvailableBalance = CashBalance + CreditLimit - FreezeAmount - ArrearsBalance；公式不一致时说明无法确认状态，并报告实际余额、预期值和差额。",
                "missing_values": "AvailableBalance 缺失时 success 且 message 说明无法确认；金额类型/有限值契约错误或 JSON/结构损坏时 error。",
                "time_fields": "原接口不返回快照时间，result/message/_meta 均不新增 queried_at、snapshot_time 或其他时间参数。",
                "export": "显式 --out 时 result.file 返回 CSV；_meta 指向 metadata/fields sidecar。",
            },
            "statuses": {
                "success": {
                    "exit_code": 0,
                    "meaning": "接口及本地执行未报错；范围和时效限制由 message 说明。",
                },
                "partial": {"exit_code": int(ExitCode.PARTIAL_RESULT), "meaning": "仍有可用结果，但必需请求范围存在已知缺口。"},
                "error": {"exit_code": "nonzero_except_6", "meaning": "没有可信可交付结果。"},
            },
            "artifacts": [
                {"name": "csv", "path": "显式 --out，或默认自动临时路径", "content": "原始字段加 _action/_query_id"},
                {"name": "fields", "path": "CSV 同目录下的 <out_stem>.fields.json", "content": "按当前 CSV 表头裁剪的字段语义目录，供 Agent 选择指标、直接分析或按需使用 helper"},
                {"name": "metadata", "path": "文件产物同目录下的 <out_stem>.meta.json", "content": "queries/coverage/freshness/warnings/artifacts"},
            ],
            "forward_compatibility": "未知响应字段原样进入 CSV 和小结果 result，不产生特殊 warning；已知字段类型错误失败。",
            "field_exposure": "显式屏蔽的核销字段会从 CSV、result 和 fields artifact 静默剔除，不作为 unknown 字段出现。",
        },
        "errors": {
            "stream": "stdout",
            "format": {
                "status": "error",
                "message": "脱敏且可直接行动的错误说明",
                "result": None,
                "_meta": {
                    "output_protocol_version": "1.0",
                    "error": {
                        "code": "ERROR_CODE",
                        "details": {
                            "invalid_parameters": "参数错误时，仅列出错误参数、违反约束及其局部真实契约；已知参数附实际值，未知参数不回显实际值；不提供执行计划或下一工具建议。"
                        },
                    },
                },
            },
            "exit_codes": {str(int(code)): code.name.lower() for code in ExitCode},
            "codes": [code.value for code in ErrorCode],
            "all_queries_failed_policy": (
                "所有查询分片均失败时，在写业务产物前返回非零退出码；同因失败沿用具体错误码，"
                "异因失败使用 ALL_QUERIES_FAILED。details.failed_queries 保留各分片错误，"
                "cause 保留经脱敏和限长的 ve billing 原生 stdout/stderr、returncode、remote code/message 和 request ID。"
            ),
        },
        "examples": [
            {
                "id": "single_page",
                "argv": ["query", "--action", "ListBillDetail", "--body", "{\"BillPeriod\":\"2026-07\"}", "--pagination", "page", "--page-offset", "0", "--page-size", "100", "--out", "bill-detail.csv"],
            },
            {
                "id": "non_paged_filter_catalog",
                "argv": ["query", "--action", "GetFilterInfoForCostAnalysis", "--body", "{\"TimeGranularity\":0,\"BeginTimeStr\":\"2026-07-01\",\"EndTimeStr\":\"2026-07-01\"}"],
            },
            {
                "id": "full_period",
                "argv": ["query", "--action", "ListBill", "--body", "{\"BillPeriod\":\"2026-07\"}", "--pagination", "full", "--out", "bill.csv"],
            },
            {
                "id": "full_multi_period",
                "argv": ["query", "--action", "ListBill", "--body", "{}", "--period", "2026-06", "--period", "2026-07", "--pagination", "full", "--out", "bill.csv"],
            },
        ],
    }


def describe_query(section: str = "all") -> dict[str, Any]:
    if section not in ("all", *CONTRACT_SECTIONS):
        raise ValueError(f"未知 contract section: {section}")
    contract = query_contract()
    if section == "all":
        return contract
    return {"section": section, section: contract[section]}
