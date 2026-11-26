---
name: arkcli-usage
version: 1.3.5
description: "查询平台 Token/请求数、套餐额度快照、Agent Plan 按模型明细和团队席位用量。已发生调用的人民币金额、实际花费、用量折算费用优先转 arkcli-billing；目录询价转 pricing，明确要求按单价估算时才组合 usage 与 pricing。Coding Plan 只有额度快照，不提供按模型明细。席位列表/分配/轮换 Key 转 arkcli-plans；TTS/ASR 用量不支持查询。"
metadata:
  requires:
    bins: ["arkcli"]
  cliHelp: "arkcli usage stats --help"
---

# arkcli usage

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../arkcli-shared/GUIDE.md`](../arkcli-shared/GUIDE.md),其中包含认证闸门、配置排查与共享安全规则**
**CRITICAL — `usage stats` 在执行之前,务必先用 Read 工具读取 [`references/arkcli-usage-stats.md`](references/arkcli-usage-stats.md),禁止直接盲目调用命令。**
**CRITICAL — `usage plan` 在执行之前,务必先用 Read 工具读取 [`references/arkcli-usage-plan.md`](references/arkcli-usage-plan.md),禁止直接盲目调用命令。**
**CRITICAL — `usage plan-details` 在执行之前,务必先用 Read 工具读取 [`references/arkcli-usage-plan-details.md`](references/arkcli-usage-plan-details.md),禁止直接盲目调用命令。**
**CRITICAL — Coding Plan / Coding Plan Team 当前不提供按模型套餐明细。这类问题只能用 `usage plan --product coding-plan`（团队版用 `--product coding-plan-team`）给 quota 快照并明说能力边界；禁止改跑 `usage stats` 后把 platform / Endpoint Token 统计冒充 Coding Plan 套餐按模型明细。**
**CRITICAL — 上述 Coding Plan 问题在本轮执行 `usage plan` 并说明边界后就停止。不主动追加 Endpoint / platform `usage stats`，因为它无法归因为 Coding Plan 套餐明细；只有用户在知道两者不同后另行明确要求「再看 platform / Endpoint 用量」，才开新查询。**
**CRITICAL — `usage balance` 在执行之前,务必先用 Read 工具读取 [`references/arkcli-usage-balance.md`](references/arkcli-usage-balance.md),禁止直接盲目调用命令。**
**CRITICAL — `usage seats` 在执行之前,务必先用 Read 工具读取 [`references/arkcli-usage-seats.md`](references/arkcli-usage-seats.md),禁止直接盲目调用命令。**

> **数据时效(务必先看):`usage stats` 走的是上游 BFF 的聚合管道,数据有 5–30 分钟延迟,定位为「日级 / 聚合分析」。** 不要把它用于实时预算监控、限流、实时告警等需要秒级精度的控制场景——这类场景请直接读 `+chat` / `+gen` 等推理命令返回里的 `.usage` 字段(per-request、零延迟,详见 [arkcli-chat](../arkcli-chat/GUIDE.md) 与 [arkcli-gen](../arkcli-gen/GUIDE.md))。

> **语音模型边界**：TTS / ASR / 配音 / 朗读 / 播客 / 音色 / 实时语音交互，或 `doubao-seed-tts-*` / `doubao-seed-asr-*` / `seedasr-*` 等广场语音模型，当前在 arkcli 只支持 `models search` 发现。不要用 `usage stats --model`、`usage plan-details` 或套餐/余额命令回答语音模型用量；直接说明 arkcli 不支持查询语音模型费用或用量。

> **stats / plan / plan-details / balance 区分:**
> - `stats` 出"按 token 计费的 inference 用量"(任何身份,5–30 分钟延迟)
> - `plan` 出"订阅套餐的 quota 快照"(AgentPlan / CodingPlan 个人版 + 团队版的"我用了几成 / 几号刷新")
> - `plan-details` 出"AgentPlan 按模型 / 套餐内外的时间序列调用明细"(AgentPlan 个人版 + 团队版,CodingPlan 没有按模型 endpoint)
> - `balance` 出"还剩多少 X"(余额视角,`--type free-quota / media-asset / plan` 三选一)
> - `seats` 出"团队席位**用量** admin 视角"(每个 seat 用了多少 / 套餐百分比;**只是用量视图**)。**席位的列表 / 绑定 / 分配 / API Key 轮换** 走 [`arkcli-plans`](../arkcli-plans/GUIDE.md) 的 `plans team seat-list / seat-assign / rotate-apikey`。
>
> 用户问「我的套餐还剩多少额度」→ `plan` 或 `balance --type plan`(后者输出更精简);「我哪个模型用得最多」→ Agent Plan 用 `plan-details`，Coding Plan 只能用 `plan` 给 quota 快照并说明不支持按模型拆分;「我今天用了多少 token」→ `stats`;「我还剩多少免费额度 / 媒资库容量」→ `balance`;「**每个 seat 用了多少 / 团队席位用量分布**」→ `seats --with-usage`(纯管理类:谁绑了哪个 seat / 列出席位 / 分配席位 / 轮换 key → `arkcli-plans`)。

## Step 0：先分金额、数量与额度，再确认身份

先看用户要交付的单位；句子中出现“用量”不决定查询入口：

- **已发生用量折算人民币 / 实际花费 / 应付账单**：先读取 [`arkcli-billing`](../arkcli-billing/GUIDE.md)，按其日期、个人归属和 T+1 规则查实际应付。此分支在任何 `usage stats` 或价格查询之前执行。用户同时要调用量时再另查 Usage，分别交付。
- **模型 / 套餐目录多少钱、每 Token 单价**：读取 Pricing 做询价，不查个人账单或用量。
- **明确要求目录单价估算 / 预算预测**：才读取 Pricing，与用户指定范围的调用量组合；结果标“估算”，披露免费额度、折扣、缓存及结算差异。已有实际费用问题遇到 T+1 未出账时，报告未结算部分，不自动改成估算金额。

用户已明确套餐名称时，直接用 `usage plan --product <plan>`；Agent Plan 按模型明细用 `usage plan-details --product <agent-plan|agent-plan-team> --start <日期>`。订阅属于账号/子用户，**不是由 active profile.type 决定**；platform profile 不等于没有套餐，也不需要为查询先切成 plan profile。

- 平台 Token / 请求数 → `usage stats --start <日期>`；用户说“我的”时首条就带 `--mine`，追加 `--by model|endpoint|apikey` 不能删掉范围限制。
- 套餐额度 → `usage plan` / `usage balance --type plan`；Agent Plan 明细 → `plan-details`；Coding Plan 只有 quota 快照，解释限制后停止，不补查平台桶冒充套餐明细。
- “我的用量”未指明口径时，结合本轮上下文确认是平台 Token 还是套餐额度；仍有歧义就问这一项。只有用户明确要合并查看时才查多个桶，并分开报告，不能把百分比、AFP、Token 直接相加。
- `subscribed:false` 只表示当前身份下该 SKU 没查到订阅，不证明其他身份无订阅，不触发自动切身份或平台查询。

身份核对遵守当前宿主的共享协议；已有执行上下文可复用，缺少摘要且确需核实时用 `arkcli auth whoami --format json`。普通查询不调用可能同步/回写 Key 的 `profile show/list/keys list`。确需另一身份时先确认目标，不能静默切 Profile、Key、Project 或账号范围。

**时间与交付：** `stats` / `plan-details` 必带 `--start`，没有 CLI 默认“近 7 天”；按用户时间词补齐 `--start/--end`，无日期时说明按今天查。长窗口按当前 reference 的限制分片，边界不重叠，保留用户原请求范围；无法覆盖的日期明确标注，不静默改成最近 30 天。回答同时标明口径、身份/范围、时间窗和数据延迟。

### 数值与范围交付

- `usage stats` 输出的顶层 `totals` 汇总本次所有返回记录；点名模型/品牌时按实际模型身份筛选并重新计算，不能把混合模型合计全归给目标模型。“我想查询”只是请求主语，不自动收窄为本人创建的资源；“我的用量/我创建的 Endpoint”才采用本人归属，且不改当前身份和 Project。
- 套餐逐项以 `items[].product/edition/tier/seat_id` 标识身份，以同一项 `periods[].label/used/total/percent/reset_at` 生成正文和卡片；提交前比对二者数值、单位和周期。团队版和个人版不能因为档位名相同就复用额度；静态价格/套餐目录不能覆盖实时 `total`。
- 排查套餐限额或交付额度快照时，按“套餐/版本/席位 → 周期 → 已用/总额/余量（原单位） → 已用百分比 → 重置时间（含时区）”逐项交付本轮返回值；卡片无法完整承载时用 Markdown 保留这些字段。只有同周期、同单位的真实 `used/total` 才计算余量；缺字段写未返回。不能只给百分比表而省略已有的绝对余量与重置时刻，也不能只摘一个健康窗口就宣称全部配额健康。
- Coding Plan 仅有百分比、缺少 `used/total` 时只展示已有百分比与重置时间，不推算绝对额度、次数或 Token。缺字段、失败项和零消耗分开，不从另一个 SKU 填数。历史限额报错与当前快照分开标明，不能把当前未耗尽反推为历史报错不可能发生。

### 限额报错：历史事实、当前快照与恢复条件

用户贴出 `AccountQuotaExceeded` 或带重置时刻的套餐限额报错时，先保留原错误码、时间和已知套餐；需要错误目录解释时可转 [`arkcli-doctor`](../arkcli-doctor/GUIDE.md)，近似错误码不能冒充原码。用 `usage plan` 查当前快照，按上方字段交付；查询失败或某桶失败时保留未知。

- 原重置时刻已过去，只能说明那次窗口已经过去；当前快照未耗尽，只能证明本轮所查身份和套餐的额度状态。仍有新报错时需要它的时间、错误码、套餐/调用上下文；没有客户端日志，不把“自动重试旧请求”“客户端缓存”当成已知原因，也不由额度正常保证调用必然成功。
- 恢复建议按实际 `product/edition` 区分。等待时引用对应窗口真实 `reset_at`；升配时转 [`arkcli-plans`](../arkcli-plans/GUIDE.md) 并按该套餐文档说明生效条件，不把 Coding Plan 的时效规则推广到 Agent Plan。Agent Plan 文档中的“超额后付费”是有资格、服务开通和计费条件的恢复选项，不能笼统说所有套餐“只能等待”；Coding Plan 不自动继承该选项。
- `usage plan` 的额度字段和 `plans get` 的订阅状态都不包含超额后付费开关，不能由这些返回值宣称已开启或已关闭。说明该选项会产生额外费用、需用户自行决定；本轮排障不启用开关、不升配、不切换收费路径，也不发送推理请求试探额度是否恢复。当前未超限时无需执行恢复操作。

### 空结果与归属排查

1. 区分命令失败、成功但空、存在 records 但合计为零；三者不能互相代替。
2. 核对日期/时区、聚合延迟、所选口径、身份以及实际生效的 Project/过滤条件。近期记录未进入聚合不代表调用未发生；账号全范围不等于有所有资源权限，也不能先断言是 Project 隔离。
3. Volc 个人平台统计仅在成功为空，或 CLI 明确报告本人没有 Endpoint 时，保留原日期/过滤条件改查 `--mine --mine-by=apikey`；已显式选 API Key 维度就不重复。鉴权、权限、网络错误不是空结果。CLI 提示 `omit --mine` 只列出另一种命令范围，不代表用户同意扩大查询。第二层为空或资源筛选失败时停在本人范围，分别报告空结果或未能取得结果；仅在用户另行明确要求后查询账号全量。无法获得新回复时保留范围和未知项，不用他人用量补齐。
4. 平台 `records` 的 `ModelEndpoint` 可交给 `infer endpoint get <id>`；`AuthToken` 是 Key 掩码标识，可用 `apikey.list` 的元数据核对归属，后缀有冲突时报告歧义，不取明文、不轮换 Key。
5. Agent Plan `plan-details` 不提供 Endpoint / API Key 级归属，查到模型/Harness 消耗即到边界；Coding Plan 无模型/Harness 明细。不能跨口径拼出不存在的调用归属，也不因 CLI 报错改用记忆/检索结果充当账号数据。

## 适用场景

- 查看当日或指定日期范围的推理用量(**接受 5–30 分钟延迟**)
- 看订阅套餐(AgentPlan / CodingPlan)的配额消耗 / 重置时间
- 看 AgentPlan 套餐内 vs 套餐外的按模型拆分明细
- 按模型、接入点、API Key 维度分组统计(stats)
- 分析 Token 消耗趋势、出对账报表
- **不适用于语音模型用量**：用户问 TTS / ASR / 语音模型用了多少、剩余额度、调用次数时，不执行本 skill，转 `arkcli-models` 说明只支持广场发现

## 业务定位

- 本 skill 对应"看存量调用结果和消耗"的场景,是**离线 / 准实时**分析入口
- 它通常发生在两类后置链路之后:
  - Endpoint 已经存在,想按 endpoint 看使用情况
  - 模型已经在被调用,想按 model / API Key 分析消耗
  - 或:订阅了套餐,想看额度还剩多少
- 它不是创建 Endpoint 的入口,也不是试用模型的入口
- **它不是实时预算 / 限流 / 告警的数据源**——实时控制请走 per-request `.usage` 字段(见上方 banner)

## 快速决策

- 用户问"我的套餐还剩多少 / 用了几成 / 几号刷新 / 我有几个套餐":
  - `arkcli usage plan`(默认探所有 4 个 SKU:personal × 2 + team × 2,subscribed 桶才下发 usage 请求)
  - `arkcli usage plan --all`:不探订阅,4 桶全跑(诊断 / Excel)
  - `arkcli usage plan --product=X`:跳过探测,单查
  - **跟 `balance --type plan` 是同一份数据**;`usage plan` 输出完整(带 `subscribed` / `updated_at`),`balance --type plan` 精简(去掉元字段)。一般默认走 `usage plan`,只有用户明确把套餐余额跟"免费额度 / 媒资库容量"一起对账时,才走 `balance --type plan`(三 type 一起跑节省心智)
- 用户问"我哪个模型用得最多 / 套餐内套餐外各占多少 / 团队某个子用户用得多":
  - `arkcli usage plan-details --start <YYYY-MM-DD>`（Day 粒度，Agent Plan personal；显式补日期）
  - `arkcli usage plan-details --product=agent-plan-team`(团队版,自动找 caller seat 或显式 `--seat <id>`)
  - **Coding Plan 例外**：不执行 `plan-details` 或 `stats`；只执行 `arkcli usage plan --product coding-plan`(团队版用 `coding-plan-team`)，并明确该结果只是 quota 快照、不是本周按模型明细，然后停止。用户未另行要求 platform / Endpoint 用量时，不主动补跑 `usage stats`。
- 用户问"我的用量 / 我今天用了多少 token / 我的 endpoint 消耗":
  - 先按 Step 0 确定口径；明确的平台 Token / Endpoint 问题直接查下述平台桶，不因 profile.type 自动追加套餐查询。
  - 如果用户点名的是语音模型或 TTS / ASR 场景 → **不要继续查 usage**；当前 arkcli 只承认语音模型广场发现，不支持语音模型用量查询
  - **火山:** 先 `arkcli usage stats --start <YYYY-MM-DD> --mine`（默认 endpoint 维度）
    - 返回 `data_count > 0` → 直接从 `totals` 取合计
    - 返回 `data_count=0`（用户没有 Endpoint 或近期未通过 Endpoint 调用）→ 立即重试 `arkcli usage stats --start <YYYY-MM-DD> --mine --mine-by=apikey`
    - 不自动退化为账号全量；第二层也成功为空时，可询问用户是否另查整个账号。明确同意后按 [stats 的第三层流程](references/arkcli-usage-stats.md#空结果的完整排查链) 保留其他参数、只移除 mine 限定，并标明“账号全量，可能包含其他用户”。这不是个人用量，也不授权切身份。
- 用户问"我每个 APIKey 用了多少":
  - **火山:** `arkcli usage stats --start <YYYY-MM-DD> --mine --mine-by=apikey`,从 `records[].AuthToken` 拆分
- 用户问"我账上还有多少免费 token / 模型免费额度 / 媒资库还能存多少":
  - `arkcli usage balance --type free-quota`(模型免费推理额度)
  - `arkcli usage balance --type media-asset`(素材库容量)
- 用户问"团队席位**用了多少** / 每个 seat 消耗 / 套餐百分比 by seat"(admin 用量视角):
  - `arkcli usage seats --product agent-plan-team --with-usage`(列席位 + 每个 seat 的 AFP 用量)
  - 不带 `--with-usage` 也行,但只有基础元数据,没有用量数字
  - **路由分工**:本命令**只**回答"用量",不负责 seat 管理。"**列席位 / 谁绑了哪个 seat / 给员工分配席位 / 轮换席位 APIKey**" 全部走 [`arkcli-plans`](../arkcli-plans/GUIDE.md) 的 `plans team seat-list / seat-assign / rotate-apikey`。Agent 路由这条问句先看动词:**"用了 / 消耗 / 多少"** 留这边,**"绑 / 列 / 分 / 轮换"** 跳过去 plans。
- 数据看起来不对:先查认证和 profile,再怀疑数据本身

## Agent 快速执行顺序

1. 先按 Step 0 选定金额、数量或额度入口；需要核对缺失的身份摘要时遵循共享协议。
2. 先做最小查询,再逐步加时间范围和分组条件
3. 结果异常时,先检查 profile / region / API Key 来源是否正确,再怀疑数据本身
4. 如果用户要按 endpoint 看 usage,最好先确认 endpoint-id 已知

## 常见降级

- 鉴权错误:转 [`../arkcli-auth/GUIDE.md`](../arkcli-auth/GUIDE.md)
- 查询范围或环境不对:转 [`../arkcli-config/GUIDE.md`](../arkcli-config/GUIDE.md)
- 用户其实还没有 Endpoint,只是在准备正式接入:转 [`../arkcli-deploy/GUIDE.md`](../arkcli-deploy/GUIDE.md)
- 用户想看套餐**价格**(不是用量):转 [`../arkcli-pricing/GUIDE.md`](../arkcli-pricing/GUIDE.md)(`pricing plans` 出 catalog 询价,`usage plan` 出 quota 快照,两者是不同视角)
- 用户想看**结算金额 / 账单 / 花了多少钱**(不是 token 用量):转 [`../arkcli-billing/GUIDE.md`](../arkcli-billing/GUIDE.md)(数据源是火山计费中心, T+1 出账; usage stats 是 BFF 推理聚合, 近实时)
- 用户问语音模型 / TTS / ASR 的用量或额度:转 [`../arkcli-models/GUIDE.md`](../arkcli-models/GUIDE.md) 只说明广场可搜与 arkcli 不支持用量查询，不转 pricing / billing

## 命令一览

| 命令 | 说明 |
|------|------|
| [`usage stats`](references/arkcli-usage-stats.md) | 查询推理用量(Token / 请求数,按日 / 小时聚合,按 token 计费的 inference 视角) |
| [`usage plan`](references/arkcli-usage-plan.md) | 查询订阅套餐的额度快照(AgentPlan / CodingPlan,5h / weekly / monthly / session 周期的"用了多少 / 还剩多少 / 几号刷新")。默认探所有 4 个 SKU |
| [`usage plan-details`](references/arkcli-usage-plan-details.md) | 查询 AgentPlan **个人版 + 团队版** 按模型 / Harness 的时间序列调用明细(套餐内 vs 套餐外拆分)。必传 `--start`，`--product=agent-plan-team` 切团队版 |
| [`usage balance`](references/arkcli-usage-balance.md) | 余额视角统一入口 `--type free-quota / media-asset / plan`(模型免费推理额度 / 素材库容量 / 套餐余额) |
| [`usage seats`](references/arkcli-usage-seats.md) | **Admin 视角** 列举企业版套餐下所有席位(SeatID / 绑定子用户 / billing 状态)。子用户调通常 AccessDenied |

## 自然语言触发词表

| 用户怎么说 | 对应命令 |
|---|---|
| "按模型明细 / 哪个模型用得最多 / 模型维度拆分 / 按模型时序 / 套餐内套餐外按模型" | `arkcli usage plan-details` |
| "coding plan 按模型明细 / coding plan 套餐内套餐外" | `arkcli usage plan --product coding-plan`，并明说只支持 quota 快照、不支持按模型时序明细；禁止用 `usage stats` 冒充 |
| "配额还剩多少 / 余额 / 还能用多少 / 用了几成 / 套餐额度" | `arkcli usage plan` 或 `arkcli usage balance --type plan` |
| "免费额度还有多少 / 模型免费额度 / 免费 token" | `arkcli usage balance --type free-quota` |
| "AFP 消耗 / 今日 AFP / 本周 AFP" | `arkcli usage plan`（AFP 就是套餐额度单位） |
| "我的用量 / 我今天用了多少 token / 推理用量 / token 消耗" | `arkcli usage stats --start <YYYY-MM-DD> --mine` |

## 参考

- [arkcli-deploy](../arkcli-deploy/GUIDE.md) -- 先创建 Endpoint,再按 endpoint 看 usage
- [arkcli-pricing](../arkcli-pricing/GUIDE.md) -- catalog 询价(`pricing plans`),跟 `usage plan` quota 快照互补
- [arkcli-shared](../arkcli-shared/GUIDE.md) -- 认证和全局参数
