# volcengine-agent-toolkit

本仓库是 Volcengine Team 维护的 skill marketplace，为 AI coding agent 提供火山引擎场景能力。

## 仓库结构

- `skills/`：包含 `core/` 和 `specialized/`。
- `skills/core/`：只允许 `volcengine-cli`、`volcengine-troubleshooting`、`volcengine-knowledge-search`、`volcengine-find-skills`、`volcengine-feedback`、`volcengine-billiing-and-cost-managment`。
- `plugins/volcengine-core/`：默认核心 plugin，包含 hooks 和上述 core skill 的生成副本。
- `plugins/volcengine-<domain>/`：按产品域拆分的可选 plugin，也是其 skill 的唯一源码位置。
- `skills/specialized/<domain>/<skill>/`：可选 plugin 的生成副本；分类名为 plugin 名去掉 `volcengine-` 前缀。
- `scripts/sync_plugins.py`：从 finder catalog 同步核心与专项 skill 副本、文档清单、plugin manifest 与 marketplace。
- `scripts/validate_codex_plugin_layout.py`：校验目录、文档链接与清单、同步状态和默认安装约束。
- `hooks/`：跨 skill 复用的 telemetry hook。

核心 skill 只修改 `skills/core/`，不要直接修改 `plugins/volcengine-core/skills/`。可选 skill 则直接修改所属 `plugins/volcengine-<domain>/skills/`。

## 什么时候使用

- 操作火山引擎 ECS / VPC / VKE / CLB / RDS / Redis / TOS / DNS / CDN 等资源。
- 使用 `ve`、tosutil、veFaaS 或 Volcengine SDK。
- 处理火山引擎部署、监控、运维、合规、Landing Zone 等场景。
- 用户消息包含「火山」「火山引擎」或 `volcengine`。
- 用户需要查找或安装尚未加载的 Volcengine skill。

## 修改约束

- 所有 skill 必须以 `volcengine-` 为前缀；读 env / 调 bin 必须在 `metadata.openclaw.requires` 声明。
- 用户补充某个 API 的精确 payload、Action、Version 或服务名时，脚本、skill 正文、reference 和测试示例必须同步使用该精确值。
- 跨 skill 经验放在“决策发生的 skill”里；工具型 skill 只保留自身能力、参数约束和安全边界。
- 产品 skill 经 `ve` 代理调用产品 CLI（如 `ve tosutil`、`ve arkcli`、`ve volclog`）时，只写调用前缀和 `ve` 版本门槛；PATH/托管副本解析、首次安装与升级差异属于 `volcengine-cli`，不要在产品 skill 里重复。
- 不要把一次验证里的具体地域、规格、镜像、镜像源候选、清理顺序或临时资源形状写成默认流程，除非它是强依赖约束。
- 排障 skill 按症状、证据类型和判断分支组织；仅在存在真实依赖时规定顺序。
- 不得提交账号信息、AK/SK、本地绝对目录、真实资源 ID 或 TRN。
- 资源 ID 脱敏时保留固定前缀，例如 `vpc-<id>`、`clb-<id>`；账号或数字 ID 使用 `<account-id>` 等语义占位符。


## 新增或移动 skill

1. 核心 skill 放在 `skills/core/volcengine-<name>/`；可选 skill 放在 `plugins/volcengine-<domain>/skills/volcengine-<name>/`。
2. 更新 `skills/core/volcengine-find-skills/references/catalog.json` 中的 plugin、skill 映射和中英文能力摘要。
3. 若安装或使用方式变化，更新相关文档正文；技能清单由 catalog 生成。
4. 运行 `python3 scripts/sync_plugins.py`，同步 core 与 specialized 副本、`README.md`、`README_en.md`、`.cursor/rules/volcengine-skills.mdc`、`GEMINI.md` 的清单和 manifest。
5. 运行 `python3 scripts/validate_codex_plugin_layout.py`，确保文档、marketplace 策略和所有生成副本一致。
6. 运行 `python3 -m unittest discover -s tests -v`，验证同步器的路径与写入边界。

不要手工维护 `plugins/volcengine-core/skills/`、`skills/specialized/`、文档生成区块、plugin manifest 或 marketplace 条目；它们由 catalog 和同步脚本生成。可选 plugin 的 `skills/` 是源码，必须直接维护。

## 当前技能

见 [README Skills 表](./README.md#skills)。
