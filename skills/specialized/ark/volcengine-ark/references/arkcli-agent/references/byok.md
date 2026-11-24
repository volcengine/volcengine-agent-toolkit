# BYOK 模型与请求凭证

本期仅支持 Direct 接入：MA 模型网关直接请求用户配置的模型 HTTPS 接口。Provider 必须已在目标 MA 环境配置为 Direct；名称由用户或服务配置提供，不凭名称推断已开通，也不把某个 STG 测试 Provider 当作线上通用值。CLI 不提供出网模式切换参数。

仅适用于用户明确提供第三方模型接入信息的场景。使用当前火山产品内已确认的 Platform profile，不能沿用 Agent Plan / Coding Plan profile；必要时用单次 `--profile` 选择，详见 [认证与 Profile](../GUIDE.md#认证与-profile)。`Model.BaseUrl` 是模型服务地址，不是 CLI 的 `--base-url`，后者会改变 MA 数据面地址。

## 区分 MA 与模型上游

| 配置 | 作用对象 |
| --- | --- |
| `--env prod/stg` | MA 控制面和默认数据面环境，不改写 `Model.BaseUrl` |
| Platform Profile / `ARK_API_KEY` / `--api-key` | 访问 MA 的凭证，必须适用于目标 MA 环境；控制面仍需登录 |
| `Model.Provider/Id/Protocol/BaseUrl` | 模型上游配置；Provider 属于 MA 环境，模型 ID 和完整接口 URL 属于上游 |
| `--model-header-env Authorization=MODEL_AUTH` | 上游模型凭证；若上游使用 Bearer，变量值须为完整的 `Bearer <key>` |

MA 与上游可以处于不同环境。例如用户要求 STG MA 调线上模型时，使用 `--env stg` 和 STG MA Key，`Model.BaseUrl` 则填线上模型接口，`MODEL_AUTH` 使用线上模型 Key。不要把上游 Key 填入 CLI `--api-key`，也不要用 `--base-url` 设置上游地址。环境切换不保证 Profile 中的 Key 自动适配目标环境。

## 模型配置

Agent 创建/更新的 `--model` 接受 ID 或 inline JSON/YAML 对象；复杂请求用 `--file`。Session 创建使用 `--agent-overrides`，已有 Session 使用 `session upgrade --model`。它们支持同一组模型字段，升级接口使用 snake_case，其余使用下表的 TOP 字段名；常见 snake_case/camelCase 别名会归一化，Headers 内容不改写。

| 字段 | 类型与含义 |
| --- | --- |
| `Id` | string；用户选择的模型标识，不猜测或替换 |
| `Provider` | string；模型提供方；省略或 `ark` 走原有 Ark 模型开通检查，其他值不查询/开通 Ark 模型；MA 服务开通检查仍保留 |
| `Protocol` | string；按模型接入契约选择，例如 `openai_chat_completions`、`openai_responses`、`anthropic_messages`、`ark_responses`；CLI 不维护业务枚举白名单 |
| `BaseUrl` | string；完整 HTTPS 模型接口 URL，需由用户提供或从可靠配置取得；网关不自动追加路径，例如 Chat Completions 要包含 `/v1/chat/completions`（实际前缀由上游决定） |
| `Headers` | string → string 对象；持久化的普通上游 Headers，不用于存放密钥 |
| `TokenLimits.ContextWindow` | int64；模型上下文 token 上限 |
| `TokenLimits.MaxInputTokenLength` | int64；最大输入 token 数 |
| `TokenLimits.MaxOutputTokenLength` | int64；最大输出 token 数 |
| `InputModalities` | string 数组；模型输入模态，按提供方声明填写，不据此自动添加多模态工具 |
| `Speed/Thinking/ReasoningEffort/ServiceTier` | 可选运行参数，含义见 [model-config.md](model-config.md)；不把 Ark metadata 当作任意第三方模型的事实源 |

未提供的可选字段不发送；显式空 Headers、空模态数组、空字符串和 TokenLimits 的 0 会保留。是否允许清空、数值边界、Provider/Protocol 合法性由接口校验。不要自行补默认值。

自建 Direct Provider 的 TokenLimits 三项均需为正整数，不能只填 ContextWindow。向用户或上游规格取得实际值；若上游明确是方舟模型，可在上游所在环境按准确模型名和版本查询 metadata：`context_window`、`max_input_tokens`、`max_completion_tokens`，依次映射到上述三项。缺失值不能当 0，也不能套用其他模型的上限。

```bash
arkcli agent agent create \
  --name byok-demo \
  --model '{"Id":"<model-id>","Provider":"<provider>","Protocol":"openai_chat_completions","BaseUrl":"https://model.example/v1/chat/completions","TokenLimits":{"ContextWindow":131072,"MaxInputTokenLength":126976,"MaxOutputTokenLength":4096},"InputModalities":["text"]}' \
  --dry-run --format json
```

地址、模型和 token 数只是格式示例，必须替换成用户确认的实际配置。确认后执行并 `agent agent get` 回读。Preview 不验证第三方模型可用性。

Agent 请求优先级：`--file` → 显式 `--model` 替换整个请求 Model → 显式运行参数 flags。update 不传 `--version` 时仍读取当前版本；不把旧 Model 整块合回新配置。更新 Agent 不会更新旧 Session，后者要显式 upgrade。Session override/upgrade 只提交显式字段，保留/清空语义由后端决定。

## 每次消息的模型凭证

支持入口：`agent session events send`、`agent session compact`、`+new session`。使用可重复的 `--model-header-env HeaderName=ENV_NAME`。环境变量值是完整 Header 值，不会自动补 `Bearer`。

```bash
# 先由用户或密钥管理工具安全地设置 MODEL_AUTH；不要打印它。
arkcli agent session events send <session-id> \
  --text 'hello' \
  --model-header-env Authorization=MODEL_AUTH \
  --dry-run --format json
```

- Preview 只展示引用，不读取环境变量值；发送和 compact 可预览，`+new session` 不支持 dry-run，应先只读核对并确认。
- 真实发送才读取变量。MA 的 Authorization 来自显式 MA Key 或当前 Platform profile；模型凭证单独通过 `X-User-Model-Header-*` 发送。每一轮 send/compact 都需重新传入上游凭证映射，Session 不保存它。
- 仅消息 POST 携带模型凭证；不写入 Agent、Session、profile 或请求 Body，不传给查询、SSE、文件请求。多事件串行发送共用本次凭证，部分成功后不自动重放。
- Header 名不区分大小写，不允许重复映射；变量缺失、空值或非法 HTTP Header 值会在副作用前报错。凭证请求不跟随重定向。
- 静态 `Model.Headers` 不放 `Authorization`、`X-Api-Key`、`Api-Key`；后端会校验静态/动态 Header 冲突。不要用静态 Headers 绕过请求凭证入口。
- upgrade 的 initial_events 是否支持传递 BYOK 凭证尚未确认，因此 upgrade 没有此 flag。先升级配置并回读；需要压缩时另行显式调用 compact，不擅自追加操作。
- 不在日志、对话、调试导出或报告里展示密钥。查询成功、创建成功、消息受理都不等于模型推理成功；需在获得测试授权后核对实际回复和终止事件。

## 验证与排障

- 等待实际回复使用 `events send ... --stream --format jsonl`（或不指定 format）；流式输出不能配 `--format json`。正常回复、`end_turn` 和退出码 0 才能确认本轮完成。
- 中间某次 `span.model_request_end.is_error=true` 不等于最终失败：后端可能重试后成功。记录尝试次数与最终状态，不自动重发已受理消息；最终 `retries_exhausted` 应为退出码 5 / `agent_execution_failed`。
- 消息提交即报 MA 鉴权错误时，先核对 MA Key 与 `--env`，不据此判断上游 Key 无效。收到模型错误时核对 Provider 在目标 MA 环境的配置、完整 URL、协议及上游凭证；只有泛化 provider 错误时保留 Session ID 和时间供查日志，不猜 401、限流或网络故障。获授权的上游直连成功只证明上游可用，不代替 MA 端到端验证。
