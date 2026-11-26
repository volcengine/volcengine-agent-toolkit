# plans model-apply

> **前置条件：** 先阅读 [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md) 了解认证、全局参数和安全规则。

设置指定套餐的 **ark-code-latest 路由目标**：`auto`（智能调度，平台自动挑底层模型）或清单中某个具体影子模型。与控制台「选择 ark-code-latest 路由模型」确认按钮调同一批后端接口，改动立即生效、两端同步。写操作。

## 命令

```bash
# 交互终端：省略 --model 会弹出路由目标选择器（当前生效项带 [当前生效] 标注并默认高亮）
arkcli plans model-apply --plan agent-plan

# 非交互 / agent：必须显式 --model（model id / output name / auto 均可）
arkcli plans model-apply --plan agent-plan --model auto
arkcli plans model-apply --plan coding-plan --model doubao-seed-code
arkcli plans model-apply --plan coding-plan-team --model doubao-seed-code-251028
```

## 参数

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `--plan` | 否 | string | `agent-plan` / `coding-plan` / `agent-plan-team` / `coding-plan-team`，默认 `agent-plan-team` |
| `--model` | 非交互必填 | string | 路由目标：模型 `model_id`、`output_name` 或 `auto`；交互终端可省略进入选择器 |

## 返回值

```json
{
  "plan": "agent-plan",
  "previous_selected_model_id": "doubao-seed-code-251028",
  "applied": {
    "model_id": "auto",
    "output_name": "auto"
  }
}
```

| 字段 | 说明 |
|------|------|
| `plan` | 入参回显 |
| `previous_selected_model_id` | 写入前 ark-code-latest 命中的影子模型 id（未设置时为空） |
| `applied.model_id` / `applied.output_name` | 本次写入的路由目标；`auto` 时两字段均为 `auto` |

## 注意事项

- **可选项以 [`plans model-list --mode routing`](arkcli-plans-model-list.md) 返回的 `models[]` 为准**；`--model` 传清单外的值会报 `不支持路由目标` 并列出可选项
- 团队版（`*-team`）作用域是**当前身份的席位**：账号在该套餐下没有有效席位时会报错，需先在控制台开通席位
- 写入后 CLI 会重读一次清单校验；控制面异步生效期间不一致只打 stderr `warn`、不影响退出码，可用 `plans model-list --mode routing` 复核
- 该命令只改"路由指向"，不改本机 Agent 配置；本机 Agent 要切模型走 [`../../arkcli-helper/GUIDE.md`](../../arkcli-helper/GUIDE.md) 的 `helper configure --model`

## 参考

- [arkcli-plans](../GUIDE.md) -- skill 概览
- [`plans model-list --mode routing`](arkcli-plans-model-list.md) -- 只查询可选路由目标与当前生效项
- [arkcli-shared](../../arkcli-shared/GUIDE.md)
