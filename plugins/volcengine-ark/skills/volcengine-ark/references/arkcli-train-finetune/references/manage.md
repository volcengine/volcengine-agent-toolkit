# 查询和管理指定精调任务

本 reference 处理已知 job id 的详情、观察和生命周期操作。需要根据指标选择产物、导出 custom model 或继续部署时，改读 [`export-deploy.md`](export-deploy.md)。

## 命令速查

| 命令                                               | 何时用                     | 常用参数                                                |
| ------------------------------------------------ | ----------------------- | --------------------------------------------------- |
| `arkcli train finetune get <job-id>`             | 查完整详情，PRD-canonical 读入口 | `--transform`                                       |
| `arkcli train finetune status <job-id>`          | 查状态；语义上等同详情查询           | `--transform`                                       |
| `arkcli train finetune watch <job-id>`           | 持续监测进度及指标变化             | `--interval`、`--timeout`、`--quiet`、`--rich`         |
| `arkcli train finetune metrics <job-id>`         | 查指标曲线                   | `--metric`、`--from-step`、`--to-step`、`--output`     |
| `arkcli train finetune logs <job-id>`            | 查训练日志                   | `--tail`、`--since`、`--search`、`--follow`、`--output` |
| `arkcli train finetune trajectory list/get`      | 查 RL 轨迹                 | 仅在任务和 TLS 配置支持时使用                                   |
| `arkcli train finetune update <job-id>`          | 改名称或描述                  | `--name`、`--description`                            |
| `arkcli train finetune pause/resume/stop/delete` | 生命周期操作                  | 写/删/终止前必须确认；需要时才加 `--yes`                           |

## 先查询当前状态

任何写操作前先执行：

```bash
arkcli train finetune get <job-id>
```

确认 job id、当前阶段和目标操作是否匹配。具体阶段限制以当前命令 `--help` 和后端错误为准，不维护静态阶段矩阵。

用户询问指定任务“为什么查不到”时也直接执行同一条 `get`，并原样保留权威 API 错误。不要从 `mcj-*` 的日期片段或后缀猜测合法性；不要先执行 `list` 搜索相似任务，也不要切换 profile/project/region。用户明确限制范围时，失败即停止并解释该错误。

## 详情与过程观察

按用户目标选择最小命令：

```bash
arkcli train finetune get <job-id>
arkcli train finetune watch <job-id>
arkcli train finetune metrics <job-id>
arkcli train finetune logs <job-id>
arkcli train finetune trajectory list <job-id>
```

执行前查看对应 `--help`。

- 一次性状态用 `get`，持续等待终态用 `watch`。
- 指标先查询可用 metric 名称，再按真实名称过滤。
- `metrics` 同时使用 `--from-step` 和 `--to-step` 时，`to-step` 必须严格大于 `from-step`。
- 日志、轨迹和指标可能很大；优先使用过滤、tail 或 `--output`，不要把完整内容灌入上下文。
- trajectory 仅在任务和当前 ArkCLI 能力支持时使用。
- 任务失败时返回阶段、错误原因和 CLI 提供的 hint，不要盲目重复提交。

### 保存指定任务日志

用户同时给出 MCJ ID 和输出路径时直接执行：

```bash
arkcli train finetune logs <mcj-id> --output <path>
```

这是单任务只读查询。不要先跑 `logs --help` 后停住，也不要执行 `train finetune list --page-all`、用 Python 遍历任务或建议切换 profile/project。命令失败时保留原错误并停止；只有语法不兼容时才查看当前 `logs --help` 后重试同一个目标命令。

`--follow` 会在活跃任务上持续轮询。任务执行前已经处于 `Completed` / `Failed` / `Terminated` 时，CLI 输出当前日志快照后自动退出；活跃任务后续进入终态且没有新日志时也自动退出。终态任务允许 `--follow --format json` 返回一个有界 JSON 快照；活跃任务的无界 follow 不支持单文档结构化输出。

### 查询指定任务的完整 trajectory

```bash
arkcli train finetune trajectory list <mcj-id> --full
```

命令层级必须包含 `train finetune trajectory list`；不要尝试 `arkcli train trajectory` 或在 help 树里漫游。`--full` 返回完整 rollout 内容，结果较大时仅在用户给出路径或同意后增加 `--output <path>`。若命令返回任务未开启 trajectory logging、无轨迹、认证或 TLS 权限错误，保留原错误并停止，不查询其他任务、profile 或 MCP 配置。

## TLS 配置

查询或管理精调 TLS 配置时，必须使用完整的 `tls config` 层级：

```bash
arkcli train finetune tls config get
arkcli train finetune tls config enable
arkcli train finetune tls config disable
arkcli train finetune tls config delete
```

不存在 `tls update`。不要省略 `config` 写成 `arkcli train finetune tls get`。

- `get` 只读，无需确认。
- `enable` 会创建可能产生费用的 TLS 资源，先说明费用影响并取得确认。
- `disable` 停止写入新数据但保留已有数据，执行前需确认。
- `delete` 会永久删除已有 trajectory、custom log、trace 和 explainability 数据，需单独确认；非交互执行只有在确认后才添加 `--yes`。

## 任务元数据

更新名称或描述前，打印 job id、当前值和目标值并取得用户确认：

```bash
arkcli train finetune update <job-id> --help
arkcli train finetune update <job-id> --name <name>
```

只发送用户要求修改的字段。

## 暂停、恢复、停止和删除

先分别查看当前接口：

```bash
arkcli train finetune pause --help
arkcli train finetune resume --help
arkcli train finetune stop --help
arkcli train finetune delete --help
```

规则：

- `pause` 用于希望后续继续的任务。
- `resume` 的主要用途是恢复 `Paused` 任务，与 `pause` 形成可逆关系；后端允许时也可重试 `Failed` / `Terminated`。执行前仍以当前任务 phase 和后端结果为准。
- `stop` 是不可逆终止，必须明确说明影响并获得确认。
- `delete` 删除任务记录，必须展示目标 job id、名称和当前阶段，并获得单独确认。**Phase 强校验**：仅终态（`Completed` / `Failed` / `Terminated`）可删，非终态在客户端直接拒绝并提示先执行 `train finetune stop`，避免用户输 y 后被 backend `phase_mismatch` 拒。
- Agent 环境要求 `--yes` 时，只能在用户确认后添加。
- 阶段不允许时，根据 CLI/backend hint 给出下一步，不通过反复重试绕过限制。

## 训练产物

用户只想查看产物时，可以执行：

```bash
arkcli train finetune artifacts list <job-id>
```

用户要选择最佳产物、导出或部署时，不在本文件继续，读取 [`export-deploy.md`](export-deploy.md)。
