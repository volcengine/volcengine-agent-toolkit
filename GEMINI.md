# Volcengine Skills (for Gemini CLI)

This extension installs the Volcengine core plugin. For Volcengine tasks, load the matching core
skill from `plugins/volcengine-core/skills/<skill-name>/SKILL.md`.

<!-- BEGIN GENERATED: skill-catalog -->
Core skills:

- `volcengine-billing-and-cost-management` — Analyze cloud cost changes and attribute anomalies to products, charge items, usage, price, and amount components.
- `volcengine-cli` — Manage Volcengine resources with ve; route TOS and Ark tasks to product skills using ve tosutil and ve arkcli.
- `volcengine-troubleshooting` — Diagnose Volcengine errors, resource health, quotas, metrics, and OpenAPI failures.
- `volcengine-knowledge-search` — Search and fetch official Volcengine documentation with ve docs search/fetch, without login.
- `volcengine-find-skills` — List all Volcengine skills so an agent can select and install missing capabilities.
- `volcengine-feedback` — Draft and submit voluntary, redacted GitHub feedback on usage issues, capability needs, practical scenarios, and successful workflows without blocking the main task.

Optional catalogued skills:

- `volcengine-tosutil` — `volcengine-storage`; Manage TOS buckets and objects with the tosutil command-line tool.
- `volcengine-tls` — `volcengine-storage`; Operate Volcengine TLS log service with volclog: contract-first discover/describe/exec, log search, analysis, ingest, export, and error recovery.
- `volcengine-tls-logcollector` — `volcengine-storage`; Design, validate, deploy, and troubleshoot TLS LogCollector collection on Linux hosts or Kubernetes through volclog.
- `volcengine-db-supabase` — `volcengine-database`; Manage Volcengine AI-native BaaS Supabase workspaces, SQL, Auth, Realtime, and Edge Functions.
- `volcengine-vefaas` — `volcengine-containers-middleware`; Deploy veFaaS applications and MCP servers, and manage functions, sandboxes, and OpenAPI calls through the vefaas CLI.
- `volcengine-compliance` — `volcengine-security`; Recommend compliance baselines, report posture, and author custom Rego compliance rules.
- `volcengine-cloud-trail` — `volcengine-security`; Query CloudTrail audit logs and manage trails and backfill delivery tasks.
- `volcengine-landing-zone` — `volcengine-identity-access-control`; Consult, set up, and manage Volcengine landing zones and account baselines, and deploy solutions or blueprints.
- `volcengine-sale` — `volcengine-service-support`; Orchestrate Volcengine product transactions: purchase, price enquiry, and unsubscribe.
- `volcengine-prepare` — `volcengine-service-support`; Analyze a repository and recommend ECS, VKE, or veFaaS deployment shapes.
- `volcengine-deploy` — `volcengine-service-support`; Deploy a local directory or Git repository to Volcengine.
- `volcengine-iac` — `volcengine-service-support`; Manage Volcengine infrastructure with Terraform and infrastructure as code.
- `volcengine-api` — `volcengine-service-support`; Query Volcengine API specifications, parameters, errors, and response structures.
- `volcengine-sdk-generator` — `volcengine-service-support`; Generate accurate, runnable Volcengine SDK examples in supported languages.
<!-- END GENERATED: skill-catalog -->

When an optional skill is needed, or an active Volcengine task exceeds the capabilities of the
currently loaded or installed skills, load `volcengine-find-skills` and follow its discovery and
installation workflow. Do not treat a catalogued optional skill as installed merely because its
source exists inside another plugin or has a generated copy under
`skills/specialized/<domain>/<skill-name>/` in this repository. Categories follow plugin names
without the `volcengine-` prefix. Install the exact selected skills, not their owning plugins.

Trigger on Volcengine / 火山引擎 / 火山 keywords, `ve` commands, or
`VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY` / `VOLCENGINE_REGION` usage.
