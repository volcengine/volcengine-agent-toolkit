---
name: volcengine-tls-logcollector
description: >-
  Use when designing, validating, deploying, changing, or troubleshooting Volcengine TLS LogCollector
  collection on Linux hosts or Kubernetes, including Project, Topic, host group, collector rule, index,
  binding, heartbeat, parsing, and end-to-end log ingestion checks through volclog. 当用户需要设计、部署、
  变更或排查火山引擎日志服务 LogCollector 采集（主机、Kubernetes DaemonSet/Controller、机器组、采集配置、
  心跳、解析、日志未入库）时调用。
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

# Volcengine TLS LogCollector

> Adapted from [`tls-logcollector`](https://github.com/volcengine-tls/ve-tls-cli/tree/b451c506f24573dc0e71220e7ad15339ed7f04e4/skills/tls-logcollector) in `volcengine-tls/ve-tls-cli` (Apache-2.0). Command examples keep the upstream native `volclog ...` form; run them as `ve volclog ...` (requires `ve >= 1.1.11`) with all later arguments unchanged.

## Scope

Use this skill for LogCollector collection tasks. Use `volcengine-tls` as the generic CLI operating model and this skill as the LogCollector-specific workflow.

First classify the request:

- TLS resource or collector-rule configuration
- Linux host installation or lifecycle management
- Kubernetes DaemonSet installation
- Kubernetes Controller/CRD installation or rule management
- heartbeat, binding, parsing, or ingestion troubleshooting

If the user only asks for a plan or commands, do not change remote resources. If the user asks to execute, show the resolved target and planned writes, validate them, then perform only the authorized changes.

## Required inputs

Resolve only what the selected path needs:

- runtime selector: explicit `--profile <name>`, `--secrets-file <path>`, or intentionally selected environment credentials
- `region` and TLS `endpoint`; never derive one from the other
- public or private network path
- target Project, Topic, host group, and collector rule, by ID or exact name
- input source: host file, container stdout/stderr, or container file
- for Kubernetes: cluster context, namespace, workload type/name, and container selector
- installation method and version when deployment is in scope

Do not request or echo credential values in chat. Do not put AK/SK in skill files, repositories, generated manifests, or shell history.

## Contract-first workflow

1. Run `volclog --profile <profile> doctor`; add `--online` only when a live connectivity check is needed.
2. Discover exact actions with `volclog tool list <group>`.
3. Read every selected contract with `volclog tool describe <group.action> --view full`.
4. Read [references/config-validation.md](references/config-validation.md) and validate representative samples before persisting a non-trivial parser, path extraction, timestamp, index delimiter, or processor configuration.
5. Read [references/tls-resources.md](references/tls-resources.md) when Project, Topic, host group, collector rule, index, or binding changes are needed.
6. Run write operations with `--dry-run` first. Dry-run validates local request shape; it does not prove that the service will accept the request or that parsing semantics are correct.
7. Execute the authorized write once. After an ambiguous write result, reconcile with a read action instead of retrying blindly.
8. Follow the environment-specific deployment reference when installation is in scope:
   - [references/linux-host.md](references/linux-host.md)
   - [references/kubernetes-daemonset.md](references/kubernetes-daemonset.md)
   - [references/kubernetes-controller.md](references/kubernetes-controller.md)
9. Read [references/verification.md](references/verification.md) and verify process or workload health, machine heartbeat, rule binding, and Topic ingestion.

## Collection design rules

- Treat current `tool describe` output as authoritative for action IDs, fields, enum values, and required properties. Examples in references are starting points, not frozen API contracts.
- Use host-file input only for host paths, container-stdout input only for stdout/stderr, and container-file input only for files inside containers. Do not mix incompatible `Paths` and `ContainerRule` shapes.
- Select the narrowest stable path and Kubernetes filters. Never create an empty container filter that can collect the entire cluster by accident.
- Use a Label host group unless the user or an existing deployment explicitly requires IP matching. The installed `label` and the host group's `HostIdentifier` must agree. Never configure both label and IP identity on the same agent.
- Reuse existing resources only after exact-name or exact-ID reconciliation. If multiple candidates match, stop and ask the user to select one.
- Do not invent production values for shard count, retention, index settings, resource names, paths, regexes, time zones, or parsing keys.
- Do not automatically collect LogCollector's own logs. A self-log POC is allowed only when the user explicitly requests a temporary end-to-end test and accepts the feedback-loop risk; define teardown and observe two short windows.
- Installation success is not collection success. A healthy process or Pod, machine heartbeat, rule binding, and real Topic ingestion are separate acceptance gates.

## Stop conditions

Stop and report the exact stage when:

- runtime selector, region, endpoint, target account, cluster, or resource identity is ambiguous
- a write returns an ambiguous transport result and read-after-write cannot reconcile it
- generated or supplied parsing configuration fails representative sample validation
- installation would overwrite or delete an existing service, DaemonSet, release, CRD, ClusterRole, binding, or collector rule outside the confirmed target
- a POC self-log rule shows accelerating ingestion or resource usage

## Output contract

Report:

- selected runtime, target environment, and resource IDs or exact names
- collection source and parser strategy
- validation actions run and their results
- planned and completed writes, separating dry-run from live execution
- deployment commands and where each command runs
- verification evidence for process or Pod health, heartbeat, binding, and Topic ingestion
- cleanup steps for any temporary POC resources

