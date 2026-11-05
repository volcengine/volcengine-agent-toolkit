# 历史补投任务

相关 Action 为 `ListBackfillDeliveryTasks`、`DescribeBackfillDeliveryTask`、
`CreateBackfillDeliveryTask` 和 `StopBackfillDeliveryTask`，版本固定为 `2021-09-01`。

## 任务范围

- 用户要查看历史补投任务列表或任务详情。
- 用户要把近 90 天内的历史审计事件补投到 Trail 已配置的 TOS / TLS 日志主题。
- 用户要停止 `PENDING` / `RUNNING` 状态的补投任务。
- 用户要删除 Trail，需先确认该 Trail 没有关联的活跃补投任务。

## 操作前核对

- 已按 [rules.md](rules.md) 核实本次操作的账号、实际调用身份、权限与地域；以下技术参数不要求逐项向用户询问。
- 写操作的预览、确认和执行遵循[rules.md 的“操作授权”](rules.md#操作授权)。
- 创建补投时，核对指定 Trail 存在、已启用、具备管理事件 selector，并配置了要补投到的 TOS 存储桶或 TLS 日志主题。
- 账号内已有补投任务记录时，脚本据此通过开通预检；本次可用性继续以当前接口响应核实。
- 首次补投先查已有开通信息；需申请时说明当前账号、地域及官方开通渠道。取得开通确认后，在原方案中继续执行。

## 查询与分页

```text
python3 scripts/cloud_trail.py --expected-account-id <account-id> backfill list --page-number 1 --page-size 10
python3 scripts/cloud_trail.py --expected-account-id <account-id> backfill describe --task-id bdt-<id>
```

默认输出 JSON；需要其他格式时把全局 `--format` 放在 `backfill` 前，例如
`python3 scripts/cloud_trail.py --expected-account-id <account-id> --format table backfill list --page-number 1 --page-size 10`。

`PageNumber` / `PageSize` 为可选参数，默认 1/10；页码使用正整数，页大小为 1..100。普通列举只取请求页；
删除 Trail、重复任务检查等安全预检必须严格翻到 `Total` 覆盖的末页，任何一页读取失败都停止后续操作。

## 创建补投

```bash
python3 scripts/cloud_trail.py --expected-account-id <account-id> backfill create --trail-name <trail-name> --start-time <recent-rfc3339-start> --end-time <recent-rfc3339-end> --enable-tos
```

- `EndTime < now` 且 `EndTime > StartTime`；`StartTime` 落在当前时间前 90 天内，单任务跨度不超过 90 天。
  贴近 90 天边界的执行漂移按秒级安全余量收窄，当前实现预留 60 秒。
- `--enable-tos` / `--enable-tls` 至少一个为 true，且 Trail 对应投递配置完整。
- Trail 必须存在、已启用且具备有效管理事件 selector。
- 一个云账号同时只允许一个活跃补投任务。创建前严格分页查找账号内全部任务；任一 `PENDING` / `RUNNING`
  任务都会阻断，不因关联 Trail、窗口或投递配置不同而放行。
- `CreateBackfillDeliveryTask` 按当前账号与地域的开放情况使用。遇到 `InvalidActionOrVersion`，核对 Action、版本、服务地址及当前账号的能力开通情况；保留错误和请求 ID，向产品支持确认对应环境的接口支持情况。
- CLI metadata 未注册该 Action 时，兼容路径使用 `--force --method GET` 与扁平 Query 参数；仅排障需要时向用户解释该差异。
- API 响应成功且包含 `TaskID` 时，使用该 ID 查询详情并验证。
- 创建前记录已有补投任务 ID。创建响应异常或缺少 `TaskID` 时，按跟踪、时间范围和投递配置全页核对，排除创建前已存在的任务；仅找到唯一新增匹配任务时继续验证，否则说明结果不确定，不自动重试创建。

账号内未发现历史补投任务记录时，用户确认补投能力已开白及本次写操作后，执行时补充：

```text
--whitelist-confirmed --confirm
```

## 停止与删除依赖

```text
python3 scripts/cloud_trail.py --expected-account-id <account-id> backfill stop --task-id bdt-<id>
```

只允许停止 `PENDING` 或 `RUNNING`；任务结束后的状态为 `FAILED`、`STOPPED`、`COMPLETED`。停止接口返回成功后，仍需查询任务是否已停止。
`ApiResponse` 保留成功 envelope，在诊断中保存顶层 `ResponseMetadata.RequestId`，默认不向用户展示，并用
`WriteAccepted` / `StateVerified` 分别表示写入请求是否成功、实际状态是否验证通过；状态尚未符合预期时先做只读复查。

删除 Trail 前必须检查补投任务；存在活跃任务时需先单独完成停止和验证。删除流程不会自动停止任务。

## 输出规范

- 存在活跃任务冲突时，说明冲突任务及对本次补投的影响。
- 开通状态说明所依据的当前确认或历史记录；接口报错时说明待核实的支持范围及后续处理方式。
- 时间窗口同时给出用户输入和解析后的 RFC3339/本地时间，便于核对边界。

## 完整时段转存与下载

仅要求历史补投时，核验任务结果及 TOS／TLS 中的日志范围后结束，无需下载到本地。用户还要求导出或分析时，继续相应操作。

- 用户要求某时段全部日志时，先核对正确账号、已有投递配置及该时段已有日志覆盖；已投递的日志完整覆盖所需范围则直接下载。需补投时核对已完成任务与时间重叠，避免不必要的重复写入；不能仅因当前跟踪启动较晚就断定早期数据不存在。
- 确认方案包含日志时段、事件范围、日志保存位置、保留策略和费用；创建跟踪会持续投递后续日志，必须在预案中说明。涉及临时变更时，将需要恢复的配置和触发条件纳入方案；执行后验证恢复结果。一次确认可覆盖已明确的资源准备、创建跟踪和补投步骤及临时变更的恢复；停止投递仍须单独说明要停止的跟踪和影响，并取得针对停止动作的明确授权，不从上述授权中推定。若涉及的资源或影响改变，再说明变化。
- 任务仍在 PENDING／RUNNING 时按合理间隔检查，不重复创建。执行受阻或当前会话无法继续等待时，保留任务 ID、账号、日志保存位置、时间窗口和最新状态；恢复后先查询原任务，再继续等待或下载，不重新创建任务。
- 用户还要求导出时，等待补投任务终态；投递到 TOS 的日志按 result-export.md 的 TOS 流程下载；投递到 TLS 的日志在补投任务 COMPLETED 后检查实际审计字段和日志时间，再按 [result-export.md](result-export.md) 创建 TLS 离线下载任务、等待文件生成并下载；超过单任务限制时按时间分段。TLS 中已有所需日志时，不为解决下载超限重复补投。部分失败、停止、超时或下载未完成时分别说明实际状态，不报告全部导出成功。
- 导出时，核实下载时间覆盖历史补投日志的真实写入时间，以 EventTime 判断请求的历史时段；主题混存时须有可靠的审计日志筛选条件，不能直接下载主题中全部业务日志冒充审计日志。
- 本次范围为操作审计可补投的管理事件；用户的“全部”若还包含数据事件，先说明实际支持范围，不把管理事件导出称为全部类型日志。
