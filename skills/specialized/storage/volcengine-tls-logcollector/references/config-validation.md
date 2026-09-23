# Validate LogCollector configuration

Use this reference when a collection rule contains parsing, multiline, path extraction, timestamp, delimiter, index-tokenization, or processor logic. These helpers call TLS validation backends but do not persist collector or processor state.

## Before validating

1. Collect representative positive samples, boundary cases, and at least one sample that must not match.
2. Run `volclog tool list collector`, `volclog tool list log`, or `volclog tool list processor` to confirm the current action IDs.
3. Run `volclog tool describe <action> --view full` immediately before authoring input. Respect case exactly; some wire fields intentionally use lower camel case.
4. Keep samples free of credentials, tokens, personal data, and other secrets.

Dry-run only validates the local request contract. The actions below perform semantic validation and therefore require a live TLS request.

## Helper map

| Configuration question | Action | Important result rule |
| --- | --- | --- |
| Does a begin regex or full-log regex match and extract the sample? | `collector.extract` | Both `BeginRegex` and `LogRegex` keys are required; at least one value must be non-empty. |
| Can TLS propose a multiline begin regex? | `collector.generate-begin-regex` | Treat the generated regex as a candidate and validate it on multiple samples. |
| Can TLS generate extraction regex from selected offsets? | `collector.generate-log-regex` | `Start` and `End` are paired comma-separated offsets selecting `[start,end)` ranges. |
| Does delimiter parsing preserve quoted content? | `collector.split` | If `Quote` is present, it must be non-empty and must not occur in `Delimiter`. |
| Does a path regex extract the intended values? | `collector.parse-path` | `PathSample` must be an absolute path without `*`, `?`, or `**`. |
| Does a timestamp format/timezone parse correctly? | `collector.parse-time` | `EnableNanosecond=false` returns milliseconds; `true` returns nanoseconds. |
| How will a full-text delimiter tokenize a real log? | `log.preview` | Fields are `topicId`, `delimiter`, and `log`, with exact lower-camel spelling. |
| Does a processor DSL/SPL compile and transform a sample? | `processor.exec-processor` | Inspect `ExecStatus` even after HTTP 200; a failed execution reports its error there. |

## Regex and multiline validation

Generate only when it helps; validate before saving:

```bash
volclog --profile <profile> tool describe collector.generate-begin-regex --view full
volclog --profile <profile> tool exec collector.generate-begin-regex \
  --input '{"LogSample":"<single representative first line>"}'

volclog --profile <profile> tool describe collector.extract --view full
volclog --profile <profile> tool exec collector.extract \
  --input '{"BeginRegex":"<begin-regex-or-empty>","LogRegex":"<log-regex-or-empty>","LogSample":"<representative-log-sample>"}'
```

For `collector.generate-log-regex`, derive offsets from the exact sample bytes expected by the current contract. Do not guess offsets after visually counting multibyte characters.

Reject a candidate that merges unrelated records, drops required fields, or accepts the negative samples.

## Delimiter validation

```bash
volclog --profile <profile> tool describe collector.split --view full
volclog --profile <profile> tool exec collector.split \
  --input '{"Delimiter":",","Quote":"\"","LogSample":"2026-09-02,info,\"value,with,commas\""}'
```

Compare the returned field count and boundaries with the intended `ExtractRule.Keys`. Test missing fields, extra delimiters, empty quoted fields, and escaped quotes when they can occur.

## Path and timestamp validation

```bash
volclog --profile <profile> tool describe collector.parse-path --view full
volclog --profile <profile> tool exec collector.parse-path \
  --input '{"PathSample":"/var/log/app/prod/service.log","Regex":"^/var/log/app/([^/]+)/([^/]+)\\.log$"}'

volclog --profile <profile> tool describe collector.parse-time --view full
volclog --profile <profile> tool exec collector.parse-time \
  --input '{"TimeFormat":"%Y-%m-%dT%H:%M:%S%z","TimeSample":"2026-09-02T20:00:00+0800","TimeZone":"Local","EnableNanosecond":false}'
```

Confirm path capture order matches the configured path keys. For timestamps, compare the returned instant with an independently known time and explicitly decide whether the source timestamp contains a zone or relies on `TimeZone`.

## Index delimiter preview

This validates tokenization against a real Topic and does not persist an index:

```bash
volclog --profile <profile> tool describe log.preview --view full
volclog --profile <profile> tool exec log.preview \
  --input '{"topicId":"<topic-id>","delimiter":",;=|/","log":"<representative-log>"}'
```

Do not copy delimiter examples into production without checking the actual query and tokenization requirements.

## Processor validation

```bash
volclog --profile <profile> tool describe processor.exec-processor --view full
volclog --profile <profile> tool exec processor.exec-processor \
  --input '{"DSLContent":"<dsl-or-spl>","ExecAction":"debug","LogSample":{"message":"<sample>"},"ProcessorDSLType":"dsl","ProcessorType":"ingester"}'
```

The current backend accepts `ExecAction=debug`; `ProcessorDSLType` is `dsl` or `spl`, and `ProcessorType` is `ingester` or `consumer`. Re-read the contract before use because these are server-controlled enums.

## Acceptance gate

Before creating or modifying a collector rule:

- every representative positive sample parses as intended
- negative samples do not silently match as valid records
- extracted keys, field order, path captures, and timestamp units are correct
- index tokenization supports the intended search behavior
- processor output has `ExecStatus` success and the expected transformed object
- the final `collector.create` or `collector.modify-rule` request passes `--dry-run`

