---
name: volcengine-billing-and-cost-management
description: 用于 FinOps / 费用异常分析与 RCA 的技能。遇到用户询问费用上涨、账单波动、异常来源、根因定位、是哪类维度导致异常、是用量还是单价/折扣/其他指标导致异常等场景时，都应主动使用本 skill。该 skill 会根据问题自动选择异常维度定位、异常指标定位等能力，使用当前授权身份分析费用波动。
license: MIT
metadata:
  openclaw:
    requires:
      bins: [python3, ve]
---

# volcengine-billing-and-cost-management

该 skill 用于 FinOps 场景下的费用异常分析、波动解释和根因定位（RCA）。
它是一个总控型分析 skill，但内部工具调用遵循更严格的 tool schema 设计原则：
- 先做结构化任务识别
- 再决定调用哪个分析动作
- 必要时串联多个动作
- 对模型暴露统一、稳定、最小化的参数语义
- 通过 adapter 映射到底层 OpenAPI 接口
- 所有数值结论只来自工具结果，不允许模型补造
- 最终输出结构化、可解释的 FinOps 结论

## 适用场景

当用户出现以下任一意图时，使用本 skill：
- "为什么费用涨了 / 降了"
- "帮我做一下 RCA / 根因分析"
- "哪个产品、地域、实例、主体导致异常"
- "是单价、用量、折扣还是其他指标导致异常"
- "帮我定位费用异常来源"
- "帮我看某个客户 / 账户 / 账期的费用波动原因"
- "帮我解释某个账单异常"

不适用于：
- 纯术语解释
- 纯权限问题
- 不涉及异常分析的静态数据查询

## 运行环境与身份

需要 Python 3.9+、PATH 中可用的 `ve` CLI，以及 Host 提供并隔离的当前用户认证上下文（CLI profile 或环境凭证）。不读取、输出或复制 AK/SK/token，不修改全局 CLI 登录配置。

编排动作、脚本输入和 OpenAPI Action 统一使用 `QueryCostChangeDimensions`、`QueryCostChangeAmountComponents`、`QueryCostChangeDrivers`，**始终使用 `--force` 泛化调用**，固定 `billing`、`2022-01-01`、`POST` 和 JSON Content-Type。不兼容旧动作名及旧分析状态，请新建分析任务。`--force` 只跳过 CLI 元数据校验，服务端仍需发布新接口并授予当前身份访问权限。新接口不可用时按工具失败路径处理，不回退旧接口或内部接口。

每个会话/分析任务使用独立目录和 `state-file`。初始化可以接收 `--environment online|boe`、`--region`、`--endpoint`、`--profile`、`--timeout-seconds`，只采用 Host/测试环境提供的配置；业务上下文和 hook 不携带这些字段。BOE 必须显式提供 endpoint。初始化将非敏感配置写入 `<state-file>.artifacts/openapi_config.json`，后续 `tool_command` 自动沿用；不要改写配置。切换身份、环境或账号授权后新建任务，不复用旧分析状态。

详细配置与响应契约见 `references/api_mapping.md`。

如果调用返回 `VE_CLI_UPGRADE_REQUIRED`（ve 不支持 `--force`），必须明确提示用户先升级 ve 到支持 `--force` 泛化调用的版本，再重新发起分析；不要自动反复重试、移除 `--force` 或回退旧接口。仅报“不支持 Action”时不能直接认定为版本过低，仍需区分 CLI、平台代理与接口发布问题。

## 默认执行入口：run_rca_workflow.py

RCA 分析必须通过 `scripts/run_rca_workflow.py` 的 `init / step / resume` 流程执行。该脚本是 skill 的默认编排入口，负责推进固定工作流、调用 `analysis_state.py` 完成状态迁移、管理 hook artifact、校验输入并输出下一步 action。

禁止绕过 `run_rca_workflow.py` 直接按旧流程手动调用 `analysis_state.py next-step / apply-result` 或直接拼 `call_openapi.py` 参数。`analysis_state.py` 仍是 canonical state 的唯一状态迁移入口，但由 `run_rca_workflow.py` 调用，不由 LLM 手工串联。

标准流程：

```plain_text
1. 初始化：
   python3 scripts/run_rca_workflow.py init \
     --question "<用户问题>" \
     --context-json '<current_period/base_period 等业务上下文>' \
     --state-file <state.json>

2. 根据脚本输出 action 执行：
   - action=await_hook：读取 hook_request_file，按 hook_type 生成 hook_response.json，
     然后执行 resume --hook-response-file。
   - action=execute_tool：按脚本输出的 tool_command 参数数组执行 scripts/call_openapi.py，
     将工具结果写入 tool_result.json，然后执行 resume --tool-result-file。
   - action=final：输出脚本返回的 final_answer。

3. 每次 resume 后，继续按脚本返回的 action 执行，直到 action=final。
```

三个 LLM hook：

- `choose_task`：从 `pending_tasks` 中选择一个 `selected_task_id`，并给出 `decision_reason`。
- `interpret_result`：解释工具结果，输出 `result_summary`、`findings`、`candidate_tasks`、`llm_decision`。
- `draft_answer`：在脚本确认 `stop_condition.final.should_stop=true` 后，基于 findings 生成最终自然语言答案。

Hook response 不是 `analysis_state`。LLM 只能返回 hook schema 要求的轻量 JSON，不得手写完整 `analysis_state`、FSM 状态或任务队列。完整 orchestrator 设计和 hook 示例见 `references/rca_orchestrator_design.md`。

## Tool Definitions

本 skill 内部有 3 个分析工具：`QueryCostChangeDimensions`、`QueryCostChangeAmountComponents`、`QueryCostChangeDrivers`。
这里仅保留模型做 Tool Choice 所必需的信息；底层 OpenAPI 请求体、字段映射、返回结构细节统一放在 `references/api_mapping.md`。

### 通用调用原则

#### 模型层统一参数

调用任何工具时，模型层统一使用以下字段名：

- `current_period: string`，格式 `YYYY-MM-01`
- `base_period: string`，格式 `YYYY-MM-01`
- `dimension: string`，仅在 `QueryCostChangeDimensions` 中使用
- `filters: object`，过滤条件，选填，用于约束上层范围
- `charge_item_code: string`，仅在 `QueryCostChangeAmountComponents` / `QueryCostChangeDrivers` 中使用

通用约束：

- 默认分析当前授权账号，不向用户追问账号 ID，也不向 OpenAPI 传 `account_id` / `AccountID`。用户指定其它账号时，先说明当前身份边界；没有 Host 的授权切换能力时不能代查或静默改查当前账号。
- `filters` 仅允许以下 key：`product`、`instance_no`、`charge_item_code`、`project`、`region_code`
- 模型只使用统一字段名；底层字段差异由 adapter 或脚本层处理

### QueryCostChangeDimensions

**用途**：定位异常主要集中在哪些对象上。

**适用问题**：

- 哪个产品导致上涨 / 下跌
- 哪个地域异常
- 哪个实例最异常
- 哪些对象贡献了大部分波动
- 帮我定位异常来源

**不适用问题**：

- 用户在问金额构成变化 → 不优先用 `QueryCostChangeDimensions`
- 用户在问用量 / 单价驱动 → 不优先用 `QueryCostChangeDimensions`

**前置条件**：

- 需要账期
- 需要明确定位维度；若是泛化 RCA，默认从 `dimension="product"` 开始

---

### QueryCostChangeAmountComponents

**用途**：分析某个 `charge_item_code` 的金额构成变化。

**适用问题**：

- 应付金额为什么变多 / 变少
- 原价、折后价、退款、代金券等金额项分别怎么变了
- 金额结构层面发生了什么变化

**前置条件**：

- **只有在 `charge_item_code` 已知时才能调用**

**不适用问题**：

- 用户只是问异常在哪里 → 不用 `QueryCostChangeAmountComponents`
- 用户在问用量 / 单价驱动 → 改用 `QueryCostChangeDrivers`

---

### QueryCostChangeDrivers

**用途**：分析某个 `charge_item_code` 的变化由哪些驱动因子造成。

**适用问题**：

- 到底是用量问题还是单价问题
- 哪个因子在驱动上涨 / 下跌
- usage、unit_price、impact_factor 分别贡献了多少

**前置条件**：

- **只有在 `charge_item_code` 已知时才能调用**

**不适用问题**：

- 用户只是问异常定位 → 不用 `QueryCostChangeDrivers`
- 用户在问金额构成 → 改用 `QueryCostChangeAmountComponents`

---

## Tool Choice 路由规则

本节是该 skill 的核心。
模型不直接调度下一轮工具；是否继续由 `run_rca_workflow.py` 根据 canonical state 输出下一步 action。模型只在脚本输出 hook 时做窄决策。

### 中间状态约束

`run_rca_workflow.py` 是 RCA 主流程编排入口；`analysis_state.py` 是 canonical `analysis_state` 的**唯一迁移入口**。LLM 是策略决策者，不直接生成/修改完整 `analysis_state`，也不手工串联底层状态命令。

新版 `analysis_state` 采用 `analysis-state-v0.3` 协议，核心分工是：

- **LLM 负责**：响应 `run_rca_workflow.py` 输出的 hook，提供 `selected_task_id` / `decision_reason`、`findings` / `result_summary` / `candidate_tasks` / `llm_decision`，以及最终 `final_answer`
- **LLM 禁止**：手写完整 `analysis_state`、自行推导 `fsm.state`、自行维护 task_queue、自行判断"给受限答案"绕过失败路径
- **Orchestrator 负责**：决定下一步 action、管理 hook/tool artifacts、校验 hook response、调用 `analysis_state.py`、原子写回 canonical state
- **Runtime 负责**：状态结构校验、`pending/current/completed/failed` 迁移、`task_key` 去重、前置条件校验、max steps / 无可执行任务 / 工具失败重试等硬护栏、FSM 推进、stop condition 计算。Runtime 是 canonical state 的唯一写入者。

每轮状态必须包含 `question`、`context`、`fsm`、`current_task`、`pending_tasks`、`completed_tasks`、`failed_tasks`、`findings`、`scheduler`、`progress_signals`、`stop_condition`、`dedup` 等顶层字段。完整 JSON Schema、字段说明和状态迁移示例见 `references/analysis_state.md`。

初始化时通过 `run_rca_workflow.py init` 传入用户问题和 `current_period/base_period` 等上下文。Runtime 会生成初始 task；缺少必要业务上下文时，Runtime 会生成 `blocked` 状态，清空可执行任务指针，Agent 应追问用户补齐字段，而不是继续调用工具。

**强制工作流（每轮必须遵循，由 orchestrator 输出 action 驱动）**：

```
run_rca_workflow.py init
→ action=await_hook/choose_task
→ run_rca_workflow.py resume --hook-response-file
→ action=execute_tool
→ call_openapi.py
→ run_rca_workflow.py resume --tool-result-file
→ action=await_hook/interpret_result
→ run_rca_workflow.py resume --hook-response-file
→ [若 continue] action=await_hook/choose_task
→ [若 stop] action=await_hook/draft_answer
→ run_rca_workflow.py resume --hook-response-file
→ action=final
```

**失败处理规则**：

- `run_rca_workflow.py init` 失败是阻断性错误，必须重试、追问用户补齐上下文或终止；不允许在没有 canonical state 的情况下直接调用 `call_openapi.py`。
- `call_openapi.py` 调用失败时，必须把失败结果写入 `tool_result.json` 并通过 `run_rca_workflow.py resume --tool-result-file` 进入 failure/interpretation 路径，不允许跳过状态迁移直接给受限答案或进入下一轮。
- `run_rca_workflow.py resume` 失败是阻断性错误，必须根据错误修正 hook response/tool result 后重试或终止；不允许手写状态文件、FSM 状态或任务队列。
- 工具参数必须来自 `execute_tool.tool_args`，不得绕过编排器手工拼参。
- 在 `stop_condition.final.should_stop = false` 时不得直接给出最终答案。

### 第一轮选择原则

- 初始任务由 `run_rca_workflow.py init` 调用 runtime 生成。
- 若脚本输出 `action=await_hook` 且 `hook_type=choose_task`，只能从 `hook_request_file` 的 `pending_tasks` 中选择一个 `selected_task_id`。
- 选择任务时遵循业务优先级：泛化 RCA 通常先定位产品维度；金额构成/驱动因子问题若缺少 `charge_item_code`，先通过定位任务补齐计费项。

### 每轮后的判断原则

每次拿到工具结果后，必须把结果写入 `tool_result.json` 并执行 `run_rca_workflow.py resume --tool-result-file`。脚本随后输出 `interpret_result` hook；LLM 只填写 hook response，不自行修改 state：

- LLM 提供轻量 interpretation：`result_summary`、`findings`、`candidate_tasks`、`progress_signals`、`llm_decision`
- Runtime 自动完成：`current_task` → `completed_tasks/failed_tasks`、`findings` 合并、`pending_tasks` 更新、`fsm.state` 推进、`stop_condition` 计算

如果 finding 表示已经定位到主计费项，必须把 `charge_item_code` 写入 `finding.scope.charge_item_code`，不能只写在 `summary` 文本里；Runtime 只基于结构化 scope 推导 `progress_signals.has_primary_charge_item`，不会从自然语言摘要中抽取计费项。

Runtime 随后更新 `stop_condition.runtime_guardrail` 和 `stop_condition.final`。只有脚本再次输出 `action=execute_tool` 或 `action=await_hook` 时才继续；脚本输出 `action=final` 时，基于脚本返回的 `final_answer` 输出结论或说明阻塞原因。

### 前置条件规则

- `QueryCostChangeAmountComponents` 和 `QueryCostChangeDrivers` 只能在 `charge_item_code` 已知时调用
- 如果缺少 `charge_item_code`，必须先通过 `QueryCostChangeDimensions` 补齐
- 用户只提供月份、未指定年份时，默认使用当前年份；有明确历史上下文时沿用该年份。
- 缺少账期时向用户追问；凭证或授权失败按 OpenAPI 错误处理，补账号 ID 不能修复认证。
- 如果初始化状态已因缺少必要上下文进入 `blocked`，必须基于 `stop_condition.final.reason` 追问缺失字段，不得调用 `call_openapi.py`
- 不允许跳过前置条件直接调用解释型工具
- 工具参数由 `analysis_state.context + analysis_state.current_task.scope` 合成，模型不得从自然语言上下文中绕过状态对象临时拼参

## 运行文件与敏感信息

- `state-file` 及其 `.artifacts` 目录保存业务状态、hook 请求、工具参数/结果、最终答复及非敏感 OpenAPI 配置，用于跨命令推进分析流程。
- 不得把 Authorization、AK、SK、token、JWT、cookie、API key 等敏感信息写入运行文件或控制台输出。

## 统一 OpenAPI 调用

所有底层分析动作统一通过 `call_openapi.py` 执行 `ve billing <Action> --force` 调用 OpenAPI，模型不直接拼接底层 HTTP 请求或手写 OpenAPI 请求体。脚本输入、工作流中的 `action` 与网关 Action 均使用三个新名称，无旧名称映射。

### 执行入口原则
- `run_rca_workflow.py` 是 RCA 分析默认编排入口，Agent 必须按它输出的 action 推进
- `call_openapi.py` 是底层 OpenAPI 分析动作执行入口，只能在 `run_rca_workflow.py` 输出 `action=execute_tool` 后按脚本给出的 `tool_command` 调用
- `analysis_state.py` 是 canonical `analysis_state` 初始化、任务选择、工具参数构造和状态迁移的**唯一权威入口**（不是辅助入口），但由 `run_rca_workflow.py` 调用，不由 LLM 手工串联
- 标准运行链路：`run_rca_workflow.py init` → 按 action 处理 `await_hook / execute_tool / final` → `run_rca_workflow.py resume` → 循环直到 `action=final`
- 模型负责：
  - 在 `choose_task` hook 中选择 `pending_tasks` 中的 `selected_task_id`，并说明 `decision_reason`
  - 在 `interpret_result` hook 中解释工具结果，生成 `findings` / `candidate_tasks` / `llm_decision`
  - 在 `draft_answer` hook 中生成最终答案
  - 不直接手写底层 OpenAPI 请求体；常规链路下不直接拼 `call_openapi.py` 的 `model_args`，而是使用 `run_rca_workflow.py` 输出的 `execute_tool.tool_args`
- `call_openapi.py` 负责：
  - 校验 Action 与关键前置参数
  - 直接调用 `QueryCostChangeDimensions` 时校验 `dimension` 只能是 `product`、`charge_item_code`、`instance_no`、`region_code`、`project`
  - 执行模型层参数到 OpenAPI 请求体的 adapter 映射
  - 处理不同 Action 的底层字段命名差异和固定 `Metric`
  - 发起 OpenAPI 调用并返回结果
- 阻断型前置条件和任务合法性检查必须通过 `run_rca_workflow.py` 间接调用 `analysis_state.py next-step` 完成。
- AdapterError 属于脚本参数错误，以结构化失败 JSON 返回；常规链路应使用 `run_rca_workflow.py` 输出的 `execute_tool.tool_args`，由 orchestrator 间接完成参数构造和前置校验。
- 模型不负责：
  - 处理底层字段命名差异
  - 拼接 OpenAPI 请求体
  - 决定固定 `Metric` 取值
  - 兼容不同 Action 的底层 payload 结构

### 调用约束

- 必须通过脚本调用，不直接手写 curl
- 使用可执行本地命令的工具运行 `tool_command`；参数必须保持独立并正确引用，不能把 JSON 当 shell 代码。
- Action 映射、adapter 规则、请求体格式、字段映射和返回结构详见 `references/api_mapping.md`

## 输出规范

最终回答应基于脚本返回结果生成，采用**先结论、后展开**的表达方式，优先输出用户可直接理解的业务解释，而不是原始字段或 JSON。

### 输出原则

- 先用 1–2 句话说明总体结论：费用是涨了还是降了，主要由什么对象或因素驱动
- 再按需要展开关键证据，可结合短段落和表格
- 叙事部分要突出因果关系，不要只罗列数字
- 表格只展示关键数据，不堆砌底层字段
- 数值统一保留两位小数，金额使用千分位分隔
- 若异常高度集中，可只展示 Top1，并说明集中度高
- 若当前结果不足以支持明确结论，应直接说明信号不足或前置条件缺失，不得补造原因

### 表达要求

- 面向业务用户表达，优先解释“为什么”
- 不直接粘贴原始 JSON
- 不暴露底层 OpenAPI 字段名作为正文主体
- 在金额构成、归因路径、因子分解等场景下，可按问题需要选择性展示表格
- 结尾可补充 1–2 个可继续追问的方向

### 与 `api_mapping.md` 的关系

返回结构中的字段提取方式、TopN 选择规则、金额构成排序规则、因子聚合规则等实现细节，统一见 `references/api_mapping.md`。

## 约束

1. **禁止直接写 SQL 查数据**，所有数据必须通过脚本获取
2. **禁止编造数据**，所有数值结论必须来自脚本输出的 JSON
3. 如果脚本执行失败，必须说明卡在哪一步、报错信息是什么，并根据错误区分凭证失效、无权限、参数错误、超时或服务异常；不能把失败解释为零费用
4. 缺少关键前置条件（如账期、`charge_item_code`）时，必须先追问用户或通过前置动作补齐，不得跳过条件直接输出解释性结论
5. 如果用户追问更细粒度的问题（如“按地域分析”），应继续遵循 Tool Choice 与前置条件规则，选择合适的下一轮分析动作
6. 最终回答面向业务用户表达，不输出底层脚本命令、OpenAPI 请求体或实现层字段映射作为正文主体
