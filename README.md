# volcengine-skills

---
[![Volcengine SKILL & CLI Survey](img_new.png)](https://www.volcengine.com/survey/q/v2/7662656599489085475/q36U8r81/5ffc/channel=doc)

为提高您对火山引擎 skill 的使用体验，邀您参加[有奖调研](https://www.volcengine.com/survey/q/v2/7662656599489085475/q36U8r81/5ffc/channel=doc)。

---

[English](./README_en.md) | **简体中文**

火山引擎团队维护的 skill marketplace，面向 Claude Code / Codex / OpenCode / Cursor / Gemini CLI
等 AI coding agent。仓库默认只安装核心插件；其他技能按火山引擎产品域拆分为可选插件，由
`volcengine-find-skills` 统一发现和安装。

**[快速安装 →](#默认安装)**

## Plugins

| Plugin | 产品分类 | Skills | 默认安装 |
| --- | --- | --- | --- |
| `volcengine-core` | 核心 | `volcengine-cli`、`volcengine-troubleshooting`、`volcengine-knowledge-search`、`volcengine-find-skills` | 是 |
| `volcengine-storage` | 存储 | `volcengine-tosutil` | 否 |
| `volcengine-database` | 数据库 | `volcengine-db-supabase` | 否 |
| `volcengine-containers-middleware` | 容器与中间件 | `volcengine-vefaas` | 否 |
| `volcengine-security` | 安全 | `volcengine-compliance` | 否 |
| `volcengine-identity-access-control` | 身份与访问控制 | `volcengine-landing-zone` | 否 |
| `volcengine-service-support` | 服务支持 | `volcengine-sale`、`volcengine-prepare`、`volcengine-deploy`、`volcengine-iac`、`volcengine-api`、`volcengine-sdk-generator` | 否 |

核心插件的 marketplace 策略为 `INSTALLED_BY_DEFAULT`，其他插件均为 `AVAILABLE`。
`skills/` 下只保留 `core/` 分类；发布工具会自动发现其中的核心 skill。其他 skill 由各自的可选 plugin 直接拥有，不在 `skills/` 下保留副本。

## Skills

| Skill | Plugin | 场景 |
| --- | --- | --- |
| [`volcengine-cli`](./skills/core/volcengine-cli/SKILL.md) | `volcengine-core` | 用 `ve` CLI 创建、查询和管理云资源 |
| [`volcengine-troubleshooting`](./skills/core/volcengine-troubleshooting/SKILL.md) | `volcengine-core` | 火山引擎故障排查与诊断 |
| [`volcengine-knowledge-search`](./skills/core/volcengine-knowledge-search/SKILL.md) | `volcengine-core` | 使用 `ve docs search/fetch` 检索火山引擎官方文档并获取全文，无需登录 |
| [`volcengine-find-skills`](./skills/core/volcengine-find-skills/SKILL.md) | `volcengine-core` | 列出全部 skill，供 Agent 选择并安装 |
| [`volcengine-sale`](./plugins/volcengine-service-support/skills/volcengine-sale/SKILL.md) | `volcengine-service-support` | 火山引擎商品售卖 |
| [`volcengine-prepare`](./plugins/volcengine-service-support/skills/volcengine-prepare/SKILL.md) | `volcengine-service-support` | 分析仓库并推荐 ECS / VKE / veFaaS 部署形态 |
| [`volcengine-deploy`](./plugins/volcengine-service-support/skills/volcengine-deploy/SKILL.md) | `volcengine-service-support` | 将本地目录或 Git 仓库部署到火山引擎 |
| [`volcengine-iac`](./plugins/volcengine-service-support/skills/volcengine-iac/SKILL.md) | `volcengine-service-support` | 使用 Terraform 编排火山引擎基础设施 |
| [`volcengine-tosutil`](./plugins/volcengine-storage/skills/volcengine-tosutil/SKILL.md) | `volcengine-storage` | 管理 TOS 对象存储资源 |
| [`volcengine-db-supabase`](./plugins/volcengine-database/skills/volcengine-db-supabase/SKILL.md) | `volcengine-database` | 管理 AI 原生 BaaS 平台 Supabase 版（AIDAP） |
| [`volcengine-vefaas`](./plugins/volcengine-containers-middleware/skills/volcengine-vefaas/SKILL.md) | `volcengine-containers-middleware` | 部署和管理 veFaaS Serverless 应用 |
| [`volcengine-compliance`](./plugins/volcengine-security/skills/volcengine-compliance/SKILL.md) | `volcengine-security` | 推荐合规基线、汇总态势并编写自定义规则 |
| [`volcengine-landing-zone`](./plugins/volcengine-identity-access-control/skills/volcengine-landing-zone/SKILL.md) | `volcengine-identity-access-control` | Landing Zone、账号工厂与治理基线 |
| [`volcengine-api`](./plugins/volcengine-service-support/skills/volcengine-api/SKILL.md) | `volcengine-service-support` | 查询 API 参数、错误码和返回结构 |
| [`volcengine-sdk-generator`](./plugins/volcengine-service-support/skills/volcengine-sdk-generator/SKILL.md) | `volcengine-service-support` | 生成可运行的多语言 SDK 示例 |

## 默认安装

### Finder 设计

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
codex plugin marketplace add volcengine/volcengine-skills
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
npx skills add volcengine/volcengine-skills \
  --global --yes --copy --full-depth \
  --skill volcengine-cli volcengine-troubleshooting volcengine-knowledge-search volcengine-find-skills
```

后续可由 finder 调用 `npx skills add --skill` 精确安装单个或多个 skill。如需一次安装 catalog 中的全部 skill：

```bash
npx skills add volcengine/volcengine-skills --full-depth
```

### Claude Code

```text
/plugin marketplace add volcengine/volcengine-skills
/plugin install volcengine-core@volcengine-skills
/reload-plugins
/volcengine-core:volcengine-find-skills
```

### Gemini CLI

```bash
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-cli
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-troubleshooting
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-knowledge-search
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-find-skills
gemini skills list
```

首次安装时逐项确认安全提示。安装后重新启动 Gemini CLI；可直接描述火山引擎任务，也可要求它使用 `volcengine-find-skills`。

### OpenCode

按 [OpenCode 安装说明](./.opencode/INSTALL.md) 挂载核心插件的 `skills/` 目录。

### Cursor

```text
/add-plugin volcengine-core@https://github.com/volcengine/volcengine-skills
/volcengine-find-skills
```

在 Cursor 2.5 或更高版本的 Agent 对话中输入完整命令；`/add-plugin` 可能不会出现在自动补全中。

## 目录结构

```text
volcengine-skills/
├── skills/
│   └── core/                         # CLI 默认安装的核心 skill
├── plugins/
│   ├── volcengine-core/              # 默认核心 plugin，复制 skills/core 并保留 hooks
│   └── volcengine-<domain>/          # 可选 plugin，也是其 skill 的唯一源码
└── .agents/plugins/marketplace.json
```

`skills/core/` 是核心 skill 的规范源码；可选 skill 直接在所属 plugin 中维护。同步脚本只复制 core、生成 manifest 和 marketplace。修改或新增 skill 后运行：

```bash
python3 scripts/sync_plugins.py
python3 scripts/validate_codex_plugin_layout.py
python3 -m unittest discover -s tests -v
```

## License

MIT，见 [LICENSE](./LICENSE)。
