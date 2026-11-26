# Infer Endpoint 回归场景

以下是运行行为验收协议。先保留实际失败Trace和已加载Skill哈希；文档场景不代表已通过云端回归。

| 场景 | 用户输入/真实条件 | 验收重点 |
| --- | --- | --- |
| 触发：已有客户端故障（4341/163540） | 已有平台Key和Endpoint，CC Switch/Claude Code失败；本机compatible请求200、原客户端配置未见 | 原客户端与本机对照分行，结论只覆盖受测组合，不声称已锁定用户配置根因；不虚构“复现率最高”、fallback必失败、标题生成或客户端无响应；保留原平台链路 |
| 凭证来源矩阵 | 同账号有个人Coding、个人Agent及团队席位；参考答案笼统要求Coding专属Key | 按源码区分个人Coding普通池、个人Agent Scene池、团队席位；不为迎合参考答案切套餐/换Key。只读缺失信息保持未知 |
| 真实原路径正例 | 用户提供脱敏的实际Base URL/SDK路径与对应404；另有不相关接口403 | 根据原请求条件给修正，不用新的403替代原404；客户端追加路径按其真实版本核对 |
| 验证协议 | 用户授权一次Anthropic兼容文本探针 | 使用原模型与兼容messages路径、明确小token预算并保留结果；不把`arkcli +chat --model <endpoint-id>`的Responses成功当Anthropic验证；不回显Key、不重试收费请求 |
| guard：控制面不等于数据面 | `arkcli infer endpoint get <endpoint-id>`返回Running/Key Active，但无业务响应 | 说明仅控制面已验证，不宣布调用成功；不同模型/模态或协议不混写；未授权时给步骤而不发推理 |
| anti-trigger：普通创建 | 用户只说创建一个推理接入点，未选raw CRUD | 转Deploy；显式raw CRUD才留在本Skill。两者均保留模型唯一解析、宿主确认和写操作边界 |

边界对照：已知原请求与未知原请求、HTTP 200与仅Running、已授权与未授权测试、个人与团队Key、一个位缺失与有版本证据的fallback、静态配置与已生效新会话。缺证据不补事实，不以重新生成的好答案覆盖原失败。

## 正常路径：只读核对已有 Endpoint

用户明确提供当前身份下的 `endpoint_id`，要求核对接入点配置。先读取共享协议与本 Skill；变量只取用户提供或本轮已查证的完整 ID，不使用演示 ID 请求服务。

```bash
arkcli infer endpoint get "$endpoint_id" --format json
```

验收：命令成功时保留真实模型绑定与管理状态，仅报告接入点元数据已查证，不声称原客户端或数据面已恢复；原 URL/协议缺失时仍列为未知。不存在、无权限或认证失败时保留原错误，不创建替代 Endpoint、换身份或提交推理请求。该命令的参数与实际 `arkcli infer endpoint get --help` 核对一致。
