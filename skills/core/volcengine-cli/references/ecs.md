# ECS Service Notes

## Resource Discovery Pitfalls

`DescribeInstanceTypes` returns only a small default page and does not prove zone inventory. For placement decisions, query the target zone with `DescribeAvailableResource`; otherwise `RunInstances` can fail with `InvalidInstanceType.NotFound` even when the type exists globally.

For instance type inventory, read `.Result.AvailableZones[].AvailableResources[] | select(.Type=="InstanceType").SupportedResources[]`, then keep entries whose `Status` is `Available`; do not look for a top-level `InstanceTypes` list.

veLinux image search should use an exact name prefix. A fuzzy keyword like `velinux` also matches GPU, Docker, ARM, and other variants. Known useful names:

- `veLinux 2.0 64`
- `veLinux 2.0 ARM 64`

## Current RunInstances Shape

Current CLI accepts `--ZoneId` for `RunInstances`; older examples may show `--Placement.ZoneId`. Check the installed CLI help before assuming one shape.

`RunInstances` requires either `--Password` or `--KeyPairName`, even when SSH is not opened. For Cloud Assistant-only deployments, generate a one-time strong password and do not log or persist it.

For no-EIP validation, remove all `EipAddress.*` parameters and use `--DryRun true`. A successful DryRun exits non-zero and prints `DryRunOperation`; this is expected and creates no instance.

Inline EIP `ChargeType` values observed in help/validation are `PayByBandwidth`, `PayByTraffic`, and `PrePaid`.

If creating the VPC/subnet/security group immediately before `RunInstances`, wait for VPC and security group readiness first. The API can return `InvalidVpc.InvalidStatus` when a subnet is created right after `CreateVpc`, and `InvalidSecurityGroup.InvalidStatus` when an ingress rule is written right after `CreateSecurityGroup`.

## DeleteInstance Status Casing

`DescribeInstances` can return uppercase statuses such as `CREATING` and `RUNNING`. Do not compare only against title-case values.

Calling `DeleteInstance` while the instance is still `CREATING` fails with `InvalidInstanceStatus`. Poll until `RUNNING`, `STOPPED`, or another deletable final state before deletion.

Verified no-EIP lifecycle: created a disposable instance, confirmed `EipAddress: null`, waited for `RUNNING`, deleted it, and verified a follow-up name query returned `TotalCount: 0`.

## Cloud Assistant Gotchas

After `InstallCloudAssistant`, the agent can report `ReadyReboot`; `RunCommand` may keep timing out until the instance is rebooted. Prefer `--InstallRunCommandAgent true` during instance creation.

`RunCommand` requires an explicit `--InvocationName`. Use a name no longer than 64 characters, containing only Chinese characters, letters, digits, underscores, or hyphens, and do not start it with a digit or hyphen. Keep it short and stable, for example `deploy-check`; if omitted, some `ve` CLI versions can derive the invocation name from `CommandContent`, and base64 or long shell payloads then fail with `LimitExceeded.MaximumInvocationName`.

`RunCommand --Timeout` minimum is 60 seconds. Lower values fail with `LimitExceeded.MaximumTimeout`.

`RunCommand --CommandContent` must be base64-encoded shell content. Passing plain text such as `echo OK` can fail with `InvalidBase64Content.Malformed`.

Treat `RunCommand` as scheduling only. Poll invocation results and read the result status from `.Result.InvocationResults[0].InvocationResultStatus`; terminal values include `Success`, `Failed`, and `Timeout`. Pair it with `.Result.InvocationResults[0].ExitCode`, and decode `.Result.InvocationResults[0].Output` from base64 when inspecting command output.

```bash
command_b64=$(printf '%s' 'systemctl is-active --quiet app && echo OK' | base64 | tr -d '\n')
invocation_id=$(ve ecs RunCommand \
  --Type Shell \
  --InstanceIds.1 "$instance_id" \
  --InvocationName "deploy-check" \
  --Timeout 60 \
  --CommandContent "$command_b64" \
  | jq -r '.Result.InvocationId')
if [ -z "$invocation_id" ] || [ "$invocation_id" = "null" ]; then
  echo "RunCommand returned no InvocationId; check its error, including safety-policy blocks" >&2
  exit 1
fi

for _ in $(seq 1 30); do
  result=$(ve ecs DescribeInvocationResults --InvocationId "$invocation_id" --InstanceId "$instance_id")
  result_status=$(printf '%s' "$result" | jq -r '.Result.InvocationResults[0].InvocationResultStatus // empty')
  exit_code=$(printf '%s' "$result" | jq -r '.Result.InvocationResults[0].ExitCode // empty')
  case "$result_status" in
    Success|Failed|Timeout) break ;;
  esac
  sleep 5
done

echo "$result" \
  | jq -r '.Result.InvocationResults[0] | [.InvocationResultStatus, (.ExitCode | tostring)] | @tsv'
if [ "$result_status" != "Success" ] || [ "$exit_code" != "0" ]; then
  echo "RunCommand failed or timed out" >&2
  exit 1
fi
echo "$result" \
  | jq -r '.Result.InvocationResults[0].Output // ""' \
  | base64 -d
```

## veLinux Docker Deployment

veLinux 2 may report `VERSION_CODENAME=lyra`; do not use `lyra` as the Docker official Debian repository codename. For quick deployments, prefer the distribution package:

```bash
apt-get update
apt-get install -y docker.io
systemctl enable --now docker
```

Docker Hub and GHCR can time out from China regions. Prefer Volcengine CR, user-provided registries, or verified mirror pull commands from the mirror's own image detail page. `docker.aityp.com` can be used as a search/sync candidate for some images, but do not assume `docker.aityp.com/<image>` is a universal drop-in registry path.
