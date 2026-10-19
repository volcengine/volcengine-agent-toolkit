# volcengine-agent-toolkit

---
[![Volcengine SKILL & CLI Survey](img_new.png)](https://www.volcengine.com/survey/q/v2/7662656599489085475/q36U8r81/5ffc/channel=doc)

为提高您对火山引擎 skill 的使用体验，邀您参加[有奖调研](https://www.volcengine.com/survey/q/v2/7662656599489085475/q36U8r81/5ffc/channel=doc)。

---

[English](./README_en.md) | **简体中文**

火山引擎团队维护的 skill marketplace，面向 Claude Code / Codex / OpenCode / Cursor / Gemini CLI
等 AI coding agent。仓库默认只安装核心插件；其他技能按火山引擎产品域拆分为可选插件，由
`volcengine-find-skills` 统一发现和安装。

**[快速安装 →](#默认安装)**

`volcengine-cli` 优先通过 `ve tosutil` 和 `ve arkcli` 使用产品 CLI，要求 **`ve >= 1.1.9`**
（稳定版 `1.1.9` 起）；使用前执行 `ve version`，版本不满足时先升级。TOS 操作由 finder
查找并安装 `volcengine-tosutil`；Ark 操作引导下载[官方 skills](https://github.com/volcengine/ark-cli/tree/main/skills)。
具体操作遵循对应 skill；通过 `ve` 转发产品命令，并按下述规则传递调用方标识。

Agent 执行 `ve` 时必须注入 `VE_CALLER_TYPE=ai_agent`、`VE_CALLER_NAME=<agent-id>` 和
`VE_SKILL_NAME=<current-volcengine-skill>`，用于标识 Agent 类型及当前执行操作的 skill。
仅 `VE_CALLER_TYPE` 固定为 `ai_agent`；另外两项由 Agent 在每次调用时根据实际运行环境及当前 skill 的名称确定，不能固定为 `codex` 或 `volcengine-cli`。无需用户手动配置；详见 [调用方标识规则](./skills/core/volcengine-cli/SKILL.md#agent-caller-metadata-mandatory)。
通过 `ve arkcli ...` 调用时，由 `ve` 转换调用方标识，Agent 无需重复添加 `ARKCLI_*` 调用标识，也不直接复制独立 Ark CLI 示例中的通知设置前缀。

## Plugins

<!-- BEGIN GENERATED: plugin-catalog -->
| Plugin | 产品分类 | Skills | 默认安装 |
| --- | --- | --- | --- |
| `volcengine-core` | 核心 | `volcengine-cli`、`volcengine-troubleshooting`、`volcengine-knowledge-search`、`volcengine-find-skills`、`volcengine-feedback` | 是 |
| `volcengine-storage` | 存储 | `volcengine-tosutil`、`volcengine-tls`、`volcengine-tls-logcollector` | 否 |
| `volcengine-database` | 数据库 | `volcengine-db-supabase` | 否 |
| `volcengine-containers-middleware` | 容器与中间件 | `volcengine-vefaas` | 否 |
| `volcengine-security` | 安全 | `volcengine-compliance`、`volcengine-cloud-trail` | 否 |
| `volcengine-identity-access-control` | 身份与访问控制 | `volcengine-landing-zone` | 否 |
| `volcengine-service-support` | 服务支持 | `volcengine-sale`、`volcengine-prepare`、`volcengine-deploy`、`volcengine-iac`、`volcengine-api`、`volcengine-sdk-generator` | 否 |
<!-- END GENERATED: plugin-catalog -->

核心插件的 marketplace 策略为 `INSTALLED_BY_DEFAULT`，其他插件均为 `AVAILABLE`。
`skills/core/` 存放核心 skill；`skills/specialized/<domain>/<skill>/` 按产品分类提供可选 skill 副本。
分类名取自所属 plugin 去掉 `volcengine-` 前缀，例如 `volcengine-database` 对应
`skills/specialized/database/`。可选 skill 在 plugin 中维护源码，副本由同步脚本生成。

## Skills

<!-- BEGIN GENERATED: skill-catalog -->
| Skill | Plugin | 场景 |
| --- | --- | --- |
| [`volcengine-cli`](./skills/core/volcengine-cli/SKILL.md) | `volcengine-core` | 使用 ve 管理火山引擎资源；引导获取 TOS、Ark 技能，并通过 ve tosutil、ve arkcli 执行。 |
| [`volcengine-troubleshooting`](./skills/core/volcengine-troubleshooting/SKILL.md) | `volcengine-core` | 诊断火山引擎错误、资源状态、配额、指标与 OpenAPI 故障。 |
| [`volcengine-knowledge-search`](./skills/core/volcengine-knowledge-search/SKILL.md) | `volcengine-core` | 使用 ve docs search/fetch 检索并获取火山引擎官方文档全文，无需登录。 |
| [`volcengine-find-skills`](./skills/core/volcengine-find-skills/SKILL.md) | `volcengine-core` | 列出全部火山引擎技能，供 Agent 选择并安装当前缺失的能力。 |
| [`volcengine-feedback`](./skills/core/volcengine-feedback/SKILL.md) | `volcengine-core` | 整理并提交脱敏的 GitHub 使用反馈，涵盖问题、能力需求、实际场景和成功实践，始终不阻塞主任务。 |
| [`volcengine-tosutil`](./skills/specialized/storage/volcengine-tosutil/SKILL.md) | `volcengine-storage` | 使用 tosutil 命令行工具管理 TOS 桶和对象。 |
| [`volcengine-tls`](./skills/specialized/storage/volcengine-tls/SKILL.md) | `volcengine-storage` | 使用 volclog 操作火山引擎日志服务 TLS：按契约发现/描述/执行，覆盖日志检索、分析、导入、导出与错误恢复。 |
| [`volcengine-tls-logcollector`](./skills/specialized/storage/volcengine-tls-logcollector/SKILL.md) | `volcengine-storage` | 通过 volclog 设计、校验、部署并排查 Linux 主机或 Kubernetes 上的 TLS LogCollector 日志采集。 |
| [`volcengine-db-supabase`](./skills/specialized/database/volcengine-db-supabase/SKILL.md) | `volcengine-database` | 管理火山引擎 AI 原生 BaaS Supabase 工作区、SQL、Auth、Realtime 与 Edge Functions。 |
| [`volcengine-vefaas`](./skills/specialized/containers-middleware/volcengine-vefaas/SKILL.md) | `volcengine-containers-middleware` | 在火山引擎 veFaaS 上部署和管理 Serverless 应用。 |
| [`volcengine-compliance`](./skills/specialized/security/volcengine-compliance/SKILL.md) | `volcengine-security` | 推荐合规基线、汇总合规态势并编写自定义 Rego 合规规则。 |
| [`volcengine-cloud-trail`](./skills/specialized/security/volcengine-cloud-trail/SKILL.md) | `volcengine-security` | 查询操作审计日志，并管理跟踪和历史补投任务。 |
| [`volcengine-landing-zone`](./skills/specialized/identity-access-control/volcengine-landing-zone/SKILL.md) | `volcengine-identity-access-control` | 咨询、搭建和管理火山引擎 Landing Zone 与账号基线，并支持部署方案或蓝图。 |
| [`volcengine-sale`](./skills/specialized/service-support/volcengine-sale/SKILL.md) | `volcengine-service-support` | 编排火山商品交易意图：识别开通购买、询价预估与退订三类动作并分流执行。 |
| [`volcengine-prepare`](./skills/specialized/service-support/volcengine-prepare/SKILL.md) | `volcengine-service-support` | 分析代码仓库并推荐 ECS、VKE 或 veFaaS 部署形态。 |
| [`volcengine-deploy`](./skills/specialized/service-support/volcengine-deploy/SKILL.md) | `volcengine-service-support` | 将本地目录或 Git 仓库部署到火山引擎。 |
| [`volcengine-iac`](./skills/specialized/service-support/volcengine-iac/SKILL.md) | `volcengine-service-support` | 使用 Terraform 和基础设施即代码管理火山引擎资源。 |
| [`volcengine-api`](./skills/specialized/service-support/volcengine-api/SKILL.md) | `volcengine-service-support` | 查询火山引擎 API 规格、参数、错误码和返回结构。 |
| [`volcengine-sdk-generator`](./skills/specialized/service-support/volcengine-sdk-generator/SKILL.md) | `volcengine-service-support` | 生成准确、可运行的多语言火山引擎 SDK 示例。 |
<!-- END GENERATED: skill-catalog -->

## 默认安装

### 按需发现与安装

`volcengine-find-skills` 内置唯一 catalog，覆盖全部 core skill 和所有可选 plugin skill：

1. 用户主动查找 skill，或者执行火山引擎任务时当前已加载/已安装 skill 无法覆盖所需产品、工具或流程，都会触发 finder。
2. `list` 一次列出完整 catalog，由 Agent 根据名称、产品域、摘要和关键词选择最小必要 skill 集合。
3. 安装前必须解析为精确的 skill 名称；plugin 只用于分类，不能作为安装目标。
4. finder 对所有宿主都通过 skills CLI 直接安装选中的 skill，不安装整个 plugin。
5. 安装命令成功后再次读取宿主安装清单，只有目标全部可见才返回 `verified: true`。
6. 新增 skill 安装后，若宿主不能动态加载，则新开对话并携带原任务和已完成上下文继续执行。

### Codex

添加 marketplace 后只安装核心插件：

```bash
codex plugin marketplace add volcengine/volcengine-agent-toolkit
codex plugin add volcengine-core@volcengine-skills
codex plugin list
```

上述 plugin 命令只用于首次加载核心 finder。finder 后续发现缺失能力时，只直接安装选中的 skill。

在新对话中直接描述需求，例如“查找对象存储相关 skill”或“安装 `volcengine-tosutil`”。finder 会读取
完整 catalog、自主选择并直接安装合适的 skill，不会安装整个产品域 plugin。若当前对话不能动态加载新增 skill，需新开对话继续。

在源码仓库内也可以直接验证发现结果：

```bash
python3 plugins/volcengine-core/skills/volcengine-find-skills/scripts/find_skills.py list
python3 plugins/volcengine-core/skills/volcengine-find-skills/scripts/find_skills.py install volcengine-tosutil --agent codex
python3 plugins/volcengine-core/skills/volcengine-find-skills/scripts/find_skills.py status --agent codex
```

### 通用 skills CLI

下面的命令只安装当前核心 skill，不会默认安装可选产品域 skill：

```bash
npx skills add volcengine/volcengine-agent-toolkit \
  --global --yes --copy --full-depth \
  --skill volcengine-cli volcengine-troubleshooting volcengine-knowledge-search volcengine-find-skills volcengine-feedback
```

后续可由 finder 调用 `npx skills add --skill` 精确安装单个或多个 skill。如需交互选择仓库内的 skill：

```bash
npx skills add volcengine/volcengine-agent-toolkit --full-depth
```

### Claude Code

```text
/plugin marketplace add volcengine/volcengine-agent-toolkit
/plugin install volcengine-core@volcengine-skills
/reload-plugins
/volcengine-core:volcengine-find-skills
```

### Gemini CLI

```bash
gemini skills install https://github.com/volcengine/volcengine-agent-toolkit --path skills/core/volcengine-cli
gemini skills install https://github.com/volcengine/volcengine-agent-toolkit --path skills/core/volcengine-troubleshooting
gemini skills install https://github.com/volcengine/volcengine-agent-toolkit --path skills/core/volcengine-knowledge-search
gemini skills install https://github.com/volcengine/volcengine-agent-toolkit --path skills/core/volcengine-find-skills
gemini skills install https://github.com/volcengine/volcengine-agent-toolkit --path skills/core/volcengine-feedback
gemini skills list
```

首次安装时逐项确认安全提示。安装后重新启动 Gemini CLI；可直接描述火山引擎任务，也可要求它使用 `volcengine-find-skills`。

### OpenCode

按 [OpenCode 安装说明](./.opencode/INSTALL.md) 挂载核心插件的 `skills/` 目录。

### Cursor

```text
/add-plugin volcengine-core@https://github.com/volcengine/volcengine-agent-toolkit
/volcengine-find-skills
```

在 Cursor 2.5 或更高版本的 Agent 对话中输入完整命令；`/add-plugin` 可能不会出现在自动补全中。

## 反馈与场景分享

我们希望了解你通过 Agent 使用火山引擎时的实际收获、遇到的困难和后续期待。欢迎分享当前 skill 的使用问题、能力需求、待支持场景及成功实践，帮助用户与开发者共同改进 Agent 管理云服务的体验。描述任务目标、实际结果或期望改进即可，不必先定位根因或准备完整报告。

可直接说明“用 volcengine-feedback 帮我反馈：……”。默认核心 skill [`volcengine-feedback`](./skills/core/volcengine-feedback/SKILL.md) 会根据已有上下文整理简短的脱敏草稿，供你审阅后选择发送、修改或保留草稿。无需先准备日志、版本或完整报告；发布成功后返回 issue 链接，继续原任务。

也可以直接填写 [Feedback issue 表单](https://github.com/volcengine/volcengine-agent-toolkit/issues/new?template=feedback.yml)：填写标题与反馈内容即可，分类和补充信息均为选填。旧版本或未加载该 skill 的环境同样可用。反馈始终自愿，不会阻塞主任务；Agent 在同一对话中的主动邀请最多一次，不等待回复，也不为反馈安装工具或重启对话。

GitHub issue 是公开内容。发布前请检查正文与附件，移除凭证、账号信息、真实资源 ID、内部地址和客户数据，不公开敏感漏洞细节，并遵守 [反馈与社区规则](./.github/FEEDBACK_GUIDELINES.md) 及其中的 GitHub 社区规范。欢迎客观描述使用中遇到的问题、影响和改进建议；包含人身攻击、骚扰、歧视等违规内容的 issue 会被维护者直接关闭。需要私密排障或紧急恢复时，请使用火山引擎官方支持渠道。

## 目录结构

```text
volcengine-agent-toolkit/
├── skills/
│   ├── core/                         # CLI 默认安装的核心 skill 源码
│   └── specialized/
│       └── <domain>/
│           └── volcengine-<name>/    # 对应可选 plugin 的生成副本
├── plugins/
│   ├── volcengine-core/              # 默认核心 plugin，复制 skills/core 并保留 hooks
│   └── volcengine-<domain>/          # 可选 plugin，也是其 skill 的唯一源码
└── .agents/plugins/marketplace.json
```

`skills/core/` 是核心 skill 的规范源码；可选 skill 直接在所属 plugin 中维护。
同步脚本复制核心与专项 skill，并生成 manifest、marketplace，以及 README / Gemini / Cursor 中的技能清单。
生成副本和 `BEGIN GENERATED` / `END GENERATED` 标记间的清单由脚本维护。
CLI 默认发布包仍只包含核心 skill；需要专项能力时按名称安装对应 skill。
修改或新增 skill 后运行：

```bash
python3 scripts/sync_plugins.py
python3 scripts/validate_codex_plugin_layout.py
python3 -m unittest discover -s tests -v
```

## License

MIT，见 [LICENSE](./LICENSE)。

## 项目 Rules

除 skill 外，推荐在客户项目中加入火山引擎规则文件 [`rules/volcengine-agent-rules.md`](rules/volcengine-agent-rules.md)，让 Agent 在每次会话中优先使用 skill、按证据确定目标、核实 API 细节。安装插件不会自动启用规则：把内容复制到 `CLAUDE.md`、`AGENTS.md`、`GEMINI.md` 或 `.cursor/rules/volcengine.mdc`，详见 [rules/README.md](rules/README.md)。
