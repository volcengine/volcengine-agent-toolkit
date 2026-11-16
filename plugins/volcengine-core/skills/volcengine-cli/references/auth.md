# Credentials, profiles and login

## Credential safety

Credentials reach `ve` through its profile or the process environment. The Agent never needs to see them.

- **Never print or dump environment variables**: no `env`, `printenv`, `set`, `export -p`, `declare -x`, `echo $VOLCENGINE_*`, and no reading `/proc/*/environ`. This includes "pre-flight" or "environment" checks.
- **Never read `~/.volcengine/config.json`** or any other credential or login-cache file — they contain AK/SK and session tokens.
- **Do not rely on your own redaction**: piping those commands through `sed`, `grep`, `grep -v`, `awk` or `cut` to mask values is not allowed either. Hand-written masking is easy to get wrong, and the secret is then already in the tool output.
- **The only credential check is `ve sts GetCallerIdentity`.** Success means the credentials work; nothing else needs to be inspected. On failure, follow the login plan below.
- When running `ve configure set` with `--secret-key`, prefer letting the **user** paste and run the command in their own shell rather than executing it yourself — secrets passed as command-line arguments end up in shell history and process listings.
- Never write AK/SK, secret keys, or session tokens into replies, files, or logs in plain text.

## Profile selection (fixed for the conversation)

`ve` can use different credentials through profiles, but the agent must not choose a profile by itself.

- If the user did not explicitly select a profile, use the CLI default resolution: run `ve sts GetCallerIdentity` directly. Do not list all profiles first and choose one yourself.
- If the user explicitly selected a profile, keep using that same profile for all later commands in this conversation: `ve ecs DescribeInstances --profile prod`, `python3 scripts/call_extend_api.py --profile prod ...`.
- Do not infer the desired profile from profile name, region, list order, recent availability, success rate, or task content.
- If the default identity does not match the task risk, or a profile choice is required, tell the user the current default identity, list candidate profile names only, and wait for the user to choose.
- Once a profile is fixed for this conversation, do not switch to another profile unless the user explicitly asks to switch.

Run the identity verification command to confirm that credentials are usable:

```bash
ve sts GetCallerIdentity
```

**Success** — inform the user of the current account identity and region, then proceed with the task.

> **Switching regions later**: `--region` on a service API call **does** override the region for that single call (the response `Region` changes accordingly), and `VOLCENGINE_REGION` sets the default when the profile has none. What does **not** change is the profile's bound login session/account — a region override only redirects where the request goes, not who you are. Do not switch regions or profiles on your own initiative: only pass `--region` or switch profiles (`ve configure profile --profile <name>`) when the user explicitly asks. Use `ve configure list` only to show candidate profile names; after listing, do not choose a profile yourself. This is separate from the `--region` flag on `ve login` itself, which is required (see below).

**Failure** — no usable profile. Default plan: use `ve login` (Console Login). Announce this to the user up front, and tell them they can say "use AK/SK", "use STS token", or "use SSO" to switch.

The same plan applies when a previously working session expires **mid-task**: any `ve` command failing with `failed to refresh session token. Please run 've login' to re-authenticate` (or similar refresh-token/session-expired text) is this exact failure, no matter which skill issued the command. The error text tells the human to run `ve login` — do **not** relay that instruction to the user or ask them to run `ve login` in their own terminal; run the Console Login procedure below yourself and only hand the user the sign-in link. Re-login must target the profile that was in use: if a profile was fixed earlier in the conversation, pass it to `start` so both the login and its verification hit that profile — omitting it refreshes `default`, leaves the fixed profile broken, and pollutes the default account context.

## Default: Console Login via `scripts/ve_login_remote.sh`

**NEVER call `ve login` directly. ALWAYS use `scripts/ve_login_remote.sh`.** `ve login` is a device-code flow: ve prints a verification URL and user code, then polls until the user approves in a browser on any device. The device code lives only in that ve process, so the helper detaches it (`setsid`) to survive tool-call boundaries, records the URL/code, answers ve's prompts, and verifies the result. Calling `ve login` yourself orphans the process and kills the link.

**Before the first `start` of a conversation, read [references/console-login.md](console-login.md) completely** — it holds the step-by-step procedure, every exit code, the `start-wait` variant, tuning, and the full list of things that break the flow. The shape is:

```text
scripts/ve_login_remote.sh start <region> [profile]   # prints URL= CODE= LINK= EXPIRES_IN= NEXT=
scripts/ve_login_remote.sh url                        # same block, never blocks (11 = not yet, 3 = process gone)
# hand the user LINK (fallback: URL + CODE), end the turn, wait for "done"
scripts/ve_login_remote.sh verify [profile]           # 0 ok · 11 still pending · 13 logged in but API unreachable · 10 start over
scripts/ve_login_remote.sh abort                      # on user interrupt / expired code, then start again
```

Region: the one the user named; otherwise pass `"${VOLCENGINE_REGION:-cn-beijing}"` and let the shell expand it, without printing the variable. Pass `[profile]` only when the user fixed one earlier, and pass the same value to `start` and `verify`.

Invariants that must hold even without reading the reference:

- Announce the plan and the off-ramp ("say 'use AK/SK' to switch"), then start — do not present a menu of login methods.
- A hung or killed `start` proves nothing: call `url`/`status` before concluding anything; never retry `start`, `abort`, or switch to `nohup` because of it.
- Nothing is pasted back by the user; there is no authorization code. Run `verify` when they say they approved.
- `verify` exit 13 means the login **worked** and the host cannot reach `open.volcengineapi.com` — do not restart the login.
- Use `LINK` exactly as printed; never build `signin.volcengine.com` URLs or reuse one from an earlier process.
- `start` exit 4 = `ve` missing or too old for device-code login → install/upgrade ([install.md](install.md)), then retry.

If `ve login` fails (network error, `start` exit 4, no browser on any device), or the user asks for another method, fall back to the alternatives below.

## Alternative: AK/SK (long-term credentials, for CI/CD or scripting)

Ask the user for AccessKey and SecretKey, then:

```text
ve configure set --profile default --region cn-beijing \
  --endpoint open.volcengineapi.com \
  --access-key <AK> --secret-key <SK>
```

For STS (temporary) credentials, also pass `--session-token <TOKEN>`.

Alternative for the current shell only: the user exports `VOLCENGINE_ACCESS_KEY`, `VOLCENGINE_SECRET_KEY`, `VOLCENGINE_REGION`, optionally `VOLCENGINE_SESSION_TOKEN`. Do not print them back to check; run `ve sts GetCallerIdentity`.

## Alternative: SSO / Cloud Identity Center (for enterprise federation)

Three-step setup; ask the user for the SSO start URL and session name first:

```text
ve configure sso-session --name <session-name> \
  --start-url https://<sso-host>/userportal \
  --region cn-beijing \
  --registration-scopes cloudidentity:account:access,offline_access

ve configure sso --profile <profile-name> --sso-session <session-name>

ve configure profile --profile <profile-name>
```

Then `ve sso login --sso-session <session-name>` (use `--no-browser` on headless machines).
