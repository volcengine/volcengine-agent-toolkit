# 在 OpenCode 中安装 volcengine-agent-toolkit

本仓库自带 `.opencode/opencode.json`，已通过 `skills.paths` 声明核心插件目录。OpenCode 默认发现 `volcengine-core` 的所有核心 skill，包括 `volcengine-feedback`；其他产品域 skill 由 `volcengine-find-skills` 按需安装。若要全局使用，按下面方式挂载核心插件。

## 前置条件

- [OpenCode.ai](https://opencode.ai) 已安装

## 当前推荐：skills.paths 方式

1. **Clone 仓库：**
   ```bash
   git clone git@github.com:volcengine/volcengine-agent-toolkit.git ~/.config/opencode/volcengine-agent-toolkit
   ```

2. **在 `opencode.json` 中添加 skills 路径：**
   ```json
    {
      "skills": {
        "paths": ["~/.config/opencode/volcengine-agent-toolkit/plugins/volcengine-core/skills"]
      }
    }
   ```

3. **重启 OpenCode** 让 skills 被发现。

## 使用

先确认所有核心 skill 均可发现：

```bash
opencode debug skill
```

然后启动 OpenCode，直接描述火山引擎任务，或明确要求加载 finder：

```
use skill tool to load volcengine-find-skills
```

## 更新

```bash
cd ~/.config/opencode/volcengine-agent-toolkit && git pull
```

Skills 通过路径挂载，`git pull` 后即刻生效。

## 卸载

```bash
# 从 opencode.json 的 skills.paths 里移除对应条目
rm -rf ~/.config/opencode/volcengine-agent-toolkit
```

## 工具映射（OpenCode ↔ Claude Code）

本仓库 skill 中引用的 Claude Code 工具，在 OpenCode 里对应：

- `TodoWrite` → `todowrite`
- `Task`（subagent）→ `@mention` 语法
- `Skill` → OpenCode 原生 `skill` 工具
- `Read` / `Write` / `Edit` / `Bash` → 对应原生工具

## 问题反馈

- 使用 `volcengine-feedback` 整理问题、新能力期待或应用案例，或直接填写 [Feedback](https://github.com/volcengine/volcengine-agent-toolkit/issues/new?template=feedback.yml)。反馈自愿，不影响当前任务。
