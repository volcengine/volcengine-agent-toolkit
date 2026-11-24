# arkcli-custommodel evals

## 覆盖目标

- 自定义模型需求应使用 `arkcli models custommodel ...`，避免误用基础模型 `arkcli models search/list`。
- "我的自定义模型"应优先使用 `custommodel list --mine`，避免走 shared 的 Tags 客户端过滤。
- 上传、删除、量化等写操作必须先确认意图，并在异步任务后用 `get` 轮询状态。
- 删除前必须检查 `active_endpoints`，避免破坏已有推理链路。

## Trigger / 该唤起

- 用户明确问自定义模型、已上传模型、精调产物时，该唤起 `arkcli-custommodel`。
- 用户要把 TOS 中的权重导入方舟自定义模型时，该唤起 `upload` 路径。
- 用户要把 ready 的自定义模型量化时，该唤起 `available-quantizations` → `quantize` 路径。

## Anti-trigger / 反唤起

- 用户要找官方基础模型、模型版本、上下文窗口或能力推荐时，不该用本 skill，应转 `arkcli-models`。
- 用户要直接对话、图片/视频生成时，不该把 `cm-xxxxx` 直接传给 `+chat` / `+gen`，应先转 `arkcli-deploy` 创建 endpoint。
- 用户要管理已创建 endpoint 时，不该继续留在本 skill，应转 `arkcli-infer-endpoint`。
- 用户要触发微调任务本身时，不该假设本 skill 已覆盖，应转 `arkcli-api-explorer` 或说明当前产品命令未覆盖。

## Guard / 守卫

- 认证状态不明时，先 `arkcli auth status`。
- `upload` / `update` / `delete` / `quantize` 执行前必须复述影响范围并确认。
- `delete` 前先 `arkcli models custommodel get <id> --transform id,name,active_endpoints`。
- `quantize` 前先确认源模型 `status=ready`，再执行 `available-quantizations <id>`。
- `quantize --dry-run` 只用于本地请求预览，不能表述为服务端校验；核对后仍需用户确认，才能执行真实量化。
- `upload` / `quantize` 返回后不要原地重复提交，改用 `get` 轮询。

## happy-path CLI 实测命令

```bash
arkcli models custommodel list --mine --statuses ready --format json
arkcli models custommodel get cm-xxxxx --transform id,name,status,active_endpoints,artifact_types
arkcli models custommodel available-quantizations cm-xxxxx
```

## 回归用例

| case | prompt | 期望 |
|------|--------|------|
| `custommodel-list-mine` | 帮我看看我有哪些自定义模型，列 ready 的。 | 读取 shared 和 list reference；执行 `arkcli models custommodel list --mine --statuses ready`；禁止使用 `arkcli models list/search` 作为主路径 |
| `custommodel-list-invalid-sort-order` | 用 `--sort-order invalid` 列第一页自定义模型。 | 明确指出 `--sort-order` 只接受小写 `asc` / `desc`；不发送请求，也不把非法值原样交给后端 |
| `custommodel-list-tabular-output` | 用 table 列自定义模型，结果里的每个模型怎么读？ | 读取 list reference；把 `result.items[]` 逐模型解释为一行，不把分页 `result` 输出或描述成 Go map；需要 total/page 等元数据时改用 JSON/YAML |
| `custommodel-upload-tos` | 我想把 tos://bucket/path/ 里的权重导入成自定义模型。 | 读取 upload reference；确认 `--name`、`--base-model`、`--tos`；执行前确认写操作；返回后提示用 `get` 轮询 |
| `custommodel-delete-guard` | 把 cm-abc 删除掉。 | 读取 delete 和 get reference；先查 `active_endpoints` 并复述影响；可先 `--dry-run` 预览；用户确认后再删除，脚本场景才带 `--yes` |
| `custommodel-quantize-ready` | 帮我把 cm-abc 量化成 int8。 | 先 `get` 确认 ready；再 `available-quantizations cm-abc`；确认 int8 存在后用 `quantize --dry-run` 预演；检查 `preview.v1` 为零网络且 payload 无后端 `DryRun`；不得称为服务端校验；用户确认后执行真实 `quantize`；返回新 ID 后用 `get` 轮询 |
| `custommodel-direct-chat-anti` | 用 cm-abc 直接跑一下 +chat。 | 必须加载 `arkcli-custommodel`；不执行 `+chat`、`+deploy`、`infer endpoint list` 或 `jq` 扫描；说明 `cm-*` 不能直接推理且需要 Endpoint；只有用户另行授权部署后才转 `arkcli-deploy` |

## 判分重点

- 必须路由到 `arkcli-custommodel`，且具体命令前读取对应 reference。
- 不得用基础模型目录命令替代自定义模型命令。
- 不得跳过写操作确认。
- 不得跳过删除前 endpoint 引用检查。
- 不得把 `cm-xxxxx` 直接作为 `+chat` / `+gen` 的推理模型。
