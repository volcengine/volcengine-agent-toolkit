# 火山引擎 Agent Toolkit 安装手册

这份手册写给 AI Agent。用户把下面这句话发给你时，按本手册安装，全程只需要运行一条命令：

> 打开 https://cloudcache.volccdn.com/ve/skills/install.md ，按说明帮我安装火山引擎 Skills，装完告诉我是否需要重启对话。

所有宿主都用这同一句话，豆包也一样。

> **豆包请使用工作模式安装。** 对话模式不能执行命令和写文件，装不了 Skill。你是豆包且当前处于对话模式时，不要继续往下做，按第 1 步的话术提醒用户切换到工作模式。

## 1. 先确认你能安装

安装需要在用户的机器上执行终端命令、联网、写入用户主目录。

做不到就停下，不要声称已安装，直接回复用户：

> 当前模式不能执行安装。请切换到可以运行命令的模式后，把这句话再发一次。

**豆包**只有工作模式可以安装。在对话模式下回复：

> 对话模式下无法安装 Skill。请切换到「工作模式」，然后把这句话再发一次。

如果你的运行环境对联网或写主目录需要用户批准，就请求批准；不要绕过沙箱，也不要改装到别的位置。

## 2. 运行一条命令

把 `<agent>` 换成你自己所在的宿主：

| 你是 | `<agent>` |
|---|---|
| Claude Code | `claude` |
| Codex | `codex` |
| Trae CLI（`coco` / `traecli`） | `trae-cli` |
| Gemini CLI | `gemini` |
| 豆包（工作模式） | `doubao-work` |
| Trae IDE 国际版 / 国内版 | `trae` / `trae-cn` |
| Cursor | `cursor` |
| OpenCode | `opencode` |

不确定自己是哪个宿主时问用户，不要猜。要给同一台机器上的多个宿主安装，用英文逗号连接，例如 `claude,codex`。

macOS、Linux、WSL、Git Bash：

```bash
curl -fsSL https://cloudcache.volccdn.com/ve/skills/install.sh | sh -s -- --agent <agent>
```

Windows PowerShell：

```powershell
& ([scriptblock]::Create((irm https://cloudcache.volccdn.com/ve/skills/install.ps1))) -Agent <agent>
```

没有 `curl` 时用 `wget -qO- <同一地址> | sh -s -- --agent <agent>`。

脚本自己判断网络：GitHub 可达就从 GitHub 仓库安装；GitHub 不通就从火山引擎 CDN 下载整包到 `~/.volcengine/agent-toolkit/`，校验 SHA-256 后从本地目录安装。两条路径装的内容相同，不需要让用户选，也不需要你自己探测网络。

## 3. 读结果并告诉用户

脚本装完会向宿主确认安装结果，然后在标准输出打印：

```text
SOURCE=cdn
VERSION=<version>
TOOLKIT_DIR=<本地目录>
INSTALL_SOURCE=<实际安装来源>
AGENT=<agent>
VERIFIED=<agent>:ok
```

退出码为 0 且 `VERIFIED` 里每一项都是 `:ok`，安装就完成了，不需要再运行别的命令验证。向用户汇报：

1. 装好了 6 个核心 skill：`volcengine-cli`、`volcengine-troubleshooting`、`volcengine-knowledge-search`、`volcengine-find-skills`、`volcengine-feedback`、`volcengine-billing-and-cost-management`。
2. 来源：`SOURCE=github` 是 GitHub，`SOURCE=cdn` 是火山引擎 CDN；从 CDN 安装时带上 `VERSION`。
3. 何时生效：Claude Code 在当前会话执行 `/reload-plugins` 或新开会话；豆包新开任务；其他宿主新开会话。Codex 新会话启动时会提示审核这个 plugin 带的 hooks，提前告诉用户按提示选择即可，不信任 hooks 也不影响 skill 加载。

脚本以非零退出码结束时，最后一行 `ERROR:` 说明原因。如实告诉用户没有装成，并按下表处理：

| `ERROR:` 内容 | 处理 |
|---|---|
| `Cannot read .../toolkit-manifest.json` | CDN 不可达。让用户检查网络或代理后重跑 |
| `Checksum mismatch` | 下载内容与发布清单不一致。不要绕过校验，重跑一次；仍失败就停止并告诉用户 |
| `'<命令>' is not on PATH` | 对应的 Agent CLI 没装或不在 PATH。告诉用户先安装它，或换一个 `<agent>` |
| `... is not a Volcengine toolkit directory` | 目标目录被别的内容占用。加 `--dir <其他目录>` 重跑，不要删除用户的目录 |
| `npx skills add failed` 且日志是 npm 下载超时 | npm 源不可达。征得用户同意后执行 `npm config set registry https://registry.npmmirror.com` 再重跑 |
| `No DoubaoWork user skill directory found` | 豆包还没有创建工作区。让用户在工作模式下开始一次任务后重跑 |
| `Installed, but <agent> does not list the core skills` | 命令都成功但宿主看不到。把这句话原样告诉用户，不要报告成功 |

## 补充说明

- **本地目录要保留**：Claude Code 直接从 `~/.volcengine/agent-toolkit/` 加载 plugin，Codex 和 Trae CLI 把它登记为 marketplace 根目录。不要放到临时目录，装完不要删。
- **升级**：重新运行同一条命令。CDN 路径下本地已是最新版本时不会重复下载。
- **其他产品域的 skill**：用户提出需求时用 `volcengine-find-skills` 安装。它同样先试 GitHub，不通时自动改用 CDN 整包。
- **可选参数**（PowerShell 为 `-Source`、`-Dir`、`-Version`、`-DryRun`）：`--source cdn` 或 `--source github` 跳过网络探测；`--dir <目录>` 更换本地目录；`--version <版本>` 安装指定版本；`--dry-run` 只打印将使用的来源、版本和目录。
- **安装形态**：`claude`、`codex`、`trae-cli` 安装核心 plugin；`gemini` 逐个安装核心 skill；`doubao-work` 把核心 skill 复制到豆包的用户 skill 目录；其余宿主通过 `npx skills add` 安装，需要本机有 Node.js。

脚本本身下载不了时，可以手工完成 CDN 路径：

1. 下载 `https://cloudcache.volccdn.com/ve/skills/latest/toolkit-manifest.json`，读出 `toolkit.url` 和 `toolkit.sha256`。
2. 下载 `toolkit.url` 指向的 zip，SHA-256 与清单一致才继续。
3. 解压到 `~/.volcengine/agent-toolkit/`，该目录下直接是 `plugins/`、`skills/` 等内容。
4. 以这个目录为来源执行宿主命令，例如 `claude plugin marketplace add ~/.volcengine/agent-toolkit` 和 `claude plugin install volcengine-core@volcengine-skills`。
