# 基础检索与结果导出

用于通过 `LookupEvents` 查询近 90 天内的操作审计日志、查看完整事件内容，以及导出查询结果（最多 200 条），并在用户需要完整日志时输出带字段注释的
JSONC。

## 目录

- [使用边界](#使用边界)
- [条件选择](#条件选择)
- [时间与分页](#时间与分页)
- [完整日志输出](#完整日志输出)
- [查询结果导出](#查询结果导出)
- [全部删除事件](#全部删除事件)
- [解析事件名](#解析事件名)

## 使用边界

本文件负责基础检索的参数与使用规则。全量导出已知超出基础能力时，不执行基础导出，转入 result-export.md 的已投递日志下载或 backfill-delivery-tasks.md 的补投流程。用户仅要求字段完整时使用原始事件输出，不因此扩大为全部匹配事件。

## 快速决策

- 用户要查登录、登出、资源创建/删除/修改、失败事件、RequestID 或 EventID 等对应的审计记录。
- 用户只给出资源 ID、用户名、产品名或中文动作，需要先判断合适的查询条件。
- 用户明确要求“完整审计日志 / 原始审计日志 / 日志详情”。

## 查询前检查

- 已按 [rules.md](rules.md) 核实本次操作的账号、实际调用身份、权限与地域。
- 复用用户已给出的条件。常规查看采用用户指定的时间和数量，其余使用默认近 3 天、前 10 条，先返回结果，再按需细化；同时说明实际范围及是否还有结果。
- 用户提供完整事件时，直接解释已有字段，需要补充事实时再查询。要查询的操作或资源不明确时，结合上下文询问一个关键问题。

## 条件选择

- 登录：明确登录用 `--signin-action login`，明确登出用 `logout`；其他 signin 行为用 `other`，只按
  `EventSource=signin` 宽查一次。
- 标识类型结合用户表述、所属产品和上下文确定。应用 ID、资源 ID、账号 ID 分别使用对应查询能力；产品 API Key 的调用记录按该产品日志能力查询，确认是云账号 AK 后使用 `AccessKeyID`。logid 确认为审计请求 ID 后使用 `RequestID`。
- 用户明确查询 IAM 子用户操作或登录时，直接说明本账号权限范围内支持的查询维度，再按已有条件查询。
- 资源操作：优先使用 `--resource-id <id>`；明确写操作再加 `--operation write`，明确读操作加 `read`。
- 构造查询条件需要事件源或事件名、且无法确定时，按[解析事件名](#解析事件名)流程处理。仅按 RequestID、EventID 或资源 ID 等条件查询时，无需额外解析事件名。
- 登录条件与资源条件分开查询；`--operation` 和 `--resource-id` 配套使用；重复或冲突条件在 API 前拒绝。

IAM 用户名可映射为 `IdentityType=IAMUser` 与 `IdentityName=<name>`。数字 IAM 用户 ID 不能直接作为
`IdentityName`，应先用 IAM 只读能力解析用户名。

## 时间与分页

- 月份按上下文确定年份并覆盖整月；年份有歧义时再确认。基础检索范围之外的历史记录按已有 TLS／TOS 日志选择查询方式。
- 相对时间优先用 `--lookback-days <1..90>`，由程序在同一进程中使用同一个 UTC `now` 计算起止时间戳，避免手算不一致。
- 绝对时间支持 Unix 秒、带时区 RFC3339、`YYYY-MM-DD` 和本地时间 `YYYY-MM-DD HH:MM:SS`。无时区输入按
  Asia/Shanghai 解释；仅日期作为 `EndTime` 时按当天 `23:59:59` 处理。
- 未来、倒序、明显超过 90 天、或开始时间明显早于当前时刻前 90 天时，返回错误信息，说明哪个字段有问题、原因、
  允许范围和建议命令。开始时间接近最近 90 天的最早允许时间时，脚本预留 60 秒，避免计算和执行之间的时间差导致请求超出允许范围。
- `--lookback-days` 与 `--start-time` / `--end-time` 互斥。未指定时间时默认最近 3 天。
- 普通查询默认 10 条，单次最多 50 条；有边界的 `--all` 只请求一页 50 条，不代表全部。`--fetch-all` 每页 50 条，固定初次解析的时间与条件，连续查询至末页或 `--max-pages` 上限（默认 20，范围 1..1000）。返回 `Complete`、`HasMore`、`PageCount`、`RequestIds`；重复游标或身份变化时报错，不报告完整。相对时间也是有效查询边界。
- 普通查看中，`HasMore=true` 表示还有结果。用户明确要求下一页时，原样重传起止时间、筛选条件、数量模式、
  `NextToken` 和 `QueryFingerprint`；每次取一页。
- 自动翻页复用首次请求体，仅更新游标；手动续页在原有边界容差内保留原时间窗口，并继续校验查询指纹。服务端拒绝过期窗口或游标时如实报错，不擅自改变起止时间。
- 输出 `ResolvedWindow`，其中包含最终采用的 UTC 起止时间与来源，便于核对脚本最终使用的时间范围。

## agent 内部调用示例

```bash
python3 scripts/cloud_trail.py --expected-account-id <account-id> events lookup --signin-action login --lookback-days 3
python3 scripts/cloud_trail.py --expected-account-id <account-id> events lookup --resource-id vpc-<id> --operation write --lookback-days 7
python3 scripts/cloud_trail.py --expected-account-id <account-id> events lookup --start-time <recent-rfc3339-start> --end-time <recent-rfc3339-end> --condition ErrorCode=AccessDenied --all
```

## 完整日志输出

结果按 `EventTime` 倒序，默认省略原始 `EventDetail`。用户要求查看完整审计日志或原始审计日志时加 `--raw`。
`--raw` 表示输出本次查询返回的每条事件的完整内容，不会自动翻页或获取全部匹配日志；返回条数仍受查询及分页参数限制。
该模式的 stdout 输出完整 JSONC 响应，保留 `AuthContext`、`Query`、`ResolvedWindow`、`HasMore`、`NextToken`、
`QueryFingerprint`、`PaginationNote` 及调用响应元数据。`Events` 中的事件字段以 `"Field": value, // 字段含义` 展示，
事件顶层与嵌套对象字段都带注释，`SourceIPAddress` 注释为“来源 IP”。若 `EventDetail` 是可解析的 JSON object，展示其内部内容并加注释，省略外层
`"EventDetail": ...` 字段本身；按 `Events` 中的带注释内容转述。保留事件自身的 `RequestID`，接口成功时的完整响应 放在
`ApiResponse`，将调用 `LookupEvents` 的顶层 `ResponseMetadata.RequestId` 保留为诊断证据，默认不向用户展示。空结果必须连同
账号、地域和实际时间范围表述；profile 与 `ResolvedWindow` 原始结构保留在诊断中。

## 查询结果导出

使用 `events export`，查询条件和时间参数与 `events lookup` 一致；通过 `--output-file` 指定文件，
`--export-format json|csv` 指定导出格式，默认为 JSON。CSV 中的嵌套对象和数组保存为 JSON 字符串。
不接受 `--next-token`、`--all` 或 `--raw`。

```bash
python3 scripts/cloud_trail.py --expected-account-id <account-id> events export --signin-action login --lookback-days 3 --output-file ./signin-events.json
python3 scripts/cloud_trail.py --expected-account-id <account-id> events export --resource-id vpc-<id> --operation write --lookback-days 7 --export-format csv --output-file ./resource-events.csv
```

返回字段包括 `OutputFile`、`ExportedCount`、`HasMore`、`Complete`、实际 `Query`、`AuthContext` 和调用 `RequestIds`；
分页或文件生成失败时，返回错误及 `FetchedCount`。

执行规则：

- 沿用已执行查询时，保持账号与筛选条件不变，传入固定的 `--start-time`、`--end-time`，不重新使用相对时间计算窗口；尚未查询时，先明确账号、筛选条件和时间范围。
- 用户仅要求保存已获取的结果时，不重新扫描日志；需要继续获取结果时，自动连续分页，无需每页再次询问，分页过程中保持查询条件和时间范围不变。
- `events export` 最多导出 200 条；保存已查到的结果时，按这些结果的实际条数保存。如果事先不知道数量，导出后发现达到上限且仍有结果，记录未导完的情况，再按 result-export.md 继续导出其余日志。不把只含部分日志的文件当作最终结果；只有符合该文档中提供部分结果的条件时，才提供这个文件。
- 文件保存完整事件字段与查询范围，不以展示用摘要替代原始日志。可附操作结果、资源名称等解释列，但保留其来源，不擅自替换原字段；已有文件不覆盖。
- 成功后返回文件路径或下载入口，并说明实际导出条数、时间范围及筛选条件。
- 无匹配日志时不生成文件，说明当前查询范围及筛选条件下未查到记录；分页或文件生成失败时，说明失败情况及已获取条数，不提供未完成的文件。
- 用户需要超出基础检索导出上限的完整日志时，按 [result-export.md](result-export.md) 的导出方式处理，不通过反复拆分基础检索绕过上限。

## 全部删除事件

- 未指定资源或产品时，不只查询某一个 Delete API。先判断基础检索是否能满足所需范围和规模；小规模可在固定窗口内检查非只读操作全部分页，并读取事件详情的 `OperationType`；复杂条件或大量数据转高级检索。
- `OperationType=Delete` 可能包含解绑标签等操作。汇总时分别标明资源删除和其他删除类行为，不能将解绑标签表述为资源被删除。
- 分类字段缺失时，结合具体事件语义判断；仅凭名称含 Delete/Remove 等只能作为候选，不宣称覆盖所有删除行为。分类或数据覆盖存在缺口时说明限制。

## 解析事件名

查询条件涉及事件源或事件名且无法确定时，先用 `events resolve` 读取本地 `ve <service>` metadata，必要时配合其 `--doc-search`：

```bash
python3 scripts/cloud_trail.py events resolve --service vpc --keyword Delete --resource-id vpc-<id> --operation write
```

返回 `action-unique` 时，仅表示本地 Action 候选唯一；仍需确认审计支持范围后，才可使用 `ResolvedEventName` 作为查询条件。

- 返回 `ambiguous` 时，结合用户描述、操作含义、资源类型和读写属性，判断哪个事件名符合需求。名称匹配到多个事件时，不直接选第一条。
- 仍无法确定事件名，或返回 `unresolved` 时，如果已安装 `volcengine-api` / `volcengine-knowledge-search`，可以用它们查资料核实，但不是必需步骤。
- 未查资料，或查过后仍无法确定时，如果已有 ResourceID，可以去掉不确定的 EventSource/EventName 查询一次，并说明结果可能包含其他操作；没有 ResourceID 时，请用户补充信息。
- 返回字段 `RecommendedLookupMode=semantic-review` 表示先根据用户描述和操作含义判断事件名；`ExternalFallback.Required=false` 表示不强制使用其他 skill 查资料。`NextWithoutExternalFallback` 和 `AfterExternalFallback` 分别说明不使用其他 skill、以及查资料后仍无法确定时，可以继续做什么。

## 条件 allowlist

`EventSource`、`EventName`、`IdentityType`、`IdentityName`、`EventID`、`RequestID`、
`AccessKeyID`、`Region`、`ResourceType`、`ResourceID`、`ApiVersion`、`ErrorCode`、`ReadOnly`。
`ReadOnly` 必须是字符串 `true` 或 `false`。

## 输出规范

用户沟通遵循 [rules.md](rules.md#用户沟通与证据)，下列仅为本能力的补充。

- 先给结论，再列关键证据字段。
- `SourceIPAddress` 解释为“来源 IP”。
- 空结果表述为“当前查询范围及筛选条件下未查到匹配记录”。
- 多条候选按时间倒序；证据不足时明确无法唯一确认。

## 查不到事件或字段缺失

- 查不到已知操作时，核对账号、地域、时间及时区、EventSource/EventName；有 RequestID 时用它定位。调用来自其他系统时，先核实该产品与操作的审计接入范围。
- 怀疑筛选条件时，在同一账号和时间窗口内去掉一个条件对照原始事件，再按原要求筛选。关联字段缺失时，将匹配结论标为待核实。
- 请求、响应或资源字段缺失时，对照原始事件和该操作的公开记录范围，核实是否为未记录、脱敏、接口未返回或页面未展示。原因随核实结果说明。

## 操作身份与历史变更

- `UserIdentity` 表示日志中的调用身份。共享账号、角色会话或服务代调用需结合会话与身份记录定位具体人员；历史身份或 AK 的归属按事件发生时的信息核实。
- 结合 `EventType`、`UserAgent`、AK 和 `SourceIPAddress` 判断调用来源。保留来源 IP 原值，结合代理或服务调用链核实终端来源与安全风险。
- 回溯资源或权限变更时，按 Action、事件时间及执行结果整理记录。删除事件缺少旧策略、或变更记录不全时，说明只能还原哪些内容。

查询当前管理员、权限或在线设备时，使用对应产品的身份、权限或会话查询能力；审计日志用于说明相关历史操作。
