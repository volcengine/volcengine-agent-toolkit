---
name: volcengine-cli
description: >-
  Create and manage Volcengine cloud resources using the Volcengine CLI (`ve` command). Supports all
  Volcengine services including ECS, VPC, CLB, RDS, Redis, and more. Trigger this skill whenever the
  user asks to create, query, modify, or delete cloud resources on Volcengine, mentions the `ve` command,
  says "volcengine CLI", or describes infrastructure tasks such as "create an ECS instance",
  "set up a VPC", "list security groups", "allocate an EIP". Also trigger on Chinese prompts
  mentioning "火山引擎" or "火山" (e.g., "火山引擎上有哪些 ECS"、"查一下我火山的云服务器"、
  "火山引擎创建一个 VPC"), on `ve` command errors, and for account real-name verification
  (实名认证) or extended OpenAPIs missing from CLI metadata. Also use for TOS bucket/object operations,
  tosutil (sometimes written tosutils), Ark (方舟) / arkcli models, prices, API Keys, inference,
  generation, endpoints, plans, or usage, and TLS (日志服务) / volclog log search, analysis, ingest,
  export, or LogCollector collection, through `ve tosutil`, `ve arkcli` and `ve volclog`.
license: MIT
metadata:
  openclaw:
    requires:
      bins:
        - ve
        - npx
      env:
        - VE_CALLER_TYPE
        - VE_CALLER_NAME
        - VE_SKILL_NAME
    install:
      - kind: node
        package: "@volcengine/cli"
        bins: [ve]
    envVars:
      - name: VE_CALLER_TYPE
        required: true
      - name: VE_CALLER_NAME
        required: true
      - name: VE_SKILL_NAME
        required: true
      - name: VOLCENGINE_ACCESS_KEY
        required: false
      - name: VOLCENGINE_SECRET_KEY
        required: false
      - name: VOLCENGINE_SESSION_TOKEN
        required: false
      - name: VOLCENGINE_REGION
        required: false
      - name: VOLCENGINE_ENDPOINT
        required: false
      - name: VOLCENGINE_PROFILE
        required: false
      - name: VOLCSTACK_PROFILE
        required: false
      - name: VOLCENGINE_CLI_CONFIG_FILE
        required: false
      - name: VOLCENGINE_LOGIN_CACHE_DIRECTORY
        required: false
      - name: VOLCENGINE_CLI_DOWNLOAD_BASE_URL
        required: false
      - name: VOLCENGINE_CLI_SKIP_SKILLS
        required: false
      - name: VE_VERSION
        required: false
      - name: VE_INSTALL_DIR
        required: false
      - name: VE_LOGIN_URL_TIMEOUT
        required: false
---

# Volcengine CLI Skill

## Credential safety (mandatory)

`ve` finds its credentials by itself. You never need to see them, in whole or in part.

- **Never print or dump environment variables**: no `env`, `printenv`, `set`, `export -p`, `declare -x`, `echo $VOLCENGINE_*`, no reading `/proc/*/environ`. "Pre-flight" and "environment" checks are no exception.
- **Never read `~/.volcengine/config.json`** or other credential/login-cache files.
- **No self-made redaction**: do not pipe the above through `sed`, `grep`, `grep -v`, `awk` or `cut` to mask values, and do not print a prefix, suffix or length of a secret. Such filters are easy to get wrong and leak it.
- **The only credential check is `ve sts GetCallerIdentity`.** Success = usable. Failure = follow [references/auth.md](references/auth.md); do not inspect or edit the credentials to debug it.
- Never put an AccessKey, SecretKey or session token in a reply, file or log.

## Agent caller metadata (mandatory)

Prefix **every** `ve` execution (help, version, login, API calls, retries, polling, product CLIs) and every `scripts/` helper with three variables:

```text
VE_CALLER_TYPE=ai_agent VE_CALLER_NAME="<agent-id>" VE_SKILL_NAME="<current-volcengine-skill>" \
  ve ecs DescribeInstances --output json
```

| Variable | Value |
| --- | --- |
| `VE_CALLER_TYPE` | Always `ai_agent`. |
| `VE_CALLER_NAME` | Your own Agent product name, such as `codex` or `claude-code`. You already know which Agent you are: write it directly, and do not look at environment variables or host information to find it. It names the Agent application, not a model, account or user. |
| `VE_SKILL_NAME` | The frontmatter `name` of the Volcengine skill whose workflow runs the command; `volcengine-cli` when this skill owns it. |

- Write the values yourself; never pass the placeholders or copy another Agent's name.
- A tool call may start a fresh shell: repeat the prefix every time. In pipelines and `$(...)` it must reach the `ve` process itself.
- These are assignments, not flags or request fields. Never add `VOLCENGINE_SAFETY_*` here.
- `ve arkcli`: these three only, no `ARKCLI_*` variables. More cases: [references/env-vars.md](references/env-vars.md).

**Next: `Product CLI routing` and `Native OpenAPI essentials`.** If you cannot see both headings below, your tool cut them out; before your first `ve` call run:

```text
sed -n '/^## Product CLI routing/,/^## References/p' <path-of-this-SKILL.md>
```

## Product CLI routing

| Task | Entry point | Read before use |
| --- | --- | --- |
| Cloud resource OpenAPIs | `ve <service> <Action>` | [locate-api.md](references/locate-api.md), [execute-api.md](references/execute-api.md) |
| TOS buckets, objects and transfers | `ve tosutil <command>` | [product-cli.md](references/product-cli.md), then skill `volcengine-tosutil` |
| Ark (火山方舟) models, model prices, API Keys, inference, generation, endpoints, fine-tuning, plans, usage | `ve arkcli <command>` | [product-cli.md](references/product-cli.md), then skill `volcengine-ark` |
| TLS (日志服务) search, analysis, ingest, export, LogCollector | `ve volclog <command>` | [product-cli.md](references/product-cli.md), then `volcengine-tls` / `volcengine-tls-logcollector` |

- Prefer the `ve` proxy even when a standalone `tosutil`, `arkcli` or `volclog` is installed. `ve` installs a missing child on first use.
- Replace only the executable prefix of the product skill's examples (`tosutil ...` → `ve tosutil ...`); keep every later argument. Child flags go after the child command.
- Delegated CLIs keep their own authentication, profiles, flags, output and confirmation rules. Native rules (`--output`, `--query`, `--force`, `--DryRun`, the safety policy and its `--yes` retry) do not carry over, and a working `ve sts GetCallerIdentity` does not prove the child is authenticated.
- `ve` has no native `tls` service: never use `--force` for TLS; an unknown-service answer from `ve volclog` means `ve` is too old.

## Native OpenAPI essentials

Details and examples: [locate-api.md](references/locate-api.md) and [execute-api.md](references/execute-api.md).

- **Find the API**: `ve <service> 2>&1 | grep -i <keyword>` for the Action, `ve 2>&1 | grep -i <keyword>` for the service, then `python3 scripts/find_api.py <keyword>`, then [extend-apis.md](references/extend-apis.md) (some APIs such as `account_verify` `GetVerifyInfo` are absent from both `ve` metadata and `find_api.py`). A non-default API version is a separate command (`iam` v2021-08-01 → `iam20210801`).
- **Parameters**: `ve <svc> <Action> --help`; add `--detail` for write/destructive actions or after `Invalid*` / `Missing*` errors. Never guess parameter names.
- **Shape**: API parameters are PascalCase (`--InstanceIds.1 i-xxx`, `--Tags.1.Key k`), system flags are lowercase and follow the Action (`--region`, `--profile`, `--output`, `--query`). When `--help` shows only `--body`, pass one JSON body: `--body '{...}'`.
- **Output**: keep the default `json` for your own reading; `--query '<JMESPath from Result.>'` with `--output text` to capture IDs, `--output table` to show lists to the user. Do not use `--output off` on `Create*` / `Run*` / `Allocate*`.
- **Async resources**: poll the `Describe*` call with a deadline until the target status; take status names from `--help --detail` and the service note.
- **DryRun**: a successful `--DryRun true` exits 1 with `DryRunOperation` in stderr; that is the pass signal.

### Extended APIs (`--force` and query+body helper)

When an OpenAPI is missing from `ve` metadata (`unknown service` / `unknown action`) or absent from `find_api.py`, check [extend-apis.md](references/extend-apis.md) and [extend-api-params.md](references/extend-api-params.md) before concluding `ve` cannot call it (covers `account_verify`, CDN, CodePipeline, DCDN, `domain_openapi`, Flink, GA, IoT, Live, MCDN, Metrics, `sec_agent`, `trademark`, VEEN, VKE VirtualNode, and VMP):

1. **`ve ... --force` (default)** — for any Action/Version OpenAPI: pass `--version <YYYY-MM-DD>`, `--endpoint <host>` (mandatory for unknown services, usually `open.volcengineapi.com`), `--method POST` when needed, `--region <signing-region>` when fixed, and `--force` (presence-only, never `--force true`).
2. **`python3 scripts/call_extend_api.py` (query + body split only)** — only for POST APIs that need URL query parameters *and* a request body in one call (VMP Prometheus, Flink GWS; inspect with `--list` / `--describe <Action>`, see [extend-api-helper.md](references/extend-api-helper.md)). Never use `--force` for TLS (`ve volclog` owns TLS).

**Account real-name verification (`实名认证`)**: when the user asks whether the account is real-name verified, needs real-name authentication, a product pre-check requires personal/enterprise verification, or an API returns `AccountNotVerified` / `ErrNotVerifiedAccount` ([common-errors.md](references/common-errors.md)), call the `account_verify` extension API:

```bash
VE_CALLER_TYPE=ai_agent VE_CALLER_NAME="<agent-id>" VE_SKILL_NAME="<current-volcengine-skill>" \
  ve account_verify GetVerifyInfo \
    --version 2018-01-01 --endpoint open.volcengineapi.com \
    --method POST --force \
    --query 'Result.{IsVerified:IsVerified,IdentityType:IdentityType}'
```

- `IsVerified: true` means verified (`IdentityType` is `"individual"` or `"enterprise"`; `"individual"` does not satisfy enterprise-only requirements).
- Submitting KYC documents or face recognition has no OpenAPI: when `IsVerified` is `false` (or the user needs to complete/upgrade verification), report the status, direct them to `https://console.volcengine.com/user/authentication/detail/`, wait for confirmation, and re-run `GetVerifyInfo` to confirm.

## References

If the text above this heading shows a `truncated` marker, the two sections before it were cut: run `sed -n '/^## Product CLI routing/,/^## References/p'` on this file. Then read the reference for your step.

- Install / upgrade `ve`: [install.md](references/install.md)
- Credentials, profiles, login: [auth.md](references/auth.md); Console Login procedure: [console-login.md](references/console-login.md)
- Confirmation modes, safety policy, DryRun: [safety.md](references/safety.md)
- Find the API, parameters, `--force`: [locate-api.md](references/locate-api.md); `--force` recipes: [extend-apis.md](references/extend-apis.md), [extend-api-params.md](references/extend-api-params.md); query+body helper: [extend-api-helper.md](references/extend-api-helper.md)
- System flags, parameters, `--output` / `--query`, polling: [execute-api.md](references/execute-api.md)
- Product CLIs: [product-cli.md](references/product-cli.md); errors: [common-errors.md](references/common-errors.md)
- Service notes: [alb](references/alb.md), [clb](references/clb.md), [cloudcontrol](references/cloudcontrol.md) ([writes](references/cloudcontrol-write.md)), [cr](references/cr.md), [dns-edge](references/dns-edge.md), [ebs](references/ebs.md), [ecs](references/ecs.md), [iam](references/iam.md), [kms](references/kms.md), [mq](references/mq.md), [natgateway](references/natgateway.md), [observability](references/observability.md), [rds](references/rds.md), [redis](references/redis.md), [storage](references/storage.md), [vefaas](references/vefaas.md), [vke](references/vke.md), [vpc](references/vpc.md)

## Mandatory rules

1. **Version** — before any other `ve` command in a task, run `ve version` and require `ve >= 1.1.11`, also for product CLI delegation. Missing or older: [references/install.md](references/install.md).
2. **Read-only by default** — change resources only when the user explicitly asks.
3. **Leave the safety policy alone** — unless the user explicitly asks to change the policy itself, never run `ve configure safety-policy enable|disable|add|remove`, never read or edit `~/.volcengine/safety-policy.json`, never set `VOLCENGINE_SAFETY_POLICY_ENABLED`, `VOLCENGINE_SAFETY_POLICY_RULES` or `VOLCENGINE_SAFETY_SKIP_CONFIRM`.
4. **Confirmation mode** — before the first native call of a conversation (including `ve sts GetCallerIdentity`) run `ve configure safety-policy show`, then **read [references/safety.md](references/safety.md) before any write or destructive call**.
   - JSON with `"enabled": true` and non-empty `rules`: the CLI enforces. Run without `--yes`. `requires confirmation` → ask the user, end the turn, then re-run the identical command once with `--yes`. `blocked by safety policy` → stop; no other route.
   - Anything else: built-in rules. `Describe*/List*/Get*/Query*` run directly. `Create*/Run*/Allocate*/Attach*/Associate*/Authorize*` → show the full command and wait for confirmation. `Delete*/Terminate*/Release*/Revoke*/Modify*/Stop*/Detach*` → show command and impact; confirmation required. DryRun first when supported.
5. **Profile and region** — never choose or switch them yourself; pass `--profile` / `--region` only when the user explicitly selected one, then keep it.
6. **Login** — never call `ve login` directly and never ask the user to run it. Read [references/auth.md](references/auth.md) and use `scripts/ve_login_remote.sh`, also when a session expires mid-task.
7. **Errors** — when a command fails or returns `ResponseMetadata.Error`, read [references/common-errors.md](references/common-errors.md) completely before diagnosing. Permission errors: use `volcengine-troubleshooting`.

## Native OpenAPI execution flow

```text
1. Caller metadata on every command -> ve version -> ve configure safety-policy show (rule 4)
2. Run `ve sts GetCallerIdentity`. This IS the credential check: do not look at environment
   variables or config files. Report identity and region.
3. Is the user querying or changing something?
4. Locate the API: ve <service> | grep -> scripts/find_api.py -> extend-apis.md (--force / helper)
5. Parameters: --help; --help --detail for write/destructive actions
6. Dependent IDs: Describe*/List* with --query
7. Read -> execute and show results (--output table for lists)
   Write, built-in rules -> show command -> DryRun if supported -> user confirms -> execute
   Write, safety policy  -> execute -> if blocked or held, follow references/safety.md
8. Parse the response and report
```

Credential reminder: never run `env`, `printenv`, `set`, `export -p` or `echo $VOLCENGINE_*`, with or without a `sed`/`grep` filter, and never read `~/.volcengine/config.json`. `ve sts GetCallerIdentity` is the only credential check; if it fails, follow references/auth.md instead of inspecting the credentials.
