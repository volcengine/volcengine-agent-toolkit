# plans personal rotate-apikey

> **前置条件：** 先阅读 [`../../arkcli-shared/GUIDE.md`](../../arkcli-shared/GUIDE.md) 了解认证、全局参数和安全规则。

> **⚠️ 写操作 / 毁坏性：** 调用成功后**原 APIKey 立即失效**，需要立即替换接入该 API Key 的模型 / Harness 配置以避免服务中断。默认走 [Y/N] 二次确认；脚本场景可加 `--yes` 跳过。

轮换 Agent Plan **个人版** 的专属 APIKey。一次调用先查 `ListApiKeys` (Filter.Scene=`RealAgentPlanPersonal`)，仅提交一次 `UpdateApiKey {Id, Regen:true}`，再读 `GetRawApiKey` 并最多三次只读 `ListApiKeys` 核验同一 Id 为 Active；全部成功才返回新明文。

## 排查错误时先区分发生阶段

用户只要求解释或排查报错时，先保存原命令、时间、Profile/身份与错误；当前只读检查、后续写操作的拒绝、历史报错分开记录。不要为复现自动新建/切换 Profile、refresh 本地 Key 库存、导出明文或轮换 Key。按 [Key 查询契约](../../arkcli-auth/references/api-key-query.md)核对当前订阅与 `Filter.Scene=RealAgentPlanPersonal` 的完整元数据；查询失败保留未知。

| 实际证据 | 可以得出的结论 | 不能据此推断 / 下一步 |
| --- | --- | --- |
| `no Agent Plan 个人版 API Key found` | 本次 Scene 查询响应、Result 或 Items 为空，尚未进入本命令的 Update | 不是“没买套餐”的充分证据；CLI 购买 hint 是通用提示。当前查到订阅或 Key 也不能解释历史为空，需核对当时身份、时间与请求范围 |
| `plan_agreement_identity_required` / `plan_agreement_status_unavailable` | 本次受保护操作在身份/协议状态门禁被拒或未能核验 | 不能倒推原 NoKeyFound 的根因，不能断言未签协议或签后一定补配 Key；依宿主恢复身份，不换 Action 绕过 |
| `UpdateApiKey` 超时或返回错误 | 轮换未拿到成功回执；具体是否落地须看服务端证据 | 不保证原 Key 有效，也不自动重放 Regen；先核对同一 Id 的实际结果 |
| Update 已成功，但 `GetRawApiKey` 或后置 Active 校验失败 | 写入已经发生，后续读取或状态核验失败 | 整条命令非零不等于“没轮换”；不能承诺旧 Key 仍可用或无中断，只做获准的只读核查 |
| 返回 `status=success`、同一 `key_id` 与新明文 | 本次轮换、读取及管理状态校验成功 | `Active` 不等于外部客户端已换 Key/业务不中断；凭证仅交给获准的安全落点，另核对客户端是否已加载 |

交付时先给原错误的已知语义，再列当前核验结果、后续操作结果和仍待确认的根因。原问题不能由新报错替换；没有独立证据时不说“已定位根因”“旧 Key 仍可用”或“已恢复”。轮换内部只写一次 `UpdateApiKey(Regen=true)`，随后最多三次 `ListApiKeys` 是只读状态核验，不是允许 Agent 重跑轮换命令。

## 命令

```bash
# 交互式：会先弹 [Y/N] 确认
arkcli plans personal rotate-apikey

# 非交互（脚本 / CI）：跳过确认
arkcli plans personal rotate-apikey --yes
```

## 参数

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `--yes` | 否 | bool | 跳过 [Y/N] 二次确认（脚本/CI 友好） |

## 返回值

成功：
```json
{
  "status": "success",
  "key_id": 114788,
  "api_key": "sk-rotated-new-secret"
}
```

`api_key` 是**新明文**，跟 frontend Modal 弹出的 "新 APIKey" 同一份。务必立即保存。

## 失败语义

| 场景 | exit code | 输出 |
|---|---|---|
| 用户 [N] / EOF / 空回车取消 | 1（ExitGeneral） | `{"ok":false,"error":{"type":"cancelled","message":"operation cancelled"}}` |
| 本次个人 Agent Plan Scene 查询没有返回 Key（response / Result / Items 为空） | 2（ExitValidation） | `{"ok":false,"error":{"type":"validation","message":"no Agent Plan 个人版 API Key found","hint":"Subscribe Agent Plan 个人版 first via \`arkcli plans buy --plan agent-plan ...\`"}}` |
| transport / 服务端错 | 1（ExitGeneral） | 普通 error 上抛 |

## 二次确认文案

CLI 输出（stderr）：
```
确认更新专属 APIKey?
更新后原 APIKey 将立即失效，请及时替换接入该 API Key 的模型及 Harness 配置，以避免服务中断。
继续? [y/N]:
```

输入 `y` / `Y` 才放行；其它（含空回车 / EOF / 任何字符）都按取消。

## 注意事项

- 这条命令仅影响 Agent Plan **个人版** scoped APIKey（`Filter.Scene=RealAgentPlanPersonal`），**不会影响**普通 Platform / Coding 池的 APIKey
- CLI 使用本次 Scene 列表的第一项；源码没有据此保证服务端最多只有一把。排查时保留真实记录，不凭普通池或本地库存推断专属池。
- 跟 `arkcli auth` 持久化的 SSO STS / IDToken 无关 —— 那是 CLI 自己的鉴权链路，APIKey 是给数据面 SDK 用的
- `ErrNoAgentPlanPersonalKey` 只对应本次 Scene 查询没有 Key；查询 transport 错另行返回。订阅资格与 Key 是否存在分开核验，不能把购买 hint 当成未订阅的证据。

## 参考

- [arkcli-plans](../GUIDE.md) -- skill 概览
- [`plans get`](arkcli-plans-get.md) -- 先确认是否有 Agent Plan 个人版订阅
- [`plans team rotate-apikey`](arkcli-plans-team-rotate-apikey.md) -- 团队版席位 APIKey 轮换
- [arkcli-shared](../../arkcli-shared/GUIDE.md)
