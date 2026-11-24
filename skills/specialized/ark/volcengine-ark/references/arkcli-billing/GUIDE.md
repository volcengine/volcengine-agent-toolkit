---
name: arkcli-billing
version: 1.1.3
description: "查询火山引擎 ARK 拆分账单明细（结算金额、Token 用量计费），支持按账期月、月范围、Endpoint、API Key、产品编码等维度过滤。当用户问账单、花了多少钱、对账、账期、按 EP / API Key 拆账、按产品拆账、月度账单、出账明细时使用。注意 billing 跟 usage stats 不同：stats 出推理量（近实时），billing 出结算金额（T+1 出账，财务口径）。"
metadata:
  requires:
    bins: ["arkcli"]
  cliHelp: "arkcli billing list --help"
---

# arkcli billing

**执行前 MUST 读取** [`../arkcli-shared/GUIDE.md`](../arkcli-shared/GUIDE.md) (认证 / 全局规则) 和 [`references/arkcli-billing-list.md`](references/arkcli-billing-list.md) (参数详解)。

## 适用场景

- 查询某账期月或月范围内的拆分账单明细(结算金额 / Token 用量)
- 按 Endpoint、API Key、产品编码、账单类型过滤拆账行
- 月度 / 季度 / 年度对账
- 排查"这个 EP / 这把 key 花了多少钱"

## 业务定位 — billing vs usage stats

| 维度 | `usage stats` | `billing list` |
|---|---|---|
| 数据源 | ARK BFF 推理聚合 | 火山计费中心拆账 |
| 时效 | 5–30 分钟延迟 | T+1 出账 |
| 单位 | Token / 请求数 | CNY 金额 |

想看"用了多少 token"→ [`arkcli-usage`](../arkcli-usage/GUIDE.md);想看"花了多少钱"→ 本 skill。

## Step 0：确认账单口径与范围

先分清“已结算金额”与“Token / 套餐额度消耗”，后者交给 Usage，不用单价乘估算 Token 冒充账单。用户只查某个 Endpoint、Key 或订阅时，仅查其明确范围；`profile.type=platform` 不能证明没有套餐。

身份上下文已知则复用，确需核实时按共享宿主协议使用 `arkcli auth whoami --format json`；托管宿主的注入协议优先。普通账单查询不调用可能同步/回写 Key 的 `profile show/list/keys list`，不为了补全账单切换身份。

- “我的调用用了多少钱 / 我的用量折合多少人民币”按本人 Key 归属查询，显式使用 `--mine --mine-by=apikey`；“我部署的接入点花了多少”才选 `--mine --mine-by=endpoint`。只说“我花了多少”而未点名资源时，可按本人 Key 归属解释并在输出开头说明这一口径，不把 CLI 默认 Endpoint 视图直接称作本人的全部消费；“我想查询豆包调用次数及费用”中的“我想查询”只是请求主语，不等于本人资源归属限定。先按用户点名的模型/产品、已生效的身份与 Project 查询并说明范围；不能擅自追加 `--mine` 把问题缩成本人创建的 Endpoint。用户要求订阅类账单时显式 `--product ark_subscription`，并解释其账号/订阅范围，不称为个人 Endpoint 用量。
- “整个账号花了多少”才使用账号查询；Project 筛选按本次实际上下文说明，不能为补数擅自清空 Project、换 Profile 或换身份。
- 每条 `billing list` 必带 `--start <YYYY-MM>`，跨月加 `--end <YYYY-MM>`。账期是月份，不是 Usage 的日级参数；T+1 及当期未出账部分必须披露。
- “本周”与“最近 N 天”先读取真实运行日期，按用户明确的时区与周起点计算；未指定时说明采用的时区、本周按周一至当天，近 N 天按当天向前 N−1 天。用日历工具计算闭区间和星期，不心算、不抄历史日期。冻结起止、归属和产品范围；跨月覆盖全部账期。T+1尚未出账不能把本周扩大为上一周或近7天来凑金额。
- `BillingDate` 在 `--interval day` 结果中也可能缺失。先检查真实行结构；有有效日期才过滤原区间，缺失时按参数详解的逐日查询流程补查并保留请求日期来源，不能把缺日期行过滤成零。部分日期失败或无法证实覆盖时如实说明缺口，不把整月金额说成本周金额。
- 返回数组是 `items`，不是 `Items`；使用 `--output FILE` 后从文件读取完整记录，stdout 的 `items:null` 只是摘要形式。先校验退出状态、`returned`、`total_records`、`partial_failures` 和 `is_truncated`。日期、金额字段都须按实际输出判断，缺失不等于零；完整成功的空结果与解析失败、请求失败、截断分开报告。

### 用量与费用同时回答时

- `usage stats` 的 `totals` 是本次全部返回记录的合计。用户点名模型/品牌时按实际模型身份筛选记录后重新合计；有明确版本可用 `--model`，不能把包含其他模型的总请求数直接叫作“豆包次数”。原始数值先计算，再统一展示单位和舍入。
- 账单 `Count` 与同一行的 `Unit`、`ChargeItemCode`、`ConfigurationCode` 绑定；例如“326.7 千 Token”才换算为 326,700 Token。金额、视频计量、Token 和请求次数分别呈现，不能把某一计费项的 Count 从全模型 usage Token 中减去，再把差额归给剩余请求。
- 只有日期、模型/产品、资源归属、单位和已出账覆盖都相同，才逐项对账；否则分列推理统计与已结算金额，披露延迟/范围差异。未出账部分可以给有来源的估算，但清楚标成估算，不能把估算当实际账单或从一次空列表宣称费用为零。

### 汇总交付：一份记录，一次本地计算

1. 将本轮完整返回落盘，记录查询范围与时间。筛选后的同一份记录同时用于总量、Top N、其余项、比例和卡片；只为排序、求和或排版不要再次请求服务。需要刷新时整组更新，不把新总量与旧明细拼接。
2. 用本地程序一次产出所有展示数值：请求数用精确整数，金额用Decimal等十进制运算，最后统一舍入。“其余”从未展示的记录直接求和，不能心算补数，也不能用来自另一查询的总量减Top N。缺少完整明细时说明无法核对，不凑差额。
3. 输出前断言同范围的总量等于已展示分组与其余项之和，分组个数也相符；舍入后的金额有尾差时单独说明。文字、表格和卡片直接复用计算结果。出现矛盾时先修本地计算或说明快照差异，不用“约”掩盖一个未经计算的精确数字。

## 快速决策

| 用户问 | 命令 |
|---|---|
| 我的调用 / 用量这个月花了多少 | `arkcli billing list --start <YYYY-MM> --mine --mine-by=apikey`；按本人当前 Active Key 归属，并披露历史覆盖限制 |
| 我部署的接入点这个月花了多少 | `arkcli billing list --start <YYYY-MM> --mine --mine-by=endpoint`；可能包含他人调用这些接入点的费用 |
| 整个账号花了多少 / 公司账号 / 整体 (无主语自指) | `arkcli billing list --start 2026-05` (账号维度全量) |
| 这个 EP 花了多少 | `arkcli billing list --start 2026-05 --endpoint ep-...` |
| 这把 key 花了多少 | `arkcli billing list --start 2026-05 --apikey ark-...` |
| 账号下每个 EP / key 各花了多少 | `--split-dim endpoint` 或 `--split-dim apikey` |
| 按天 / 按每条结算明细 | `--interval day` 配 `--day YYYY-MM-DD`,或 `--interval detail` |
| 过去 N 个月对账 | `--start ... --end ...` (闭区间, 最多 24 个月) |
| 看 Agent Plan / Coding Plan 订阅类账单 | 显式 `--product ark_subscription` (默认查询不含) |

### 按用户意图选择本人账单归属

`--mine` 只表示按当前身份拥有的资源归集；`--mine-by` 决定是哪种资源。CLI 默认仍是 `endpoint`，这不是“本人调用消费”的同义词，也不能仅因 Usage 默认相同就沿用到费用问题。

1. 先确定用户明确的资源与费用意图，再显式选择维度。Endpoint 视图查询本人创建的接入点账单；API Key 视图查询当前可列出的本人 Active Key 的账单。两组资源和金额可以不同，同一消费也可能同时体现在两个视图，不能相加或互相替代。
2. 输出开头说明维度、身份/Project、日期与已出账覆盖。按 Key 归属不等于识别了实际发起请求的人；共享 Key 的调用也按 Key 归集。源码仅筛选当前 Active Key，不能据此保证覆盖历史已停用、删除或不再归属本人的 Key。
3. 返回有数据也先检查 `partial_failures`、`is_truncated` 和实际日期范围，再用同一份完整记录汇总。不能因某一维度先查到数据，就认为它一定回答了用户要的口径。
4. 成功但 `items` 为空，或明确报告本人无该类资源时，报告该口径未查到匹配账单，并核对日期、出账延迟和覆盖限制。请求/鉴权失败与空数据分开。如果原意是本人调用费用、先前误用了 Endpoint 维度，可以纠正为 Key 维度，并明确说明这是归属口径纠正；不能把它叫作相同范围的重试。
5. 用户已指定某个 Endpoint、Key、订阅或明确归属维度时，保留其范围；空结果不自动替换为另一组资源。用户要求对照两种归属时分别标注查询与合计。始终保留已授权的账期、日期、产品和 Project，不删 `--mine` 扩成全账号，也不切 Profile 或身份补数。

## Agent 关键纪律

- **保留 stderr**：首次查询和用于得出结论的查询不得加 `2>/dev/null`。账号全量 scope 提示、软截断 WARN 与部分失败原因都可能只写 stderr；需要解析 JSON 时只接管 stdout，或优先使用 `--output FILE`。
- **`is_truncated=true` 时停下问用户,不要自动决策** — 撞 cap (preflight 模式下 items 不返,只有 metadata + partial_failures + stderr 警告) 是规模信号不是错误。先把 `total_records` 和 `partial_failures[*].total` 报给用户,列出 4 条出路,**等用户明确选一个再继续**。选哪条要看用户当前任务意图(对账 / 排查 / 导出),agent 不要替用户拍。**永远不要 sum items 当总额**(items 可能为空或部分):
  - 想要全量明细 → `--output FILE` (落盘 stdout 不爆;自动放宽 cap 到 300k 行)
  - 只要总金额 → `--split-dim apikey|endpoint` (服务端聚合到几十行)
  - 缩到一个资源 → `--endpoint <ep-...>` / `--apikey <ark-...>`
  - 强行流进 stdout → `--page-limit=N` (N 见 partial_failures.reason 建议;mind context size)
- **`--limit/--offset` 在 fan-out 时是 per-fan-out 各 N 行** (`--end` 跨月或 `--mine` 多资源时), `partial_failures` 标 `reason="windowed sample"`, agent 据此知 returned ≤ limit × fanout_count
- **金额是 CNY 字符串** — JSON 数字精度有损,加和 / 比较用 decimal 库,不要 `parseFloat`
- **月初对完整账期时查前一个月** — T+1出账，当月当日数据可能不全；用户明确问本周或当期时保留其日期范围，不能改成上月。
- **`--mine` ≠ `PayerID`** — `--mine` 按 IAM 子用户过滤资源,`PayerID` 是财务托管 owner 账号 ID,单账户场景手撸 `PayerID` 是 no-op (= 全账号查询)。默认 `--mine-by=endpoint`(infra ownership,对齐 usage stats),要看 cost causation (我的 key 在花钱) 显式 `--mine-by=apikey`
- 默认 scope = ARK 推理 / Agent 9 个支持 API Key 分账的产品(**不含 `ark_subscription`**,要看订阅类显式 `--product ark_subscription`) + profile.project 自动注入(若 profile.project 是具体 id 如 `auto-test`,自动按 project 过滤;`default`/账号全部资源哨兵/空跳过 = 真账号全量;stderr 出软提示)。要强制账号全量传 `--project=` (空值清空默认)

## 常见降级

- 鉴权错误 / SSO 失效 → [`../arkcli-auth/GUIDE.md`](../arkcli-auth/GUIDE.md)
- 想看推理量 (token / 请求数) → [`../arkcli-usage/GUIDE.md`](../arkcli-usage/GUIDE.md)
- 想看模型 / 套餐价格目录 → [`../arkcli-pricing/GUIDE.md`](../arkcli-pricing/GUIDE.md)

## 命令一览

| 命令 | 说明 |
|------|------|
| [`billing list`](references/arkcli-billing-list.md) | 拆分账单明细查询(结算金额 × Token 用量) |
