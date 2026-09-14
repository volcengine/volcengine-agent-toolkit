---
name: volcengine-cloud-trail
description: >-
  Use when the user asks to query Volcengine CloudTrail audit logs, investigate
  login or resource operations, or manage CloudTrail trails and backfill delivery
  tasks. Trigger on 操作审计, 审计日志, CloudTrail, cloud_trail, trail, 跟踪,
  历史补投, or backfill in a Volcengine context. Audit queries are read-only;
  trail and backfill mutations require an explicit preview and confirmation.
license: MIT
version: 1.0.0
user-invocable: true
allowed-tools: Bash, Read
metadata:
  openclaw:
    requires:
      bins:
        - ve
        - python3
    install:
      - kind: node
        package: "@volcengine/cli"
        bins: [ve]
    envVars:
      - name: VOLCENGINE_ACCESS_KEY
        required: false
        description: AccessKey for AK/SK auth path (alternative to ve login)
      - name: VOLCENGINE_SECRET_KEY
        required: false
        description: SecretKey for AK/SK auth path
      - name: VOLCENGINE_SESSION_TOKEN
        required: false
        description: Optional STS session token for temporary credentials
      - name: VOLCENGINE_REGION
        required: false
        description: Default region used by ve when the profile has none
---

# 火山引擎操作审计

通过 `ve cloudtrail`（`Version=2021-09-01`）查询审计事件，并安全管理 Trail 与历史补投任务。

## 速查

| 项目 | 说明 |
| --- | --- |
| 适用场景 | 操作审计日志查询、登录/资源操作溯源、Trail 管理、历史补投任务管理 |
| 核心能力 | 审计事件查询（只读）、事件名解析（只读）、Trail 列表/创建/更新/启停/删除、补投列表/详情/创建/停止 |
| 底层调用 | `scripts/cloud_trail.py` 封装 `ve cloudtrail <Action>`，版本固定 `2021-09-01` |
| 写操作 | Trail 创建/更新/启停/删除、补投创建/停止，均先预览，用户确认后执行 |
| 主要参考 | [event-query.md](references/event-query.md)、[event-trail-management.md](references/event-trail-management.md)、[backfill-delivery-tasks.md](references/backfill-delivery-tasks.md) |

## 能力

| 能力 | 做什么 | 子命令 | 必读参考 |
| --- | --- | --- | --- |
| 审计事件查询 | 查询登录、资源操作、失败事件，输出摘要或带注释完整日志 | `events lookup` | [event-query.md](references/event-query.md) |
| 事件名解析 | 根据服务、关键词、资源和读写属性判断 `EventSource` / `EventName` 候选 | `events resolve` | [event-query.md](references/event-query.md) |
| Trail 管理 | 列出、创建、更新、启停、删除操作审计 Trail | `trails ...` | [event-trail-management.md](references/event-trail-management.md) |
| 历史补投 | 列出、查看、创建、停止历史补投任务 | `backfill ...` | [backfill-delivery-tasks.md](references/backfill-delivery-tasks.md) |

## 什么时候用

- 用户要查操作审计、审计日志、CloudTrail、登录记录、资源变更记录、失败事件或 RequestID / EventID 对应事件。
- 用户要确认某个火山资源是谁创建、删除、修改，或需要按资源 ID、用户、事件名、错误码定位审计证据。
- 用户要创建、更新、开启、停止或删除操作审计 Trail。
- 用户要查看、创建或停止历史补投任务，或判断补投任务与 Trail 删除之间的依赖。
- 用户消息里出现「火山 / 火山引擎 / volcengine」且属于操作审计、跟踪、Trail、历史补投、CloudTrail 场景。

## 前置条件

- `ve` CLI 与 `python3` 可用，并已通过 `ve configure` 或环境变量完成鉴权。
- 鉴权、profile、CLI 安装或会话失败时，使用 `volcengine-cli` skill 处理登录/配置；本 skill 只处理 CloudTrail
  业务动作。
- 固定 profile 后，身份确认和后续 CloudTrail 调用使用同一 profile。每个会话首次签名调用、重新鉴权或
  profile 改变后，先只读确认调用账号。
- 只有用户明确指定时才传 `--profile` 或 `--region`。结论里说明账号、profile/default 解析、地域和时间范围。
- 补投创建能力需要运营开白。账号内已有任一补投任务记录时，可视为当前账号已完成补投能力开白。

## agent 内部调用

从本 skill 目录执行：

```bash
python3 scripts/cloud_trail.py --help
python3 scripts/cloud_trail.py events lookup --signin-action login --lookback-days 3
python3 scripts/cloud_trail.py events resolve --service vpc --keyword Delete --resource-id vpc-<id> --operation write
python3 scripts/cloud_trail.py trails list
python3 scripts/cloud_trail.py backfill list
```

默认输出格式就是 JSON，读操作通常直接省略 `--format json`。需要 `md` 或 `table` 时，`--format` 是全局参数，
放在 `events` / `trails` / `backfill` 之前，例如：

```bash
python3 scripts/cloud_trail.py --format table trails list
python3 scripts/cloud_trail.py --format md backfill list --page-number 1 --page-size 100
```

## 工作流

所有动作通过 `scripts/cloud_trail.py` 完成（命令相对本 skill 目录执行）。

### 审计事件查询（只读）

```text
python3 scripts/cloud_trail.py events lookup --signin-action login --lookback-days 3
python3 scripts/cloud_trail.py events lookup --resource-id vpc-<id> --operation write --lookback-days 7
python3 scripts/cloud_trail.py events lookup --raw --request-id <request-id>
```

- 相对时间优先用 `--lookback-days <1..90>`；绝对时间支持 Unix 秒、RFC3339、`YYYY-MM-DD` 和本地时间。
- 贴近 90 天边界时使用秒级安全余量，当前实现预留 60 秒。
- 单次查询最多 50 条；下一页只在用户明确要求时，携带原查询指纹取一页。
- `EventSource` / `EventName` 不确定时先运行 `events resolve`。`ambiguous` 时结合用户原话、动作语义、资源类型
  和读写属性判断；语义仍不唯一或结果为 `unresolved` 时，已安装的 `volcengine-api` 与
  `volcengine-knowledge-search` 可作为补证。已有 ResourceID 时可去掉存疑条件宽查一次；仍无法判断时请用户补充上下文。

### Trail 管理（写操作需确认）

```text
python3 scripts/cloud_trail.py trails list
python3 scripts/cloud_trail.py trails create --trail-name <trail-name> --event-rw All --tos-bucket-region <region> --tos-bucket-name <bucket>
python3 scripts/cloud_trail.py trails update --trail-name <trail-name> --event-rw Write
python3 scripts/cloud_trail.py trails start --trail-name <trail-name>
python3 scripts/cloud_trail.py trails stop --trail-name <trail-name>
python3 scripts/cloud_trail.py trails delete --trail-name <trail-name>
```

- 创建 Trail 必须显式传 `EventRW=All|Read|Write`，并至少配置一个完整 TOS 或 TLS 投递目标。
- 创建确认后默认执行 `CreateTrail -> DescribeTrails 校验 -> StartLogging -> DescribeTrails 校验`，不再二次确认开启。
- 创建跨账号 Trail 时，agent 默认先完成目标账号 IAM 角色和 TOS/TLS 投递资源配置，再创建 Trail；缺少目标账号身份
  或权限时请用户补齐。
- 删除 Trail 前严格分页检查补投任务；全部任务均非 `PENDING` / `RUNNING` 后再删除。

### 历史补投（写操作需确认）

```text
python3 scripts/cloud_trail.py backfill list --page-number 1 --page-size 10
python3 scripts/cloud_trail.py backfill describe --task-id bdt-<id>
python3 scripts/cloud_trail.py backfill create --trail-name <trail-name> --start-time <recent-rfc3339-start> --end-time <recent-rfc3339-end> --enable-tos
python3 scripts/cloud_trail.py backfill stop --task-id bdt-<id>
```

- 创建或停止补投前先只读查询补投任务。账号内已有任一补投任务记录时，可直接作为已开白依据。
- 未发现历史补投任务记录时，预案请用户确认补投功能已开白；用户确认后，agent 加开白确认与写入确认标记执行。
- 创建前严格分页检查账号内全部任务；存在任一 `PENDING` / `RUNNING` 活跃任务时停止创建。
- 补投窗口满足 `EndTime < now`、`EndTime > StartTime`、`StartTime` 在近 90 天内，单任务跨度不超过 90 天。

## agent 执行流程

1. 判断诉求：事件查询、事件名解析、Trail 管理，还是历史补投。
2. 读取对应参考文档，按参考文档选择参数和校验条件。
3. 首次签名调用先只读确认账号、profile/default、地域；身份符合预期后继续。
4. 查询类请求直接执行并汇报证据。涉及完整日志时使用 `events lookup --raw`，按 JSONC 注释格式转述。
5. 写操作先 dry-run，向用户只展示【操作摘要 + 特殊提醒 + 下一步动作】；用户回复「确认执行」后，使用同一参数
   加确认标记执行。
6. 写入成功后读取验证结果。`WriteAccepted=true` 只表示控制面受理；只有 `StateVerified=true` 才表述为已生效。

## 输出规范

- 查询结论先行，再列 `EventTime`、`EventName`、`EventSource`、`UserName`、`SourceIPAddress`、`Region`、
  `ErrorCode`、`RequestID`、`EventID` 和 `RelatedResources`。
- 用户要求完整审计日志或原始审计日志时使用 `events lookup --raw`。该模式 stdout 直接渲染
  `AnnotatedEventLogs` 的 JSONC 文本，格式为 `"Field": value, // 字段含义`；顶层与嵌套对象字段都带注释。
- 若事件包含可解析的 `EventDetail` JSON object，只展示 `EventDetail` 内部内容并加注释，省略外层
  `"EventDetail": ...` 字段本身。`SourceIPAddress` 注释为“来源 IP”。
- 空结果表述为“账号 X 在当前地域与时间范围内无记录”。多条候选按时间倒序；证据不足时明确无法唯一确认。
- stdout 保持结构化，诊断走 stderr；调用级请求 ID 使用 `ResponseMetadata.RequestId`，事件字段使用 `RequestID`。

## 写操作边界

- CloudTrail 业务 API 使用脚本 allowlist；STS 身份确认及公开 API/文档查证是明确例外。
- Trail 与补投写操作都需要预案确认。预案面向用户保持简短，只展示操作摘要、特殊提醒和下一步动作。
- wrapper 对每个 API 只发起一次 `ve` 调用；`ve` / SDK 内部重试由底层控制。
- `StopLogging` 是独立写操作，单独预览和确认。`DeleteTrail` 在确认无活跃补投任务后直接删除。
- API 响应成功后保留 `ApiResponse` envelope，并向用户保留顶层 `ResponseMetadata.RequestId`。
