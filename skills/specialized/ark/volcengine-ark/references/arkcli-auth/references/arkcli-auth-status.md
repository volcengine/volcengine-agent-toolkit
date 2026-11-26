# auth status / logout

## 查看状态

```bash
arkcli auth status
```

输出通常包含：

- `volc_sso` 或 `aksk`（取决于当前 profile 的 tenant 和登录方式）
- 顶层 `identity_type`：当前账号主体类型，固定为 `individual`（个人）或 `enterprise`（企业）。它是账号级事实，与 SSO / AKSK / `init-volc` 等登录方式无关
- `volc_sso.identity`：当前火山账号身份事实（`name` / `account_id` / `trn` / `is_root`），并附带账号实名认证状态：
  - `verified`：是否完成实名认证（`true` / `false`）
  - 实名探测失败（网络 / STS / 权限）时 `verified` 省略（与"未探测"语义一致，绝不假报已实名/未实名）
  - 实名是账号级事实，与 profile / project / 登录方式无关；实名是"开通模型 / 开通云产品 / 创建推理接入点"的必要前提
- `ark_api_key`：当前缓存的 ARK API Key
- `ark_api_key.key / status`：当前 Key 掩码值，以及与远端列表对齐后的状态
- `status` 取值为 `active`、`disabled`、`notfound`，远端不可判断时为 `unknown`
- `project_name`：当前生效的 ARK Project Name

敏感字段会做掩码处理，不会直接打印完整 token / secret。

## Project Name 排障

- 如果 `project_name` 不是预期值：
  1. 先确认本次命令由 `--profile` / `ARK_PROFILE` / `default_profile` 选中了哪个 profile
  2. 再看该 profile 的 `project` 字段（`arkcli profile create --project <name>` 或 `arkcli profile project [<name>]` 写入）
  3. 老 profile 没有 `project` 时，再检查 identity store / `.env` 中由 SSO 或 `auth apikey` 留下的兼容值
  4. 都不设置时，火山默认值为 `"default"`
- 想固定 Project：使用 `arkcli profile project [<name>]`，或创建/切换到绑定该 Project 的 profile。只想让单次命令使用另一套上下文时传 `--profile <name>`
- 根命令不再提供 `--project-name`，`ARK_PROJECT_NAME` 也不参与运行时解析
- 老 `arkcli config init --project-name ...` 已废弃, 不应再建议

## 退出登录

```bash
arkcli auth logout
```

该命令会删除本地存储的认证信息，执行前应确认用户确实要清理凭证。
