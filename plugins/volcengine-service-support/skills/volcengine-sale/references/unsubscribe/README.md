# unsubscribe 动作：退订流程

用户需要退订、退款或取消订阅已购买的包年包月实例时执行本流程。所有商品共用本流程。

## 安全等级（最高优先级，不得跳读）

`UnsubscribeInstance` 是**破坏性操作**，适用最严格的确认要求：

- 必须展示**完整命令 + 影响摘要**，并获得用户**明确确认**后才执行。
- **一次只退一个实例**（`InstanceID` 为单值字符串），**禁止批量循环退订**。
- 本接口**不支持 DryRun**，不得尝试 `--DryRun`。
- 确认必须是用户的明确肯定表述。沉默、"嗯"、"继续"、"好的"**都不算确认**。
- 部分资源一经退订**无法恢复**；退款仅退还实付金额的部分，**已使用的代金券不退还**。

## 步骤 1：实例定位

按用户是否提供实例 ID 分为两种方式。**两种方式都不需要用户提供商品**：`Product` 一律取自 `ListAvailableInstances` 返回值中选中实例的该字段。

### 1.1 已提供实例 ID：直接查询该实例

```bash
ve billing ListAvailableInstances --body '{"InstanceIDs":["<instance-id>"],"MaxResults":10}'
```

### 1.2 未提供实例 ID：直接列出候选实例

`Product` 为**可选过滤条件，不是必填参数**。用户未指明商品时**不传该参数**，直接拉取全部可退订实例：

```bash
ve billing ListAvailableInstances --body '{"MaxResults":50}'
```

- **不得为了调用接口而先追问商品**。商品编码在步骤 4 从选中实例的返回值中获取，查询阶段无需知道。
- **不得自行附加 `Product`、`RenewType` 等过滤条件**，否则候选列表不完整。自动续费实例同样可以退订。
- 仅当**用户主动指明**筛选条件时才加对应参数：说明了商品就加 `Product`（编码取自 [common/product-catalog.md](../common/product-catalog.md) 的商品清单；商品未收录时**不得猜测编码**，按不传处理，改为在返回列表中筛选）；要求"快到期的"加 `ExpiredTimeStart` / `ExpiredTimeEnd`；要求"手动续费的"才加 `RenewType`。
- 查询结果以表格呈现供用户选择，列出：`InstanceID`、`InstanceName`、`Product`、`PaymentMethod`、`Status`、`RenewType`、`BeginTime`、`ExpiredTime`。
- 结果较多时按 `MaxResults` 与 `NextToken` 翻页，**不得截断后当作全部**；可请用户补充商品、到期时间等条件缩小范围。
- 用户必须**明确选定单个** `InstanceID` 才能进入步骤 2。"全部退订"不予受理，需逐个执行完整流程。

### 接口约束（两种方式通用）

| 约束 | 说明 |
|---|---|
| 必填参数 | 仅 `MaxResults` 必填。`Product`、`InstanceIDs`、`RenewType`、时间区间均为**可选过滤条件**，用户未提及时一律不传 |
| 数据延迟 | 本接口有 **3–5 秒延迟**。查不到时等待后重试（最多 3 次），**不得立即判定实例不存在** |
| QPS | 单账号 **QPS ≤5**，翻页需控制频率 |
| 分页 | `MaxResults` **必填**，范围 `[1, 100]`；超出时用 `NextToken` 翻页 |
| 时间格式 | `BeginTimeStart/End`、`ExpiredTimeStart/End` 用 UTC 格式 `yyyy-MM-dd'T'HH:mm:ss'Z'`，同类区间跨度不超过 31 天 |
| 实例 ID 批量 | `InstanceIDs` 单次最多 100 个 |

## 步骤 2：可退订性核对

基于 `ListAvailableInstances` 的返回值逐项判定：

| 核对项 | 依据字段 | 不通过时的处理 |
|---|---|---|
| 实例存在且属于当前账号 | `InstanceID`、`AccountID` | 停止流程，请用户核对账号与实例 ID |
| 付费方式为包年包月 | `PaymentMethod` | 后付费实例**不可退订**；说明差异并引导用户到对应产品控制台释放资源 |
| 实例状态允许退订 | `Status`、`SubStatus` | 已是退订关停 / 到期关停 / 服务关闭等状态时，说明当前状态，**不重复退订** |

**能查到实例不等于该实例可通过 OpenAPI 退订。** 最终以 `UnsubscribeInstance` 是否返回 `CannotUnsubscribe` 为准。

## 步骤 3：影响摘要与强制确认

向用户完整展示以下六段内容，缺任一段不得进入步骤 4：

```
【即将退订】
  实例：<instance-id>（<instance-name>）
  商品：<product>
  付费方式 / 周期：<payment-method> / <begin-time> ~ <expired-time>

【关联实例】
  是否一并退订当前实例 ID 关联的实例（同一实例组内的实例，
  或套装促销需整体退订的实例）？（是 / 否）

【费用影响】
  退款仅退还实付金额的部分；已使用的代金券不退还。
  实际退款金额以费用中心的退订工单为准。

【不可逆风险】
  部分资源一经退订无法恢复，实例数据可能被直接销毁且无法找回。

【替代方案】
  仅需停止续费 → 关闭自动续费（SetRenewalType），不销毁资源，不影响当前周期使用
  仅需暂停使用 → 前往产品控制台停机或释放具体资源

【确认】
  请一并回复以上两项：
    1. 是否退订关联实例（是 / 否）
    2. 确认退订请明确回复「确认退订 <instance-id>」
```

### 关联实例的取值

| 用户回答 | `UnsubscribeRelatedInstance` |
|---|---|
| 明确回答"是" | `true` |
| 明确回答"否"，或说明仅退订当前实例 | `false` |
| 未明确回答 | **不发起退订** |

四条硬约束：

- **未得到明确回答不得发起退订**，包括沉默、"随便"、"你决定"，以及仅回复确认退订语但未答此项的情形。**不得默认取 `false`**。
- **不得列举具体的关联实例**。关联实例清单无接口可查，询问时仅描述其定义，不提供实例 ID。
- **不得推断实例间的关联关系**。同商品、同到期时间、名称相似均不构成实例组的判定依据。
- 接口报错提示需整体退订时，**不得自行改为 `true` 重试**，须重新向用户确认。

两条反模式：

- **不得预估退款金额。** 询价接口为新购口径，无法用于计算退款；不得调用询价接口推算退款金额。
- **不得将替代方案视为已执行。** `SetRenewalType` 本身为写操作，用户选择该方案时需重新执行完整确认流程。

## 步骤 4：执行退订

```bash
ve billing UnsubscribeInstance --body '{"InstanceID":"<instance-id>","Product":"<product-code>","UnsubscribeRelatedInstance":false,"ClientToken":"<uuid>"}'
```

- 服务：`billing`，Action：`UnsubscribeInstance`，版本：`2022-01-01`，方法：POST，单账号 QPS ≤50。
- 子用户需具备 `BillingCenterFullAccess` 或 `BillingCenterRefundAccess` 权限策略。
- 仅支持退订符合退订规则的**包年包月实例或包月预留实例券**；支持退订的商品范围见[支持 OpenAPI 退订的商品清单](https://www.volcengine.com/docs/6269/1166376)，退订规则见[退订管理](https://www.volcengine.com/docs/6269/81013)。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `InstanceID` | string | 是 | **单个实例**，不支持批量 |
| `Product` | string | 是 | 实例 ID 对应的商品编码。**取自步骤 1 中该实例返回值的 `Product` 字段**，不得要求用户提供，也不得自行推断或从商品清单反查 |
| `UnsubscribeRelatedInstance` | boolean | 否 | 是否退订关联实例。**按步骤 3 用户的明确回答填写**，命令模板中的 `false` 只是占位 |
| `ClientToken` | string | 否 | `uuidgen` 生成的 UUID，用于幂等；同一次退订意图的所有重试**共享同一个值** |

出参：`OrderIDList[]`（退订订单号列表）、`SuccessInstanceInfos[]`（含 `Product`、`InstanceID`）。`OrderID` 字段**已废弃**，一律用 `OrderIDList` 取订单号。

## 步骤 5：结果核验

```bash
ve billing ListAvailableInstances --body '{"InstanceIDs":["<instance-id>"],"MaxResults":10}'
```

- 因数据有 3–5 秒延迟，首次查询前先等 3s；之后每 3s 轮询一次，最多 5 次。
- `Status` / `SubStatus` 变为退订关停 / 已关闭 → 退订成功，输出 `OrderIDList` 与实例状态。
- 5 次轮询后状态仍未变化 → **不得重复调用 `UnsubscribeInstance`**。已返回 `OrderIDList` 即表示工单已受理，凭订单号引导用户前往费用中心的订单管理页查看进度。

破坏性操作的重试语义：**状态未确认时按"可能已生效"处理，而非"失败可重试"。**

## 执行失败

命令实际返回错误时，按 [errors.md](./errors.md) 处理。

## 替代方案

用户的实际诉求可能并非退订，执行前先确认：

| 用户诉求 | 更合适的做法 |
|---|---|
| 停止续费 / 停止自动扣费 | 关闭自动续费 `SetRenewalType`，资源保留至当前周期结束。该操作为写操作，需执行完整确认流程 |
| 暂停使用 | 前往对应产品控制台停机或释放具体资源 |
| 配置选择有误 | 优先确认该商品是否支持变配；不支持变配时再考虑退订重购 |

无法通过接口完成退订时，引导用户前往**费用中心 → 订单管理 → 退订**自行提交。
