---
name: volcengine-feedback
description: >-
  Help users draft and, when authorized, submit feedback to volcengine/volcengine-skills:
  skill problems, missing capabilities, cloud scenarios, and successful Agent workflows.
  Use for explicit feedback or sharing requests, or an optional invitation at a natural summary
  after Volcengine CLI errors or an incompletely solved task. Feedback never blocks the main task.
license: MIT
---

# Volcengine Feedback

Help users share practical experience of managing cloud services with an Agent: benefits,
difficulties encountered, and capabilities they would like to use. A short description of the
scenario is sufficient; a diagnosis or proposed implementation is optional.

Destination: **`volcengine/volcengine-skills`** on GitHub.
[Feedback form](https://github.com/volcengine/volcengine-skills/issues/new?template=feedback.yml)
· [Community and privacy guidance](https://github.com/volcengine/volcengine-skills/blob/main/.github/FEEDBACK_GUIDELINES.md).

## Keep the main task moving

- An error or incomplete result is permission for an optional invitation, never permission to
  publish. Continue authorized diagnosis, recovery, and remaining work first. Mention feedback
  at a natural summary, at most once per conversation across all skills. If declined, ignored, or already
  offered, continue without another reminder. Routine success needs no solicitation; help share
  a successful scenario when the user expresses interest.
- Keep an unsolicited invitation to one short sentence with the form link. Do not wait for an
  answer or start drafting, searching issues, collecting logs, installing tools/skills, logging
  in, or opening a browser just to invite feedback. Example:
  “如需反馈本次未解决的问题，可通过 [Feedback](https://github.com/volcengine/volcengine-skills/issues/new?template=feedback.yml)
  说明使用场景和改进建议；反馈不影响当前任务继续。”
- Once the user asks for feedback, handle it as an optional side task. Missing details, unavailable
  GitHub access, declined publication, or submission failure never become prerequisites for cloud
  work. Preserve the draft in the conversation and return to remaining work. Never repeat cloud
  mutations or reproduce an incident just to obtain feedback evidence.

## One sentence → one preview → a result

The user can say “我希望反馈使用中遇到的问题：……” or “分享本次成功部署的实践”, or invoke
`volcengine-feedback` in their host. This skill does not add a native `/feedback` or `ve feedback`
command; use the host's actual skill invocation. Keep the interaction conversational:

1. **Draft from context.** Reuse the user's sentence and the relevant conversation. Infer the
   optional category (skill problem, capability request, scenario need, or success story), title,
   and known product/skill details. Ask at most one short question only when there is no usable
   experience to describe. Otherwise leave missing details out; never turn this into a questionnaire.
2. **Show one compact preview.** Present `[Feedback] <short title>` and a short paragraph explaining
   the goal, experience, and desired change or value, as far as they are known. Add an optional
   “Details” paragraph only when existing sanitized evidence helps. Versions, reproduction steps,
   logs, and a separate emotion rating are not required. Use clear, professional wording in the
   user's language and accurately retain their reported experience and concerns. Do not invent
   root causes, results, time savings, or maintainer commitments.
3. **Offer one publication decision.** Identify the public repository next to the exact preview
   and link the community/privacy guidance as a reminder for public sharing.
   The user can send it, edit it, or leave it as a draft. A drafting request does not authorize
   publication; use existing explicit authorization if it already covers this exact content and
   destination. Otherwise ask once whether to publish, without pausing unrelated main work.

Example preview when the conversation supports these facts:

> **[Feedback] 建议在部署完成后增加服务可用性验证**
>
> 使用 Agent 部署测试应用时，已完成资源创建，但尚未验证服务可用性。
> 建议继续执行可用性检查，并提供明确的验证结果。
>
> 将公开发布到 `volcengine/volcengine-skills`，仅包含以上脱敏内容。
> 发布前请检查敏感信息，并遵守[反馈约定](https://github.com/volcengine/volcengine-skills/blob/main/.github/FEEDBACK_GUIDELINES.md)。
> 你可以确认发送以上内容、修改或先留作草稿。

For an active incident, continue troubleshooting or official support; a public issue carries no
response-time or resolution guarantee.

## Review for public sharing

Before any issue search, URL prefill, attachment, or submission, minimize and redact the data.
The issue will be **public**. Include only information necessary to understand the scenario:

- Remove AK/SK, tokens, cookies, authorization headers, signed URLs, passwords, personal/customer
  data, private endpoints, local absolute paths, and confidential business content. Replace account
  IDs with `<account-id>`, resource IDs with prefix-preserving forms such as `vpc-<id>` and
  `clb-<id>`, and real TRNs with `<resource-trn>`. Check titles, screenshots and attachments too.
- Prefer a short sanitized excerpt to entire transcripts, configuration files, or logs. Do not
  inspect credential stores or collect more cloud data for feedback. If safe redaction is uncertain,
  omit the detail. Security vulnerabilities or suspected credential exposure belong in the project's
  available private security reporting channel or official Volcengine support, not a public issue;
  do not invent a private contact or upload exploit details.
- Follow the [GitHub Community Guidelines](https://docs.github.com/en/site-policy/github-terms/github-community-guidelines).
  Welcome reports of problems encountered during use and suggestions for improvement. Focus on
  facts, evidence, and impact. Personal attacks, harassment, discrimination, hate speech, threats,
  and disclosure of others' private information are unacceptable; maintainers will directly close
  issues containing such violations. If a draft contains an attack, offer a factual rewrite that
  preserves the underlying concern; do not publish the attacking text.

## Deliver or submit

Use an available authorized GitHub integration or browser after the publication decision above.
There is no mandatory executable or environment-variable dependency. The form's public-sharing
guidance is informational, with no checkbox or separate agreement step. Authorization for the exact
content and public submission remains required. Do not require an issue search. If a matching issue
is already known or the user asks to find one, search only sanitized keywords; commenting on an
existing thread requires authorization for that destination too.

| Outcome | Finish the feedback side task |
| --- | --- |
| Submission verified by returned URL or read-back | Briefly acknowledge the contribution and return the issue link. |
| Draft only, no GitHub access, or definite submission failure | Mark “not submitted”; return the copyable draft and form link without requiring login, installation, or a new conversation. Help set up access only if requested. |
| Creation timed out and may have succeeded | Check for a matching issue before any retry. If unverifiable, mark “submission unconfirmed”, preserve the draft, and stop this attempt to avoid duplicates. |

Continue remaining authorized main work immediately. No outcome requires waiting for a maintainer.
