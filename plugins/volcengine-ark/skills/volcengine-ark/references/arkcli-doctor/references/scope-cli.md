# `arkcli doctor`（CLI 健康检查，默认 scope）

> 这是 [`arkcli-doctor`](../GUIDE.md) 的 **CLI scope reference**。当用户/Agent 遇到「刚装 arkcli 能用吗 / 命令突然报错跑不通 / 联通性异常 / 未登录跑不了 / 版本旧不旧」这类**环境/客户端本身**问题时读这里。
>
> **CRITICAL — 开始前 MUST 先用 Read 工具读取**：
> - [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md)（认证闸门、命令选择顺序）
> - [`../GUIDE.md`](../GUIDE.md)（doctor 总入口与路径决策表）

## 它解决什么

`arkcli doctor`（无参调用）一次性把「这台机器上的 arkcli 现在能不能用」答清楚——本地二进制版本、能不能拉到 registry 的最新版、能不能解析并握手到 Ark 数据面、系统时钟对不对、当前 profile 有没有可用凭证，以及**本地存的 apikey 服务端仍是否可用 + profile 是否过期**（configuration 段会主动拉服务端最新 apikey 列表跟本地对比）。

| 用户场景 | Agent 跑什么 |
|----------|-------------|
| 「刚装 arkcli 能用吗」                                    | `arkcli doctor`（无参） |
| 「命令突然报错跑不通」                                    | 同上——先做环境四段体检（installation / connectivity / auth / configuration） |
| 「显示未登录 / InvalidTimestamp」        | 同上（时钟偏差在 connectivity 段、凭证状态在 auth 段） |
| 「网络能通吗 / 走不走代理有关系吗」                        | 同上（DNS/TCP/TLS 都在 connectivity 段） |
| 「装的是不是最新版」                                      | 同上（installation.latest_version） |
| 「我的 apikey 还有效吗 / 服务端删了没 / 套餐过期了没」     | 同上（configuration 段发 API 拉服务端 apikey 列表对比本地） |
| 「账号权限 / 模型开通 / 接入点状态 / 用量」               | ❌ **不属于本 scope**——跳到 `doctor account` / `doctor model` / `doctor infer-endpoint` |

## 边界：不做什么

- **不查业务侧状态**（账号权限 / 模型开通 / 接入点存活 / 用量 / 配额）——这些走同族其他 scope。
- **不改任何配置**——只读体检；发现未登录只给 hint（`arkcli auth login`），不替按。
- **不下载升级**——`latest_version.up_to_date=false` 只提示，安装动作由用户执行 `npm install -g @volcengine/ark-cli`。
- **不查代理 / 网卡明细**——只做端到端 DNS+TCP+TLS 三级探测，具体网络拓扑排查交给用户/运维。

## 硬约束：connectivity ≠ auth，不许混

> [!WARNING]
> **网络联通性和登录状态是两件独立的事，不许互推**。这是本 skill 最容易被 agent 误伤的点，MUST 严格遵守：
>
> - `connectivity.*` 只回答「DNS 解析成没成 / TCP+TLS 握手到没到目标网关 / 服务端时钟对得上不」——**跟当前 profile 有没有凭证、AK/SK 对不对、apikey 服务端是否 active 完全无关**。
> - `auth.*` 才是「有没有登录 / 什么方式登录 / 凭证在不在」，纯本地判 `~/.arkcli/config.yaml` + identity store，不发任何 API 调用。
> - `configuration.api_key` 才是「服务端是否仍认可这个 key」，走 `ListApiKeys` 在线校验。
>
> 三段独立、并行、都会出结论——所以只要用户问「网络通吗 / 能不能连上方舟」，答案 MUST 只从 `connectivity` 段读，一个字都不许提「你没登录」「凭证过期」这类话。
>
> **严禁的错误路径（agent 曾经踩过的坑）**：
>
> - ❌ 用户问「网络通吗」→ agent 跑 `curl -o /dev/null -w "%{http_code}" https://ark.cn-beijing.volces.com` → 拿到 `401` → 结论「网络可达但未登录」
>
>   → 这是**双重错误**：
>     1. 裸 curl 不带 Authorization 头，网关本来就会返 401——`401` 只说明「TLS 握手成了 + 网关识别我是无鉴权请求」，跟本机 arkcli 到底有没有登录**完全无关**（本机可能是 SSO / AK/SK / apikey 齐全的登录态）
>     2. 用户问的是网络，你答的是登录——scope 错了
> - ❌ 用户问「网络通吗」→ agent 跑 `curl` 判 HTTP 状态码 → 任何形式的『所以你需要 `arkcli auth login`』提示
>
>   → `arkcli auth login` 是 auth 段的修复动作，跟 connectivity 段的结论没有因果关系。
>
> **唯一正确姿势**：`arkcli doctor` 无参跑一次，只报 `connectivity.dns.ok` / `connectivity.tcp.ok` / `connectivity.clock_skew.ok` 三个字段的结论。用户如果**另外**问了登录状态，再从 `auth.*` 段读一次；两段不许串。
>
> **如果 agent 只想快速判「网络通不通」而不想跑完整 doctor**：也 MUST 走 `arkcli doctor` 而不是 curl；命令是只读的，未登录也能跑（onboarding 场景专用），比裸 curl 快不了多少却语义正确。真要 curl 探测，只允许看「TCP+TLS 是否握手成功」（e.g. `curl -o /dev/null -w "%{http_connect}\n%{http_code}\n" --max-time 5 https://ark.cn-beijing.volces.com`），**HTTP 状态码不许拿来解读登录状态**。

## 第一步：跑诊断

```bash
arkcli doctor                              # 默认，无参
arkcli doctor --format json                # 完整结构化 JSON（默认）
arkcli doctor --debug 2>&1 | head -20      # 网络时序看得清
```

> 命令本身就是**只读体检**，不注册 `--dry-run`，不需要登录也能跑（onboarding 场景专用）。当前 profile 未配置时，`configuration` 段照出 `credentials_present=false` + 原因，不会 fail。

## 第二步：读输出（4 段）

### ① Installation（本地二进制）

| 字段                        | 看什么                          | 失败/异常时                                                   |
|-----------------------------|--------------------------------|--------------------------------------------------------------|
| `installation.cli_version`  | 本地二进制版本（build 时注入）  | dev build 会显示 `dev`，无需担心                             |
| `installation.latest_version.available` | 是否成功拉到 npm registry | `false` → 看 `reason`：dev build 会 skip；网络失败给具体错误 |
| `installation.latest_version.up_to_date` | 当前版本 vs registry 最新 **仅在 `available=true` 时存在** | 缺失 → 说明 `available=false`，**不要**据此推断"要升级" |
| `installation.path`         | 二进制绝对路径                  | 排查"跑的是哪份 binary"（PATH 覆盖 / 多版本共存）             |

**latest_version.up_to_date=false → 修复**：
```bash
npm install -g @volcengine/ark-cli
```

### ② Connectivity（端到端网络）

以 active profile 的 `BaseURL` 派生 host（未配置时兜底 `https://ark.cn-beijing.volces.com/api/v3`）依次探测。**前一步失败时后一步自动跳过并标 `reason: "skipped: <前置>"`**——排查时按 DNS → TCP → clock skew 顺序看。

| 字段                          | 看什么                                                                                | 失败时                                                                              |
|-------------------------------|--------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| `connectivity.endpoint`       | 探测**派生源**（完整 URL 回显当前 profile 的 base_url）                             | —                                                                                  |
| `connectivity.probe_target`   | **实际探测目标**（`host:port`，如 `ark.cn-beijing.volces.com:443`）——注意 probe 只到 TLS 握手层，`/api/v3` 路径**不会**被访问 | DNS 前置失败时缺失 |
| `connectivity.dns.ok`         | DNS 解析                                                                             | `false` → 网络 / DNS 服务器 / VPN / hosts 覆盖问题                                 |
| `connectivity.dns.latency_ms` | 解析耗时                                                                             | 200ms+ 表示 DNS 慢，考虑换 resolver                                                |
| `connectivity.tcp.ok`         | TCP 建连 + TLS 握手一次到位                                                          | `false` → firewall / proxy MITM / 网关不可达 / TLS 版本不匹配                     |
| `connectivity.tcp.tls_version`| 协商到的 TLS 版本（`TLS 1.3` / `TLS 1.2`）                                          | 低于 1.2 → 客户端 / 中间设备强制降级，通常是 MITM 代理                            |
| `connectivity.clock_skew.ok`  | **系统时钟偏差是否在 5s 阈值内**                                                     | `false` → 见下方专段                                                              |
| `connectivity.clock_skew.direction` | 偏差方向：`in_sync`（阈值内）/ `local_ahead`（本地快）/ `local_behind`（本地慢） | agent 建议 NTP 命令时**看这个字段**，不要靠 `offset_ms` 正负号自己反推           |

### ③ Clock skew（时钟偏差专段）

**为什么单独讲**：Volc V4 签名（AK/SK 请求）在服务端有严格时间戳窗口校验。本地时钟偏差过大会导致：

- AK/SK 签名请求全部失败：报 `InvalidTimestamp` / `SignatureDoesNotMatch`
- JWT token 判活异常：SSO IDToken 的 `exp` claim 被本地时钟当作过期强制重登
- TLS 握手可能失败：极端偏差下证书 `notBefore/notAfter` 校验挂

这是虚拟机 / 长时间挂起的笔记本 / dev container 的高频"莫名其妙"故障根因。

**修复**（`clock_skew.hint` 已按当前 OS 给出对应命令）：

| 系统    | 修复命令                                                                              |
|---------|--------------------------------------------------------------------------------------|
| macOS   | `sudo sntp -sS time.apple.com`                                                       |
| Linux   | `sudo chronyd -q 'server pool.ntp.org iburst'` 或 `sudo ntpdate pool.ntp.org`        |
| Windows | 以管理员身份运行 PowerShell：`w32tm /resync`                                         |

修复后重跑 `arkcli doctor` 确认 `clock_skew.ok=true`。

### ④ Auth（登录状态，本地）

**这一段纯本地判断**——从 `~/.arkcli/config.yaml` + `~/.arkcli/identity_store/` 派生，不发任何 API 调用。未登录场景也会正常输出。

| 字段                       | 看什么                                       |
|----------------------------|---------------------------------------------|
| `auth.logged_in`           | 是否持有可用凭证（等价于 `auth_method != "none"`） |
| `auth.auth_method`         | 认证类型：`sso` / `aksk` / `apikey` / `sts` / `none`（**系统规范**，与 `core.CliConfig.AuthMethod()` 同源，跨命令一致） |
| `auth.credential_state`    | ⚠️ **CLI scope 独有字段**（不是 arkcli 全局规范）：`active`（有凭证）/ `expired`（SSO 过期）/ `absent`（从未登录 / 已 logout）/ `unknown`（cfg 加载失败）—— 用于避免 agent 靠 reason 字符串推子状态。**不要**拿到别的 arkcli 命令的输出里做联合查询。 |
| `auth.reason`              | `logged_in=false` 时的原因                    |

**按 credential_state 修复**：

- `active` → 无需处理
- `expired` → SSO token 过期，跳 [`arkcli-auth`](../../arkcli-auth/GUIDE.md) 走 `arkcli auth login` 刷新
- `absent` → 从未登录或已 logout，同样跳 `arkcli-auth`
- `unknown` → cfg 加载失败（`reason` 里给具体原因），先解决配置文件问题再重试

### ⑤ Configuration（profile 校验，**在线**）

**这一段发 API 调用**——拉服务端最新 apikey 列表跟本地 profile 存的对比，同时读 `profile.ExpiresAt` 判套餐/席位过期。未登录/无 invoker 时降级为 `verified=false`，不阻塞其他段。

| 字段                              | 看什么                                       |
|-----------------------------------|---------------------------------------------|
| `configuration.profile`           | 当前 active profile 名（Config 未加载时为空串） |
| `configuration.profile_expires_at`| 套餐 / 席位到期时间戳（Unix 秒；`0` = 未知/永不过期） |
| `configuration.profile_expired`   | profile 是否已过期（`ExpiresAt > 0 && now > ExpiresAt`） |
| `configuration.api_key`           | 当前 apikey 的**服务端校验**结果（未验证时字段缺失） |
| `configuration.api_key.key_masked`| 打码后的 apikey（如 `ark-****7364`；明文不进 JSON） |
| `configuration.api_key.status`    | `active` / `disabled` / `notfound` / `unknown`（与 `arkcli auth status` 归一化后同款） |
| `configuration.api_key.refresh_hint` | 非 active 时的刷新命令（`arkcli profile apikey refresh`） |
| `configuration.verified`          | 是否成功完成在线校验                          |
| `configuration.reason`            | `verified=false` 时的具体原因                 |

**verified=false 的常见原因**（一律不阻塞其他段）：

- `skipped: not logged in` —— 未登录场景（auth.logged_in=false），已经在 auth 段告诉用户要 login
- `skipped: invoker unavailable: <原始 err>` —— cfg 加载 OK 但 ArkInvoker 构造失败，罕见
- `no api key to validate (auth_method=sso)` —— 登录方式非 apikey 且 profile 里没缓存 apikey
- `describe status: <原始 err>` —— 打到 ListApiKeys 失败（网络/权限）

**按 api_key.status 修复**：

- `active` → 无需处理
- `disabled` → 本地 key 在服务端已被停用 → `arkcli profile apikey refresh` 拉最新 active key
- `notfound` → 本地 key 在服务端已删除（key rotation / user 手动删）→ 同上 `arkcli profile apikey refresh`；仍不行走 `arkcli auth apikey` 重选
- `unknown` → 服务端匹配上但状态字段异常，先 `arkcli auth status` 看详情

**按 profile_expired 修复**：

- `false` → 无需处理
- `true` + Agent/Coding Plan 用户 → 引导控制台续订套餐
- `true` + platform 用户 → 一般不会命中（platform profile 无 ExpiresAt），检查 profile 是否被误改

> **敏感字段脱敏**：`arkcli doctor` 输出**不会**回显 AK/SK / token 明文；apikey 只出 masked（`ark-****xxxx`）。如果用户拿输出问"怎么这个字段没出来"，就是**因为脱敏，不是 bug**。

## 常见 Finding → 修复路径

| Finding                                                | 严重度 | 修复方向                                                                              |
|--------------------------------------------------------|--------|---------------------------------------------------------------------------------------|
| `installation.latest_version.up_to_date=false`         | info   | `npm install -g @volcengine/ark-cli` 升级；旧版可能缺失近期修复                       |
| `installation.latest_version.available=false`（非 dev build）| warn   | 网络到 npm registry 不通；影响升级检查但不影响 CLI 使用                              |
| `connectivity.dns.ok=false`                            | fail   | DNS 挂：排查 `/etc/resolv.conf`、VPN、hosts 覆盖；换 8.8.8.8 试试                    |
| `connectivity.tcp.ok=false`（DNS 通）                  | fail   | TCP/TLS 挂：查 firewall、proxy 是否 MITM、公司网关是否阻断 volces.com                 |
| `connectivity.tcp.tls_version` < TLS 1.2               | warn   | 中间设备做 TLS 降级；找运维检查企业出口代理                                           |
| `connectivity.clock_skew.ok=false`                     | fail   | 按 `hint` 里的平台命令同步 NTP；不修则 AK/SK 请求会持续报签名类错误                   |
| `auth.logged_in=false`（credential_state=expired）     | fail   | SSO 过期，跳 [`arkcli-auth`](../../arkcli-auth/GUIDE.md) 走 `arkcli auth login` 刷新  |
| `auth.logged_in=false`（credential_state=absent）      | fail   | 从未登录 / 已 logout，跳 `arkcli-auth` 登录                                          |
| `configuration.api_key.status=disabled`                | fail   | 本地 apikey 被停用 → `arkcli profile apikey refresh`                                    |
| `configuration.api_key.status=notfound`                | fail   | 本地 apikey 服务端已删 → `arkcli profile apikey refresh`；仍不行 `arkcli auth apikey` 重选 |
| `configuration.profile_expired=true`                   | fail   | 套餐/席位到期，控制台续订                                                             |
| `configuration.verified=false` + `reason=describe status: <err>` | warn   | 服务端 ListApiKeys 打不通（网络/权限），一般是临时故障，重试即可                     |

## 给用户看的话术

1. **一句话结论**：CLI 是否可用 —— 拆成"网络通了 + 时钟正常 + 已登录 + apikey 服务端仍有效"四个"是/否"。
2. **关键问题**：摘 fail 级的 finding，一次说一个。多个 fail 同时命中时按 `connectivity → auth → configuration → installation` 顺序引导用户修（前面 block 掉后面：网络挂了谈登录没意义；未登录谈 apikey 校验没意义）。
3. **修复命令**：**先给用户看、等确认**再让用户执行。特别是 `sudo` 类命令必须让用户明确同意；`arkcli profile apikey refresh` 也一样先展示等确认。
4. **下一步**：修完让用户重跑 `arkcli doctor` 确认闭环；确认没问题后再引导他们跑真实业务命令（`doctor account` / `doctor model` / 等）。

## 安全与边界

- **本地为主，在线校验只调 apikey 列表**：installation / connectivity / auth 三段全本地；configuration 段发一次 `ListApiKeys` 拉服务端最新列表。不消耗推理 token，不发业务请求。
- **越权边界**：DNS / TCP / TLS / HEAD 都是端到端标准协议探测；apikey 校验用当前 profile 已有的凭证签名，只读 caller 自己的 key 池，不跨账号。
- **敏感字段脱敏**：AK/SK / SSO token 明文不进 JSON 输出；apikey 只出 masked（`ark-****xxxx`）。
- **不 fail-fast**：未配置时命令仍能出结果——onboarding 场景就是要在没登录时也能拿到诊断。

## 何时 _不_ 用本 reference

- 想看**账号/模型/接入点**业务侧状态 → `doctor account` / `doctor model <name>` / `doctor infer-endpoint <ep-id>`（各自的 scope reference）
- 想**登录 / 切 profile / 查身份** → [`../../arkcli-auth/GUIDE.md`](../../arkcli-auth/GUIDE.md) / [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md)
- 想**装 / 升级 CLI** → 直接 `npm install -g @volcengine/ark-cli`（不需要 doctor）
- 想查**某个错误码含义** → `doctor error <code>`（→ [`error-codes.md`](error-codes.md)）

## 参考

- [`../GUIDE.md`](../GUIDE.md) — 总入口与路径决策
- [`scope-infer-endpoint.md`](scope-infer-endpoint.md) — 单接入点诊断
- [`scope-model.md`](scope-model.md) — 单模型诊断
- [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md) — 共享执行协议
- [`../../arkcli-auth/GUIDE.md`](../../arkcli-auth/GUIDE.md) — 登录 / 认证管理
