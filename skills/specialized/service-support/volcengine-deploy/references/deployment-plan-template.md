# Deployment Plan Template

Use this reference to generate `.volcengine/deployment-plan.md`, the human-readable deployment gate created inside the user's project before changing Volcengine resources. It complements `.volcengine/deploy-choice.json`: the JSON is machine-readable state, while the Markdown plan is what the user reviews.

## Language

Write the generated `.volcengine/deployment-plan.md` in the user's original language. If the user writes in Chinese, write the plan in Chinese; if the user writes in English, write it in English; if the user writes in Japanese, write it in Japanese. Keep product names and stable enum values unchanged, such as `ECS`, `VKE`, `veFaaS`, `RDS`, `CR`, `EIP`, `ecs`, `vke`, `vefaas`, `cli`, and `iac`.

Keep the frontmatter keys and section markers in English so agents can parse the plan reliably even when the visible text is localized.

## Required gate

Do not create resources until all of these are true:

1. `.volcengine/deployment-plan.md` exists.
2. Frontmatter `status` is `validated` (validation checks passed).
3. The Validation Proof section is populated with real checks and has no failed required check.
4. Frontmatter `approval` is `granted` with a non-empty `approval_evidence` quoting the user authorizing resource creation.
5. The resource plan has been shown to the user.

If `status` is `draft`, finish validation first. If `approval` is `pending`, show the resource plan and obtain authorization. If the user changes `mode`, `region`, `infra_management`, dependencies, or the resource plan, reset `status: draft` and `approval: pending`, clear `approval_evidence`, and refresh the affected sections.

## Template

Copy this structure when generating `.volcengine/deployment-plan.md`. Translate visible headings and table labels into the user's original language. Keep frontmatter keys, enum values, and `<!-- volcengine:section=... -->` markers unchanged.

```md
---
schema_version: "1"
language: <language-code>
status: draft
approval: pending
approval_evidence: ""
mode: <ecs|vke|vefaas>
infra_management: <cli|iac>
recipe: <ecs-systemd|ecs-docker|ecs-compose|vke-k8s|vefaas>
generated_at: "<iso-8601-timestamp>"
---

# <Localized Volcengine Deployment Plan Title>

<!-- volcengine:section=deployment-target -->
## 1. <Deployment Target>

| Field | Value |
|---|---|
| Repository | `<repo_name>` |
| Repo Path or Git URL | `<repo_dir-or-git-url>` |
| Git SHA | `<git_sha>` |
| Region | `<region>` |
| Project | `<project>` |
| Mode | `<ecs|vke|vefaas>` |
| Resource Management | `<cli|iac>` |
| Recipe | `<recipe>` |
| Public Port | `<port-or-n/a>` |
| Health Path | `<path-or-unknown>` |

<!-- volcengine:section=user-decisions -->
## 2. <User Decisions>

| Decision | Value | Notes |
|---|---|---|
| Resource strategy | `<create-isolated-project|reuse-existing>` | `<notes>` |
| Resource management | `<cli|iac>` | `<reason>` |
| ECS SSH 22 | `<yes|no|n/a>` | `<restriction-or-n/a>` |
| Managed dependencies | `<none|RDS|AIDAP|Redis|TOS|...>` | `<notes>` |
| Migration handling | `<none|manual|job|command>` | `<notes>` |

<!-- volcengine:section=resource-plan -->
## 3. <Resource Plan>

| Action | Resource | Name | Quantity | Key Config | Purpose | Public Exposure | Cleanup |
|---|---|---:|---:|---|---|---|---|
| `<create|reuse>` | `<resource-type>` | `<name>` | `<n>` | `<config-or-runtime-query>` | `<purpose>` | `<yes|no|limited>` | `<ledger|Terraform|not deleted>` |

<!-- volcengine:section=runtime-configuration -->
## 4. <Runtime Configuration>

| Type | Source | Destination | Status |
|---|---|---|---|
| Non-sensitive config | `<source>` | `<destination>` | `<resolved|missing|n/a>` |
| Secrets | `<source>` | `<destination>` | `<resolved|missing|n/a>` |
| Database URL | `<source>` | `<Secret/env destination>` | `<resolved|missing|n/a>` |
| Redis URL | `<source>` | `<Secret/env destination>` | `<resolved|missing|n/a>` |

<!-- volcengine:section=validation-proof -->
## 5. <Validation Proof>

| Check | Evidence | Result |
|---|---|---|
| CLI auth | `<evidence>` | `<pass|fail|deferred>` |
| Region/resource availability | `<evidence>` | `<pass|fail|deferred>` |
| Quota/capacity | `<evidence>` | `<pass|fail|n/a|deferred>` |
| Dependency readiness | `<evidence>` | `<pass|fail|n/a|deferred>` |
| Secret completeness | `<evidence>` | `<pass|fail>` |
| Recipe loaded | `<evidence>` | `<pass|fail>` |

<!-- volcengine:section=execution-plan -->
## 6. <Execution Plan>

1. Resolve repo and load this plan.
2. Verify `status: validated`, populated Validation Proof, `approval: granted`, and non-empty `approval_evidence`.
3. Provision or reuse resources through `<cli|iac>`.
4. Wire runtime config and managed dependencies.
5. Execute deployment case `<ecs|vke|vefaas>`.
6. Run migrations when required.
7. Verify public endpoint and one core behavior.
8. Print deployment summary and cleanup path.

<!-- volcengine:section=cleanup-plan -->
## 7. <Cleanup Plan>

| Resource Source | Cleanup Method |
|---|---|
| CLI-created resources | Reverse-order commands from `.volcengine/created-resources.json` |
| Terraform-created resources | Terraform destroy under `.volcengine/terraform` after user confirmation |
| Reused resources | Never delete automatically |

<!-- volcengine:section=deployment-result -->
## 8. <Deployment Result>

| Field | Value |
|---|---|
| Status | `<pending|succeeded|failed>` |
| URL | `<pending>` |
| Health | `<pending>` |
| Acceptance | `<pending>` |
| Logs | `<pending>` |
| Cleanup | `<pending>` |
| Notes | `<warnings-or-none>` |
```

## Fill Rules

Use the template above as the single source of shape: frontmatter keys, enum values, section markers, section order, table columns, and deployment-result fields come from the template.

Plan content rules:

- Frontmatter enum values must stay lowercase: `status` is `draft` or `validated`; `mode` is `ecs`, `vke`, or `vefaas`; `infra_management` is `cli` or `iac`.
- `approval` is `pending` or `granted`. `approval_evidence` quotes the user's words authorizing resource creation ("just deploy it", "open the resources for me"); a configuration choice such as "use ecs" is selection, not spend authorization, and must never be used as evidence. Never set `approval: granted` with an empty `approval_evidence`.
- `language` records the visible language used in the body.
- `recipe` is the selected execution recipe, for example `ecs-systemd`, `ecs-docker`, `ecs-compose`, `vke-k8s`, or `vefaas`.
- Include repository, repo path or Git URL, git SHA, region, project, mode, resource management, recipe, public port, and health path if known.
- Record decisions that materially affect cost, exposure, ownership, or cleanup: create/reuse strategy, CLI/IaC, ECS SSH 22, managed dependencies, and migration handling.
- List every resource that will be created or reused before provisioning. The resource plan is mandatory and must be shown to the user before resource creation.
- Only include resources relevant to the selected mode and dependencies.
- Use semantic placeholders where exact values are not known yet; do not invent zones, specs, images, CIDRs, quotas, or concrete resource IDs.
- Keep secrets out of the plan. Do not write passwords, tokens, AK/SK, full connection strings, or pre-signed URLs.

Resource-plan example rows:

| Action | Resource | Name | Quantity | Key Config | Purpose | Public Exposure | Cleanup |
|---|---|---:|---:|---|---|---|---|
| create | VPC | `deploy-<repo>-vpc` | 1 | CIDR decided at runtime | isolated network | no | ledger/Terraform |
| create | Subnet | `deploy-<repo>-subnet` | 1+ | zone decided at runtime | private network | no | ledger/Terraform |
| create | Security Group | `deploy-<repo>-sg` | 1 | app port `<port>` | ingress control | app port only | ledger/Terraform |
| create | ECS | `deploy-<repo>-ecs` | 1 | spec/image queried at runtime | run service | via EIP | ledger/Terraform |
| create | EIP | `deploy-<repo>-eip` | 1 | bandwidth/traffic billing | public endpoint | yes | ledger/Terraform |
| create | VKE Cluster | `deploy-<repo>-vke` | 1 | node arch verified | Kubernetes runtime | via CLB/EIP | ledger/Terraform |
| create | CR Repository | `deploy-<repo>` | 1 | private repository | store app image | no | ledger/Terraform |
| create | RDS MySQL | `deploy-<repo>-mysql` | 1 | private endpoint | application database | no | ledger/Terraform |
| reuse | Redis | `<existing-redis>` | 1 | private endpoint | cache/session | no | not deleted |

When confirming with the user, summarize this section in plain text, for example:

```text
The following resources will be created or reused:

- create VPC: deploy-myapp-vpc, used for network isolation
- create Subnet: deploy-myapp-subnet, used for private ECS/VKE resources
- create Security Group: deploy-myapp-sg, opens only application port 8080
- create ECS: deploy-myapp-ecs, runs the application service
- create EIP: deploy-myapp-eip, provides public access
- reuse RDS MySQL: existing-mysql-private, used as the application database and excluded from cleanup
```

Localize this confirmation text to the user's original language.

Runtime configuration rules:

- non-sensitive config from `.env.example`, `.env.sample`, or framework config
- secrets from user input or managed dependency outputs
- database URL status
- Redis URL status
- target destination: ECS `.env`, Kubernetes ConfigMap/Secret, or veFaaS app env vars

Validation rules:

- Record concrete evidence that the plan is executable.
- A `fail` on any required check blocks provisioning. `deferred` is allowed only when the check cannot be performed before provisioning and its evidence names the post-provision command or gate; a check that can run before provisioning must not be deferred.
- Do not mark the plan `validated` if required user decisions or secrets are still missing.
- Keep mutually exclusive deployment branches as cases under one "execute deployment" step.

Cleanup rules:

- CLI-created resources: reverse-order commands from `.volcengine/created-resources.json`.
- Terraform-created resources: Terraform destroy under `.volcengine/terraform` after user confirmation.
- Reused resources: never delete automatically.
