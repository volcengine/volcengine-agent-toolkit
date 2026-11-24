# Product CLI routing: `ve tosutil`, `ve arkcli`, `ve volclog`

**Version requirement:** The [minimum version](install.md) (`ve >= 1.1.11`)
also gates delegation to another CLI, including `ve tosutil`, `ve arkcli` and `ve volclog`. Verify
it before delegation. The presence of a proxy command in `--help` alone does not satisfy this
requirement.

When `ve` is available, prefer **`ve tosutil`**, **`ve arkcli`** and **`ve volclog`**, even when a
standalone `tosutil`, `arkcli` or `volclog` is also installed. The TOS command is spelled `tosutil`; `toscli` is a
compatibility alias. The existing TOS skill is named `volcengine-tosutil` (not `volcengine-tosutils`).

| Task | Entry point | Read before use |
| --- | --- | --- |
| General cloud resource OpenAPIs | `ve <service> <Action>` | Native API workflow in [SKILL.md](../SKILL.md) |
| TOS buckets, objects and transfers | `ve tosutil <command>` | Use `volcengine-find-skills` to find `volcengine-tosutil`, install it if missing, and read its instructions |
| Ark (火山方舟) models, model prices, API Keys, inference, generation, Endpoints, fine-tuning, plans and usage | `ve arkcli <command>` | Use `volcengine-find-skills` to find `volcengine-ark`, install it if missing, and read its instructions |
| TLS (日志服务) log search, analysis, ingest, export, Project/Topic and LogCollector collection | `ve volclog <command>` | Use `volcengine-find-skills` to find `volcengine-tls` (or `volcengine-tls-logcollector` for collection), install it if missing, and read its instructions |

For TOS, follow the finder's `list` → select exact `volcengine-tosutil` → install if missing →
verify installation flow. Load the installed skill and the references it selects before executing.
Use its native tosutil command examples, replacing `tosutil ...` with `ve tosutil ...`.

For TLS, follow the same finder flow with exact `volcengine-tls`, or `volcengine-tls-logcollector`
for LogCollector collection. Those skills write native `volclog ...` examples; run them as
`ve volclog ...`. `ve` has no native `tls` OpenAPI command: if `ve volclog` reports an unknown
service or suggests `--force`, the `ve` build is older than the version requirement above, so
upgrade `ve` instead of adding `--force`.

For Ark, follow the same finder flow with exact `volcengine-ark`. That one skill bundles the
official Ark CLI guides for model lookup, pricing, API Keys, endpoints, inference, generation,
usage and the rest; read its `SKILL.md`, then the guide it selects for the task. The guides write
native `arkcli ...` examples; run them as `ve arkcli ...`. Do not install the upstream `arkcli-*`
skills or a standalone arkcli for this. Ark knowledge questions (concepts, usage, billing rules)
are answered by `volcengine-knowledge-search` instead.

For live model availability or pricing, a missing skill in the selected distribution is an
installation failure. Report which source lacks the skill and use a matching toolkit release
or checkout if available. If Ark reports an expired session, resume the live query after Ark
login. Public prices or model lists cannot establish what this account can use.

A skill installed by the finder is a directory of files. If the host does not load it into the
current conversation, read its `SKILL.md` and references by path from the install location and
continue the task; start a new conversation only when the files cannot be read. Keep product
instructions in those skills; this skill only routes to them.

`arkcli`, `tosutil` and `volclog` are transparent delegated CLIs: replace only the executable prefix in
their examples, keeping all later arguments unchanged. They retain their own authentication,
profile, parameters, output, and exit codes. Native API rules such as `--output`, `--query`,
`--force`, `--detail`, PascalCase parameters and `--DryRun` do **not** carry over. Neither do the
local safety policy and its `--yes` retry ([safety.md](safety.md)); the product skill's own confirmation rules apply.

- Put supported child flags after the child command. `ve --profile <name> arkcli ...` is invalid;
  `ve arkcli ... --profile <name>` selects an **Ark** profile, not a `ve` profile.
- Follow the product skill's authentication, flags, and output handling. Change `tosutil ...` /
  `arkcli ...` / `volclog ...` into `ve tosutil ...` / `ve arkcli ...` / `ve volclog ...` while
  keeping all child arguments unchanged.
  For `ve arkcli`, use only the `VE_*` caller metadata as described in
  [Ark delegation](#ark-delegation-one-set-of-caller-variables); do not copy the standalone Ark
  caller/notifier prefix. Keep any required product environment assignments before `ve`.
- A working `ve sts GetCallerIdentity` does not prove either child is authenticated. Follow the
  selected product skill. Help, version, and local preview tasks do not require native API login.
- `ve` may refresh its current Console Login session before delegation; that does not translate
  all `ve` credentials or profile settings into child configuration. A refresh warning alone
  does not establish that the child command failed.

## Product CLI installation and upgrade

`ve` resolves the child from `PATH`, then its managed directory, and installs a missing child
on first use from the official CDN with checksum verification. A separate product installation
is not a prerequisite. Check only the child needed for the task:

```bash
ve tosutil version
ve tosutil help
ve arkcli --version
ve arkcli --help
ve volclog --version
ve volclog --help
```

Upgrade a managed child with `ve proxycli upgrade tosutil`, `ve proxycli upgrade arkcli` or
`ve proxycli upgrade tls-cli`. Management commands take the product ID (`tls-cli` for TLS),
while invocation uses the native command name (`ve volclog`).
These commands leave external installations on `PATH` to their original package manager;
upgrading `ve` alone does not upgrade them. If a child command is missing from `ve --help`,
upgrade `ve` first. Product flags and available capabilities follow the resolved child's help.

## Ark delegation: one set of caller variables

For `ve arkcli ...`, supply the three `VE_*` caller variables from
[SKILL.md](../SKILL.md#agent-caller-metadata-mandatory). `ve` converts them into
the Ark CLI environment, so the Agent must not also add `ARKCLI_CALLER_TYPE`,
`ARKCLI_CALLER_NAME`, or `ARKCLI_SKILL_NAME`. Do not copy `ARKCLI_NO_UPDATE_NOTIFIER=1` from
standalone Ark examples into the command prefix either; let `ve` manage the delegated process.
This applies to Ark authentication, model operations, help, and version commands.

```text
VE_CALLER_TYPE=ai_agent \
VE_CALLER_NAME="<agent-id>" \
VE_SKILL_NAME="<current-volcengine-skill>" \
  ve arkcli auth status
```

Replace the placeholders with your own Agent product name and the active Volcengine skill's
name; do not inspect environment variables to find them. When
reusing a process environment from a standalone Ark invocation, omit the four wrapper-managed
variables named above from this invocation. Preserve other product settings and credentials.
Standalone `arkcli ...` calls continue to follow the upstream Ark skill's environment rules.
