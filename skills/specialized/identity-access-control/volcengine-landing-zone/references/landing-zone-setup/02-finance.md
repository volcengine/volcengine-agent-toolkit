---
stage_id: 02-finance
stage_type: landing-zone-setup
user_step_name: 财务关系设置
user_goal: 完成主账号与核心账号之间的财务托管或财务关联
user_progress_text: 正在处理多账号财务关系
user_completion_text: 财务关系设置已完成
user_intro_why_now: 组织和核心账号就位后，需要先明确账号间的财务归属关系，后续治理和运维边界才清晰
user_intro_value: 帮用户把多账号体系中的账单归属和管理关系尽早理顺
user_intro_outcome: 完成后核心账号会具备明确的财务关系，为后续持续运营和成本治理打底
purpose: Establish the finance relationship model needed for unified multi-account governance and management
---

# Phase 2: Account Finance Relationships (02-finance)

**Target directory**: `./volcengine-landing-zone-workspace/blueprints/landing-zone-setup/02-finance/`

## Phase Goal

This phase binds finance relationships between the primary account and the core accounts through `null_resource` plus the `ve billing` CLI.

## Minimum Input

- `prefix` must stay aligned with `01-organization`. By default, `AccountAlias = <prefix>-<key>`
- `financial_relation_accounts` should be assembled automatically from the core account IDs produced by the previous phase instead of asking the user to fill them again
- Ask for `financial_relation_type` only when it is missing, to determine whether the model is finance hosting or finance association
- Ask for `financial_relation_auth_list_str` only when the chosen relationship type truly requires extra authorization items
- Do not ask early in this phase for identity, logging, or networking variables

## Execution Conventions

- If the target finance relationship already exists, prefer reuse
- Even when `CreateFinancialRelation` returns a duplicate or already-exists style result, do not treat it as success directly. Continue with read-after-write validation through `ListFinancialRelation`
- `Financial_Hosting` maps to `Relation = 1`
- `Financial_Association` maps to `Relation = 4`

## Result Notes

- After this phase completes, make it clear which core accounts already have the intended finance relationships
- Finance relationships are not automatically removed when Terraform resources are destroyed. If removal is needed, run `ve billing DeleteFinancialRelation` or an equivalent cleanup command separately
