---
name: volcengine-troubleshooting
description: Use when the user encounters VolcEngine errors or needs local troubleshooting for OpenAPI, Python SDK, CLI, IAM, billing, compute, networking, storage, database, CDN, media, AI, security, or VKE cases.
license: MIT
metadata:
  openclaw:
     envVars:
        - name: VOLCENGINE_ACCESS_KEY
          required: false
          description: AccessKey for AK/SK auth path (alternative to `ve login`)
        - name: VOLCENGINE_SECRET_KEY
          required: false
          description: SecretKey for AK/SK auth path
        - name: VOLCENGINE_SESSION_TOKEN
          required: false
          description: Optional STS session token for temporary credentials
        - name: VOLCENGINE_REGION
          required: false
          description: Default region; falls back to cn-beijing if unset
---

# VolcEngine Troubleshooting

本 skill 面向用户本地环境使用，目标是在不修改云上资源的前提下，帮助定位 VolcEngine 产品、OpenAPI、Python SDK、`ve`/`tosutil` CLI 和控制台操作失败的原因。主入口只保留必要的启动规则、场景路由和安全边界；本地工具检查与完整领域索引放在 `references/getting-started.md`，OpenAPI 报错、签名、鉴权、参数、限流以及 `ve`/`tosutil`/Python SDK 调用链路的快速检查放在 `references/openapi-quick-check.md`，具体产品域手册放在 `references/domain-guides/`。

先把 `SKILL_ROOT` 解析为包含本 `SKILL.md` 的绝对目录。所有脚本和 reference 都从
`${SKILL_ROOT}` 解析，不依赖仓库布局或当前工作目录。

## 开始前

1. 先读取 `references/getting-started.md`，确认本地工具、环境变量、场景依赖和领域路由。
2. 如用户允许执行本地体检，运行通用检查：

   ```bash
   bash "${SKILL_ROOT}/scripts/common_check.sh"
   ```

3. 优先用 `ve sts GetCallerIdentity` 验证当前身份链路，只报告是否可用和必要的身份摘要，不输出 SecretKey、SessionToken、完整 AccessKeyId、完整手机号、账单明细或对象内容。
4. 不要运行 `ve configure`、登录/SSO 初始化、安装依赖、写入配置文件或修改云资源，除非用户明确要求并确认影响。
5. 若不确定归属，按 `references/getting-started.md` 中的“场景路由”定位领域；遇到 OpenAPI 报错、签名/鉴权失败、参数校验、限流、服务端错误，或由 `ve`/`tosutil`/Python SDK 暴露出的 OpenAPI 调用失败，先读 `references/openapi-quick-check.md` 收敛 RequestId、Action、Region、错误码和最小复现上下文。
6. 根据下方路由打开对应 `references/domain-guides/<domain>/README.md`，再按领域手册的“先读这些”读取 `query-cli-catalog.md`、章节 README、`api-coverage-matrix.md` 和脚本 README。

## 场景路由

先从用户报错中提取 `RequestId`、`ErrorCode`、`Action`、`Service`、`Region`、资源 ID、发生时间和调用方式。如果缺失，先问最少必要问题。

领域判断优先读 `references/getting-started.md`。确定领域后，再进入对应 `references/domain-guides/<domain>/README.md`：

- `openapi-sdk-cli`：OpenAPI、`ve` CLI、Python SDK、签名、API 网关。
- `account-permission`：账号、AK/SK、STS、IAM、角色、权限不足。
- `billing-quota`：账单、余额、欠费、订单、配额、资源包。
- `compute-container-network`：ECS、VKE、CLB/ALB、VPC、NAT、EIP、路由、安全组。
- `storage-database`：TOS、EBS、文件存储、云备份、RDS、Redis、数据库连接。
- `domain-cdn-ingress`：DNS、域名、证书、CDN/DCDN、入口回源。
- `communication-media`：SMS、RTC、VOD、Live、CV/OCR、veImageX。
- `llm-ecosystem`：Ark、豆包、VikingDB、AgentKit、ArkClaw、Coze、机器学习平台。
- `security-kms-encryption`：KMS、Secret、云加密机、WAF、DDoS、Cloud Firewall、安全中心。

仍无法分类时，完成 `scripts/common_check.sh` 后，按报错中的服务名查 `ve SERVICE --help` 和 `ve SERVICE ACTION --help`。

## 非阻塞反馈

已有证据显示 skill 指引有误、CLI 行为异常、缺少所需能力，或用户目标仍未完全解决时，先继续已授权的排障、恢复和主任务。在自然总结点，可以简短邀请用户分享这次真实场景；清楚区分已确认的问题与尚未验证的原因。反馈不替代故障处理，也不是继续任务或结束排障的前置条件。

- 同一对话的主动邀请最多一次，跨 skill 路由也共用此限制；用户拒绝或忽略后不再提醒。用可忽略的陈述句附上入口，不停下来等待答复。
- 邀请只使用已有上下文，不为此安装工具或 skill、登录、搜索 issue、额外采集日志，或重试云操作来复现错误。主任务仍可继续时直接继续。
- 用户主动提出反馈时，使用已可用的 `volcengine-feedback` 整理实际目标、观察结果和期望。若该 skill 未安装或无法在当前对话加载，直接提供 [反馈表单](https://github.com/volcengine/volcengine-skills/issues/new?template=feedback.yml)，也可在当前对话整理脱敏草稿；不要要求为反馈安装、登录或重启主对话。公开发布前的内容确认和脱敏由反馈流程处理。

例如：“如需反馈本次发现的能力缺口，可通过 [反馈表单](https://github.com/volcengine/volcengine-skills/issues/new?template=feedback.yml) 说明使用场景和改进建议；反馈是可选的，不影响当前任务继续。”

## 核心原则

- **只读优先**：默认只执行 Describe/List/Get/Query/Lookup/Check 类命令。Create/Update/Delete/Attach/Detach/Put/Set/Start/Stop/Run/Invoke/Pay/Renew/Refresh/Preload 等写操作必须先解释影响并等待用户确认。
- **CLI 优先，SDK 辅助**：只支持 `ve` 和 `tosutil` 两类 CLI。只有分页聚合、跨资源拓扑、日志归并或 CLI 未覆盖时，才建议 `volc-sdk-python` 或 `volcengine-python-sdk` 脚本。
- **凭证安全**：只从环境变量读取 AK/SK/Token；不要要求用户把凭证写入文件；不要打印 SecretKey、SessionToken 或完整 AccessKeyId；展示 AK 时至少遮蔽中间部分。
- **最小上下文**：每次排障只收集当前问题所需的服务、地域、资源和时间窗口。不要批量枚举无关账号资源。
- **解释判据**：每个检查都说明为什么查、期望看到什么、异常意味着什么，以及下一步该收集哪一项证据。
