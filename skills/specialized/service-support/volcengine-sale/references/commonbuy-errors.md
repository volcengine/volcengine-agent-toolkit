# CommonBuy 执行失败处理

仅当 `ve billing CommonBuy` **实际执行后返回错误**时才加载本文件。按下表顺序自上而下匹配错误码或错误消息，命中的第一行决定处理方式；均未命中时走兜底行。匹配大小写不敏感，同时兼容错误码与消息子串。

## 错误处理表

| # | 类别 | 匹配条件（错误码 / 消息子串，任一命中即可） | 处理方式 |
|---|---|---|---|
| 1 | 鉴权 / 登录 | `failed to refresh session token`、`Please run 've login'`、`Unauthorized`、`InvalidAccessKey`、`SignatureDoesNotMatch` | 委托 volcengine-cli skill 完成 `ve login`，登录后复用同一个 ClientToken 重试 |
| 2 | 余额不足 / 欠费 / 预留金不足 | `BalanceNotEnough`、`AccountInArrears`、``余额不足`、`欠费`、`预留金不足` | 告知用户账户余额或预留金不足 / 已欠费，引导前往充值页 <https://console.volcengine.com/finance/fund/recharge>；用户完成充值后询问是否重试，重试复用同一个 ClientToken |
| 3 | 未实名认证 | `NotVerifiedAccount`、`未实名`、`未实名认证`、`has not been verified` | 明确告知用户"账号尚未完成实名认证，无法下单"，禁止表述为"认证信息不完善 / 未完善 / 不满足"；引导前往实名认证控制台 <https://console.volcengine.com/user/authentication/> 完成个人 / 企业实名认证；认证通过后询问是否重试，重试复用同一个 ClientToken |
| 4 | 弱实名认证不支持购买 | `WeakVerified`、`弱实名`、`weak verified`、`weak verification` | 明确告知用户"当前账号为弱实名认证，不支持购买该商品"，禁止表述为"认证信息不完善 / 未完善 / 不满足"；引导前往实名认证控制台 <https://console.volcengine.com/user/authentication/> 升级为强实名认证（个人 / 企业），完成后询问是否重试，重试复用同一个 ClientToken |
| 兜底 | 其他业务错误 | 上述均未命中 | 原样展示实际错误码与消息，附商品专属控制台链接（见对应 `<product>.md`）作为替代方案，询问用户是否重试 |

## 扩展新错误处理

新增一类错误分类时：

1. 在错误处理表兜底行之前追加一行，写明匹配条件（错误码或消息子串）与处理方式。
2. 更精确、更具体的分类必须排在更宽泛的分类之前，避免被上游行提前命中。
3. 处理方式中的引导链接必须是官方控制台真实地址，严禁臆造。
