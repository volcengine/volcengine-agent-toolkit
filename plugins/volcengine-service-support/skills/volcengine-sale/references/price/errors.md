# price 执行失败处理

仅当询价接口**实际执行后返回错误**时才加载本文件。

先按 [common/errors.md](../common/errors.md) 的通用表匹配；未命中再按下表匹配，命中第一行即停。匹配大小写不敏感，同时兼容错误码与消息子串。

## 错误处理表

| # | 类别 | 匹配条件 | 处理方式 |
|---|---|---|---|
| P1 | 参数无效 | 400 `InvalidParam` | 复核 `Count`、`UseDuration`、`Quantity` 的取值（是否为 0、负数或超出商品定义范围）；修正后重新询价，连续 2 次失败转入降级流程 |
| P2 | 参数缺失 | 400 `MissingParameter` | 按 [README.md](./README.md) 步骤 6 的参数表补齐必填项；`Count` 与 `UseDuration` 一律传入 |
| P3 | 配置不可询价 | 400 `OperationDenied.ConfigurationNotOnline` / `ConfigurationNotPublic` / `ConfigurationNotAllowed` | 该配置未上架、未公开或不允许询价（如定制价格）。**不得猜测替代编码**，说明原因后转入降级流程 |
| P4 | 计费项不可询价 | 400 `OperationDenied.ChargeItemNotOnline` / `ChargeItemNotPublic` / `ChargeItemNotAllowed` | 该计费项未上架、未公开或不允许此操作。**不得猜测替代编码**，说明原因后转入降级流程 |
| P5 | 折后价被掩码 | 返回体含 `***` 且折扣信息为空 | 按下方「折后价被掩码」处理，**不视为错误，不重试** |
| P6 | 询价限流 | `FrequentRequest`、`Throttling`、`429` | 询价 QPS ≤10；退避后最多重试 2 次，仍失败如实说明 |
| P7 | 操作被拒 | 403 `RequestReject` | 账号涉及违规操作，功能暂不可用。**不重试**，引导用户联系火山引擎客服 |
| P8 | 服务内部异常 | 500 `InternalError` | 退避后最多重试 1 次；仍失败时如实说明并转入降级流程 |
| 兜底 | 其他业务错误 | 上述均未命中 | 原样展示实际错误码与消息，附价格计算器链接作为替代方案，询问是否重试 |

## 折后价被掩码

返回中除 `TotalOriginalAmount` 外的金额字段为 `***`、且折扣信息为空时，是**子用户被 Deny `Billing:QueryDiscounAmount` 导致的权限掩码**，不是接口异常。

- 如实说明系权限所致，**不得报为系统错误或接口故障**。
- **原样保留 `***`**，严禁以原价替代折后价，严禁自行推算或编造被掩码的金额。原价可正常展示。
- 提示解法：联系主账号授予 `BillingCenterReadOnlyAccess` 或 `BillingCenterFullAccess`，或移除对 `Billing:QueryDiscounAmount` 的 Deny 策略。
- **不重试**。

## 降级：价格计算器

触发条件：商品未命中清单、配置或计费项编码无法获得、P1 连续失败、P3、P4，以及用户明确说明计费方式为按峰值 / 按平均量月结。

用量属性值与购买时长缺失**不触发降级**：取默认值 `1`，由用户在确认环节决定。

对客回复直接使用以下模板：

```
该配置需要在价格计算器中选型询价：
https://www.volcengine.com/pricing

进入后选择对应的商品、配置和计费项即可查看实时价格。
```

降级即流程终点。**不得抓取价格计算器等页面的内部接口**以反向获取配置计费项信息，也不得据此自行拼装价格。

## 扩展新错误处理

1. 在兜底行之前追加一行，写明匹配条件与处理方式。
2. 更精确、更具体的分类必须排在更宽泛的分类之前，避免被上游行提前命中。
3. 处理方式中的引导链接必须是官方真实地址，严禁臆造。
