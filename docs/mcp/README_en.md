# Volcengine MCP Tools

[中文](./README.md)

## Tool reference

See [Remote MCP](../../README_en.md#remote-mcp) for the hosted connection, OAuth, and the four modes.

| Tool | Purpose | Main inputs |
|---|---|---|
| `search_api` | Searches the official public API catalog by keyword or natural-language task. Returns the action, service, version, description, and score. Use `NextOffset` for the next page. | Required `query`. Optional `limit`, `offset`. |
| `list_services` | Lists products and their service codes supported by the CLI. Use it to browse products if the search finds no match. | No inputs. |
| `list_apis` | Lists the API actions supported by the CLI for a service. | Required `service`. |
| `get_api_parameters` | Returns request parameters, types, required fields, and an example for a supported API. | Required `service`, `api`. |
| `call_api` | Executes one supported OpenAPI call as the authorized identity. IAM permissions and the selected mode apply. | Required `service`, `api`. Pass a `parameters` object and `region` as needed. |
| `run_script` | Runs Python in a hosted sandbox to orchestrate several OpenAPI calls with loops, branching, pagination, data processing, and bounded concurrency. Returns the script result and a per-call log. Available when enabled on the server. | Required `code`. Optional `args`, `max_calls`, `max_concurrency`, `timeout_seconds`, `call_timeout_seconds`. |
| `search_docs` | Searches public Volcengine documentation and returns titles, URLs, service codes, and snippets. | Required `query`. Optional `limit`, `service_codes`, `snippet_length`. |
| `fetch_docs` | Reads a document URL returned by `search_docs`. To page through longer articles by Unicode character index, pass `next_start_index` as the next `start_index`. | Required `url`. Optional `start_index`, `max_length`. |

### Typical workflow

1. Find the service code and action with `search_api`. If the search fails or finds no suitable match, use `list_services` and `list_apis`.
2. Use `get_api_parameters` to check request parameters and required fields. `call_api` uses the CLI's built-in service version. The public catalog may list other versions.
3. Use `call_api` for one call or `run_script` for pagination, batching, or aggregation. Scripts use the Python standard library and support top-level `await`. Invoke APIs with `await call_api(service, api, parameters, region)` and assign a JSON-serializable value to `result`.

In `confirm` mode, both `call_api` and `run_script` accept an optional `yes` parameter. The agent omits it
initially and adds `yes: true` for one unchanged retry only after the call is held by a confirmation
rule and you approve that operation. A script stops at the first call that requires confirmation.
Approval covers the entire script. Before rerunning it, check the call log for successful calls and
calls with unknown outcomes because they may execute again.
