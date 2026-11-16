# Extended APIs: parameter notes

Per-service parameter notes for the `--force` recipes in [extend-apis.md](extend-apis.md) and the helper in [extend-api-helper.md](extend-api-helper.md). Confirmation notes apply to calls using the built-in rules ([safety.md](safety.md)).

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
- `RegisterDomain` (POST body): required `domain`, `template_tag`; optional `period`, `ns_list`, `is_auto_renew`, `package_id`. Billable, creates an async task — in built-in mode, confirm with the user first.

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
- `StopCloudServer` / `RebootCloudServer` stay force-only and take `cloud_server_id`; in built-in mode, confirm before running.

### VKE

- `ListVirtualNodes`: optional pagination and cluster/virtual-node filters.
- `CreateVirtualNode`: `Kubeconfig`, `VirtualNodeConfig`. Creates infrastructure; there is no matching virtual-node delete in this list, so plan cleanup through public VKE APIs first.

### VMP (helper)

- `QueryMetrics`: body `query`, optional `time`. `QueryMetricsRange`: body `query`, `start`, `end`, `step`.
- `GetLabels`, `GetSeries`, `GetLabelValues`: body `match[]` (Prometheus HTTP API name — not `match`/`matches`), optional `start`, `end`.
- For instant queries on freshly remote-written data, query at or after the sample timestamp; earlier instants correctly return an empty vector.
- Workspace setup for testing: `ve vmp CreateWorkspace --body '{...,"PublicAccessEnabled":true,...}'`; BasicAuth is set with `Username` + base64 `Password` via `UpdateWorkspace` (do not pass `AuthType: Basic`); remote write goes to `PrometheusWriteEndpoint` + `/api/v1/write` (HTTP 204 on success; `/api/v1/push` is not accepted).
