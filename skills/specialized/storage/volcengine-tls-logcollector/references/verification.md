# Verify the LogCollector path

Treat process health, machine heartbeat, rule binding, and Topic ingestion as separate gates. Passing an earlier gate does not prove the later ones.

## 1. Runtime and contract

```bash
command -v volclog
volclog --version
volclog --profile <profile> doctor
volclog --profile <profile> doctor --online

volclog tool describe host-group.describe-hosts --view full
volclog tool describe host-group.describe-host-group-rules --view full
volclog tool describe collector.describe-rule-v2 --view full
volclog tool describe log.search --view full
```

Keep the chosen runtime selector explicit. Do not expose credentials. Use the current contract when example fields differ.

## 2. Process or workload health

Linux host:

```bash
sudo systemctl is-active logcollectord.service
sudo systemctl status logcollectord.service --no-pager -l
/usr/local/logcollector/logcollector -v
```

Kubernetes:

```bash
kubectl -n <namespace> get daemonset,pods -o wide
kubectl -n <namespace> describe daemonset <daemonset-name>
kubectl -n <namespace> logs daemonset/<daemonset-name> --tail=200
```

For Controller/CRD, also inspect the Controller Deployment, its logs, the `LogCollectorRule` object, and its status.

## 3. Machine heartbeat

```bash
volclog --profile <profile> tool exec host-group.describe-hosts \
  --input '{"HostGroupId":"<host-group-id>","PageNumber":1,"PageSize":100}'
```

Check the complete response for:

- expected host or node count
- healthy heartbeat status
- expected host identity, hostname/IP, and LogCollector version
- Label matching the host group's `HostIdentifier`, unless the deployment explicitly uses an IP group

A short control-plane delay immediately after installation can be normal. Persistent absence requires endpoint, credential, network, and identity investigation; it is not fixed by blindly reinstalling.

## 4. Rule and binding

```bash
volclog --profile <profile> tool exec collector.describe-rule-v2 \
  --input '{"RuleId":"<rule-id>"}'

volclog --profile <profile> tool exec host-group.describe-host-group-rules \
  --input '{"HostGroupId":"<host-group-id>","PageNumber":1,"PageSize":100}'
```

Confirm `RuleId`, `TopicId`, input type, paths, parser settings, container filters, and the rule-to-host-group relationship. Re-read each action's contract if the field names differ.

## 5. Topic ingestion

Calculate a bounded Unix-seconds interval at execution time:

```bash
volclog --profile <profile> tool exec log.search \
  --input '{"TopicId":"<topic-id>","StartTime":<start-unix-seconds>,"EndTime":<end-unix-seconds>,"Query":"*","Limit":100,"Sort":"desc"}'
```

Use representative business fields, `__path__`, and container metadata to prove that the expected source—not merely some source—is arriving. `HitCount` describes the current response window, not necessarily the whole interval. If `ResultStatus=incomplete`, narrow the interval before trusting counts or absence of data.

For large exports, read `volclog workflow describe log.export`; do not emulate full export with repeated high offsets.

## 6. Temporary self-log POC

Use LogCollector self-logs only when the user explicitly requested a temporary POC and accepted the feedback-loop risk.

- Host POC: verify `__path__` matches only the approved LogCollector log path.
- Kubernetes POC: verify logs come only from the exact LogCollector namespace/workload/container and selected stream.
- Query two short, adjacent windows and compare ingestion rate with collector CPU/memory and self-logs.
- If the rate accelerates unexpectedly, immediately unbind and delete the POC rule using current contracts.
- Remove temporary rules and resources after the test unless the user explicitly asks to retain them.

## Success criteria

The collection task succeeds only when all applicable statements are true:

1. LogCollector service or Kubernetes workload is healthy.
2. The intended hosts or nodes have healthy heartbeats in the exact host group.
3. The intended rule is configured as validated and bound to that group.
4. The exact Topic receives new logs from the intended source in a bounded post-deployment interval.
5. Parsed fields, timestamp, path/container metadata, and index behavior match the validated design.
