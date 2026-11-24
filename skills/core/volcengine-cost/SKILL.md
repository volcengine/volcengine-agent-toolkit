---
name: volcengine-cost
allowed-tools: Bash, Read, Write
description: 查询与分析火山引擎账单、费用和当前账户资金状态。适用于账单查询与导出、费用变化分析、账务对账、欠费核实、财务托管关系与付费归属，以及资源包和代金券的状态与抵扣核查。不执行预算、支付、充值、购买或资源变更。
license: MIT
compatibility: Python 3.10+; ve CLI for live queries, with --force support for cost-change APIs. Offline queries and analysis use the Python standard library.
metadata:
  version: "3.0.9"
  openclaw:
    requires:
      bins: [python3, ve]
    envVars:
      - name: VE_CALLER_TYPE
        required: false
        description: Set to ai_agent for Agent executions; inherited by ve subprocesses.
      - name: VE_CALLER_NAME
        required: false
        description: Current Agent product name, supplied from the session context.
      - name: VE_SKILL_NAME
        required: false
        description: Set to volcengine-cost for this Skill's Agent executions.
      - name: VOLCENGINE_REGION
        required: false
        description: Existing ve region context, inherited without changing the global configuration.
      - name: VOLCENGINE_PROFILE
        required: false
        description: Existing authenticated ve profile context.
      - name: VOLCENGINE_ACCESS_KEY
        required: false
        description: Optional ve credential source; use existing authorization without reading or displaying its value.
      - name: VOLCENGINE_SECRET_KEY
        required: false
        description: Optional ve credential source; use existing authorization without reading or displaying its value.
      - name: VOLCENGINE_SESSION_TOKEN
        required: false
        description: Optional temporary ve credential, inherited without reading or displaying its value.
      - name: VOLCENGINE_ENDPOINT
        required: false
        description: Existing authorized ve endpoint context; do not print its value or select another environment.
---

# 火山引擎费用查询与分析

## 明确任务与口径

从用户问题与已有上下文明确期望结果、金额口径、账号与筛选范围、时间轴和比较
窗口、必要字段与粒度、时效要求，以及是否需要文件。复用已确认的信息。

信息足够时直接执行最小足够的只读查询。只有缺少没有安全默认值的关键参数、
口径歧义会改变结论，或继续执行会明显扩大范围时，才说明原因并向用户确认。

## 选择执行流程

按期望结果直接进入对应章节，无需依次执行同一文档中的其他流程。已有适用数据时，
从分析或核验步骤继续。

| 用户目标或上下文 | 指引 | 执行方向 |
|---|---|---|
| 当前账户是否欠费、余额多少 | [账户欠费与抵扣核查](references/arrears-analysis.md)中的“当前账户状态” | 刷新账户资金快照，给出当前状态和必要金额 |
| 谁替当前账号付账、是否财务托管、余额为零为什么仍能使用，或主账号替哪些成员付费 | [财务托管与付费归属](references/financial-relations.md) | 核对关系类型、状态和主子视角；需要金额时再查询对应账单 |
| 哪些产品有未还款、指定账期的欠费明细 | [账户欠费与抵扣核查](references/arrears-analysis.md)中的“已出账未还款金额构成” | 查询指定账期的已出账未还款金额，按产品解释；无需先查询账户状态 |
| 资源包为什么未抵扣、抵扣为什么减少 | [账户欠费与抵扣核查](references/arrears-analysis.md)中的“资源包未抵扣与抵扣变化” | 从目标消费、候选包和必要比较期取证；无需先查询账户状态 |
| 代金券为什么未抵扣、抵扣为什么减少 | [账户欠费与抵扣核查](references/arrears-analysis.md)中的“代金券未抵扣与抵扣变化” | 从目标消费、候选券和必要比较期取证；无需先查询账户状态 |
| 为什么当前欠费，包括资源包或代金券是否造成欠费 | [账户欠费与抵扣核查](references/arrears-analysis.md)中的“当前欠费原因分析” | 先确认账户欠费，再定位相关消费，按线索组合费用变化分析或抵扣核查 |
| 查询账单、明细、分账归属、摊销成本、资源包或代金券状态与抵扣记录，或导出 | [查询与分析](references/cost-query.md) | 根据口径、粒度和必要字段选择 Action，检查结果范围后解释 |
| 筛选、汇总、TopN、跨期比较、费用变化原因分析或可复现分析 | [查询与分析](references/cost-query.md) | 按分析原则处理数据，核验金额、关联关系和比较窗口 |
| 核对两份账务来源或下钻差异 | [聚合对账与观察性比较](references/cost-reconciliation.md) | 按用户目标选择正式对账或保留原始范围的受限比较 |

“费用异常”指跨期变化时走查询与分析，指账单和明细不一致时走对账，指当前账户欠费或
余额为负时走欠费分析。只有解释当前欠费原因时才要求先确认账户欠费。解释费用变化或
欠费原因时，用已查询的账户、产品、用量或金额项支撑结论。区分已确认事实、关联变化和因果
证据；状态快照或同时发生的金额变化只支持其实际证据范围。

组合任务始终继承用户的账号、筛选、时间和金额口径。正式对账保持两侧范围可比；
输入不满足标准对账要求时，可用 `--mode observational` 完成可计算的文件比较，
不重复确认已接受的限制，也不擅自统一范围。数值差异不证明多算、漏算或业务根因。
完成一个阶段后继续处理尚未回答的子问题。

只读取当前流程的指引。接口参数、字段和执行细节以动态契约为准；复用已经加载且
仍适用的契约和结果，不为尚未出现的缺口提前调用 schema、describe 或 help。

## 通用底线

- 使用当前已授权身份和环境，只调用已登记的公开只读 Billing Action；账号筛选同时符合接口
  契约和身份授权。财务关系查询可用同一凭证的只读 `STS GetCallerIdentity` 核实当前账号。
  支付、购买、续费、退订、预算或资源变更不在本 Skill 执行。
- body 只放业务参数。AK/SK/session token 不进入 body、输出、分析文件或日志，本地 profile
  信息不进入回答；使用既有认证配置，不索取凭证或修改全局登录配置。
- 必要字段与请求粒度须匹配。未知字段不猜含义，已屏蔽字段不恢复；金额从原始值进入
  Decimal，保留精度和正负号，缺失值不补零，不同币种和不可比单位分别处理。
- 按统一的 `status`、`message`、`result` 读取工具输出：`success` 只在声明的范围内使用，
  `partial` 只解释已交付部分并按缺口补查或降级，`error` 不形成业务结论。非零退出码仍可能
  交付 partial 结果，不能丢弃 stdout。
- 参数错误读取 `error.details.invalid_parameters` 中的错误参数、局部契约，以及已知参数的实际值；根据任务上下文
  自主决定修正、重新发现或终止，不把局部契约解释为后续执行计划。
- 执行成功不等于范围完整、账期最终或原因已证实。结论继承所有必需输入的范围、时效和失败
  限制；没有获得证据不等于已排除，派生结果不会把局部数据变成全量。手工输入或缺少机器
  证据时只作受限分析，不修改证据扩大结论。
- 结论先行并回答全部子问题；需要文件时交付实际路径，无法继续时说明缺少的证据或能力。
- 不展示内部置信度、状态机、API 名称或执行过程，只有用户明确要求接口、JSON 或复现命令时，才提供技术证据。
