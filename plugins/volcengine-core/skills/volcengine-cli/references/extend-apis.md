# Extended APIs

Use this reference when an OpenAPI is missing from the `ve` command surface (unknown service, or an Action the CLI metadata has not caught up with). There are two tools, in this order:

1. **`ve ... --force`** — for any Action/Version API. This is the default.
2. **`scripts/call_extend_api.py`** — only for APIs that need URL query parameters *and* a request body in one POST (VMP, Flink GWS), which `ve` cannot express.

Apply the same read/write/destructive confirmation rules from `SKILL.md` to both.

Apply [the mandatory Agent caller metadata](../SKILL.md#agent-caller-metadata-mandatory) to every
`ve --force` invocation and to the Python helper process. The helper's internal `ve` credential
probe and the audit script's CLI discovery calls must inherit all three variables. Keep these
values in the process environment; do not add them to API query parameters or request bodies.

## 1. `ve --force`

`--force` skips the local service/action metadata check and sends the request as-is. It needs the facts the metadata would normally supply:

```bash
ve <service> <Action> \
  --version <YYYY-MM-DD> \
  --endpoint <host> \
  [--method GET|POST] \
  [--region <region>] \
  --<Param> <value> ... \
  --force
```

- `--version` is mandatory with `--force` (`--version is required when using --force`).
- `--endpoint` is mandatory for a service the CLI does not know; the profile endpoint or `VOLCENGINE_ENDPOINT` also satisfies it. Most services use `open.volcengineapi.com`; the table below lists the exceptions.
- `--method` defaults to GET. Use `--method POST` for POST APIs.
- `--region` matters for signing: several media/edge services sign with `cn-north-1` regardless of resource location.
- `--body '{...}'` sends a JSON body and cannot be combined with flattened `--Param` values. `--header Name=Value` adds headers (Content-Type overrides the default; Host/Authorization/Content-Length are blocked).
- `--force` is presence-only: write `--force`, never `--force true`.
- `--output` and `--query` work as usual.

Examples:

```bash
# Unknown-to-ve service, GET
ve domain_openapi CheckFee --version 2022-12-12 --endpoint open.volcengineapi.com \
  --region cn-north-1 --domain example.com --force

# POST with a JSON body
ve dcdn DescribeRealtimeData --version 2021-04-01 --endpoint open.volcengineapi.com \
  --region cn-north-1 --method POST \
  --body '{"StartTime":"2026-01-01 00:00:00","EndTime":"2026-01-01 01:00:00","Metrics":["all"]}' --force

# Region-templated endpoint
ve metrics ListWorkspace --version 2024-06-29 --endpoint metrics.cn-beijing.volcengineapi.com \
  --method POST --body '{"PageNumber":1,"PageSize":20,"ListGlobal":true}' --force
```

### Service recipes

These are the service code / version / endpoint / signing-region facts an agent cannot guess. Action names are listed for lookup; parameter notes are in section 3.

| Service code | Version | `--endpoint` | `--region` | Method | Actions |
| --- | --- | --- | --- | --- | --- |
| `account_verify` | `2018-01-01` | `open.volcengineapi.com` | profile default | POST | `GetVerifyInfo` (service and action are absent from the CLI metadata; `--force` required) |
| `cdn` | `2021-03-01` | `cdn.volcengineapi.com` | `cn-north-1` | POST | `DescribeOriginTopStatisticalData` — `ve cdn` exists but does not list this action; `ve cdn ... --force` signs correctly (verified: returns business errors such as `NotFound.Domain`, not signature errors) |
| `cp` | `2023-05-01` | `open.volcengineapi.com` | profile default | POST | `ListPipelineRunStagesInner` |
| `dcdn` | `2021-04-01` | `open.volcengineapi.com` | `cn-north-1` | POST | `DescribeRealtimeData`, `DescribeOriginRealtimeData`, `DescribeTopIPs`, `DescribeTopReferers`, `DescribeTopUrls` |
| `domain_openapi` | `2022-12-12` | `open.volcengineapi.com` | `cn-north-1` | GET | `CheckFee`, `GetAsyncTask`, `GetDomain`, `GetTemplate`, `ListDomains`, `ListTemplates` |
| `domain_openapi` | `2022-12-12` | `open.volcengineapi.com` | `cn-north-1` | POST | `RegisterDomain` (billable) |
| `flink` | `2021-06-01` | `open.volcengineapi.com` | profile default | GET | `ListGMSProject`, `GetGMSProjectDetail`, `GetGRSAppById` (formerly sent with `Content-Type: text/plain`) |
| `flink` | `2022-06-01` | `open.volcengineapi.com` | profile default | GET | `ListGMCSResourcePool` |
| `flink` | `2021-06-01` | `open.volcengineapi.com` | profile default | POST | `ListGASLogs`, `GetGWSApplication` — other GWS actions need the helper (section 2) |
| `ga` | `2022-03-01` | `open.volcengineapi.com` | `cn-north-1` | GET | `ListAccelerateAreas` |
| `ga` | `2022-03-01` | `open.volcengineapi.com` | `cn-north-1` | POST | `ListBandwidthPackages`, `GetBandwidthPackage`, `GetAcceleratorDimension`, `DescribeListenerLogs`, `GetBasicEndpointRelatedAccInstanceInfos`, `GetEndpointRelatedAccInstanceInfos` |
| `iot` | `2021-12-14` | `iot.cn-shanghai.volcengineapi.com` | `cn-shanghai` | POST | `GetInstanceList`, `GetInstanceDetail`, `GetInstanceEndpoints`, `GetProductList`, `GetProductDetail`, `GetDeviceList`, `GetDeviceDetail`, `GetDeviceStatus`, `GetDeviceOverview`, `GetThingModel`, `GetCustomTopicList`, `GetLastDevicePropertyValue`, `GetAllLastDevicePropertyValue`, `GetPropertyValuesByTime`, `GetDeviceEventRecordList`, `GetDeviceServiceCallRecordList`, `CallService`, `SetProperty` |
| `live` | `2023-01-01` | `live.volcengineapi.com` | `cn-north-1` | POST | `DescribeLiveBatchStreamTranscodeData`, `DescribeLiveBatchStreamSessionData` |
| `mcdn` | `2022-03-01` | `open.volcengineapi.com` | `cn-north-1` | GET | `DescribeCdnDomainConfig` |
| `metrics` | `2024-06-29` | `metrics.<region>.volcengineapi.com` | that region | POST | `ListWorkspace`, `GetWorkspaceInfo`, `ListQueryClusters`, `GetQueryCluster`, `ListPreagg`, `InfluxQuery`, `MetricsQuery` |
| `sec_agent` | `2025-01-01` | `open.volcengineapi.com` | profile default | POST | `RunAlertFormatter`, `RunAlertInvestigator`, `RunDlpScreenshotAnalyzer`, `RunPcapAnalyzer`, `RunSensitiveDataDetector`, `RunThreatIntelProducer`, `RunWebRiskAssessor` |
| `trademark` | `2023-06-01` | `open.volcengineapi.com` | `cn-north-1` | GET | `GetApplicant`, `GetRequirement`, `GetTrademark`, `ListApplicants`, `ListBarrierTrademarks`, `ListRequirements`, `ListTrademarks` |
| `trademark` | `2023-06-01` | `open.volcengineapi.com` | `cn-north-1` | POST | `SearchTrademark`, `SearchTrademarkInfo` |
| `veenedge` | `2021-04-30` | `veenedge.volcengineapi.com` | `cn-north-1` | POST | `StopCloudServer`, `RebootCloudServer` (param `cloud_server_id`) |
| `vke` | `2022-05-12` | `open.volcengineapi.com` | profile default | POST | `CreateVirtualNode`, `ListVirtualNodes` |
| `vmp` | `2021-03-03` | `vmp.<region>.volcengineapi.com` | that region | POST | helper only (section 2) |

The other former veenedge extension actions (StartCloudServer and the four usage queries) are already in the CLI metadata and are deliberately absent from this table.

Rule: whenever the CLI metadata lists an Action of the same name (`ve <service> <Action> --help` works), use the plain command and ignore this table. Run `python3 scripts/audit_extend_apis.py` after upgrading `ve` to find rows that have become plain CLI actions.

For an Action that is not in this table, `python3 scripts/find_api.py <keyword>` can locate only its Service/Action/Version. Get method, endpoint and parameters from the user's material or the `volcengine-api` skill — do not guess them.

## 2. `scripts/call_extend_api.py` — query + body in one request

`ve --force` cannot put some parameters in the URL query string and the rest in a body (`--body` excludes flattened parameters, and the body is JSON only). The helper does exactly that and nothing else.

```bash
python3 scripts/call_extend_api.py --list                 # registered APIs and their query keys
python3 scripts/call_extend_api.py --describe QueryMetrics
```

### Registered APIs

| Service | Version | Endpoint | Body | Actions and URL query keys |
| --- | --- | --- | --- | --- |
| `vmp` | `2021-03-03` | `vmp.<region>.volcengineapi.com` | `application/x-www-form-urlencoded` | `QueryMetrics`, `QueryMetricsRange`, `GetLabels`, `GetSeries` → `workspace`; `GetLabelValues` → `workspace`, `label` |
| `flink` | `2021-06-01` | `open.volcengineapi.com` | JSON | `ListGWSDirectory` → `ProjectId`, `Type`; `GetGWSApplicationDraft`, `DeleteGWSApplication`, `GWSGetEventList`, `StartGWSApplication`, `CancelGWSApplication`, `RestartGWSApplication` → `ProjectId`; `CreateGWSApplicationDraft`, `UpdateGWSApplicationDraft` → `ProjectId` (also kept in the body); `DeployGWSApplicationDraft` → `ProjectId`, `Id`; `ListGWSApplication` → `PageSize`, `PageNum`, `SortField`, `SortOrder` |

Pass every field in one `--params` JSON object; the helper moves the query keys to the URL:

```bash
python3 scripts/call_extend_api.py \
  --api QueryMetrics \
  --params '{"workspace":"vmp-workspace-id","query":"up"}'

python3 scripts/call_extend_api.py \
  --api CreateGWSApplicationDraft \
  --params @request.json
```

Options: `--region` (drives the `vmp.<region>` host and the signing scope), `--host` (override endpoint), `--content-type`, `--output json|pretty`, `--show-headers`, `--profile`. STS tokens come from `VOLCENGINE_SESSION_TOKEN` or the profile; do not put them on the command line.

### Free mode (unregistered API with the same problem)

```bash
python3 scripts/call_extend_api.py \
  --api SomeAction --service <svc> --version <YYYY-MM-DD> \
  --query-keys ProjectId,Type [--body-keys-also ProjectId] \
  [--method POST] [--host <endpoint>] [--content-type application/x-www-form-urlencoded] \
  --params '{"ProjectId":"...","Type":"JOB","Other":"..."}'
```

`--query-keys` is required in free mode; without it the API has no query/body split and belongs to `ve --force` (the helper says so and exits). Without `--host` the endpoint is `VOLCENGINE_ENDPOINT` or `open.volcengineapi.com`. `--body-keys-also` names query keys that must additionally stay in the body.

### Credentials

Resolution order:

1. `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY` (+ optional `VOLCENGINE_SESSION_TOKEN`).
2. The `ve` config file (`VOLCENGINE_CLI_CONFIG_FILE`, default `~/.volcengine/config.json`): the selected profile's `access-key`/`secret-key`, or for a `console-login` profile its unexpired local `ve login` cache (`VOLCENGINE_LOGIN_CACHE_DIRECTORY` overrides the cache dir).

Profile selection follows the conversation-scoped rule in `SKILL.md`: pass `--profile` only when the user explicitly selected one; otherwise the config's current profile, then `VOLCENGINE_PROFILE`, is used. The helper does not refresh SSO, assume roles, or fetch ECS metadata; when nothing usable is found it says so — run `ve login`, `ve configure set`, or export the env credentials. Never print AK/SK/session tokens.

## 3. Parameter notes

Facts gathered while validating these APIs. Pass them as `--Param` values (or `--body` JSON) with `ve --force`, or inside `--params` for the helper.

### Account verification

- `GetVerifyInfo`: no parameters. Personal real-name = `IsVerified=true` + `IdentityType="individual"`; enterprise = `IsVerified=true` + `IdentityType="enterprise"`.

### CDN

- `DescribeOriginTopStatisticalData`: required `Domain`, `StartTime`, `EndTime` (Unix seconds), `Item` (`url`), `Metric` (`flux`, `pv`, `status_2xx`, `status_3xx`, `status_4xx`, `status_5xx`).

### CodePipeline

- `ListPipelineRunStagesInner`: required `WorkspaceId`, `PipelineId`, `PipelineRunId`. Find them with the public `ve cp` list APIs first.

### DCDN

- `DescribeRealtimeData`, `DescribeOriginRealtimeData`: required `StartTime`, `EndTime` as `"YYYY-MM-DD HH:MM:SS"` within 24 h, `Metrics` array (`all`, `traffic`, `bandwidth`, `request`, `QPS`, `2xx`…`5xx`; edge also `RequestHitRate`, `TrafficHitRate`). Optional `Domains`, `ProjectName`, `IspNameEn`, `RegionNameEn`, `Protocol`, `Type`, `IPVersion`.
- `DescribeTopIPs`, `DescribeTopReferers`, `DescribeTopUrls`: required `StartTime`, `EndTime`, `Sort` (`traffic`, `bandwidth`, `request`, `QPS`); optional `Limit` (1–100), `ProjectName`, `Domain`, `StatusCode`.

### Domain (`domain_openapi`, lowercase snake_case params)

- `CheckFee`: `domain`. `GetDomain`: `domain` or `instance_no`. `GetAsyncTask`: `task_no`. `GetTemplate`: `tag`.
- `ListDomains`: optional `domain`, `status`, `verify_status`, `expired_after`, `is_auto_renew`, `domain_name_audit_status`, `order_by`, `asc_or_desc`, `page_number`, `page_size`.
- `ListTemplates`: optional `registrant_zh`, `registration_type`, `tag`, `status`, `page_number`, `page_size`.
- `RegisterDomain` (POST body): required `domain`, `template_tag`; optional `period`, `ns_list`, `is_auto_renew`, `package_id`. Billable, creates an async task — confirm with the user first.

### Flink

- GET: `ListGMSProject` optional `SearchKey`, `PageSize`, `PageNum`; `GetGMSProjectDetail` required `ProjectName`; `ListGMCSResourcePool` (`2022-06-01`) `ProjectId`, optional `Name`, `NameKey`, `PageSize`, `PageNum`; `GetGRSAppById` required `AppIdKey`.
- POST via `ve --force --body`: `GetGWSApplication` required `Id`, optional `AccountId`; `ListGASLogs` `Application`, `Project`, `StartTime`, `EndTime`, optional `Level`, `Properties.component`, `Properties.podName`, `Cursor`, `PageSize`.
- GWS via the helper: `ListGWSDirectory` `Type` is `JOB` or `QUERY`; `GetGWSApplicationDraft` `ProjectId`, `Id`; `CreateGWSApplicationDraft` `ProjectId`, `JobName`, `DirectoryId`, optional `JobType`, `EngineVersion`; `UpdateGWSApplicationDraft` `Id`, `ProjectId`, `AccountId`, `UserId`, `JobName`, `JobId`, `DirectoryId`, `DirectoryName`, `SqlText`, optional `DynamicOptions`, `JobType`, `EngineVersion`; `DeployGWSApplicationDraft` `ProjectId`, `Id`, `ResourcePool`, `Queue`, optional `Priority`, `SchedulePolicy`, `ScheduleTimeout`; `Delete/Start/Cancel/RestartGWSApplication` `ProjectId`, `Id` (start/restart also `Type` such as `FROM_NEW`, `FROM_LATEST`); `ListGWSApplication` optional `ProjectId`, `JobName`, `ResourcePool`, `JobType`, `State`, pagination and sort keys; `GWSGetEventList` `ProjectId`, optional `Id`, `Limit`.

### Global Accelerator

- `ListAccelerateAreas`: none. `GetBandwidthPackage`: `BandwidthPackageId`.
- `ListBandwidthPackages`: `BandwidthType`, `PageNumber`, `PageSize`; optional `AcceleratorId`, `AccountId`, `BandwidthPackageId`, `Domain`, `Isp`, `OrderType`, `State`, `States`, `ProjectName`, `ResourceTagFilter`.
- `GetAcceleratorDimension`: `AcceleratorType`, `TargetName`, `Filters` (array of `{"Name":..., "Values":[...]}`).
- `DescribeListenerLogs`: `InputIdType`, `InputId`, `StartTime`, `EndTime`, `Interval`; optional `Metrics`, `RegionType`, `Region`, grouping fields.
- `Get(Basic)EndpointRelatedAccInstanceInfos`: the endpoint identifier of the matching endpoint type plus `PageNum`/`PageSize`.

### IoT

Identifiers by level: `InstanceId`; `ProductKey`/`ProductID`; `DeviceName`/`DeviceID`/`DeviceSecret`; thing model `ModuleKey`, `Identifier`, `PropertyIdentifier`, `EventIdentifier`, `ServiceIdentifier`; pagination/time `PageNumber`, `PageSize`, `StartTime`, `EndTime`. `CallService` needs device identifiers + service identifier + input params; `SetProperty` needs device identifiers + property values.

### Live

- `DescribeLiveBatchStreamTranscodeData` / `DescribeLiveBatchStreamSessionData`: required `StartTime`, `EndTime` as RFC3339 (`2022-11-10T00:00:00+08:00`); optional `DomainList`, `PageNum`, `PageSize` (+ `OnlineUserType` for session data).

### MCDN

- `DescribeCdnDomainConfig`: prefer `DomainId`; also `DomainName`, `Vendor`, `DomainVersion`, `NormalizeOptions`.

### Metrics

- `ListWorkspace`: `PageNumber`, `PageSize`, `ListGlobal`; optional `Filters`, `ProjectName`. `GetWorkspaceInfo`: `WorkspaceId`.
- `ListQueryClusters`: `Page` object (`PageNumber`, `PageSize`); optional `Name`, `ProjectName`. `GetQueryCluster`: `Id`.
- `ListPreagg`: `PageNumber`, `PageSize`, `onlyShowMine`; optional `Filters` such as `{"WorkspaceName":"..."}`.
- `InfluxQuery`, `MetricsQuery`: workspace identifier, query expression(s), time range.

### Security workflows (`sec_agent`)

`Run*` actions need real input (alert details, PCAP, URL, screenshot, text). An empty call is not a validation.

### Trademark

- GET: `GetApplicant` `ApplicantID`; `GetTrademark` `TrademarkID`; `GetRequirement` `RequirementID`; list APIs take filters plus `PageNumber`, `PageSize` (`ListApplicants` also `ApplicantType`, `ApplicantName`, `Status`, `Country`, `OrderBy`).
- POST: `SearchTrademarkInfo` `ClassID`, `RegistrationNumber`; `SearchTrademark` at least one of `TrademarkName`, `ApplicantName`, `RegistrationNumber`, optional pagination/class/status filters.

### VEEN

- `StartCloudServer` and the four usage-query Actions are in the CLI metadata: use plain `ve veenedge <Action>` and read `--help --detail`.
- `StopCloudServer` / `RebootCloudServer` stay force-only and take `cloud_server_id`; confirm before running.

### VKE

- `ListVirtualNodes`: optional pagination and cluster/virtual-node filters.
- `CreateVirtualNode`: `Kubeconfig`, `VirtualNodeConfig`. Creates infrastructure; there is no matching virtual-node delete in this list, so plan cleanup through public VKE APIs first.

### VMP (helper)

- `QueryMetrics`: body `query`, optional `time`. `QueryMetricsRange`: body `query`, `start`, `end`, `step`.
- `GetLabels`, `GetSeries`, `GetLabelValues`: body `match[]` (Prometheus HTTP API name — not `match`/`matches`), optional `start`, `end`.
- For instant queries on freshly remote-written data, query at or after the sample timestamp; earlier instants correctly return an empty vector.
- Workspace setup for testing: `ve vmp CreateWorkspace --body '{...,"PublicAccessEnabled":true,...}'`; BasicAuth is set with `Username` + base64 `Password` via `UpdateWorkspace` (do not pass `AuthType: Basic`); remote write goes to `PrometheusWriteEndpoint` + `/api/v1/write` (HTTP 204 on success; `/api/v1/push` is not accepted).

## 4. Notes for agents

- Prefer the normal `ve <service> <Action>` when the CLI knows the action; use `--force` only when it does not, and the helper only for the query+body cases above.
- Do not invent parameters. Use section 3, the user's values, `find_api.py`, or the `volcengine-api` skill; if a required business ID is missing, get it with a read-only list/get call or ask.
- Many of these services return `AccessDenied` for accounts without the product entitlement; that is an IAM/product state, not a request-shape problem (see `common-errors.md`).
