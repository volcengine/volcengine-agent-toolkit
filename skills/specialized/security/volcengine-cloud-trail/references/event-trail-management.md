# 事件跟踪与投递

CloudTrail Trail 相关 Action 为 `DescribeTrails`、`CreateTrail`、`UpdateTrail`、`StartLogging`、
`StopLogging` 和 `DeleteTrail`，版本固定为 `2021-09-01`。

## 任务范围

- 用户要列出、创建、更新、开启、停止或删除操作审计 Trail。
- 用户要把审计日志投递到 TOS 或 TLS，包含同账号或跨账号投递。
- 用户要检查 Trail 是否启用、投递配置是否正确、组织级 Trail 是否存在。

## 操作前核对

- 创建或变更投递配置时，核对接收日志的存储资源、写入权限、保留策略及费用影响；启停、删除时，核对指定跟踪状态与对应操作的依赖。方案说明本次动作涉及的账号、范围和影响。

- 已按 [rules.md](rules.md) 核实本次操作的账号、实际调用身份、权限与地域；以下技术参数不要求逐项向用户询问。
- 组织级 Trail 的创建、更新、删除需要在摘要中明确组织范围和潜在投递量影响。
- 跨账号投递需要接收日志的资源所属账号的身份或权限，用于准备 IAM 角色和 TOS/TLS 投递资源。

## 查询与组织范围

```text
python3 scripts/cloud_trail.py --expected-account-id <account-id> trails list
python3 scripts/cloud_trail.py --expected-account-id <account-id> trails list --trail-name <trail-name>
python3 scripts/cloud_trail.py --expected-account-id <account-id> trails list --include-organization-trail
```

查找可导出的已投递日志时可直接使用 `--include-organization-trail` 完整检查可见跟踪；空列表按 rules.md 限定账号与范围。

默认输出 JSON；需要其他格式时把全局 `--format` 放在 `trails` 前，例如
`python3 scripts/cloud_trail.py --expected-account-id <account-id> --format table trails list`。

`TrailType=0` 是单账号 Trail，`TrailType=1` 是组织 Trail。创建、更新或删除组织 Trail 时，预案的摘要和
影响必须明确写出组织范围及潜在投递量影响，授权须明确包含组织级操作；已有明确确认不重复询问，只同意操作普通 Trail，不代表同意操作组织 Trail。

## 写操作确认

预览、确认和执行遵循[rules.md 的“操作授权”](rules.md#操作授权)。跟踪写操作的确认参数为：

```text
--confirm
```

确认调用会重新读取身份与状态；跟踪状态变化时按当前状态重新核对方案。

## 创建

### 开通投递

以下创建流程用于管理事件投递。

1. 列出已有跟踪，比较采集账号、事件源、读写范围和日志保存位置。已有配置满足需求时复用；需要调整时说明变更内容。
2. 沿用用户指定的日志保存位置。尚未选定时，根据用途给出方案：检索和分析用 TLS，文件归档用 TOS；同时需要两者时可同时投递到 TOS 和 TLS。沿用已明确的日志存储地域和保留时间，缺项时再确认。
3. 准备 TOS 存储桶或 TLS 日志主题：TOS 核对桶及地域；TLS 核对日志项目、主题及所属地域。资源缺失时，将新建资源列入方案。TLS 的日志项目与资源管理项目分别核对。
4. 核对写入权限、保留策略和用户要求的加密配置。TLS 新主题显式检查保存时长；TOS 留存要求按生命周期或合规保留的实际用途确定配置。复用资源时沿用其现有策略，需要调整则列入方案。
5. 按 rules.md 一次确认资源准备、采集范围、持续投递及相关存储费用。通过 `volcengine-tls` 或 `volcengine-tosutil` 创建对应资源后，再查询确认配置，再创建、开启跟踪，按下文验证。跨账号资源准备见“TOS SSE 与跨账号”。

采集账号范围由用户需求确定；控制台预选项只作参考。用户要求历史日志且需要补投时，创建并开启跟踪后继续[历史补投](backfill-delivery-tasks.md)；历史时段、日志保存位置与费用一并纳入方案。

### 创建跟踪

- `CreateTrail` 必须显式传 `EventRW=All|Read|Write`；实测服务端要求填写此参数。
- 选择器使用二选一形态：`IncludeAllEventSources=true`；或 `IncludeAllEventSources=false` 且
  `EventSources` 非空。
- 未传 `--event-source` 时创建默认 `IncludeAllEventSources=true`；传入一个或多个 `--event-source` 时
  固定为 false。如果更新会移除最后一个事件选择器，则不执行更新。
- 创建时至少提供一组完整的 TOS 或 TLS 投递配置。默认确认后执行 `CreateTrail -> DescribeTrails 校验 -> StartLogging`
  并校验开启状态，不再要求用户二次确认开启。只有显式传 `--no-auto-start` 时才跳过自动开启。
- 跟踪已创建但自动开启调用报错时，保留创建成功结果，再只读核对开启状态；已确认开启则如实说明，未确认时说明开启状态待核实，不重新创建跟踪。

agent 内部调用示例（初次均为预览）：

```text
python3 scripts/cloud_trail.py --expected-account-id <account-id> trails create --trail-name <trail-name> --event-rw All --tos-bucket-region <region> --tos-bucket-name <bucket>
python3 scripts/cloud_trail.py --expected-account-id <account-id> trails create --trail-name <trail-name> --event-rw Write --event-source ecs --tls-project-region <region> --tls-project-name <log-project> --tls-topic-name <topic>
```

## 更新

更新前先读取当前配置，将本次修改合并进去，再检查合并后的配置。API 请求只包含用户明确要求修改的字段；如果服务端要求同时传入存储资源标识，就从当前配置中补齐这些必需字段，不传其他无关字段。

- TOS 配置字段由 `TosBucketRegion` + `TosBucketName` 触发服务端合并；更新 account、role、prefix、
  project 或 SSE 字段时，带上当前 region/name 作为存储资源标识字段。
- TLS 配置字段由 `TlsProjectRegion` + `TlsProjectName` + `TlsTopicName` 触发合并；更新其他 TLS
  字段时，带上当前 region/project/topic 作为存储资源标识字段。
- 从指定事件源切换为全部事件源时，传入 `--include-all-event-sources`，不再传 `--event-source`；后端会清空旧的指定事件源，本地合并配置同步清空旧值。显式同时指定两种范围仍视为冲突。
- 更新前后都检查合并后的配置，确认投递配置齐全、事件选择器有效，并满足跨账号和 SSE 要求。修改后重新读取配置，核对修改的字段；
  返回成功但状态不一致时输出 `StateVerified=false`。

## TOS SSE 与跨账号

- `TosSSEAlgorithm=kms` 同时提供格式合法的 KMS key TRN（字段 `TosSSEKMSKeyID`）；算法为
  `AES256` 或空时省略该字段。
- 跨账号 TOS 投递使用未启用 SSE 的 TOS 存储桶。
- 跨账号 TOS/TLS 必须提供接收日志的资源所属账号 ID 与格式合法的写入角色 TRN；TRN 中账号必须等于接收日志的资源所属账号。
- 更新时根据合并后的配置判断是否跨账号；取得调用方数字 AccountId 后再校验投递配置。
- 创建跨账号 Trail 时，默认先在接收日志的资源所属账号中准备资源：确认或创建 TOS/TLS 投递资源，创建或复用资源账号中的
  写入角色，绑定 `CloudTrailDeliveryPolicy`，并信任创建 Trail 账号的 `ServiceRoleForCloudTrail` 执行
  `sts:AssumeRole`。脚本预案会输出 `PreparationDefault=agent-managed` 和对应准备步骤。

## 启停、删除与验证

- `StopLogging` 停止指定 Trail 的后续记录和投递，不影响其他 Trail，也不删除已有归档；必须单独说明要停止的跟踪和停止影响，取得针对该动作的明确授权；不得从导出、补投或清理授权中推定。相同动作已明确授权时不重复询问。
- 删除前严格分页列出全部补投任务；所有分页读取成功且该 Trail 无 `PENDING` / `RUNNING` 任务后再删除。
  确认前重新核对跟踪状态，避免遗漏预检后发生的状态变化。
- 脚本对每个写 API 只发起一次 `ve` 调用；`ve` / SDK 内部重试由底层控制。接口成功时的完整响应保存在 `ApiResponse` 中，将顶层
  `ResponseMetadata.RequestId` 保留在诊断中，按 rules.md 按需展示。写结果输出 `WriteAccepted` / `StateVerified`；只读验证失败或状态尚未符合预期时
  不得直接重试写入。

## 输出规范

- 操作摘要写清账号、Trail 名、事件源范围、读写范围、投递配置和实际执行的步骤。
- 特殊提醒只放会影响用户决策的内容，例如自动开启、组织级影响、跨账号资源准备、停止后的记录影响。
- 写结果区分 `WriteAccepted` 与 `StateVerified`；`StateVerified=false` 时说明需要只读复查。
- 创建、开启或变更投递配置后，重新查询配置与开启状态，再用开启后产生且符合采集范围的已有事件核对已投递的日志。优先以事件 ID 或请求 ID 关联，结合事件时间和身份核对；TOS 检查对象中的事件，TLS 检查日志样本。同时投递到 TOS 和 TLS 时分别验证。
- `StateVerified` 表示配置检查结果。结果中分别说明配置状态、日志到达情况和保存位置；暂时没有匹配事件时，说明检查了哪些日志，以及之后如何继续检查。需要额外业务操作产生测试事件时，先明确具体动作和影响。
- 用户还要检索或分析时，继续按 [advanced-query.md](advanced-query.md) 检查 TLS 字段与索引，执行原查询。

## 已开启但收不到日志

按已有证据选择检查项，定位后再提出对应变更。

| 现象 | 检查与处理 |
| --- | --- |
| 跟踪已开启，TOS／TLS 中暂时查不到事件 | 核对事件发生时间是否晚于开启时间，以及采集账号、事件源、读写范围是否匹配；历史事件转历史补投流程。 |
| TOS 存储桶或 TLS 日志主题访问失败或出现投递错误 | 核对资源是否存在、地域和账号是否一致，再按实际错误检查写入权限、跨账号角色或 KMS 授权。资源已删除时，准备新的存储桶或日志主题并更新跟踪。 |
| TLS 中存在日志，但检索为空 | 检查日志时间、查询条件、字段及索引，按高级检索流程验证。 |
| 配置与权限正常，匹配事件仍未到达 | 按产品当前投递时效间隔复查，记录事件和存储桶或日志主题的状态；持续异常时提供请求 ID、事件时间及存储桶或日志主题信息用于排查。 |
