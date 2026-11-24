# usage stats

> **前置条件：** 先阅读 [`../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md) 了解认证、全局参数和安全规则。

> **⚠️ 数据时效：** `usage stats` 数据来自上游 BFF 聚合管道，**有 5–30 分钟延迟**，定位为「日级 / 聚合分析」。**不适合**实时预算监控、限流、实时告警。这类实时控制场景请直接读推理命令返回的 per-request `.usage` 字段（[arkcli-chat](../../arkcli-chat/GUIDE.md) / [arkcli-gen](../../arkcli-gen/GUIDE.md)），零延迟、按调用计量。

查询指定时间范围内的 ARK 推理用量，支持按接入点、模型、API Key 等多维度过滤与分组。

**先核对交付单位：** 用户问已发生调用的实际花费、人民币或用量折算费用时，先转 [Billing](../../arkcli-billing/GUIDE.md) 查实际应付；本页只提供数量统计。目录报价转 [Pricing](../../arkcli-pricing/GUIDE.md)；只有用户明确要按单价估算/预测时，才组合数量与价格并标为估算。个人数量查询失败不允许换成账号全量后乘单价来补一个“我的费用”。

**语音模型不支持**：TTS / ASR / 配音 / 播客 / 音色 / 实时语音交互，或模型名命中 `doubao-seed-tts-*`、`doubao-seed-asr-*`、`seedasr-*` 时，不要用 `usage stats --model` 查询。广场可搜不代表 usage 管道有可查用量；应回到 `arkcli models search <keyword>` 的可发现说明。

## 命令

```bash
# 查询当日用量（--start 必填，缺失会报 required flag(s) "start" not set；查今天就把 start 填成今天）
arkcli usage stats --start <YYYY-MM-DD>

# 查询本月按天用量
arkcli usage stats --start 2025-09-01 --end 2025-09-30

# 按小时粒度查询
arkcli usage stats --start 2025-09-17 --end 2025-09-19 --interval Hour --endpoint ep-20xxxx-xxx

# 查询指定模型的用量
arkcli usage stats --start 2025-09-01 --end 2025-09-30 --model doubao-pro-4k

# 按模型分组查看所有模型用量
arkcli usage stats --start 2025-09-01 --end 2025-09-30 --by model

# 按接入点分组
arkcli usage stats --start 2025-09-01 --end 2025-09-30 --by endpoint

# 同时按模型和接入点分组
arkcli usage stats --start 2025-09-01 --end 2025-09-30 --by model,endpoint

# 按 API Key 过滤
arkcli usage stats --start 2025-09-01 --end 2025-09-30 --apikey ak-xxxxxxxx

# 使用绑定目标 Project 的 profile 查询
arkcli --profile my-project-profile usage stats --start 2025-09-01 --end 2025-09-30

# 显示按计费窗口拆分的明细（每条记录附带所属计费窗口）
arkcli usage stats --start 2025-09-01 --end 2025-09-30 --show-window-detail

# ─── “我的用量” 入口（AI Agent 高频调用） ───
# 默认走 endpoint 维度：列出我创建的全部 Endpoint，合并查它们的用量
arkcli usage stats --start <YYYY-MM-DD> --mine

# 显式 endpoint 维度（语义同 --mine）
arkcli usage stats --start <YYYY-MM-DD> --mine --mine-by=endpoint

# apikey 维度：筛选本人 active APIKey 的非空掩码后缀，分别查后合并
arkcli usage stats --start 2026-05-01 --end 2026-05-08 --mine --mine-by=apikey

# 按 APIKey 后缀模糊匹配（与 console "AuthToken ValueLike" 对齐）
arkcli usage stats --start <YYYY-MM-DD> --apikey-suffix d9bcce38dab0
```

## 参数

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `--start` | **是** | string | 开始日期，YYYY-MM-DD 格式 |
| `--end` | 否 | string | 结束日期，YYYY-MM-DD 格式（与开始日期间隔不超过 31 天），默认当日 |
| `--interval` | 否 | string | 查询粒度：`Day`（默认）或 `Hour` |
| `--endpoint` | 否 | string | 按接入点 ID 过滤 |
| `--model` | 否 | string | 按模型名称过滤，输出中附加 `ModelName`、`ModelUnitID` 列 |
| `--apikey` | 否 | string | 按 API Key 完整值过滤（Values 精确匹配，兼容旧用法） |
| `--apikey-suffix` | 否 | string | 按 API Key 后缀过滤（ValueLike 模糊匹配，与 console 行为一致；推荐传末 12 位） |
| `--mine` | 否 | bool | 限定为当前登录身份名下的资源；与 `--mine-by` 配合使用。 |
| `--mine-by` | 否 | string | `--mine` 的维度：`endpoint`（默认）= 我创建的所有 Endpoint；`apikey` = 本人 active APIKey 中带可用掩码后缀的项。 |
| `--by` | 否 | string | 追加分组维度，逗号分隔。可选值：`model`、`endpoint`、`apikey` |
| `--show-window-detail` | 否 | bool | 输出按计费窗口拆分的明细。**与 `SplitByWindows` 互斥**（后者目前仅通过 `arkcli api GetInferenceUsage` raw 调用使用） |

### --mine 行为细节

**火山：**
- **要求 SSO 子用户登录**：root 账号或 AK/SK 登录会拒绝执行（会引导你重新 `arkcli auth login volc-sso`）
- **互斥规则**：`--mine --mine-by=endpoint` 与 `--endpoint` 互斥；`--mine --mine-by=apikey` 与 `--apikey` / `--apikey-suffix` 互斥
- **`--mine-by=endpoint`**：通过 `sys:ark:createdBy` Tag 拉出我创建的全部 Endpoint，单次请求合并查（强制 `--page-all`）
  - 成功返回空 `records` 且 `data_count=0`，或明确没有本人 Endpoint 时，保留其他条件改查 `arkcli usage stats <日期参数> --mine --mine-by=apikey` 一次；这不证明本人没有其他调用。
  - 保留 `--mine`；范围处理按下表执行，错误提示不能代替用户确认。
- **`--mine-by=apikey`**：列出本人 APIKey，再筛出 Active 且掩码后缀非空的项，**为每个 key 串行发一次请求**（ValueLike 是单值），客户端合并 records；`totals` 字段是合并后的合计

### 空结果与资源筛选失败的处理

先保留原命令的 exit code、stderr 和完整 JSON，按下表判断；不要把解析失败或资源筛选失败写成“用量为 0”。

| 实际结果 | 能说明什么 | 下一步 |
| --- | --- | --- |
| 命令成功，`records` 为空且 `data_count=0` | 该次范围内未返回明细 | 本人 endpoint 维度可按相同日期、模型、分组、粒度及 Profile/Project 改查本人 apikey 维度一次 |
| `no endpoints found ... try --mine-by=apikey or omit --mine` | 当前本人 Endpoint 筛选集合为空，尚未取得该范围的用量明细 | 只可尝试 `--mine --mine-by=apikey`；错误里的 `omit --mine` 是另一个命令范围，不代表用户同意扩大查询 |
| `no active API keys found under your account` | 本次 `ListPersonalKeys` 结果经 Active 和非空 Key 后缀筛选后集合为空 | 报告“未取得本人范围用量”，保留未知项；不能据此说整个账号无 Key、没有调用或费用为零 |
| `records` 有行但 `totals` 为 0 | 返回了记录；指标可能为真实零或解析有误 | 对照记录、字段及数值类型，不按空结果切换范围 |
| 鉴权、权限、网络、解析等其他错误 | 查询失败，未得到可信结果 | 按实际错误处理；不删除本人或资源过滤来绕过失败 |

第二层成功为空或筛选失败时，分别说明已查范围与缺口。只有用户另行明确要求查询整个账号，才移除 `--mine` / `--mine-by`，保持其余条件并标“账号全量（可能包含其他用户）”。用户拒绝、未回复或当前任务无法交互时，停在原范围；不能把“我会查询全量”这样的单方面告知当成确认。

Usage 的本人 Key 过滤读取 Active 项的 `Key` 掩码后缀；Billing 的同名维度读取 Active 项的非空 `SID`，两者的筛选依据不同，集合可能不同。Usage 筛选失败不能代替 Billing 的实际结果。用户确实问费用时，按 Billing 契约直接查询该金额范围；不要为了拿后缀去获取明文 Key、创建/轮换 Key 或修改 Profile。

近期空结果可核对真实调用日/时区、聚合延迟、平台或套餐口径、身份、Project 和 Key 掩码归属。移除分组可用于检查 totals，但不顺便删身份或资源过滤；归属核对见 [Key 查询](../../arkcli-auth/references/api-key-query.md)。展示已核对项与未知项，不因空结果自动切账号、登录、换 Key 或查另一个计费桶。

### --by 说明

`--by` 用于在不过滤的情况下，将指定维度作为输出列返回并按维度分组：

| 值 | 追加的输出列 |
|----|------------|
| `model` | `ModelName`、`ModelUnitID` |
| `endpoint` | `ModelEndpoint` |
| `apikey` | `AuthToken` |

> `--model` 与 `--by model` 的区别：前者过滤出指定模型的数据，后者返回所有模型并按模型分组。两者都会在输出中附加 `ModelName` 和 `ModelUnitID` 列。

## 返回值

JSON 格式：

```json
{
  "fields": [
    { "name": "AccountID", "type": "BIGINT" },
    { "name": "Day", "type": "DATE" },
    { "name": "InputTokens", "type": "BIGINT" },
    { "name": "CacheTokensHit", "type": "BIGINT" },
    { "name": "OutputTokens", "type": "BIGINT" },
    { "name": "TotalTokens", "type": "BIGINT" },
    { "name": "ReqCnt", "type": "BIGINT" },
    { "name": "ImageCount", "type": "BIGINT" }
  ],
  "records": [{
    "Day": "2025-09-01",
    "ModelName": "<实际模型名>",
    "ModelEndpoint": "<实际 Endpoint ID>",
    "AuthToken": "****example",
    "ProjectName": "<实际 Project>",
    "BillingStatus": "<实际结算状态>",
    "InputTokens": "382",
    "OutputTokens": "5317",
    "TotalTokens": "5699",
    "ReqCnt": "11",
    "CacheTokensHit": "0",
    "ImageCount": "4"
  }],
  "totals": {
    "InputTokens":  "382",
    "OutputTokens": "5317",
    "TotalTokens":  "5699",
    "ReqCnt":       "11",
    "CacheTokensHit": "0",
    "ImageCount":   "4"
  },
  "data_count": 1
}
```

> `totals` 是把 records 中所有 metric 列（`InputTokens` / `OutputTokens` / `TotalTokens` / `ReqCnt` / `CacheTokensHit` / `ImageCount`）跨行加和的结果。维度列（`AccountID` / `Day` / `ModelEndpoint` / `AuthToken` / `ProjectName` / `BillingStatus`）**不会**被加和。AI Agent 答"我今天用了多少 token"直接读 `totals.TotalTokens`；要按维度拆走 `records`。

维度列出现条件：

| 列名 | 出现条件 |
|------|---------|
| `Day` / `Hour` | 对应查询粒度；以本次 `fields` 和 `records` 为准 |
| `ModelEndpoint` | 使用了 `--endpoint`、`--by endpoint` 或 endpoint 维度的 `--mine` |
| `ModelName` | 使用了 `--model` 或 `--by model` |
| `ModelUnitID` | 使用了 `--model` 或 `--by model` |
| `AuthToken` | Key 过滤/分组或 apikey 维度的 `--mine`；掩码不是完整凭证 |

上面是带维度的结构示例，不保证每次返回所有列；以 `fields` 声明及实际键为准。指标可能是数字字符串，聚合前验证数值类型，不做字符串拼接；缺失字段不是数值 0。不要把 `AuthToken` 写成旧文案的 `ApiKey`，也不要把 PascalCase 改成 snake_case。动态 JSON 参数使用 [Raw API 的安全拼装方式](../../arkcli-api-explorer/references/arkcli-api.md)，不手写转义拼用户输入。

## 常见错误

| 错误 | 原因 | 处理方式 |
|------|------|---------|
| `not logged in` | 未认证 | 运行 `arkcli auth login volc-sso` 重新建立 Volc 身份 |
| `AuthFailure` / 401 | AK/SK 或 SSO token 无效 | 重新登录 |
| 时间范围超过 31 天 | API 限制 | 拆分为多次查询 |
| 返回空 records | 当前范围未返回匹配数据；不等于权限正常或用量必为零 | 核对时间、身份和过滤条件；保留用户指定范围，扩大范围前先确认，不自动去掉过滤 |

## 注意事项

- **`--start` 必填**：缺失直接报 `required flag(s) "start" not set`，CLI **不会**默认今天；用户未给任何日期时，默认 `--start`=今天、`--end` 缺省同今天再跑，不要裸跑省略 `--start`
- **数据有 5–30 分钟延迟**：上游聚合管道行为，arkcli 仅透传，不可缩短；做实时预算 / 限流 / 告警请改走 per-request `.usage`，不要轮询本接口
- **语音模型不在本命令支持范围**：不要为 TTS / ASR / 语音交互构造 `--model`、`--by model` 或 API Key fallback；当前只说明 arkcli 不支持语音模型用量查询
- arkcli 自动过滤掉 `free_for_coding_plan` 的用量行，始终保留有 `ModelUnitID` 的行
- `--interval Hour` 时返回的 `Hour` 字段为 STRING 类型
- `stats` 的开始/结束跨度须严格小于 31 天；更长请求按原时间范围分片并核对边界，不能默默只查最近 30 天

## 参考

- [arkcli-usage](../GUIDE.md) -- usage skill 概览
- [arkcli-chat](../../arkcli-chat/GUIDE.md) -- 实时 / per-request 用量：`+chat` 返回里的 `.usage` 字段
- [arkcli-gen](../../arkcli-gen/GUIDE.md) -- 实时 / per-request 用量：`+gen` 图片/视频任务返回里的 `.usage` 字段
- [arkcli-shared](../../arkcli-shared/GUIDE.md) -- 认证和全局参数
