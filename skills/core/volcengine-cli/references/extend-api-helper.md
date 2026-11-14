# Extension helper: `scripts/call_extend_api.py`

For the few APIs that need URL query parameters *and* a request body in one POST. Everything else uses `ve ... --force` ([extend-apis.md](extend-apis.md)). Extension-helper calls keep the built-in confirmation rules ([safety.md](safety.md)), and need the [caller metadata](../SKILL.md#agent-caller-metadata-mandatory) like any `ve` call.

`ve --force` cannot put some parameters in the URL query string and the rest in a body (`--body` excludes flattened parameters, and the body is JSON only). The helper does exactly that and nothing else.

```bash
python3 scripts/call_extend_api.py --list                 # registered APIs and their query keys
python3 scripts/call_extend_api.py --describe QueryMetrics
```

### Registered APIs

| Service | Version | Endpoint | Body | Actions and URL query keys |
| --- | --- | --- | --- | --- |
| `vmp` | `2021-03-03` | `vmp.<region>.volcengineapi.com` | `application/x-www-form-urlencoded` | `QueryMetrics`, `QueryMetricsRange`, `GetLabels`, `GetSeries` → `workspace`; `GetLabelValues` → `workspace`, `label` |
| `flink` | `2021-06-01` | `open.volcengineapi.com` | JSON | `ListGWSDirectory` → `ProjectId`, `Type`; `GetGWSApplicationDraft`, `DeleteGWSApplication`, `GWSGetEventList`, `StartGWSApplication`, `CancelGWSApplication`, `RestartGWSApplication` → `ProjectId`; `CreateGWSApplicationDraft`, `UpdateGWSApplicationDraft` → `ProjectId` (also kept in the body); `DeployGWSApplicationDraft` → `ProjectId`, `Id`; `ListGWSApplication` → `PageSize`, `PageNum`, `SortField`, `SortOrder` |

Pass every field in one `--params` JSON object; the helper moves the query keys to the URL:

```bash
python3 scripts/call_extend_api.py \
  --api QueryMetrics \
  --params '{"workspace":"vmp-workspace-id","query":"up"}'

python3 scripts/call_extend_api.py \
  --api CreateGWSApplicationDraft \
  --params @request.json
```

Options: `--region` (drives the `vmp.<region>` host and the signing scope), `--host` (override endpoint), `--content-type`, `--output json|pretty`, `--show-headers`, `--profile`. STS tokens come from `VOLCENGINE_SESSION_TOKEN` or the profile; do not put them on the command line.

### Free mode (unregistered API with the same problem)

```bash
python3 scripts/call_extend_api.py \
  --api SomeAction --service <svc> --version <YYYY-MM-DD> \
  --query-keys ProjectId,Type [--body-keys-also ProjectId] \
  [--method POST] [--host <endpoint>] [--content-type application/x-www-form-urlencoded] \
  --params '{"ProjectId":"...","Type":"JOB","Other":"..."}'
```

`--query-keys` is required in free mode; without it the API has no query/body split and belongs to `ve --force` (the helper says so and exits). Without `--host` the endpoint is `VOLCENGINE_ENDPOINT` or `open.volcengineapi.com`. `--body-keys-also` names query keys that must additionally stay in the body.

### Credentials

Resolution order:

1. `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY` (+ optional `VOLCENGINE_SESSION_TOKEN`).
2. The `ve` config file (`VOLCENGINE_CLI_CONFIG_FILE`, default `~/.volcengine/config.json`): the selected profile's `access-key`/`secret-key`, or for a `console-login` profile its unexpired local `ve login` cache (`VOLCENGINE_LOGIN_CACHE_DIRECTORY` overrides the cache dir).

Profile selection follows the conversation-scoped rule in [auth.md](auth.md): pass `--profile` only when the user explicitly selected one; otherwise the config's current profile, then `VOLCENGINE_PROFILE`, is used. The helper does not refresh SSO, assume roles, or fetch ECS metadata; when nothing usable is found it says so — run `ve login`, `ve configure set`, or export the env credentials. Never print AK/SK/session tokens.
