# Trail 管理

CloudTrail Trail 相关 Action 为 `DescribeTrails`、`CreateTrail`、`UpdateTrail`、`StartLogging`、
`StopLogging` 和 `DeleteTrail`，版本固定为 `2021-09-01`。

## 任务范围

- 用户要列出、创建、更新、开启、停止或删除操作审计 Trail。
- 用户要把审计日志投递到 TOS 或 TLS，包含同账号或跨账号投递。
- 用户要检查 Trail 是否启用、投递目标是否正确、组织级 Trail 是否存在。

## 操作前核对

- 已通过主 `SKILL.md` 确认账号、profile/default 与地域。
- 写操作先 dry-run，面向用户只展示【操作摘要 + 特殊提醒 + 下一步动作】。
- 组织级 Trail 的创建、更新、删除需要在摘要中明确组织作用域和潜在投递量影响。
- 跨账号投递需要目标账号身份或权限，用于准备 IAM 角色和 TOS/TLS 投递资源。

## 查询与组织作用域

```text
python3 scripts/cloud_trail.py trails list
python3 scripts/cloud_trail.py trails list --trail-name <trail-name>
python3 scripts/cloud_trail.py trails list --include-organization-trail
```

默认输出 JSON；需要其他格式时把全局 `--format` 放在 `trails` 前，例如
`python3 scripts/cloud_trail.py --format table trails list`。

`TrailType=0` 是单账号 Trail，`TrailType=1` 是组织 Trail。创建、更新或删除组织 Trail 时，预案的摘要和
影响必须明确写出组织作用域及潜在投递量影响，并取得针对“组织级 Trail”的单独确认；普通 Trail 的模糊同意不能复用。

## 写操作确认

先执行不带确认参数的命令。CLI stdout 的预案只渲染【操作摘要 + 特殊提醒 + 下一步动作】；面向用户也只转述
这三段。取得用户明确同意后，agent 使用同一参数加确认标记执行：

```text
--confirm
```

确认调用会重新读取身份与状态；若目标状态已经变化，按当前状态执行现有保护逻辑，不使用额外确认令牌机制。

## 创建

- `CreateTrail` 必须显式传 `EventRW=All|Read|Write`；这是服务端实测必填兼容约束。
- 选择器使用二选一形态：`IncludeAllEventSources=true`；或 `IncludeAllEventSources=false` 且
  `EventSources` 非空。
- 未传 `--event-source` 时创建默认 `IncludeAllEventSources=true`；传入一个或多个 `--event-source` 时
  固定为 false。更新若将移除最后一个选择器则阻断。
- 创建至少有一个完整 TOS 或 TLS 投递目标。默认确认后执行 `CreateTrail -> DescribeTrails 校验 -> StartLogging`
  并校验开启状态，不再要求用户二次确认开启。只有显式传 `--no-auto-start` 时才跳过自动开启。

agent 内部调用示例（初次均为预览）：

```text
python3 scripts/cloud_trail.py trails create --trail-name <trail-name> --event-rw All --tos-bucket-region <region> --tos-bucket-name <bucket>
python3 scripts/cloud_trail.py trails create --trail-name <trail-name> --event-rw Write --event-source ecs --tos-bucket-region <region> --tos-bucket-name <bucket>
python3 scripts/cloud_trail.py trails update --trail-name <trail-name> --event-rw Write
python3 scripts/cloud_trail.py trails start --trail-name <trail-name>
python3 scripts/cloud_trail.py trails stop --trail-name <trail-name>
python3 scripts/cloud_trail.py trails delete --trail-name <trail-name>
```

## 更新

更新先读取 current，将 patch 合并为 effective config 后校验。API 请求包含用户明确给出的 patch；若服务端
字段耦合要求，还会从 current 补入使该 patch 生效所需的最小主目标字段，不携带其他无关字段。

- TOS 目标字段由 `TosBucketRegion` + `TosBucketName` 触发服务端合并；更新 account、role、prefix、
  project 或 SSE 字段时，带上当前 region/name 作为主目标字段。
- TLS 目标字段由 `TlsProjectRegion` + `TlsProjectName` + `TlsTopicName` 触发合并；更新其他 TLS
  字段时，带上当前 region/project/topic 作为主目标字段。
- 更新前后都按 effective config 验证投递目标完整性、selector、跨账号与 SSE 约束。写后比较期望字段；
  返回成功但状态不一致时输出 `StateVerified=false`。

## TOS SSE 与跨账号

- `TosSSEAlgorithm=kms` 同时提供格式合法的 KMS key TRN（字段 `TosSSEKMSKeyID`）；算法为
  `AES256` 或空时省略该字段。
- 跨账号 TOS 投递使用未启用 SSE 的 TOS 目标。
- 跨账号 TOS/TLS 必须提供目标账号 ID 与格式合法的写入角色 TRN；TRN 中账号必须等于目标资源账号。
- 更新时基于 effective config 判断跨账号；取得调用方数字 AccountId 后再校验投递配置。
- 创建跨账号 Trail 时，默认先完成目标账号资源准备：确认或创建 TOS/TLS 投递资源，创建或复用资源账号中的
  写入角色，绑定 `CloudTrailDeliveryPolicy`，并信任创建 Trail 账号的 `ServiceRoleForCloudTrail` 执行
  `sts:AssumeRole`。脚本预案会输出 `PreparationDefault=agent-managed` 和对应准备步骤。

## 启停、删除与验证

- `StopLogging` 会停止新的审计记录和投递，是独立写操作，必须独立预览和确认。
- 删除前严格分页列出全部补投任务；所有分页读取成功且该 Trail 无 `PENDING` / `RUNNING` 任务后再删除。
  确认前重新核对目标状态，以覆盖预检后的并发变化。
- wrapper 对写 API 只发起一次 `ve` 调用；`ve` / SDK 内部重试由底层控制。成功 envelope 通过 `ApiResponse` 传递，并向用户保留顶层
  `ResponseMetadata.RequestId`。写结果输出 `WriteAccepted` / `StateVerified`；只读验证失败或未收敛时
  不得直接重试写入。

## 输出规范

- 预案转述只包含操作摘要、特殊提醒和下一步动作。
- 操作摘要写清账号、Trail 名、事件源范围、读写范围、投递目标和实际动作链路。
- 特殊提醒只放会影响用户决策的内容，例如自动开启、组织级影响、跨账号资源准备、停止后的记录影响。
- 写结果区分 `WriteAccepted` 与 `StateVerified`；`StateVerified=false` 时说明需要只读复查。
