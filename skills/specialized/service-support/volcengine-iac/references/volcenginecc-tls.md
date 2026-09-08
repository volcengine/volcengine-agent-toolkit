# Volcenginecc TLS Example

Verified example path:

```text
assets/examples/volcenginecc-tls/main.tf
assets/examples/volcenginecc-tls-schedule-sql/main.tf
assets/examples/volcenginecc-tls-import-task/main.tf
```

Use these examples when a Volcengine deployment needs a Terraform-managed TLS log project, topic, search index, a basic host file collection rule, a consumer group for log consumption, a scheduled SQL task that writes results to another TLS topic, or a TOS-to-TLS import task. Use [`volcenginecc-cloudmonitor.md`](./volcenginecc-cloudmonitor.md) for CloudMonitor alert rules.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_tls_project` | Log Service project for isolating application/service logs |
| `volcenginecc_tls_topic` | Log topic for ingestion, search, analysis, and consumption |
| `volcenginecc_tls_index` | Search/analysis index for a topic |
| `volcenginecc_tls_rule` | Host file collection rule template for LogCollector |
| `volcenginecc_tls_consumer_group` | Consumer group for shard-based log consumption |
| `volcenginecc_tls_schedule_sql_task` | Scheduled SQL analysis from one topic into another topic |
| `volcenginecc_tls_import_task` | Batch/stream import from TOS into a TLS topic |

## Dependency-blocked resources

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_tls_alarm_notify_group` | Provider-shape blocked | Empty groups are rejected by the API; both top-level GeneralWebhook `receivers` and `notice_rules.receiver_infos` created but provider `0.0.46` returned inconsistent nested sets after apply. |
| `volcenginecc_tls_alarm` | Dependency-blocked | Requires a stable alarm notification group ID. Do not add until `tls_alarm_notify_group` is no-op clean or an existing group is intentionally imported. |
| `volcenginecc_tls_shipper` | Drift-blocked | TOS shipper can create/delete, but disabled `status = false` reads back as `true`, causing a follow-up plan diff. |
| `volcenginecc_cloudmonitor_rule` | Verified separately | Disabled ECS CPU rule create/no-op/destroy succeeded; see `volcenginecc-cloudmonitor.md`. |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-tls
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -out=tfplan-noop.binary -input=false
terraform destroy
```

Observed apply result: project, topic, index, a basic host file rule, a consumer group, the separate scheduled SQL task stack, and the separate TOS import task stack created successfully. Follow-up plans returned `No changes` after omitting import task `status`. Destroy removed TLS resources and the import task; the TOS bucket was actually deleted but its Cloud Control destroy waiter could remain stale, so verify bucket absence before any temporary state cleanup.

Observed timings in `cn-beijing`: project creation took about 1s, topic creation about 1-3s, index creation about 6-11s, rule creation about 1s, TOS import task creation about 3s, and import task deletion about 2s. The dependent TOS bucket creation took about 1m56s, and its destroy waiter was still running after 5m even though `tosutil stat` returned 404.

## Pitfalls found during verification

1. `volcenginecc_tls_topic.project_id` needs the project ID, not project name. Use `volcenginecc_tls_project.main.project_id`.

2. Keep the default example away from tiered storage fields unless explicitly needed. `enable_hot_ttl`, `hot_ttl`, `cold_ttl`, and `archive_ttl` have cross-field constraints; the verified example uses simple 30-day retention with `ttl = 30`.

3. `volcenginecc_tls_index` must define at least one index mode. The example enables both a small full-text index and one key-value text index.

4. Fully define nested index attributes. The generated docs warn that partial nested set/list objects can cause unstable diffs. The example fills `auto_index_flag`, `case_sensitive`, `delimiter`, `include_chinese`, `index_all`, `index_sql_all`, `sql_flag`, and `value_type` for the key-value field.

5. `max_text_len` docs say valid range is 64-16384 bytes; the generated example uses 20480, which is outside the documented range. The verified example uses 2048.

6. `tls_rule` can be created without `host_group_infos`, but `paths` must still be set for host file collection. The first minimal retry omitted `paths` and failed with `InvalidArgument: Invalid argument key Paths, value <nil>`.

7. Do not set `pause = 1` in the default `tls_rule`. The service created the rule, but read it back as `pause = 0`, causing a follow-up plan to update `0 -> 1`. Omitting `pause` produced a clean no-op plan.

8. Generated `tls_rule` examples include placeholder `host_group_id` values and many optional nested collection fields. Do not copy those placeholders into generated IaC. Start from the verified minimal host-file rule, then add a real host group only when the deployment actually has LogCollector hosts.

9. `tls_consumer_group` was verified with `allow_consume = true` on the topic. The topic reads back a generated `consume_topic` value, but the follow-up plan stayed clean.

10. `tls_alarm_notify_group` needs either `notice_rules` or both `notify_type` and `receivers`. An empty notification group planned but failed during create with `InvalidArgument: Invalid argument key NotifyType, value []`.

11. A minimal top-level GeneralWebhook `tls_alarm_notify_group` did create and delete, but provider `0.0.46` failed the apply with `Provider produced inconsistent result after apply` because `receivers` did not correlate with the actual returned set. A later retry using `notice_rules.receiver_infos` also created and deleted successfully, but failed the same way on `.notice_rules`. Do not ship notification groups as verified examples until provider readback is fixed or the group is imported and a no-op plan is proven.

12. `tls_alarm` requires `alarm_notify_groups`; generated examples use placeholder notification group IDs. Do not include `tls_alarm` until a real notify group is verified.

13. `cloudmonitor_rule` is verified separately in `volcenginecc-cloudmonitor`. Keep it disabled in reusable examples and use `period = "60"`; `1m` and `60s` failed API validation.

14. `tls_shipper` to TOS needs a separately verified TOS bucket. `enable_version_status = "Suspended"` on a new bucket can partially create the bucket and fail with `InvalidBody: The bucket multi-version is not enabled`; use `Enabled` for new buckets.

15. A disabled TOS `tls_shipper` created, but read back as `status = true`, so a no-op plan proposed `true -> false`. Keep shipper out of default examples until provider/API readback is stable.

16. `tls_schedule_sql_task` requires an index on the source topic. The first retry with only source/destination topics failed with `IndexNotExists: Index does not exist.` The verified example creates indexes for both source and destination topics before the task.

17. Keep the scheduled SQL example disabled with `status = 0` and use a bounded `process_end_time` for validation. This avoids creating a continuously running analysis job.

18. `tls_import_task` TOS source was verified with a separately created TOS bucket, `source_type = "tos"`, `compress_type = "none"`, and a JSON target parser. The source prefix can be empty/nonexistent for lifecycle validation; task statistics stayed at zero records.

19. Do not set `status` on `tls_import_task` in the default example. `status = 4` planned and applied, but read back as `0`, causing a follow-up diff. Omitting `status` produced a clean no-op plan.

20. `tls_import_task` destroy completed cleanly, but the dependent `tos_bucket` destroy can hit the known stale waiter pattern. In verification, `tosutil stat tos://cc-iac-tls-import-05300752 -e=tos-cn-beijing.volces.com -re=cn-beijing` returned 404 while Terraform was still waiting after 5m. Only remove a temporary state entry after independently proving the bucket is gone.

## Import IDs

```bash
terraform import volcenginecc_tls_project.main <project-id>
terraform import volcenginecc_tls_topic.app <topic-id>
terraform import volcenginecc_tls_index.app <topic-id>
terraform import volcenginecc_tls_rule.host_file <rule-id>
terraform import volcenginecc_tls_consumer_group.app <project-id>|<consumer-group-name>
terraform import volcenginecc_tls_schedule_sql_task.main <task-id>
terraform import volcenginecc_tls_import_task.tos <task-id>
terraform import volcenginecc_tls_alarm_notify_group.webhook <alarm-notify-group-id>
terraform import volcenginecc_tls_alarm.errors <alarm-id>
```
