# 历史补投任务

相关 Action 为 `ListBackfillDeliveryTasks`、`DescribeBackfillDeliveryTask`、
`CreateBackfillDeliveryTask` 和 `StopBackfillDeliveryTask`，版本固定为 `2021-09-01`。

## 任务范围

- 用户要查看历史补投任务列表或任务详情。
- 用户要把近 90 天内的历史审计事件补投到 Trail 已配置的 TOS / TLS 目标。
- 用户要停止 `PENDING` / `RUNNING` 状态的补投任务。
- 用户要删除 Trail，需先确认该 Trail 没有关联的活跃补投任务。

## 操作前核对

- 已通过主 `SKILL.md` 确认账号、profile/default 与地域。
- 目标 Trail 存在、已启用、具备管理事件 selector，并配置了要补投的 TOS 或 TLS 投递目标。
- 账号内已有任一补投任务记录时，视为已完成补投能力开白。
- 账号内未发现历史补投任务记录时，通过简洁预案请用户确认补投能力已开白。

## 查询与分页

```text
python3 scripts/cloud_trail.py backfill list --page-number 1 --page-size 10
python3 scripts/cloud_trail.py backfill describe --task-id bdt-<id>
```

默认输出 JSON；需要其他格式时把全局 `--format` 放在 `backfill` 前，例如
`python3 scripts/cloud_trail.py --format table backfill list --page-number 1 --page-size 10`。

`PageNumber` / `PageSize` 为可选参数，默认 1/10；页码使用正整数，页大小为 1..100。普通列举只取请求页；
删除 Trail、重复任务检查等安全预检必须严格翻到 `Total` 覆盖的末页，任何页失败均 fail closed。

## 创建补投

```bash
python3 scripts/cloud_trail.py backfill create --trail-name <trail-name> --start-time <recent-rfc3339-start> --end-time <recent-rfc3339-end> --enable-tos
```

- `EndTime < now` 且 `EndTime > StartTime`；`StartTime` 落在当前时间前 90 天内，单任务跨度不超过 90 天。
  贴近 90 天边界的执行漂移按秒级安全余量收窄，当前实现预留 60 秒。
- `--enable-tos` / `--enable-tls` 至少一个为 true，且 Trail 对应投递目标完整。
- Trail 必须存在、已启用且具备有效管理事件 selector。
- 一个云账号同时只允许一个活跃补投任务。创建前严格分页查找账号内全部任务；任一 `PENDING` / `RUNNING`
  任务都会阻断，不因关联 Trail、窗口或投递目标不同而放行。
- `CreateBackfillDeliveryTask` 是隐藏能力。确认 Action/version/endpoint 均正确后，
  `InvalidActionOrVersion` 通常表示账号未开白；停止并提示联系运营，不重复调用。
- CLI metadata 未注册该 Action 时，兼容路径使用 `--force --method GET` 与扁平 Query 参数；对外表述为兼容路径。
- API 响应成功后复用 `TaskID` 查询详情；响应超时或缺 TaskID 时先按 Trail、窗口、目标全页核对，
  找到匹配任务则按已创建处理，未找到时报告结果不确定。

账号内未发现历史补投任务记录时，预览只向用户展示操作摘要、特殊提醒和下一步动作。用户确认开白后，agent 在下一次
执行中补充：

```text
--whitelist-confirmed --confirm
```

## 停止与删除依赖

```text
python3 scripts/cloud_trail.py backfill stop --task-id bdt-<id>
```

只允许停止 `PENDING` 或 `RUNNING`；终态为 `FAILED`、`STOPPED`、`COMPLETED`。停止成功只表示控制面受理，
`ApiResponse` 保留成功 envelope，对用户输出顶层 `ResponseMetadata.RequestId`，并用
`WriteAccepted` / `StateVerified` 区分受理和有效后态；未收敛时先做只读复查。

删除 Trail 前必须检查补投任务；存在活跃任务时需先单独完成停止和验证。删除流程不会自动停止任务。

## 输出规范

- 补投创建预案只展示操作摘要、特殊提醒和下一步动作。
- 只读预检结果可说明账号、profile/default、地域、已有任务数量、是否存在活跃任务、可用 Trail。
- 开白判断优先使用已有补投任务记录；未发现记录时再请用户确认。
- 时间窗口同时给出用户输入和解析后的 RFC3339/本地时间，便于核对边界。
