---
stage_id: 01-organization
stage_type: landing-zone-setup
user_step_name: 组织和核心账号准备
user_goal: 按已确认的客户账号架构复用或创建 OU 和账号
user_progress_text: 正在完成组织和核心账号准备
user_completion_text: 组织和核心账号准备已完成
user_intro_why_now: 先把组织结构和核心账号准备好，后续财务、身份、日志和网络配置才有统一落点
user_intro_value: 帮用户建立符合自身管理边界、可治理且可持续扩展的账号架构
user_intro_outcome: 完成后会得到按稳定逻辑键索引的 OU、账号和语义角色目录，供后续阶段复用
purpose: Reuse or create the confirmed customer-specific organization structure and account architecture required by later phases
---

# Phase 1: Organization and Accounts (01-organization)

**Target directory**: `./volcengine-landing-zone-workspace/blueprints/landing-zone-setup/01-organization/`

## Phase Goal

- Reuse or create the complete OU/account architecture confirmed under G1
- Keep display names independent from stable internal keys and Landing Zone semantic roles
- Produce generic OU/account catalogs and downstream finance, identity, logging, and networking hand-off values

## Architecture Branch

- If the customer confirmed the recommended solution, materialize `recommended-v1` as the complete `${WORKSPACE_ROOT}/confirmed-architecture.json`. Do not ask OU/account design questions again. The versioned default remains the current top-level `Platform`, `Applications`, and `SandBox`; `Dev`, `Staging`, and `Prod` under `Applications`; and the five recommended accounts.
- If the customer requested changes, apply only their business differences to `recommended-v1`, but persist one **complete** normalized architecture JSON. Generate the Markdown confirmation directly from the same JSON and, after confirmation, pass its exact `organization_architecture` object into the workspace execution copy. The customer describes business requirements; the Agent assigns stable keys, OU levels/parents, account placement, selectors, capability switches, and semantic role bindings.
- A complete object replaces the whole default architecture; it is not a partial patch. An empty account map is rejected in ordinary convergence. Removing all applied objects is a migration request, not a special empty-object shortcut.
- Keep stable keys unchanged when only names change. A key change, OU parent/level change, account move, or managed/reference conversion is a migration even if the requested business tree looks similar.
- Support OU levels 1 through 5 and at most 20 OU nodes, matching the enterprise-organization service limits. Validate missing parents, cycles/invalid levels, duplicate sibling names, invalid account placement, duplicate account names, and account-name length before any provider write.
- Role bindings are independent of account names. Require `log_archive` when the log capability is enabled and `network` when the network capability or built-in network account-factory baseline is enabled. If the customer disables that capability, mark the dependent phase skipped; never guess by name.
- Multiple semantic roles may bind to one physical account, but G1/G2 must explicitly show the reduced isolation boundary and increased blast radius. Never consolidate roles by default.

## Minimum Input

- Prefer read-only lookup for `root_ou_id`; do not ask the user for it first.
- Ask for `prefix` only when it is missing. The default architecture uses it for account names, and later phases reuse it for resource naming.
- Ask for `region` only when it is missing. Prefer `VOLCENGINE_REGION`, otherwise default to `cn-beijing`.
- Resolve and persist the verified management account ID. Persist the organization ID when discovery exposes it.
- Do not expose the Terraform object shape, stable keys, depth values, existing-ID maps, or output wiring as customer questions.
- The per-account `finance_enabled`, `identity_enabled`, and finance alias values default safely and are changed only when the confirmed account design requires it.

## Read-Only Discovery and Reconciliation

- Run `ve organization DescribeOrganization` first. If the organization exists, resolve Root and recursively inventory current OUs and organization accounts. If it does not exist, route into the G2 bootstrap branch; do not create it during preflight.
- Match desired OUs by the confirmed parent path plus exact name, not by name alone. Match an account by an explicitly supplied ID or a unique exact `account_name`; verify its display name and target OU.
- Record unambiguous matches in generic `existing_ou_ids` and `existing_account_ids`, indexed by the same stable keys used by the desired architecture. The fixed `existing_*_ou_id` variables remain only for backward compatibility.
- Classify every desired object and actual plan action as `reuse`, `create`, `update_in_place`, `conflict`, or `migration_required`. Duplicate matches, a mismatched parent, an account already placed in another OU, or an ID whose live attributes do not match the desired object is a conflict. Delete, replace, movement, stable-key change, or ownership conversion is `migration_required`.
- Reuse is unmanaged reference mode: the blueprint verifies the known ID but does not rename or move the live object. If the customer wants Terraform to manage or move an existing object, handle import and migration as a separate, explicitly confirmed operation.
- Inspect the current Terraform state before populating existing-ID maps. Objects already managed by this workspace must remain managed; do not also convert them into unmanaged references.
- Discovery does not delete, move, invite, or rename anything. Existing accounts outside the enterprise organization remain outside the default automation path.

## Phase Confirmation and Execution

- Under G2, show one complete impact summary after read-only reconciliation and plan: final tree, stable key/name pairs, capability switches, account placement, semantic role bindings, finance/identity target sets, full plan classification, and Phase 04/05 readiness.
- State explicitly that unplanned current objects are untouched and that this ordinary phase performs no account moves, retirements, or deletions.
- After confirmation, apply the saved plan with `-parallelism=1` continuously for this phase. The five level-specific OU resource blocks are intentional; do not collapse them into a self-referencing `for_each`, which creates a Terraform dependency cycle.
- If the organization does not yet exist, G2 must first cover `CreateOrganization` plus the expected tree. After Root OU is created, continue only if the plan contains exactly the confirmed creates; otherwise stop and reconfirm.
- For a workspace created by the original fixed blueprint, retain the default stable keys so the built-in `moved` blocks migrate the six OU and five account state addresses. Review the plan and require zero unexpected creates/destroys before apply.

## Output and Recovery

- Read `landing_zone_context_payload`, add only Terraform state `lineage` and `serial` under `producer`, and atomically write `${WORKSPACE_ROOT}/landing-zone-context.json` with mode `0600`. The context must remain non-sensitive and rebuildable.
- Keep `ou_ids_by_key`, `ou_catalog`, `account_ids_by_key`, `account_catalog`, `account_ids_by_role`, `finance_relation_targets`, and `identity_target_account_ids` as compatibility outputs for one migration cycle.
- Downstream phases consume generic maps/selectors. Compatibility scalar outputs remain available for the default keys and roles, but a missing custom key/role legitimately returns `null` and must not trigger name-based fallback.
- If `ConcurrentException` or partial success occurs, inventory live resources again, refresh only confirmed stable-key matches, and regenerate a plan instead of calling the whole phase a failure.
- Removing a key from an architecture that has already been applied is not an ordinary update: `prevent_destroy` is enabled, and account/OU retirement must enter a separate migration workflow with explicit impact confirmation.
