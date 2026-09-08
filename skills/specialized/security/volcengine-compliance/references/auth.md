# 鉴权与前置条件（Auth）

本技能通过 `ve config <Action>` 调用火山引擎配置审计接口，依赖调用方**已完成 `ve` 鉴权**。
完整的 `ve login` 设备码登录流程由 `volcengine-cli` 技能统一维护，**这里不重复**。

## 前置检查清单

跑 `scripts/compliance.py` 前确认：

1. **`ve` 已安装**：`npm i -g @volcengine/cli`。
2. **已鉴权**（二选一）：`ve login` 交互登录；或设 `VOLCENGINE_ACCESS_KEY` /
   `VOLCENGINE_SECRET_KEY`（+ 可选 `VOLCENGINE_SESSION_TOKEN`）。
3. **权限**：
   - 只读子命令（recommend / overview）需配置审计读权限；
   - 写子命令（apply / --enable-recorder）需配置审计写权限；账号组场景需目标账号组管理员。
4. **配置记录器（recorder）**：部署合规包前需启用；未启用时 `apply --enable-recorder` 可
   在确认后一并启用（见 apply.md）。

## 登录 / 会话过期

- 若 `ve config` 报 `failed to refresh session token. Please run 've login'...`（或类似
  会话过期文案），**不要**让用户自己去终端跑 `ve login`，也**不要**盲目重试。
- 按 **`volcengine-cli` 技能**的 Console Login（`scripts/ve_login_remote.sh` 设备码流程）
  帮用户完成登录，只把登录链接交给用户（老版本 ve 才需要用户回传授权码）。本技能不复制该脚本。
- **profile 一致性**：若对话中早前固定过某 profile，重新登录必须打到同一 profile，否则会
  刷新 `default`、弄坏原 profile 并污染默认账号上下文。

## 单账号 vs 账号组

- **单账号**：所有子命令默认作用于当前鉴权账号（`X-Top-Account-Id`）。
- **账号组**：recommend / overview / 部署都有账号组版 Action（`...AccountGroup...`），需
  `AccountGroupId`；owner / delegated admin 可作用于整组，普通成员只能自身账号。无权限
  返回 `403 AccessDenied`。

## 安全边界

- 产物与对外汇报中**不得**出现 AK / SK / Authorization / 会话 token。
- 资源 ID 对外脱敏保留固定前缀、抽象随机段（如 `i-<id>`、`cp-<id>`、`ag-<id>`）。
- 写操作（apply / enable-recorder）执行前必须向用户复述影响并取得明确同意，再加 `--confirm`。
