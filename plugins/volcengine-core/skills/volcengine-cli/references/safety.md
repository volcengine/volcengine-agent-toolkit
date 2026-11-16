# Safety rules and confirmation modes

These apply in every conversation:

1. **Default to read-only** — unless the user explicitly requests a change, execute in read-only mode
2. **Protect credentials** — never print or dump environment variables (`env`, `printenv`, `set`, `export -p`, `echo $VOLCENGINE_*`), not even through a `sed`/`grep` filter; never read `~/.volcengine/config.json`; never expose access-key, secret-key, or session-token in output. Check credentials only with `ve sts GetCallerIdentity` ([auth.md](auth.md))
3. **Leave the safety policy alone** — unless the user explicitly asks to change the policy itself, never run `ve configure safety-policy enable|disable|add|remove`, never read or edit `~/.volcengine/safety-policy.json`, and never set, unset or override `VOLCENGINE_SAFETY_POLICY_ENABLED`, `VOLCENGINE_SAFETY_POLICY_RULES` or `VOLCENGINE_SAFETY_SKIP_CONFIRM` in a command prefix, script or environment

Approval to execute or retry an operation does not authorize changing the safety policy. A policy change requires an explicit request to change the policy itself.

For native OpenAPI calls, use exactly one confirmation source: the CLI when the safety policy is enabled and its rules are non-empty, otherwise this skill's built-in rules. Never apply both to the same operation.

## Choose the confirmation mode

Before the first native `ve <service> <Action>` call of a conversation, including `ve sts GetCallerIdentity`, run this with the same caller metadata and environment as the later calls:

```bash
ve configure safety-policy show
```

Decide from stdout and the message text, not the exit code. A `ve` without safety policy support has no `safety-policy` command: it prints `ve configure` usage to stderr, nothing to stdout, and still exits 0.

| Output | Mode |
| --- | --- |
| stdout is JSON with `"enabled": true` and a non-empty `rules` list | **Safety policy** — let the CLI enforce it; do not apply the skill's built-in confirmation rules |
| stdout is JSON with `"enabled": false` or an empty `rules` list | **Built-in rules** — follow [Built-in rules](#built-in-rules) only |
| The output contains `load effective safety policy:` | Neither. `ve` refuses every API call until the policy is fixed; report the error to the user and stop. |
| Anything else: empty stdout, `ve configure` usage, an unknown-command error, or other non-JSON output, whatever the exit code | **Built-in rules** — the `ve` does not support a safety policy |

Read only `enabled` and whether `rules` is empty to choose the mode. Do not interpret, match, or cache individual policy rules to decide whether an operation may run; the CLI makes that decision.

Keep the mode for the conversation. Run `show` again only when the user says the policy changed, or when a call in built-in mode is blocked or asks for confirmation — then continue in the mode the new output selects.

## Built-in rules

Apply these to native calls only in built-in mode. Extension-helper calls retain these built-in confirmation rules.

| Level | Operation Types | Behavior |
|-------|----------------|----------|
| **Read-only** | Describe\* / List\* / Get\* / Query\* | Execute directly, no confirmation needed |
| **Write** | Create\* / Run\* / Allocate\* / Attach\* / Associate\* / Authorize\* | Show the full command and wait for user confirmation |
| **Destructive** | Delete\* / Terminate\* / Release\* / Revoke\* / Modify\* / Stop\* / Detach\* | Show command + impact summary; **require** user confirmation |

1. **DryRun first** — if a write/destructive operation supports `--DryRun true`, run a DryRun to preview the plan, then confirm before executing
2. **Confirm before executing** — show the full command for write operations and wait for approval

Confirmation notes in the references ("confirm with the user first", "require explicit confirmation") belong to these rules.

## Local safety policy

For native calls in safety-policy mode, do not apply the built-in rules above or the confirmation notes in the references. `ve` checks every native call, including `--force` calls, so run the command the task needs and act on the CLI's result:

| `ve` result | Policy decision | Action |
| --- | --- | --- |
| API response or API error | No safety-policy block | Handle the normal API result or error; do not add another confirmation step. |
| `operation blocked by safety policy: <service> <Action> (rule: <pattern>)` / `操作被安全策略拒绝：...` | `deny`; no request was sent | Stop and tell the user the operation was denied and cannot continue under the current policy. Ask whether they want to adjust the policy, then end the turn and wait. Do not retry or change the policy on your own. |
| `safety policy requires confirmation for: <service> <Action>` / `安全策略要求确认以下操作：...` | `confirm`; no request was sent | Briefly explain the target and impact, ask whether to continue, and end the turn. After a new explicit approval, re-run the identical command once with `--yes` added. The approval is then used up, even if that call fails. |

- Start every operation without `--yes` (or `-y`); add it only for the single approved retry. Approvals from earlier in the conversation, including for the same command, do not count.
- If `ve` waits at `Type 'yes' to proceed` / `输入 'yes' 继续`, never answer it or pipe input into `ve`; other messages are in [references/common-errors.md](common-errors.md#local-safety-policy).
- Run one write or destructive operation per tool call and check its result before the next; a blocked command inside a multi-command shell block does not stop the commands after it. Reads can be held for confirmation too: stop a polling loop when a call is intercepted.
- When several operations need confirmation, run each once without `--yes`, list every intercepted command for the user, and retry with `--yes` only the commands the user explicitly approves, once each.
- Do not reach a denied or held operation another way: no other spelling or version of the service, `--force`, Cloud Control, the extension helper, a product CLI, an SDK or raw HTTP. `ve` applies a rule to every spelling of a service (`rds_mysql`, `rdsmysql` and `rdsmysqlv2`; `cloudtrail` and `cloudtrail20180101`).
- The policy does not cover delegated product CLIs (`ve tosutil`, `ve arkcli`, `ve volclog`); follow their product skill.

## DryRun notes

A successful DryRun validation returns **exit code 1** (non-zero) with `DryRunOperation` in stderr. This is expected behavior:

```text
output=$(ve <svc> <action> --DryRun true ... 2>&1)
if echo "$output" | grep -q "DryRunOperation"; then
  echo "Parameter validation passed"
fi
```
