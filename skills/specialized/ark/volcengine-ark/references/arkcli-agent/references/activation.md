# 开通 Managed Agent 服务（仅火山）

用户只要求开通 MA 时使用 `arkcli agent activate`，不要创建测试 Agent、Session 或发送消息来代替开通。此入口仅适用于火山版。

先按共享规则执行 `auth status --format json`，确认当前账号、认证状态和 Platform 上下文。该命令使用控制面登录凭证，API Key 不能代替登录。开通属于账号级计费能力操作；需告知用户并取得明确确认。

```bash
arkcli agent activate
```

- 已开通：返回 `activated=true, already_activated=true`，不重复开通。
- 未开通：真实终端询问确认；`--yes` 只跳过真实终端的确认。非交互环境单独加 `--yes` 不授权开通。
- 已取得用户明确开通授权时，非交互调用可使用下面的命令（AI 调用仍需附加共享 Skill 的归因前缀）：

```bash
ARKCLI_ALLOW_HEADLESS_ACTIVATION=1 arkcli agent activate --yes
```

成功后 `activated=true, already_activated=false`。只开通 `DataManagedAgentSum` 的 `sandbox`、`web_search`，并轮询确认状态；不激活模型、不创建 Agent/Environment/Session、不购买套餐、不修改 Profile。

查询失败或状态未知时停止，不以 Agent 列表可访问作为已开通证据。开通失败时保留服务端错误；开通后状态确认超时不代表服务端没有生效，先核对状态，避免盲目重试。

该命令依赖在线状态决定跳过或开通，不提供 `--dry-run`。`agent agent create` / `+new-agent` 仍保留原有的自动开通流程，模型开通是另一项独立操作。
