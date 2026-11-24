# plans model-list

> **前置条件：** 先阅读 [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md) 了解认证、全局参数和安全规则。

列出指定套餐的两类模型：`models` 是 `ark-code-latest` 的路由候选，
`direct_models` 是可直接写入推理请求或 Agent 配置 `model` 字段的 ModelName。
两类条目都可包含负载和模型规格。读操作。

清单包含具体模型及控制面的 Auto 路由选项，不能把所有 `output_name` 原样当客户端 Model Name。Coding Plan 的 `auto` 即使同时出现在 `model_id` 和 `output_name`，也只证明它是控制台/`plans model-apply` 的可选目标。客户端要跟随控制台选择（含 Auto），配置 `ark-code-latest`；要直接指定具体模型，则核对当前套餐官方文档并使用支持的具体名称。不能建议客户端填写 `model=auto`，也不因用户只问页面/配置方法而执行 `model-apply`。

以本次 `selected_model_id`/`selected` 标记当前默认模型，不能照抄示例默认值。交付全部清单时保留每项名称与明确的档位限制；只列举部分时说明是示例。

## 命令

```bash
# 当前身份只持有一个有效套餐时，自动识别该套餐
arkcli plans model-list

# 看 Agent Plan 个人版模型
arkcli plans model-list --plan agent-plan

# 看 Coding Plan 团队版模型
arkcli plans model-list --plan coding-plan-team

# 只查可以直接配置/调用的 ModelName（只请求 VirtualModelID）
arkcli plans model-list --plan coding-plan --mode direct

# 只查 ark-code-latest 智能路由候选（只请求 LatestModel）
arkcli plans model-list --plan coding-plan --mode routing
```

## 参数

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `--plan` | 否 | string | `agent-plan` / `coding-plan` / `agent-plan-team` / `coding-plan-team`；省略时自动识别当前身份唯一持有的有效套餐，持有多个时要求显式指定 |
| `--mode` | 否 | string | `all` / `direct` / `routing`，默认 `all`；`direct` 只请求直接 ModelName，`routing` 只请求智能路由候选 |

只有 `--plan` 一个业务筛选参数，不接受 `--type` / `--tier` / `--product` / `--edition`。套餐模型目录按 plan 查询，不按购买档位查询；同一家族的档位共享模型目录，价格、配额与其他权益另查 [buy](arkcli-plans-buy.md) 和 [pricing](../../arkcli-pricing/GUIDE.md)，不能把“模型列出来了”推导为某个档位已获全部权益。

例如 `arkcli plans model-list --plan coding-plan --type pro` 会报未知 flag；应使用 `arkcli plans model-list --plan coding-plan`。需要 vendor、模态或基础模型版本元信息时，把返回的 `model_id`（不是友好展示名 `model_name`）交给 [models get](../../arkcli-models/references/arkcli-models-get.md)，不要从名字推断。

未传 `--plan` 时，CLI 会查询当前身份实际持有的四类套餐。只有一个有效个人订阅或 Running 团队席位时自动使用其 `Edition + BizInfo`；存在多个有效套餐时不按顺序猜选，而是报出候选并要求重新传 `--plan`。任一套餐状态查询失败时也不会根据不完整结果自动选择。

## 返回值

```json
{
  "plan": "agent-plan-team",
  "edition": "enterprise",
  "tier": "large",
  "selected_model_id": "doubao-seed-2-0-pro-260215",
  "models": [
    {
      "model_id": "doubao-seed-2-0-pro-260215",
      "model_name": "Doubao Seed 2.0 Pro",
      "output_name": "doubao-seed-2-0-pro",
      "context_window": 262144,
      "max_input_tokens": 229376,
      "max_completion_tokens": 65536,
      "input_modalities": ["text", "image", "video"],
      "load": {"status": 1, "level": 2, "score": 0.46, "coverage": 0.92, "updated_at": 1789999999},
      "selected": true
    },
    {
      "model_id": "doubao-pro-32k-260215",
      "model_name": "Doubao Pro 32K",
      "output_name": "doubao-pro-32k"
    }
  ],
  "direct_models": [
    {
      "model_name": "doubao-seed-code",
      "context_window": 262144,
      "max_input_tokens": 229376,
      "max_completion_tokens": 65536,
      "input_modalities": ["text", "image", "video"],
      "load": {"status": 1, "level": 1}
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `plan` | 入参回显 |
| `edition` | 请求套餐模型接口使用的版本：个人版 `personal`，团队版 `enterprise` |
| `tier` | 当前套餐档位，即请求中的 `BizInfo` |
| `selected_model_id` | 当前路由选择的后端模型 ID；个人版按订阅服务端 `Enabled` 字段判断，团队版从用户席位映射读取；未选择时省略 |
| `models[]` | `ark-code-latest` 的路由候选；用于 `plans model-apply`，不是直接 ModelName 清单 |
| `models[].model_id` | 后端路由目标 ID，适合控制面写入 |
| `models[].model_name` | 面向用户的展示名；不要把它误当成调用 ID |
| `models[].output_name` | 路由写接口配套的输出名；不要据此推断可直接调用的 ModelName |
| `models[].selected` | 为 `true` 时表示当前路由选中该项；未选中时因 `omitempty` 可能不出现 |
| `direct_models[]` | 当前套餐可直接调用的模型清单，来源为 VirtualModelID 接口 |
| `direct_models[].model_name` | 可直接写入推理请求或 Agent 配置 `model` 字段的准确 ModelName |
| `*.context_window` | 上下文窗口大小，单位为 token；接口未提供时省略 |
| `*.max_input_tokens` | 最大输入 token 长度；接口未提供时省略 |
| `*.max_completion_tokens` | 最大输出 token 长度；接口未提供时省略 |
| `*.input_modalities` | 支持的输入模态，例如 `text` / `image` / `video`；只有 `text` 时表示纯文本输入 |
| `*.load` | 服务端负载快照；仅 `status=1` 且 `level=1/2/3` 分别表示低/中/高负载，其余状态不能解释为当前可用负载 |

## 注意事项

- CLI 会先解析目标套餐的当前档位，实际发出的每个模型列表请求都会携带 `Edition` + `BizInfo`；没有有效订阅/Running 席位或档位为空时直接报错，不发送无范围查询。
- `--mode all` 请求两类模型接口；`--mode direct` 只请求 VirtualModelID，返回空的 `models`；`--mode routing` 只请求 LatestModel，返回空的 `direct_models`。团队版 routing 为标识当前选中项仍可能读取席位信息。
- 个人版与团队版的 ark-code-latest 当前选择来源不同：
  - 个人版：服务端按订阅维度返回模型清单 + Enabled flag
  - 团队版：从用户席位 `ExtraConfig.ArkCodeLatestMappingModelID` 字段读
- 不要把路由候选与直接 ModelName 混用：切换 `ark-code-latest` 只看 `models[]`；直接配置/调用只看 `direct_models[].model_name`。
- 模型规格直接来自套餐模型接口的 `ModelCapability`；缺失字段会省略，不能按模型名猜测或用其它目录数据覆盖
- 数据是订阅期内允许调用的模型，不等同于全局可调用模型；试用模型用 [`../arkcli-models/`](../../arkcli-models/GUIDE.md)

## 参考

- [arkcli-plans](../GUIDE.md) -- skill 概览
- [`plans get`](arkcli-plans-get.md) -- 先看自己持有哪些套餐
- [arkcli-models](../../arkcli-models/GUIDE.md) -- 不限于套餐的模型查询
- [arkcli-shared](../../arkcli-shared/GUIDE.md)
