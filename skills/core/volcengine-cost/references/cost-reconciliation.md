# 费用对账、观察性比较与差异下钻

使用 `cost.py reconcile` 按目标选择正式对账或观察性比较,命令路径相对 Skill 根目录。

- `run` 和 `drill-down` 必须通过 `--out` 指定结果路径。
- reconcile 的左右输入可使用 query 返回的文件型 `result`（`--left-result '<result-json>'` /
  `--right-result '<result-json>'`），或既有 CSV 路径（`--left` / `--right`）。

## 1. 选择模式、关系与阶段

- **正式对账（默认）**：用于验证账务一致性，检查来源关系、范围和完整性。
- **观察性比较（`--mode observational`）**：输入不满足正式对账条件（如范围不同、来源关系
  未登记、查询证据或完整性不足），但用户需要查看文件差额时，保留原始范围计算，
  不要求统一范围或重复确认。结果仅解释文件快照，不形成标准对账或多算结论。

已有 CSV 可读但缺 meta/fields 时，观察性比较仍可按已确认的金额字段和实际分组列分析，
不声称来源、完整性或时效已经验证。必要字段、金额语义或币种无法确定时，停止受影响的计算。
CSV 本身缺失时，按 [查询与分析](cost-query.md) 获取实际数据，不能生成数字。
用户指定现有文件时优先保留原快照，重新查询不替换原输入。

例如保留左侧 ECS、右侧 ECS+RDS 的原始范围按 Project 比较：

```bash
python3 scripts/cost.py reconcile run --mode observational \
  --left artifacts/project-left-bill-detail.csv \
  --right artifacts/project-right-split-detail.csv \
  --group-by Project --metric PayableAmount --out task-result/project-comparison.csv
```

已有适用关系契约时直接使用；关系尚未确认时查看：

```bash
python3 scripts/cost.py reconcile describe --section profiles
```

现有关系为产品总览与账单、账单与账单明细、账单明细与分账明细。默认共同粒度分别为
Product、BillID、Product/InstanceNo；实际可用维度、金额和条件以 profiles 及实际文件为准。

两侧产物中的 Action 自动选择关系，不自行传 relationship/profile。缺少当前阶段的
参数依据时，读取相应契约的 arguments；以下命令按需选择，不要求连续执行三次：

```bash
python3 scripts/cost.py reconcile describe --section preflight
python3 scripts/cost.py reconcile describe --section run
python3 scripts/cost.py reconcile describe --section drill_down
```

未登记 Pair 不临时构造 profile。正式对账可通过已支持的中间来源分段核验；
自定义分析按查询指引进行。

### 最小示例：核对产品总览与账单

以下以 2026-09 全部产品的应付金额为例。执行前复用或加载两侧请求契约，将日期、筛选和
`task-result` 路径替换成本任务范围；两侧账号和业务筛选一致。已有适用产物时跳过查询。

```bash
python3 scripts/cost.py query \
  --action ListBillOverviewByProd \
  --body '{"BillPeriod":"2026-09"}' \
  --pagination full \
  --require-field Product --require-field PayableAmount --require-field Currency \
  --out task-result/product-overview.csv

python3 scripts/cost.py query \
  --action ListBill \
  --body '{"BillPeriod":"2026-09"}' \
  --pagination full \
  --require-field Product --require-field PayableAmount --require-field Currency \
  --out task-result/bills.csv
```

检查两次查询状态及 metadata，再执行核对。`run` 内置 preflight；通常直接运行，只有需要
单独检查可比性时才另用 `preflight`：

```bash
python3 scripts/cost.py reconcile run \
  --left task-result/product-overview.csv \
  --right task-result/bills.csv \
  --group-by Product --metric PayableAmount \
  --out task-result/reconciliation.csv
```

从实际返回的产物读取每个产品的左右金额、差额和状态，并保留 claim_scope。差额为正表示
右侧账单金额较高；全部 matched 只表示本次范围的该金额一致。出现 block 时按报告修正
输入或范围，出现差异时再决定是否下钻，不直接归因。

例如要解释 ECS 行的账单构成，可从右侧按 BillingMode 展开：

```bash
python3 scripts/cost.py reconcile drill-down \
  --from task-result/reconciliation.csv \
  --row Product=ECS --row Currency=CNY \
  --by BillingMode --side right \
  --out task-result/ecs-billing-mode.csv
```

## 2. 检查两侧证据

preflight 在计算前检查：

- 产物来源与证据一致，关系已经登记，必要字段实际存在于双方 CSV。
- 去掉分页和服务端粒度参数后，账期、账号、产品、计费模式等请求范围等价。
- 两侧完整性和时效满足比较要求，没有未披露的失败范围。
- 共同过滤、维度和金额可比较，币种自动纳入键；SettlementType 只在用户要求区分
  结算/非结算/Quota 等范围时显式加入。
- 当前账期、时效及非标准 Project/Tag 比较保留相应限制。

preflight 按所选 mode 判断：pass 可正式核对；warn 按返回的 claim_scope 受限计算；
block 表示当前模式的必要条件不足，停止本次计算，不修改原始 metadata 使检查通过。

`ARTIFACT_INVALID` 表示当前模式的输入加载失败，来源关系、范围、维度和金额检查尚未执行。
按 recovery_options 核对实际文件，不猜路径反复 run，也不把该错误解释成已验证的范围不一致。

当前月结果即使采集成功，也因账期未结束而只支持受限比较。是否允许计算由 preflight 根据
机器证据判断；Agent 只按 verdict、claim_scope 和 message 行动，不手写或修改机器证据使其
通过。缺证据、失败范围或其他停止原因仍会阻断或限制对账。

## 3. 聚合与解释差额

本地 Filter 同时作用于两侧；observational 模式保留输入文件原有的不同范围。工具先分别
聚合，再按共同维度及币种关联，避免一对多金额放大；关键维度为空时结果为 inconclusive。

金额指标使用契约支持的可加和字段；每个指标分别输出 left、right、difference 和 status。
`difference = right - left`，Decimal 精确比较，当前 tolerance 固定为 0；数量和单价不套入
金额核对。读取实际结果状态：

| 状态 | 解释 |
|---|---|
| matched | 所比较金额的 difference 均为零 |
| mismatched | 至少一项金额存在差额 |
| left_only / right_only | 当前键只在一侧出现 |
| inconclusive | 缺关键维度、金额或证据不足，不能确认一致性 |

observational 模式下，文件范围内未出现的组金额计为 0，保留 left_only/right_only 标记，
允许计算该组的文件差额；这不表示真实业务金额为零。记录中缺失的金额保持未知，不补零。
双侧数值均可计算时输出差额，matched/mismatched 降为 inconclusive，不能据此认定多算。

账单和账单明细是原始账务依据，分账是归属参考。一对多分拆应按共同维度聚合，不能把
每条分账行当成账单明细的一对一副本；成本与明细没有稳定逐条键时不猜测关联关系。

差额只证明指定来源、范围、粒度和金额口径下的关系。不能根据产品、BillingMode、
Project/Tag 或单侧记录直接推断“此费用不应参与分账”等业务规则。时效、分账生成或
标签更新延迟可以作为待核实线索，不能直接认定根因；需要确认后台链路或订正时建议提工单。

## 4. 下钻与归属解释

`drill-down` 前读取父结果实际列和 metadata，确认下钻维度在输入中存在，用实际行值和币种
唯一定位父行。下钻继承父级输入、Filter、金额、时间和口径，在原 group_by 上增加维度。
工具校验下钻后的金额合计是否与父行一致；校验失败时结果为
inconclusive，不把子级结果用于确定归因。

`--side both` 继续双侧核对；`--side left/right` 仅解释单侧构成，不证明差额原因或双侧一致性。
本地路径或 selector 错误只修正本地调用，不重新查询 Billing。

## 5. 交付

报告实际比较的金额口径、币种、范围、关键差异和 claim_scope，说明失败/缺失、当前月
及延迟限制。给出工具实际生成的结果、两侧归一化产物和复现证据；缺前提时说明需要补齐
什么，不生成看似完整的对账结论。
