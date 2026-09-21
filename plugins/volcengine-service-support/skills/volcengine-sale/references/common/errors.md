# 通用错误处理

price 与 unsubscribe 动作**共用**的错误分流表。仅当命令**实际执行后返回错误**时才加载本文件。

> buy 动作有自己完整的错误处理表，见 [buy/errors.md](../buy/errors.md)，不使用本文件。

## 匹配顺序

1. 先匹配本文件的**通用错误表**，命中第一行即停；
2. 未命中则回到当前动作的**专属错误表**：
   - price → [price/errors.md](../price/errors.md)
   - unsubscribe → [unsubscribe/errors.md](../unsubscribe/errors.md)
3. 动作专属表仍未命中 → 走该动作自己的兜底行。

匹配大小写不敏感，同时兼容错误码与消息子串。

## 通用错误表

| # | 类别 | 匹配条件（错误码 / 消息子串，任一命中即可） | 处理方式 |
|---|---|---|---|
| 1 | 鉴权 / 登录 | `failed to refresh session token`、`Please run 've login'`、`Unauthorized`、`InvalidAccessKey`、`SignatureDoesNotMatch` | 委托 volcengine-cli skill 完成 `ve login`，登录后**按当前动作的重试规则**重试（unsubscribe 复用同一个 ClientToken；price 无 ClientToken，直接重发原命令） |
| 2 | 限流 | `FrequentRequest`、`Throttling`、`429`、`操作频繁` | 退避后重试，**最多 2 次**；仍失败则如实告知用户接口繁忙。各接口 QPS 上限不同，见对应动作文件（询价 ≤10、`ListAvailableInstances` ≤5、`UnsubscribeInstance` ≤50） |
| 3 | IAM 权限不足 | `AccessDenied`、`NoPermission`、`权限不足`、`policy` 相关拒绝 | 说明当前账号 / 子用户缺少该 Action 的 IAM 权限，引导主账号按最小权限原则授权。**不要**将其与第 1 行的登录态失效混为一谈，也不要尝试 `ve login` 重试 |
| 兜底 | 未命中通用分类 | 上述均未命中 | 回到当前动作的专属错误表继续匹配 |

## 扩展新错误处理

1. 只有 price 与 unsubscribe **都会遇到**的错误才放本表；单一动作特有的错误放对应动作文件。
2. 在兜底行之前追加一行，写明匹配条件（错误码或消息子串）与处理方式。
3. 更精确、更具体的分类必须排在更宽泛的分类之前，避免被上游行提前命中。
4. 处理方式中如需给出引导链接，必须是官方控制台真实地址，严禁臆造。
