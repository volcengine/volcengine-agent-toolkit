# 火山引擎 Agent Toolkit 安装手册

这份手册写给 AI Agent。收到安装请求时，先确认用户要在哪个应用和模式里使用 Skills，再按第 1 节选择安装方式。

> 打开 https://cloudcache.volccdn.com/ve/skills/install.md ，按说明帮我安装火山引擎 Skills，装完告诉我是否需要重启对话。

## 1. 先确认安装目标，再选择安装方式

- **Claude Cowork** 在桌面应用的插件界面安装，按第 1.1 节操作。即使能运行终端命令，Cowork 也不走脚本或手工复制。
- **Claude Code 命令行或桌面 Code 模式**使用第 1.2 节和第 2 节的脚本流程。只有这两个目标使用 `--agent claude`。
- **其他宿主**从第 1.2 节开始。豆包请使用工作模式，并选择「本地电脑」。

如果用户只说「Claude 桌面版」，且上下文无法区分目标，先问「你想在 Cowork 任务里使用 Skills，还是在 Code 模式里使用？」

### 1.1 在 Claude Cowork 安装并验证

1. 在 Claude 桌面应用中进入 **Cowork**，打开「自定义」（部分版本从侧栏的「插件」进入），再进入「插件管理」。
2. 选择「添加插件市场」，输入 `https://github.com/volcengine/volcengine-agent-toolkit` 并确认。如果看不到这个入口，请用户检查当前工作区的插件管理权限，必要时联系工作区管理员，取得权限后再继续。
3. 打开刚添加的 `volcengine-skills` 市场，选择 `volcengine-core`，点击「安装」。
4. 回到插件管理的「已安装」列表，确认其中出现 `volcengine-core`。仅在市场中看到插件时，还需要完成上一步安装。
5. 新开一个 **Cowork 任务**验证 Skill 能否调用。可以发送「请调用 volcengine-find-skills，列出与对象存储 TOS 相关的 Skills，只查询。」确认新任务实际调用了该 Skill 并返回查询结果。

只向用户提供了以上路径时，回复「已提供指引，尚未验证安装」。如果只确认了第 4 步，告诉用户插件已列入「已安装」，尚待新任务验证。第 4、5 步都确认后，再报告「volcengine-core 已安装，新 Cowork 任务已验证 Skill 可调用」。Cowork 的流程到此结束。

### 1.2 确认脚本能在用户本机运行

脚本安装需要在用户的机器上执行终端命令、联网、写入用户主目录。

做不到就停下，不要声称已安装，直接回复用户：

> 当前模式不能执行安装。请切换到可以运行命令的模式后，把这句话再发一次。

**豆包**只有工作模式可以安装。在对话模式下回复：

> 对话模式下无法安装 Skill。请切换到「工作模式」，然后把这句话再发一次。

如果你的运行环境对联网或写主目录需要用户批准，就请求批准；不要绕过沙箱，也不要改装到别的位置。

有些应用把你的终端放在隔离的沙箱或虚拟机里，例如豆包的“云电脑”、各类云端工作区。在那里安装只会装进沙箱，用户的应用读不到，脚本却仍然会报告成功。

运行安装命令前先看一眼 `uname -s`、`echo "$HOME"` 和 `whoami`。出现下面任一情况，就说明你在沙箱里：

- 系统和用户实际使用的不一致，比如用户用的是 macOS 或 Windows 上的桌面应用，而命令跑在 Linux 里。
- 主目录是 `/sessions/...`、`/home/user`、`/root` 这类临时目录，看不到用户平时的文件。

在沙箱里不要运行安装命令，也不要声称已安装。按下面的方式告诉用户：

- **豆包**：请用户把执行环境切到“本地电脑”，再把这句话发一次。
- **其他应用**：请用户在自己机器的终端里运行第 2 步的命令，`<agent>` 填该应用对应的值，然后回来告诉你结果。

## 2. 为目标宿主运行安装脚本

按第 1 节确认的安装目标填写 `<agent>`。

| 目标宿主 | `<agent>` |
|---|---|
| Claude Code（命令行，或桌面应用里的 Code 模式） | `claude` |
| Codex（命令行或桌面端） | `codex` |
| Cursor | `cursor` |
| Trae IDE 国际版 / 国内版 | `trae` / `trae-cn` |
| Trae CLI（`coco` / `traecli`） | `trae-cli` |
| 豆包（工作模式） | `doubao-work` |
| WorkBuddy | `workbuddy` |
| Qoder / Qoder 国内版 | `qoder` / `qoder-cn` |
| Gemini CLI | `gemini` |
| OpenCode | `opencode` |
| 其他 Agent | `other` |

**表里没有你的宿主，不代表不支持。** 这时不要回复“暂不支持”，用 `other` 安装：脚本会通过 `npx skills add` 装到通用目录 `~/.agents/skills`，以及它在这台机器上检测到的各个 Agent 的 skill 目录。如果你知道自己在 skills CLI 里的名字，也可以直接把那个名字当作 `<agent>`。

宿主自己的命令行不在 PATH 里也照常安装，不需要用户先去装命令行：`claude`、`codex`、`gemini`、`trae-cli` 找不到对应命令时，脚本自动改用 `npx skills add` 装到该宿主的用户 skill 目录，桌面端同样读取这个目录。

确实判断不出自己是哪个宿主时，用 `other`；要给同一台机器上的多个宿主安装，用英文逗号连接，例如 `claude,codex`。

macOS、Linux、WSL、Git Bash：

```bash
curl -fsSL https://cloudcache.volccdn.com/ve/skills/install.sh | sh -s -- --agent <agent>
```

Windows PowerShell：

```powershell
& ([scriptblock]::Create((irm https://cloudcache.volccdn.com/ve/skills/install.ps1))) -Agent <agent>
```

没有 `curl` 时用 `wget -qO- <同一地址> | sh -s -- --agent <agent>`。

脚本自己选择下载源，优先 GitHub：GitHub 可达就从 GitHub 安装；GitHub 不通，或者从 GitHub 安装中途失败，就改从火山引擎 CDN 下载整包到 `~/.volcengine/agent-toolkit/`，校验 SHA-256 后从本地目录安装。两条路径装的内容相同，不需要让用户选，也不需要你自己探测网络。

有些宿主会对来自网页的命令弹出确认，这是正常的，请用户点允许。

## 3. 核对脚本安装结果

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
| `'npx' is not on PATH` | 这条安装路径需要 Node.js。告诉用户先安装 Node.js 再重跑 |
| `No WorkBuddy directory found` | WorkBuddy 还没有创建自己的目录。让用户先打开一次 WorkBuddy 再重跑；仍然失败按第 4 步手工安装 |
| `... is not a Volcengine toolkit directory` | 目标目录被别的内容占用。加 `--dir <其他目录>` 重跑，不要删除用户的目录 |
| `npx skills add failed` 且日志是 npm 下载超时 | npm 源不可达。征得用户同意后执行 `npm config set registry https://registry.npmmirror.com` 再重跑 |
| `No Doubao user skill directory found` | 豆包还没有创建工作区，或者你的豆包版本把用户 skill 放在了脚本不认识的目录。按第 4 步手工安装 |
| `Installed, but <agent> does not list the core skills` | 命令都成功但宿主看不到。把这句话原样告诉用户，不要报告成功 |
| 其他报错，或脚本不认识你的宿主 | 按第 4 步手工安装 |

## 4. 脚本没覆盖或失败时：自己完成安装

为第 1.2 节中的宿主安装时，如果脚本失败、下载不了或无法识别宿主，可以按本节手工安装 6 个核心 skill。Claude Cowork 只使用第 1.1 节的桌面插件界面。

下面三种情况不要手工安装，停下来告诉用户：

- 第 1 步判断出你在沙箱里，或者没有执行命令、写主目录的权限。
- 报错是 `Checksum mismatch`：下载内容不可信，不要绕过。
- CDN 本身访问不了：没有可用的下载源。

### 4.1 下载并校验

1. 下载 `https://cloudcache.volccdn.com/ve/skills/latest/manifest.json`，读出 `version`、`bundle.url` 和 `bundle.sha256`。
2. 下载 `bundle.url` 指向的 `volcengine-skill-bundle.zip`，计算 SHA-256，与 `bundle.sha256` 一致才继续。
3. 解压到一个临时目录。解压后顶层就是 6 个目录：`volcengine-cli`、`volcengine-troubleshooting`、`volcengine-knowledge-search`、`volcengine-find-skills`、`volcengine-feedback`、`volcengine-billing-and-cost-management`，每个目录里都有 `SKILL.md`。

### 4.2 确定你的宿主读取用户 skill 的目录

优先用你自己能确认的信息：你当前已加载的其他用户级 skill 所在的目录，就是要放的位置。确认不了时再查下表：

| 宿主 | 用户 skill 目录 |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex、Cursor、OpenCode | `~/.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| Trae IDE 国际版 / 国内版 | `~/.trae/skills/` / `~/.trae-cn/skills/` |
| Qoder / Qoder 国内版 | `~/.qoder/skills/` / `~/.qoder-cn/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` |
| 豆包工作（独立应用，macOS） | `~/Library/Application Support/DoubaoWork/<profile>/.doubaowork/agent_mode/workspace/.user_skills/` |
| 豆包应用内置的工作模式（macOS） | `~/Library/Application Support/Doubao/<profile>/.doubao/agent_mode/workspace/.user_skills/` |
| 表里没有 | `~/.agents/skills/`，多数宿主会读取这个通用目录 |

目录确认不了、表里也没有、通用目录装完宿主又看不到时，问用户，不要随便找一个目录放。

### 4.3 复制并核对

1. 把 6 个目录复制到上一步确定的位置。只替换这 6 个同名目录，不要动该位置下的其他内容。
2. 核对 6 个目录都在，且各自有 `SKILL.md`。
3. 告诉用户：脚本为什么没用上（带上 `ERROR:` 原文），你是手工安装的，来源是火山引擎 CDN 和 `version`，装到了哪个目录，以及需要新开会话或任务才能加载。手工安装没有 `VERIFIED` 输出，不要编造这一行。

### 4.4 想装成 plugin 的宿主

Claude Code、Codex、Trae CLI 也可以手工装成核心 plugin，这样能带上 hooks：

1. 下载 `https://cloudcache.volccdn.com/ve/skills/latest/toolkit-manifest.json`，读出 `toolkit.url` 和 `toolkit.sha256`。
2. 下载 `toolkit.url` 指向的 zip，SHA-256 与清单一致才继续。
3. 解压到 `~/.volcengine/agent-toolkit/`，该目录下直接是 `plugins/`、`skills/` 等内容。这个目录要长期保留。
4. 以这个目录为来源执行宿主命令，例如 `claude plugin marketplace add ~/.volcengine/agent-toolkit` 和 `claude plugin install volcengine-core@volcengine-skills`。

## 脚本安装补充说明

- **本地目录要保留**：Claude Code 直接从 `~/.volcengine/agent-toolkit/` 加载 plugin，Codex 和 Trae CLI 把它登记为 marketplace 根目录。不要放到临时目录，装完不要删。
- **升级**：重新运行同一条命令。CDN 路径下本地已是最新版本时不会重复下载。
- **其他产品域的 skill**：用户提出需求时用 `volcengine-find-skills` 安装。它同样先试 GitHub，不通时自动改用 CDN 整包。
- **可选参数**（PowerShell 为 `-Source`、`-Dir`、`-Version`、`-DryRun`）：`--source cdn` 或 `--source github` 跳过网络探测；`--dir <目录>` 更换本地目录；`--version <版本>` 安装指定的已发布版本，已发布版本只在 CDN 上，所以会直接走 CDN；`--dry-run` 只打印将使用的来源、版本和目录。
- **安装形态**：`claude`、`codex`、`trae-cli` 安装核心 plugin；`gemini` 逐个安装核心 skill；`doubao-work`、`workbuddy` 把核心 skill 复制到各自的用户 skill 目录；其余宿主，以及上面四个找不到自身命令行时，通过 `npx skills add` 安装，需要本机有 Node.js。
