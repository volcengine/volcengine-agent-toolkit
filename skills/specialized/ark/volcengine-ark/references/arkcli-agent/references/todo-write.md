# Todo Write 任务计划工具

用户明确要求启用任务计划/待办工具时读本节。`todo_write` 是内置工具，复用 Agent create/update 的 `--tool`，不是 custom tool，也没有独立的 Todo CLI 命令。

## 配置与前提

- 配置名固定为 `todo_write`，属于 `agent_toolset_multimodal_20260825`；不要放进 `agent_toolset_20260701` 或 `agent_toolset_20260916` 等基础工具集。
- 不需要 `Models`，不查询工具模型，也不因 toolset 名称含 multimodal 而开启生图/视频工具。
- 火山后端 `release/20261013` 对普通 Agent 使用该 toolset 检查 `FrontendMutilmodalTools` 白名单。CLI 能构造配置不代表账号已获准使用；遇到权限/白名单错误，保留错误与 RequestId，停止重试，不换基础 toolset 或 Raw API 绕过。其他产品的上线和权限以其服务端为准，不从火山推断。

下面是**一个工具集条目，不是完整 Tools 数组**。新添此 toolset 且仅需 Todo 时，显式关闭默认工具，再单独启用 Todo，避免省略 DefaultConfig 导致其他工具默认启用或触发模型依赖校验：

```json
{
  "Type": "agent_toolset_multimodal_20260825",
  "DefaultConfig": {
    "Enabled": false,
    "PermissionPolicy": {"Type": "always_allow"}
  },
  "Configs": [
    {
      "Name": "todo_write",
      "Enabled": true,
      "PermissionPolicy": {"Type": "always_allow"}
    }
  ]
}
```

## 创建、更新与验证

1. 创建时显式传 `--tool` 会替换默认工具；将上面的条目与用户需要的完整基础工具配置合成数组，不要只传 Todo 条目而丢掉 bash/read/write 等工具。
2. 更新前先 `arkcli agent agent get <agent-id> --format json`。若已有该 toolset，只合并/修改它的 `Configs` 中的 `todo_write`，不要追加重复 toolset，也不要用示例的 DefaultConfig 覆盖已有设置。保留其他工具、模型绑定和 PermissionPolicy；前端隐藏权限控件不表示应删除权限字段。
3. 用 `arkcli agent agent update <agent-id> --tool '<完整 Tools JSON 数组>' --format json` 提交，再 get 回读核对 Todo 与其他工具。关闭时把该项设为 `Enabled: false`，保留其余配置。
4. 要验证实际调用，创建绑定新 Agent 版本的 Session；不要假设旧 Session 自动使用更新后的配置。发送明确要求使用 Todo 制定/更新计划的消息并检查工具事件。配置接受成功不等于工具已被调用；未出现工具事件时如实报告未验证调用。

运行时事件名可能是 `todo_write` 或 `TodoWrite`（取决于 BaseAgent），二者都用于识别 Todo 调用；**写配置始终使用 `todo_write`**。Todo 由 Agent Loop 内置执行，不需要用户实现 custom tool 或手工回传 custom tool result。
