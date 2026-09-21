# Preflight Checks

This file defines the shared preflight checks for `volcengine-landing-zone`.

## 1. Tool Checks

```bash
which terraform && terraform version
which ve && ve version
which python3 && python3 --version
```

- If `ve` is unavailable, prefer the latest installation instructions from the official README instead of maintaining fixed install steps inside this skill.
- Official README: <https://github.com/volcengine/volcengine-cli/blob/master/README.MD>

## 2. Credential Checks

This skill does not create or expose long-lived credentials. It helps the customer establish a supported authentication path and verifies that path before execution. Everything owned by the CLI or the Provider — authentication paths, exact config fields, default config file paths, precedence, the `assume_role` schema, and credential-combination validation — drifts with tool/provider versions, so **do not restate it here; read it at run time from:**

- Volcengine CLI README: <https://github.com/volcengine/volcengine-cli/blob/master/README.MD>
- Volcengine Terraform Provider README: <https://github.com/volcengine/terraform-provider-volcenginecc>

Fixed decisions this skill keeps (they need no runtime lookup):

- **Reuse the customer's existing authentication style** when it is usable. If no credentials are configured, recommend `ve login` first using the flow appropriate to the current runtime, then configure Terraform to reuse the resulting profile according to the current Provider documentation. Use another supported authentication path only when the customer prefers it or the package/provider cannot consume that profile.
- Record once during preflight and reuse for the whole run: `region`, the chosen `ve` CLI auth path, the Terraform credential source, the Terraform runtime env shape, the profile name and optional config file path when profile-based, and whether a session token is required.
- When a profile is the source, follow the provider README for how that version consumes profile credentials. Current provider versions support a profile source together with cross-account `assume_role`; when the version in use does support it, a profile-based run no longer has to be rewritten into env vars just to cross accounts. If a given version still cannot, resolve the profile's current values into the provider's runtime env form before `terraform init/plan/apply` as a compatibility fallback, carrying the fields unchanged (no base64-decode, no transformation). Do not assume `VOLCENGINE_PROFILE` is always consumed reliably by the provider.
- Never write long-lived credentials inline into Terraform files unless the customer explicitly asks and accepts the leakage risk.
- Never ask the customer to paste credentials or tokens into chat.
- **Cross-account behavior is execution SOP, not a credential-setup step** — see the setup guidebook's "Cross-account execution model". Preflight's only cross-account job is the AssumeRole readiness check in §4: right before each cross-account phase, confirm the base identity can perform the required `AssumeRole`.

### 2a. `ve` CLI login verification

Before real execution, verify that the selected `ve` credential path is already usable. Which paths exist and how to configure them live in the CLI README — do not enumerate them here.

Fixed rules for this skill:

- If the customer already has a working local auth flow and `ve sts GetCallerIdentity` succeeds, reuse it. Do not force a migration to another auth style.
- If no usable authentication exists, recommend `ve login` first. Use the normal login flow when the runtime can complete it; on a headless or remote agent host, follow the `volcengine-cli` skill's Console Login procedure (`scripts/ve_login_remote.sh`, device code with `--no-browser`). The resulting profile may also be reused by Terraform as described in §2b.

After the selected `ve` auth path is ready, verify it with:

```bash
ve sts GetCallerIdentity 2>&1
```

If this check still fails, stop and ask the user to repair the selected `ve` auth path first, then rerun preflight.

### 2b. Terraform environment setup

The provider's supported authentication paths, config fields, default config path, and precedence live in the Terraform Provider README — read them there, do not restate them here. The source→runtime normalization rules are in §2 above and are not repeated here.

- Prefer reusing the profile produced by `ve login` when no prior Terraform credential source exists. Configure the Provider to consume that profile according to the current documentation. A profile source may also be combined with cross-account `assume_role`; only choose another supported source or normalize profile values into the runtime environment when the package/provider cannot consume the profile directly. Keep actual values outside the repository and outside chat.
- Verify Terraform readiness with a read-only provider check such as `terraform plan`. On a missing-credential or expired/invalid-credential error, guide the user to refresh the **selected Terraform auth path**, then restart from preflight.

## 3. Execution Context Checks

> Path anchors: any `./skills/volcengine-landing-zone/...` and `./volcengine-landing-zone-workspace/...` path in this file or elsewhere resolves through the `Path Anchors` section in `SKILL.md` as `${SKILL_ROOT}/...` and `${WORKSPACE_ROOT}/...`. Do not depend on process cwd.

- Confirm that `./skills/volcengine-landing-zone/assets/blueprints/` exists and contains the blueprints required for this run.
- Confirm that `./skills/volcengine-landing-zone/references/landing-zone-setup/contract.schema.json` exists.
- If the flow will enter `04-log`, confirm that `./skills/volcengine-landing-zone/assets/blueprints/landing-zone-setup/04-log/tos_activate.py` exists.
- Confirm that `${WORKSPACE_ROOT}/` is writable; create it automatically with mode `0700` if it does not exist.
- **Blueprint source provenance (before copying or reusing any execution package).** This applies equally to setup phase directories and to account-factory/solution run directories. Beside each package's `.tf` files, keep a small `blueprint-source.json` recording where the package came from (built-in skill, git URL + resolved commit, or local dir), the chosen `update_mode` (`pinned` by default, `follow-source` only when the user opts in), and a per-file SHA-256 baseline of the source **before** customer edits or variable injection. Use a resolved commit as the version only when the copy actually matches that revision; otherwise use a content digest. Do not fabricate git lineage from the enclosing repo's HEAD or a plugin version.
  - Before reusing a copy, compare three things: the recorded baseline, the current execution files, and — only when considering an update — the candidate source.
    - Execution files match the baseline and the source is unchanged: reuse as-is (and confirm any saved plan is still applicable).
    - Source changed: in `pinned` mode, report the available update and let the user keep the pin or upgrade; in `follow-source` mode, refresh automatically only when the copy has no local edits. Show added/changed/removed files before upgrading.
    - Execution files were edited, removed, or added locally: treat as customizations, keep them, never silently overwrite.
    - Record missing, malformed, or unknown: treat provenance as `unknown` — this is not evidence the code is stale or that resources must be recreated. Compare read-only, then offer keep-as-legacy-pin or upgrade. An older workspace-root record is a hint, not an authoritative per-package record.
  - Freeze one source snapshot through the whole operation (plan → G2 → apply → recovery); a retry or new user message is not a new plan cycle. Only an explicit upgrade starts a new cycle.
  - Upgrading changes local blueprint files only — never state or cloud resources. Preserve `.terraform/`, `terraform.tfstate*`, `.terraform.lock.hcl`, user tfvars, and architecture/context records; back them up first. Refresh only source-owned files, invalidate saved plans and their G2 approvals, then `terraform init` + `validate` (keep the provider lock; `init -upgrade` only for a reviewed dependency bump) and generate a new plan. A retained state does not guarantee a no-op apply. Any cloud change remains behind G2.
- Confirm that `${WORKSPACE_ROOT}/confirmed-architecture.json` exists, matches the runtime contract, is mode `0600`, and still has the SHA-256 digest associated with the G1 confirmation.
- If `${WORKSPACE_ROOT}/landing-zone-context.json` already exists, verify that it contains no sensitive values, is mode `0600`, and still matches the confirmed architecture plus the current Phase 01 state lineage/serial. Delete and rebuild this cache when stale; do not edit individual fields in place.
- Built-in blueprint sources inside the skill are read-only in the execution chain. See G3. Custom changes must land only in workspace execution copies.
- Runtime directories such as `account-factory/baseline-plans/`, `account-factory/baselines/`, and `account-factory/runs/` may be created automatically.
- Keep runtime JSON, tfvars, state, saved plans, and sensitive deliverables at mode `0600`.

## 4. Path-Specific Extra Checks

- `Consulting and Solution Design`
  - Under G5, this path is read-only: explain concepts, ordering, value, and recommendations only. Do not start any real execution action such as preflight, Terraform environment setup, blueprint sync, or writes.

- `Initial Landing Zone Setup`
  - Under G1, confirm that solution confirmation is already complete, meaning the solution document has been displayed and the user has confirmed it, before entering further preflight.
  - Run `ve organization DescribeOrganization` first. If the organization already exists, then run `ve organization ListOrganizationalUnits --body '{}'` to fetch the root OU.
  - If it returns `RecordNotExists` or a similar `organization not exists`, treat that as the normal initial state and record the Phase 01 G2 bootstrap requirement. Preflight is read-only and must not create the organization.
  - Use the complete `${WORKSPACE_ROOT}/confirmed-architecture.json` for both the default and custom branches. The standard skill path never leaves an executed workspace using `organization_architecture = null`.
  - Verify that enabled capabilities have their required selectors/roles: finance and identity need non-empty target sets, log needs `log_archive`, and network needs `network`.
  - When the organization already exists, recursively scan OUs according to that confirmed tree. Use parent-scoped traversal such as `ListOrganizationalUnitsForParent` with pagination for nested custom trees; do not search only the six default names.
  - Inventory current organization accounts as well as OUs. Match OUs by exact parent path plus name, and accounts by an explicit ID or unique exact account name. Treat duplicate matches, wrong parents, and wrong account placement as conflicts rather than guessing or moving objects.
  - Inspect the current `01-organization` Terraform state before discovery results are injected. Keep already-managed instances managed; populate generic `existing_ou_ids` / `existing_account_ids` only for matching live objects outside the current state.
  - Ask the user for an ID only when the current organization cannot be resolved uniquely. Discovery is read-only and must not move, rename, invite, delete, or retire existing objects.
  - Before write confirmation, verify the target shape does not exceed the service limits (five OU levels and 20 OU nodes) and account creation will remain within the current organization quota.

- `Account Creation and Baseline Setup`
  - Before account creation, check that the minimum account-creation input is complete.
  - For `account create`, resolve a dedicated `run_id` first and execute from `account-factory/runs/<run_id>/account-create/terraform/`, not from the read-only asset source or a shared workspace root.
  - Before baseline creation, confirm that `account-factory/baseline-plans/` can be created and written.
  - Before baseline apply, confirm that the target `*.baseline.json` exists in `account-factory/baseline-plans/` and conforms to `references/account-factory/baseline.schema.json`.
  - When applying a baseline, pass `workspace_root` explicitly and confirm that it points at `./volcengine-landing-zone-workspace/`.
  - For `account create`, confirm that execution will happen in `account-factory/runs/<run_id>/account-create/terraform/` and that the run artifacts can be reused for later recovery or baseline continuation.
  - For `baseline apply`, confirm that execution will happen in `account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/` and not in a shared root.

- `Solution Deployment`
  - Confirm the package source is resolvable and materialize it under `${WORKSPACE_ROOT}/solution-deployment/packages/<name>/`.
  - Resolve the package entrypoints, required tools, declared targets, inputs, and writes.
  - For every Terraform target, resolve either provider role assumption or a runtime credential/profile that already represents the target. Do not ask the user to choose when the package and runtime context make the strategy clear.
  - For a verified member account in the current enterprise organization, when cross-account role assumption is required and no role is specified, use `trn:iam::<account-id>:role/OrganizationAccessControlRole`. Do not infer this role for an account outside the current organization.
  - Verify read-only that each effective Terraform identity resolves to its declared target before planning any write. Stop on an unverifiable or mismatched target-to-identity mapping.
  - Confirm execution will happen under `solution-deployment/runs/<run_id>/`, reuse-first, not in a shared root.

- `Cross-account execution phases`
  - Do not block earlier global preflight steps just because `AssumeRole` is not yet available.
  - Check cross-account `AssumeRole` suitability only right before entering `04-log`, `05-network`, or a cross-account networking module inside baseline apply.
  - Readiness can be satisfied by any path that reaches the confirmed target account — the Terraform provider's `assume_role` with a base identity from env credentials or a profile, or an equivalent profile-based scheme. Stop only when no path can establish an identity that reaches the confirmed target; in that case explain that the current base identity cannot assume into the target `OrganizationAccessControlRole` and let the user supply one that can (for example an IAM sub-user with `STSAssumeRoleAccess`).

- `Failure Recovery`
  - Confirm the failure point, the latest execution artifacts, and the current resource state first.
  - If the issue involves `ConcurrentException`, partial success, or state drift, reconcile first and regenerate a plan later.

## 5. Failure Handling

- If any required check fails, stop real execution.
- Explain the problem first, then give a repair suggestion. After repair, restart from preflight.
- A missing directory is not automatically a failure. Treat it as a real blocker only when blueprints cannot be populated, the workspace cannot be created, the runtime root is not writable, or results cannot be written.
- `DescribeOrganization` or `ListOrganizationalUnits` returning `organization not exists` is not a preflight failure. It routes Phase 01 into the separately confirmed G2 bootstrap branch.
