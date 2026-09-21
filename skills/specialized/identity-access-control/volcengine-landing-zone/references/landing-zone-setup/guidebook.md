# Volcengine Landing Zone Setup Guide

Use this file only after the workflow has clearly entered the real execution path for `Initial Landing Zone Setup`. If the user is still consulting, designing, evaluating, or discussing the solution, do not execute from this file. G5 applies.

## Overall Flow

G1 must be complete before using this execution workflow.

### Step 0: Preflight Checks

The shared rules come from [../preflight-checks.md](../preflight-checks.md). This path adds only two specific branches.

First-time organization enablement branch:

- Run `ve organization DescribeOrganization` first.
- If the organization already exists, run `ve organization ListOrganizationalUnits --body '{}'` to fetch the root OU.
- If it returns `RecordNotExists` or a similar `organization not exists`, record that Phase 01 needs the G2 bootstrap branch. Preflight stays read-only and must not call `CreateOrganization`.
- The Phase 01 G2 impact summary must include organization creation and the complete expected OU/account tree. Only after confirmation may the Agent call `CreateOrganization`, fetch Root OU, and produce the Terraform plan.
- If `CreateOrganization` returns `NoPermissionOnVerificationError`, recognize it as missing enterprise real-name verification and guide the user to complete verification before retrying the same bootstrap branch.
- After Root OU is available, continue automatically only if the plan contains no impact beyond the creates already covered by G2. Any unexpected update, delete, replacement, or conflict requires a new confirmation.

Confirmed-architecture reconciliation branch:

- Use the complete `${WORKSPACE_ROOT}/confirmed-architecture.json` produced by G1 for both default and custom designs; never execute with a dynamic Terraform `null` architecture.
- Ensure `${WORKSPACE_ROOT}` is mode `0700` and the confirmed JSON is atomically written with mode `0600`, valid against `contract.schema.json`, and still matches its confirmed SHA-256.
- Before Terraform for `01-organization`, recursively inventory current OUs and organization accounts against the confirmed design. In the default branch this naturally scans `Platform`, `Applications`, `SandBox`, and the three Applications children; in the custom branch it follows the custom parent tree up to five levels.
- Match an OU by exact parent path plus exact name and an account by explicit ID or unique exact `account_name`. Populate generic `existing_ou_ids` and `existing_account_ids` with unambiguous stable-key matches.
- Classify each desired object as `reuse`, `create`, or `conflict`. A duplicate match, wrong parent, account name/display mismatch, or existing account in the wrong OU is a conflict. Do not silently move an account or choose one duplicate.
- Inspect Terraform state before injecting reuse IDs. A resource already managed by the workspace remains managed and must not also be converted into an unmanaged data reference.
- Ask the user for an ID only when read-only discovery cannot resolve an ambiguity. Do not ask the user to author the architecture object or internal stable keys.

### Step 1: Prepare the Workspace Execution Copy

> Path anchors are defined in `SKILL.md`: `./skills/...` resolves to `${SKILL_ROOT}/...`, and `./volcengine-landing-zone-workspace/...` resolves to `${WORKSPACE_ROOT}/...`.

- Blueprint source directory: `${SKILL_ROOT}/assets/blueprints/` (that is, `./skills/volcengine-landing-zone/assets/blueprints/`)
- Execution copy directory: `${WORKSPACE_ROOT}/blueprints/` (that is, `./volcengine-landing-zone-workspace/blueprints/`)
- Prepare or reuse each phase's execution package under the blueprint source provenance rule in [../preflight-checks.md](../preflight-checks.md) §3, with its own source record. Freeze one source snapshot for the current multi-phase operation; do not refresh an existing phase directory before checking its record and local customizations.
- If built-in skill blueprints are missing, stop and tell the user the skill package is incomplete.
- Create the workspace automatically if it does not exist.
- Use mode `0700` for the workspace and runtime directories. Use `0600` for architecture/context JSON, tfvars, plans, state files, and sensitive deliverables.
- Real execution happens only inside workspace copies. Under G3, built-in blueprint sources remain read-only at all times.

### Step 1a: Maintain the Runtime Contracts

- `${WORKSPACE_ROOT}/confirmed-architecture.json` is the only user-design source. Its complete object includes schema/profile, prefix/region, capability switches, OUs, accounts, selectors, and semantic roles.
- `${WORKSPACE_ROOT}/landing-zone-context.json` is a filtered, non-sensitive hand-off cache. Generate it after Phase 01 by combining `landing_zone_context_payload` with only the `lineage` and `serial` fields from `terraform state pull`.
- Write both files atomically with mode `0600`. Never copy the complete state, plan JSON, credentials, temporary profiles, or initial passwords into the context.
- Before each downstream phase, compare the exact confirmed-architecture file SHA-256 and the Phase 01 state lineage/serial with the context. Rebuild the context from the current Phase 01 outputs when it is missing or stale.
- The authority order is: live read-only cloud facts -> Terraform state/outputs -> confirmed architecture -> rebuildable context -> saved plan/status -> conversation memory.

### Step 2: Fill Only the Minimum Variables for the Current Phase

- Ask follow-up questions only when the next phase is actually about to start and some required input is still missing.
- Do not ask again for values that can already be derived from preflight checks, the current environment, previous outputs, or blueprint defaults.
- After a phase finishes, keep reusable results available for later phases.
- For `01-organization`, always pass the complete `organization_architecture` from the confirmed JSON, including the materialized default. Also pass `configuration_schema_version`, `architecture_profile`, `architecture_mode`, exact file SHA-256, capability switches, and the verified management/organization scope.
- For `02-finance` through `05-network`, pass the absolute `landing_zone_context_path`. Legacy scalar/map inputs are supported only for older standalone workspaces; when both are present they must match the context exactly.

### Step 3: Execute Phase by Phase

The order is fixed: `01-organization` -> `02-finance` -> `03-identity` -> `04-log` -> `05-network`.

For each phase, complete permitted read-only discovery, reconciliation, workspace preparation, and planning in the background, then apply G2 to the actual Terraform and CLI/API write set. After approved writes finish, validate and summarize the outcome. Use the user-language fields from the phase document frontmatter; apply G4 when a user-review file is produced.

Execution conventions:

- Credential handling (which `ve`/Terraform auth path, source→runtime normalization, cross-account rules) is defined once in [../preflight-checks.md](../preflight-checks.md) §2. Use the paths validated there; when no credentials exist, follow its `ve login`-first branch instead of inventing a separate setup flow.
- If a phase-level Terraform command fails with missing-credential or expired/invalid credential errors, treat it as the selected Terraform auth path needing setup or refresh, then restart from preflight after it is ready again.
- `01-organization`, `02-finance`, and `03-identity` use `terraform plan/apply -parallelism=1`.
- Before G2 for `01-organization`, show the final OU/account tree, stable keys, capability switches, role bindings, finance/identity target sets, and the full `reuse/create/update_in_place/conflict/migration_required` classification from the actual plan. Ordinary convergence must reject delete, replace, OU/account movement, stable-key change, retirement, or managed/reference ownership conversion.
- Persist the filtered `landing_zone_context_payload`, add only Phase 01 state lineage/serial, and write `${WORKSPACE_ROOT}/landing-zone-context.json`. Do not reconstruct downstream inputs from default names or assume the fixed five-account shape.
- Record key phase outputs and summary-report material continuously in the background. Do not wait until all phases finish and reconstruct everything from memory.
- **Existing-resource reconciliation (all phases).** Any blueprint resource with a stable real-world identity (fixed name, service-linked role name, share name) may already exist outside this workspace's Terraform state: the customer deployed before, is redeploying, lost or reset state, a prior run partially applied, or the cloud auto-created it (for example, service-linked roles are often created on first use of NAT or Transit Router even in an otherwise untouched account). A blind create against an already-existing object fails with `AlreadyExists`, so this is a normal first-run concern, not only a recovery concern. Because the provider's data sources here are ID-only or cannot filter by name, discovery is a read-only `ve`/OpenAPI step, not a Terraform data lookup. Before apply, every phase must:
  1. Discover read-only whether each stable-identity target already exists in the target account.
  2. Classify each object as `reuse`, `create`, or `conflict`, and surface that classification in the phase G2 impact summary.
  3. For a match that this phase owns, bring it under management with `terraform import` at the resource's already-declared address, then let plan converge it in place. Never reintroduce a `local-exec`/CLI create fallback just to dodge the conflict.
  4. If a name matches but attributes differ, treat it as `conflict`: stop and get a user decision. Never silently mutate or move an existing object.
  5. Inspect Terraform state before importing, so a resource already managed by this workspace stays managed and is not also imported or converted into an unmanaged reference.

### Cross-account execution model

Cross-account work (`04-log`, `05-network`, member-account baselines) is an **execution SOP**, not extra credential management. Credential setup follows [../preflight-checks.md](../preflight-checks.md) §2. Given a working base identity, pick the execution path by whether the object has a Terraform resource:

- **Default — Terraform provider `assume_role`.** Any object the `volcenginecc` provider exposes as a resource is created cross-account through a provider whose `assume_role` targets the member/network account's `OrganizationAccessControlRole`. The base identity comes from the validated Terraform credential source; a wrong target `account_id` fails at plan/apply and never lands resources in the wrong account. TR/VPC/subnet/NAT/attachment, `volcenginecc_iam_role` service-linked roles, and Resource Share associations all go this way.
- **Exception — `ve` CLI AssumeRole, only for objects the provider has no resource for.** In the current built-in blueprints these are: **CloudTrail** (`CreateTrail`/`StartLogging`), **TOS service activation** (account-level `ActiveTosSvc`/`GetAccountStatus`, not a bucket resource), and **organization delegated-administrator registration** (`RegisterDelegatedAdministrator`). For these, `ve sts AssumeRole` into the target role, write the returned STS credentials into an **isolated temporary CLI home**, call `ve` with explicit `--profile`, and delete the temporary home with finally-style cleanup. This detour exists because `ve` prefers a local profile over env STS tokens, so identity cannot be switched by env vars alone.
- **Do not** expand the CLI exception into a general escape hatch. When a future provider version adds a resource for one of the exception objects, prefer migrating it to path 1. Re-check the provider resource list before assuming an object still needs the CLI path.
- **Readiness, not setup.** Right before each cross-account phase, confirm the selected identity path can reach the target `OrganizationAccessControlRole` (§4 of preflight). If it cannot, stop and return to the credential guidance in preflight.

### Step 4: Generate the Summary Report

At the end of a `landing-zone-setup` run, always generate an HTML summary report:

- Template: `./skills/volcengine-landing-zone/assets/html/landing-zone-setup-report-template.html`
- Output: `./volcengine-landing-zone-workspace/outputs/landing-zone-setup-report.html`
- Trigger timing: after all five phases finish, or when the run ends because of a blocker, scope reduction, or a user pause.
- The report must include at least per-phase execution details, key delivered files, manual follow-up items, and recommended next steps.
- After the report is produced, handle it under G4 by opening or delivering it first, then telling the user to review it.

## Exception Recovery

- When `ConcurrentException`, partial success, or inconsistent state appears, reconcile first and regenerate the plan later. Do not immediately call the whole run a total failure.
- Report only confirmed completed items, real blockers, and whether another write confirmation is needed.
- Do not move into the next phase until the current phase is settled.
