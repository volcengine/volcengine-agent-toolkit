# API 映射表

本文档承接 `SKILL.md` 中被有意收敛的底层 OpenAPI 实现细节，供脚本层、adapter 层和维护者参考。

`SKILL.md` 只定义：
- 模型何时选择哪个分析动作
- 模型层统一参数
- 统一脚本调用入口
- 最终回答的输出行为约束

本文档负责定义：
- 模型层参数到 OpenAPI 请求体的映射
- 各 Action 的底层字段差异
- 固定 `Metric` 取值
- adapter 输出样例
- 返回结构概要
- 输出阶段的数据提取建议

如果只是判断“该调用哪个动作、何时继续下一轮、最终应如何组织表达”，应看 `SKILL.md`；如果需要知道“该动作对应什么 OpenAPI body、字段如何映射、返回结构如何取数”，应看本文档。

## 统一调用入口

由 `call_openapi.py` 使用 Python `subprocess.run` 参数数组执行：

```text
ve billing <QueryCostChangeDimensions|QueryCostChangeAmountComponents|QueryCostChangeDrivers> --force --version 2022-01-01
  --method POST --header Content-Type=application/json --output json --body <JSON>
```

三个 Action 均强制带 `--force`，不探测目录后切换模式，不因失败改用内部接口。当前授权账号由 OpenAPI 鉴权上下文确定；请求不携带 `AccountID`、`account_id`、RPC `Base` 或凭证。不要自行签名或加入 Authorization header。

### 运行配置

在 `run_rca_workflow.py init` 选择配置，优先级为 CLI 参数 > `RCA_OPENAPI_*` 环境变量 > 默认值。region/endpoint/profile 还可继承 `VOLCENGINE_REGION` / `VOLCENGINE_ENDPOINT` / `VOLCENGINE_PROFILE`。默认 environment=online、timeout_seconds=120。后续子进程清除实时环境中的这三个 VOLCENGINE 路由/profile 变量，以保存的配置通过显式 flag 传入。未指定的字段沿用 CLI 配置文件默认值；Host 必须保证该配置文件及用户认证上下文在任务期间稳定且按用户隔离，脚本不读取或快照凭证文件。

| 初始化参数 | 环境变量 | 说明 |
|---|---|---|
| `--environment` | `RCA_OPENAPI_ENVIRONMENT` | online 或 boe；boe 必须有明确 endpoint |
| `--region` | `RCA_OPENAPI_REGION` | OpenAPI region |
| `--endpoint` | `RCA_OPENAPI_ENDPOINT` | API host；不含凭证、路径或查询参数 |
| `--profile` | `RCA_OPENAPI_PROFILE` | 已认证的 CLI profile 名称，不写入密钥 |
| `--timeout-seconds` | `RCA_OPENAPI_TIMEOUT_SECONDS` | 正数，单次调用超时，无调用层自动重试 |

配置保存于 `<state-file>.artifacts/openapi_config.json`。`execute_tool.tool_command` 自动传入 `--runtime-config-file`，不能再叠加 runtime overrides。新任务不能覆盖已存在的 state/artifacts，需使用新路径。BOE 的实际 endpoint、路由与账号由测试环境提供，不能根据示例推断。

## Action 映射

| 语义动作 | OpenAPI Action | 用途 | 模型层入口参数 |
|---|---|---|---|
| 异常维度定位（内部 `QueryCostChangeDimensions`） | `QueryCostChangeDimensions` | 定位哪个产品 / 地域 / 实例 / 计费项等维度贡献了异常 | `current_period` + `base_period` + `dimension` + `filters` |
| 异常金额构成定位（内部 `QueryCostChangeAmountComponents`） | `QueryCostChangeAmountComponents` | 分析某计费项的金额构成（原价、折后价、退款、代金券等）变动 | `current_period` + `base_period` + `charge_item_code` |
| 因子分解（内部 `QueryCostChangeDrivers`） | `QueryCostChangeDrivers` | 分解计费项异常为用量、单价、影响因子的贡献 | `current_period` + `base_period` + `charge_item_code` |

编排动作、脚本输入及网关 Action 均使用三个新名称，无旧名称兼容层；请新建分析任务，不复用旧分析状态。模型参数与响应解析保持不变。单接口单账号默认限流为 5 QPS，正常工作流逐步执行；限流错误沿用现有失败处理路径。

## 模型层参数到 OpenAPI 的映射

本节定义统一模型层参数如何被转换为各 Action 的真实 OpenAPI 请求体。
该映射由 `call_openapi.py` 中的 adapter 逻辑统一执行。
模型层只使用统一字段名，不直接拼接底层 payload。

实现约束：
- `call_openapi.py` 是唯一执行入口，必须负责把模型层统一参数映射为各 Action 的真实 OpenAPI 请求体
- 不允许调用方直接依赖不同 Action 的底层 payload 差异
- 不允许再维护与本文档不一致的第二套 payload 构造规则

### QueryCostChangeDimensions

模型层：

```json
{
  "current_period": "2026-04-01",
  "base_period": "2026-03-01",
  "dimension": "product",
  "filters": {}
}
```

OpenAPI 请求体：

```json
{
  "CurrentPeriod": "2026-04-01",
  "BasePeriod": "2026-03-01",
  "CandidateDimensions": ["product"],
  "Metric": 3,
  "Filters": {}
}
```

映射规则：
- `current_period` → `CurrentPeriod`
- `base_period` → `BasePeriod`
- `dimension` → `CandidateDimensions: [dimension]`
- `filters` → `Filters`
- `Metric=3` 为固定值，表示应付金额口径

约束：
- `CandidateDimensions` 只能传单元素数组
- `filters` 的值必须为 string，key 仅允许：`product`、`instance_no`、`charge_item_code`、`project`、`region_code`

### QueryCostChangeAmountComponents

模型层：

```json
{
  "current_period": "2026-04-01",
  "base_period": "2026-03-01",
  "charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"
}
```

OpenAPI 请求体：

```json
{
  "CurrentPeriod": "2026-04-01",
  "BasePeriod": "2026-03-01",
  "Metric": 3,
  "Filters": {
    "charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"
  }
}
```

映射规则：
- `current_period` → `CurrentPeriod`
- `base_period` → `BasePeriod`
- `charge_item_code` → `Filters.charge_item_code`
- `Metric=3` 为固定值，表示应付金额口径

约束：
- `Filters` **必须**包含 `charge_item_code`
- 保留统一 `filters` 中的上层范围，并合入 `charge_item_code`；两处计费项冲突时报错。

### QueryCostChangeDrivers

模型层：

```json
{
  "current_period": "2026-04-01",
  "base_period": "2026-03-01",
  "charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"
}
```

OpenAPI 请求体：

```json
{
  "current_period": "2026-04-01",
  "base_period": "2026-03-01",
  "filters": {
    "charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"
  },
  "Metric": "original_bill_amount"
}
```

映射规则：
- `current_period` → `current_period`
- `base_period` → `base_period`
- `charge_item_code` → `filters.charge_item_code`
- `Metric="original_bill_amount"` 为固定值

约束：
- **注意**：`QueryCostChangeDrivers` 底层字段使用 snake_case，和 `QueryCostChangeDimensions` / `QueryCostChangeAmountComponents` 不一致
- 模型层不需要感知这个差异；由 adapter 或脚本层负责转换

## Adapter 输出样例

### 1. 定位产品级异常

```json
{
  "CurrentPeriod": "2026-04-01",
  "BasePeriod": "2026-03-01",
  "CandidateDimensions": ["product"],
  "Metric": 3,
  "Filters": {}
}
```

### 2. 已知产品后定位实例级异常

```json
{
  "CurrentPeriod": "2026-04-01",
  "BasePeriod": "2026-03-01",
  "CandidateDimensions": ["instance_no"],
  "Metric": 3,
  "Filters": {
    "product": "ML"
  }
}
```

### 3. 已知实例后定位计费项异常

```json
{
  "CurrentPeriod": "2026-04-01",
  "BasePeriod": "2026-03-01",
  "CandidateDimensions": ["charge_item_code"],
  "Metric": 3,
  "Filters": {
    "instance_no": "r-xxx"
  }
}
```

### 4. 分析金额构成

```json
{
  "CurrentPeriod": "2026-04-01",
  "BasePeriod": "2026-03-01",
  "Metric": 3,
  "Filters": {
    "charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"
  }
}
```

### 5. 分析驱动因子

```json
{
  "current_period": "2026-04-01",
  "base_period": "2026-03-01",
  "filters": {
    "charge_item_code": "ml.hpcpni2.28xlarge_cn-beijing"
  },
  "Metric": "original_bill_amount"
}
```

## 输出与错误契约

调用器输出 `status`、`action`、`model_args`、`request_body`、`result`、`error`、`openapi`。`result` 保留原 OpenAPI envelope；`openapi` 记录非敏感运行配置及 `request_id`。编排器将业务 `result.Result` 传给 interpret_result hook。

成功要求：CLI 退出码为 0，stdout 是 JSON 对象，未返回 `ResponseMetadata.Error`，`Result` 包含有效的三个总额和候选/贡献列表。帮助文本、空输出、缺字段和非法金额都属于失败；有效的空列表或 null 列表才是无候选。保留原响应和 RequestId 便于追踪。

错误包含 `error_code`、`error_message`、`retryable`，API 错误额外保留脱敏的 `remote_code`、`request_id`。缺 CLI、鉴权失败、无权限、参数/响应错误不自动重试；超时、限流、明确临时服务异常沿用状态机的有界重试。脚本失败退出码为 1，stdout 仍是完整 JSON；成功与失败都必须保存并 resume，禁止用 `&&` 让失败跳过 resume。

## 返回结构概要

### QueryCostChangeDimensions 返回

```json
{
  "Result": {
    "totalDiff": 12345.67,
    "baseAmount": 100000.00,
    "currentAmount": 112345.67,
    "candidates": [
      {
        "dimension": "product",
        "coverageRatio": 0.85,
        "values": [
          {
            "valueKey": "ML",
            "valueName": "机器学习",
            "deltaAmount": 10000.0,
            "baseAmount": 80000.0,
            "currentAmount": 90000.0,
            "contributionRatio": 0.81
          }
        ]
      }
    ]
  }
}
```

关键字段：
- `Result.totalDiff`：总差额
- `Result.baseAmount` / `Result.currentAmount`：基期 / 当期总额
- `Result.candidates[0].dimension`：本轮定位维度
- `Result.candidates[0].coverageRatio`：Top values 对异常的覆盖率
- `Result.candidates[0].values[*]`：候选值列表

### QueryCostChangeAmountComponents 返回

```json
{
  "Result": {
    "totalDiff": 5000.0,
    "baseAmount": 8000.0,
    "currentAmount": 13000.0,
    "candidates": [
      {
        "dimension": "amount_component",
        "coverageRatio": 1.0,
        "values": [
          {
            "valueKey": "original_bill_amount",
            "valueName": "原价",
            "deltaAmount": 5000.0,
            "baseAmount": 8000.0,
            "currentAmount": 13000.0,
            "contributionRatio": 1.0
          }
        ]
      }
    ]
  }
}
```

关键字段：
- `values[*].valueKey` / `valueName`：金额构成项
- `values[*].deltaAmount`：差额
- `values[*].baseAmount` / `currentAmount`：基期 / 当期金额

### QueryCostChangeDrivers 返回

```json
{
  "Result": {
    "total_diff": 6500.0,
    "base_amount": 10000.0,
    "current_amount": 16500.0,
    "contributions": [
      {
        "dimension": "usage",
        "dimension_name": "用量",
        "contribution": 8000.0,
        "base_amount": 10000.0,
        "current_amount": 16500.0
      },
      {
        "dimension": "unit_price",
        "dimension_name": "单价",
        "contribution": -2000.0,
        "base_amount": 10000.0,
        "current_amount": 16500.0
      },
      {
        "dimension": "impact_factor",
        "dimension_name": "影响因子",
        "contribution": 500.0,
        "base_amount": 10000.0,
        "current_amount": 16500.0
      }
    ]
  }
}
```

关键字段：
- `Result.contributions[*].dimension`：因子编码
- `Result.contributions[*].dimension_name`：因子中文名
- `Result.contributions[*].contribution`：贡献值

## 输出阶段的数据提取建议

本节定义脚本返回结果到最终用户结论之间的取数规则，供 `SKILL.md` 的输出规范引用。

### 1. 总体趋势
来自 `QueryCostChangeDimensions` 第一步：
- `Result.totalDiff`
- `Result.baseAmount`
- `Result.currentAmount`

### 2. 归因路径
来自多级 `QueryCostChangeDimensions`：
- `Result.candidates[0].values` 的 Top3
- 每项取：`valueName` 或 `valueKey`、`deltaAmount`、`contributionRatio`
- 必要时结合 `coverageRatio` 判断是否“集中度高”

### 3. 金额构成
来自 `QueryCostChangeAmountComponents`：
- 按 `|deltaAmount|` 排序展示 Top5
- 特别关注包含 `refund` / `reversal` / `chargeback` / `adjust` 的金额项

### 4. 因子分解
来自 `QueryCostChangeDrivers`：
- `dimension == "usage"` → 用量贡献
- `dimension == "unit_price"` → 单价贡献
- 其余项合并为影响因子

## 维护原则

1. `SKILL.md` 只保留模型决策必需信息
2. 底层字段命名差异、固定 `Metric`、返回结构细节统一放在本文件
3. 如果底层接口变动，优先修改本文件与 adapter，不要把底层历史包袱重新暴露回 `SKILL.md`
