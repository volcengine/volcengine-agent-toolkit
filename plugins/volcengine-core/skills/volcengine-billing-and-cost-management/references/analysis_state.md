# Analysis State Protocol v0.3

本文档定义费用 RCA 多轮分析中的运行时状态协议。`analysis_state` 服务 Agent 的多轮任务调度和状态流转。

核心边界：

- LLM 主导 RCA 分析路径、工具选择、结果解释、候选任务生成和语义停止判断。
- Runtime 负责状态结构校验、任务状态迁移、`task_key` 去重、前置条件校验、max steps / 无可执行任务 / 工具失败重试等硬护栏。

## 顶层结构

每轮状态必须包含以下顶层字段，字段不得缺失：

```json
{
  "schema_version": "analysis-state-v0.3",
  "question": {},
  "context": {},
  "fsm": {},
  "current_task": null,
  "pending_tasks": [],
  "completed_tasks": [],
  "failed_tasks": [],
  "findings": [],
  "scheduler": {},
  "progress_signals": {},
  "stop_condition": {},
  "dedup": {}
}
```

结构字段必须齐全，但 `context` 中的业务字段在初始化阶段允许为空。缺少 `current_period/base_period` 等必要业务上下文时，Runtime 应生成 `fsm.state=blocked` 且 `stop_condition.final.should_stop=true` 的合法状态，而不是初始化失败。真正执行 task 前再通过 `requires` 校验阻断工具调用。

## 字段说明

### `question`

```json
{
  "raw_user_query": "为什么 6 月费用上涨？",
  "question_type": "generic_rca",
  "analysis_goal": "explain_cost_increase"
}
```

`question_type` 允许值：`dimension_locate`、`amount_breakdown`、`driver_decompose`、`generic_rca`。

`analysis_goal` 允许值：`locate_main_dimension`、`explain_amount_change`、`explain_driver_change`、`explain_cost_increase`。

### `context`

```json
{
  "current_period": "2026-06-01",
  "base_period": "2026-05-01",
  "global_filters": {}
}
```

`context` 保存所有 RCA tool 调用共享的公共参数。工具参数必须由：

```text
context + current_task.scope
```

合成。

当前授权账号由 OpenAPI 鉴权上下文确定；业务状态不记录用户/模型提供的 account_id 或 AccountID，工具参数不携带账号身份。

初始化输入中仍推荐把业务过滤条件放入 `global_filters`；为降低接入成本，Runtime 也会兼容顶层 `product`、`instance_no`、`charge_item_code`、`project`、`region_code`，并在初始化时归一进 `context.global_filters`。当顶层字段与 `global_filters` 同名时，以 `global_filters` 中的显式值为准。

初始化阶段如果缺少必要业务上下文，可使用空字符串或 `null` 表示未知字段；此时状态必须携带：

```json
{
  "fsm": {"state": "blocked"},
  "stop_condition": {
    "runtime_guardrail": {"must_stop": true, "reason": "missing_required_context"},
    "final": {"should_stop": true, "reason": "runtime_guardrail_missing_required_context"}
  }
}
```

### `fsm`

```json
{
  "state": "running",
  "step": 0,
  "last_transition": null
}
```

`state` 允许值：`initialized`、`running`、`waiting_for_tool`、`interpreting_result`、`ready_to_answer`、`blocked`、`stopped`。

`fsm.state` 表示生命周期，不表达业务动作。业务动作由 `current_task.task_type` 表达。

### Task 对象

`current_task` 与 `pending_tasks` 中的 task 使用同一结构：

```json
{
  "task_id": "task_001",
  "task_key": "locate_charge_item|product=ML",
  "task_type": "locate_charge_item",
  "scope": {"product": "ML"},
  "requires": ["current_period", "base_period"],
  "priority": 90,
  "parent_task_id": "task_000",
  "reason": "ML 是产品维度主因，需要继续定位其下主要计费项",
  "evidence_summary": "ML 是产品维度主因，需继续定位计费项"
}
```

`task_type` 允许值：`locate_product`、`locate_charge_item`、`locate_instance`、`locate_region`、`locate_project`、`locate_amount`、`decompose_charge_item`。最终回答不是 `task_type`；Runtime 不支持 `answer` task。最终回答由 Agent 在 `stop_condition.final.should_stop = true` 后基于 `findings` 生成。

### `completed_tasks`

记录已完成任务，表示“做过什么”，不等同于业务结论：

```json
{
  "task_id": "task_001",
  "task_key": "locate_product",
  "task_type": "locate_product",
  "scope": {},
  "result_summary": "产品维度定位到 ML 是主因，ECS 是次因",
  "evidence_refs": {"result_file": "locate_product_result.json", "request_id": "request_001"},
  "generated_task_ids": ["task_002", "task_003"],
  "completed_at_step": 1
}
```

### `failed_tasks`

失败任务不能静默丢弃，也不能无限留在 `pending_tasks`：

```json
{
  "task_id": "task_006",
  "task_key": "decompose_charge_item|charge_item_code=ecs.xxx|product=ECS",
  "task_type": "decompose_charge_item",
  "scope": {"product": "ECS", "charge_item_code": "ecs.xxx"},
  "failure_reason": "tool_error",
  "error_code": "FAAS_TIMEOUT",
  "error_message": "timeout",
  "retryable": true,
  "retry_count": 1,
  "failed_at_step": 6
}
```

`failed_tasks[].retry_count` 表示该次失败对应任务已经携带的 `retry_count`：首次执行失败为 `0`，第 1 次重试失败为 `1`。它不是“同一个 task_key 的累计失败次数”；新的重试任务会在生成时把 `retry_count` 递增。

### `findings`

`findings` 是最终回答的结构化结论来源：

```json
{
  "finding_id": "finding_001",
  "finding_type": "driver_decompose",
  "scope": {"product": "ML", "charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"},
  "summary": "ML 下该计费项费用上涨主要由用量增长导致",
  "confidence": "high",
  "evidence_refs": {"result_file": "locate_charge_item_result.json", "request_id": "request_002"},
  "source_task_id": "task_004"
}
```

`finding_type` 允许值：`dimension_locate`、`amount_breakdown`、`driver_decompose`、`anomaly_detected`、`insufficient_signal`。

`confidence` 允许值：`high`、`medium`、`low`、`unknown`。

如果 finding 表示已经定位到主计费项，必须把 `charge_item_code` 写入 `finding.scope.charge_item_code`，不能只写在 `summary` 文本中。Runtime 只基于结构化 `scope.charge_item_code` 推导 `progress_signals.has_primary_charge_item`，不会从自然语言摘要中抽取计费项。

### `scheduler`

```json
{
  "mode": "llm_guided",
  "max_steps": 8,
  "max_retry": 1,
  "selection_policy": "llm_selects_task_runtime_validates"
}
```

LLM 选择下一步任务，Runtime 校验任务是否合法、是否重复、是否满足前置条件、是否超过 `max_steps`。

### `progress_signals`

```json
{
  "has_primary_dimension": false,
  "has_primary_charge_item": false,
  "has_driver_explanation": false,
  "has_answerable_finding": false,
  "has_user_requested_scope_resolved": false,
  "has_unresolved_required_task": true
}
```

这些是给 LLM 判断是否停止的轻量信号。本版本不引入复杂数值覆盖率计算流程；语义停止由 LLM 判断，Runtime 只做硬性护栏与可从 `findings` 推导出的硬事实一致性更新。`has_user_requested_scope_resolved` 是 LLM 语义判断信号，Runtime 不从 `findings` 自动推导，只做布尔结构校验；`has_unresolved_required_task` 表示 Runtime 当前仍看到 `pending_tasks/current_task` 且最终未停止，并不等同于所有 pending task 都是业务上必须执行的 required task；required 语义仍由 LLM 结合问题目标判断。

### `stop_condition`

```json
{
  "llm_decision": {
    "should_stop": false,
    "answer_readiness": "partially_ready",
    "reason": "已定位到主因产品 ML，但尚未解释具体计费项或驱动因素",
    "next_required_task_id": "task_002"
  },
  "runtime_guardrail": {
    "must_stop": false,
    "reason": null
  },
  "final": {
    "should_stop": false,
    "reason": "llm_requires_more_analysis"
  }
}
```

`answer_readiness` 允许值：`not_ready`、`partially_ready`、`ready`、`ready_with_limitations`。

Runtime hard stop reason 允许值：`missing_required_context`、`max_steps_reached`、`no_executable_task`、`tool_error_retry_exceeded`、`invalid_state`。

`missing_required_context` 优先级最高；`max_steps_reached` 只在 LLM 尚未判断可停止时作为硬停。如果最后一次允许的工具调用后 LLM 已设置 `llm_decision.should_stop=true`，最终原因应保留为 `llm_answer_ready` 或 `llm_answer_ready_with_limitations`，不能被 max steps 覆盖。

最终停止规则：

```text
if runtime_guardrail.must_stop = true:
    final.should_stop = true
elif llm_decision.should_stop = true and answer_readiness in {"not_ready", "partially_ready"}:
    final.should_stop = true
    final.reason = "llm_stop_decision_inconsistent"
    llm_decision.warnings += ["inconsistent_llm_stop_decision"]
else:
    final.should_stop = llm_decision.should_stop
```

### `dedup`

```json
{
  "visited_task_keys": ["locate_product", "locate_charge_item|product=ML"]
}
```

`task_key` 稳定生成规则：

```text
task_type + sorted(scope key=value)
```

例如：

```text
locate_product
locate_charge_item|product=ML
decompose_charge_item|charge_item_code=ml.hpcpni2.28xlarge_cn-beijing|product=ML
```

## 初始化规则

初始化时优先使用 LLM / Agent 显式传入的 `parsed_context.initial_tasks`。Runtime 只负责补齐 `task_id`、`task_key`、`requires`、`parent_task_id` 等结构字段，并过滤非法 task；如果 `initial_tasks` 缺失或为空，才使用下面的保守 fallback。

`pending_tasks` 表示候选可执行任务。初始化阶段 Runtime 会过滤 `requires` 无法从 `context + global_filters + scope` 满足的 `initial_tasks`；如果所有显式 `initial_tasks` 均不可执行，则回退到保守 fallback 或因缺少必要上下文进入 `blocked`。被过滤的显式 initial task 不能静默丢弃，Runtime 会在 `fsm.last_transition.skipped_initial_tasks` 中记录原因，便于排查 fallback 来源。

缺少 `current_period/base_period` 等必要上下文时，初始化状态应直接进入 `blocked`，且 `pending_tasks=[]`、`current_task=null`、`stop_condition.llm_decision.next_required_task_id=null`、`runtime_guardrail.must_stop=true`。此时 Runtime 不再逐个 materialize / filter `initial_tasks`，避免同时产生 initial task 缺上下文与 `missing_required_context` 两类重复 warning；下一步是追问缺失字段，而不是选择或执行 pending task。

示例：

```json
{
  "question_type": "generic_rca",
  "analysis_goal": "explain_cost_increase",
  "initial_tasks": [
    {
      "task_type": "locate_product",
      "scope": {},
      "priority": 100,
      "reason": "用户询问整体费用上涨原因，先从产品维度定位"
    }
  ]
}
```

### 泛化 RCA

用户问“为什么 6 月费用上涨？”时，初始化 `pending_tasks`：

```json
[
  {
    "task_id": "task_001",
    "task_key": "locate_product",
    "task_type": "locate_product",
    "scope": {},
    "requires": ["current_period", "base_period"],
    "priority": 100,
    "parent_task_id": null,
    "reason": "整体费用上涨归因先从产品维度定位"
  }
]
```

### 用户已指定产品

用户问“ML 为什么涨了？”时，初始化 `pending_tasks`：

```json
[
  {
    "task_id": "task_001",
    "task_key": "locate_charge_item|product=ML",
    "task_type": "locate_charge_item",
    "scope": {"product": "ML"},
    "requires": ["current_period", "base_period"],
    "priority": 100,
    "parent_task_id": null,
    "reason": "用户已指定产品 ML，直接定位其下主要计费项"
  }
]
```

### 用户已指定计费项

用户问“ml.hpcpni2.28xlarge_cn-beijing 为什么涨？”时，初始化 `pending_tasks`：

```json
[
  {
    "task_id": "task_001",
    "task_key": "decompose_charge_item|charge_item_code=ml.hpcpni2.28xlarge_cn-beijing",
    "task_type": "decompose_charge_item",
    "scope": {"charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"},
    "requires": ["current_period", "base_period", "charge_item_code"],
    "priority": 100,
    "parent_task_id": null,
    "reason": "用户已指定计费项，直接拆解驱动因素"
  }
]
```

## 状态转移规则

### LLM 选择任务

触发条件：

```text
fsm.state = running
current_task = null
pending_tasks 非空
stop_condition.final.should_stop = false
```

LLM 从 `pending_tasks` 中选择任务，Runtime 校验：

- `selected_task_id` 是否存在于 `pending_tasks`
- 该任务是否满足 `requires`
- 该任务是否已重复执行
- `fsm.step` 是否小于 `scheduler.max_steps`

校验通过后：

1. 从 `pending_tasks` 移除该任务；
2. 设置为 `current_task`；
3. 将 `task_key` 加入 `dedup.visited_task_keys`；
4. `fsm.state = waiting_for_tool`；
5. `fsm.step += 1`。

### 构造工具调用

工具参数由 `context + current_task.scope` 合成。`build_tool_args` 会先执行完整 `validate_analysis_state(state)`，再校验 `current_task.requires`；即使调用方绕过 `select_task_by_llm` 直接写入 `current_task`，非法状态、缺失顶层字段或缺失 `charge_item_code` 等必需字段也会在构造工具参数阶段被拦截。构造出的 `model_args` 不包含 `account_id`；只携带账期、定位维度、过滤条件和计费项等业务参数。

| `task_type` | RCA tool |
|---|---|
| `locate_product` | `QueryCostChangeDimensions(dimension=product)` |
| `locate_charge_item` | `QueryCostChangeDimensions(dimension=charge_item_code, filters=current_task.scope)` |
| `locate_instance` | `QueryCostChangeDimensions(dimension=instance_no, filters=current_task.scope)` |
| `locate_region` | `QueryCostChangeDimensions(dimension=region_code, filters=current_task.scope)` |
| `locate_project` | `QueryCostChangeDimensions(dimension=project, filters=current_task.scope)` |
| `locate_amount` | `QueryCostChangeAmountComponents(charge_item_code=current_task.scope.charge_item_code, filters=remaining_scope)` |
| `decompose_charge_item` | `QueryCostChangeDrivers(charge_item_code=current_task.scope.charge_item_code, filters=remaining_scope)` |

`locate_charge_item` 的 `product` 仅是可选 scope 字段；当用户询问全局计费项定位时，可直接执行 `QueryCostChangeDimensions(dimension="charge_item_code")`。

### 工具成功返回

1. `fsm.state = interpreting_result`；
2. LLM 解释工具结果；
3. LLM 生成 `findings`；
4. LLM 生成下一批候选任务；
5. Runtime 对候选任务生成 `task_id/task_key`；
6. Runtime 对候选任务去重；
7. Runtime 将当前任务移入 `completed_tasks`；
8. Runtime 将合法候选任务加入 `pending_tasks`；
9. Runtime 清空 `current_task`；
10. LLM 更新 `progress_signals` 和 `stop_condition.llm_decision`；
11. Runtime 更新 `stop_condition.runtime_guardrail` 和 `stop_condition.final`；
12. 如果 `final.should_stop = true`，`fsm.state = ready_to_answer`；否则 `fsm.state = running`。

`llm_interpretation` 必须非空；如果调用方漏传，Runtime 抛出 `AnalysisStateError`，不会完成当前 task，也不会生成 `completed_tasks/findings/candidate_tasks`。工具成功后的状态迁移必须依赖 LLM 对工具结果的解释。

为避免沿用上一轮停止判断，每次 success interpretation 都应显式输出完整 `llm_decision.should_stop`、`llm_decision.answer_readiness` 和 `llm_decision.reason`。Runtime 兼容缺失字段，但会在 `fsm.last_transition.warnings` 中记录 `llm_interpretation_missing_llm_decision`、`llm_interpretation_missing_should_stop`、`llm_interpretation_missing_answer_readiness` 或 `llm_interpretation_missing_stop_reason` 等 warning，并把缺失的 `llm_decision.reason` 标记为 `llm_decision_missing_in_current_interpretation`，避免将上一轮判断误当作本轮的新判断。

### 工具失败返回

1. Runtime 将当前任务移入 `failed_tasks`；
2. 如果失败可重试且未超过重试上限，Runtime 可生成重试任务加入 `pending_tasks`；
3. Runtime 清空 `current_task`；
4. LLM 根据已有 `findings` 判断是否可降级回答；
5. Runtime 更新硬护栏；
6. 如果 `final.should_stop = true`，`fsm.state = ready_to_answer`；否则 `fsm.state = running` 或 `blocked`。

重试任务会保留上一次失败摘要：`last_failure_reason` 记录失败原因，`evidence_summary` 使用 `retry after previous failure: ...` 格式，便于 LLM 再次选择 retry task 时理解重试背景。

## 停止判断规则

LLM 可以停止，当满足以下任一条件：

1. 用户问题的核心意图已经被回答；
2. 已形成至少一个可直接用于最终回答的 finding；
3. 继续调用工具大概率只会补充细节，不会改变主结论；
4. 剩余 pending task 对当前用户问题不是必要分支；
5. 工具失败或数据不足，但已有信息足以给出带限制的回答。

LLM 不应停止，当出现以下任一情况：

1. 用户问“为什么涨”，但当前只定位到“哪里涨”；
2. 只找到产品主因，但没有计费项或驱动解释；
3. 当前 finding 只是中间定位结果，不能支撑最终回答；
4. 仍有用户明确关注的 pending task 未分析；
5. 工具结果显示多个显著分支，但当前结论只覆盖其中一个，且这些分支对回答用户问题有必要。

按 `question_type`：

- `dimension_locate`：完成用户要求的主维度定位后通常可以停止。
- `generic_rca`：通常需要形成“主因产品/对象 → 主因计费项 → 驱动因素”的解释链路。
- `driver_decompose`：目标对象的驱动因素解释清楚即可停止。
- `amount_breakdown`：金额拆分足够解释差异来源即可停止，不一定需要 QueryCostChangeDrivers。

## 状态持久化

标准入口是 `run_rca_workflow.py init/step/resume`。`init` 创建独立的 `state-file`；`step`、`resume` 从该文件读取业务状态。任务选择与结果解释经 `analysis_state.py` 校验并完成迁移后，由编排器原子写回。

`resume --tool-result-file` 先保存工具结果，再请求 LLM interpretation；消费 interpretation 时才更新任务、findings 和停止条件。`fsm.last_transition` 保留最近一次状态变化及任务过滤原因，是业务状态的一部分。

Agent 只填写 hook response，不得手工修改状态文件或绕过编排器串联底层状态命令。

## Runtime 辅助函数

`scripts/analysis_state.py` 提供以下辅助函数：

- `initialize_analysis_state(user_query, parsed_context)`
- `validate_analysis_state(state)`
- `select_task_by_llm(state, llm_decision)`
- `build_tool_args(state)`
- `apply_tool_success(state, tool_result, llm_interpretation)`
- `apply_tool_failure(state, error, llm_interpretation)`
- `generate_task_key(task_type, scope)`
- `materialize_candidate_tasks(state, candidate_tasks, parent_task_id=None)`：将 LLM candidate 补齐为合法 task 对象，并完成前置条件过滤与 `task_key` 去重
- `dedup_tasks(state, candidate_tasks)`：仅按 `task_key` 去重，保留兼容；新调用方不要用它生成 `pending_tasks`
- `update_runtime_guardrail(state)`
- `finalize_stop_condition(state)`

这些函数只负责状态一致性与硬护栏，不替代 LLM 做业务判断。

业务执行入口使用 `run_rca_workflow.py init/step/resume`。`analysis_state.py` 底层 CLI 保留给开发者调试与测试，不作为 Agent 的另一套工作流。查看运行状态时直接读取编排器写入的 state-file。

## 端到端状态流转示例

1. 用户问“为什么 6 月费用上涨？”；Agent 调用 workflow init，Runtime 初始化 `pending_tasks=[locate_product]`。
2. LLM 选择 `task_001`，Runtime 将其迁移到 `current_task`，`fsm.state=waiting_for_tool`。
3. Runtime 构造 `QueryCostChangeDimensions(dimension="product")` 参数，编排器输出 `execute_tool.tool_command`。
4. 工具返回 ML / ECS 等产品贡献结果；LLM 解释结果，生成 `dimension_locate` finding 和 `locate_charge_item|product=ML` 候选任务。
5. Runtime 调用 `apply_tool_success`，写入 `completed_tasks`、`findings`、`pending_tasks`，由编排器持久化到 `state-file`。
6. 下一次 workflow 调用读取最新 `state-file`，选择下一任务并继续 ML 分支的 `QueryCostChangeDimensions(charge_item_code)`。
7. 当 LLM 判断 findings 已足够回答时，在 interpretation hook 中返回 `llm_decision.should_stop=true`；Runtime 得到 `final.should_stop=true`，编排器请求 draft_answer，消费答复后输出 `action=final`。
