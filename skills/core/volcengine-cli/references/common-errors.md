# Common Error Handling

Use this reference when a Volcengine response includes `ResponseMetadata.Error`, especially for account state, real-name verification, purchase limits, service activation, or permission-looking errors.

## Real-Name Verification

Check the account verification state before assuming a request-format bug:

```bash
ve account_verify GetVerifyInfo \
  --version 2018-01-01 \
  --endpoint open.volcengineapi.com \
  --method POST \
  --force \
  --query 'Result.{IsVerified:IsVerified,IdentityType:IdentityType}'
```

Treat the account as not real-name verified when `IsVerified` is `false`. `IdentityType` is `individual` or `enterprise` when verified.

The console authentication page is:

```text
https://console.volcengine.com/user/authentication/detail/
```

Do not write real account IDs, request IDs, TRNs, personal names, certificate numbers, phone numbers, or resource IDs into shared troubleshooting notes.

## Error Classification

| Error code | Classification | Confirmed contexts | Handling |
| --- | --- | --- | --- |
| `AccountNotVerified` | Explicit real-name verification blocker | Organization `CreateOrganization` | Ask the user to complete console authentication, then retry. |
| `ErrNotVerifiedAccount` | Explicit real-name verification blocker | PrivateZone `ListPrivateZones` | Ask the user to complete console authentication, then retry. |
| `OperationDenied.InvalidAccount` with message containing `Account not verified yet or may not exist` | Explicit real-name verification blocker | CR `ListRegistries`, `GetPublicEndpoint`, `GetVpcEndpoint`, `ListNamespaces`, `ListRepositories`, `ListTags`, `CreateRegistry` | Check `GetVerifyInfo`; if unverified, ask the user to authenticate before retrying. |
| `Forbidden.PurchaseLimited` | Account purchase qualification or risk-control blocker | VPC `AllocateEipAddress` | Do not classify as real-name verification without `GetVerifyInfo` or product documentation. Escalate as account purchase eligibility. |
| `AccountPrivilegeInsufficient` | Account privilege blocker | RDS MySQL `CreateDBInstance` | Do not classify as real-name verification without another source. Check product/account permissions. |
| `AccountNoPermission` | Product permission blocker | VEENEdge `StartCloudServer`, `StopCloudServer`, `RebootCloudServer` | Do not classify as real-name verification without another source. Check product permission or entitlement. |
| `ProductUnsubscribed`, `ServiceNotActivated`, `KMS_ServiceNotOpen`, `OperationDenied.ServiceStopped` | Service not enabled or stopped | Multiple service activation checks | Treat as service activation/account service state, not as request-format bugs. |

## Local Safety Policy

These messages come from the user's local safety policy, not from the Volcengine service. No request was sent, so they are not permission, credential, or request-format errors and do not start a feedback invitation. Follow `SKILL.md` §2; never change the policy or its `VOLCENGINE_SAFETY_*` variables on your own to get past them.

| Message | Meaning | Handling |
| --- | --- | --- |
| `operation blocked by safety policy: <service> <Action> (rule: <pattern>)` / `操作被安全策略拒绝：<service> <Action>（规则：<pattern>）` | A `deny` rule matched | Stop and tell the user the operation was denied and cannot continue under the current policy. Ask whether they want to adjust the policy, then end the turn and wait. Do not retry, use another route, or change the policy on your own. |
| `safety policy requires confirmation for: <service> <Action>` / `安全策略要求确认以下操作：<service> <Action>` | A `confirm` rule matched in a non-interactive run | Explain the target and impact, ask, and end the turn. After a new approval, re-run the identical command once with `--yes`. |
| `Type 'yes' to proceed, anything else to cancel:` / `输入 'yes' 继续，其他任意输入取消：` | A `confirm` rule matched and stdin is a terminal, so `ve` is waiting for an answer | Never answer it or pipe input into `ve`. Leave it for the user to answer, or cancel it and handle the operation like the row above. |
| `operation cancelled by user` / `操作已由用户取消` | The interactive prompt got an answer other than `yes` | The operation did not run. Do not retry unless the user asks again. |
| `operation cancelled: confirmation input is unavailable` / `操作已取消：无法读取确认输入`, `operation cancelled: reading confirmation: ...` / `操作已取消：读取确认输入失败：...` | The prompt could not read an answer | The operation did not run. Handle it like a confirmation request. |
| `load effective safety policy: ...` | The policy file or a `VOLCENGINE_SAFETY_*` value is invalid; `ve` refuses every API call | Report the message to the user and stop. Do not edit the policy file or variables unless the user asks you to fix the policy. |

## Console Login Process Exited

The following helper error means the `ve login` process started by `scripts/ve_login_remote.sh` is no longer running:

```text
ERROR: no running ve login subprocess. Any previously recorded URL is dead
(its device code died with the process). Run './scripts/ve_login_remote.sh start <region>' for a fresh URL.
```

`url`, `verify` and `status` (`DEAD: no running ve login subprocess.`) all report this condition, and `url` refuses to print a recorded URL once its process is gone: the device code lives only in that process, so its URL, user code and prefilled `LINK` are unusable.

Distinct causes, which need different responses:

| Cause | Signal | Response |
| --- | --- | --- |
| The device code expired before the user approved (300 s lifetime) | `verify` exited **10** with `device authorization timed out` / `device code is invalid or expired` in the log; `status` showed `note=device-code-expired-...` beforehand | `abort`, then `start` again and hand the user the new `LINK`. Nothing to salvage. |
| The user denied the request in the browser | `verify` exited **10** with `device authorization was denied` in the log | `abort`, then `start` again. Ask the user to approve this time, or switch method if they refuse. |
| A managed runner killed background descendants when the launching call returned | `status` said `ALIVE` earlier, `DEAD` now, with no user approval in between | Retry `start` once. The helper launches ve with `setsid`, so it survives process-group cleanup; if it still dies, the runner is tearing down the whole cgroup and `ve login` is not viable here. |
| Nothing was ever started, or `abort` ran | No `.pid` file under `/tmp/ve_login_<uid>.*` | Run `start`. |

Recovery:

1. Run `scripts/ve_login_remote.sh abort` to remove stale state.
2. Start a new flow with `scripts/ve_login_remote.sh start <region> [profile]`. This call may hang until the runner's timeout — that is expected, and ve survives it. Do not retry it and do not replace it with `nohup ... &`.
3. Recover the new block with `scripts/ve_login_remote.sh url` in a separate call, and confirm liveness with `scripts/ve_login_remote.sh status` if needed.
4. Hand the user `LINK`; when they say they approved, run `scripts/ve_login_remote.sh verify [profile]`.

Use `start-wait` instead of steps 2–3 only where a single tool call can stay open for the entire browser round-trip.

If the runtime can neither hold a long-running tool session nor keep a `setsid` descendant alive, do not guess — fall back to another authentication method (AK/SK, STS token, or SSO).

Do not hand out a `LINK` printed by an exited login process.

## Login Succeeded but API Calls Fail with EOF

```text
LOGGED_IN_UNVERIFIED: ve reported 'Successfully logged in!', but GetCallerIdentity failed:
  RequestError: send request failed
  caused by: Post "https://open.volcengineapi.com/?Action=GetCallerIdentity&Version=2018-01-01": EOF
```

`verify` exit **13**. The login itself worked — ve wrote the session and exited 0 — but the agent host cannot complete a TLS handshake with `open.volcengineapi.com`. Seen when an `HTTPS_PROXY` is set and `NO_PROXY` whitelists `.volcengine.com` (so `signin.volcengine.com` and the login succeed) but not `.volcengineapi.com` (so every service API call is pushed through a proxy that drops it). `curl -sS https://open.volcengineapi.com/` reproduces it independently of `ve`.

Do **not** restart the login and do not switch credentials: every method would fail the same way. Report the connectivity problem to the user; once the host can reach `open.volcengineapi.com`, the cached session is used as-is.
