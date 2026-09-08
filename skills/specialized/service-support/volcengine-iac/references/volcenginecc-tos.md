# Volcenginecc TOS Example

Verified example path:

```text
assets/examples/volcenginecc-tos/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed TOS bucket with CORS and default server-side encryption.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_tos_bucket` | Object storage bucket for artifacts, static assets, logs, backups, or Terraform remote state prerequisites |
| `volcenginecc_tos_bucket_cors` | Browser cross-origin access rules for frontend/static asset workflows |
| `volcenginecc_tos_bucket_encryption` | Default server-side encryption for newly uploaded objects |

Inventory, event notification, and realtime log are not part of this verified example. See [`volcenginecc-blocked.md`](./volcenginecc-blocked.md) before using `volcenginecc_tos_bucket_inventory`, `volcenginecc_tos_bucket_notification`, or `volcenginecc_tos_bucket_realtime_log`.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-tos
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

Observed apply result: bucket, CORS, and AES256 bucket encryption created successfully. A follow-up plan returned `No changes`.

Observed outputs:

```text
intranet_endpoint = "tos-cn-beijing.ivolces.com"
extranet_endpoint = "tos-cn-beijing.volces.com"
```

Observed timings in `cn-beijing`: bucket creation took about 1m56s. CORS and encryption completed within seconds after the bucket was ready.

## Pitfalls found during verification

1. Bucket names are globally unique. Replace `local.bucket_name` before applying the example; keep lowercase letters, numbers, and hyphens.

2. The generated provider example includes bucket policy and lifecycle rules. Do not copy those blindly: policy needs real account principals and TRNs, and lifecycle nested set objects must be fully defined to avoid unstable diffs.

3. `volcenginecc_tos_bucket_encryption` works with `sse_algorithm = "AES256"` and no KMS key. Use this for the default example to avoid coupling TOS verification to KMS permissions. Use `sse_algorithm = "kms"` only after a verified `kms_key` TRN is available.

4. CORS rules are `SetNestedAttribute` values. Fully define every nested field used by the provider (`allowed_origins`, `allowed_methods`, `allowed_headers`, `expose_headers`, `max_age_seconds`, `response_vary`) to avoid diff churn.

5. Bucket destroy can delete the cloud resource but keep the Cloud Control provider waiter running. During verification, `tosutil stat tos://<bucket>` returned 404 and Terraform refresh warned `Resource Not Found During Refresh`, but the original destroy was still waiting after 12 minutes. For one-off validation, confirm deletion with `tosutil` or refresh, then remove the stale state entry if needed:

```bash
tosutil stat tos://<bucket> -e=tos-cn-beijing.volces.com -re=cn-beijing -i="$VOLCENGINE_ACCESS_KEY" -k="$VOLCENGINE_SECRET_KEY"
terraform plan -refresh-only -input=false
terraform state rm volcenginecc_tos_bucket.main
```

6. The provider's generic delete timeout is long. Do not assume a stuck TOS destroy will fail quickly; actively verify cloud-side deletion before deciding whether state cleanup is appropriate.

7. `volcenginecc_tos_bucket_inventory` and `volcenginecc_tos_bucket_realtime_log` require real IAM roles trusted by TOS. Default-looking role names such as `TosArchiveTOSInventory` and `TOSLogArchiveTLSRole` failed with `InvalidRole: Role must exist` when the roles were absent.

8. `volcenginecc_tos_bucket_notification` cannot be verified with `notification_rules = []`; Cloud Control returned `NotificationRule not found`. Use a real Kafka, RocketMQ, or veFaaS destination and its required role/TRN.

## Import IDs

```bash
terraform import volcenginecc_tos_bucket.main <bucket-name>
terraform import volcenginecc_tos_bucket_cors.main <bucket-name>
terraform import volcenginecc_tos_bucket_encryption.main <bucket-name>
```
