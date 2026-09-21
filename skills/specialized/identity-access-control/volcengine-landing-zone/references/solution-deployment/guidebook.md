# Solution Deployment Workflow

Use this guidebook to validate and deploy a solution package.

## Core Principles

- Existing environments may already run production workloads. Confirm the exact targets before any write.
- Preserve the package's source revision and execution state so deployment and recovery remain reproducible.
- The customer owns credential secrets and permission policy. The agent selects and validates the execution identity without exposing or persisting those secrets.
- For Terraform solutions that manage Volcengine resources, prefer the `volcenginecc` provider when it supports the required resources. Use it by default when generating a new package, but do not silently replace an explicit, working provider in a customer-supplied package solely to enforce this preference.
- If no usable credentials exist, recommend `ve login` first and configure the package's Terraform provider to reuse the resulting profile when supported; otherwise follow the package/provider's documented authentication path.

## Standard Flow

Complete package preparation and target confirmation as one read-only flow. G2 applies once the deployment plan and any additional writes are known.

### 1. Prepare the Package

The agent resolves the package itself. Its source may be a built-in package name, git URL, local path, or a package generated from the user's requirements.

- Materialize the source under `${WORKSPACE_ROOT}/solution-deployment/packages/<name>/` without modifying the original.
- Record source provenance under [../preflight-checks.md](../preflight-checks.md) §3.
- Inspect the package to determine its entrypoints, inputs, dependencies, targets, expected writes, outputs, and recovery evidence.
- For Terraform packages, inspect `required_providers` and `.terraform.lock.hcl` to determine the actual resolved provider and version before choosing the credential path.
- Validate and plan the package with the tooling and workflow it defines.
- Keep credentials out of source files, generated input files, logs, and command arguments.

Continue directly to target confirmation unless an unresolved conflict or ambiguity requires user input.

### 2. Resolve and Confirm the Targets

- Resolve every deployment target from the user's request, package configuration, existing outputs, or read-only discovery.
- Confirm the declared targets and include them in G2.
- Label higher-blast-radius targets explicitly in the impact summary.

### 3. Resolve the Terraform Execution Identity

For each target, choose the suitable strategy from the package and runtime context instead of asking the user to select one when the choice can be derived:

- **Provider role assumption:** keep the base credential/profile in the runtime and configure the Terraform provider to assume into the target account. If the execution copy needs a provider adaptation, make it visible and include it in G2.
- **Target runtime identity:** bind this run to credentials or a profile that already resolves to the target account, and use the package's ordinary provider configuration. Prefer per-run binding over changing the user's global current profile.

When the resolved `volcenginecc` provider version is `0.0.70` or later, Terraform can use the profile created by `ve login` directly. Prefer reusing that profile and do not request separate AK/SK configuration solely for Terraform. For an older `volcenginecc` version or another provider, follow the package/provider's documented authentication path.

Apply these defaults and boundaries:

- An explicitly configured role or identity path takes precedence.
- For a verified member account in the current enterprise organization, when cross-account role assumption is required and no role was provided, default to `trn:iam::<account-id>:role/OrganizationAccessControlRole`.
- When the selected runtime identity already resolves to the target account, do not add another role assumption.
- For the management account itself, use its confirmed direct identity unless the package explicitly requires another path.
- Do not infer `OrganizationAccessControlRole` for an account outside the current enterprise organization.
- A single Terraform graph that writes to multiple accounts must use target-specific providers/aliases or be split into independently planned steps; do not switch one global profile during an active plan/apply.

Before planning any write, verify read-only that each effective Terraform identity resolves to its declared target. If the mapping cannot be verified or does not match, stop and request only the missing access or target information. Record the target-to-identity strategy without recording secret values.

### 4. Plan and Deploy (G2)

- Resolve `run_id` by reuse-first under `solution-deployment/runs/<run_id>/`. Reuse an unfinished run only when its source, targets, and inputs still match.
- Preserve the package layout in an isolated execution copy and initialize `run.json`, `context.json`, and step-level `status.json`.
- Generate the strongest read-only deployment preview available and derive execution order from actual dependencies.
- Present the targets, target-to-identity strategy, source revision, resource impact, sensitive deliverables, and additional writes under G2.
- After confirmation, execute only the reviewed plan and listed writes.
- Refresh status and filtered non-sensitive outputs after each significant step.
- If a step produces a local file the user must review, G4 applies: deliver it first, then pause.

## Failure Recovery

Recovery reuses [../failure-recovery.md](../failure-recovery.md). Continue from the existing `solution-deployment/runs/<run_id>/` artifacts, reconcile current state, and replan only unfinished work. Material changes require a new G2 confirmation.

## Result Output

Summarize the resolved targets, deployed source revision, completed writes, filtered non-sensitive outputs, and manual follow-up.
