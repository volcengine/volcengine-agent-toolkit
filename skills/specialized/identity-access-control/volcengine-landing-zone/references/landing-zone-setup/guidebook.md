# Volcengine Landing Zone Setup Guide

Use this file only after the workflow has clearly entered the real execution path for `Initial Landing Zone Setup`. If the user is still consulting, designing, evaluating, or discussing the solution, do not execute from this file. G5 applies.

## Overall Flow

### Step -2: Confirm the Solution First

G1 applies here. Follow the `Hard Gates` section in `SKILL.md`: display the solution confirmation document first, then continue only after the user explicitly confirms it. This file does not restate G1.

### Step -1: Create the Execution Checklist

If the current agent supports tasklists or checklists, create the fixed-order checklist before real execution starts:

1. `01-organization`
2. `02-finance`
3. `03-identity`
4. `04-log`
5. `05-network`
6. `06-account-factory`

Conventions:

- The full setup should keep all six steps by default. Even when only the first five are in scope, it is still recommended to keep the sixth step as the later entry unless the user explicitly excludes account factory.
- Mark a phase as in progress before it starts and completed after it finishes. If scope shrinks, mark it skipped instead of deleting it.
- `06-account-factory` may serve as the entry into the dedicated account-factory tasklist.
- Note that `06-account-factory` is **not** a phase document under `references/landing-zone-setup/`. This directory contains only the five phase documents `01-organization` through `05-network`. The actual entry for the sixth step is [../account-factory/guidebook.md](../account-factory/guidebook.md). Do not look for a nonexistent `06-account-factory.md`.
- The checklist manages pace and status only. Under G6, it does not mean later steps are already authorized.

### Step 0: Preflight Checks

The shared rules come from [../preflight-checks.md](../preflight-checks.md). This path adds only two specific branches.

First-time organization enablement branch:

- Run `ve organization DescribeOrganization` first.
- If the organization already exists, run `ve organization ListOrganizationalUnits --body '{}'` to fetch the root OU.
- If it returns `RecordNotExists` or a similar `organization not exists`, continue with `ve organization CreateOrganization --body '{}'`.
- If `CreateOrganization` returns `NoPermissionOnVerificationError`, recognize it as missing enterprise real-name verification and guide the user to complete verification before retrying.
- After successful creation, fetch the root OU again and use it as `root_ou_id` for `01-organization`.

Existing standard OU auto-discovery branch:

- Before Terraform for `01-organization`, automatically scan `Platform`, `Applications`, and `SandBox` under the root OU.
- If `Applications` exists, continue scanning `Dev`, `Staging`, and `Prod` under it.
- For standard OUs that are detected reliably, inject the corresponding `existing_*_ou_id` before Terraform runs.
- Ask the user for OU IDs only when names are nonstandard, duplicates cannot be resolved uniquely, or the result is unstable.

### Step 1: Prepare the Workspace Execution Copy

> Path anchors are defined in `SKILL.md`: `./skills/...` resolves to `${SKILL_ROOT}/...`, and `./volcengine-landing-zone-workspace/...` resolves to `${WORKSPACE_ROOT}/...`.

- Blueprint source directory: `${SKILL_ROOT}/assets/blueprints/` (that is, `./skills/volcengine-landing-zone/assets/blueprints/`)
- Execution copy directory: `${WORKSPACE_ROOT}/blueprints/` (that is, `./volcengine-landing-zone-workspace/blueprints/`)
- If built-in skill blueprints are missing, stop and tell the user the skill package is incomplete.
- Create the workspace automatically if it does not exist.
- Real execution happens only inside workspace copies. Under G3, built-in blueprint sources remain read-only at all times.

### Step 2: Fill Only the Minimum Variables for the Current Phase

- Ask follow-up questions only when the next phase is actually about to start and some required input is still missing.
- Do not ask again for values that can already be derived from preflight checks, the current environment, previous outputs, or blueprint defaults.
- After a phase finishes, keep reusable results available for later phases.

### Step 3: Execute Phase by Phase

The order is fixed: `01-organization` -> `02-finance` -> `03-identity` -> `04-log` -> `05-network`.

For outward communication, use the user-language fields from each phase document frontmatter instead of dumping directory names and internal output chains. Every phase follows the same rhythm:

1. Explain the phase goal, value, and minimum input before execution. G2 applies.
2. In the background, complete directory preparation, `terraform init`, variable preparation, and `terraform plan`, always with the selected Terraform credential source already normalized into the standard provider runtime environment-variable form documented in the Terraform Provider README at <https://github.com/volcengine/terraform-provider-volcenginecc>. A `ve` profile may still be the source of those values, but should not be treated as the only recommended Terraform execution form.
3. Write actions inside the phase run continuously. G2 means no prompting for each individual write.
4. After execution, output the conclusion in the unified result summary format.
5. If the phase produces a local file, G4 applies.
6. Authorization does not carry automatically into the next phase. See G6.

Execution conventions:

- Use the `ve` credential path validated in preflight for phase-level CLI actions. Reuse the customer's working local auth method when it already passes `ve sts GetCallerIdentity`; do not force `ve login` if another supported method is already in place.
- Run every phase-level `terraform init/plan/apply` with the selected Terraform credential source already normalized into runtime environment variables in the agent process.
- If a phase-level Terraform command fails with missing-credential or expired/invalid credential errors, treat it as the selected Terraform auth path needing setup or refresh, then restart from preflight after it is ready again.
- `01-organization`, `02-finance`, and `03-identity` use `terraform plan/apply -parallelism=1`.
- After `03-identity` produces `identity-login-info.md`, handle it under G4 by opening or delivering it first, then waiting for the user to continue.
- Record key phase outputs and summary-report material continuously in the background. Do not wait until all phases finish and reconstruct everything from memory.

`04-log` specific branch:

- Check TOS state only inside this phase, not earlier in global preflight.
- Before running Terraform for `04-log`, first run `RegisterDelegatedAdministrator` in the organization administrator context. Duplicate or already-exists results may be treated as satisfying the prerequisite.
- Treat delegated-administrator registration as a phase pre-step outside Terraform. The `04-log` blueprint assumes this prerequisite is already satisfied and does not register it again.
- Inside Terraform, assume into the log archive account through `OrganizationAccessControlRole`, obtain temporary credentials, and write them into an isolated temporary CLI home.
- The TOS helper always uses the `cn-beijing` control plane and should converge through `GetAccountStatus` -> optional `ActiveTosSvc` -> repeated `GetAccountStatus` until `Activated`.
- When running `CreateTrail`, `StartLogging`, and `DescribeTrails`, bind the isolated CLI home and pass `--profile <temp_log_profile>` explicitly. After the phase ends, delete the temporary home directory.
- Acceptance must include at least the two read-only checks `GetCallerIdentity` and `DescribeTrails`.
- Check the cross-account `AssumeRole` prerequisite only right before this phase. If the current `ve` identity from the selected credential path cannot perform the required `AssumeRole`, stop and ask the user to switch to an IAM sub-user identity with `STSAssumeRoleAccess`.
- Even when the original Terraform credential source is a local profile, run the phase-level Terraform commands with normalized environment variables rather than relying on `VOLCENGINE_PROFILE` alone for the provider's cross-account `assume_role`.

`05-network` specific branch:

- Check the cross-account `AssumeRole` prerequisite only right before this phase. If the current `ve` identity from the selected credential path cannot perform the required `AssumeRole`, stop and ask the user to switch to an IAM sub-user identity with `STSAssumeRoleAccess`.
- Before sharing the TR, first call `RegisterDelegatedAdministrator` for trusted service `resource_share` in the organization administrator context, using the network account as the delegated administrator. Duplicate or already-exists results may be treated as satisfying the prerequisite.
- Then run `EnableSharingWithOrganization` in the organization administrator context before entering the network-account execution path.
- Then assume into the network account through `OrganizationAccessControlRole`, create an isolated temporary CLI home, and use that isolated home with explicit `--profile` for Resource Share creation and association commands.
- Build the TR resource TRN as `trn:transitrouter:{region}:{network_account_id}:transitrouter/{transit_router_id}` and share it through Resource Share, not through a per-member Transit Router grant rule.
- `05-network` creates or reuses the TR share container and associates the TR resource only. It does not associate the whole organization or any member account principal in this phase.
- When reconciling the share, prefer the idempotent sequence `DescribeResourceShares` -> optional `CreateResourceShare` -> `AssociateResourceShare`.
- Acceptance must include read-after-write verification that the share contains the TR resource in `ASSOCIATED` status. Member-account principals are added later by account-factory.
- Even when the original Terraform credential source is a local profile, run the phase-level Terraform commands with normalized environment variables rather than relying on `VOLCENGINE_PROFILE` alone for the provider's cross-account `assume_role`.
- Before creating the TR VPC attachment, ensure that `ServiceRoleForTransitRouter` already exists inside the network account.
- Prefer the idempotent command `ve iam CreateServiceLinkedRole --ServiceName transitrouter`.
- Treat `RoleAlreadyExists` as already authorized.
- That service-linked role must be created in the network-account context, not accidentally in the management-account context.

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
