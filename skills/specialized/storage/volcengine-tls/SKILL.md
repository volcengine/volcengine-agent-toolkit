---
name: volcengine-tls
description: >-
  Use when operating Volcengine TLS (日志服务) through volclog in agent or CI sessions and you
  need a contract-first workflow for runtime selector resolution, discover/describe/exec routing, App
  resource or Topic resolution, envelope reading, large-result delivery, and error recovery without
  guessing commands, fields, or shortcut flows. 当用户提到火山引擎日志服务 TLS、volclog、日志检索/分析/导入/导出、
  日志项目或日志主题等操作时调用。
license: Apache-2.0
metadata:
  openclaw:
    emoji: "🪵"
    homepage: "https://github.com/volcengine-tls/ve-tls-cli"
    requires:
      bins:
        - ve
    install:
      - kind: node
        package: "@volcengine/cli"
        bins: [ve]
---

# Volcengine TLS (volclog)

> Adapted from [`volclog-core`](https://github.com/volcengine-tls/ve-tls-cli/tree/b451c506f24573dc0e71220e7ad15339ed7f04e4/skills/volclog-core) in `volcengine-tls/ve-tls-cli` (Apache-2.0). Command examples keep the upstream native `volclog ...` form; run them as `ve volclog ...` (requires `ve >= 1.1.11`) with all later arguments unchanged.

## Overview

Use this skill only for agent-only incremental knowledge.

Treat this file as the dominant generic operating model for `volclog`, not as an environment-specific bootstrap note and not as an API reference. This file is the behavior summary; references are the authoritative detail. If `volclog tool describe ...` or `volclog workflow describe ...` already answers the question, stop and follow that contract instead of adding duplicate guidance here.

## Operating Stance

- Treat `tool describe` or `workflow describe` as the contract truth source. Read `tool describe` or `workflow describe` first.
- Treat profile configuration as a runtime-selector problem, not a region-discovery ritual.
- Think in runtime selectors: active profile, explicit `--profile <name>`, one-shot `--secrets-file`, `context.secrets_file`, or process-scoped environment credentials.
- Use `tool` for published public APIs, `workflow` for CLI-owned orchestration, and `raw` only when method/path is already known.
- Keep one-call App, LogApp, Trace, and TraceScore capabilities on `tool`; use `workflow app.resolve-resources` or `app.resolve-topic-ids` only for CLI-owned cross-call expansion.
- Prefer structured JSON input such as `--input '{...}'` when `tool exec` or `workflow exec` already supports it.

## Runtime Selector Model

- Treat the execution environment as unknown until the available runtime selectors are confirmed.
- Do not assume the active or default profile is the right selector for the task.
- Run `volclog configure list` only when local profile discovery is actually relevant.
- Use `region` only when the contract or task explicitly requires an override. Do not infer it from endpoint or domain.
- `--profile`/`context.profile` and `--secrets-file`/`context.secrets_file` are runtime selectors, not business input fields.
- Never read, print, export, or persist AK/SK or token values in prompts, memory, request artifacts, or skill content.

## Canonical Agent Loop

Discover -> Describe -> Exec -> Read Result

1. Resolve runtime selectors.
   - decide whether this run is using profile, secrets file, or environment credentials
   - if local profile discovery matters, run `volclog configure list`
   - keep the chosen selector explicit in the command or context
2. Discover the callable surface.
   - `volclog tool list`
   - `volclog tool list <group>`
   - `volclog workflow list <group>`
3. Read the contract.
   - `volclog tool describe <group.action>`
   - use `volclog tool describe <group.action> --view full` when authoring a nested request or when compact output omits an expected optional field
   - treat compact view as the discovery summary and full view as the request-authoring contract
   - `volclog workflow describe <group.command>`
4. Execute with structured input.
   - `volclog tool exec <group.action> --input '{...}'`
   - `volclog workflow exec <group.command> --input '{...}'`
   - `volclog raw --method <METHOD> --path <PATH> --body '{...}'`
5. Read result in this order.
   - `status` (`"success"` or `"failed"`)
   - `summary.deliveryMode`
   - the flat `error` object (when `status` is `"failed"`)
   - business fields under `data` (when `status` is `"success"`)

## Reference Escalation

- Do not read every reference file by default.
- Read `tool describe` or `workflow describe` first.
- Read [references/routing.md](references/routing.md) only when the surface is still unclear after describe or list.
- Read [references/sops.md](references/sops.md) only when the task clearly spans multiple calls and you need stop conditions.
- Read [references/best-practices.md](references/best-practices.md) only when runtime semantics, delivery mode, or recovery posture are still unclear after the contract is known.
- `contract_cache_hint` and `contract_digest` come from `tool describe` or `workflow describe` output. Read `contract_cache_hint.safe_scope` and `contract_cache_hint.refresh_when`, and reuse cached results only while the same CLI build still reports the same `contract_digest`.
- Stop after one reference resolves the current uncertainty; do not keep browsing all references “just in case”.

## Key Rules

- Do not guess command names, tool ids, workflow ids, JSON fields, or output shape.
- If the action id is still unknown, run `volclog tool list <group>` or `volclog workflow list <group>` before guessing.
- Let the operation's `risk`, `recovery`, and `usage_constraints` override the generic recovery map below.
- Treat `high-risk-retry` as a warning that retrying is high risk. After an ambiguous result, reconcile only through a get/describe/list action named by the contract; otherwise stop and escalate instead of retrying automatically.
- Do not use human shortcut commands as the primary agent flow.
- Do not repeat schema details that already exist in `tool describe` or `workflow describe`.
- Do not rebuild a valid `tool exec` or `workflow exec` request into flag-heavy shortcut form just because the shell path looks shorter.
- Do not pipe `volclog` output into `jq` or `grep` just to rediscover schema or field paths.
- Read the full JSON envelope first; use `--jmes-filter` only when you already know the envelope path you want.
- Prefer `--dry-run` before any write or destructive change, but only on `raw`, `tool exec`, or `workflow exec`.
- Treat `--dry-run` as contract or plan validation, not proof that the business query is correct.
- If fields are uniquely named, prefer flat JSON input before manual nesting.

## Error Recovery Quick Map

Use this table as the default first response after a failed envelope only after reading the operation's `risk`, `recovery`, and `usage_constraints`. The operation contract takes precedence. Read `references/best-practices.md` only when you need runtime-specific detail beyond the quick action below.

| Signal | Next action |
| --- | --- |
| `error.kind=validation` | Go back to `describe` and fix shape or selector problems first. |
| `error.kind=auth` or `401` | Re-check runtime selector, then credentials, then endpoint or region override. |
| `403 Forbidden` | Re-check tenant or profile alignment before widening the permission search. |
| `error.kind=usage` | Re-run `tool list` or `workflow list`; do not invent aliases. |
| `error.kind=unsupported_feature` | Read `error.hint`, then remove the unsupported flag or switch to the named surface; non-LogApp Topic resolution should switch to `app.resolve-resources`. |
| `error.kind=incompatible_flags` | Remove one conflicting flag and rerun. |
| `error.kind=filesystem` | Fix `--output-dir`, local path, or permissions before retrying. |
| `error.kind=decode` | Read `error.hint`, remove the wrong filter or projection if present, then rerun unfiltered or with `--trace-dir`. |
| `error.kind=server` | Read `error.code` and `error.requestId`; retry with backoff only when the operation contract permits it and the failure is clearly transient. |
| `error.kind=config` | Run `volclog doctor` for host-side configuration checks, then inspect the reported runtime issue. |
| `error.kind=unknown` | Read `error.hint` first, then `error.message` or `error.details`, and rerun with `--dry-run` or `--trace-dir` only if more detail is still needed. |
| `ResultStatus=incomplete` | Narrow the time window and rerun before trusting counts or emptiness. |

`volclog doctor` checks host/runtime configuration such as credentials, endpoint, and local setup. It does not replace `describe`, and it does not validate business query semantics.

## Large Result Handling

- Keep surface choice and delivery choice separate.
- When a result may be large, provide a writable `--output-dir`.
- Let `summary.deliveryMode` tell you what actually happened at runtime.
- Read [references/best-practices.md](references/best-practices.md) for exact `outputMode`, `deliveryMode`, file delivery, and `--jmes-filter` semantics instead of duplicating them here.

## Quick Map

| Need | Prefer |
| --- | --- |
| Public API contract already chosen | `volclog tool describe <group.action>` / `volclog tool exec <group.action>` |
| CLI workflow already chosen | `volclog workflow describe <group.command>` / `volclog workflow exec <group.command>` |
| Need to discover action or workflow ids | `volclog tool list <group>` / `volclog workflow list <group>` |
| Need help choosing the surface | read `references/routing.md` |
| Need multi-step execution order | read `references/sops.md` |
| Resolve an App resource graph | `volclog workflow describe app.resolve-resources` / `volclog workflow exec app.resolve-resources` |
| Resolve Topic IDs for a LogApp App | `volclog workflow describe app.resolve-topic-ids` / `volclog workflow exec app.resolve-topic-ids` |
| Need runtime/error/recovery semantics | read `references/best-practices.md` |
| Use an exact method/path | `volclog raw --method ... --path ...` |
| Authenticate a stateless run | host-selected local profile -> one-shot `--secrets-file` or `context.secrets_file` |
| Need contract reuse safety | reuse cached results only while the same CLI build still reports the same `contract_digest` |
