# 配置审计投递

投递渠道决定把哪些数据发到哪里。例如，可以把高风险不合规事件发到一个 SNS 主题，也可以把每日资源快照存到一个 TOS 桶。

## 查看已有投递

以下命令在本 skill 目录下运行。默认查看当前账号。查看账号组时，用 `ve config ListAccountGroups` 找到组 ID。后续每条投递命令都使用同一个 `--group`。

```bash
python3 scripts/compliance.py delivery list
python3 scripts/compliance.py delivery list --group '<账号组 ID>'
python3 scripts/compliance.py delivery show --id '<渠道 ID>'
```

告诉用户渠道名称、状态、目标和投递内容。若有快照，把 UTC 时间换算为用户的当地时间。若筛选条件为空，说明渠道包含记录器覆盖的全部资源类型和全部风险等级。

## 新建投递

1. 确定账号或账号组。账号组由组织管理账号或配置审计委派管理员操作。
2. 查看已有投递。如果已有渠道满足要求，告诉用户渠道名称和状态。单账号最多有 5 个渠道，每个账号组最多有 3 个。
3. 用 `DescribeConfigurationRecorders` 查看对应的记录器。单账号看 SingleAccount，账号组看 Organization。选资源类型时，只选记录器已覆盖的类型。如果记录器已停用，告诉用户需要先启用哪个记录器。
4. 确定渠道名称、投递内容、地域和目标。用户已经给出的信息可以直接使用。遇到同名目标，列出地域和所属账号，请用户选一个。

| 用户要投递的内容 | DeliveryContents 取值 | 可选目标 |
| --- | --- | --- |
| 资源的配置变更 | ConfigurationItemChangeNotification | TOS、TLS、SNS |
| 资源不合规事件 | NonCompliantNotification | TOS、TLS、SNS |
| 每日资源快照 | ConfigurationSnapshot | TOS、TLS |
| 每日合规快照 | CompliantSnapshot | TOS、TLS |

可以选多种内容。选了快照，才需要每日投递时间。例如，北京时间每天 00:30 对应 `SnapshotDeliveryTime` 的 `16:30Z`。选了不合规事件，可以指定高、中、低风险。指定资源类型时，用记录器返回的类型名称。

### 准备目标和角色

用户未指定目标时，需要长期保存数据可推荐 TOS，需要检索和分析数据可推荐 TLS，需要告警通知可推荐 SNS。

优先使用用户指定的目标。要新建资源时，先列出资源名称、地域、角色权限及可能产生的费用。用户确认后再创建。每一步都记下返回的资源标识。如果后续步骤失败，先查已经建好的资源，再继续。

| 目标 | 怎样准备 | 角色需要的权限 |
| --- | --- | --- |
| TOS 对象存储 | 用 `volcengine-tosutil` 查找或创建桶。记下桶名和地域。用户选了项目时，调用 IAM 的 `MoveProjectResource`（版本 `2021-08-01`），传入 `TargetProjectName` 和 `ResourceTrn.1`。新建桶时可指定文件前缀。按需选择加密方式。 | 对桶及桶内对象授予 `tos:PutObject`。使用 KMS 时，对选定的密钥环和密钥授予 `kms:GenerateDataKey`。 |
| TLS 日志服务 | 用 `volcengine-tls` 查找日志项目和主题。需要新建时，先建项目，再建主题。记下地域、项目 ID 和主题 ID。控制台新建主题时保留 30 天，使用 5 个分片。 | 对该主题授予 `tls:PutLogs`、`tls:DescribeTopics`。 |
| SNS 简单消息收发服务 | 查主题名和地域。需要新主题时，在目标地域调用 SNS 的 `CreateTopic`，传入 `Name` 和 `Policy`（字符串 `{"Statement":[]}`）。SNS 需先开通。 | 对该主题授予 `sns:Publish*`。 |

如果当前环境缺少对应的 skill，用 `volcengine-find-skills` 按上表中的名称查找。目标准备好后，继续配置投递角色。

如果本机 ve 缺少 SNS 命令，用下面的命令查主题。创建主题时，使用同一地域、版本和地址。把主题名和策略一起放在 JSON 请求体中。

```bash
ve sns ListTopics --version 2023-01-01 --region '<region>' --endpoint open.volcengineapi.com --method GET --force
ve sns CreateTopic --version 2023-01-01 --region '<region>' --endpoint open.volcengineapi.com --method POST --force --body '{"Name":"<topic-name>","Policy":"{\"Statement\":[]}"}'
```

用目标资源所属账号构造目标标识（TRN）。TOS 格式为 `trn:tos:<region>:<account-id>:<bucket>`，TLS 为 `trn:tls:<region>:<account-id>:project/<project-id>/topic/<topic-id>`，SNS 为 `trn:sns:<region>:<account-id>:topic/<topic-name>`。

**给配置审计授权**

1. 选择未使用的角色名和策略名。
2. 用 `ve iam CreateRole` 创建角色。信任策略填 `{"Statement":[{"Effect":"Allow","Action":["sts:AssumeRole"],"Principal":{"Service":["config"]}}]}`。这允许配置审计使用该角色。
3. 用 `ve iam CreatePolicy` 创建权限策略。按上表填写允许的操作（`Action`）和目标资源（`Resource`）。每条权限放进 `Statement`，并将 `Effect` 设为 `Allow`。
4. 用 `ve iam AttachRolePolicy` 将策略绑定到角色。策略类型填 `Custom`。
5. 将角色的 TRN 填入下面的 `DeliveryRoleTrn`。

### 预览并创建

下面的例子只投递高风险不合规事件。将占位符换成已核对的值，再运行命令。

```bash
python3 scripts/compliance.py delivery create --settings '{
  "DeliveryChannelName": "高风险提醒",
  "DeliveryChannelType": "SNS",
  "DeliveryChannelTargetTrn": "trn:sns:<region>:<account-id>:topic/<topic-name>",
  "DeliveryRoleTrn": "trn:iam::<account-id>:role/<role-name>",
  "DeliveryContents": ["NonCompliantNotification"],
  "Condition": "[{\"FilterType\":\"RuleRiskLevel\",\"Values\":[\"High\"]}]"
}'
```

`Condition` 是 JSON 字符串。指定资源类型时加入 `ResourceType` 条件，用 `Values` 列出类型。全部资源、全部风险填 `"[]"`。如果本次已新建桶，且用户指定了文件前缀，在创建或编辑渠道的命令中加 `--new-tos-bucket`，并在 `--settings` 中填写 `TosKeyPrefix`。脚本会核对保存后的前缀。选择已有桶时省略这两个参数。加密方式填 `TosSSEAlgorithm`：空字符串表示不加密，`AES256` 表示 SSE-TOS，`kms` 表示 SSE-KMS。使用 KMS 时，另填密钥标识 `TosSSEKMSKeyId`。

向用户说明账号范围、内容、筛选条件、目标、角色和可能产生的费用。用户确认后，在同一条命令后加 `--confirm`。脚本会查询渠道详情，核对写入的设置。如果请求超时，先查渠道列表。要确认数据已送达，请查看桶中的对象、日志主题中的记录或 SNS 订阅端收到的消息。

## 编辑、暂停和删除

先查看渠道详情。编辑时只传要改的字段。编辑时优先复用现有角色和权限策略。修改投递目标或 KMS 密钥时，先检查现有角色是否有对应权限，权限不足时再创建新的角色和权限策略。删除渠道后，该渠道停止投递。

```bash
python3 scripts/compliance.py delivery update --id '<渠道 ID>' --settings '{"DeliveryContents":["ConfigurationItemChangeNotification"]}'
python3 scripts/compliance.py delivery disable --id '<渠道 ID>'
python3 scripts/compliance.py delivery enable --id '<渠道 ID>'
python3 scripts/compliance.py delivery delete --id '<渠道 ID>'
```

这四条命令都先显示预览。告诉用户将修改或删除哪个渠道。用户确认后再加 `--confirm`。若用户要改渠道名称或类型，请先预览一个新渠道。旧渠道由用户决定是否保留。

如果用户只想修改原桶的投递前缀，说明控制台仅在选择“新建存储桶”并展开“高级配置”时提供文件前缀。
