# Locate APIs and retrieve parameters

## Locate the API (find the service name + Action name)

```text
Step 1: Service name + Action known? -> Use them directly; skip to "Retrieve parameters"
Step 2: Service name known, Action unknown?
  -> ve <service> 2>&1 | grep -i <keyword>
Step 3: Service name also unknown?
  -> ve 2>&1 | grep -i <service keyword>
Step 4: None of the above work?
  -> python3 scripts/find_api.py <keyword>   (returns Service, Action, Version)
Step 5: Still missing (or unknown service/action)?
  -> Check references/extend-apis.md (covers APIs absent from both ve metadata and find_api.py, such as account_verify GetVerifyInfo for real-name verification)
```

## Retrieve parameters (once the Action is known)

`--help` is concise (names, types, Required/Optional). `--help --detail` adds the full description, enum values, constraints and examples for every parameter — it is the CLI's own copy of the API documentation, so no external fetch is needed.

| Situation | Command |
|---|---|
| **Read-only** (Describe/List/Get) | `ve <svc> <Action> --help` — names alone are usually enough |
| **Write/destructive** (Create/Run/Delete…) | `ve <svc> <Action> --help --detail` — required fields, nested structures, examples |
| **Still unclear after `--help`** | `--help --detail`; add `--lang ZH` for the Chinese text |
| **Errors like `Invalid*` / `Missing*`** | Recheck names, required fields and ranges with `--help --detail` |

```text
ve ecs DescribeInstances --help
ve ecs RunInstances --help --detail
ve ecs RunInstances -h --detail --lang ZH
```

The `Parameter Form` / `--body` sections of the same output tell you whether the action takes flat parameters or a JSON body ([execute-api.md](execute-api.md)).

For API questions that go beyond one action's parameters (comparisons, error-code semantics, pagination behaviour, whether a batch variant exists), load the `volcengine-api` skill, which queries the API Explorer directly.

## ve command name and API version relationship

- Default version -> ve command = base service name (e.g., `iam`)
- Non-default version -> ve command = `service name + version without hyphens` (e.g., `iam` v2021-08-01 -> `iam20210801`)
- When in doubt: `ve 2>&1 | grep <service>` to confirm

## Calling an API the CLI metadata does not list: `--force`

When `ve` answers `unknown service "<svc>"` or `unknown action`, but the API exists (the user provided it, `find_api.py` found its Service/Action/Version, or the docs describe it), call it with `--force`. `--force` skips the local metadata check, so **you** must supply what the metadata would have: the version, and — for a service the CLI does not know — the endpoint.

```bash
ve newservice DescribeNewResource \
  --version 2024-01-01 \
  --endpoint open.volcengineapi.com \
  --SomeParam value \
  --force
```

- `--version` is mandatory (`--version is required when using --force`); `--endpoint` is mandatory for an unknown service unless the profile or `VOLCENGINE_ENDPOINT` already sets one.
- `--method POST` for POST APIs (default GET); `--body '{...}'` for a JSON body (cannot be mixed with `--Param` values); `--region` when the service signs in a fixed region.
- `--force` is a presence flag: `--force`, not `--force true`.
- Parameters are unvalidated: take them from the user's material, the `volcengine-api` skill, or [references/extend-apis.md](extend-apis.md) — never guess them. `find_api.py` only locates Service/Action/Version; it does not return parameters, method, or endpoint.
- [safety.md](safety.md) applies exactly as for a listed action; a local safety policy checks `--force` calls too.
- Do not use `--force` for TLS (日志服务); `ve` has no `tls` OpenAPI command, so route TLS tasks to `ve volclog` through the Product CLI routing table instead.

[references/extend-apis.md](extend-apis.md) carries the service-code / version / endpoint / signing-region recipes for the extension services (`account_verify` real-name verification, CDN, CodePipeline, DCDN, `domain_openapi`, Flink, GA, IoT, Live, MCDN, Metrics, `sec_agent`, `trademark`, VEEN, VKE, VMP).

## Extension helper (query + body in one request only)

`ve --force` cannot send URL query parameters *and* a request body in one POST. A handful of APIs (VMP Prometheus queries, Flink GWS) need exactly that; use the helper for those and nothing else:

```bash
python3 scripts/call_extend_api.py --list
python3 scripts/call_extend_api.py --api QueryMetrics --params '{"workspace":"<id>","query":"up"}'
```

After upgrading `ve`, run `python3 scripts/audit_extend_apis.py` — it lists which recipes/helper entries the new metadata now covers natively, so they can be dropped.

It also has a free mode (`--service/--version/--query-keys`) for unregistered APIs with the same shape. Credentials, options and the registered list are in [extend-api-helper.md](extend-api-helper.md). Do not pass `--profile` unless the user has explicitly selected one for this conversation.

Extension helpers retain the built-in confirmation rules ([safety.md](safety.md)). They are outside this native-CLI safety-policy integration.
