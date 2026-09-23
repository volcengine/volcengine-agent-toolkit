# Routing

Use this file only to choose the execution surface. Do not use it for runtime/output decisions.

Stop once one row clearly matches the current intent. After the surface is chosen, return to the main contract flow and do not keep comparing other surfaces.

| Intent | Prefer | First Command | Escalate When |
| --- | --- | --- | --- |
| Import local lines/jsonl/json-array from file or stdin | `workflow log.ingest` | `volclog workflow describe log.ingest` | You actually need the raw public `PutLogs` contract |
| Preview rows or do interactive analysis | `tool log.search` | `volclog tool describe log.search` | You need the full analysis row set or explicit export |
| Preview pure-search time buckets | `tool log.describe-histogram-v1` | `volclog tool describe log.describe-histogram-v1` | You already know the final row query and do not need bucket preview |
| Export many raw search rows | `workflow log.export` | `volclog workflow describe log.export` | You only need a small preview, not export |
| Export full SQL/analysis rows | `workflow log.export-analysis` | `volclog workflow describe log.export-analysis` | You only need interactive analysis or a small preview |
| Call one App, template, LogApp, Trace, span-search, or TraceScore API | `tool` | `volclog tool list app`, `log-app`, or `trace` | The intent is to expand relationships across multiple APIs |
| Resolve an App into a normalized resource graph | `workflow app.resolve-resources` | `volclog workflow describe app.resolve-resources` | You only need one atomic Describe API response |
| Resolve Topic IDs owned by a LogApp App | `workflow app.resolve-topic-ids` | `volclog workflow describe app.resolve-topic-ids` | AppType is not `LogApp`; use `app.resolve-resources` instead |
| Exact method/path is already known | `raw` | `volclog raw --method <METHOD> --path <PATH>` | A public `tool` or `workflow` contract exists |

## Decision Rules

- Start with `tool` for published public APIs.
- Use `workflow` only when the intent is clearly local import/export or another CLI-owned orchestration.
- Do not route ordinary App/LogApp/Trace reads or mutations through an App workflow. The App workflows exist only to expand `DescribeApp -> DescribeLogApp -> DescribeTraceInstance` relationships.
- Choose `app.resolve-resources` for a reusable graph or for non-LogApp applications. Choose `app.resolve-topic-ids` only when the required output is the deduplicated Topic ID list and `AppType=LogApp`.
- `log.export-analysis` is not a different analysis API. Choose it only when the same SearchLogs analysis query now needs a file-oriented full-row export instead of interactive preview.
- For `log.ingest` vs `tool log.put`:
  - local file/stdin import where CLI should normalize lines/jsonl/json-array -> `log.ingest`
  - explicit public `PutLogs` contract work or direct API control -> `tool log.put`
- Human shortcut groups are for humans. Do not route an agent there unless the user explicitly asks for shortcut behavior.

## Rediscovery

- For non-`log` groups and plain CRUD intent, default to `volclog tool list <group> --verb <verb>` before browsing anything else.
- If `unknown tool` happens, rerun `volclog tool list <group>` before guessing aliases.
- If the intent already implies a verb, re-run `volclog tool list <group> --verb <user-intent-verb>`.
- Example: create project -> `volclog tool list project --verb create`
- Example: list alarms -> `volclog tool list alarm --verb list`
- If `tool list` still does not fit and the intent is ingest/export, switch to `volclog workflow list <group>`.
