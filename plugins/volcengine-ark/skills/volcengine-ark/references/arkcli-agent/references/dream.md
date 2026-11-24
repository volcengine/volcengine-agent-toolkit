# Dream：整理会话记忆（仅火山）

Dream 把一个 Memory Store 与若干 Session 作为输入，异步生成新的 Memory Store。创建可能产生模型与运行费用；用户仅要求查询或分析时不创建任务。当前仅火山版本提供这些命令。

## 执行前：确认命令、身份与地址

首次使用或排障时，先确认实际执行的 `arkcli --version` 和 `arkcli agent dream --help`。需要 `create/list/get/wait/cancel`；`unknown command` 是本地命令不可用，不是服务端 404。不要在非火山产品上改地址尝试启用 Dream。安装 CLI 不代表宿主已加载同版本 Skill；若实际加载的 Skill 缺少 Dream 指引，按 `arkcli-connect` 的流程同步当前二进制内嵌 Skill，不凭记忆补命令。

通过 `auth status`、`profile list/show` 核对当前账号与选定 Profile 的 Region、Project。后续命令沿用同一 `--profile <已确认的名称>` 和 `--env prod|stg`；线上任务用 `prod`，不要沿用其他测试留下的 stg 设置，也不要为解决报错擅自切环境。

| 操作 | 接口与认证 |
| --- | --- |
| `dream create` | MA 数据面 `POST /dreams`（标准地址下完整路径为 `/api/v3/dreams`），使用 API Key |
| `dream list/get/wait/cancel` | 控制面 `ListDreams/GetDream/CancelDream`，使用有效的 SSO/STS 或 AK/SK；API Key 不能替代控制面登录 |

没有显式 Key 时使用 Platform Profile，不使用 Agent Plan / Coding Plan 的 Key。用户显式提供 `--api-key` 或 `ARK_API_KEY` 时可覆盖默认 Profile 的 Key，即使默认是套餐 Profile，也不应要求用户先修改全局默认配置。

未显式指定地址时，让 CLI 按产品、Region、环境选择 MA 标准数据面地址，不继承套餐路由。检查是否遗留 `--base-url` 或 `ARK_BASE_URL`：它们会覆盖标准地址；不要把 BYOK 上游模型地址当作 Dream 地址，也不要手工追加 `/dreams` 到 base URL。用户明确要求的自定义地址应保留，发现用途不符时先说明并确认，不静默替换。诊断只展示地址与凭证来源，不输出 Key。

## 选择输入和模型

先核对 Platform 身份、目标资源及权限。account-wide Platform Profile 可以使用，无需强制新建项目级 Profile；资源列表可见不代表可绑定，跨项目是否合法由接口判断。不要自动修改全局 Profile。

用户未指定模型时，复用 `agent model list --format json` 的主模型候选及缓存；不加 `--usage tool`，也不默认加 `--primary-only`。多个候选时让用户选择。`--model` 接受返回的 `items[].model` 字符串，不接受 Agent 的 BYOK Model 对象；Dream 未开放 `--model-header-env`。

这里调用的是 Dream API，不是 `+chat` 推理接口：直接传上述模型 ID，不套用普通 Platform 推理的 Endpoint 选择流程，不自动部署 Endpoint 或将模型 ID 改写为 `ep-*`。

源 Memory Store 应可挂载且不处于 Dreaming，源 Session 不应是 Dream 自身生成的会话（`scene=dreams`）。先读取候选的实际字段；CLI 不额外硬编码资源状态或项目拦截，最终由后端验证。

## 创建

```bash
arkcli agent dream create --memory-store-id <memstore-id> \
  --session-id <session-id-1> --session-id <session-id-2> \
  --model <model-id> --output-name "整理后的记忆" \
  --instructions @dream-instructions.txt --format json
```

| 参数 | 含义 / 当前后端要求 |
| --- | --- |
| `--memory-store-id` | 一个源 Memory Store ID |
| `--session-id` | 可重复；1–100 个非空、不重复的 Session ID |
| `--model` | 模型 ID 字符串，必填 |
| `--output-name` | 新 Memory Store 名称，1–64 个 Unicode 字符 |
| `--output-description` | 可选，最多 300 个 Unicode 字符 |
| `--instructions` | 可选，最多 4096 个 Unicode 字符，支持 `@file` |
| `--file` | 原生 snake_case JSON/YAML；`-` 读 stdin，不隐式读取 stdin |

长度、输入组合、权限和模型资格由接口校验。CLI 校验 payload 结构、类型及基本必填项，未知文件字段报错，避免拼写错误被静默忽略。

```json
{
  "inputs": [
    {"type": "memory_store", "memory_store_id": "<memstore-id>"},
    {"type": "sessions", "session_ids": ["<session-id>"]}
  ],
  "model": "<model-id>",
  "output_memory_store_name": "整理后的记忆"
}
```

flags 覆盖文件中的对应字段；覆盖 `inputs` 时须同时传 `--memory-store-id` 和 `--session-id`，完整替换输入，不与文件隐式拼接。`create --dry-run` 只预览请求，不验证线上资格。

创建仅请求一次，不自动重试网络错误、5xx，也不跟随重定向。响应不确定时先查询任务列表，不重发创建。成功返回 `Result.Id` 后保存 ID，再执行下一条命令。

## 查询、等待和取消

```bash
arkcli agent dream list --limit 20 --page 1 --status running --format json
arkcli agent dream get <dream-id> --format json
arkcli agent dream wait <dream-id> --wait-timeout 600 --wait-interval 10 --format json
arkcli agent dream cancel <dream-id> --yes --format json
```

list 支持可重复 `--status`、`--source-memory-store-query`（ID 精确或名称模糊匹配）、`--order asc|desc`。`--page` 是从 `1` 开始的数字字符串页码；下一页沿用 `NextPage`。`--limit` 为单页条数（后端 1–100，默认 20）；`--page-all` 默认单页 100、最多 10 页；`--page-limit` 是最多页数，不是单页大小。达到上限后检查 `NextPage`。

单任务输出 `Result` 对象；list 输出 `Result` 数组及 `NextPage` / `TotalCount`。`Usage: null` 表示未知用量，不是零费用；保留 `SessionId`、`Outputs`、`Error` 和 `RunningTime`。

wait 仅在 `completed` 时退出 0；`failed` / `canceled` 非零退出并保留任务 ID、状态和后端原因。未知状态报错，不无限轮询。默认等待 600 秒、间隔 10 秒；超时和中断都不取消任务，可用同一个 ID 继续 get/wait。get 查询到失败任务仍是正常查询成功。

只有用户明确确认取消目标后才传 `--yes`。cancel 返回服务端实际状态，若竞态下已 completed，不宣称已取消；不会删除输入或已生成的输出库。create/cancel 支持离线 `--dry-run`，list/get/wait 不支持。完成后用 `agent memory-store get <Outputs[].MemoryStoreId>` 回读输出，而非只凭 completed 宣称记忆内容验证通过。

## 遇到 404 时

先保留失败步骤、脱敏后的完整命令、CLI 版本、产品、环境、Profile 的 Region/Project、目标 ID、HTTP 状态、后端错误码/消息及 RequestId（缺失就说明缺失），再定位：

1. `list/get/wait/cancel` 与 `create` 不是同一条链路。列表成功只能证明控制面调用成功，不能证明创建使用的 Key、地址或数据面路由正确。
2. 创建失败时核对上述地址覆盖与环境；查询失败时核对 Dream ID 是否来自同账号、环境和 Region，并结合后端错误判断资源不存在或不可见。单凭 404 不能断言“接口未发布”“模型不支持”或“Key 错误”。
3. 有任务 ID 就查询该 ID；创建结果不确定且无 ID 时，用任务列表结合输入库、输出名和创建时间核对。未确认前不重发创建，也不通过换地址、换 Key、猜 raw API 路径反复试写。

汇报时区分“创建已受理”“任务 completed”“输出内容已验证”。完整验收需查询输出库、列出输出记忆，并按用户目标读取内容核对；只拿到输出库 ID 或文件列表不能宣称内容正确。
