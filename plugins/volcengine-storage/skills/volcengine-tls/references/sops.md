# SOPs

Use this file only for cross-group execution order, stop conditions, and hand-off points between surfaces.

Pick one SOP, follow it until its stop condition, then stop. Do not chain multiple SOPs unless the current one fails to resolve the task.
If any step returns an error envelope, first follow `SKILL.md` Error Recovery Quick Map, then retry the same step or stop if the task itself changed.

## Create A Searchable Log Pipeline

1. `project.create`
2. `topic.create`
3. `index.create`
4. `log.search`

Stop when:
- one read path returns the expected searchable shape, or
- `project` / `topic` / `index` already exists and the pipeline can move to validation

Notes:
- After `index.create`, wait for index readiness before trusting search results.
- Prefer `index.describe` and read `Status` or equivalent readiness fields when available.
- If readiness is not explicit, poll `index.describe` with a reasonable timeout and retry one narrow validation query only after the index looks ready.

## Ingest And Validate

1. `workflow log.ingest`
2. `log.search`

Stop when:
- the write path succeeds, and
- one narrow validation query returns rows

Notes:
- Keep validation queries small and recent.
- If the write succeeded but search is empty, switch to the troubleshooting SOP below instead of widening the query immediately.

## Troubleshoot Empty Search

1. runtime selector check
2. `topic.describe-topic`
3. `index.describe`
4. `log.search`

Stop when:
- the wrong profile, topic, or time range is identified, or
- search starts returning rows

Notes:
- Reconfirm the runtime selector before changing business input. If local profiles matter, run `configure.list`; otherwise verify the injected selector that the session is already using.
- If index readiness is unclear, check `Status` first, then retry with a narrow window.

## Preview Search Volume Before Reading Rows

1. `tool describe log.describe-histogram-v1`
2. `tool exec log.describe-histogram-v1`
3. `tool describe log.search`
4. `tool exec log.search`

Stop when:
- the next execution surface is clear, and
- you know whether to stay interactive or switch to export

Notes:
- Use this only for pure search queries.
- `Histogram.TotalCount` is the whole-window estimate for pure search.
- `HitCount` is only the count in the current `SearchLogs` response.

## Interactive SQL Exploration

1. `tool describe log.search`
2. `tool exec log.search`
3. If the row set grows beyond comfortable stdout, switch to `workflow log.export-analysis`

Stop when:
- the user has the answer from preview rows, or
- the task clearly needs a full analysis row set

Notes:
- `log.search` supports interactive SQL exploration directly in `Query`.
- Switch only when the preview no longer answers the user question.

## Export Large Result Sets

1. `workflow log.export`
2. `workflow log.export-analysis`

Stop when:
- stdout or the written output confirms the expected envelope shape, and
- the file contains the full output needed by the user

Notes:
- Read the stdout notice or written envelope and stop once the expected output shape is confirmed.

## Resolve Application Resources

1. `workflow describe app.resolve-resources`
2. `workflow exec app.resolve-resources --input '{"AppId":"..."}'`

Stop when:
- `data.Nodes` and `data.Edges` expose the resource relationships needed by the caller, or
- the workflow rejects cross-Region expansion or a malformed downstream resource

Notes:
- For `AppType=LogApp`, the workflow expands LogApp resources and Trace instances; for other App types it preserves opaque `AppResource` nodes instead of guessing their semantics.
- The workflow includes both `TraceTopicId` and `DependencyTopicId`, preserves first-seen order, deduplicates IDs, and returns no partial graph after a failed dependent call.

## Resolve LogApp Topic IDs

1. `workflow describe app.resolve-topic-ids`
2. `workflow exec app.resolve-topic-ids --input '{"AppId":"..."}'`

Stop when:
- `data.TopicIds` returns the deduplicated Topic ID list, or
- `error.kind=unsupported_feature` reports that the App is not a LogApp

Notes:
- On a non-LogApp result, follow `error.hint` and switch to `app.resolve-resources`; do not infer Topic IDs from opaque resources.
- Do not manually add `NeedLogAppTopics=true`; the workflow traverses `RelatedResourceList` so Trace dependency topics are retained.
