# Debug / Export / 验证

## Debug / Export

- `+debug <session-id>` 聚合 session get、最近 events、resources、threads，输出状态、错误事件、pending action、warnings。用 `--limit` 控制事件数量，`--session-thread-id` 聚焦单线程。
- `+export <session-id>` 写 `arkcli-session-<session-id>-<timestamp>.tar.gz`，可用 `--output` 指定路径。归档包含 `manifest.json`、`session.json`、`events.json`、`resources.json`、`threads.json`、`notes.md`。
- 写归档前先执行同一条 `+export <session-id> ... --dry-run --format json`，核对零网络 `preview.v1` 中的四个读取步骤、归档条目和本地输出路径。未传 `--output` 时默认文件名中的时间是 `unresolved` 占位符；Preview 不读取 session，也不创建或覆盖归档。
- 当前 workspace tarball 和 memory snapshot 没有可用读取接口，导出时只在 manifest 标为 unsupported，不伪造内容。

## 端到端验证模板

下面每一行都必须是**独立的 shell/tool 调用**，不要合并成一个带 `;`、`&&` 或管道的长命令。每一步成功后再把返回的 ID 传给下一步；某一步超时后，单独对已知 ID 做诊断。

```bash
arkcli agent agent get <agent-id> --format json
arkcli agent env create --name arkcli-<domain>-env-<timestamp> --config '{Type: cloud, Networking: {Type: unrestricted}}' --format json
arkcli agent session create --agent-id <agent-id> --environment-id <env-id> --title arkcli-<domain>-session-<timestamp> --format json
arkcli agent session events send <session-id> --type user.message --text "<one small test task>" --format json
arkcli agent session events stream <session-id>
arkcli agent session get <session-id> --format json
arkcli agent session events list <session-id> --limit 20 --format json
arkcli +tail <session-id> --session-thread-id <thread-id>
arkcli agent session threads list <session-id> --limit 10 --format json
arkcli agent session resources list <session-id> --format json
```

用户要求“不要删资源”时，保留创建出的 agent/env/session/vault/credential。
