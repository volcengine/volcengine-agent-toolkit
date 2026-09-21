# Account Factory Workflow

Use this guidebook to create standardized accounts inside the Landing Zone and optionally apply baselines after account creation.

## Contents

- Core Principles · Runtime Directories — setup and layout
- Preflight Focus — what to confirm before writing
- Standard Flow — resolve intent and inputs → select/create baseline → create account → apply baseline
- Authoring a baseline package (`.tf` source) — Gate 0 support check, Template A/B, security checklist
- Result Output — final summary format

## Core Principles

- Account creation and baseline application are independently invocable. A creation flow may optionally continue into one or more baselines after the account exists.
- Account creation must determine OU placement, finance relationship, and tags. Baseline handles only standard configuration after the account exists.
- Baseline execution prefers Terraform first and uses `ve` CLI only when supplementation is necessary.
- Any `ve` CLI supplementation must follow the real parameter contract of the action. Do not assume every action supports the same `--body` shape.
- When multiple baselines are used together, merge them in the user-selected order. Later selections override earlier ones.

## Runtime Directories

> See the `Path Anchors` section in `SKILL.md`: `./skills/...` resolves to `${SKILL_ROOT}/...`, and `./volcengine-landing-zone-workspace/...` resolves to `${WORKSPACE_ROOT}/...`.

- Runtime root: `${WORKSPACE_ROOT}/` (that is, `./volcengine-landing-zone-workspace/`)
- Blueprint source directory: `./skills/volcengine-landing-zone/assets/blueprints/` (see G3: built-in blueprints are read-only)
- Account-create execution directories are created per run under `./volcengine-landing-zone-workspace/account-factory/runs/<run_id>/account-create/terraform/`
- Baseline plan directory: `./volcengine-landing-zone-workspace/account-factory/baseline-plans/`
- Account-factory runtime-state directory: `./volcengine-landing-zone-workspace/account-factory/runs/`
- Workspace baseline package directory: `./volcengine-landing-zone-workspace/account-factory/baselines/`
- Baseline schema: `skills/volcengine-landing-zone/references/account-factory/baseline.schema.json`
- Built-in network baseline example: `skills/volcengine-landing-zone/references/account-factory/examples/network-cross-account-connectivity.baseline.json`
- Baseline package execution directories are created per run under `./volcengine-landing-zone-workspace/account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/`

If the customer wants to author or customize baseline `.tf` source, read in this order first:

1. `assets/blueprints/account-factory/baselines/README.md` — package directory model, source resolution, and runtime layout
2. `references/account-factory/baseline.schema.json` — baseline plan shape and variable injection contract
3. `assets/blueprints/account-factory/baselines/network-cross-account-connectivity/README.md` — the canonical built-in member-account baseline reference
4. `assets/blueprints/account-factory/baselines/network-cross-account-connectivity/` source files — concrete provider, variable, output, and `local-exec` patterns
5. The "Authoring a baseline package (`.tf` source)" section below — support gate, template choice, and security checklist

## Preflight Focus

The general rules come from [../preflight-checks.md](../preflight-checks.md), including all credential handling (§2). This path focuses on confirming:

- The `ve` and Terraform credential paths validated in preflight §2 are usable for account-factory actions.
- If no usable credentials exist, follow preflight §2's `ve login`-first guidance and reuse the resulting profile for Terraform when supported.
- The minimum input for account creation is complete.
- Baseline-related directories can be created automatically.
- If a baseline must be applied, the target `*.baseline.json` execution plan exists and conforms to `baseline.schema.json`.
- If `terraform plan` fails with missing-credential or expired/invalid credential errors, treat it as the selected Terraform auth path needing setup or refresh, then restart from preflight after it is ready again.

## Standard Flow

Account creation and baseline application have separate real plans and therefore separate G2 confirmations. Complete all read-only preparation continuously until the next write boundary.

### 1. Resolve Account Intent and Inputs

When the user asks to use defaults, infer them from the current conversation, relevant prior customer context, the confirmed architecture, existing run artifacts, and live read-only state. Treat remembered values as candidates and validate them against current evidence when possible. Defaults fill missing values only; preserve existing cloud configuration unless the user explicitly requests a change. Resolve safe defaults before asking questions:

- `account_name` must identify the requested account. When `show_name` is absent, default it to `account_name`.
- Resolve `target_ou_id` from the live `01-organization.ou_catalog` when the requested OU has one unambiguous match. Ask for a choice only when the intended OU is missing or ambiguous; do not ask for a raw ID first.
- Use account tags from an explicitly confirmed organization policy or user request. Otherwise use the blueprint default (no tags) instead of treating tags as a required questionnaire field.
- Resolve the finance relationship from confirmed policy or explicit intent. Ask for `financial_relation_type` and any required authorization list only when no applicable policy/default exists.
- If `financial_relation_account_alias` is not specified, it may default to `account_name`. When the default alias conflicts, the blueprint automatically retries once by appending the account ID suffix. If the user explicitly provided an alias and it conflicts, stop and ask the user to rename it.
- For the built-in network baseline, resolve shared-network IDs and route tables from completed `05-network` outputs. Derive region/AZ values and candidate workload CIDRs only from the confirmed network design and verified live allocations. Ask for the unresolved network values when a non-overlapping allocation cannot be established; never invent an unverified CIDR.
- Do not assume custom architectures contain `Applications/Dev`, `Applications/Staging`, or `Applications/Prod`. Use the live `ou_catalog`; if Phase 01 was not run or the selected OU is outside that catalog, then ask for and verify an explicit OU ID.
- If the confirmed Landing Zone omitted the `network` role and Phase 05 was skipped, explain that the built-in network baseline is unavailable until a network account/foundation is provided; do not infer one from an account name.

Group related unresolved inputs when practical. Do not pause merely to restate values that were derived safely; include those assumptions in the G2 impact summary.

### 2. Resolve Baseline Intent

Honor an explicit request to create only the account, apply a named baseline, or create a custom baseline without presenting a path-selection menu. If the request does not establish whether a baseline is wanted, explain its optional purpose briefly and ask once. After the intent is clear, continue through baseline preparation and the account-creation plan without an additional confirmation checkpoint.

### 3. Select or Create a Baseline

When selecting an existing baseline:

- scan `account-factory/baseline-plans/`
- list only `*.baseline.json`
- support multi-select

When creating a baseline on the spot:

- if the customer asks for a **custom** baseline (anything beyond the built-in packages), first run **Gate 0 — Provider resource support check** (see "Authoring a baseline package" below): verify the `volcenginecc` provider supports every required resource. If any required resource is unsupported, tell the customer it is not supported for now and do not generate the baseline `.tf`.
- the currently supported built-in baseline package is `network-cross-account-connectivity`
- when the user needs a starting point, reuse the example file `references/account-factory/examples/network-cross-account-connectivity.baseline.json` and replace its placeholders with the current run values
- generate baseline JSON from `baseline.schema.json`
- validate the package name, file name, variables, and business impact without adding a separate confirmation; ask only when a conflict or ambiguity cannot be resolved without changing the user's intent

#### Authoring a baseline package (`.tf` source)

##### Gate 0 — Provider resource support check (mandatory before authoring any custom baseline)

> This gate, together with the "Baseline package security checklist" below, is the shared contract for **any** package that is not a vetted built-in one. The `Solution Deployment` path ([../solution-deployment/guidebook.md](../solution-deployment/guidebook.md)) reuses both when it imports an external blueprint from a git URL or local path. "Authoring" below therefore also covers "importing and validating a third-party blueprint before deploying it".

Before writing any `.tf` for a custom (non-built-in) baseline, first confirm that the `volcenginecc` Terraform provider actually exposes a resource for every cloud object the baseline needs to manage. Never assume support — verify it.

- Determine the concrete resources the baseline must create (for example a VPC, a subnet, a transit-router attachment, a resource-share association, a service-linked role).
- For each one, check whether the provider declares a matching `volcenginecc_*` resource type. Use the provider's published resource list as the source of truth, in this priority order:
  1. `terraform providers schema -json` from an initialized package, then look for the resource name (most authoritative — reflects the exact pinned version).
  2. The provider documentation / Terraform Registry resource index for `volcengine/volcenginecc`.
  3. The provider source repository (`terraform-provider-volcenginecc`) resource registration list.
- **If every required resource is supported:** proceed to author the baseline `.tf` using Template A or Template B below.
- **If any required resource is NOT supported:** stop. Tell the customer plainly that this baseline is **not supported for now** because the `volcenginecc` provider has no Terraform resource for the missing object, and do **not** generate baseline `.tf`. Do not silently fall back to inventing a `local-exec` + `ve` CLI workaround for a customer's ad-hoc custom baseline.
  - The sanctioned built-in `local-exec` exception is the pattern already implemented in `network-cross-account-connectivity/main.tf`: network-share scope update for Resource Share principal association. Reuse only that established built-in pattern when it matches the same ownership boundary; do not generalize it into a catch-all CLI escape hatch for unsupported resources in a customer's ad-hoc custom baseline.

A baseline package is self-contained: the agent writes only `terraform.tfvars.json` and runs `terraform apply` — it never generates a central orchestrator root. The target account is decided by the package's own provider. Pick exactly one template from [baseline-templates/](baseline-templates/) based on where the baseline deploys:

- **Template A — new member account (needs cross-account AssumeRole):** [baseline-templates/member-account/](baseline-templates/member-account/). Provider carries `assume_role`; every resource pins the `member` alias. Copy the built-in `network-cross-account-connectivity` package as the fuller working reference. Any `local-exec` here starts from the current `ve` identity and is used only for objects `volcenginecc` has no resource for; for supported objects, prefer Terraform resources pinned to the owning account's alias.
- **Template B — current management account (no AssumeRole):** [baseline-templates/management-account/](baseline-templates/management-account/). Bare default provider; resources need no `provider =` line. Any `local-exec` here calls `ve` through the preflight-validated `ve` credential path.

Selection rule: **new member account → Template A; current management account → Template B.** The templates are the common shapes, not the only allowed ones. When a deployment involves cross-account role assumption, the target identity may be established through the Terraform provider's `assume_role` (its base identity coming from env credentials or a profile) or an equivalent profile-based scheme; the one invariant is that writes must land in the confirmed target account. Prefer choosing a single provider shape at authoring time; adding an `enable_assume_role` toggle or a `dynamic "assume_role"` block is discouraged, because runtime conditional identity logic can silently target the wrong account. Cross-account execution rules are in the setup guidebook's "Cross-account execution model".

#### Baseline package security checklist

- Any sensitive output (access keys, secret keys, tokens, passwords) must set `sensitive = true`. Avoid emitting long-lived secrets as outputs at all where possible.
- For cross-account identity, use the `OrganizationAccessControlRole` delegation (Template A). Do not create a long-lived IAM user + access key inside a baseline to obtain admin power.
- When attaching a system policy, do not invent or guess the system preset policy name. Resolve it from the existing system preset policy catalog first, then use that exact name in Terraform and user-facing explanations. A CLI example is `ve iam ListPolicies --Scope System --Limit 100`. For the built-in administrator baseline, use the exact policy name `AdministratorAccess` (not `AdministerAccess`).
- Keep base credentials out of the package and off the command line. Terraform reads them from the selected runtime auth path, and `ve` CLI actions use the selected `ve` credential path or a short-lived AssumeRole credential scoped inside the package.

### 4. Create the Account

- Resolve the account-factory `run_id` before the first write by **reuse-first**, not by blindly creating a new directory. Before creating anything, scan `account-factory/runs/` for an existing run whose `run.json` records the same account-create intent and is not yet completed.
  - Treat the account-create intent as the tuple `account_name + show_name + target_ou_id`. When those values match and the recorded task is still `failed`, `in_progress`, or otherwise unfinished, prefer to reuse that `run_id`.
  - If a partial apply already produced an `account_id`, treat the matching `account_id` as the strongest reuse signal and continue from that run even when later inputs such as baseline selections have changed.
  - A credential failure before or during Terraform plan/apply is the typical zero-state failure: no new account resource has landed yet, so the same `run_id` should be reused after the credential path is repaired.
  - Only create a new run directory under `account-factory/runs/<run_id>/` when no reusable unfinished run matches the same account-create intent, or the existing run artifacts are missing or proven unusable. A new `run_id` should include a timestamp plus account identity, for example `<timestamp>-<account_name>-<target_ou_id>`.
- Ensure an isolated execution directory exists under `account-factory/runs/<run_id>/account-create/terraform/`. Materialize or reuse the built-in `account-create` package under the blueprint source provenance rule in [preflight-checks.md](../preflight-checks.md) §3, recording its source baseline before writing resolved `terraform.tfvars.json`. Reuse preserves state; changed code or resolved inputs invalidate old plans rather than silently reusing them.
- Initialize or refresh the run artifacts before planning account creation: `run.json` for overall task state, `context.json` for resolved inputs and later outputs, and `account-create/status.json` for the current account-create step.
- Run `terraform init`, variable preparation, and `terraform plan -parallelism=1 -out=tfplan` in the background inside `account-factory/runs/<run_id>/account-create/terraform/`, using the Terraform credential source normalized per preflight §2.
- If an account-creation Terraform command fails with missing-credential or expired/invalid credential errors, treat it as the selected Terraform auth path needing setup or refresh, then restart from preflight after it is ready again.
- Present the saved plan plus the follow-up finance CLI write impact under G2. Confirmation for this task covers both; do not interrupt for each individual internal write.
- After confirmation, run `terraform apply -parallelism=1 tfplan` in the same isolated account-create run directory with the same normalized Terraform runtime environment.
- Account tags are managed on `volcenginecc_organization_account.tags`; do not backfill tags through `ve organization TagResources` for accounts created by this blueprint.
- If the account has already been created successfully but post-create CLI steps such as finance relationship fail, treat it as partial success. Do not delete the account and do not rebuild from scratch.
- For those failures, inspect the current state first, then backfill the failed `null_resource` step through another `plan/apply` in the same run directory instead of rebuilding a shared workspace copy.
- After each significant step, refresh `account-create/status.json`, merge `terraform output -json` into `context.json`, and update `run.json` so the same `run_id` can continue into baseline apply later if needed.

Read-after-write validation and CLI conventions:

- After finance relationship creation, validate with `ve billing ListFinancialRelation`.
- Account tags are validated through Terraform refresh/state on `volcenginecc_organization_account.tags`, not through a separate `ve organization ListTagResources` step.
- Even if `CreateFinancialRelation` returns a duplicate or already-exists style result, do not treat it as success without read-after-write validation.
- Finance relationship actions currently use `--body`.
- The `CreateFinancialRelation` body should be organized with `SubAccountID`, `Relation`, optional `AuthListStr`, and optional `AccountAlias`. Follow `--help` for the exact field names.
- Treat `AccountAlias` conflicts as alias uniqueness issues, not as an `already exists so skip it` case.

After account creation completes, summarize the result. If the user already requested a baseline, continue automatically with its read-only preparation and present the actual baseline plan under G2 when ready. Do not apply the baseline under the account-creation confirmation.

### 5. Apply the Baseline

The baseline is **not** applied by a central orchestrator root. The agent reads one or more baseline execution plans, turns them into a run-level execution queue, and applies the referenced baseline packages serially. Baseline apply should reuse the same account-factory `run_id` that already captured `account create` whenever that run is the one being continued.

- Read the selected `*.baseline.json` files directly, merge them in order (later selections override earlier declarations with the same baseline `name`), and validate against `references/account-factory/baseline.schema.json`.
- Resolve all `{{ variable_name }}` references against the merged `variables` block plus the run context. The run context includes at least the `account-create` outputs from `account-factory/runs/<run_id>/account-create/terraform/` and outputs from previously completed baselines in the same run.
- Identify the final enabled baselines and variables first. Ask for missing minimum variables only for baseline packages that are actually enabled.
- Resolve the run directory by **reuse-first**, do not blindly create a new one. When the current baseline apply is continuing from a just-finished or partially finished account-create run, reuse that same `run_id` first. Otherwise, before creating anything, scan `account-factory/runs/` for an existing run whose `run.json` targets the **same `account_id` and the same set of enabled baselines** and is **not yet completed** (status is `failed`, `in_progress`, or otherwise unfinished). If such a run exists and its artifacts are still consistent, **reuse that `run_id`** and resume from the recorded step (see `references/failure-recovery.md`) instead of starting a new run.
  - A credential failure (provider auth missing/expired, or an AssumeRole failure) is the typical **zero-state** failure: Terraform usually wrote no state, so the previous run directory is safe to reuse. After the user fixes credentials, **resume the same `run_id`** rather than spawning a new one.
  - Only create a **new** dedicated run directory under `account-factory/runs/<run_id>/` when no reusable unfinished run is found, or the existing run's artifacts are missing or proven unusable. A new `run_id` should include a timestamp plus account identity, for example `<timestamp>-<account_name>-<account_id>`.
- When the run directory is **newly created**, initialize run state files before the first baseline apply. When **reusing** an existing run, load the existing files instead of overwriting them, and continue from the recorded state.
  - `run.json` — overall workflow state, selected plans, execution queue, current step, final summary
  - `context.json` — resolved variables, account-create outputs, and accumulated baseline outputs
  - `account-create/status.json` — account-create execution state
  - `baselines/<baseline-name>/status.json` — per-baseline execution state
- For each enabled baseline package, ensure an isolated execution directory exists under `account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/`. Materialize or reuse it under the blueprint source provenance rule in [preflight-checks.md](../preflight-checks.md) §3, recording its source baseline before writing resolved `terraform.tfvars.json`. Each package has its own source record; updating a shared workspace package must not silently refresh an unfinished run.
- Resolve package sources by name. Check `account-factory/baselines/<package>/` in the workspace first; if it does not exist, fall back to the built-in `blueprints/account-factory/baselines/<package>/`.
- Use `depends_on`, then optional `order`, then declaration order to derive the serial execution queue. Do not run dependent baselines before their prerequisites succeed. The target account is fixed by each baseline package itself and is not configurable in the baseline plan.
- Each baseline package owns its own provider wiring, and the target identity is decided **inside the package's provider**. The runtime supplies the validated Terraform credential source, and that base identity initiates any package-level `assume_role`. Whether the package targets the management account or a member account is fixed by whether the package's provider declares `assume_role` (see "Authoring a baseline package" above). If the selected credential path cannot reach the target role, AssumeRole fails at plan/apply and no resource is created in the wrong account; stop and return to the credential guidance in preflight.
- If a member-account baseline package needs a service-linked role (for example `ServiceRoleForTransitRouter`), manage it with `volcenginecc_iam_role` through that package's member provider. If the role already exists outside Terraform state, import it into the package state instead of adding a CLI fallback. For a management-account package (provider without `assume_role`), use the default provider for supported Terraform resources.
- In the background, run `terraform init` and `terraform plan -parallelism=1 -out=tfplan` inside each baseline package directory, using the Terraform credential source normalized per preflight §2.
- If Terraform reports missing or expired/invalid credentials, stop and guide the user to refresh the selected Terraform auth path first.
- Show the actual serial plan set and a concise impact summary to the user. Do not expand internal state-file shapes or package-copy mechanics unless troubleshooting requires it.
- G2 applies to this task after all enabled baseline plans are available: one confirmation covers the current baseline apply set and internal writes run continuously.
- After confirmation, run `terraform apply -parallelism=1 tfplan` serially in each enabled package directory. After each step, update `status.json`, merge filtered non-sensitive outputs into `context.json`, and refresh `run.json`.

After baseline apply completes, summarize the result and any material follow-up.

## Result Output

Summarize the outcome in a natural structure appropriate to the run. Include the applicable facts:

- the new account's identity, OU placement, and finance relationship
- which baselines were used
- which baseline segments were applied automatically
- any blocker or manual follow-up that remains
