# 火山引擎 MCP 工具

[English](./README_en.md)

## 工具清单

线上连接、OAuth 授权和四种模式见[远程 MCP](../../README.md#远程-mcp)。

| 工具 | 用途 | 主要入参 |
|---|---|---|
| `search_api` | 用关键词或自然语言检索官方公开 API 目录。结果包含 action、service、version、描述与评分。用结果中的 `NextOffset` 翻页。 | 必填 `query`。可选 `limit`、`offset`。 |
| `list_services` | 列出 CLI 支持的产品及其 service code。搜索无结果时可用它浏览产品。 | 无需入参。 |
| `list_apis` | 列出指定产品在 CLI 中支持的 API action。 | 必填 `service`。 |
| `get_api_parameters` | 查询 CLI 所支持 API 的请求参数、类型、必填项和示例。 | 必填 `service`、`api`。 |
| `call_api` | 使用授权身份执行一次受支持的 OpenAPI 调用。调用受 IAM 和所选模式约束。 | 必填 `service`、`api`。按需传入 `parameters` 对象和 `region`。 |
| `run_script` | 在托管沙箱中运行 Python，编排多个 OpenAPI 调用，支持循环、分支、分页、结果处理和有限并发。返回脚本结果和逐次调用日志。服务端启用后可用。 | 必填 `code`。可选 `args`、`max_calls`、`max_concurrency`、`timeout_seconds`、`call_timeout_seconds`。 |
| `search_docs` | 搜索火山引擎公开文档，返回标题、URL、service code 和正文摘要。 | 必填 `query`。可选 `limit`、`service_codes`、`snippet_length`。 |
| `fetch_docs` | 读取 `search_docs` 返回的文档链接。长文可按 Unicode 字符索引分段获取，使用 `next_start_index` 作为下一段的 `start_index`。 | 必填 `url`。可选 `start_index`、`max_length`。 |

### 调用流程

1. 先用 `search_api` 找到 service code 和 action。搜索失败或未找到合适结果时，用 `list_services` 和 `list_apis`。
2. 用 `get_api_parameters` 核对请求参数和必填项。`call_api` 使用 CLI 内置的服务版本，公开目录可能列出其他版本。
3. 单次调用用 `call_api`。需要分页、批量调用或汇总结果时，可用 `run_script`。脚本用标准库，支持顶层 `await`，通过 `await call_api(service, api, parameters, region)` 调用 API，把可序列化为 JSON 的结果赋给 `result`。

在 `confirm` 模式下，`call_api` 和 `run_script` 都支持可选的 `yes` 参数。Agent 首次发起操作时省略它，
仅在操作触发确认规则且得到本次批准后，才加上 `yes: true` 原样重试一次。
脚本遇到首个须确认的调用会停止。批准范围是整个脚本，重跑前应检查调用日志中已成功和结果未知的操作，
因为它们可能再次执行。
