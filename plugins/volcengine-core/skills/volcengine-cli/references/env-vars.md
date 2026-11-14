# Environment variables and caller metadata details

Never print these variables or dump the environment to see whether they are set
(`env`, `printenv`, `set`, `export -p`, `echo $VOLCENGINE_*`), filtered or not. `ve` reads them
itself; `ve sts GetCallerIdentity` is the only credential check ([auth.md](auth.md)).

## Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `VE_CALLER_TYPE` | yes | Set by the Agent for every `ve` process; always `ai_agent` |
| `VE_CALLER_NAME` | yes | The Agent's own product name (e.g. `codex`, `claude-code`), written by the Agent on each invocation; no fixed default |
| `VE_SKILL_NAME` | yes | Frontmatter `name` of the Volcengine skill that owns the operation; no fixed default |
| `VOLCENGINE_ACCESS_KEY` | no | AccessKey for the AK/SK auth path (alternative to `ve login`) |
| `VOLCENGINE_SECRET_KEY` | no | SecretKey for the AK/SK auth path |
| `VOLCENGINE_SESSION_TOKEN` | no | STS session token for temporary credentials |
| `VOLCENGINE_REGION` | no | Default region; falls back to `cn-beijing` if unset |
| `VOLCENGINE_ENDPOINT` | no | Fallback endpoint for `--force` calls and extension-helper calls that do not define a product endpoint |
| `VOLCENGINE_PROFILE` | no | Volcengine CLI profile name used by the extension helper credential fallback |
| `VOLCSTACK_PROFILE` | no | Legacy alias of `VOLCENGINE_PROFILE` honoured by the extension helper credential fallback |
| `VOLCENGINE_CLI_CONFIG_FILE` | no | Full path to the Volcengine CLI config file; defaults to `~/.volcengine/config.json` |
| `VOLCENGINE_LOGIN_CACHE_DIRECTORY` | no | Console-login cache directory used by the extension helper credential fallback |
| `VOLCENGINE_CLI_DOWNLOAD_BASE_URL` | no | Base URL (or local mirror directory) that `scripts/install_ve.sh` downloads release archives from; defaults to `https://cloudcache.volccdn.com/ve` |
| `VOLCENGINE_CLI_SKIP_SKILLS` | no | Set to `1` to stop `scripts/install_ve.sh` from running `ve skills update` after installing |
| `VE_VERSION` | no | Pin the `ve` version `scripts/install_ve.sh` installs instead of reading the CDN latest file |
| `VE_INSTALL_DIR` | no | Directory `scripts/install_ve.sh` installs `ve` into; defaults to `/usr/local/bin` when writable, else `~/.local/bin` |
| `VE_LOGIN_URL_TIMEOUT` | no | Seconds `scripts/ve_login_remote.sh` waits for `ve login` to print its URL (default 30) |

## Caller metadata details

The rules are in [SKILL.md](../SKILL.md#agent-caller-metadata-mandatory). Additional cases:

- The three values are runtime attribution, not credentials or a user setup step. Only
  `VE_CALLER_TYPE=ai_agent` is fixed. `codex` is valid only when the Agent is Codex, and
  `volcengine-cli` only when that skill owns the current operation; change `VE_SKILL_NAME` when
  the workflow moves to another Volcengine skill.
- Shared helpers and upstream product CLIs inherit the calling Volcengine skill's identity; their
  executable names or installation directories do not determine it.
- A new tool call may start a fresh shell, so an earlier `export` is not sufficient. For a
  multi-command shell block, export all three at the beginning of that block. For pipelines and
  `$(...)`, set the variables on the `ve` process itself or export them in that same shell first.
- Apply the same environment to any script that launches `ve`, including `install_ve.sh`,
  `ve_login_remote.sh`, `audit_extend_apis.py`, and `call_extend_api.py`. Their child processes
  inherit it, including detached login processes; later helper invocations need it again.
- When running a downloaded installer through a pipe, attach the environment to the shell running
  the installer, not only to the download command.
- Put assignments before the executable; they are not CLI flags, API parameters, or request-body
  fields. Never add the `VOLCENGINE_SAFETY_*` variables to this prefix ([safety.md](safety.md)).
- For `ve arkcli`, see [Ark delegation](product-cli.md#ark-delegation-one-set-of-caller-variables).
- Command examples in this skill and its references show syntax only; the caller metadata applies
  to every execution of them.
