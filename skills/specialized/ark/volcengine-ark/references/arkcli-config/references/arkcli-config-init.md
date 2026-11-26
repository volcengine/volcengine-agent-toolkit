# config init

## 创建或更新 profile

```bash
arkcli config init \
  --profile default \
  --tenant volc \
  --api-key <ark_api_key> \
  --base-url https://ark.cn-beijing.volces.com/api/v3 \
  --region cn-beijing \
  --default-model doubao-seed-1-6 \
  --format json
```

可选控制面凭证：

```bash
arkcli config init --profile default --access-key <ak> --secret-key <sk> --format json
```

## 关键字段

- `--profile`
- `--tenant`（`volc`，决定控制面路由与身份体系）
- `--api-key`
- `--base-url`
- `--region`
- `--env`（全局 flag，非 `config init` 专属；`prod` / `stg` 仅火山有意义）
- `--default-model`
- `--set-default`

## Profile schema v1 (0.1.16+) 改动

- **Project Name 在 0.1.16 起进 profile 切面**：`arkcli profile create --project X` 会把 `Project: X` 写入 `config.yaml` 当前 profile。
- 根命令已删除 `--project-name`，`ARK_PROJECT_NAME` 也不再覆盖运行时。解析顺序为 active profile `Project` > identity store / 火山 `.env` 旧状态兼容 > `default`。
- Region 同样由 Profile 持有；根命令已删除 `--region`，`ARK_REGION` 不再覆盖运行时。

## 推荐迁移到 `arkcli profile create`

`config init` 已 deprecated，新代码请用 `arkcli profile create`：

```bash
arkcli profile create --type platform --region cn-beijing --project default --set-default
arkcli profile create --type agent-plan --plan-tier medium --set-default
arkcli profile create --type coding-plan --plan-tier lite --set-default
```

`profile create` 强制要求显式 `--type`，对应"platform / agent-plan / coding-plan" 三档；其余字段（region / project / owner-trn / default-api-key / plan-tier）跟旧 `config init` 语义一致。
