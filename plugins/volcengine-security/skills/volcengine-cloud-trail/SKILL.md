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

先读取 [账号与操作规则](references/rules.md)，再按下表读取本次操作的参考；上下文中已有的有效内容可直接复用。

## 能力与选路

| 用户目标 | 执行路径 | 必读参考 |
| --- | --- | --- |
| 近 90 天的事件查询、详情或小规模结果导出，且条件组合受支持 | 基础检索；单次查询最多 50 条，基础导出最多 200 条 | [event-query.md](references/event-query.md) |
| 解析产品事件源、事件名或操作语义 | 事件名解析，按需结合官方资料核实 | [event-query.md](references/event-query.md) |
| 复杂条件或 SQL 统计，且已有覆盖目标时段的 TLS 日志 | TLS 高级检索 | [advanced-query.md](references/advanced-query.md) |
| 全部匹配日志或当前页导出不足 | 按筛选条件、结果数量和已有日志覆盖选择基础导出或副本下载，详见“路径选择” | [result-export.md](references/result-export.md)，缺副本需补投时读 [backfill-delivery-tasks.md](references/backfill-delivery-tasks.md) |
| 超过 90 天的事件查询 | 先查已有 TLS／TOS 日志及保留时间，再选择检索或下载；见“已有副本发现” | [result-export.md](references/result-export.md#已有副本发现) |
| 开通、调整或停止审计日志投递，排查投递异常 | 跟踪与投递管理，包含目标资源准备和日志到达验证 | [event-trail-management.md](references/event-trail-management.md) |
| 保存指定历史时段日志或管理补投任务 | 历史补投管理 | [backfill-delivery-tasks.md](references/backfill-delivery-tasks.md) |
| 查找、使用或管理检索模板 | 模板管理；仅管理模板不检查历史数据覆盖 | [search-templates.md](references/search-templates.md) |

完整导出优先级高于原查询路径，但“全部”不等于“大批量”：基础路径可以证明完整时，不为切换工具而发现副本或准备补投。仅要求保存当前页或当前已取得结果时，按用户指定范围处理，不扩大为全量任务。

## 工具与前置条件

- CloudTrail 业务接口仅通过 `scripts/cloud_trail.py` 的 allowlist 调用 `ve cloudtrail`，API 版本为 `2021-09-01`；STS 身份确认及公开文档查证不受此清单限制。
- CloudTrail 调用前检查 `ve --version`：稳定版至少 1.2.0。版本缺失、不可识别或不满足时停止业务调用，按 `volcengine-cli` 准备工具后恢复任务。版本通过不代表接口注册或鉴权通过。
- 脚本需要 `python3`。`--help` 不要求安装 ve；直接 TLS 操作按对应工具的版本要求执行。
- ve 安装、鉴权与配置按 `volcengine-cli`；TLS 操作按 `volcengine-tls`；TOS 操作按 `volcengine-tosutil`。具体命令、参数与工具要求由对应技能维护。
- 身份选择、账号绑定与登录恢复统一按 rules.md；需要时读取相关工具技能。遵循当前工具要求携带 Agent 调用来源标识，不记录或回显密钥和令牌。
- 标准输出保留结构化结果，诊断进入标准错误；成功 API envelope 保留在 `ApiResponse`。技术证据的保存与面向用户展示分开处理。

## 写操作边界

写操作先预览并核对授权。停止投递必须单独列出目标和影响，取得针对该动作的明确授权；不得从导出、补投或清理授权中推定。相同动作已明确授权时不重复询问。组织级操作须明确组织范围及影响。

## 时间与条件

- 基础检索限近 90 天；TLS 实际可查范围取决于投递覆盖和保留情况；补投窗口见对应参考。
- 续查与导出沿用已固定的账号、时间范围和筛选条件。时间格式、时区解析、单位转换与边界处理见对应能力参考。
- 根据真实条件组合和预期结果选路，不先试基础检索再丢弃不受支持的条件。基础检索空结果先核对范围，不能只因空结果自动改走 TLS。
- 产品、事件源、事件名和读写语义不确定时先核实。“完整原始事件”指字段完整，“全部事件”指结果集合完整，分别处理。

## 调用入口

在本技能目录使用 `python3 scripts/cloud_trail.py --help` 查看入口；按需查看对应子命令帮助，业务示例见能力参考。

仅实际调用 CloudTrail API 的业务路径须带已确认账号的全局 `--expected-account-id`，必要时带对应已授权身份选择。直接 TLS／TOS 调用独立核实身份。本地帮助与元数据解析不要求账号校验。

默认输出 JSON；需要其他格式时，全局 `--format` 放在业务分组之前。
