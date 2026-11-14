# Execute native OpenAPI calls

## CLI system flags

Every `ve <service> <Action>` call accepts these **after the Action**, all with two hyphens:

| Flag | Purpose |
| --- | --- |
| `--profile <name>` | Use a configured profile for this call only |
| `--region <region>` | Override the region for this call only |
| `--endpoint <host>` | Override the endpoint for this call only |
| `--lang EN\|ZH` | Display language for this call |
| `--version <YYYY-MM-DD>` | API version; metadata default when omitted (required with `--force`) |
| `--method GET\|POST` | HTTP method; metadata default, else GET |
| `--force` | Skip metadata validation ([locate-api.md](locate-api.md)); presence-only, never `--force true` |
| `--output <fmt>` / `--query <jmespath>` | Response formatting and projection (below) |
| `--header Name=Value`, `--body '{...}'` | Custom header / raw JSON body |

API parameters are PascalCase (`--Region`, `--InstanceIds.1`), system flags are lowercase (`--region`), so they do not normally collide. Only when an API parameter is spelled exactly like a system flag in lowercase (an API with its own `--query` or `--lang` field), write the **system** flag with three hyphens (`---query`) and leave the API parameter with two. Do not use three-hyphen flags anywhere else.

CLI management commands (`ve configure ...`, `ve login`, `ve sso login`) and the helper scripts take their own two-hyphen flags as shown by `--help`.

## Basic format

```text
VE_CALLER_TYPE=ai_agent VE_CALLER_NAME=<agent-id> VE_SKILL_NAME=<current-volcengine-skill> \
  ve <ServiceCode> <ActionName> --ParamName "value" [system flags]
```

System flags (`--profile`, `--region`, `--endpoint`, `--output`, `--query`, …) go after the Action, in any order relative to the parameters.

## Parameter passing rules

Determine the format from `--help` output:
- **Flat parameter format**: `--help` lists individual `--Key type` entries (e.g., ECS, VPC, IAM) -> pass with `--Key "value"`
- **Array parameters**: prefer the numbered CLI form shown by `--help`, such as `--InstanceIds.1 "$instance_id"` or `--SubnetIds.1 "$subnet_id"`. Do not assume JSON-array strings are accepted by every action.
- **JSON format**: `--help` only shows `--body '{...}'` (e.g., Redis, CR, and other POST APIs) -> pass with `--body '{...}'`

```bash
# Flat parameters — nested fields use dot notation; arrays use .N index (starting from 1)
ve ecs RunInstances --ZoneId "cn-beijing-a"
ve ecs RunInstances --NetworkInterfaces.1.SubnetId "subnet-xxxx"
ve ecs RunInstances --Tags.1.Key "publish-by" --Tags.1.Value "deploy-skill"

# JSON format (when --help only shows --body)
ve redis CreateDBInstance --body '{"InstanceName":"demo","RegionId":"cn-beijing","ConfigureNodes":[{"AZ":"cn-beijing-a"}],"ShardedCluster":0,"NodeNumber":2,"ShardCapacity":1024,"ShardNumber":1,"EngineVersion":"6.0","SubnetId":"subnet-xxxx","VpcId":"vpc-xxxx","Password":"<secret>","Tags":[{"Key":"publish-by","Value":"deploy-skill"}]}'
```

## Output format and querying

Every API call accepts `--output` and `--query`; they replace ad-hoc `grep`/`jq` over the JSON.

| `--output` | Use |
| --- | --- |
| `json` (default) | Full response; the form to parse programmatically |
| `table` / `table-num` | Human-readable list; `table-num` adds a row-number column — good for showing the user a resource list |
| `text` | Plain values, one per line — good for capturing a single field or ID list in a shell variable |
| `yaml` | Human-readable nested detail |
| `off` | Run the call but print nothing (skips response-dependent `--query` evaluation). Only for calls whose response you genuinely do not need — never for `Create*`/`Run*`/`Allocate*`, whose response is the only place the new resource ID appears |

`--query` takes a JMESPath expression evaluated on the **full** response before formatting, so paths start at `Result.` (or `ResponseMetadata.`):

```bash
# Single field
ve sts GetCallerIdentity --query 'Result.AccountId' --output text

# Project a list for the user
ve ecs DescribeInstances --query 'Result.Instances[].{Id:InstanceId,Name:InstanceName,Status:Status,Zone:ZoneId}' --output table

# Filter, then pick IDs into a shell variable
ids=$(ve ecs DescribeInstances --query "Result.Instances[?Status=='RUNNING'].InstanceId" --output text)

# Length / existence checks
ve vpc DescribeVpcs --query 'length(Result.Vpcs)' --output text
```

Rules of thumb:
- Keep `json` when you (the agent) need to read the response; switch to `table`/`yaml` only for what you show the user.
- Do not `--query` a write/destructive call into silence before you have seen `ResponseMetadata.Error`; on failure the error object is still printed.
- `--query` filters what is printed, not what is requested — pagination (`NextToken`, `PageNumber`) is unchanged.

## Response format

```json
// Success
{ "ResponseMetadata": { "RequestId": "..." }, "Result": { ... } }

// Failure
{ "ResponseMetadata": { "Error": { "Code": "...", "Message": "..." } } }
```

## Error handling

A safety-policy block or confirmation request ([safety.md](safety.md)) means no request was sent. Handle it as that file describes; it is neither a permission error nor a CLI anomaly, so it does not start permission diagnosis or a feedback invitation.

Whenever a native `ve <service> <Action>` command or extension helper fails, or a response contains `ResponseMetadata.Error`, read [references/common-errors.md](common-errors.md) completely before diagnosing the error or responding to the user. Partial searches, matched lines, or excerpts do not satisfy this requirement. For `ve tosutil` / `ve arkcli` / `ve volclog` failures, follow the selected product skill and native child error format.

First classify the error as request-format, missing dependency, account state, service activation, real-name verification, purchase qualification, or permission related. For product-specific errors, also read the matching service note below. For permission errors (`AccessDenied`, `NoPermission`, `RoleNotExist`, `Forbidden`, or STS-related failures), activate the `volcengine-troubleshooting` skill and use its account-permission diagnosis capability to locate the root cause and guide the user through remediation.

For CLI anomalies or an incompletely solved task, follow the **non-blocking feedback** guidance in
`volcengine-troubleshooting`: continue the main task and reserve any optional invitation for a natural
summary. User-requested feedback belongs to `volcengine-feedback`; when unavailable, use the
[feedback form](https://github.com/volcengine/volcengine-agent-toolkit/issues/new?template=feedback.yml)
in the current conversation rather than installing a skill or restarting the task for feedback.

## Async resource creation requires polling

Some resources (VKE clusters, RDS instances, ECS instances, etc.) take several minutes to create. After creation, poll the Describe endpoint until the resource reaches the desired status before proceeding.

> Creating sub-resources (e.g., security groups) immediately after VPC creation may fail with `InvalidVpc.InvalidStatus`. Create sub-resources sequentially (subnet first, then security group), or wait a few seconds and retry.

```text
# General polling pattern: check every 30 s, give up after a deadline, stop on API failure
max_attempts=40   # 40 x 30 s = 20 min; size it to the resource type
for attempt in $(seq 1 "$max_attempts"); do
  if ! cur_status=$(ve <svc> Describe<Resource> --<IdParam> "xxx" --query 'Result.<Path>.Status' --output text 2>&1); then
    echo "describe failed: $cur_status"; break        # classify with common-errors.md, do not keep looping
  fi
  echo "$(date +%H:%M:%S) $cur_status"
  case "$cur_status" in
    Running) break ;;
    Error|Failed|Deleted) echo "resource entered $cur_status"; break ;;
  esac
  [ "$attempt" -eq "$max_attempts" ] && echo "timed out waiting for Running"
  sleep 30
done
```

`Result.<Path>` and the terminal status names differ per product — take them from `--help --detail` and the service note, do not assume `Running`.
