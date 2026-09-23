# Configure TLS resources with volclog

Use this reference to reconcile or create the Project, Topic, host group, collector rule, index, and binding required by LogCollector.

## Safety model

- Query before every create. Exact-name lookup is reconciliation evidence, not just convenience.
- Never auto-select among multiple matches. Show the IDs and ask the user to resolve ambiguity.
- Do not auto-generate production resource names. For an explicitly requested POC, propose one base name such as `poc-test-YYYYMMDDHHMMSS`, show the mapping, and use it only after the user accepts it.
- Do not invent `ShardCount`, `Ttl`, billing mode, index behavior, paths, parsing rules, or Kubernetes filters. Example values are not production defaults.
- Run each write with `--dry-run`, then execute it once. Dry-run does not reserve a name or prove service-side acceptance.
- After an ambiguous create response, query by the exact name before deciding whether another write is safe.

## Contract discovery

Run only for resources in scope:

```bash
volclog --profile <profile> tool describe project.describe-projects --view full
volclog --profile <profile> tool describe project.create --view full
volclog --profile <profile> tool describe topic.describe-topics --view full
volclog --profile <profile> tool describe topic.create --view full
volclog --profile <profile> tool describe host-group.describe-host-groups-v2 --view full
volclog --profile <profile> tool describe host-group.create --view full
volclog --profile <profile> tool describe collector.describe-rules --view full
volclog --profile <profile> tool describe collector.create --view full
volclog --profile <profile> tool describe collector.apply-rule-to-host-groups --view full
volclog --profile <profile> tool describe index.describe --view full
volclog --profile <profile> tool describe index.create --view full
```

## Reconciliation order

1. Resolve or create the Project; record `ProjectId`.
2. Resolve or create the Topic inside that Project; record `TopicId`.
3. Resolve or create the host group; record `HostGroupId` and its identity rule.
4. Validate samples and parser settings using [config-validation.md](config-validation.md).
5. Resolve or create the collector rule; record `RuleId`.
6. Resolve current bindings, then add only the missing rule-to-host-group binding.
7. Inspect the Topic index; create it only when absent, otherwise modify deliberately while preserving existing field indexes.

## Project and Topic

Use exact-name filters and inspect the complete envelope:

```bash
volclog --profile <profile> tool exec project.describe-projects \
  --input '{"ProjectName":"<project-name>","IsFullName":true,"PageNumber":1,"PageSize":100}'

volclog --profile <profile> --dry-run tool exec project.create \
  --input '{"ProjectName":"<project-name>","Region":"<region>"}'

volclog --profile <profile> tool exec topic.describe-topics \
  --input '{"ProjectId":"<project-id>","TopicName":"<topic-name>","IsFullName":true,"PageNumber":1,"PageSize":100}'

volclog --profile <profile> --dry-run tool exec topic.create \
  --input '{"ProjectId":"<project-id>","TopicName":"<topic-name>","ShardCount":<confirmed-count>,"Ttl":<confirmed-days>}'
```

Remove `--dry-run` only after reviewing the planned request and confirming the lookup was empty. Record returned IDs immediately.

## Host group

Use a Label host group unless the user or existing deployment explicitly requires IP matching:

```bash
volclog --profile <profile> tool exec host-group.describe-host-groups-v2 \
  --input '{"HostGroupName":"<host-group-name>","PageNumber":1,"PageSize":100}'

volclog --profile <profile> --dry-run tool exec host-group.create \
  --input '{"HostGroupName":"<host-group-name>","HostGroupType":"Label","HostIdentifier":"<host-identifier>","ServiceLogging":true}'
```

The installed LogCollector label must exactly match `HostIdentifier`. For an explicitly requested IP group, re-read `host-group.create`, use its current `HostGroupType` and `HostIpList` contract, and configure installation with IP identity only. Do not combine label and IP identity.

## Collector rule

Choose the request shape from the actual input source:

- host file: `InputType=0` plus host `Paths`
- container stdout/stderr: `InputType=1`, `ContainerRule.Stream`, and precise container/Kubernetes filters; no `Paths`
- container file: `InputType=2`, container file `Paths`, and precise container/Kubernetes filters

Query by exact rule identity within the known Project or Topic before creation:

```bash
volclog --profile <profile> tool exec collector.describe-rules \
  --input '{"TopicId":"<topic-id>","RuleName":"<rule-name>","PageNumber":1,"PageSize":100}'
```

Host-file skeleton:

```bash
volclog --profile <profile> --dry-run tool exec collector.create \
  --input '{"RuleName":"<rule-name>","TopicId":"<topic-id>","InputType":0,"LogType":"minimalist_log","Paths":["<absolute-path-pattern>"]}'
```

Container-stdout skeleton:

```bash
volclog --profile <profile> --dry-run tool exec collector.create \
  --input '{"RuleName":"<rule-name>","TopicId":"<topic-id>","InputType":1,"LogType":"minimalist_log","ContainerRule":{"Stream":"stdout","KubernetesRule":{"NamespaceNameRegex":"^<namespace>$","WorkloadType":"<workload-type>","WorkloadNameRegex":"^<escaped-workload-name>$"}}}'
```

These skeletons deliberately omit advanced extraction fields. Build them from the current full contract and validate them with [config-validation.md](config-validation.md). Do not use an empty Kubernetes filter.

For updates, use `collector.modify-rule` and its own contract. Do not reuse a create body: in 1.0.6, `collector.modify-rule` requires `RuleId` and does not accept `TopicId`.

## Binding

Inspect both sides before changing the relationship:

```bash
volclog --profile <profile> tool describe collector.describe-bound-host-groups --view full
volclog --profile <profile> tool describe host-group.describe-host-group-rules --view full

volclog --profile <profile> --dry-run tool exec collector.apply-rule-to-host-groups \
  --input '{"RuleId":"<rule-id>","HostGroupIds":["<host-group-id>"]}'
```

Remove `--dry-run` only for missing bindings. Do not assume applying an existing binding is harmless unless the current service contract says so.

## Index

```bash
volclog --profile <profile> tool exec index.describe \
  --input '{"TopicId":"<topic-id>"}'

volclog --profile <profile> --dry-run tool exec index.create \
  --input '{"TopicId":"<topic-id>","EnableAutoIndex":true,"FullText":{"CaseSensitive":false,"Delimiter":"<confirmed-delimiters>"}}'
```

Create only when the service explicitly reports that the index is absent. If it exists, use `index.modify`, preserve all user-owned settings, and preview delimiter behavior with `log.preview` before changing tokenization.

## Completion

Proceed to [verification.md](verification.md). Resource IDs and successful writes are intermediate evidence; the task is not complete until heartbeat, binding, and Topic ingestion are verified.
