# Best Practices

Use this file only for runtime semantics, recovery posture, and credential handling. Routing belongs in `routing.md`; multi-step execution order belongs in `sops.md`.

Do not use this file to reopen surface selection once routing is already clear.
This file refines the quick recovery map in `SKILL.md`; it does not override the main skill's default first response.

## Contents

- [Runtime Signals](#runtime-signals)
- [Contract View And Recovery Precedence](#contract-view-and-recovery-precedence)
- [Dry-Run Scope](#dry-run-scope)
- [Envelope Filtering](#envelope-filtering)
- [Search, Histogram, And Analysis](#search-histogram-and-analysis)
- [Error Object](#error-object)
- [Profile And Credential Selection](#profile-and-credential-selection)
- [Doctor Boundary](#doctor-boundary)
- [Thin Client Boundary](#thin-client-boundary)
- [Recovery Signals](#recovery-signals)
- [Known Traps](#known-traps)

## Runtime Signals

Read these signals in this order after routing is already clear:

1. keep the chosen `tool / workflow / raw` surface fixed
2. let CLI decide how the result is delivered
3. inspect the flat `error` object only if the call failed

Key rules:

- Keep surface choice and delivery choice separate. Skill decides `tool / workflow / raw`; CLI decides stdout vs file delivery.
- Do not let shortcut-oriented help or examples change the runtime reading order described here.
- Let CLI `deliveryMode` decide stdout vs `file_auto`.
- For `log.search`, let CLI `deliveryMode` decide stdout vs `file_auto` after the surface is already chosen.
- Treat `outputMode` as caller intent and `deliveryMode` as runtime result:
  - explicit file request -> `deliveryMode=file_forced`
  - auto spill because the envelope is too large -> `deliveryMode=file_auto`
  - normal stdout -> `deliveryMode=stdout`
- For large responses, prefer `--output-mode file --output-dir <writable-dir>`.
- If auto spill fails because no writable directory was provided, rerun with `--output-dir <writable-dir>` instead of inventing a filename.
- `tool / workflow / raw` write a full JSON envelope when file delivery is used, even if stdout format preference was `jsonl`.
- `log.export` and `log.export-analysis` are the exception: their files contain exported data rows, while stdout keeps the envelope and points to the file through `artifacts`.

## Contract View And Recovery Precedence

- Use compact `tool describe` output for discovery and ordinary flat requests.
- Run `volclog tool describe <group.action> --view full` before authoring nested objects or whenever an expected optional field is absent from compact output.
- Treat full view as the request-authoring schema; do not infer omitted optional fields from compact view.
- Read `risk`, `recovery`, and `usage_constraints` before executing or recovering a mutating operation. These operation-specific fields override the generic recovery tables in this skill.
- Interpret `high-risk-retry` as “retrying is high risk,” not as permission to retry automatically.
- After an ambiguous high-risk result, use a get/describe/list reconciliation action only when the contract names one. If it does not, stop and escalate with the request ID and business error evidence.

## Dry-Run Scope

- `--dry-run` applies to `raw`, `tool exec`, and `workflow exec`. It does not apply to `tool describe`, `workflow describe`, or shortcut groups.
- For `tool exec` and `workflow exec`, `--dry-run` validates contract shape and execution plan without sending the real mutating call.
- For `raw`, `--dry-run` only validates the transport/local plan. It does not validate API-required fields the way `tool exec` or `workflow exec` can.
- Treat any dry-run success as transport or contract confidence only. It is not proof that the business query or time window is semantically correct.

## Envelope Filtering

- `--jmes-filter` runs on the complete CLI envelope.
- `--jmes-filter` is stdout-only; do not combine it with file delivery.
- `execution.projection` is different: it runs on the raw result before envelope wrapping.
- Use `--jmes-filter` for envelope fields such as `data`, `summary`, or `error`.
- Use `execution.projection` only for raw service-result fields.
- If `--jmes-filter` targets an existing envelope field whose value is `null`, stdout returns literal `null` and the command still succeeds.
- `filter matched no value` means the path was wrong, not that a null field was returned.
- `filter matched no value` and `invalid --jmes-filter` are `decode` failures and return exit 3.
- If the original envelope already failed, keep the original non-zero exit and `error.kind`; a filter miss only adds a warning instead of replacing the failure.

## Search, Histogram, And Analysis

Use this section to interpret result semantics after the surface has already been chosen.

- `log.search` itself supports plain search and SQL/analysis queries in `Query`.
- Use `log.search` for interactive analysis, small previews, and quick iteration.
- `log.describe-histogram-v1` is for time-distribution preview and total-hit estimation only for pure search queries.
- `log.export-analysis` uses the same SearchLogs SQL/analysis `Query` syntax as `log.search`; it does not add a new server-side analysis API or another pagination model.
- Choose `log.export-analysis` when the user needs the full analysis row set written as an export file for offline reading, downstream processing, or token-safe handoff.
- Stay on `log.search` when the user is still validating SQL, iterating on the query, or only needs a small interactive preview.
- `raw --input` is only a compatibility alias for `--body`; it does not do `tool exec` style smart mapping for GET requests.
- `HitCount` is only the count returned in the current `SearchLogs` response window.
- `Histogram.TotalCount` is the better whole-window total only for pure search when histogram is the correct surface.
- `ResultStatus=incomplete` means the service returned only a partial scan. This can happen for SearchLogs in both search and analysis mode, so narrow the time range and rerun before trusting counts, rows, empty results, or bucket distribution.
- For search+analysis or pure analysis queries, do not use histogram as the analysis row count. Use SQL such as `select count(*)` when the user asks for analysis totals.

## Error Object

Failed envelopes use one flat `error` object.

Read it in this order:

1. `error.source`
2. `error.kind`
3. `error.hint`
4. `error.code`
5. `error.statusCode`
6. `error.message`
7. `error.details`
8. `error.requestId`

Interpretation rules:

- For upstream service failures, `error.code` is already the business error code such as `ProjectAlreadyExist`.
- If the service embeds extra JSON details, the CLI lifts them into `error.details`; do not parse `error.message` again unless `details` is absent.
- Use `error.kind` to choose the smallest recovery action:
  - `validation`: fix input or selector shape first
  - `unsupported_feature`: remove the unsupported capability, or switch surface
  - `incompatible_flags`: remove one of the conflicting flags and rerun
  - `filesystem`: fix `--output-dir`, path, or local permissions before retrying

## Profile And Credential Selection

Credential selection is a host/runtime concern, not a business-input concern.

- Discover saved profiles with `volclog configure list`.
- Omit `profile` to use the active CLI profile.
- Set `context.profile` only when switching tenant or environment inside one session.
- For stateless service assistants and CI, keep long-lived credentials on the host. Let the host choose the local profile, then inject one-shot credentials with `--secrets-file` or `context.secrets_file`.

Preferred order:

1. non-secret selector such as profile or environment label
2. `--secrets-file`
3. `context.secrets_file`
4. process-scoped `VOLCENGINE_ACCESS_KEY_ID` / `VOLCENGINE_ACCESS_KEY_SECRET` only as fallback

Hard rule:

- Environment credentials override profile resolution. If a stateless run must target a specific local profile, use host-generated secrets files instead of sandbox-wide env injection.
- `--profile`/`context.profile` and `--secrets-file`/`context.secrets_file` are mutually exclusive runtime selectors; conflicting selectors fail fast instead of silently overriding each other.

## Doctor Boundary

- `volclog doctor` is for host/runtime diagnosis: credentials, config, selector visibility, endpoint reachability, and similar local setup issues.
- Use `volclog doctor` for `error.kind=config`, and for stubborn `401`/credential problems after selector and endpoint checks.
- Do not use `volclog doctor` as a replacement for `tool describe` or `workflow describe`.
- Do not expect `volclog doctor` to prove that a business query, time window, or SQL expression is semantically correct.

## Thin Client Boundary

The CLI validates contract shape and runtime preconditions. It does not validate business semantics for you.

What the CLI does validate:

- required fields and JSON shape
- conflicting runtime selectors or output flags
- local output path / writable directory constraints

What the CLI does not try to judge:

- whether a timestamp is business-valid
- whether a query is semantically reasonable
- whether an empty result is surprising for the workload

If the command reached the service without a local validation/decode/filesystem error, debug the business query and time window before assuming the CLI blocked something.

## Recovery Signals

When the command already failed, follow the smallest next action:

| Signal | Smallest next action |
| --- | --- |
| `unknown tool` | Re-run `tool list` or `workflow list` for the group before guessing aliases or fallback names. |
| `missing --input` | Re-read `input_schema` and `input_encoding_hint`, then resend inline JSON, stdin, or file input using the documented shape. |
| `filter matched no value` | Inspect one unfiltered response first, then correct the `--jmes-filter` or `execution.projection` path. |
| `jmes filter returned literal null` | Treat literal `null` as a successful projection result; only debug further if the command returned a real filter error instead. |
| `401 Unauthorized` | Run `volclog doctor`, then inspect credentials, region, and endpoint. |
| `403 Forbidden` | Check tenant/profile alignment first, then verify resource permissions before retrying. |
| `error.kind=server` or `5xx` | Read `error.code`, `error.requestId`, and `error.statusCode` first. Retry with backoff only when the operation contract permits it and the failure is clearly transient; otherwise reconcile or escalate with those identifiers. |
| `IndexNotExists` | Inspect or create the index, then wait for readiness before retrying search. |
| `TopicAlreadyExist` | Re-list topics in the target project, then switch to get or modify instead of repeating create. |
| `ProjectAlreadyExist` | Re-list projects, then switch to get or modify instead of repeating create. |
| `ResultStatus=incomplete` | Narrow the time range and rerun before trusting counts, rows, or empty results. |
| `search returned empty after write` | Confirm selector, topic, time range, and index readiness before widening the query. |
| `huge stdout payload` | Rerun with `--output-mode file --output-dir <writable-dir>`, or reduce stdout with `--jmes-filter` or `execution.projection`. |
| `unsupported_feature` | Remove the unsupported capability such as `page.all`, or switch to a surface whose contract explicitly supports it. |
| `filesystem` | Supply a writable `--output-dir`, or fix the local path and permissions before retrying. |

## Known Traps

- `page-all-is-not-compression`: `page.all` increases completeness and payload size; combine it with file delivery instead of expecting smaller stdout.
- `jmes-filter-and-projection-have-different-scope`: use `summary.*` or `data.*` under `--jmes-filter`, and raw keys only under `execution.projection`.
- `jmes-filter-null-is-still-success`: literal `null` means the selected field exists and is null; that is not the same as `filter matched no value`.
- `jmes-filter-does-not-mix-with-file-delivery`: `--jmes-filter` is stdout-only; remove it if the goal is file delivery.
- `deliverymode-belongs-to-runtime`: choose `tool / workflow / raw` first, then read `summary.deliveryMode` from the actual result.
- `hitcount-is-not-whole-window-total`: `HitCount` is only the current response window, not the whole-window total.
- `incomplete-means-partial-scan`: treat `ResultStatus=incomplete` as partial evidence and rerun on a narrower time range.
- `workflow-ids-are-not-tool-ids`: `log.ingest`, `log.export`, and `log.export-analysis` belong to `workflow`, not `tool`.
- `ingest-is-not-tool-put`: use `workflow log.ingest` for local file or stdin import, and `tool log.put` only for the public PutLogs contract.
- `shortcuts-are-human-first`: human shortcut groups are for humans; agent flows should stay on `tool / workflow / raw`.
- `thin-client-does-not-judge-business-semantics`: if there was no local validation, decode, or filesystem error, debug the query semantics and time window before blaming the CLI.
- `env-creds-override-profile`: process-wide environment credentials override local profile resolution.
- `profile-and-secrets-file-are-exclusive`: choose exactly one runtime selector family, not both `profile` and `secrets_file`.
- `high-risk-retry-is-not-auto-retry`: ambiguous high-risk outcomes require contract-named reconciliation or escalation, never an automatic replay.
- `compact-describe-can-omit-optional-fields`: use `tool describe --view full` before authoring nested optional configuration.
- `topic-resolution-is-logapp-only`: if `app.resolve-topic-ids` reports `unsupported_feature`, follow its hint and use `app.resolve-resources`; do not guess Topic IDs for opaque resources.
