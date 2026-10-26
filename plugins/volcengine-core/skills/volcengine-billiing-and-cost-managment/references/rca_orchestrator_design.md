# RCA Orchestrator 详细设计 (V1.2)

> 状态：REVISED — 待三次评审（合并 judge_stop 到 interpret_result）
> 设计原则：脚本执行工作流，LLM 只做策略函数。

---

## 1. 总览

### 1.1 问题

当前 RCA Skill 的核心流程（选 task → 调 OpenAPI → 解释结果 → 迁移 state → 判断停止）写在 `SKILL.md` 里，依赖 LLM 自觉执行。问题是：
- LLM 经常跳过步骤、自行推导 state、绕过 `analysis_state.py`
- 即使 V3 改造后 `analysis_state.py` 已是 canonical state 唯一迁移入口，LLM 仍可能不按流程调用

### 1.2 方案

新增 `scripts/run_rca_workflow.py`，用 **step/resume** 模式执行确定性工作流。脚本每次调用生命周期短，从 canonical state 恢复，不阻塞等待。

### 1.3 架构

```
SKILL.md（精简）
  └─ 触发条件、使用指引、hook I/O 说明、禁止项

scripts/run_rca_workflow.py（确定性编排）
  └─ step:   读取 canonical state → 判断下一步 → 输出 hook_request 或 tool_args 或 final
  └─ resume: 消费 hook_response 或 tool_result → 推进 state → 再判断下一步

scripts/analysis_state.py（状态迁移，不变）
  └─ init / apply-result / next-step / ...

references/
  └─ 业务规则、指标口径、hook schema 详细示例
```

---

## 2. Orchestrator CLI

### 2.1 命令

```bash
# 推进到下一步（自动判断需要什么）
run_rca_workflow.py step --state-file <path>

# 消费 LLM hook 响应，推进 state
run_rca_workflow.py resume --state-file <path> --hook-response-file <path>

# 消费工具执行结果（仅落盘，不推进 state）
run_rca_workflow.py resume --state-file <path> --tool-result-file <path>

# 初始化（首次调用）
run_rca_workflow.py init --question <str> --context-json <json> --state-file <path>
```

### 2.2 step 输出

`step` 命令输出一个 JSON，包含 `action` 字段：

```json
// 情况 A：需要 LLM 决策
{
  "action": "await_hook",
  "hook_type": "choose_task | interpret_result | draft_answer",
  "hook_request_file": "/path/to/hook_request.json",
  "prompt_for_agent": "请根据 hook_request.json 中的内容，返回 JSON 决策..."
}

// 情况 B：需要执行工具
{
  "action": "execute_tool",
  "tool_args": { "action": "QueryCostChangeDimensions", "model_args": { "dimension": "product" } },
  "tool_command": ["<python3>", "<scripts>/call_openapi.py", "QueryCostChangeDimensions", "<完整 model_args JSON>", "--runtime-config-file", "<state-file>.artifacts/openapi_config.json"],
  "prompt_for_agent": "按 tool_command 参数数组执行 call_openapi.py。"
}

// 情况 C：完成
{
  "action": "final",
  "final_answer": "分析结论...",
  "prompt_for_agent": "RCA 分析已完成。请将 final_answer 输出给用户。"
}
```

### 2.3 resume 输出

同 `step`，`resume` 也返回相同结构的输出，因为消费输入后需要继续推进到下一个决策点。

---

## 3. 状态流

### 3.1 主循环（由 agent 驱动，脚本不循环）

```
┌──────────────────────────────────────────────────────────────────┐
│                      Agent 驱动循环                                │
│                                                                    │
│  1. run_rca_workflow.py init                                       │
│     → 初始化 state，输出 step 结果（通常是 choose_task hook）       │
│                                                                    │
│  2. 循环：                                                         │
│     ├─ 如果 action=await_hook                                      │
│     │   → agent 读 hook_request.json，做决策                         │
│     │   → 写 hook_response.json                                    │
│     │   → run_rca_workflow.py resume --hook-response-file            │
│     │     （脚本校验 → 推进 state → 原子写回 state-file）              │
│     │                                                              │
│     ├─ 如果 action=execute_tool                                    │
│     │   → agent 执行 call_openapi.py                                   │
│     │   → 将工具输出写入 tool_result.json                           │
│     │   → run_rca_workflow.py resume --tool-result-file             │
│     │     （脚本保存 tool_result 到 state 的 artifact 目录，           │
│     │      但不调用 apply-result，因为还需要 interpretation）        │
│     │     → 输出 interpret_result hook                              │
│     │   → agent 填 hook_response (interpretation)                   │
│     │   → run_rca_workflow.py resume --hook-response-file            │
│     │     （脚本把 tool_result + interpretation 一起交给              │
│     │      analysis_state.py apply-result 完成状态迁移）             │
│     │                                                              │
│     └─ 如果 action=final                                           │
│         → 输出 final_answer 给用户                                │
│         → 结束                                                     │
└──────────────────────────────────────────────────────────────────┘
```

**关键：execute_tool 后的两步 resume + stop 判断**

正确时序（与 `analysis_state.py apply-result` 的 `llm_interpretation` 要求一致，且 `llm_decision` 在 `apply-result` 中通过 `_merge_llm_decision` 合入 canonical state）：

```
step → execute_tool
  → agent 执行 call_openapi.py
  → resume --tool-result-file
    （脚本：保存 tool_result，不调 apply-result，输出 interpret_result hook）
  → agent 填 hook_response (interpretation，含 llm_decision)
  → resume --hook-response-file
    （脚本：tool_result + interpretation → analysis_state.py apply-result
     → 状态迁移完成（含 stop_condition 更新）→ 原子写回 state-file）
  → 脚本读新 state 的 stop_condition.final
  → should_stop=false → 回到 choose_task
  → should_stop=true  → draft_answer hook → final
```

### 3.2 脚本内部状态机

```
        ┌──────────┐
        │  init    │
        └────┬─────┘
             │
             ▼
    ┌────────────────┐
    │  need_task?    │──Yes──→ hook: choose_task
    │  (pending 非空  │         → next-step
    │   且无 task)   │         → tool_args ready
    └───────┬────────┘
            │ No (已有 current_task→waiting_for_tool)
            ▼
    ┌────────────────┐
    │  tool 已执行?  │──No──→ action: execute_tool
    │  (有 tool      │        (输出 tool_args)
    │   result 文件) │
    └───────┬────────┘
            │ Yes (tool_result 已落盘)
            ▼
    ┌────────────────┐
    │  interpretation│──No──→ hook: interpret_result
    │  已获取?       │        (agent 填后 resume)
    └───────┬────────┘
            │ Yes (tool_result + interpretation 都就绪)
            ▼
    ┌────────────────────┐
    │  analysis_state.py │
    │  apply-result      │
    │  (tool_result +    │
    │   interpretation   │
    │   →apply+transition│
    │   → 原子写回 state) │
    └───────┬────────────┘
            │
            ▼
    ┌────────────────────┐
    │  读新 state 的      │
    │  stop_condition.    │
    │  final.should_stop  │
    │  (apply-result 已   │
    │   写入 stop_cond)   │
    └───┬───────┬────────┘
        │       │
    stop=false  stop=true
        │       │
        ▼       ▼
   回到：     hook:
   need_task  draft_answer
              → final
```

**注意**：stop 判断在 `apply-result` 内部完成（`llm_interpretation.llm_decision` 通过 `_merge_llm_decision` + `update_runtime_guardrail` + `finalize_stop_condition` 合入 state）。脚本只从新 state 读取 `stop_condition.final.should_stop`，不需要独立 `judge_stop` hook。

### 3.3 关键规则

- **每次 step/resume 调用后脚本退出**，不做循环等待
- **所有状态从 canonical state 文件恢复**，不依赖内存
- **所有产生新 canonical state 的动作，由 orchestrator 校验后原子写回 `state-file`**（使用 `runtime_utils.atomic_write_json`）
- `resume --tool-result-file` 只落盘 tool_result（不写回 state-file，因为 state 尚未迁移），并输出 `interpret_result` hook
- `resume --hook-response-file`（interpret_result）：将 tool_result + interpretation 一起交给 `analysis_state.py apply-result`，返回的 `analysis_state` 原子写回 state-file
- **hook_request 和 hook_response 是独立文件**，可审计
- **schema 校验失败**：脚本输出错误，不修改 state，要求 agent 重试
- **非法选项**：LLM 选择不存在的 task_id 时返回校验错误，修正后重新 resume，不能自行跳过 hook
- **state-file 的 artifacts 目录**：`<state-file>.artifacts/` 存放 tool_result、hook_request、hook_response 等临时文件，`step` 和 `resume` 自动管理

---

### OpenAPI 运行配置

`init` 接收 `--environment`、`--region`、`--endpoint`、`--profile`、`--timeout-seconds` 并将非敏感配置保存为 `<state-file>.artifacts/openapi_config.json`，不进入 LLM business context。BOE 缺 endpoint 会初始化失败。`init` 不覆盖已存在的状态或 artifacts；跨身份、环境必须使用新任务目录。默认分析当前授权身份，缺 account_id 不阻断流程。

`execute_tool` 保留 `tool_args` 供查看，并增加可以直接执行的 `tool_command` 参数数组；调用器固定三个 Action 的 `--force`、API 版本、HTTP 方法和 JSON 格式。成功时 interpret hook 的 `tool_result_summary` 是实际 `result.Result`，失败时传完整错误供解释。嵌套 `error` 的错误码和 retryable 原样交给状态机，保留有界重试。

## 4. Hook Schema

### 4.1 hook: choose_task

**时机**：pending_tasks 非空，需要选择下一个执行的任务

**输入** (hook_request.json):
```json
{
  "hook_type": "choose_task",
  "question": "为什么费用上涨？",
  "analysis_goal": "定位费用上涨原因",
  "current_findings_summary": ["已确认产品维度：ML 费用上涨 30%", "计费项：instance_type 变化"],
  "pending_tasks": [
    {
      "task_id": "task_002",
      "task_type": "locate_charge_item",
      "scope": {"product": "ML"},
      "reason": "定位 ML 中的主要计费项",
      "priority": 1
    }
  ],
  "completed_tasks": ["task_001"],
  "failed_tasks": [],
  "constraints": {
    "max_steps": 10,
    "remaining_steps": 8
  }
}
```

**输出** (hook_response.json):
```json
{
  "hook_type": "choose_task",
  "selected_task_id": "task_002",
  "decision_reason": "产品维度已定位，下一步需要定位到具体计费项"
}
```

**校验规则**：
- `selected_task_id` 必须在 `pending_tasks` 中
- `decision_reason` 不能为空
- 校验失败 → 返回错误，Agent 修正 hook_response 后重新 resume；无法修正则报告阻塞，不跳过状态机。

### 4.2 hook: interpret_result

**时机**：`resume --tool-result-file` 已将 tool_result 落盘（但尚未调用 `apply-result`，因为 `apply_tool_success` 需要 `llm_interpretation` 参数）。脚本输出此 hook 让 LLM 解释结果。

**正确时序**：
```
execute_tool → agent 调 call_openapi.py
  → resume --tool-result-file（落盘 tool_result，输出 interpret_result hook）
  → agent 填 hook_response
  → resume --hook-response-file（tool_result + interpretation → apply-result → 原子写回 state）
```

**输入** (hook_request.json):
```json
{
  "hook_type": "interpret_result",
  "tool_name": "QueryCostChangeDimensions",
  "tool_args": { "action": "QueryCostChangeDimensions", "model_args": { "dimension": "product" } },
  "tool_result_summary": {
    "top_items": [
      { "name": "ML", "change_pct": 30.5, "contribution_pct": 65.2 },
      { "name": "存储", "change_pct": 5.1, "contribution_pct": 12.3 }
    ],
    "total_items": 15
  },
  "current_task": {
    "task_id": "task_001",
    "description": "定位产品维度"
  },
  "existing_findings": [
    {
      "finding_type": "dimension_locate",
      "summary": "总费用上涨 23%",
      "scope": { "product": "ML" }
    }
  ],
  "question": "为什么费用上涨？"
}
```

**输出** (hook_response.json):
```json
{
  "hook_type": "interpret_result",
  "result_summary": "产品维度定位完成，ML 是主要上涨来源（贡献 65.2%）",
  "findings": [
    {
      "finding_type": "dimension_locate",
      "summary": "ML 产品费用上涨 30.5%，贡献总上涨的 65.2%",
      "scope": { "product": "ML" }
    }
  ],
  "candidate_tasks": [
    {
      "task_type": "locate_charge_item",
      "scope": {"product": "ML"},
      "reason": "定位 ML 中的主要计费项",
      "priority": 1
    }
  ],
  "llm_decision": {
    "should_stop": false,
    "answer_readiness": "not_ready",
    "reason": "已定位到产品维度，但还需要定位到计费项维度"
  }
}
```

**`llm_decision` 字段说明**（对齐 `analysis_state.py` 的 `_merge_llm_decision` 和 `_llm_decision_warnings`）：
- `should_stop` (boolean)：LLM 认为是否应该停止
- `answer_readiness` (string)：`not_ready` / `partially_ready` / `ready` / `ready_with_limitations`
- `reason` (string)：判断理由

**校验规则**：
- `result_summary` 不能为空
- `findings` 必须是数组，每个 finding 必须有合法的 `finding_type` 和 `summary`，结构化 scope 只能记录工具已证实的维度值
- 如果 finding 有 `scope.charge_item_code`，必须非空
- `llm_decision.should_stop` 必须是 boolean
- `llm_decision.answer_readiness` 必须是有效枚举值
- 校验失败 → 返回错误，Agent 修正 hook_response 后重新 resume；无法修正则报告阻塞，不跳过状态机。

**注意**：`llm_decision` 作为 `llm_delta` 的一部分传给 `analysis_state.py apply-result`，由 `normalize_llm_delta` 标准化后通过 `_merge_llm_decision` + `update_runtime_guardrail` + `finalize_stop_condition` 合入 canonical state。脚本在 `apply-result` 完成后从新 state 读取 `stop_condition.final.should_stop` 决定下一步。

### 4.3 hook: draft_answer

**时机**：`apply-result` 完成后 `stop_condition.final.should_stop = true`（或 runtime guardrail 触发强制 stop），需要生成最终答案

**输出消费**：draft_answer hook_response 被消费后，orchestrator 将 final_answer 写入 `final_answer.json`，并输出 `action=final`。**agent 不应自行输出最终答案**，而应使用脚本输出的 `final_answer` 内容。

**输入** (hook_request.json):
```json
{
  "hook_type": "draft_answer",
  "question": "为什么费用上涨？",
  "analysis_goal": "定位费用上涨原因",
  "findings": [
    {
      "finding_type": "dimension_locate",
      "summary": "ML 产品费用上涨 30.5%，贡献 65.2%",
      "scope": { "product": "ML" }
    },
    {
      "finding_type": "dimension_locate",
      "summary": "instance_type 从 A 变为 B，导致单价上涨",
      "scope": { "charge_item_code": "instance_type" }
    }
  ],
  "stop_reason": "已定位到主计费项，且没有更多待执行任务",
  "completed_tasks": ["task_001", "task_002", "task_003"],
  "failed_tasks": [],
  "constraints": {
    "language": "zh-CN",
    "max_length": 2000
  }
}
```

**输出** (hook_response.json):
```json
{
  "hook_type": "draft_answer",
  "final_answer": "费用上涨的主要原因是 ML 产品费用增长了 30.5%，贡献了总上涨的 65.2%。进一步分析发现，instance_type 从 A 变为 B，导致单价上涨。建议关注 ML 产品的 instance_type 使用情况。"
}
```

**校验规则**：
- `final_answer` 不能为空
- 不校验内容质量（由 agent 自行保证）
- 校验失败 → 返回错误，Agent 修正 hook_response 后重新 resume；无法修正则报告阻塞，不跳过状态机。

---

## 5. SKILL.md 瘦身范围

### 5.1 保留（~80 行）

```markdown
# Trade Expense Analysis Skill

## 概述
用于 FinOps / 费用异常分析与 RCA 的技能。

## 何时使用
- 用户问"为什么费用上涨"
- 用户要求定位费用变化原因
- ...

## 必须使用 run_rca_workflow.py

RCA 分析必须通过 `scripts/run_rca_workflow.py` 执行。流程：
1. `run_rca_workflow.py init` 初始化
2. `run_rca_workflow.py step` 获取下一步
3. 根据 action 类型执行对应操作
4. `run_rca_workflow.py resume` 推进

禁止绕过此脚本直接调用 `call_openapi.py` 或手写 state。

## Hook 响应指南

当脚本输出 `action=await_hook` 时，你需要读取 hook_request.json 并返回 JSON。

### choose_task
- 从 pending_tasks 中选择一个 task_id
- 返回 selected_task_id 和 decision_reason

### interpret_result
- 基于工具结果总结发现
- 生成 findings 和 candidate_tasks
- 判断是否应该停止（llm_decision.should_stop, answer_readiness）

### draft_answer
- 基于所有 findings 生成最终自然语言答案

## 禁止项
- 禁止手写完整 analysis_state
- 禁止跳过 run_rca_workflow.py 直接调 call_openapi.py
- 禁止在 should_stop=false 时给 final answer
- 禁止自行推导 FSM 状态
```

### 5.2 移出到 references/

- 完整 JSON Schema → `references/analysis_state.md`（已有）
- 字段说明、状态迁移示例 → `references/analysis_state.md`（已有）
- 业务口径、指标定义 → `references/rca_business_rules.md`（新增）
- Hook schema 详细示例 → `references/hook_schema_examples.md`（新增）

### 5.3 当前 SKILL.md 中需要移出的内容

- "推荐调用顺序" 大段 → 脚本接管
- "每轮后的判断原则" 详细步骤 → 脚本接管
- 完整 JSON Schema 引用 → 已在 references/
- "首轮选择原则"、"每轮后的判断原则" → 脚本接管 + hook 输入

---

## 6. 错误处理

### 6.1 Schema 校验失败

脚本返回具体字段错误，Agent 修正 hook_response 后重新 resume；无法修正时报告阻塞。脚本不会自行拼出 findings/答案或跳过 hook。

### 6.2 工具执行失败

- `call_openapi.py` 返回非 0 时，保存 stdout 的完整失败 JSON，通过 `resume --tool-result-file` 传入。
- 脚本输出 `interpret_result` hook；LLM 解释现有错误与已取得证据，不覆写错误码或 retryable，不生成 should_retry。
- interpretation resume 将嵌套 error 原样传给状态机。仅 retryable=true 的错误才可产生重试任务，受 `scheduler.max_retry`（默认 1）和 max_steps 限制。
- 鉴权/权限/参数错误不可自动重试；超时/限流/明确临时服务异常可重试。每次失败进入 failed_tasks，由状态机决定继续或给出限制说明。

### 6.3 无法继续

- pending_tasks 为空且 current_task 为空 → 强制 stop（apply-result 内部的 `update_runtime_guardrail` 会设 `must_stop=true`）
- max_steps 耗尽 → 强制 stop，通过 `runtime_guardrail` 触发→进入 draft_answer
- 所有 task 都 failed → 强制 stop，输出"无法完成分析"

---

## 7. 文件布局

```
scripts/
  run_rca_workflow.py          # 新增，编排脚本
  analysis_state.py            # 已有，不改
  runtime_utils.py             # JSON 原子写入与敏感信息脱敏
  call_openapi.py              # ve billing --force 执行器

SKILL.md                       # 瘦身，~300行 → ~80行

references/
  analysis_state.md            # 已有，不改
  rca_business_rules.md        # 新增，业务口径
  hook_schema_examples.md      # 新增，hook 示例

tests/
  test_run_rca_workflow.py     # 新增
```

---

## 8. 不做什么

- 不在脚本内直接调用模型 API
- 不让脚本做策略推理（只做校验和状态迁移）
- 不阻塞等待（每次调用短生命周期退出）
- 不把脚本做成 daemon 或 long-running process

---

## 9. 修订历史

### V1.0 → V1.1 (2026-07-01)

**阻塞修复**（TraeX 审查）：
1. **interpret_result 时序修正**：`execute_tool` 后先 `resume --tool-result-file`（落盘 tool_result），输出 `interpret_result` hook；agent 填 interpretation 后再 `resume --hook-response-file`（tool_result + interpretation → `analysis_state.py apply-result` → 原子写回 state）。修正了 V1.0 中"apply-result 已完成再让 LLM interpret"的倒置。
2. **canonical state 原子写回规则**：明确所有产生新 canonical state 的动作由 orchestrator 校验后 `atomic_write` 回 `state-file`。`resume --tool-result-file` 不写回 state。

**非阻塞修复**：
3. 删除 `ask_user` action（V1 不做用户追问闭环，`--user-response` 参数同步删除）
4. 修正 `answer_readiness` 枚举对齐 `analysis_state.py` 的 `ANSWER_READINESS = {not_ready, partially_ready, ready, ready_with_limitations}`
5. 修正 `apply-result` 参数：`--error-json/--error-file` 而非 `--is-failure`
6. 明确 `draft_answer` 消费后由 orchestrator 写 `final_answer.json`，agent 不自行输出答案

### V1.1 → V1.2 (2026-07-01)

**阻塞修复**（TraeX 二次审查）：
1. **合并 `judge_stop` 到 `interpret_result`**：删除独立 `judge_stop` hook。`llm_decision`（should_stop / answer_readiness / reason）作为 `interpret_result` 输出的一部分，随 `llm_delta` 传入 `analysis_state.py apply-result`，由 `_merge_llm_decision` + `update_runtime_guardrail` + `finalize_stop_condition` 合入 canonical state。脚本在 `apply-result` 后直接从新 state 读取 `stop_condition.final.should_stop`。3 个 hook：`choose_task` / `interpret_result` / `draft_answer`。

**理由**：`apply-result` 的 `llm_delta` 参数已经是 `llm_decision` 的自然写入点；独立 `judge_stop` hook 在 apply-result 之后没有可用的 CLI 进行状态迁移，除非新增命令或破坏状态边界。合并后只有一个状态迁移入口，更简洁。
