# 账户欠费与抵扣核查

按用户目标选择下列入口，只读取共用约定和所选流程，无需依次执行所有章节。

| 用户目标 | 直接入口 | 必需输入或前置证据 | 完成条件 |
|---|---|---|---|
| “我欠费了吗”“现在欠多少”“余额多少” | 当前账户状态 | 当前授权账户 | 给出当前状态和必要金额 |
| “谁替我付账”“余额为零为什么还能用”“是不是托管账号” | [财务托管与付费归属](financial-relations.md) | 当前身份可见的财务关系，按问题复用余额或账单事实 | 给出关系、付费归属或无法确认的具体原因 |
| “哪些产品欠费”“欠费明细” | 已出账未还款金额构成 | 指定或默认账期 | 给出该账期的产品构成及范围限制 |
| “这个资源包为什么没抵扣”“抵扣为什么变少” | 资源包未抵扣与抵扣变化 | 目标消费；已指定时保留候选包，比较下降时增加基期 | 给出状态、抵扣证据、核查结论或具体缺口 |
| “这张券为什么没抵扣”“抵扣为什么变少” | 代金券未抵扣与抵扣变化 | 目标消费；已指定时保留候选券，比较下降时增加基期 | 给出适用范围、有效期、实际核销记录、账单抵扣证据及结论或缺口 |
| “为什么欠费”“余额为什么是负的”“刚充值为什么还欠费” | 当前欠费原因分析 | 当前账户状态及相关账务证据 | 解释资金构成、消费来源和有证据支持的原因 |

## 共用约定

- 独立查询未还款构成或核查抵扣时，无需查询账户状态；解释当前欠费原因时，先确认当前账户欠费。
- 已有适用数据时从核验或分析继续，仅补齐缺口。子流程沿用用户的账号、对象、时间和金额
  口径；完成后回到原问题，结合子流程结论继续尚未回答的部分。
- 接口选择、请求契约、字段粒度、分页、结果读取及通用分析规则（精度、聚合、跨期可比性和
  证据范围）按[查询与分析](cost-query.md)执行。
  命令路径相对 Skill 根目录；从其他目录执行时使用实际脚本路径，产物写入任务目录。
- 资源包和代金券核查共用“抵扣核查共用输入”。只查库存状态或抵扣记录时，按
  [查询与分析](cost-query.md)取得所需结果即可，无需执行原因核查。
- 按“失败、空结果与证据限制”处理缺口，按“交付”要求回答用户原问题。

## 1. 当前账户状态

使用 `QueryBalanceAcct`，缺少适用契约时读取请求规则与业务指引：

```bash
python3 scripts/cost.py schema --action QueryBalanceAcct --section request --include-guidance
```

然后刷新当前授权账户的资金快照：

```bash
python3 scripts/cost.py query --action QueryBalanceAcct --body '{}'
```

### 1.1 选择下一步

采用工具 `message` 中的账户结论，原始账户字段从 `result` 读取，按用户问题继续：

| 工具结论 | 下一步 |
|---|---|
| 账户欠费 | 按用户问题展示金额，需要解释原因时进入“当前欠费原因分析” |
| 账户不欠费 | 用户还问账务构成或抵扣时继续相应分支 |
| 无法确认账户欠费状态 | 说明 message 中的实际缺口或余额关系不一致 |

### 1.2 账户状态输出

先给结论，再给支持结论的必要金额。

`CashBalance` 是当前现金余额，暂未核销，不是账单中的现金支付金额 `PaidAmount`。
余额公式扣除欠费金额只是计算资金可用额，不表示现金余额已经用于还款或账单已核销。
需要说明支付或结清情况时，依据目标账单的支付与未还款字段，不从账户余额反推核销事实。

- 当前欠费：展示 `AvailableBalance` 和 `Currency`；`ArrearsBalance` 有值时再展示。
  当前快照不能证明哪笔消费使余额转负。
- 当前不欠费：展示 `AvailableBalance` 和 `Currency`；`ArrearsBalance > 0` 时把它作为
  独立账务事实说明，不表达为矛盾。
- 无法确认：说明失败、缺失、类型错误或余额关系不一致中的实际原因；已取得的其他账户
  字段可以展示，但不能据此生成欠费结论。

## 2. 已出账未还款金额构成

“哪些产品欠费”“欠费产品”通常按指定账期内各产品的 `UnpaidAmount` 回答，
输出名称使用“已出账未还款金额构成”。产品是账务构成维度，不是欠费主体。

默认使用 `ListBillOverviewByProd`。缺少适用契约时直接读取其请求规则：

```bash
python3 scripts/cost.py schema --action ListBillOverviewByProd --section request --include-guidance
```

需要准确构成时使用指定账期的完整结果：

```text
python3 scripts/cost.py query \
  --action ListBillOverviewByProd \
  --body '{"BillPeriod":"<YYYY-MM>"}' \
  --pagination full \
  --require-field BillPeriod \
  --require-field Product \
  --require-field ProductZh \
  --require-field UnpaidAmount \
  --require-field Currency
```

- 用户已给账期时保持原范围；未给账期时先查当前账期，当前期不足以回答问题时，再按证据
  缺口补查必要账期。
- 仅保留能够按 `Decimal` 解析且 `UnpaidAmount > 0` 的行。
- 按 `BillPeriod`、`Product`/`ProductZh`、`Currency` 分组。
- 合法空结果表示本次查询范围内没有正数未还款金额，不证明账户当前不欠费。

输出账期、产品、已出账未还款金额和币种，可以提供总额或 TopN。标题、列名和结论中不使用
“产品欠费金额”“ECS 欠费”或其他产品级欠费判断。用户还问当前账户是否欠费时，再查询
“当前账户状态”，分别解释时点账户状态与期间账务构成。

## 抵扣核查共用输入

- 解释单期未抵扣，只查询分析期，不传 `--comparison-period`。判断抵扣下降才增加可比基期，
  用重复 `--period` 把两期账单采集到同一 CSV，保留同名 `.meta.json`；不要自行拼接并伪造 metadata。
- 账单保留同一账号、产品、实例、计费项和时间范围；库存和抵扣查询按相应接口支持的筛选
  限定候选对象。示例按账期和产品筛选；有更窄需求时先加载契约，用支持的筛选或保留完整
  原始产物后做分析，并在回答中说明实际范围。
- 下述示例默认核查 2026-09 单期。执行前复用或加载适用契约，替换日期、产品、时间及
  `task-result` 路径。比较抵扣下降时，为账单查询追加基期 `--period 2026-08`，为匹配脚本
  追加 `--comparison-period 2026-08`。
- 核对查询范围是否涵盖目标消费，分别记录抵扣执行时间、消费时间、原始账期和库存时点；
  即使 full 完成，也不要把范围外消费视为已查。
- `BillPeriod` 决定普通账单记录的出账归属；`ExpenseBeginTime`/`ExpenseEndTime` 表示实例实际
  使用周期，可能晚于账期甚至位于未来，但记录仍计入原账期。使用周期可用于核实资源包或券的
  有效期，不能从账期合计中排除记录，也不能据此手工生成分摊金额；按实际使用日/月查看成本时
  改查对应分摊成本 Action。
- 归因 `status=partial` 或 result 中候选为 `insufficient_evidence` 时，报告已核实的状态、消费和
  抵扣金额，按具体缺口决定是否补查，不自行补写确定原因。

## 3. 资源包未抵扣与抵扣变化

按“抵扣核查共用输入”复用或准备账单、资源包库存和抵扣明细。用户已指定候选包时，
保留它的标识用于核查不覆盖的证据。

先定位未完全抵扣且产生应付费用的按量消费，保留匹配所需字段。以下为单账期查询示例：

```bash
python3 scripts/cost.py query \
  --action ListBillDetail \
  --body '{"BillPeriod":"2026-09","GroupPeriod":2,"GroupTerm":0,"Product":["TOS"]}' \
  --period 2026-09 \
  --pagination full \
  --require-field BillPeriod \
  --require-field Product \
  --require-field ConfigName \
  --require-field InstanceNo \
  --require-field ElementCode \
  --require-field Region \
  --require-field BillingMode \
  --require-field ExpenseBeginTime \
  --require-field ExpenseEndTime \
  --require-field Count \
  --require-field DeductionCount \
  --require-field PayableAmount \
  --require-field Unit \
  --require-field Currency \
  --out task-result/package-bills.csv
```

仅核查产生应付费用的未完全抵扣按量消费，不同产品或计费项分开解释。

按已定位的产品查询全部状态的资源包，不只查 `Effective`，否则会漏掉未生效、已用尽和已过期：

```bash
python3 scripts/cost.py query \
  --action ListResourcePackages \
  --body '{"ResourceType":"Package","Product":"TOS","MaxResults":"20"}' \
  --pagination full \
  --out task-result/resource-packages.csv
```

用户明确指定某个包时按其已知产品查询库存，再用 InstanceNo 定位；候选包产品不同于
目标消费时保留该候选包，不用目标产品筛选将它排除，才能核查产品不匹配。

再按相关执行抵扣时间查询明细。`DeductBeginTime`/`DeductEndTime` 是 UTC 左闭右开的抵扣
时间范围，不能直接当作消费账期的等价窗口：

```text
python3 scripts/cost.py query \
  --action ListPackageUsageDetails \
  --body '{"ResourceType":"Package","DeductBeginTime":"<UTC begin>","DeductEndTime":"<UTC end>","MaxResults":"50"}' \
  --pagination full \
  --out task-result/package-usage.csv
```

优先使用已知抵扣执行时间；仅有消费窗口时，可在该窗口初查，再按返回的 `BeginTime`/
`EndTime` 判断覆盖了哪些消费。目标消费可能在窗口外执行抵扣，历史关联也可能早于分析期。
有具体记录或契约支持时补查相应窗口，可用 `InstanceNo` 限定已定位的资源包；边界未知时
明确覆盖缺口，不猜固定延迟或默认遍历全部历史，也不把“没有查到”解释为“没有抵扣”。

将三份查询产物交给匹配脚本。以下为单期核查，抵扣下降比较按共用输入规则追加基期：

```bash
python3 scripts/cost.py resource-package \
  --packages task-result/resource-packages.csv \
  --usage-details task-result/package-usage.csv \
  --bill-details task-result/package-bills.csv \
  --analysis-period 2026-09 \
  --out task-result/resource-package-attribution.json
```

用户明确指定候选包时追加 `--candidate-instance '<实际资源包 InstanceNo>'`，可重复。
交付前按包标识和 `affected_bill` 筛选用户所问的对象及分析期，不把其他包或基期的标签
当作本次目标消费的结论。

消费与抵扣匹配不充分时，按 `insufficient_evidence` 指出的对象、时间或单位补查；跨期或
多分组记录无法归属时，不自行分配用量。核实生效/到期使用消费时间，不用 `DeductionTime`
代替；解释数量时分别保留资源包单位和被抵扣用量单位。

读取 `supported_reasons` 时，按下列范围解释：

| 原因 | 回答方式 |
|---|---|
| 已用尽 | 报告当前余量、与目标消费的关联及未抵扣用量；没有用尽时间时，不说消费前已用尽 |
| 已过期 | 报告目标消费时间和资源包到期时间，指出消费已晚于有效期 |
| 未生效 | 报告目标消费时间和资源包生效时间，指出消费早于生效时间 |
| 抵扣下降 | 报告两期抵扣用量、单位和应付变化；某期无记录不补零，不把全部增量归到资源包 |
| 不覆盖当前消费 | 对用户指定的包说明具体产品或地域不匹配，不扩展为全部适用范围判断 |

按用户问题展示有关资源包及目标消费的证据，而非全部库存。未抵扣用量从账单
`Count - DeductionCount` 计算并保留单位；发生跨期变化时报告两期抵扣与应付金额。
例如“该包当前余量为零，曾抵扣同一实例和计费项；本期有……未抵扣用量。尚缺用尽时间，
不能确认它在这笔消费发生前已经用尽。”不要仅因脚本标签命中就补写因果关系。

解释适用范围时，只使用明确的产品、地域或其他已核实范围证据。不要把
`ConfigurationName`/`ConfigurationCode` 当作适用配置或计费项通配规则，也不要根据库存
单独判断不覆盖某配置、计费项或计费模式。用户明确指定候选包时，可以报告已确认的产品/
地域不匹配；没有候选包或关联证据时，不把账号中其他资源包当作费用上涨原因。

交付目标包和消费的核查结论、必要金额或用量，以及影响结论的具体缺口。

## 4. 代金券未抵扣与抵扣变化

定位目标消费和候选券，按“抵扣核查共用输入”准备账单与代金券库存。

账单产物须满足下列字段要求。以下为查询单账期明细示例：

```bash
python3 scripts/cost.py query \
  --action ListBillDetail \
  --body '{"BillPeriod":"2026-09","GroupPeriod":2,"GroupTerm":0,"Product":["TOS"]}' \
  --period 2026-09 \
  --pagination full \
  --require-field BillPeriod \
  --require-field BillID \
  --require-field BillDetailId \
  --require-field Product \
  --require-field ConfigName \
  --require-field InstanceNo \
  --require-field ElementCode \
  --require-field BillingMode \
  --require-field ExpenseBeginTime \
  --require-field ExpenseEndTime \
  --require-field DiscountBillAmount \
  --require-field CouponAmount \
  --require-field PayableAmount \
  --require-field Currency \
  --require-field Region --require-field Zone --require-field Unit \
  --out task-result/coupon-bills.csv
```

不同产品、配置、实例、计费项或计费模式不合并；输入存在地域、可用区或单位时
保留这些维度。代金券金额单位为元，只与 `Currency=CNY` 的账单比较。

按已定位产品查询代金券所有状态，不只查询生效中：

```bash
python3 scripts/cost.py query \
  --action ListCoupons \
  --body '{"ProductCode":"TOS"}' \
  --pagination full \
  --page-size 10 \
  --out task-result/coupons.csv
```

用户明确指定某张券时可改用 `CouponID` 筛选；核查产品不适用时，不同时用目标消费的
ProductCode 把这张候选券排除。

对用户指定的券以及与目标消费范围匹配的候选券，分别查询完整核销记录：

```text
python3 scripts/cost.py query \
  --action ListCouponUsageRecords \
  --body '{"CouponID":"<实际 CouponID>"}' \
  --pagination full \
  --page-size 1000 \
  --out task-result/coupon-usage-<CouponID>.csv
```

`ChangeType=2` 是抵扣，`ChangeType=3` 是退回，两类非负 `ChangeAmount` 分别汇总；出现负值时
保留原值并报告金额方向无法确认，不自行取绝对值。
`PayType=post` 时，`SubBusinessID` 是账单明细号，与 `BillDetailId` 相等才能确认具体账单的
实际抵扣或退回。`PayType=pre` 时，`SubBusinessID` 是订单号；对预付费账单，使用
`SubBusinessID=BillID` 尝试关联，不与 `BillDetailId` 比较。核销记录不提供余额、有效期或
完整适用规则，这些事实仍从 `ListCoupons` 读取。

将库存、各候选券的核销记录和账单产物交给匹配脚本：

```text
python3 scripts/cost.py coupon \
  --coupons task-result/coupons.csv \
  --usage-records task-result/coupon-usage-<CouponID>.csv \
  --bill-details task-result/coupon-bills.csv \
  --analysis-period 2026-09 \
  --out task-result/coupon-attribution.json
```

多张候选券时，每张券分别 full 查询，并重复传入 `--usage-records`。比较抵扣下降时按共用
输入规则追加基期。用户指定某张券时追加 `--candidate-coupon '<实际 CouponID>'`，可重复。
交付前按券标识和 `affected_bill` 筛选目标消费；核实有效期使用 `ExpenseBeginTime`，不以
出账时间代替消费时间。

读取 `supported_reasons` 时，按下列范围解释：

| 原因 | 回答方式 |
|---|---|
| 已用尽 | 报告券当前余额和目标账单抵扣金额；没有余额历史时，不说消费时已用尽 |
| 已过期 | 报告目标消费时间、券到期时间和未抵扣金额 |
| 未生效 | 报告目标消费时间、券生效时间和未抵扣金额 |
| 不适用 | 对用户指定的券说明已核实不匹配的产品、配置、计费项、付款方式或金额门槛 |
| 券级核销下降 | 分别报告这张券两期 `ChangeType=2` 的核销金额；退回金额单列，不自行计算净额 |

`bill_observations` 只表示账单 `CouponAmount` 和应付金额的变化，不归因到具体券；
`follow_up_candidates` 表示适用范围匹配、值得查询核销记录的候选券；
`coupon_usage_summaries` 才是指定券的实际抵扣与退回记录汇总。后付费记录须匹配目标
`BillDetailId`；预付费记录须匹配预付费目标账单的 `BillID`，才能确认这张券实际作用于该账单。

计费方式、订单类型或账号限制尚未核实且可能改变结论时，指出缺少的范围证据；没有范围
匹配的券时只报告账单金额变化，不归因到具体券。完整核销结果中某账期没有 `ChangeType=2`
记录时，该券该期核销金额为零；查询不完整时不能补零。

例如“目标消费发生在这张券的有效期之后，产品和计费项范围匹配，账单抵扣金额为零；
这张券已不能按该有效期覆盖此次消费。”多张券并存时，这不解释其他券为何没有抵扣。
抵扣下降同时报告账单两期金额和相关券的实际核销变化，不把两者的差额自动视为同一笔
金额，也不称为账户欠费的唯一原因。

交付目标券和消费的核查结论、账单抵扣金额，以及影响结论的具体缺口。

## 5. 当前欠费原因分析

本流程组合账户事实、账务定位和必要的专项核查。先执行“当前账户状态”，
账户快照是当前欠费事实的唯一入口；复用仍符合当前时效要求的快照：

```text
QueryBalanceAcct
├─ 当前不欠费：结束当前欠费原因；按用户其他问题决定是否继续账务分析
├─ 无法确认：停止确定欠费结论；只报告用户明确要求且已经取得的账务事实
└─ 当前欠费：定位最小必要账期和产品汇总，再按信号下钻
```

用户明确问历史欠费时，当前账户快照只能说明“现在”。没有历史余额或资金事件证据时，不重建
过去是否欠费、余额何时转负或某笔消费如何击穿余额。

### 5.1 最小账务定位

先用账户快照中的现金、信控、冻结和欠费金额解释当前可用余额的构成；这是当前资金关系，
不代表已找到余额转负事件。用户只问余额构成时到此交付；需要解释消费来源时再查账务。

当前账户欠费后，从用户指定的账期、产品、实例或时间范围开始。未指定账期时先查当前账期，
只有需要跨期比较或当前期证据不足时才增加必要账期。

1. 使用 `ListBillOverviewByProd` 的 `full` 结果定位应付金额和未还款金额的主要产品构成。
2. 需要账单流水、支付状态、账单类型或交易时间时，再查 `ListBill`。
3. 需要配置、实例、计费项、用量、单位、优惠或逐日证据时，再查 `ListBillDetail`；根据最终
   所需字段选择 `GroupPeriod`/`GroupTerm`，并用 `--require-field` 在请求前保护粒度。
4. 只分析已有信号指向的候选原因，不先拉全部明细，也不为每个产品重复查询账户。

用户说“ECS 为什么欠费”时，把 ECS 作为消费证据筛选条件，回答它是否构成已确认的账户消费变化；不要把 ECS 当成独立欠费主体。

### 5.2 按线索选择分析分支

- 用量、价格、优惠或消费结构发生变化时，按[查询与分析](cost-query.md)中的费用变化流程取证。
- 出现资源包或代金券抵扣线索时，进入“资源包未抵扣与抵扣变化”或“代金券未抵扣与抵扣变化”，无需遍历没有线索的其他分支。
- 已证实未抵扣时，可以解释对应应付费用；确认它如何形成当前欠费仍需相应资金证据。

按以下证据判断可以回答到什么程度：

| 候选原因 | 必要证据 | 可以说 | 证据不足时 |
|---|---|---|---|
| 用量上涨 | 可比窗口、相同产品/配置/计费项、相同 `Unit` 的 `Count` 与 `PayableAmount` | 对象、窗口、用量和金额的已观测变化 | 只说明金额上涨，不猜用量 |
| 优惠或折扣减少 | 可比窗口中的 `OriginalBillAmount`、`PreferentialBillAmount`/`DiscountBillAmount`、`PayableAmount`，必要时加相同单位用量 | 账单侧优惠减少或实际应付上升 | 不表达为合同到期或合同价失效 |
| 资源包未抵扣或抵扣下降 | 按“资源包未抵扣与抵扣变化”取得匹配证据 | 将已核实抵扣情况及相关应付费用带回本流程 | 保留子流程指出的关联、时间或用量缺口 |
| 代金券未抵扣或抵扣下降 | 按“代金券未抵扣与抵扣变化”取得匹配证据 | 将已核实适用情况、账单抵扣及应付费用带回本流程 | 保留子流程指出的范围、时间或账单缺口 |
| 集中入账线索 | `ExpenseBeginTime`/`ExpenseEndTime`、`TradeTime`、相关金额和对象 | 观察到相关消费在某时间集中形成账单 | 没有余额事件时不说它导致余额在该时点转负 |
| 新购、续费、更配等账单事件 | `BillCategoryParent` 或 `BillCategory`、时间、金额、产品/实例 | 某类账单事件及其金额进入账单 | 没有订单证据时不升级为订单根因 |
| 主要消费对象变化 | 同口径完整范围内稳定的产品、配置或计费项维度 | 本期消费构成相对基期发生变化 | 范围不完整时只报告当前已见构成 |

报告已确认的对象、时间和金额变化。缺少用尽时间时，不说资源包在消费前已用尽；抵扣减少
且应付上升时，还需核查用量、价格或其他优惠变化，才能进一步解释金额驱动。缺少相关证据
时说明已确认现象和缺口，不把候选标签表述为唯一原因。

准备覆盖所选 `BillPeriod` 的可比输入，报告两期同一对象的汇总变化。输入缺少维度或金额时，
按结果中指出的缺口补齐，无法补齐则只报告已确认事实；不要据消费记录的首末时间宣称全量。

### 5.3 尚不能确认的原因

需要未查询的代金券核销记录、订单详情、合同有效期或历史资金事件才能回答时，先补查已接入
接口能够提供的证据；其余缺口说明需要用户从控制台或相关账务记录补充。不能声称已经核实，
也不能从账单字段反推订单根因或合同到期。

用户说“刚充值为什么还欠费”时刷新账户快照。缺少到账记录时只报告当前账户状态；没有官方
处理时限依据时，不说明或承诺恢复时间。

### 5.4 汇总结论

给出当前账户状态、必要的资金构成、主要消费来源及已核实的原因。每个专项结论保留其对象、
时间和证据限制；有消费证据但缺少资金事件时，说明相关费用，保留余额转负时间或过程的缺口。
已足够回答时交付；仍有关键缺口时说明已核实事实和可补齐该缺口的下一步。

## 6. 失败、空结果与证据限制

- 账户查询无权限、认证失败、超时或响应损坏：说明无法确认账户状态；不能退回账单
  `UnpaidAmount` 判定。
- 账务查询无权限或全部失败：保留已确认的账户事实，停止相应原因分支。
- 仅有手工数据且缺少查询证据时，只作受限分析，不给出确定原因；输入不完整时，补齐结果
  指出的缺口或说明无法继续，不自行调整机器证据或原因标签。
- 即使专项执行 `status=success`，也要检查对象、消费窗口和库存时点是否支持用户所问结论；
  result 中原因数组为空表示未获得相应证据，不等于已排除资源包或代金券影响。
- 一个候选原因已经有完整证据时输出；没有证据的候选原因不要为了凑报告而罗列。

## 7. 交付

按用户问题给出结论、账期，以及支撑结论的必要金额和证据。复杂原因分析再说明
相关对象、消费时间、金额口径和会改变结论的限制；有明确下一步时才给出建议。

组合问题分别回答：现在的账户状态、所选账期的未还款构成、目标消费的抵扣现象及解释。
已有消费证据但缺少资金事件时，可说明相关费用构成，仍不能确认余额何时转负。证据不足
时给出已核实事实、具体缺口和能补齐该缺口的下一步，不只返回“无法分析”。
