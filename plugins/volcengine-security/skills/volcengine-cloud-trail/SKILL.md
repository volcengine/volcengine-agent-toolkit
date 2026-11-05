---
name: volcengine-cloud-trail
description: >-
  当用户需要查询火山引擎 CloudTrail 审计日志、调查登录或资源操作、分析或导出已投递到 TLS 的审计日志、导出已投递到 TOS 的审计日志、管理检索模板，或开通、调整、排查审计日志投递及管理历史补投任务时使用。
  在火山引擎语境下，出现“操作审计、审计日志、日志检索、CloudTrail、cloud_trail、trail、跟踪、审计日志投递、历史补投、backfill”等词时触发。
license: MIT
version: 1.1.0
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

帮助用户完成审计日志查询、溯源、分析、导出，以及检索模板、跟踪和历史补投管理。

## 执行入口

先读取 [账号与操作规则](references/rules.md)，再按下表读取本次操作的参考；已经读过且仍适用的说明不必重复读取。

## 能力与使用方式

| 用户需求 | 使用方式 | 必读参考 |
| --- | --- | --- |
| 近 90 天的事件查询、详情或小规模结果导出，且条件组合受支持 | 基础检索；单次查询最多 50 条，基础导出最多 200 条 | [event-query.md](references/event-query.md) |
| 确定产品事件源、事件名或操作含义 | 事件名解析，按需结合官方资料核实 | [event-query.md](references/event-query.md) |
| 复杂条件或 SQL 统计，且已有覆盖所查时段的 TLS 日志 | TLS 高级检索 | [advanced-query.md](references/advanced-query.md) |
| 全部匹配日志或当前页导出不足 | 按筛选条件、结果数量和已有日志覆盖选择基础导出或下载已投递的日志，详见“路径选择” | [result-export.md](references/result-export.md)，缺少已投递的日志需补投时读 [backfill-delivery-tasks.md](references/backfill-delivery-tasks.md) |
| 超过 90 天的事件查询 | 先查已有 TLS／TOS 日志及保留时间，再选择检索或下载；见“查找已投递的日志” | [result-export.md](references/result-export.md#查找已投递的日志) |
| 开通、调整或停止审计日志投递，排查投递异常 | 跟踪与投递管理，包含 TOS 存储桶或 TLS 日志主题的准备和日志到达验证 | [event-trail-management.md](references/event-trail-management.md) |
| 保存指定历史时段日志或管理补投任务 | 历史补投管理 | [backfill-delivery-tasks.md](references/backfill-delivery-tasks.md) |
| 查找、使用或管理检索模板 | 模板管理；仅管理模板时，无需检查历史日志是否齐全 | [search-templates.md](references/search-templates.md) |

用户要导出全部日志时，如果原查询方式无法导全，就改用其他导出方式。基础导出能满足要求时，直接使用，不必查找 TLS／TOS 日志或准备补投。用户只要当前页或已查到的结果时，就保存这些结果，不扩大查询范围。

## 工具与前置条件

- CloudTrail 业务接口仅通过 `scripts/cloud_trail.py` 的 allowlist 调用 `ve cloudtrail`，API 版本为 `2021-09-01`；STS 身份确认及公开文档查证不受此清单限制。
- CloudTrail 调用前检查 `ve --version`：稳定版至少 1.2.0。版本缺失、不可识别或不满足时停止业务调用，按 `volcengine-cli` 准备工具后恢复任务。版本通过不代表接口注册或鉴权通过。
- 脚本需要 `python3`。`--help` 不要求安装 ve；直接 TLS 操作按对应工具的版本要求执行。
- ve 安装、鉴权与配置按 `volcengine-cli`；TLS 操作按 `volcengine-tls`；TOS 操作按 `volcengine-tosutil`。具体命令、参数与工具要求由对应技能维护。
- 身份选择、账号绑定与登录恢复统一按 rules.md；需要时读取相关工具技能。遵循当前工具要求携带 Agent 调用来源标识，不记录或回显密钥和令牌。
- 标准输出保留结构化结果，诊断进入标准错误；接口成功时的完整响应保留在 `ApiResponse`。排查用的详细记录按需保存，不必全部展示给用户。

## 写操作边界

写操作先预览并核对授权。停止投递必须单独列出要停止的跟踪和影响，取得针对该动作的明确授权；不得从导出、补投或清理授权中推定。相同动作已明确授权时不重复询问。组织级操作须明确组织范围及影响。

## 时间与条件

- 基础检索限近 90 天；TLS 能查到哪些日志，取决于实际投递和保留的日志；可补投的时间范围见对应参考。
- 续查与导出沿用已固定的账号、时间范围和筛选条件。时间格式、时区解析、单位转换与边界处理见对应能力参考。
- 根据真实条件组合和预期结果选择查询方式，不先试基础检索再丢弃不受支持的条件。基础检索空结果先核对范围，不能只因空结果自动改走 TLS。
- 不确定产品、事件源、事件名，或操作属于读取还是写入时，先核实。用户要“完整原始事件”时，提供事件的全部字段；要“全部事件”时，获取全部匹配记录。

## 调用入口

在本技能目录使用 `python3 scripts/cloud_trail.py --help` 查看可用命令；按需查看子命令帮助，示例见对应参考文档。

实际调用 CloudTrail API 时，须用全局参数 `--expected-account-id` 指定已确认的账号，必要时指定对应的已授权身份。直接 TLS／TOS 调用独立核实身份。本地帮助与元数据解析不要求账号校验。

默认输出 JSON；需要其他格式时，全局 `--format` 放在业务分组之前。
