# Extended APIs

Use this reference when an OpenAPI is missing from the `ve` command surface (unknown service, or an Action the CLI metadata has not caught up with). There are two tools, in this order:

1. **`ve ... --force`** — for any Action/Version API. This is the default.
2. **`scripts/call_extend_api.py`** — only for APIs that need URL query parameters *and* a request body in one POST (VMP, Flink GWS), which `ve` cannot express.

Apply the confirmation mode chosen in [safety.md](safety.md) to `ve --force` calls. Extension-helper calls retain the built-in read/write/destructive confirmation rules; do not manually evaluate local policy rules in the skill. The confirmation notes here and in the linked files apply to calls using the built-in rules.

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

These are the service code / version / endpoint / signing-region facts an agent cannot guess. Action names are listed for lookup; parameter notes are in [extend-api-params.md](extend-api-params.md).

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

Only for APIs that need URL query parameters and a request body in one POST (VMP, Flink GWS). Registered APIs, free mode and how the helper finds credentials: [extend-api-helper.md](extend-api-helper.md).

## 3. Parameter notes

Per-service parameter notes (account verification, CDN, CodePipeline, DCDN, Domain, Flink, Global Accelerator, IoT, Live, MCDN, Metrics, `sec_agent`, Trademark, VEEN, VKE, VMP): [extend-api-params.md](extend-api-params.md). Read the service's note before calling it.

## 4. Notes for agents

- Prefer the normal `ve <service> <Action>` when the CLI knows the action; use `--force` only when it does not, and the helper only for the query+body cases above.
- Do not invent parameters. Use [extend-api-params.md](extend-api-params.md), the user's values, `find_api.py`, or the `volcengine-api` skill; if a required business ID is missing, get it with a read-only list/get call or ask.
- Many of these services return `AccessDenied` for accounts without the product entitlement; that is an IAM/product state, not a request-shape problem (see `common-errors.md`).
