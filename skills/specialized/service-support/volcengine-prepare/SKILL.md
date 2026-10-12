---
name: volcengine-prepare
description: >-
  Use when the user wants to deploy a local directory or GitHub repository to Volcengine and
  needs the project analyzed, the app shape understood, and a ranked recommendation across
  ECS, VKE, and veFaaS before choosing an execution path. Also trigger when the user asks
  "what deploy mode should I use", "is this repo ready for Volcengine", or "check my repo
  before deploying". This skill prepares the decision; `volcengine-deploy` skill performs the
  chosen deployment, and `volcengine-iac` skill is used only when the user chooses Terraform/IaC
  or the task already has an IaC workflow.
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

# Volcengine Prepare Skill

Analyze a repo, explain viable Volcengine deployment paths, and decide the resource management path. Treat this skill as decision support, not as a workflow engine. Do not make a heavy report schema the goal.

---

## 0. Core behavior

Default flow:

1. Resolve the repo from a local path or Git URL.
2. Run the analyzer to identify language, framework, port, Docker/compose shape, dependencies, migrations, entrypoint, and the deployable service surface.
3. Optionally verify the current Volcengine identity and region when credentials are available.
4. Present a ranked list of ECS / VKE / veFaaS only after a deployable service surface is clear. Include every materially viable path; explain why each path is attractive or costly. Use `ecs | vke | vefaas` as machine-readable mode values.
5. Recommend a resource management path (`cli` or `iac`) per [`references/deploy-mode-heuristics.md`](./references/deploy-mode-heuristics.md), and ask the user to confirm.
6. Ask only for product/lifecycle ambiguity, resource reuse, and the resource management choice. If the user says "you decide", use the first ranked runtime path, the recommended resource management path from these rules, and new isolated resources.
7. Persist only minimal state in `.volcengine/` when the work will continue across steps.

Before ranking ECS / VKE / veFaaS, identify the concrete deploy target: the repo, subdirectory, command, artifact, static output, or existing cloud app/function that a path can actually run, containerize, expose, or serve. File-level signals are evidence, not conclusions. A Dockerfile, compose file, `package.json`, framework dependency, or `build`/`dev`/`test` script does not by itself prove the repo is deployable.

Do not run strict tool dependency checks during recommendation. Check path-specific tools only after the user chooses a path.

State directory:

```text
.volcengine/
  deploy-choice.json       # chosen mode/resource strategy, when persistence is useful
  created-resources.json   # maintained by deploy only for CLI fast path
  terraform/               # IaC working files, only when infra_management=iac
  iac-outputs.json         # Terraform outputs consumed by deploy
```

Use `/tmp` only for temporary clones or caches.

---

## 1. Resolve and analyze the repo

For Git URLs, clone to a temporary cache. For local paths, analyze in place.

```bash
input="${1:-.}"
if [[ "$input" =~ ^(https?|git@) ]]; then
  repo_name=$(basename "$input" .git)
  cache_dir="/tmp/volcengine-prepare/$repo_name"
  mkdir -p "$cache_dir"
  [ -d "$cache_dir/src/.git" ] || git clone --depth 1 "$input" "$cache_dir/src"
  repo_dir="$cache_dir/src"
else
  repo_dir=$(cd "$input" && pwd)
  repo_name=$(basename "$repo_dir")
fi
git_sha=$(cd "$repo_dir" && git rev-parse --short HEAD 2>/dev/null || echo "unversioned")
```

Run:

```bash
analysis=$(bash scripts/analyze-repo.sh "$repo_dir")
echo "$analysis" | jq .
```

Show the important findings in plain language:

```text
Project: <repo_name> @ <git_sha>
Runtime: <language> / <framework>
Deployable subdir: <deploy_subdir or repo root>
Deployable surface: <web service | rpc service | http api | static/html site | full-stack app | user-specified service | unclear>
Entrypoint: <entrypoint>
Port: <port>
Packaging signals: Dockerfile=<yes/no>, compose=<yes/no if detected>
Dependencies: <mysql, redis, ...>
Migrations: <paths or none>
```

If the analyzer cannot identify a concrete ECS/VKE/veFaaS deploy target, ask what subdirectory, service, command, artifact, static output, or existing veFaaS app/function should be deployed before recommending a path. Downgrade to confirmation instead of a strong recommendation when the repo appears to be primarily build tooling, packaging, examples, docs, or reusable code rather than an application surface.

A deploy target is something that can be run, containerized, exposed, or served by ECS, VKE, or veFaaS. Useful evidence includes, but is not limited to:

- a long-running process with a start command,
- a listening port or RPC/API/HTTP route,
- a static/HTML site entry or build output intended for serving,
- a health check or smoke endpoint,
- frontend and backend/API pieces with a clear service boundary,
- an explicit user instruction naming the service, subdirectory, command, artifact, or runtime target.

Do not infer deployability from a Dockerfile, package scripts, or build tooling alone.

---

## 2. Optional cloud identity check

If `VOLCENGINE_ACCESS_KEY`, `VOLCENGINE_SECRET_KEY`, and `VOLCENGINE_REGION` are set, verify identity:

```bash
ve sts GetCallerIdentity
```

Do not read `~/.volcengine/config.json`; it may contain secrets. If env vars are absent, keep the recommendation going and tell the user credential checks will happen when executing the chosen path.

If cloud service availability matters for a near-term choice, run the read-only probe:

```bash
services=$(bash scripts/check-region-services.sh)
echo "$services" | jq .
```

Surface permission or region notes in the corresponding option; do not hide that option.

Prechecks are advisory, not gates. If you can cheaply check quotas or permissions, present the result as a risk:

```text
<quota/permission> may be insufficient; continuing could fail when creating resources. Proceed anyway?
```

If account real-name verification or balance cannot be queried reliably, give a short reminder instead of inventing a check:

```text
Creating cloud resources may require a real-name-verified account with sufficient balance/credit; if creation fails, resolve the account status in the console first.
```

---

## 3. Recommend deployment paths

Use [`references/deploy-mode-heuristics.md`](./references/deploy-mode-heuristics.md) for the detailed decision rules. Present a ranked list, not `recommended=true/false` flags or scoring internals. If the deployable surface is unclear, present the ambiguity first and ask the smallest follow-up question before ranking.

Include every materially viable option; do not force a full ECS / VKE / veFaaS comparison when the repo or user request clearly rules a path out. Mention a non-viable path only when its exclusion helps the user decide.

- **ECS**: VM path. Best for targets that can run on a Linux VM, such as Web/API/RPC services, full-stack apps, static-site serving processes, binaries, Docker/compose apps, workers, scheduled commands, or apps needing OS/network/disk/debugging control.
- **VKE**: Container/Kubernetes path. Best for containerized or Kubernetes-shaped targets, such as multi-service apps, Web/API/RPC containers, workers, Jobs/CronJobs, rolling updates, replicas, HPA, Ingress/Service, GPU workloads, or production container operations.
- **veFaaS**: Serverless path. Best only when the target fits the `volcengine-vefaas` skill workflow: supported Web/API or frontend/static frameworks, or an existing veFaaS app/function. Prefer ECS/VKE for long-running workers, multi-service orchestration, complex migrations, unsupported event/task/trigger creation, custom system dependencies, or no available API Gateway. If the user chooses it, switch to/call the `volcengine-vefaas` skill for deployment; if that fails, return to the main flow so the user can retry or choose ECS/VKE.

Include:

- why it is ranked where it is
- rough cost level (`low`, `medium`, `medium-high`)
- operational tradeoffs
- known blockers or setup needed if the user chooses it
- resource management recommendation (`iac` or `cli`) and why

Do not check every tool before the user chooses. Phrase setup needs as decision guidance. Fill the resource management recommendation from [`references/deploy-mode-heuristics.md`](./references/deploy-mode-heuristics.md), but do not mention that internal reference path to the user:

```text
Resource management recommendation: <iac|cli>. Reason: <one short user-facing reason>. Confirm `iac` or `cli`.
Choosing VKE will check kubectl; if you choose IaC it will also check terraform/provider availability.
Choosing veFaaS switches to / calls the `volcengine-vefaas` skill to check the vefaas CLI, login status, and framework detection; on failure it returns here so you can fix it and retry, or switch to ECS/VKE.
```

---

## 4. Ask only necessary questions

After showing the ranked list, ask only what cannot be safely inferred:

```text
1. Deployment mode: defaults to the top-ranked option. Choose ECS / VKE / veFaaS (recorded as `ecs` / `vke` / `vefaas`).
2. Resource strategy: defaults to a new isolated project deploy-<repo> with new resources; you may also reuse existing resources.
3. Database product/engine, only when a managed database is detected or requested: choose `rds/mysql`, `rds/postgresql`, `rds/sqlserver`, `aidap/supabase`, or `aidap/postgresql`.
4. Resource management: recommend <cli|iac>; confirm whether to use the CLI resource ledger or Terraform/IaC.
```

For MySQL dependencies, use `database_product=rds` and `database_engine=mysql` unless the user rejects managed RDS. For SQL Server dependencies, use `database_product=rds` and `database_engine=sqlserver`. For PostgreSQL dependencies, preserve explicit user intent first: choose RDS PostgreSQL for an explicit RDS / managed RDS instance request, choose AIDAP PostgreSQL for an explicit AIDAP/serverless PostgreSQL request, and choose AIDAP Supabase for an explicit Supabase request. When the product is ambiguous and the user has not delegated the choice, ask because RDS PostgreSQL, AIDAP PostgreSQL, and AIDAP Supabase are different choices.

Ask whether to use Terraform/IaC explicitly. Give a recommendation per [`references/deploy-mode-heuristics.md`](./references/deploy-mode-heuristics.md), but do not turn it into a default. Ask the user to confirm `iac` or `cli`.

If the user says "you decide", use:

- deployment mode: first ranked option
- resources: create new isolated Volcengine project `deploy-<repo>`
- database product/engine: infer exact engines when unambiguous (`mysql` -> `rds/mysql`, `sqlserver` -> `rds/sqlserver`); for PostgreSQL, choose AIDAP Supabase (`database_product=aidap`, `database_engine=supabase`) when the project has no explicit RDS/AIDAP PostgreSQL/Supabase signal.
- resource management: apply [`references/deploy-mode-heuristics.md`](./references/deploy-mode-heuristics.md)

If the user chooses reuse, ask for only the resource IDs needed by that path. Reused resources must not be destroyed by cleanup.

---

## 5. Persist the user's choice only when useful

If execution continues in the same conversation, no file is required. If the user may resume later or the next step needs a durable handoff, write only a small choice record:

```json
{
  "schema_version": "1",
  "repo_dir": "/absolute/path",
  "repo_name": "my-app",
  "git_sha": "abc1234",
  "region": "cn-beijing",
  "mode": "ecs",
  "port": 8080,
  "dependencies": ["postgresql", "redis"],
  "database_product": "aidap",
  "database_engine": "supabase",
  "resource_strategy": "create-isolated-project",
  "project": "deploy-my-app",
  "infra_management": "cli"
}
```

Write it to `.volcengine/deploy-choice.json`.

Do not write score tables, rationale arrays, or a full recommendation matrix unless the user asks for a report.

---

## 6. Summary template

```text
Project detection:
- Runtime: <language>/<framework>
- Deployable surface: <surface or unclear, with evidence>
- Entrypoint/port: <entrypoint> / <port>
- Packaging signals: Dockerfile=<yes/no>, Compose=<yes/no>
- Dependencies: <deps or none>
- Database choice: <none | database_product=rds engine=mysql|postgresql|sqlserver | database_product=aidap engine=supabase|postgresql>
- Migrations: <paths or none>
- Resource management recommendation: <iac|cli>

Ranked order:
1. <mode>
   Reason: ...
   Tradeoff: ...
   Rough cost: ...

2. <mode>
   ...

3. <mode>
   ...

Please confirm:
1. Deployment mode: defaults to <first mode>
2. Resource strategy: defaults to a new isolated project deploy-<repo>; reuse is also possible
3. Resource management: recommend <iac|cli>; confirm `iac` or `cli`
```
