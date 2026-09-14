# 审计事件查询

用于只读查询 CloudTrail 审计事件、定位登录和资源操作证据，并在用户需要完整日志时输出带字段注释的
JSONC。

## 快速决策

- 用户要查登录、登出、资源创建/删除/修改、失败事件、RequestID 或 EventID 对应的审计记录。
- 用户只给出资源 ID、用户名、产品名或中文动作，需要先判断合适的查询条件。
- 用户明确要求“完整审计日志 / 原始审计日志 / EventDetail”。

## 查询前检查

- 已通过主 `SKILL.md` 的前置条件确认账号、profile/default 与地域。
- 明确查询窗口；用户未给时间时默认最近 3 天。
- 单次只读查询最多 50 条。继续翻页需要用户明确要求下一页，并携带原查询指纹。

## 条件选择

- 登录：明确登录用 `--signin-action login`，明确登出用 `logout`；其他 signin 行为用 `other`，只按
  `EventSource=signin` 宽查一次。
- 资源操作：优先使用 `--resource-id <id>`；明确写操作再加 `--operation write`，明确读操作加 `read`。
- 其他事件先运行本 skill 的 `events resolve`。返回 `action-unique` 时仅表示本地 Action 候选唯一，仍需审计
  支持范围证据后才可使用 `ResolvedEventName`；返回
  `ambiguous` 时先结合用户原话、动作语义、资源类型与读写属性判断。
- 语义判断仍不唯一或返回 `unresolved` 时，`volcengine-api` / `volcengine-knowledge-search` 是可选补证手段。
  相应 skill 已安装且补证有助于当前判断时再使用；跳过补证或补证后仍不唯一，都按同一降级规则处理：
  已有 ResourceID 时去掉存疑的 EventSource/EventName 宽查一次并说明精度下降；没有 ResourceID 时请用户补充上下文。
- Action 拼写存在只证明 API 存在；使用 CloudTrail 条件前还要确认审计支持范围。
- 登录条件与资源条件分开查询；`--operation` 和 `--resource-id` 配套使用；重复或冲突条件在 API 前拒绝。

IAM 用户名可映射为 `IdentityType=IAMUser` 与 `IdentityName=<name>`。数字 IAM 用户 ID 不能直接作为
`IdentityName`，应先用 IAM 只读能力解析用户名。

## 时间与分页

- 相对时间优先用 `--lookback-days <1..90>`，由同一进程基于同一个 UTC `now` 计算起止秒，避免手算边界漂移。
- 绝对时间支持 Unix 秒、带时区 RFC3339、`YYYY-MM-DD` 和本地时间 `YYYY-MM-DD HH:MM:SS`。无时区输入按
  Asia/Shanghai 解释；仅日期作为 `EndTime` 时按当天 `23:59:59` 处理。
- 未来、倒序、明显超过 90 天、或开始时间明显早于当前时刻前 90 天时，返回结构化纠错信息（字段、原因、
  允许范围和建议命令）。贴近 90 天边界的执行漂移按秒级安全余量收窄，当前实现预留 60 秒。
- `--lookback-days` 与 `--start-time` / `--end-time` 互斥。未指定时间时默认最近 3 天。
- 普通查询默认 10 条，单次最多 50 条；有边界的 `--all` 也只请求一页 50 条。
- `HasMore=true` 表示还有结果。用户明确要求下一页时，原样重传起止时间、筛选条件、数量模式、
  `NextToken` 和 `QueryFingerprint`；每次取一页。
- 输出 `ResolvedWindow`，其中包含最终采用的 UTC 起止时间与来源，便于确认结构化纠错后的有效窗口。

## agent 内部调用示例

```bash
python3 scripts/cloud_trail.py events lookup --signin-action login --lookback-days 3
python3 scripts/cloud_trail.py events lookup --resource-id vpc-<id> --operation write --lookback-days 7
python3 scripts/cloud_trail.py events lookup --start-time <recent-rfc3339-start> --end-time <recent-rfc3339-end> --condition ErrorCode=AccessDenied --all
```

## 完整日志输出

结果按 `EventTime` 倒序，默认省略原始 `EventDetail`。用户要求查看完整审计日志或原始审计日志时加 `--raw`。
该模式的 stdout 直接渲染 `AnnotatedEventLogs` 的 JSONC 文本，格式为 `"Field": value, // 字段含义`；顶层与
嵌套对象字段都必须带注释。若 `EventDetail` 是可解析的 JSON object，展示其内部内容并加注释，省略外层
`"EventDetail": ...` 字段本身；按 `AnnotatedEventLogs` 转述。保留事件自身的 `RequestID`，成功 envelope 放在
`ApiResponse`，并对用户保留调用 `LookupEvents` 的顶层 `ResponseMetadata.RequestId`。空结果必须连同
账号、profile/default、地域与 `ResolvedWindow` 表述。

## 解析事件名

名称不确定时先用 `events resolve` 读取本地 `ve <service>` metadata，必要时配合其 `--doc-search`：

```bash
python3 scripts/cloud_trail.py events resolve --service vpc --keyword Delete --resource-id vpc-<id> --operation write
```

返回 `ambiguous` 时，先结合用户原话、动作语义、资源类型和读写属性判断候选；字符串候选不唯一时继续做
语义判断。语义判断后仍不能唯一确认，或返回 `unresolved` 时，可以在用户已安装相应 skill 的前提下，
选择用 `volcengine-api` / `volcengine-knowledge-search` 补证；外部 skill 是可选补证手段。跳过补证或补证后仍不唯一时，有 ResourceID 就按上方规则宽查一次，否则请用户补充
上下文。机器字段 `RecommendedLookupMode=semantic-review` 表示先做语义判断；
`ExternalFallback.Required=false` 明确外部兜底可选，`NextWithoutExternalFallback` 与
`AfterExternalFallback` 分别给出不使用外部 skill、以及外部补证无结论时的降级动作。

## 条件 allowlist

`EventSource`、`EventName`、`IdentityType`、`IdentityName`、`EventID`、`RequestID`、
`AccessKeyID`、`Region`、`ResourceType`、`ResourceID`、`ApiVersion`、`ErrorCode`、`ReadOnly`。
`ReadOnly` 必须是字符串 `true` 或 `false`。

## 输出规范

- 先给结论，再列关键证据字段。
- `SourceIPAddress` 解释为“来源 IP”。
- 空结果表述为当前账号、地域和时间范围内无记录。
- 多条候选按时间倒序；证据不足时明确无法唯一确认。
