# Account Factory Workflow

Use this guidebook to create standardized accounts inside the Landing Zone and optionally apply baselines after account creation.

## Core Principles

- The main workflow is always account creation. Baseline is an optional enhancement, not a prerequisite.
- Stepwise pause mode is enabled by default. Do not chain account creation, baseline selection or creation, and baseline apply into one uninterrupted long run.
- Account creation must determine OU placement, finance relationship, and tags. Baseline handles only standard configuration after the account exists.
- Baseline execution prefers Terraform first and uses `ve` CLI only when supplementation is necessary.
- Any `ve` CLI supplementation must follow the real parameter contract of the action. Do not assume every action supports the same `--body` shape.
- When multiple baselines are used together, merge them in the user-selected order. Later selections override earlier ones.

## Checklist Conventions

If tasklists or checklists are available, account factory should be represented inside the unified six-step `volcengine-landing-zone` checklist with `06-account-factory` as the entry.

- When skipped steps can remain visible, prefer to keep the full six-step structure and mark the first five steps as skipped.
- If showing skipped steps is not a good fit, create at least one clearly named entry called `06-account-factory`.
- After entering account factory, it is recommended to create a three-step sub-checklist: `Build Account Baseline`, `Create Account`, and `Apply Baseline`.
- Keep the three-step structure even when this run does not need a baseline. Mark the related steps as skipped instead of deleting them.

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

The general rules come from [../preflight-checks.md](../preflight-checks.md). This path focuses on confirming:

- The selected `ve` credential path is usable for account-factory CLI actions.
- The selected Terraform credential source is already normalized into the standard provider runtime environment-variable form documented in the Terraform Provider README at <https://github.com/volcengine/terraform-provider-volcenginecc>. A local profile may still be the credential source, but it should not be treated as the only recommended Terraform execution form.
- The minimum input for account creation is complete.
- Baseline-related directories can be created automatically.
- If a baseline must be applied, the target `*.baseline.json` execution plan exists and conforms to `baseline.schema.json`.
- If `terraform plan` reports `Either (AccessKey and SecretKey) or Profile must be provided`, or fails with expired/invalid credential errors, treat it as the selected Terraform auth path needing setup or refresh, then restart from preflight after it is ready again.

## Standard Flow

The default rhythm is: explain before execution -> summarize results after execution -> confirm again before the next task.
`Create account` and `apply baseline` are each their own task. Each triggers G2, and write actions inside the task run continuously without per-write prompts. Authorization does not carry across tasks because of G6.

### 1. First-Round Minimum Input

Collect only the required input for account creation in the first round:

- `account_name`
- `show_name`
- `target_ou_id`
- `account_tags`

Delay the following until they are truly needed:

- `financial_relation_type`
- `financial_relation_auth_list_str`
- `network_account_id`
- `transit_router_id`
- `transit_router_resource_share_name`

### 2. Confirmation Before Creation

Before real creation, show the account summary to the user and ask only for the still-missing variables that are truly required to continue.

- If the finance relationship is not yet clear, then ask for `financial_relation_type` and, when required, `financial_relation_auth_list_str`.
- If `financial_relation_account_alias` is not specified, it may default to `account_name`. When the default alias conflicts, the blueprint automatically retries once by appending the account ID suffix. If the user explicitly provided an alias and it conflicts, stop and ask the user to rename it.
- When the network baseline is enabled, require explicit values for `workload_vpc_cidr`, `workload_subnet_cidr_az_a`, and `workload_subnet_cidr_az_b`. Do not auto-fill fallback CIDRs.
- When the built-in network baseline is enabled, also require `network_account_id`, `transit_router_id`, `transit_router_resource_share_name`, `transit_router_dmz_public_route_table_name`, `transit_router_egress_route_table_name`, and `network_vpc_attachment_id`. These should come from the already completed `05-network` outputs rather than user guesswork.
- Describe baseline briefly in business language and make its optional nature clear. Do not expand internal implementation details at this stage.

Then ask the user to choose:

- create the account only
- create the account and select an existing baseline
- create the account and create a baseline now

Then stop under G2/G6 and wait for explicit confirmation for the `create account` task.

### 3. Select or Create a Baseline

When selecting an existing baseline:

- scan `account-factory/baseline-plans/`
- list only `*.baseline.json`
- support multi-select

When creating a baseline on the spot:

- if the customer asks for a **custom** baseline (anything beyond the built-in packages), first run **Gate 0 — Provider resource support check** (see "Authoring a baseline package" below): verify the `volcenginecc` provider supports every required resource. If any required resource is unsupported, tell the customer it is not supported for now and do not generate the baseline `.tf`.
- the currently supported built-in baseline package is `network-cross-account-connectivity`
- explain first that this baseline package adds the new workload account into the existing shared TR scope and then connects that workload account into the enterprise shared network
- when the user needs a starting point, reuse the example file `references/account-factory/examples/network-cross-account-connectivity.baseline.json` and replace its placeholders with the current run values
- ask whether existing workspace baseline packages should also be included
- generate baseline JSON from `baseline.schema.json`
- ask the user to confirm the baseline plan name, file name, variables, and baseline summary
- when the file name conflicts, ask the user to rename it

#### Authoring a baseline package (`.tf` source)

##### Gate 0 — Provider resource support check (mandatory before authoring any custom baseline)

Before writing any `.tf` for a custom (non-built-in) baseline, first confirm that the `volcenginecc` Terraform provider actually exposes a resource for every cloud object the baseline needs to manage. Never assume support — verify it.

- Determine the concrete resources the baseline must create (for example a VPC, a subnet, a transit-router attachment, a resource-share association, a service-linked role).
- For each one, check whether the provider declares a matching `volcenginecc_*` resource type. Use the provider's published resource list as the source of truth, in this priority order:
  1. `terraform providers schema -json` from an initialized package, then look for the resource name (most authoritative — reflects the exact pinned version).
  2. The provider documentation / Terraform Registry resource index for `volcengine/volcenginecc`.
  3. The provider source repository (`terraform-provider-volcenginecc`) resource registration list.
- **If every required resource is supported:** proceed to author the baseline `.tf` using Template A or Template B below.
- **If any required resource is NOT supported:** stop. Tell the customer plainly that this baseline is **not supported for now** because the `volcenginecc` provider has no Terraform resource for the missing object, and do **not** generate baseline `.tf`. Do not silently fall back to inventing a `local-exec` + `ve` CLI workaround for a customer's ad-hoc custom baseline.
  - The sanctioned built-in `local-exec` exceptions are the patterns already implemented in `network-cross-account-connectivity/main.tf`: network-share scope update, service-linked-role bootstrap, and shared transit-router route-table binding / propagation repair against an already-created center TR. Reuse only those established built-in patterns when they match the same ownership boundary; do not generalize them into a catch-all CLI escape hatch for unsupported resources in a customer's ad-hoc custom baseline.

A baseline package is self-contained: the agent writes only `terraform.tfvars.json` and runs `terraform apply` — it never generates a central orchestrator root. The target account is decided by the package's own provider. Pick exactly one of the two templates below based on where the baseline deploys.

**Template A — deploy into a newly created member account (needs cross-account AssumeRole).** Copy the `network-cross-account-connectivity` package as the canonical reference. The provider carries `assume_role` and resources reference it explicitly:

```hcl
# providers.tf
provider "volcenginecc" {
  alias  = "member"
  region = var.region

  endpoints = {
    sts = "sts.volcengineapi.com"
  }

  # Base credential comes from the Terraform runtime environment selected for the run.
  # account_id decides which member account; a wrong account_id fails at AssumeRole.
  assume_role = {
    assume_role_trn              = "trn:iam::${var.account_id}:role/OrganizationAccessControlRole"
    assume_role_session_name     = "af-<baseline>-baseline"
    assume_role_duration_seconds = 3600
  }
}
```

```hcl
# main.tf — every resource pins the member provider
resource "volcenginecc_vpc_vpc" "example" {
  provider = volcenginecc.member
  # ...
}
```

Any `local-exec` in Template A starts from the current `ve` identity validated from the selected credential path. If the action targets the member account, self-assume into that member account (see the SLR pattern in `network-cross-account-connectivity/main.tf`): `ve sts AssumeRole` → write an isolated temporary CLI home → identity-probe gate on `account_id` with explicit `--profile` under that home → idempotent CLI write with the same explicit `--profile`. If the action targets the network account's existing TR share, self-assume into the network account instead and update only the current member account's share scope.

**Template B — deploy into the current management account (no AssumeRole).** Simply omit the `assume_role` part. Use a **bare default provider** (no `alias`, no `assume_role`, only `region`); the base credential acts directly on the current management account, and resources need no `provider =` line:

```hcl
# providers.tf
provider "volcenginecc" {
  region = var.region
}
```

```hcl
# main.tf — uses the default provider, no provider = ... needed
resource "volcenginecc_vpc_vpc" "example" {
  # ...
}
```

Any `local-exec` in Template B calls `ve` through the selected `ve` credential path validated in preflight.

Selection rule: **target is a newly created member account → Template A; target is the current management account → Template B.** Do not add an `enable_assume_role` toggle or `dynamic "assume_role"` block — choose one template at authoring time to keep the package free of runtime conditional logic.

#### Baseline package security checklist

- Any sensitive output (access keys, secret keys, tokens, passwords) must set `sensitive = true`. Avoid emitting long-lived secrets as outputs at all where possible.
- For cross-account identity, use the `OrganizationAccessControlRole` delegation (Template A). Do not create a long-lived IAM user + access key inside a baseline to obtain admin power.
- When attaching a system policy, use the exact policy name `AdministratorAccess` (not `AdministerAccess`) and verify against the provider/API docs.
- Keep base credentials out of the package and off the command line. Terraform reads them from the selected runtime auth path, and `ve` CLI actions use the selected `ve` credential path or a short-lived AssumeRole credential scoped inside the package.


After selection or creation is complete, summarize in user-facing language what was selected or created and what will run next, then wait for confirmation to continue.

### 4. Create the Account

- Resolve the account-factory `run_id` before the first write by **reuse-first**, not by blindly creating a new directory. Before creating anything, scan `account-factory/runs/` for an existing run whose `run.json` records the same account-create intent and is not yet completed.
  - Treat the account-create intent as the tuple `account_name + show_name + target_ou_id`. When those values match and the recorded task is still `failed`, `in_progress`, or otherwise unfinished, prefer to reuse that `run_id`.
  - If a partial apply already produced an `account_id`, treat the matching `account_id` as the strongest reuse signal and continue from that run even when later inputs such as baseline selections have changed.
  - A credential failure before or during Terraform plan/apply is the typical zero-state failure: no new account resource has landed yet, so the same `run_id` should be reused after the credential path is repaired.
  - Only create a new run directory under `account-factory/runs/<run_id>/` when no reusable unfinished run matches the same account-create intent, or the existing run artifacts are missing or proven unusable. A new `run_id` should include a timestamp plus account identity, for example `<timestamp>-<account_name>-<target_ou_id>`.
- Ensure an isolated execution directory exists under `account-factory/runs/<run_id>/account-create/terraform/`. When the directory is new, copy the built-in `account-create` package into it and write the resolved `terraform.tfvars.json`. When reusing a run, keep the existing `.terraform/`, state, and plan outputs, and refresh `terraform.tfvars.json` only when the resolved inputs actually changed.
- Initialize or refresh the run artifacts before planning account creation: `run.json` for overall task state, `context.json` for resolved inputs and later outputs, and `account-create/status.json` for the current account-create step.
- Run `terraform init`, variable preparation, and `terraform plan -parallelism=1 -out=tfplan` in the background inside `account-factory/runs/<run_id>/account-create/terraform/` with the selected Terraform credential source already normalized into runtime environment variables in the agent process.
- If an account-creation Terraform command fails with missing-credential or expired/invalid credential errors, treat it as the selected Terraform auth path needing setup or refresh, then restart from preflight after it is ready again.
- Under G2, confirmation for this task covers the account creation itself plus its follow-up CLI write actions. Do not interrupt for each individual internal write.
- After confirmation, run `terraform apply -parallelism=1 tfplan` in the same isolated account-create run directory with the same normalized Terraform runtime environment.
- If the account has already been created successfully but post-create CLI steps such as finance relationship or tags fail, treat it as partial success. Do not delete the account and do not rebuild from scratch.
- For those failures, inspect the current state first, then backfill the failed `null_resource` steps through another `plan/apply` in the same run directory instead of rebuilding a shared workspace copy.
- After each significant step, refresh `account-create/status.json`, merge `terraform output -json` into `context.json`, and update `run.json` so the same `run_id` can continue into baseline apply later if needed.

Read-after-write validation and CLI conventions:

- After finance relationship creation, validate with `ve billing ListFinancialRelation`.
- After account tags are written, validate with `ve organization ListTagResources`.
- Even if `CreateFinancialRelation` returns a duplicate or already-exists style result, do not treat it as success without read-after-write validation.
- Finance relationship actions currently use `--body`.
- Tag-related actions currently use numbered `.1/.2` style parameters instead of a JSON body.
- The `CreateFinancialRelation` body should be organized with `SubAccountID`, `Relation`, optional `AuthListStr`, and optional `AccountAlias`. Follow `--help` for the exact field names.
- Treat `AccountAlias` conflicts as alias uniqueness issues, not as an `already exists so skip it` case.

After account creation completes, follow G2/G6: output the result summary first, then ask whether to continue with baseline. Do not automatically enter the next step just because the user previously selected a baseline path.

### 5. Apply the Baseline

The baseline is **not** applied by a central orchestrator root. The agent reads one or more baseline execution plans, turns them into a run-level execution queue, and applies the referenced baseline packages serially. Baseline apply should reuse the same account-factory `run_id` that already captured `account create` whenever that run is the one being continued.

- Read the selected `*.baseline.json` files directly, merge them in order (later selections override earlier declarations with the same baseline `name`), and validate against `references/account-factory/baseline.schema.json`.
- Resolve all `{{ variable_name }}` references against the merged `variables` block plus the run context. The run context includes at least the `account-create` outputs from `account-factory/runs/<run_id>/account-create/terraform/` and outputs from previously completed baselines in the same run.
- Identify the final enabled baselines and variables first. Ask for missing minimum variables only for baseline packages that are actually enabled.
- Resolve the run directory by **reuse-first**, do not blindly create a new one. When the current baseline apply is continuing from a just-finished or partially finished account-create run, reuse that same `run_id` first. Otherwise, before creating anything, scan `account-factory/runs/` for an existing run whose `run.json` targets the **same `account_id` and the same set of enabled baselines** and is **not yet completed** (status is `failed`, `in_progress`, or otherwise unfinished). If such a run exists and its artifacts are still consistent, **reuse that `run_id`** and resume from the recorded step (see `references/failure-recovery.md`) instead of starting a new run.
  - A credential failure (provider auth missing/expired, `Either (AccessKey and SecretKey) or Profile must be provided`, AssumeRole failure) is the typical **zero-state** failure: Terraform usually wrote no state, so the previous run directory is safe to reuse. After the user fixes credentials, **resume the same `run_id`** rather than spawning a new one.
  - Only create a **new** dedicated run directory under `account-factory/runs/<run_id>/` when no reusable unfinished run is found, or the existing run's artifacts are missing or proven unusable. A new `run_id` should include a timestamp plus account identity, for example `<timestamp>-<account_name>-<account_id>`.
- When the run directory is **newly created**, initialize run state files before the first baseline apply. When **reusing** an existing run, load the existing files instead of overwriting them, and continue from the recorded state.
  - `run.json` — overall workflow state, selected plans, execution queue, current step, final summary
  - `context.json` — resolved variables, account-create outputs, and accumulated baseline outputs
  - `account-create/status.json` — account-create execution state
  - `baselines/<baseline-name>/status.json` — per-baseline execution state
- For each enabled baseline package, ensure an isolated execution directory exists under `account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/`. When the directory is new, copy the selected package into it and write `terraform.tfvars.json` with the resolved inputs. When reusing a run, keep the existing `.terraform/`, state, and plan outputs, and only refresh `terraform.tfvars.json` if the resolved inputs actually changed.
- Resolve package sources by name. Check `account-factory/baselines/<package>/` in the workspace first; if it does not exist, fall back to the built-in `blueprints/account-factory/baselines/<package>/`.
- Use `depends_on`, then optional `order`, then declaration order to derive the serial execution queue. Do not run dependent baselines before their prerequisites succeed. The target account is fixed by each baseline package itself and is not configurable in the baseline plan.
- Each baseline package owns its own provider wiring, and the target identity is decided **inside the package's provider**. The runtime supplies the Terraform base credential through normalized environment variables, and that base identity initiates any package-level `assume_role`. Whether the package targets the management account or a member account is fixed by whether the package's provider declares `assume_role` (see "Authoring a baseline package" above). If a member-account package's provider declares `assume_role` but the Terraform base credential cannot assume the target role, AssumeRole fails at plan/apply and no resource is created in the wrong account; stop and ask the user to switch to a credential with the necessary `STSAssumeRoleAccess`.
- If a member-account baseline package needs a service-linked role (for example `ServiceRoleForTransitRouter`), `local-exec` starts from the selected `ve` credential path, then runs `ve sts AssumeRole` into the member account, writes an isolated temporary CLI home, gates on `HOME=<temp_home> ve sts GetCallerIdentity --profile <temp_profile>` to confirm it landed in the target `account_id`, and creates the role idempotently with the same explicit `--profile`. Treat `RoleAlreadyExists` as already authorized. For a management-account package (provider without `assume_role`), call `ve` directly through the selected `ve` credential path.
- In the background, run `terraform init`, `terraform plan -parallelism=1 -out=tfplan`, and `terraform apply -parallelism=1 tfplan` inside each baseline package directory with the selected Terraform credential source already normalized into runtime environment variables in the agent process. After each step, update `status.json`, merge `terraform output -json` into `context.json`, and refresh `run.json`.
- If Terraform reports missing or expired/invalid credentials, stop and guide the user to refresh the selected Terraform auth path first.
- Show only a concise impact summary to the user. Do not expand internal state-file shapes or package-copy mechanics unless troubleshooting requires it.
- G2 applies to this task: one confirmation covers the current baseline apply and internal writes run continuously.

After baseline apply completes, follow G6: output the result summary and any manual follow-up items first, then explain whether to continue with further account configuration or start the next account-factory run.

## Result Output

Final output follows the unified result summary format in [../interaction-contract.md](../interaction-contract.md) and must include at least:

- basic information of the new account
- which baselines were used
- which baseline segments were applied automatically
- which items still require manual handling
- the recommended next step
