# Console Login Procedure (`scripts/ve_login_remote.sh`)

This is the full procedure behind the Console Login summary in `SKILL.md` §1. Read it completely before the first `start` of a conversation; the summary in `SKILL.md` is not a substitute.

Apply [the mandatory Agent caller metadata](../SKILL.md#agent-caller-metadata-mandatory) to each
helper invocation, including `start` and the later `verify`. Prefix the helper process with
`VE_CALLER_TYPE=ai_agent VE_CALLER_NAME=<agent-id> VE_SKILL_NAME=<current-volcengine-skill>`;
its help checks, detached login, and verification calls inherit those values. Preserve the
calling workflow's skill name when this shared helper is used by another Volcengine skill.

**IMPORTANT: NEVER call `ve login` directly. ALWAYS use the helper script `scripts/ve_login_remote.sh`.** It keeps the login subprocess alive across tool calls, extracts the URL and code, answers ve's interactive prompts, verifies the result, and cleans up. Calling `ve login` directly orphans the subprocess and loses the device code the URL depends on.

`ve login` is an OAuth 2.0 device-code flow: ve prints a verification URL and a short user code, then polls the server itself until the user approves in a browser on **any** device. **Nothing comes back from the user** — you run `verify` after they say they are done. The code expires after `EXPIRES_IN` seconds (300 today). The script prints a `KEY=value` block, so read the keys — never parse prose.

**Resolve the login region:**

1. If the user named a region in this conversation, use it.
2. Else if `VOLCENGINE_REGION` is set, use it.
3. Else default to `cn-beijing`.

**Default procedure** — commit to this path; do NOT present a menu of login methods:

1. **Announce + give the user an off-ramp**, then immediately start:
   > "I'll start Console Login (`ve login`, region `<region>`) now. Say 'use AK/SK' anytime to switch."

2. **Start the login subprocess:**

   ```text
   scripts/ve_login_remote.sh start <region> [profile]
   ```

   `start` launches `ve login --no-browser` detached with `setsid`, so it keeps its own session and a PPID of 1. It survives this tool call being killed and survives process-group cleanup. On success it prints:

   ```text
   URL=https://signin.volcengine.com/authorize/oauth/device?trace_id=<id>
   CODE=XXXX-XXXX
   LINK=https://signin.volcengine.com/authorize/oauth/device?trace_id=<id>&user_code=XXXX-XXXX
   EXPIRES_IN=300
   NEXT=...
   ```

   `NEXT` always states the exact follow-up command.

   **This call may not return.** Some sandbox runners do not consider a command finished while a descendant is still alive, so `start` can hang until the runner's own timeout kills it. **A hung or killed `start` is not a failure signal, and not a success signal either** — it tells you nothing about the session. Do **not** retry `start`, do **not** `abort`, and do **not** switch to `nohup` on the strength of it. Go to step 3 and let `url`/`status` decide.

   Detaching makes survival likely, not certain: a runner that tears down the whole cgroup or container on timeout takes ve with it regardless. Step 3 is what tells you which happened.

   Pass `[profile]` **only** when the user explicitly fixed a profile earlier in the conversation (never pick one yourself); omit it to use the CLI default resolution.

   `start` exits 4 when `ve` is missing or its `ve login --help` lacks `--no-browser` — install or upgrade (§0) and retry.

3. **Read the block back in a separate tool call** (skip if `start` already returned it):

   ```text
   scripts/ve_login_remote.sh url [profile]
   ```

   `url` never blocks. It prints the same block (exit 0), or `PENDING` (exit 11) if ve has not emitted the URL yet — retry `url` once after a moment. Exit 3 means there is no live subprocess: only then run `abort` and restart from step 2.

   `scripts/ve_login_remote.sh status` (also non-blocking) reports `ALIVE: pid=<pid> url=<yes|no> age=<n>s` if you need to confirm the subprocess independently; it appends `note=device-code-expired-...` once the device code is past its lifetime.

4. **Hand the link to the user and end the turn.** Do not use `ask_user`, decision prompts, or any other pausing tool — reply normally and wait for the user's next message. Send `LINK` as the primary action, with `URL` + `CODE` as the fallback, e.g.
   > "Open this link and approve the login: `<LINK>` (or open `<URL>` and enter code `<CODE>`). The code is valid for 5 minutes. Tell me when you're done."

   Nothing is pasted back. When the user says they finished, go to step 5.

5. **Verify** after the user says they authorized:

   ```text
   scripts/ve_login_remote.sh verify [profile]
   ```

   Pass the same `[profile]` you passed to `start`. Read the exit code:

   - **0** — logged in and `ve sts GetCallerIdentity` verified. Proceed with the task.
   - **11 (`PENDING`)** — ve is still running: the user has not actually finished in the browser. Not a failure. The message tells you how much of the device code's lifetime is used up. Ask the user to confirm they approved, then run `verify` again. Do not `abort` on 11 unless the message says the code has expired.
   - **13 (`LOGGED_IN_UNVERIFIED`)** — ve printed `Successfully logged in!` but the verification API call failed (typically `send request failed ... EOF` to `open.volcengineapi.com`). **The login succeeded**; the agent host cannot reach the API endpoint (proxy / `NO_PROXY` / firewall). Do **not** restart the login. Tell the user, and treat subsequent `ve` API failures as the same connectivity problem.
   - **10** — ve exited without a session: device code expired (5 minutes) or the user denied the request. Run `abort`, then restart from step 2 for a fresh link.

   > **Session replacement**: When the user is switching to a different account on a profile that already holds a session, `ve` asks `Replace the existing login_session? [y/N]:` on stdin *after* the user has approved in the browser. The script pre-answers it at `start`, so no extra call is needed.

6. **If the user interrupts** (says "use AK/SK", "cancel", "this is taking too long", etc.):

   ```text
   scripts/ve_login_remote.sh abort
   ```

   Then switch to the chosen alternative below.

**`start-wait` — only for runtimes that hold a long tool session open.** It prints the same block, stays blocked while ve runs, and finishes by running `verify` itself:

```text
scripts/ve_login_remote.sh start-wait <region> [profile]
```

Use it only when the runtime can keep one tool call open for the **entire browser round-trip** — several minutes of human latency — *and* lets you read the call's interim output while it runs (e.g. a background/async invocation such as `run_in_background`, whose output file you can read to pick up `LINK`). Hand the user the link, end the turn, and wait for the call's completion notification; its exit code is `verify`'s. If the runtime cannot hold a call open that long, `start-wait` will simply time out; use the `start` + `url` flow above instead, which is the default for exactly this reason.

**Tuning** — `VE_LOGIN_URL_TIMEOUT` (default 30s) is how long `start` waits for ve to emit the URL. **On expiry `start` kills ve and wipes the state**, so lowering it can destroy a session that was merely slow to start. It also does **not** shorten how long the `start` call appears to hang: that hang comes from the runner waiting on a live descendant, not from this timeout. Leave it alone unless ve genuinely needs longer than 30s to print the URL.

**Critical rules — do NOT improvise OAuth:**

- ❌ Do NOT present a menu like "A. URL  B. local browser  C. AK/SK". Commit to the script's flow; let the user interrupt to switch.
- ❌ Do NOT let the login subprocess die while the user is in the browser. The device code lives only in that process's memory; the URL, code and link all die with it.
- ❌ Do NOT treat a hung or timed-out `start` as a failure. Call `url` and `status` before concluding anything. Retrying `start` or calling `abort` throws away a link that is already usable.
- ❌ Do NOT substitute `nohup ... &` for `start`. `nohup` only ignores SIGHUP and leaves ve in the caller's process group, so group cleanup still kills it. The script already uses `setsid`, which is what actually detaches it.
- ❌ Do NOT hand the user a URL recovered from a stale log or from an earlier attempt. A link is only usable while its own ve process lives — `url` enforces this and refuses to print one whose process has gone.
- ❌ Do NOT hand out a device link after `EXPIRES_IN` has passed (`status` flags it). `abort` and `start` again.
- ❌ Do NOT pre-fetch the URL by running `ve login` and exiting, and do NOT run `ve login` without the script. The state dies with the subprocess; the link becomes useless.
- ❌ Do NOT construct `signin.volcengine.com/...` URLs yourself, including appending `user_code=` by hand — use `LINK` exactly as printed.
- ❌ Do NOT pass `--lang` to `ve login` yourself or expect Chinese output from the helper: `ve` follows the system locale, so the script pins `--lang en` — its parsing anchors are English. The `LINK`/`URL`/`CODE` you hand to the user are language-neutral.
- ❌ Do NOT call `ve login` without `--no-browser`: it tries to open a browser on the agent host, which is useless on a headless box and hijacks the user's desktop on a shared one. The script always passes it.
- ❌ Do NOT ask the user to paste anything back. There is no authorization code in this flow (the script rejects `complete` with exit 2). Run `verify` once the user says they approved.
- ❌ Do NOT spawn parallel `ve login` subprocesses. One at a time, tracked by the helper.
- ❌ Do NOT restart the login on `verify` exit 13. The login worked; the host's route to `open.volcengineapi.com` is what is broken.
- ✅ Default to `start` → `url` → hand over link → `verify`. Use `start-wait` only where a single tool call can stay open for the whole round-trip.

> **Switching region mid-flow**: run `scripts/ve_login_remote.sh abort`, then restart from step 2.
> **No browser on any device** (true offline / CI): skip `ve login`, fall back to AK/SK below.

If `ve login` fails (network error, non-interactive terminal, `start` exit 4), or the user explicitly asks for a different method, fall back to one of the alternatives below.
