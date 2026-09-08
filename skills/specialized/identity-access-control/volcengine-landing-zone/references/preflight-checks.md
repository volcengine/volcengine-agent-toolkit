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

Before recommending any credential setup, first consult the two official references and keep the guidance aligned with what they support:

- Volcengine CLI README: <https://github.com/volcengine/volcengine-cli/blob/master/README.MD>
- Volcengine Terraform Provider README: <https://github.com/volcengine/terraform-provider-volcenginecc>

The goal is to **reuse the customer's existing authentication style** whenever possible instead of forcing one path.

Ask which credential method the customer already uses or prefers for:

- `ve` CLI
- Terraform Provider

Record the selected credential source and runtime form, then reuse them consistently for the rest of the run. At minimum, record:

- `region`
- the chosen `ve` CLI auth path
- the chosen Terraform Provider credential source
- the Terraform runtime env shape that will actually be present during `terraform init/plan/apply`
- profile name and optional config file path when profile-based auth is used as a source
- whether a session token is required

If the customer has no clear preference, use this default:

- `ve` CLI: reuse an already working local login first; if none exists, profile-based auth through `ve configure set` is an acceptable default, following the CLI README at <https://github.com/volcengine/volcengine-cli/blob/master/README.MD>
- Terraform Provider: run Terraform with the standard provider runtime environment-variable form documented in the Terraform Provider README at <https://github.com/volcengine/terraform-provider-volcenginecc>

Profile-based auth remains a supported **source** for Terraform Provider credentials, but it should not be the only recommended runtime form. When the customer already has a stable `ve` login or named profile, prefer to reuse it as the source of truth and standardize Terraform execution into environment variables instead of assuming `VOLCENGINE_PROFILE` will always be consumed reliably by the provider.

Use AK/SK environment variables when the customer prefers shell-scoped credentials. For cross-account Terraform phases that rely on provider-level `assume_role` such as `04-log`, `05-network`, and member-account baseline packages, prefer environment variables even when the original credential source is a `ve` profile. Avoid writing long-lived credentials inline into Terraform files unless the customer explicitly asks for that path and understands the leakage risk.

Record the selected `region` once during preflight and reuse it for the rest of the run.

### 2a. `ve` CLI login verification

Before real execution, verify that the selected `ve` credential path is already usable.

The CLI README supports at least these common paths:

- profile-based config through `ve configure set`
- environment variables

If the customer already has a working local auth flow and `ve sts GetCallerIdentity` succeeds, reuse it. Do not force a migration to another auth style.

For a default profile-based setup, follow the profile-based configuration example in the CLI README at <https://github.com/volcengine/volcengine-cli/blob/master/README.MD> and set the selected profile active before continuing.

When the customer explicitly prefers environment variables for `ve`, follow the CLI README and guide them to export the corresponding variables instead.

If the customer already uses a console-login flow such as `ve login`, keep that path and verify it for **CLI identity only**; do not replace it just because another option exists. Use `ve login --region <region>` only when the customer explicitly chooses that path or already depends on it. On a headless or remote agent host, follow the `volcengine-cli` skill's Console Login procedure (`scripts/ve_login_remote.sh`, device code with `--no-browser`) instead of running `ve login` directly.

After the selected `ve` auth path is ready, verify it with:

```bash
ve sts GetCallerIdentity 2>&1
```

If this check still fails, stop and ask the user to repair the selected `ve` auth path first, then rerun preflight.

### 2b. Terraform environment setup

The Terraform Provider README supports these authentication paths:

- AK/SK credentials from environment variables
- profile-based auth through `profile` / `file_path`, which can also be supplied through `VOLCENGINE_PROFILE` and `VOLCENGINE_FILE_PATH`
- inline provider credentials, which are supported but should not be the default because they write secrets into Terraform configuration

Prefer to mirror the customer's existing operational style at the **source** layer, then normalize the Terraform execution environment into the standard provider runtime environment-variable form documented in the Terraform Provider README at <https://github.com/volcengine/terraform-provider-volcenginecc>. If the customer has no preference, default to reusing an AK/SK-capable credential source such as a named `ve` profile with explicit credentials or existing shell-scoped AK/SK variables.

Treat `ve login` separately: it can prove that CLI identity is already usable, but it must not be described as the Terraform Provider credential source. Terraform runtime credentials must come from explicit AK/SK material or a profile that actually stores those credential fields.

Recommended runtime example: follow the environment-variable form shown in the Terraform Provider README at <https://github.com/volcengine/terraform-provider-volcenginecc>, and keep the actual values outside the repository and outside chat.

If the customer's stable source is a named `ve` profile with explicit credential fields, keep using that profile for CLI operations as needed, but resolve the profile's current credential values into that standard Terraform runtime environment form before `terraform init/plan/apply`. Keep credential fields unchanged when carrying them from the chosen source into runtime. Do not base64-decode any secret field or apply any other transformation. Do not treat provider profile mode as the only recommended execution form for Terraform.

If the customer explicitly prefers Terraform profile mode and the run does not depend on cross-account provider `assume_role`, this is still supported:

```bash
export VOLCENGINE_PROFILE=<profile>
export VOLCENGINE_REGION=<region>
export VOLCENGINE_FILE_PATH=<YOUR_CONFIG_FILE_PATH>   # optional when not using ~/.volcengine
```

The user fills in their own values and runs the commands themselves. The skill records both the credential source and the Terraform runtime env form, then runs Terraform with those normalized environment variables already present in the agent process.

Preflight verifies Terraform readiness with a read-only provider check such as `terraform plan`. If Terraform reports `Either (AccessKey and SecretKey) or Profile must be provided`, or returns expired/invalid credential errors, guide the user to refresh the **selected Terraform auth path** and then restart from preflight.

## 3. Execution Context Checks

> Path anchors: any `./skills/volcengine-landing-zone/...` and `./volcengine-landing-zone-workspace/...` path in this file or elsewhere resolves through the `Path Anchors` section in `SKILL.md` as `${SKILL_ROOT}/...` and `${WORKSPACE_ROOT}/...`. Do not depend on process cwd.

- Confirm that `./skills/volcengine-landing-zone/assets/blueprints/` exists and contains the blueprints required for this run.
- If the flow will enter `04-log`, confirm that `./skills/volcengine-landing-zone/assets/blueprints/landing-zone-setup/04-log/tos_activate.py` exists.
- Confirm that `${WORKSPACE_ROOT}/` is writable; create it automatically if it does not exist.
- Before real execution begins, sync the blueprints into `./volcengine-landing-zone-workspace/blueprints/`.
- Built-in blueprint sources inside the skill are read-only in the execution chain. See G3. Custom changes must land only in workspace execution copies.
- Runtime directories such as `account-factory/baseline-plans/`, `account-factory/baselines/`, and `account-factory/runs/` may be created automatically.

## 4. Path-Specific Extra Checks

- `Consulting and Solution Design`
  - Under G5, this path is read-only: explain concepts, ordering, value, and recommendations only. Do not start any real execution action such as preflight, Terraform environment setup, blueprint sync, or writes.

- `Initial Landing Zone Setup`
  - Under G1, confirm that solution confirmation is already complete, meaning the solution document has been displayed and the user has confirmed it, before entering further preflight.
  - Run `ve organization DescribeOrganization` first. If the organization already exists, then run `ve organization ListOrganizationalUnits --body '{}'` to fetch the root OU.
  - If it returns `RecordNotExists` or a similar `organization not exists`, treat that as the normal initial state for a first-time setup and continue with `ve organization CreateOrganization --body '{}'`.
  - If `CreateOrganization` returns `NoPermissionOnVerificationError`, recognize it as missing enterprise real-name verification. Stop and guide the user to complete verification at <https://console.volcengine.com/user/authentication/detail/>.
  - When the organization already exists, automatically scan the standard OUs `Platform`, `Applications`, `SandBox`, plus `Dev`, `Staging`, and `Prod` under `Applications` before entering `01-organization`.
  - For any standard OU that is stably detected, inject the corresponding `existing_*_ou_id` before Terraform runs. Ask the user for OU IDs only if stable auto-detection fails.

- `Account Creation and Baseline Setup`
  - Before account creation, check that the minimum account-creation input is complete.
  - For `account create`, resolve a dedicated `run_id` first and execute from `account-factory/runs/<run_id>/account-create/terraform/`, not from the read-only asset source or a shared workspace root.
  - Before baseline creation, confirm that `account-factory/baseline-plans/` can be created and written.
  - Before baseline apply, confirm that the target `*.baseline.json` exists in `account-factory/baseline-plans/` and conforms to `references/account-factory/baseline.schema.json`.
  - When applying a baseline, pass `workspace_root` explicitly and confirm that it points at `./volcengine-landing-zone-workspace/`.
  - For `account create`, confirm that execution will happen in `account-factory/runs/<run_id>/account-create/terraform/` and that the run artifacts can be reused for later recovery or baseline continuation.
  - For `baseline apply`, confirm that execution will happen in `account-factory/runs/<run_id>/baselines/<baseline-name>/terraform/` and not in a shared root.

- `Cross-account execution phases`
  - Do not block earlier global preflight steps just because `AssumeRole` is not yet available.
  - Check cross-account `AssumeRole` suitability only right before entering `04-log`, `05-network`, or a cross-account networking module inside baseline apply.
  - If the current `ve` identity from the selected credential path cannot perform the required `AssumeRole`, stop before that phase and tell the user to switch to an IAM sub-user identity that has `STSAssumeRoleAccess`.

- `Failure Recovery`
  - Confirm the failure point, the latest execution artifacts, and the current resource state first.
  - If the issue involves `ConcurrentException`, partial success, or state drift, reconcile first and regenerate a plan later.

## 5. Failure Handling

- If any required check fails, stop real execution.
- Explain the problem first, then give a repair suggestion. After repair, restart from preflight.
- A missing directory is not automatically a failure. Treat it as a real blocker only when blueprints cannot be populated, the workspace cannot be created, the runtime root is not writable, or results cannot be written.
- `DescribeOrganization` or `ListOrganizationalUnits` returning `organization not exists` is not a failure for first-time setup. Treat it as blocking only when organization creation itself fails or the root OU still cannot be obtained afterward.
