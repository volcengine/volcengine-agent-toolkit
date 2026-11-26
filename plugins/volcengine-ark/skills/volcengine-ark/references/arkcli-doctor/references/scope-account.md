# `arkcli doctor account`（账号级诊断）

> 这是 [`arkcli-doctor`](../GUIDE.md) 的 **account scope reference**。当用户/Agent 遇到「我账号是不是有权限调 ark / 是不是被冻结 / 余额还够不够 / 子账号缺哪个策略 / VMP 是不是开通 / TOS 开通了没」这类**账号维度**问题时读这里。
>
> **CRITICAL — 开始前 MUST 先用 Read 工具读取**：
> - [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md)（认证闸门、命令选择顺序）
> - [`../GUIDE.md`](../GUIDE.md)（doctor 总入口与路径决策表）

## 它解决什么

`arkcli doctor account` 一次性把「当前账号能不能顺利用 Ark 数据面 + 控制面」答清楚。四段结构：

| 用户场景 | Agent 跑什么 |
|----------|-------------|
| 「我访问 API 告诉我没权限 / ArkFullAccess 是啥」                   | `arkcli doctor account` → 读 `permissions.iam_system_policies` |
| 「我账号是不是被冻结了 / 实名了吗 / 还有钱吗」                    | `arkcli doctor account` → 读 `compliance.realname` / `compliance.balance` |
| 「sub-account 缺 Ark 权限吧」                                    | `arkcli doctor account` → 读 `permissions.iam_system_policies.attached` |
| 「VMP 跨服务授权 / 开通失败怎么办」                                | `arkcli doctor account` → 读 `ecosystem.vmp.type` + `hint` |
| 「TOS 开通了吗 / 生视频回调存不下」                               | `arkcli doctor account` → 读 `ecosystem.tos.activated` |
| 「刚装 arkcli 能连上方舟网关吗」                                  | ❌ **不属于本 scope**——跑 `arkcli doctor`（默认 scope）|
| 「ep-xxx 状态怎么样 / 429 是不是配额压力」                        | ❌ **不属于本 scope**——跑 `arkcli doctor infer-endpoint <id>` |

## 边界：不做什么

- **不 mutate / 不自动修复**：命令只读诊断，未挂 IAM 策略 / VMP 未授权时给跳转链接（`guide_url` 字段），不自动挂策略 / 不自动开通订阅——这两步必须在控制台勾「同意条款」，CLI 不代理。VMP `--auto-bind`（自动建 workspace + 绑 telemetry）走 `doctor infer-endpoint <id> --auto-bind` / `doctor model <name> --auto-bind`，不在本 scope。
- **不越权**：仅用当前 caller 的 AK/SK；IAM `ListAttachedUserPolicies` 服务端强约束只能列出 caller 自己账号的策略；不读平台内部数据；不跨账号横比。
- **不枚举自定义策略**：`permissions.iam_system_policies.attached` 只列 Ark 4 个系统预置策略名的命中项，自定义策略不回显（隐私考量 + agent 输出精简）。`total_attached_count` 字段兜底提示"用户可能有自定义策略"的边缘场景。
- **不替代 `arkcli auth login`**：未登录时 identity 段仍出本地字段，其他段 Reason 写明 `not authenticated`——但不 auto-run 登录。

## 硬约束：与其他 scope 的边界

> [!WARNING]
> **`doctor account` 是账号维度**，跟 `doctor` (CLI 健康) / `doctor infer-endpoint` / `doctor model` / `arkcli usage` **不重叠也不互相兜底**：
>
> - ❌ 用户问「网络通吗 / TLS 握手成功吗」→ 跑 `arkcli doctor`（默认 scope），不是 `doctor account`
> - ❌ 用户问「ep-xxx 报错 429 / 慢 / 挂了」→ 跑 `arkcli doctor infer-endpoint ep-xxx`，不是 `doctor account`
> - ❌ 用户问「某错误码怎么修」→ 跑 `arkcli doctor error <code>`，不是 `doctor account`
> - ❌ 用户问「免费额度还剩多少 / 套餐还剩几次 / 媒资库额度」→ 跑 `arkcli usage balance`（quota 额度），不是 `doctor account`
> - ✅ 用户问「账号权限 / 实名 / **账户余额/账户里还剩多少钱/欠费/冻结** / 云产品开通」→ 跑 `arkcli doctor account`
>
> **『余额』语义消歧**：中文『账号余额 / 账户余额 / 还有多少钱』默认指**账户资金**（充值账户 CNY 余额），走本 scope 的 `compliance.balance`（QueryBalanceAcct）。**只有**用户明说『免费额度 / 套餐额度 / 媒资库额度』这类 **quota 语义** 才走 `arkcli usage balance`。两者数据源完全不同，别混。

## 第一步：跑诊断

```bash
arkcli doctor account                      # 默认，无参
arkcli doctor account --format json        # 完整结构化 JSON（默认）
```

> 命令本身就是**只读体检**，不注册 `--dry-run`；未登录也能跑（identity 段照出 `ok=false + reason`，其他段每个 check Reason 写明 `not authenticated`）。

## 第二步：读输出（4 段）

### ① Identity（本地派生）

从 `auth.ActiveIdentity(cfg)` 派生，纯本地。**未登录 → `ok=false` + `reason`**，其他字段留空；**已登录 → 5 个字段完整**。

| 字段                       | 含义                                       |
|----------------------------|--------------------------------------------|
| `identity.account_id`      | 主账号 ID（root 账号 ID，跟 STS 一致）     |
| `identity.user_id`         | 当前身份的 IAM 子用户 ID（主账号为 root ID）|
| `identity.user_name`       | 当前身份的 IAM 用户名（`ListAttachedUserPolicies` 传参用）|
| `identity.is_root`         | **是否主账号** —— true 表示权限段短路视为已授权 |
| `identity.auth_method`     | `sso` / `aksk` / `apikey` / `sts` / `none` |
| `identity.ok`              | 归一化布尔 == (auth_method != none)        |
| `identity.reason`          | ok=false 时的原因（SSO 过期 / 未配置 / 凭证不可用）|

### ② Compliance（实名 + 余额）

**在线段**，两个独立 check 各自降级：一个失败不阻塞另一个。

| 字段                                | 含义                                                              |
|-------------------------------------|-------------------------------------------------------------------|
| `compliance.realname.verified`      | 是否已实名（**开通 / 部署 / 计费 前置**）                          |
| `compliance.realname.identity_type` | `individual`（个人）/ `enterprise`（企业）/ `""`（未实名或未知）    |
| `compliance.realname.reason`        | 探测失败时的原因                                                  |
| `compliance.balance.available`      | 可用余额原值（字符串，保留精度）；空 = 未拿到                       |
| `compliance.balance.currency`       | 币种（当前硬编码 `CNY`，未来 API 补 Currency 字段后透传）           |
| `compliance.balance.reason`         | 探测失败时的原因                                                  |

**关键点**：
- 用户问「账号被冻结了吗」→ 看 `compliance.realname.verified` + `compliance.balance.available`。realname=false 或 balance ≤ 0 是常见冻结/欠费信号。
- 用户问「余额还剩多少」→ 读 `available`，注意是**字符串**（用户可能拿 `-45.20` 表示欠费），不要 float 解析。
- 用户问「怎么实名」→ 引导 `https://console.volcengine.com/account`（用户手动操作，本 CLI 不注册实名流程）。

### ③ Permissions（IAM 系统预置策略）

**核心：主账号短路**。`identity.is_root=true` 时 CLI 视为已授权，不再调 IAM API（跟 maasfe `useIamPolicyAuthorize` `userId === 0` 逻辑对齐）。

| 字段                                                | 含义                                                               |
|-----------------------------------------------------|--------------------------------------------------------------------|
| `permissions.iam_system_policies.main_account`      | 是否主账号 —— **true 时其余字段的语义降级为"不适用"**            |
| `permissions.iam_system_policies.authorized`        | 归一化布尔 == (main_account \|\| len(attached) > 0)              |
| `permissions.iam_system_policies.attached`          | 已挂载且命中的 Ark 4 预置策略名列表（顺序稳定）                     |
| `permissions.iam_system_policies.missing`           | 未命中的 Ark 预置候选（agent 建议可挂哪些）                          |
| `permissions.iam_system_policies.total_attached_count` | 用户挂的**全部**策略数（含自定义）                                |
| `permissions.iam_system_policies.guide_url`         | 无 Ark 策略时的控制台入口（IAM 系统预置策略页）                     |
| `permissions.iam_system_policies.reason`            | UserName 缺失 / IAM 报错时的原因                                    |
| `permissions.iam_system_policies.note`              | 当 `attached=[]` 且 `total_attached_count>0` 时给的自定义策略提示    |

**Ark 4 个系统预置策略**（按权限从高到低）：
- `ArkFullAccess` —— 完全访问
- `ArkStandardGlobalAccess` —— 标准
- `ArkReadOnlyAccess` —— 只读
- `ArkExperienceAccess` —— 体验

**Agent 消费提示**：
- 一行判断：`main_account || len(attached) > 0` = 有 Ark 权限
- `attached=[]` 且 `total_attached_count>0`：用户可能挂了自定义策略允许 ark 操作，本 check 覆盖不到，**不要断言"没有 Ark 权限"，转而说"未命中 Ark 系统预置策略，可能通过自定义策略授权，请对照 iam:ListAttachedUserPolicies 或控制台策略详情验证"**。
- `attached=[]` 且 `total_attached_count=0`：确认无 Ark 权限，引导用户去 `guide_url` 挂系统预置策略（**不强制跳转 Modal，仅提示**——与 maasfe 一致）。
- `reason` 非空：可能是子账号但 UserName 缺失、IAM API 4xx（授权不足自己看自己）、网络错。按 reason 文案分流。

### ④ Ecosystem（VMP + TOS）

推荐云产品依赖检查。VMP 三段（订阅 / 授权 / 工作区）+ TOS 开通。

#### VMP（`ecosystem.vmp`）

Precheck 短路语义：**第一步不过就不查第二步**，各字段布尔反映的是"检测到的状态"而不是"是否通过"—— agent 看 `type` 字段定夺。

| 字段                              | 含义                                                              |
|-----------------------------------|-------------------------------------------------------------------|
| `ecosystem.vmp.ok`                | 归一化布尔 == (type == "" 即 PrecheckTypeOK)                       |
| `ecosystem.vmp.enabled`           | VMP 订阅是否已开通                                                 |
| `ecosystem.vmp.cross_service_auth`| Ark 跨服务授权（IAM `CheckServiceLinkedRole ServiceName=ark`）      |
| `ecosystem.vmp.workspace_bound`   | ark telemetry 是否已绑定 VMP workspace                             |
| `ecosystem.vmp.workspace_id`      | 已绑定的 workspace UUID（`ok=true` 时非空）                         |
| `ecosystem.vmp.type`              | 状态类型（见下）                                                   |
| `ecosystem.vmp.guide_url`         | 云产品开通页跳转（`LinkOpenMgmtCloudProduct`）                      |
| `ecosystem.vmp.hint`              | 具体引导文案（中文，可直接给用户看）                                |
| `ecosystem.vmp.reason`            | VMP service 不可用 / 网络错时的原因                                 |

**`type` 值域**：
- `""` / `vmp_ok` —— 三段全通过，`ok=true`
- `vmp_not_open` —— 订阅未开通（enabled=false）
- `vmp_slr_missing` —— 订阅通过但跨服务授权缺失（enabled=true, cross_service_auth=false）
- `vmp_workspace_unbound` —— 前两段通过但 workspace 未绑（enabled=true, cross_service_auth=true, workspace_bound=false）

**Agent 消费提示**：
- `type=vmp_not_open` / `vmp_slr_missing` → 用户必须去控制台勾条款，CLI 无法代做，直接给 `guide_url`
- `type=vmp_workspace_unbound` → 引导用户跑 `arkcli doctor infer-endpoint <id> --auto-bind` 或 `arkcli doctor model <name> --auto-bind`（这两个 scope 支持自动绑定；`doctor account` 本 scope 不做 mutate）

#### TOS（`ecosystem.tos`）

`GetAccountStatus` 一次拿开通状态。与 maasfe 云产品开通管理页 TOS 状态判定同源。

| 字段                        | 含义                                                                                |
|-----------------------------|-------------------------------------------------------------------------------------|
| `ecosystem.tos.status`      | TOS 原状态值 —— `Activated` / `NonActivated` / `Stopping` / `Closed` / `Terminate` |
| `ecosystem.tos.activated`   | 归一化布尔 == (status == "Activated")                                               |
| `ecosystem.tos.guide_url`   | 未开通时的控制台入口（云产品开通页）                                                 |
| `ecosystem.tos.reason`      | 探测失败时的原因                                                                    |

**Agent 消费提示**：
- `activated=true` → 一切 OK
- `activated=false` + `status=NonActivated` → 未开通，用 `guide_url` 引导用户开通
- `activated=false` + `status=Stopping|Closed|Terminate` → 欠费 / 已销户，**不同于未开通**，需要用户去处理账户状态（引导控制台账户中心而不是开通页）
- `activated=false` + `status=""` + `reason` 非空 → 查询失败，可能是权限 / 网络，按 reason 文案分流

## 常见 Finding → 修复路径

| Finding                                              | 严重度 | 修复方向                                                                              |
|------------------------------------------------------|--------|---------------------------------------------------------------------------------------|
| `identity.ok=false`                                  | fail   | 未登录 / SSO 过期 → [`arkcli-auth`](../../arkcli-auth/GUIDE.md) 走 `arkcli auth login` |
| `compliance.realname.verified=false`                 | fail   | 未实名，控制台完成实名后重跑                                                            |
| `compliance.balance.available` 为负 / 明显不足          | warn   | 欠费或余额不足，控制台充值                                                              |
| `permissions.iam_system_policies.authorized=false` + `total_attached_count=0` | fail | 子账号无任何 Ark 策略，引导 `guide_url`（IAM 系统预置策略页）挂 `ArkFullAccess` 或最小 `ArkReadOnlyAccess` |
| `permissions.iam_system_policies.authorized=false` + `note` 非空 | warn | 用户挂了自定义策略但本 check 覆盖不到，建议对照 IAM 详情验证自定义策略是否含 ark 操作     |
| `ecosystem.vmp.type=vmp_not_open`                    | fail   | 用户去 `guide_url` 开通 VMP 订阅（勾同意条款）                                          |
| `ecosystem.vmp.type=vmp_slr_missing`                 | fail   | 用户去 `guide_url` 授权跨服务访问（VMP SLR）                                          |
| `ecosystem.vmp.type=vmp_workspace_unbound`           | warn   | 加 `--auto-bind` 走 `doctor infer-endpoint / model`；或控制台手动绑 workspace          |
| `ecosystem.tos.status=NonActivated`                  | fail   | 生视频 / 存储回调依赖 TOS，用户去 `guide_url` 开通                                     |
| `ecosystem.tos.status=Stopping/Closed/Terminate`     | fail   | 欠费或销户，控制台账户中心处理；开通页也无法直接恢复                                     |

## 给用户看的话术

1. **一句话结论**：账号是否 ready ——「身份 OK + 实名 + 余额充足 + Ark 权限 + VMP 三段 + TOS」6 个"是/否"。
2. **关键问题**：摘 fail 级的 finding，一次说一个。多个 fail 同时命中时按 `identity → compliance → permissions → ecosystem.vmp → ecosystem.tos` 顺序引导用户修（前面不通谈后面没意义：未登录谈实名没意义；无 Ark 权限谈 VMP 精度没意义）。
3. **修复动作**：CLI 层能修的只有 `doctor infer-endpoint/model --auto-bind` 那一个"自动绑 workspace"场景；其余（实名 / 挂 IAM 策略 / 开通 VMP / TOS）都必须去控制台。**给用户看 URL 前先说明控制台会做什么，让用户预期知情**。
4. **下一步**：修完让用户重跑 `arkcli doctor account` 确认闭环；6 段全绿再引导跑 `doctor model` / `doctor infer-endpoint` 深入业务侧。

## 安全与边界

- **完全只读**：不 mutate 任何资源。VMP `--auto-bind` 走另外两个 scope，本 scope 不引入 mutate 分支。
- **越权边界**：所有 API 都用当前 caller AK/SK；IAM `ListAttachedUserPolicies` 只能查 caller 自己账号；QueryBalanceAcct / GetAccountStatus / GetVerifyInfo 都是 body 空 + STS 身份推断，天然限定 caller 账号。
- **敏感字段脱敏**：AK/SK / SSO token / apikey 明文不进 JSON 输出。IAM 自定义策略名**不枚举**（可能包含内部命名，隐私考量）。
- **不 fail-fast**：identity 段未登录时命令仍出，其他段每个 check Reason 写明原因——onboarding 场景就是要在没登录时也能拿到诊断。
- **主账号短路 IAM**：主账号（`is_root=true`）不发 `ListAttachedUserPolicies` 请求，与 maasfe UX 一致 + 避免 IAM 报错。

## 何时 _不_ 用本 reference

- 想看**装 / 网络 / 时钟 / apikey 校验** → [`scope-cli.md`](scope-cli.md)（`arkcli doctor` 默认 scope）
- 想看**单接入点**状态 / 用量 / 配额 → [`scope-infer-endpoint.md`](scope-infer-endpoint.md)
- 想看**跨接入点的模型整体**用量 / 配额 → [`scope-model.md`](scope-model.md)
- 想查**某个错误码含义** → `doctor error <code>` → [`error-codes.md`](error-codes.md)
- 想**登录 / 切 profile / 生成 apikey** → [`../../arkcli-auth/GUIDE.md`](../../arkcli-auth/GUIDE.md)

## 参考

- [`../GUIDE.md`](../GUIDE.md) — 总入口与路径决策
- [`scope-cli.md`](scope-cli.md) — CLI 健康检查（默认 scope）
- [`scope-infer-endpoint.md`](scope-infer-endpoint.md) — 单接入点诊断
- [`scope-model.md`](scope-model.md) — 单模型诊断
- [`../../arkcli-auth/GUIDE.md`](../../arkcli-auth/GUIDE.md) — 登录 / 认证管理
- [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md) — 共享执行协议
