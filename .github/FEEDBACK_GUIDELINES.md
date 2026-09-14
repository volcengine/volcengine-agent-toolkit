# 使用反馈与场景共创 / Feedback guidelines

我们想听到你通过 Agent 使用火山引擎的真实体验：让你兴奋的尝试、没能走通的步骤、期待的新能力，以及已经用起来的好场景。你的经历能帮助用户与开发者一起探索 Agent 管理云的未来。负面反馈同样重要，一句话也可以，不需要完整技术报告。

Share what excited you, what was frustrating, what you hope an Agent could do, or a cloud workflow that already works well. Negative feedback is welcome too. A sentence is enough.

## 写什么 / What to share

[Feedback 表单](https://github.com/volcengine/volcengine-skills/issues/new?template=feedback.yml)除标题外，只需填写“想反馈什么”，并勾选一次公开发布确认。类型与补充信息均可不填。可以分享：

- **skill 问题**：想完成什么、实际发生了什么、希望有什么改进。
- **新能力**：希望 Agent 能做什么、为什么需要它。
- **待解决场景**：你的任务、限制或成功标准，不需要先设计方案。
- **成功案例**：做成了什么、带来了什么价值、适合什么场景。

Besides the title, only “What would you like to share?” and one publication confirmation are required. Category and details are optional. Tell us about a skill problem, a new capability, a scenario to support, or a success story.

写当前已知的信息即可；不必补齐版本、搜索相似 issue、重跑云命令或收集日志。愿意提供的相关细节可以放在补充信息中。

Share what you already know. Version checks, duplicate searches, reruns, and logs are not prerequisites.

## 公开前脱敏 / Keep public feedback safe

GitHub issue、评论和附件是公开内容，请检查正文、截图和附件：

- 删除 AK/SK、临时凭证、密码、令牌、Cookie、签名、私钥和带鉴权参数的 URL。
- 替换账号、租户、真实资源 ID、TRN、内外网地址、个人信息及敏感业务数据。资源 ID 保留固定前缀，例如 `vpc-<id>`、`clb-<id>`；账号用 `<account-id>`。
- 只提供必要且已脱敏的命令、错误或日志片段，不上传原始日志或完整 Agent 会话。案例中的客户、雇主或第三方信息也须获得公开授权。

Remove credentials, identifying details, addresses, and confidential data. Use placeholders such as `vpc-<id>` or `<account-id>`. Share only authorized, minimal, sanitized excerpts, not raw logs or full Agent conversations.

**请勿在普通 feedback issue 中公开敏感漏洞细节。** 先查看仓库 Security 页面是否提供安全政策或 “Report a vulnerability” 私密入口；若没有，通过火山引擎官方网站或控制台查找已公布的安全报告/支持渠道，确认可私密接收后再提交。不要在渠道尚未确认时发布复现或利用细节。

**Do not publish sensitive vulnerability details here.** Check the repository's Security page for a policy or private reporting option. Otherwise, find an established security or support channel on Volcengine's official website or console and confirm that it accepts private reports before sharing details.

## 社区约定 / Community expectations

请遵守 [GitHub Community Guidelines](https://docs.github.com/en/site-policy/github-terms/github-community-guidelines) 及其引用的适用规则，聚焦实际场景、产品行为和改进期待。可以表达失望，也可以尖锐地批评产品、设计或代码；不会因为负面评价本身关闭 issue。

人身攻击、骚扰、歧视或仇恨言论、威胁、泄露他人隐私等违规内容不被接受；包含此类内容的 issue 会被维护者直接关闭，相关评论按平台能力处理。本仓库未因此新增自动审核或自动关闭流程。

Follow the GitHub Community Guidelines. Direct criticism of the product, design, or code is welcome; negative feedback alone is not grounds for closure. Maintainers will directly close issues containing personal attacks, harassment, discrimination, hate speech, threats, privacy violations, or other community-rule violations. This policy does not add automated moderation.

## 通过 Agent 反馈 / Share through your Agent

一句“我想反馈……”就可以开始。Agent 根据已有上下文整理简短的脱敏草稿，一次展示发布目标、标题和正文，让你选择发送、修改或留作草稿。只有你确认具体内容和发布动作后才提交；结果明确为“已发布（链接）”“未提交（草稿）”或“提交未确认（如超时，不盲目重试）”。

Start with “I'd like to share some feedback…”. Your Agent drafts a short, sanitized summary from existing context, then shows the destination, title, and body together. Choose to send, edit, or keep the draft. It publishes only after you confirm the content and action, then reports “Published” with a link, “Not submitted” with a draft, or “Submission unconfirmed” after a timeout, without blindly retrying.

反馈完全自愿，永远不阻塞主任务。Agent 可以在合适的结果说明中轻量提醒一次，不反复追问、不自行上传会话或日志。你可以跳过、稍后再写或直接拒绝；缺少工具、无法联网、未登录 GitHub 或提交失败时，也继续主任务。

Feedback is voluntary and must never block your main task. Agents may offer one brief invitation at a suitable handoff, without repeated prompts or automatic uploads. Skip it, return later, or decline. Missing tools, connectivity, login, or a failed submission must not hold up your work.

反馈用于公开讨论与改进，不是云服务工单，不承诺响应时限或能力排期。正在发生的故障请继续按已有排障流程或官方支持渠道处理。

Feedback is for public discussion and improvement, without promised response times or delivery dates. Continue using troubleshooting or official support for active incidents.

## 设计参考 / Design references

- [Claude Code `/feedback`](https://code.claude.com/docs/en/commands)：提供统一反馈入口；[Agent 草稿流程](https://code.claude.com/docs/en/tools-reference#sendfeedback-tool-behavior)支持用户查看、编辑、发送、丢弃或稍后处理，发送前草稿保留在本机，成功后提供发送状态或回执。
- [Codex CLI `/feedback`](https://developers.openai.com/codex/cli/slash-commands/#send-feedback-with-feedback)：通过一个命令进入反馈流程，按提示提供诊断信息或日志。

这里借鉴的是简短入口、用户决定发送和明确结果。我们的目标是公开 GitHub issue，默认只整理已有上下文中的最小脱敏摘要，不自动收集或照搬其他 CLI 的全会话、日志上报机制；本 skill 也没有新增 `ve`、Claude Code 或 Codex 的原生命令。

We borrow the short entry point, user-controlled submission, and clear result. This workflow publishes a minimal, sanitized summary to a public GitHub issue; it does not automatically collect conversations or logs, and adds no native command to `ve`, Claude Code, or Codex.
