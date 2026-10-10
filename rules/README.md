# Rules

大多数 AI coding agent 支持项目级规则文件，Agent 在每次会话中都会遵循其中的指令。[`volcengine-agent-rules.md`](./volcengine-agent-rules.md) 是推荐的火山引擎规则：优先使用已安装的 `volcengine-*` skill、核实 API 细节而不猜测、按授权范围执行云端变更，并约束凭证、部署、排障与费用相关的行为。

安装插件或 skill 不会自动启用这些规则，需要把规则内容加入项目的规则文件。

## 放在哪里

| Agent | 规则文件 | 位置 |
| --- | --- | --- |
| Claude Code | `CLAUDE.md` | 项目根目录 |
| Codex | `AGENTS.md` | 项目根目录 |
| Cursor | `.cursor/rules/*.mdc` | `.cursor/rules/` 目录 |
| Gemini CLI | `GEMINI.md` | 项目根目录 |

- Claude Code、Codex、Gemini CLI：把规则内容追加到已有的 `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`，没有则在项目根目录新建。
- Cursor：新建 `.cursor/rules/volcengine.mdc`，在文件头加 `alwaysApply: true` 的 frontmatter，再粘贴规则内容。

追加到已有文件时，保留原内容，并用固定标记包裹规则，便于以后只替换标记之间的部分来更新：

```markdown
<!-- BEGIN Volcengine Agent rules -->
...volcengine-agent-rules.md 的内容...
<!-- END Volcengine Agent rules -->
```

最新版本：<https://raw.githubusercontent.com/volcengine/volcengine-skills/main/rules/volcengine-agent-rules.md>

## 自定义

推荐规则只是起点。项目自己的约束写在标记之外，例如：

```markdown
# 项目火山引擎规则

- 默认地域 `<region>`，除非明确要求，不在其他地域创建资源。
- 资源命名：{team}-{service}-{env}-{purpose}。
- 所有资源打 team、env、cost-center 标签。
- 生产环境只通过 Terraform 变更。
```

项目指令与推荐规则冲突时，以项目指令为准。

规则是指导文本，不是 IAM、审批或预算系统；硬性的权限、审批与费用控制仍由平台配置保证。
