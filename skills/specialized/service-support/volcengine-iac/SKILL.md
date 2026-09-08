---
name: volcengine-iac
description: >-
  Use Terraform/IaC for Volcengine resources only when the user explicitly chooses
  Terraform/IaC, already has a Terraform workflow/state, or confirms they need
  plan/diff/drift/destroy safety for VKE, managed databases/cache/storage, load balancers,
  domains/certificates, logging/monitoring, or team-managed infrastructure.
license: MIT
metadata:
  openclaw:
    envVars:
      - name: VOLCENGINE_ACCESS_KEY
        required: false
        description: AccessKey for AK/SK auth path (alternative to `ve login`)
      - name: VOLCENGINE_SECRET_KEY
        required: false
        description: SecretKey for AK/SK auth path
      - name: VOLCENGINE_SESSION_TOKEN
        required: false
        description: Optional STS session token for temporary credentials
      - name: VOLCENGINE_REGION
        required: false
        description: Default region; falls back to cn-beijing if unset
---

# Volcengine IaC Skill

Generate, plan, and apply Volcengine infrastructure with Terraform when the user chooses IaC. `volcengine-deploy` still owns application packaging, runtime rollout, health checks, and CLI resource-ledger deployment.

When writing new examples, prefer the Cloud Control provider `volcengine/volcenginecc`. Start from verified examples under `assets/examples/`, then read the matching `references/volcenginecc-*.md` note for validation results and pitfalls. Blocked resources are tracked in [`references/volcenginecc-blocked.md`](./references/volcenginecc-blocked.md). Existing reusable modules under `assets/modules/` still use the legacy `volcengine/volcengine` provider until each component is re-verified with `volcenginecc`.

Use this skill when one of these is true:

- the user asks for Terraform or IaC,
- the user already has Terraform state/workspace,
- plan/diff/drift detection matters,
- the infrastructure is intended for long-term team-managed operation and the user chooses IaC,
- the deployment needs VKE, managed databases/cache/storage, load balancers, domains/certificates, IAM/KMS, logging, monitoring, or Serverless triggers and the user chooses IaC.

Do not use this skill just because a deployment is long-lived, VKE-based, or has managed dependencies. Recommend IaC where appropriate, but let the user choose. Do not use this skill when the user asks for CLI, a temporary demo/quick validation, a pure ECS single-VM service with no plan/diff/destroy requirement, or when Terraform/provider installation is blocked and the target can safely use the CLI fallback.

The skill ships verified `volcenginecc` examples under `assets/examples/`, legacy reusable modules under `assets/modules/`, and wrapper scripts for tfvars generation, plan summaries, output export, and drift checks. Select files only after the target shape is known; do not load broad catalogs into context for small Terraform edits.

Resources outside the six legacy modules (CLB/ALB, VKE, CR, databases, caches, object storage) should be added as verified `volcenginecc` examples first, then wrapped only after repeated use proves the interface is stable.

---

## 0. Prerequisites

Required env vars: `VOLCENGINE_ACCESS_KEY`, `VOLCENGINE_SECRET_KEY`, `VOLCENGINE_REGION`.

Required tools: `terraform >= 1.5`, `jq`, `git`, `python3` (for `gen_tfvars.py`).

Optional: `.volcengine/deploy-choice.json` from `volcengine-prepare`/`volcengine-deploy`. If absent, ask a short batch of Terraform-specific questions.

The skill writes Terraform working files into `.volcengine/terraform/` by default. State can use a TOS S3-compatible backend when the user wants remote state; see [`references/backend-tos.md`](./references/backend-tos.md). Local state is acceptable for small one-off experiments when the user accepts the tradeoff.

If invoked by `volcengine-deploy`, return outputs in `.volcengine/iac-outputs.json` and let deploy continue with image build/push, Cloud Assistant commands, Kubernetes manifests, veFaaS release, migrations, and health checks.

---

## 1. Generation Flow

### Path A — driven by `.volcengine/deploy-choice.json`

```bash
work_dir="${work_dir:-.volcengine/terraform}"
workload="${workload:-standard}"
mkdir -p "$work_dir"

python3 scripts/gen_tfvars.py \
  --input ".volcengine/deploy-choice.json" \
  --output "$work_dir/terraform.tfvars" \
  --workload "$workload"
```

`gen_tfvars.py` derives:
- `project`, `region`, AZ pair from the choice file and environment
- `enable_vke / enable_cr / enable_rds / enable_redis / enable_tos` flags from the chosen mode and known dependencies
- Sizing (instance type, node count, RDS spec, Redis capacity) from a coarse `--workload` tier

The user can override any value before applying.

### Path B — natural language input

When no prepare report exists, ask the user **one batch of questions**, then create a Terraform working directory from verified examples or legacy modules and generate matching variable values. Required answers:

1. Project name (resource prefix)
2. Region (e.g. `cn-beijing`)
3. Need VKE? (yes/no)
4. Stateful deps needed: MySQL? PostgreSQL? Redis? TOS bucket?
5. Workload tier: light / standard / heavy

### Files written

`gen_tfvars.py` writes only `terraform.tfvars`. The Terraform configuration files come from copied verified examples under `assets/examples/` or from a small root module assembled from `assets/modules/`; edit those files to match the selected stack instead of expecting the script to generate them.

| File | Purpose |
|---|---|
| `main.tf` / `variables.tf` | Copied or assembled Terraform configuration |
| `terraform.tfvars` | Concrete values generated by `gen_tfvars.py` or edited by hand |
| `backend.tf` | Generated only when TOS remote state is selected; otherwise omit it |

The full per-module variable schema lives in [`references/modules.md`](./references/modules.md). For new `volcenginecc` work, start from a verified example under `assets/examples/` instead of these legacy modules unless the user explicitly needs the old provider.

### Path C — `volcenginecc` verified examples

Copy the relevant verified example, then run the same init/validate/plan sequence:

```bash
cp -R "assets/examples/<example-name>" "$work_dir/<component>"
cd "$work_dir/<component>"
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
```

Before apply, show the plan summary and require explicit user confirmation. Read the matching reference before changing inputs or destroying resources; the references contain field choices, validation notes, import IDs, and provider pitfalls.

---

## 2. Deployment stack mapping

Use the deployment shape to choose a small set of verified examples. Start with examples; wrap into reusable modules only after repeated use proves the interface stable. Typical stacks combine:

- ECS: `volcenginecc-network`, `volcenginecc-ecs`, optional TLS/CloudMonitor
- VKE: `volcenginecc-network`, `volcenginecc-vke`, `volcenginecc-cr`, CLB or ALB
- veFaaS: `volcenginecc-vefaas`, optional APIG/TLS
- Stateful web app: runtime stack plus RDS, Redis, and/or TOS examples
- Private service: runtime stack plus private NAT or network connectivity examples
- Domain entry: runtime stack plus DNS and load balancer certificate examples

This mapping is a guide, not a promise that a prebuilt module exists. Copy relevant examples into `.volcengine/terraform/<component>` and keep component boundaries clear so plan/destroy output remains readable.

For the end-to-end VKE private CR nginx path, use `assets/examples/volcengine-vke-cr-nginx/` and read `references/volcengine-vke-cr-nginx.md` first. That example exists for the CR credential addon, `core-dns`, CR token expiry, and image architecture pitfalls found in a real run.

---

## 3. Catalog

Use the filesystem as the catalog. After selecting a deployment shape, list only the relevant directories under `assets/examples/`, then read the matching `references/volcenginecc-*.md` file for validation notes, import IDs, and provider caveats. Do not load every example into context up front.

Common example families:

- `volcenginecc-network`, VPC extras, NAT, VPN, DirectConnect, CEN, TransitRouter, PrivateLink, DNS, PrivateZone
- `volcenginecc-ecs`, ECS extras, launch template versions, EBS snapshots, Auto Scaling
- `volcenginecc-vke`, `volcenginecc-cr`, CLB/ALB entry, APIG, veFaaS
- `volcenginecc-rdsmysql`, `volcenginecc-rdspostgresql`, `volcenginecc-rdsmssql`, Redis, Kafka allowlist
- `volcenginecc-tos`, TOS notification, TLS, CloudMonitor, IAM, FileNAS, EFS

Legacy `volcengine` modules are still available under `assets/modules/`; read [`references/modules.md`](./references/modules.md) before using them.

Legacy modules currently cover `network`, `vke`, `cr`, `rds-mysql`, `redis`, and `tos`. ECS and CLB/ALB stay as verified examples because their workload shapes vary too much for one stable module interface.

---

## 4. Init & Backend

```bash
cd "$work_dir"

# Map Volcengine creds to the Terraform s3 backend's required env variable names.
export AWS_ACCESS_KEY_ID="$VOLCENGINE_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$VOLCENGINE_SECRET_KEY"
export AWS_EC2_METADATA_DISABLED=true

terraform init -input=false
tf_workspace="${tf_workspace:-default}"
terraform workspace select "$tf_workspace" || \
  terraform workspace new "$tf_workspace"
```

When remote state is requested, generate `backend.tf` from `references/backend-tos.md`. The verified TOS backend shape requires `skip_requesting_account_id = true` and must not set `force_path_style` or `use_path_style`.

Provider download (~30–60 seconds first time) goes through `registry.terraform.io`. In China networks this may be blocked or slow. If public registry access fails and the user still wants IaC, configure Terraform `provider_installation` with a filesystem or internal mirror. Otherwise return to `volcengine-deploy` and ask whether to use the CLI resource-ledger path.

For the TOS bucket prerequisite (must exist before `init`), see [`references/backend-tos.md`](./references/backend-tos.md). Without a TOS bucket, omit `backend.tf` and Terraform falls back to local state.

---

## 5. Plan

```bash
terraform plan -out=tfplan.binary -input=false
terraform show -json tfplan.binary > tfplan.json
bash scripts/plan_summary.sh tfplan.json
```

`plan_summary.sh` groups changes by action (CREATE / UPDATE / DELETE / REPLACE) and prints a one-line summary at the end. Show this to the user before any apply.

Watch for:
- **DELETEs you didn't ask for** — usually a sign of drift or a mistakenly removed module call
- **REPLACEs on stateful resources** — RDS / Redis replace = data loss; abort and inspect the diff with `terraform show tfplan.binary`

---

## 6. Apply

**Always require explicit user confirmation.** Do not pass `-auto-approve`. The pattern:

```text
The plan above will create N resources, change M, destroy K. Approve apply? [yes/no]
```

After yes:

```bash
terraform apply tfplan.binary
```

VKE cluster creation takes ~10–15 minutes. RDS HA instances take ~20 minutes. Surface the long-running message to the user once at apply start so they don't think it hung.

After apply succeeds, run `export_outputs.sh` automatically:

```bash
bash scripts/export_outputs.sh
echo "Resources ready. .volcengine/iac-outputs.json now contains downstream consumption keys."
```

---

## 7. Outputs for Downstream

`export_outputs.sh` writes `terraform output -json` to `.volcengine/iac-outputs.json` with mode `0600`. Downstream skills commonly consume VPC/subnet/security group IDs, VKE kubeconfig, CR repository data, RDS/Redis endpoints or IDs, and TOS bucket names. Some keys are conditional on which examples/modules were enabled; consumers must use defensive `jq` defaults.

---

## 8. Destroy

```bash
# Show what will be destroyed first
terraform plan -destroy -out=destroy.binary
terraform show -json destroy.binary | bash scripts/plan_summary.sh
```

Then:

```text
This will permanently delete N resources including RDS / Redis / TOS bucket data. Confirm? [yes/no]
```

On yes:

```bash
terraform destroy
# Note: provider does not accept -auto-approve=false; we rely on the agent-level prompt above.
```

**Hard rule**: never destroy in `prod` workspace without a second confirmation. The agent should explicitly re-prompt:

```text
Workspace = prod. Re-confirm destroy by typing 'destroy prod':
```

---

## 9. Drift Detection

```bash
bash scripts/check_drift.sh
```

Returns:
- `0` and `{"drift": false, ...}` — no drift
- `2` and `{"drift": true, "changed_resources": N, ...}` — N resources changed outside Terraform
- `1` and `{"drift": "error", ...}` — refresh-only plan errored

Use this:
- After known manual interventions (someone resized a node pool via console)
- Periodically as a CI job (weekly)
- Before any non-trivial `apply` to confirm baseline matches state

---

## 10. Import Existing Resources

If the user wants to adopt resources created via `volcengine-cli` or console, use `terraform import`. Import IDs differ by resource; read the matching `references/volcenginecc-*.md` or [`references/modules.md`](./references/modules.md) before importing. After import, run `terraform plan` and reconcile by editing config, not state.

---

## 11. Safety Rules

- Never read `~/.volcengine/config.json`; it may contain plaintext AK/SK.
- Never commit `terraform.tfstate*` or `.volcengine/iac-outputs.json`.
- Never pass `-auto-approve` to `terraform apply` or `terraform destroy`.
- Run `check_drift.sh` before every apply on shared environments.
- Set mode `0600` on files holding kubeconfig or secrets.
- Pin provider versions in every module/example.

The scripts enforce file permissions where possible. Apply and destroy gates are the agent's responsibility.

---

## 12. Troubleshooting

Look up by the exact error string; act on the mapped cause before suspecting unrelated layers.

| Symptom | Cause | Fix |
|---|---|---|
| `terraform init`: "Failed to query available provider packages" | outbound to `registry.terraform.io` blocked | Configure `provider_installation` with a filesystem/internal mirror and rerun `init`; otherwise return to `volcengine-deploy` and ask whether CLI resource-ledger provisioning is acceptable |
| `terraform init`: "InvalidAccessKeyId" against TOS backend | s3 backend env vars not exported | Export `AWS_ACCESS_KEY_ID="$VOLCENGINE_ACCESS_KEY"`, `AWS_SECRET_ACCESS_KEY="$VOLCENGINE_SECRET_KEY"`, `AWS_EC2_METADATA_DISABLED=true` |
| `terraform init`: TOS backend returns `InvalidPathAccess` | path-style access or unsupported workspace prefix | Use the verified template in [`references/backend-tos.md`](./references/backend-tos.md): keep `skip_requesting_account_id = true`, remove `force_path_style`/`use_path_style` |
| `apply` succeeds for VPC but subnet fails with `InvalidVpc.InvalidStatus` | VPC not yet `Available` (consistency window) | Add `depends_on = [volcengine_vpc.main]` (already wired in the network module) |
| VKE cluster stuck in `Creating` for >20 min | quota or AZ capacity | `ve vke ListClusters --body '{"Filter":{"Ids":["..."]}}' \| jq .Result.Items[0].Status` for the real reason |
| `redis` output missing endpoint | provider does not export it | Resolve via `ve redis DescribeDBInstanceDetail --InstanceId $(jq -r '.redis_instance_id.value' .volcengine/iac-outputs.json)` |
| `terraform plan` shows unexpected changes after no edits | drift, or provider patch bump silently changing a default | Run `check_drift.sh`, inspect `tfplan.json`, decide whether to accept or revert |
| Two engineers' `apply` collide | TOS backend has no DynamoDB-style locking | Coordinate manually; see [`references/backend-tos.md`](./references/backend-tos.md) |
| Resource-specific apply/import drift | provider caveat for that resource | Read the matching `references/volcenginecc-*.md` note before editing config |
