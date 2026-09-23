# Observability Service Notes

## TLS Uses ve volclog

`ve` has no native `tls` OpenAPI command. TLS (日志服务) runs through the delegated `volclog` CLI as `ve volclog ...`, which requires the `ve` version stated in the SKILL.md Product CLI routing section.

For TLS tasks such as log search, analysis, ingest, export, Project/Topic management, or LogCollector collection, use `volcengine-find-skills` to find `volcengine-tls` (or `volcengine-tls-logcollector` for collection setup and troubleshooting), install it if missing, and follow its `volclog` workflow with the `ve volclog` prefix.

If `ve volclog` reports an unknown service or suggests `--force`, the `ve` build predates the `volclog` proxy. Upgrade `ve`; do not call TLS through `--force`.

## CloudMonitor Read Path Works

`ve cloudmonitor ListRules` returned an empty `Data` array in `cn-beijing`. No CloudMonitor rule lifecycle test was run.
