# Deploy Mode Heuristics

Use this when `volcengine-prepare` explains ECS / VKE / veFaaS choices. The output is a ranked recommendation for the user, not a score table and not a filter. Show every materially viable path, pick a default deployment mode when the deploy target is clear, and ask for lifecycle, reuse, and resource-management choices. Use `ecs | vke | vefaas` as machine-readable mode values.

## Ranking rules

Rank by deployable service surface first. Do not demote a path just because a local tool is missing; tool checks happen after the user chooses.

If analysis reports `deploy_subdir`, rank the app in that subdirectory. Only treat a repo or subdirectory as deployable when there is a concrete target: the repo, subdirectory, command, artifact, static output, or existing cloud app/function that a path can actually run, containerize, expose, or serve.

File and framework signals are only evidence. A Dockerfile, compose file, `package.json`, framework dependency, or `build`/`dev`/`test` script does not by itself mean the repo is deployable.

Before ranking, identify whether there is a concrete deploy target for ECS, VKE, or veFaaS: something that can be run, containerized, exposed, or served by one of those paths.

Useful evidence includes, but is not limited to: a long-running process, start command, listening port, RPC/API/HTTP route, health/smoke endpoint, static/frontend build output intended to be served, clear frontend/backend service boundaries, existing veFaaS app/function, or a user-provided subdirectory, service, command, artifact, or runtime target.

If the surface is unclear, ask one focused follow-up before giving a strong recommendation:

```text
I can see build/package signals, but not the deploy target yet. Which subdirectory, service, command, artifact, static output, or existing veFaaS app/function should be deployed?
```

Use this downgrade path for repos that look like a library/SDK, CLI tool, agent skill, plugin, desktop app, tutorial/demo fragment, documentation-only project, or monorepo root without a selected app. These repos are not ECS/VKE/veFaaS deployment targets by default. If the user explicitly asks to deploy one, continue by identifying the concrete runtime surface, such as a docs site, example app, demo API, service command, static build output, or artifact to run; do not reject the request just because of the repo category.

### Prefer ECS when

- The user wants the fastest path to a public URL.
- The deployable surface can run on a Linux VM as a Web/API/RPC service, full-stack app, static-site serving process, binary, Docker/compose app, worker, or scheduled command.
- The project is simple enough for one VM or a small number of VMs.
- The repo has external dependencies but the selected service does not need Kubernetes-level rollout, autoscaling, or multi-service orchestration.
- The app needs OS, network, disk, package, or debugging control.
- The user needs a quick validation, fastest public URL, or one-VM shape. For resource management, recommend CLI for pure ECS single-VM deployments, especially when Terraform or provider registry access is unavailable. Recommend IaC for ECS when it is team-managed, needs managed dependencies, or needs plan/diff/destroy safety.

ECS packaging:

| Signal | Packaging |
|---|---|
| `compose.yaml` / `compose.yml` / `docker-compose.yml` / `docker-compose.yaml` exists | `ecs-compose` |
| Dockerfile exists | `ecs-docker` |
| Go / Rust / Java / .NET or clear single-process app | `binary-systemd` |
| Unclear app start but can be containerized | ask one follow-up for start command or Dockerfile choice |

Explain the default ECS shape:

- It creates or reuses an ECS instance.
- New public services get an EIP as the access endpoint.
- Ask the user whether to open SSH 22. If they do not want SSH, deploy and debug through Cloud Assistant.
- Approximate cost: `medium` (ECS instance + system disk + EIP/bandwidth; plus any managed dependencies).

### Prefer VKE when

- The selected deployable surface is containerized or naturally maps to Kubernetes workloads.
- The app needs multiple replicas, rolling updates, HPA, Kubernetes Jobs/CronJobs, Ingress/Service, or network policies.
- The selected app has multiple services, multiple languages, or several long-running processes.
- Migrations or workers need a cleaner lifecycle than a single systemd service.
- The workload needs GPU resources or production container operations.
- The user wants a production-shaped container platform.

Recommend Terraform/volcenginecc for VKE resource creation because clusters, node pools, CR, LB, and managed dependencies benefit from plan/diff/destroy safety. Use `ve` CLI plus `.volcengine/created-resources.json` only if the user chooses CLI after seeing the tradeoff, for temporary validation, or when Terraform is unavailable.

Approximate cost: `medium-high` (VKE nodes + CR + CLB/EIP + bandwidth; plus databases/cache/storage).

### Prefer veFaaS when

- The target fits the `volcengine-vefaas` skill workflow: a supported Web/API framework, supported frontend/static framework, or an existing veFaaS app/function.
- The target is an MCP project and does not have a user-mandated ECS runtime. For MCP, rank veFaaS first, ECS second, and do not recommend VKE by default because this workflow needs session keeping.
- There are no complex in-band DB migrations, long-running workers, multi-service orchestration needs, unsupported event/task/trigger creation, custom system dependencies, or API Gateway blockers.
- The framework is likely supported by the `volcengine-vefaas` skill, such as FastAPI, Django, Flask, Express, Next.js, Nuxt, NestJS, Remix, Vite, Astro, Vitepress, Rspress, Create React App, or Angular.
- Low operational overhead and pay-by-use economics matter more than infrastructure control.

If the user chooses veFaaS, switch to/call the `volcengine-vefaas` skill. If it fails, return to the main deployment flow and let the user retry veFaaS or switch to ECS/VKE. Do not use the legacy ZIP/API flow in `volcengine-deploy`.

For MCP projects, switch to `volcengine-vefaas` after selecting veFaaS and let that skill load its own `references/mcp-deployment.md`. If it is unavailable, use `volcengine-find-skills` to install it and resume in a new thread. VKE is only appropriate when the user explicitly asks for Kubernetes and already has a session-affinity plan.

Approximate cost: `low-medium` (function resources + API Gateway; plus dependency services if used).

## Common warning signals

Mention these in the relevant option, but do not hide the option:

| Signal | What to tell the user |
|---|---|
| Dockerfile but no long-running process, port, route, static output, or user-specified start command | Dockerfile is packaging evidence, not deployability. Ask which service or artifact should be run. |
| Dockerfile references missing scripts or placeholder server packages | Treat the Dockerfile as stale or incomplete. Do not recommend ECS/VKE until a working build command and runtime entrypoint are confirmed. |
| `package.json` only has build/dev/test-like scripts | Build tooling is not a service contract. Ask whether this is a frontend site, full-stack app, API service, library, or tooling package. |
| README or runtime docs give an official port, route, or deploy command | Prefer those docs over default guesses, then verify with a smoke check after deployment. |
| Monorepo root with multiple candidates | Ask for the app/subdir to deploy before ranking. |
| Library/SDK/CLI/desktop/tutorial/docs-like repo | Downgrade to manual confirmation; ask what online service or site should be exposed. |
| `migration_paths` non-empty | veFaaS may need a separate migration step; VKE can run a Job, ECS can run a one-shot command. |
| WebSocket / long-lived connections | ECS or VKE is usually safer than veFaaS. |
| Compose file with Redis/MySQL/etc. | ECS compose can run it quickly, but data durability and scaling are weaker than managed services or VKE. |
| Many stateful dependencies | VKE or managed services may be more appropriate; ECS remains possible for quick validation. |
| External MySQL/PostgreSQL/SQL Server/Redis dependency | Recommend managed services with the same VPC, private endpoint, and explicit migration step. Use RDS for MySQL and SQL Server. For PostgreSQL, preserve explicit user intent; when ambiguous ask for RDS PostgreSQL, AIDAP PostgreSQL, or AIDAP Supabase, and if the user delegates the choice default to AIDAP Supabase. For Redis, use managed Redis by default. |
| Project only uses SQLite | Keep it as a valid choice; warn about single-node/disk durability, but do not imply RDS migration is required. |
| Long-lived cloud resources | Recommend IaC for VKE, managed dependencies, team-owned infrastructure, or plan/diff/destroy needs. Recommend CLI for pure ECS single-VM services when speed and fewer dependencies matter more. |
| Static frontend | veFaaS/static serving may be possible, but ECS/VKE are still valid if the user wants one service shape. |
| Unknown port or start command | Ask one concise follow-up after the user chooses a path. |
| Region/service permission notes | Surface them next to the affected path and let the user decide. |

## Suggested recommendation patterns

### Go API with Redis, no Dockerfile

1. ECS
   - Reason: compiled service can run directly under systemd; Redis can be managed or run via compose for quick validation.
   - Tradeoff: single-VM operation unless expanded later.
2. VKE
   - Reason: good if the user wants replicas, rolling rollout, or managed Redis wiring.
   - Tradeoff: more resources and setup.
3. veFaaS
   - Reason: low ops if the app is stateless.
   - Warning: Redis and any migration/worker behavior must be confirmed.

### Existing Dockerfile plus database migrations

1. VKE
   - Reason: containerized app and migrations map cleanly to Deployment + Job.
2. ECS
   - Reason: simpler if one VM is enough; run Docker or compose on ECS.
3. veFaaS
   - Warning: migrations need a separate plan and framework support must be verified by `volcengine-vefaas`; failure should return to the main flow for retry or ECS/VKE selection.

### FastAPI / Next.js with no external dependencies

1. veFaaS
   - Reason: supported framework shape, low ops, pay-by-use.
2. ECS
   - Reason: fastest predictable VM path with EIP.
3. VKE
   - Reason: valid but heavier unless the user wants Kubernetes.

### MCP project

1. veFaaS
   - Reason: default MCP path for HTTP exposure and session keeping.
2. ECS
   - Reason: fallback when veFaaS does not fit the runtime, dependency installation, or system-control needs.
3. VKE
   - Warning: not a default MCP path; use only when the user explicitly asks for Kubernetes and already has a session-affinity plan.

## Resource management recommendation

Recommend resource management, then ask the user to choose:

| Signal | Resource management |
|---|---|
| User says "temporary", "demo", "quick validation", or "just run it" | `cli` fast path with `.volcengine/created-resources.json` |
| Pure ECS single-VM service with no managed dependencies and no explicit plan/diff/destroy requirement | `cli` fast path with `.volcengine/created-resources.json` |
| Any VKE, managed DB/cache/storage/LB/domain/certificate, or team-owned service | `iac` |
| User needs plan/diff/drift/destroy or may resume later | `iac` |
| Terraform/provider/network unavailable and the user accepts lower reproducibility | `cli` fallback |
| User explicitly says "no Terraform/IaC" | `cli` |

For China network conditions, include a note when Docker images are involved: Docker Hub and GHCR may be slow or blocked. Deployment should prefer Volcengine CR, user-provided registries, or an inspected domestic mirror/sync URL over direct public registry pulls.

## User confirmation

After presenting the ranked list, ask only:

```text
1. Deployment mode: defaults to the top-ranked option. Choose ECS / VKE / veFaaS (recorded as `ecs` / `vke` / `vefaas`).
2. Resource strategy: defaults to a new isolated project deploy-<repo> with new resources; you may also reuse existing resources.
3. Resource management: recommend <cli|iac>; confirm whether to use the CLI resource ledger or Terraform/IaC.
```

Mention the resource management recommendation, then ask for confirmation:

```text
Resource management recommendation: choose Terraform/volcenginecc for VKE, managed dependencies, and team resources; choose the ve CLI fast path (record a resource ledger) for plain single-VM ECS, temporary validation, or when IaC is unavailable. Confirm `iac` or `cli`.
```
