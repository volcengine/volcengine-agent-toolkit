# volcengine-skills

---
[![Volcengine SKILL & CLI Survey](img_new.png)](https://www.volcengine.com/survey/q/v2/7662656599489085475/q36U8r81/5ffc/channel=doc)

To improve your experience with Volcengine skill, we invite you to participate in our [Survey with Prizes](https://www.volcengine.com/survey/q/v2/7662656599489085475/q36U8r81/5ffc/channel=doc) .

---

**English** | [简体中文](./README.md)

A skill marketplace maintained by the Volcengine team for AI coding agents including Claude Code,
Codex, OpenCode, Cursor, and Gemini CLI. Only the core plugin is installed by default. Optional
skills are grouped into Volcengine product-domain plugins and discovered through
`volcengine-find-skills`.

**[Quick Install →](#default-installation)**

## Plugins

<!-- BEGIN GENERATED: plugin-catalog -->
| Plugin | Product domain | Skills | Default |
| --- | --- | --- | --- |
| `volcengine-core` | Core | `volcengine-cli`, `volcengine-troubleshooting`, `volcengine-knowledge-search`, `volcengine-find-skills` | Yes |
| `volcengine-storage` | Storage | `volcengine-tosutil` | No |
| `volcengine-database` | Database | `volcengine-db-supabase` | No |
| `volcengine-containers-middleware` | Containers and Middleware | `volcengine-vefaas` | No |
| `volcengine-security` | Security | `volcengine-compliance` | No |
| `volcengine-identity-access-control` | Identity and Access Control | `volcengine-landing-zone` | No |
| `volcengine-service-support` | Service Support | `volcengine-sale`, `volcengine-prepare`, `volcengine-deploy`, `volcengine-iac`, `volcengine-api`, `volcengine-sdk-generator` | No |
<!-- END GENERATED: plugin-catalog -->

The core marketplace entry uses `INSTALLED_BY_DEFAULT`; all optional plugins use `AVAILABLE`.
`skills/core/` contains core skills; `skills/specialized/<domain>/<skill>/` provides optional skill
copies grouped by product domain. The category is the owning plugin name without `volcengine-`:
for example, `volcengine-database` maps to `skills/specialized/database/`. Optional skill sources
are maintained in their plugins; the sync script generates the copies.

## Skills

<!-- BEGIN GENERATED: skill-catalog -->
| Skill | Plugin | Use case |
| --- | --- | --- |
| [`volcengine-cli`](./skills/core/volcengine-cli/SKILL.md) | `volcengine-core` | Use the ve CLI to create, query, and manage Volcengine cloud resources. |
| [`volcengine-troubleshooting`](./skills/core/volcengine-troubleshooting/SKILL.md) | `volcengine-core` | Diagnose Volcengine errors, resource health, quotas, metrics, and OpenAPI failures. |
| [`volcengine-knowledge-search`](./skills/core/volcengine-knowledge-search/SKILL.md) | `volcengine-core` | Search and fetch official Volcengine documentation with ve docs search/fetch, without login. |
| [`volcengine-find-skills`](./skills/core/volcengine-find-skills/SKILL.md) | `volcengine-core` | List all Volcengine skills so an agent can select and install missing capabilities. |
| [`volcengine-tosutil`](./skills/specialized/storage/volcengine-tosutil/SKILL.md) | `volcengine-storage` | Manage TOS buckets and objects with the tosutil command-line tool. |
| [`volcengine-db-supabase`](./skills/specialized/database/volcengine-db-supabase/SKILL.md) | `volcengine-database` | Manage Volcengine AI-native BaaS Supabase workspaces, SQL, Auth, Realtime, and Edge Functions. |
| [`volcengine-vefaas`](./skills/specialized/containers-middleware/volcengine-vefaas/SKILL.md) | `volcengine-containers-middleware` | Deploy and manage serverless applications on Volcengine veFaaS. |
| [`volcengine-compliance`](./skills/specialized/security/volcengine-compliance/SKILL.md) | `volcengine-security` | Recommend compliance baselines, report posture, and author custom Rego compliance rules. |
| [`volcengine-landing-zone`](./skills/specialized/identity-access-control/volcengine-landing-zone/SKILL.md) | `volcengine-identity-access-control` | Consult, set up, and manage Volcengine landing zones and account baselines. |
| [`volcengine-sale`](./skills/specialized/service-support/volcengine-sale/SKILL.md) | `volcengine-service-support` | Route Volcengine product sale/purchase intents and delegate to the owning skill. |
| [`volcengine-prepare`](./skills/specialized/service-support/volcengine-prepare/SKILL.md) | `volcengine-service-support` | Analyze a repository and recommend ECS, VKE, or veFaaS deployment shapes. |
| [`volcengine-deploy`](./skills/specialized/service-support/volcengine-deploy/SKILL.md) | `volcengine-service-support` | Deploy a local directory or Git repository to Volcengine. |
| [`volcengine-iac`](./skills/specialized/service-support/volcengine-iac/SKILL.md) | `volcengine-service-support` | Manage Volcengine infrastructure with Terraform and infrastructure as code. |
| [`volcengine-api`](./skills/specialized/service-support/volcengine-api/SKILL.md) | `volcengine-service-support` | Query Volcengine API specifications, parameters, errors, and response structures. |
| [`volcengine-sdk-generator`](./skills/specialized/service-support/volcengine-sdk-generator/SKILL.md) | `volcengine-service-support` | Generate accurate, runnable Volcengine SDK examples in supported languages. |
<!-- END GENERATED: skill-catalog -->

## Default Installation

### Discover and install on demand

`volcengine-find-skills` embeds the single catalog for all core skills and every optional
plugin skill:

1. The finder triggers for explicit discovery and when the currently loaded or installed skills
   cannot cover a product, tool, or workflow required by an active Volcengine task.
2. `list` returns the complete catalog so the agent can select the minimum skill set from names,
   product domains, summaries, and keywords.
3. Installation requires exact skill names; plugins are classification metadata, not install targets.
4. For every host, the finder installs selected skills directly through the skills CLI, never the
   whole plugin.
5. After the installer exits successfully, the finder reads the host's installed list and returns
   `verified: true` only when every requested skill is visible.
6. When a host cannot dynamically load a newly installed skill, start a new thread carrying the
   original task and completed context.

### Codex

Add the marketplace and install only the core plugin:

```bash
codex plugin marketplace add volcengine/volcengine-skills
codex plugin add volcengine-core@volcengine-skills
codex plugin list
```

These plugin commands only bootstrap the core finder. Subsequent finder installs target exact skills.

In a new thread, ask for a skill by task, such as "find the object storage skill" or "install
`volcengine-tosutil`". The finder reads the complete catalog, selects the appropriate skill, and
installs that skill directly without installing its whole product-domain plugin. Start another
thread when the current host cannot dynamically load new skills.

From a source checkout, discovery and status can be tested directly:

```bash
python3 plugins/volcengine-core/skills/volcengine-find-skills/scripts/find_skills.py list
python3 plugins/volcengine-core/skills/volcengine-find-skills/scripts/find_skills.py install volcengine-tosutil --agent codex
python3 plugins/volcengine-core/skills/volcengine-find-skills/scripts/find_skills.py status --agent codex
```

### Generic skills CLI

This command installs only the current core skills:

```bash
npx skills add volcengine/volcengine-skills \
  --global --yes --copy --full-depth \
  --skill volcengine-cli volcengine-troubleshooting volcengine-knowledge-search volcengine-find-skills
```

The finder can later invoke `npx skills add --skill` for exact skills. To select repository skills interactively:

```bash
npx skills add volcengine/volcengine-skills --full-depth
```

### Claude Code

```text
/plugin marketplace add volcengine/volcengine-skills
/plugin install volcengine-core@volcengine-skills
/reload-plugins
/volcengine-core:volcengine-find-skills
```

### Gemini CLI

```bash
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-cli
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-troubleshooting
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-knowledge-search
gemini skills install https://github.com/volcengine/volcengine-skills --path skills/core/volcengine-find-skills
gemini skills list
```

Approve each security prompt on first install, then restart Gemini CLI. Describe a Volcengine task directly or ask it to use `volcengine-find-skills`.

### OpenCode

Follow the [OpenCode instructions](./.opencode/INSTALL.md) to mount the core plugin's `skills/`
directory.

### Cursor

```text
/add-plugin volcengine-core@https://github.com/volcengine/volcengine-skills
/volcengine-find-skills
```

Enter the complete command in a Cursor 2.5 or newer Agent chat. `/add-plugin` may not appear in autocomplete.

## Directory Structure

```text
volcengine-skills/
├── skills/
│   ├── core/                         # authoritative core skills installed by the CLI
│   └── specialized/
│       └── <domain>/
│           └── volcengine-<name>/    # generated copy from the optional plugin
├── plugins/
│   ├── volcengine-core/              # default core plugin with core skills and hooks
│   └── volcengine-<domain>/          # optional plugin and authoritative skill source
└── .agents/plugins/marketplace.json
```

`skills/core/` is authoritative for the core skills. Optional skills are maintained directly
inside their owning plugins. The sync script copies core and specialized skills and generates
manifests, marketplaces, and the README / Gemini / Cursor skill catalogs. Generated copies and
catalogs between `BEGIN GENERATED` / `END GENERATED` markers are maintained by the script.
The CLI's default release bundle still contains only core skills; install optional skills by name.
After changing or adding a skill, run:

```bash
python3 scripts/sync_plugins.py
python3 scripts/validate_codex_plugin_layout.py
python3 -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](./LICENSE).
