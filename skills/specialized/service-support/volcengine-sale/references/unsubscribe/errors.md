# unsubscribe 执行失败处理

仅当 `ve billing UnsubscribeInstance` 或 `ListAvailableInstances` **实际执行后返回错误**时才加载本文件。

先按 [common/errors.md](../common/errors.md) 的通用表匹配；未命中再按下表匹配，命中第一行即停。匹配大小写不敏感，同时兼容错误码与消息子串。

## 错误处理表

| # | 错误码 / HTTP | 处理方式 |
|---|---|---|
| U1 | 400 `CannotUnsubscribe` | 该实例受退订规则限制，不可通过 OpenAPI 退订。**不重试、不换参数试探**；说明原因并引导用户到费用中心提交退订工单 |
| U2 | 404 `InstanceNotFound` | 实例不存在或不属于当前账号；回到步骤 1 重新核对，注意 3–5 秒数据延迟 |
| U3 | 403 `InstancePermissionDenied` | 当前 AK/SK 缺少操作该实例的权限；引导主账号授予 `BillingCenterFullAccess` 或 `BillingCenterRefundAccess`。**不要尝试 `ve login` 重试** |
| U4 | 412 `StatusWrong` | 实例或订单状态不符合预期（如已在退订中、已关停）；重查状态后如实说明，**不重试** |
| U5 | 400 `InvalidIdempotentParams` | `ClientToken` 对应的参数已变更，**必须换一个新的 ClientToken** 重试 |
| U6 | 409 `IdempotentRequestConflict` | 同一 `ClientToken` 的请求正在处理中。**不换 ClientToken、不改参数**；等待数秒后用 `ListAvailableInstances` 核实结果，不要并发重发 |
| U7 | 400 `ParamInvalid` / `BadRequest` | 参数不合法或未通过业务校验；复核 `InstanceID` 与 `Product` 是否匹配，**不猜测 Product** |
| U8 | 400 `InstanceExpireTimeRequired` | 该实例未设置到期时间，不符合退订前提；如实说明并引导到费用中心处理 |
| U9 | 500 `InternalError` / `InternalServerError` / `ThirdSystemError` | **先用 `ListAvailableInstances` 确认退订是否实际已生效**，再决定是否重试，避免重复退订 |
| 兜底 | 其他业务错误 | 原样展示实际错误码与消息，说明可前往费用中心的订单管理页手工提交退订，询问是否重试 |

退订是破坏性操作：**状态未确认时默认"可能已生效"，而不是"失败可重试"。**

## 扩展新错误处理

1. 在兜底行之前追加一行，写明匹配条件与处理方式。
2. 更精确、更具体的分类必须排在更宽泛的分类之前，避免被上游行提前命中。
3. 处理方式中的引导链接必须是官方真实地址，严禁臆造。
