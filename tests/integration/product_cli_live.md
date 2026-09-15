# ve 产品 CLI 真实凭证测试

测试入口：[verify_product_clis_live.py](verify_product_clis_live.py)。直接运行时会调用真实云端；
普通 `python3 -m unittest discover -s tests -v` 不执行这组集成测试。

## 用例与通过条件

| Case | 真实调用 | 断言 |
| --- | --- | --- |
| VE-AUTH | `ve sts GetCallerIdentity` | 返回有效身份，无 API 错误 |
| TOS-LIST | `ve tosutil ls -conf=<config>` | 列表包含指定桶，返回数量与解析行数一致 |
| TOS-STAT | `ve tosutil stat tos://<bucket> -conf=<config>` | 桶名、地域与输入一致，返回存储类型 |
| ARK-AUTH | `ve arkcli auth whoami --format json` | 当前身份已认证，账号与 VE-AUTH 一致 |
| ARK-SEARCH | `ve arkcli models search <keyword> --size 3 --refresh-cache --format json` | 真实检索返回 1–3 个模型，取得名称和版本 |
| ARK-GET | `ve arkcli models get <live-model-id> --format json` | 用上一项返回的名称和版本查询，详情与检索结果一致 |

只有 6 项全部通过才返回退出码 0。命令失败、认证失败、超时、响应不符合断言均返回 1；
依赖失败导致后续项未执行时也不能通过。测试仅查询现有资源，不上传、删除、部署或发起推理。

## 前置条件

- 从目标 CLI 源码构建新版 `ve`，先执行 `ve version`，确认 **版本大于等于 `1.1.9`**
  （稳定版 `1.1.9` 起）；版本不满足或无法确认时先升级，再验证 `ve tosutil version` 和
  `ve arkcli --version`。代理命令在旧版本中可见也不能替代该版本要求。
- 使用当前或用户明确指定的账号；`ve sts GetCallerIdentity` 必须成功。
- 通过 `volcengine-find-skills` 获取 `volcengine-tosutil`，按照其配置说明准备有效的 tosutil
  配置文件。使用临时 STS 时必须同时提供 AK、SK、session token，文件权限限制为 `0600`。
- 准备同一地域的现有测试桶，并具有列桶与读取桶元信息的权限。桶名与地域由运行参数传入。
- 按官方 `arkcli-shared`、`arkcli-auth` 完成 Ark 认证。自动化环境已有合法 STS 时可按
  官方 `init-volc` 指引初始化；角色 ID 不能当作 IAM 用户 ID。模型查询使用控制面凭证，
  不要求通过额外推理调用验证 API Key。
- 阅读官方 `arkcli-models` 及 search/get reference。需要单次指定 Ark profile 时传
  `--ark-profile`；测试不会切换默认 profile。
- 账号一致性使用 `auth whoami` 的当前身份，不用 `auth status` 中可能来自旧缓存的
  `volc_sso.identity` 代替。模型关键词应指向有详情接口的基础模型；滚动别名没有详情时，
  `ARK-GET` 会失败，不能仅凭 search 成功把整组测试标记为通过。

## 执行

下列值均为占位符，执行前替换为已授权环境中的真实路径与目标：

```text
python3 tests/integration/verify_product_clis_live.py \
  --ve <new-ve-binary> \
  --agent-id <actual-agent-id> \
  --skill-name <current-volcengine-skill> \
  --tos-config <protected-tosutil-config> \
  --tos-bucket <existing-bucket> \
  --tos-region <bucket-region> \
  --keyword doubao \
  --report .local/product-cli-live-result.json
```

`ve` 优先使用 PATH 中的子 CLI；需要验证特定托管版本时，先核对二进制的实际解析来源。
测试不自动升级子 CLI，也不读取或打印凭证文件。Agent 根据实际运行环境和当前 skill
提供 `--agent-id` 与 `--skill-name`；测试统一传入三项 `VE_*` 调用标识。对于 `ve arkcli`，
由 `ve` 转换变量，不额外传入 `ARKCLI_CALLER_TYPE`、`ARKCLI_CALLER_NAME`、`ARKCLI_SKILL_NAME`
或 `ARKCLI_NO_UPDATE_NOTIFIER`。其他产品设置和凭证环境保持原样，输出格式和参数仍由子 CLI 解释。

报告仅记录脱敏命令、退出码、耗时与断言证据，不保存原始 stdout/stderr、账号 ID、桶名、
凭证或本机绝对路径。失败时应在本机按对应产品 skill 诊断，不把认证配置或原始响应提交进仓库。
测试结束后由创建临时凭证配置的调用方删除该文件；不要删除用户原有配置或登出共享登录态。
