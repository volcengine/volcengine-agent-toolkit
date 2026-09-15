# 使用反馈与场景共创 / Feedback guidelines

我们希望了解你通过 Agent 使用火山引擎时的实际收获、遇到的困难和后续期待。欢迎分享使用问题、能力需求、待支持场景及成功实践，帮助用户与开发者共同改进 Agent 管理云服务的体验。简短描述即可，不需要完整技术报告。

We would like to understand your outcomes, challenges, and expectations when using Volcengine through an Agent. Share usage issues, capability requests, scenarios to support, and successful practices to help users and developers improve the experience together. A brief description is enough; a complete technical report is not required.

## 写什么 / What to share

[Feedback 表单](https://github.com/volcengine/volcengine-skills/issues/new?template=feedback.yml)除标题外，只需填写“反馈内容”。类型与补充信息均为选填。可以分享：

- **使用问题**：相关 skill、任务目标、观察结果及期望改进。
- **能力需求**：希望 Agent 提供的能力及其使用价值。
- **待支持场景**：任务、约束或成功标准，无需预先设计解决方案。
- **成功实践**：完成的任务、实际价值及适用场景。

Besides the title, only “Feedback” is required. Category and details are optional. You can describe a skill usage issue, a requested capability and its value, a scenario and its constraints, or a successful practice and its outcomes.

提供当前已知的信息即可；不必补齐版本、搜索相似 issue、重新运行云命令或收集日志。相关细节可按需填写在补充信息中。

Share what you already know. Version checks, duplicate searches, reruns, and logs are not prerequisites.

## 公开前脱敏 / Keep public feedback safe

GitHub issue、评论和附件是公开内容，请检查正文、截图和附件：

- 删除 AK/SK、临时凭证、密码、令牌、Cookie、签名、私钥和带鉴权参数的 URL。
- 替换账号、租户、真实资源 ID、TRN、内外网地址、个人信息及敏感业务数据。资源 ID 保留固定前缀，例如 `vpc-<id>`、`clb-<id>`；账号用 `<account-id>`。
- 只提供必要且已脱敏的命令、错误或日志片段，不上传原始日志或完整 Agent 会话。案例中的客户、雇主或第三方信息也须获得公开授权。

Remove credentials, identifying details, addresses, and confidential data. Use placeholders such as `vpc-<id>` or `<account-id>`. Share only authorized, minimal, sanitized excerpts, not raw logs or full Agent conversations.

**请勿在常规反馈 issue 中公开敏感漏洞细节。** 先查看仓库 Security 页面是否提供安全政策或 “Report a vulnerability” 私密入口；若没有，通过火山引擎官方网站或控制台查找已公布的安全报告或支持渠道，确认可私密接收后再提交。不要在渠道尚未确认时发布复现或利用细节。

**Do not publish sensitive vulnerability details here.** Check the repository's Security page for a policy or private reporting option. Otherwise, find an established security or support channel on Volcengine's official website or console and confirm that it accepts private reports before sharing details.

## 社区约定 / Community expectations

请遵守 [GitHub Community Guidelines](https://docs.github.com/en/site-policy/github-terms/github-community-guidelines) 及其引用的适用规则。欢迎反馈使用中遇到的问题，请围绕实际场景客观描述，可提供已知的观察结果、相关证据、影响或改进建议。

请避免人身攻击、骚扰、歧视或仇恨言论、威胁、泄露他人隐私等违规内容。包含此类内容的 issue 会被维护者直接关闭，相关评论按 GitHub 平台规则处理。

Follow the GitHub Community Guidelines and the applicable rules they reference. Describe issues encountered during use objectively, based on the actual scenario. Include any known observations, supporting evidence, impact, or suggestions for improvement. Maintainers will directly close issues containing personal attacks, harassment, discrimination, hate speech, threats, privacy violations, or other community-rule violations. Related comments are handled under GitHub's platform rules.

## 通过 Agent 反馈 / Share through your Agent

可直接向 Agent 说明反馈内容，例如“我想反馈……”。Agent 根据已有上下文整理简短的脱敏草稿，一次展示发布目标、标题和正文，供你选择发送、修改或保留草稿。只有你确认具体内容和发布动作后才提交；结果明确为“已发布（链接）”“未提交（草稿）”或“提交未确认（如超时，不盲目重试）”。

Start with “I'd like to share some feedback…”. Your Agent drafts a short, sanitized summary from existing context, then shows the destination, title, and body together. Choose to send, edit, or keep the draft. It publishes only after you confirm the content and action, then reports “Published” with a link, “Not submitted” with a draft, or “Submission unconfirmed” after a timeout, without blindly retrying.

反馈完全自愿，始终不阻塞主任务。Agent 可以在合适的结果说明中简短提醒一次，不反复追问、不自行上传会话或日志。你可以跳过、稍后反馈或拒绝；缺少工具、无法联网、未登录 GitHub 或提交失败时，也继续主任务。

Feedback is voluntary and must never block your main task. Agents may offer one brief invitation in an appropriate summary, without repeated prompts or automatic uploads. You can skip it, respond later, or decline. Missing tools, connectivity, login, or a failed submission must not hold up your work.

反馈用于公开讨论与改进，不是云服务工单，不承诺响应时限或能力排期。正在发生的故障请继续按已有排障流程或官方支持渠道处理。

Feedback is for public discussion and improvement, without promised response times or delivery dates. Continue using troubleshooting or official support for active incidents.
