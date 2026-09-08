# Failure Recovery Workflow

This file handles the `Failure Recovery` main path and applies to:

- `landing-zone-setup`
- `account-factory account create`
- `account-factory baseline apply`

## Core Principles

- By default, repair only the failed portion. Do not require a full rerun of the entire chain.
- Reconcile the current state first, then decide whether to backfill, retry, or stop.
- For cases such as `ConcurrentException`, partially landed resources, or inconsistent state, prefer a `partial success` interpretation instead of immediately calling the entire run a failure.
- Any real write action during recovery triggers G2. Present the impact summary first and get confirmation.
- Report only confirmed completed items, real blockers, and recommended next steps to the user. Do not expand internal troubleshooting details.
- For `account-factory account create`, recovery should start from the existing run directory under `account-factory/runs/<run_id>/` instead of falling back to a shared workspace copy.
- For `account-factory baseline apply`, recovery starts from the existing run directory under `account-factory/runs/<run_id>/` instead of rebuilding a new orchestration flow from scratch.

## Standard Flow

### 1. Identify the Failure Scope

- First determine whether the failure occurred in `landing-zone-setup`, `account-factory account create`, or `account-factory baseline apply`.
- Reuse the latest available workspace, plan files, output files, and read-only inspection results whenever possible.
- If the user only describes an error symptom, fill in the minimum context first: failed path, failed phase, latest error message, and whether any resources have already landed.
- For `account-factory account create`, identify the exact `run_id` and last recorded Terraform step from:
  - `account-factory/runs/<run_id>/run.json`
  - `account-factory/runs/<run_id>/context.json`
  - `account-factory/runs/<run_id>/account-create/status.json`
  - Reuse-first rule: first look for an unfinished run whose `run.json` records the same `account_name + show_name + target_ou_id`; if an `account_id` has already been assigned, that matching `account_id` becomes the strongest reuse signal.
- For `account-factory baseline apply`, identify the exact `run_id`, failed baseline name, and last recorded Terraform step from:
  - `account-factory/runs/<run_id>/run.json`
  - `account-factory/runs/<run_id>/context.json`
  - `account-factory/runs/<run_id>/baselines/<baseline-name>/status.json`

### 2. Reconcile the Current State in the Background

- For Terraform paths, first reread the current state, outputs, and latest plan context from the existing workspace.
- For steps supplemented by `ve` CLI actions, first use read-only APIs to confirm whether the resource has already been created, bound, or written successfully.
- If partial success is possible, do not rerun a same-name create action immediately. Confirm the current state first.
- For `account-factory account create`, inspect the existing execution copy under `account-factory/runs/<run_id>/account-create/terraform/` first. Reuse its `.terraform/`, state, plan outputs, and generated `terraform.tfvars.json` when they are still consistent with `account-create/status.json`.
- For `account-factory baseline apply`, inspect the existing execution copy under `account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/` first. Reuse its `.terraform/`, state, plan outputs, and generated `terraform.tfvars.json` when they are still consistent with `status.json`.

### 3. Decide the Recovery Strategy

- If the issue is only a missing prerequisite such as credentials, permissions, unwritable directories, or an unopened service, stop write actions first and tell the user to fix that prerequisite.
- If resources have partially landed, prefer incremental repair of incomplete items. Do not delete existing resources by default.
- If the current state has clearly drifted from the intended state, regenerate a plan before deciding whether to continue the repair.
- If the issue is a naming conflict, uniqueness conflict, or cross-account authorization problem, treat it as its own blocker instead of calling the entire blueprint failed.
- For account-create runs, do not regenerate a fresh shared execution copy. Recovery should continue from the recorded `run_id` whenever the existing run artifacts are still usable.
- For account-create runs, credential failures before account creation lands are still resumable from the same `run_id`; do not allocate a second run just because the first failure happened before state existed.
- For baseline runs, do not regenerate package copies or a new run directory unless the existing run artifacts are missing or proven unusable. Recovery should continue from the recorded run state whenever possible.

### 4. Regenerate the Recovery Plan

- When needed, rerun `terraform plan`, `terraform plan -refresh-only`, or equivalent read-only checks to confirm what actions are still truly needed.
- Show the user only the post-recovery impact summary. Do not narrate internal refreshes, state extraction, or script reassembly line by line.
- If the recovery plan still contains real write actions, G2 applies: present the impact summary, get confirmation, then continue.
- If `account-factory account create` failed after the Terraform account resource landed but follow-up CLI writes did not, replan only the remaining `null_resource` work in the same run directory. Do not recreate the account.
- If `account-factory baseline apply` failed mid-queue, replan only the failed baseline and any downstream baselines that depend on it according to `run.json`. Do not restart already completed independent baselines.

### 5. Output the Recovery Conclusion

- Final output must follow the result summary format from `interaction-contract.md`.
- Clearly distinguish which items were already complete, which items were repaired successfully in this run, and which items still require manual handling.
- If recovery completes and the main flow can continue, explicitly tell the user which path they can return to next.
- For account-factory recovery, also state whether the original run remains resumable from the same `run_id` or whether a fresh baseline apply is now required.

## Common Recovery Scenarios

- **Concurrency conflicts**: reconcile the current state first, then replan. Do not immediately rerun apply.
- **Partial success**: split completed items out of the failed list and repair only what remains.
- **Missing prerequisites**: tell the user to repair the prerequisite first, then re-enter through the recovery path.
- **Enterprise organization creation hits `NoPermissionOnVerificationError`**: recognize this as missing enterprise real-name verification rather than a normal IAM permission gap. Guide the user to `https://console.volcengine.com/user/authentication/detail/` first, then retry from the `DescribeOrganization` or `CreateOrganization` branch.
- **Insufficient cross-account authorization**: recognize it as a permission problem, stop further writes, and do not misclassify it as a networking or logging blueprint failure.
- **Account create stopped after partial success**: trust `account-factory/runs/<run_id>/account-create/status.json`, Terraform state, and read-only account APIs first; mark the account resource as already complete when it has landed, and continue only with the unfinished finance relationship, tag, or follow-up checks.
- **Account-factory baseline run stopped after partial package success**: trust `baselines/<baseline-name>/status.json` and read-only cloud checks first, mark completed baselines as complete in the recovery summary, and continue only from the failed or blocked baseline onward.
- **Leftover temporary log CLI home from `04-log`**: if the previous run was interrupted in `04-log`, an isolated temporary CLI home directory may still exist. During recovery, detect and clean up the dangling temporary home directory first, then re-enter `04-log` to avoid a dirty execution state.
- **Baseline plan contract drift**: if the run reuses an older `*.baseline.json` that still contains removed fields such as `package_kind` or other schema-invalid data, normalize the plan back to the current `baseline.schema.json` contract before retrying Terraform.
- **Tag, finance relationship, or organization read-only checks disagree with expectations**: trust the read-only API result first and confirm whether any backfill is still needed.
