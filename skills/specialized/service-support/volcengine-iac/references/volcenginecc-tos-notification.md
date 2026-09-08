# Volcenginecc TOS Notification Example

Verified example path:

```text
assets/examples/volcenginecc-tos-notification/main.tf
```

Use this example when a deployment needs TOS object event notifications delivered to a veFaaS function. The example creates a bucket, a small ZIP-based veFaaS function, releases the function, and configures `tos:ObjectCreated:Put` events with a prefix filter.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_tos_bucket_notification` | Bucket event notification rules |
| `volcenginecc_tos_bucket` | Source bucket for object events |
| `volcenginecc_vefaas_function` | Notification delivery target |
| `volcenginecc_vefaas_release` | Required released function revision before TOS can bind the target |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-tos-notification
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy -auto-approve -input=false
terraform state list
```

Observed apply result: bucket `cc-iac-tos-noti-current`, veFaaS function `4cjgrs2l`, release record `ybfg6a9met7gd111`, and bucket notification `cc-iac-tos-noti-current` created successfully. A follow-up plan returned `No changes`.

Cleanup evidence: `volcenginecc_tos_bucket_notification` deleted successfully. The bucket delete operation removed the bucket in TOS, confirmed by `tosutil stat` returning HTTP 404, but the Cloud Control waiter kept polling for over 23 minutes; after the 404, the bucket was removed from Terraform state. Finished veFaaS releases cannot be deleted by Cloud Control (`release already in final status: finished`), so the release was removed from state before destroying the function. The function then destroyed successfully and final Terraform state was empty.

## Pitfalls found during verification

1. A veFaaS notification target must be released first. Binding notification directly to a newly created but unreleased function failed with:

```text
InvalidArgument: faas function has not been fully released yet, please release it first
TypeName: Volcengine::TOS::BucketNotification
TaskID: task-<id>
```

2. Do not use `notification_rules = []` as a baseline. TOS rejects empty notification configuration with `NotificationRule not found`.

3. For veFaaS destinations, set `depends_on = [volcenginecc_vefaas_release.target]` on the notification resource. The function ID alone is not enough to express the readiness dependency.

4. TOS bucket deletion can finish cloud-side while the Cloud Control Terraform waiter keeps polling. Before removing state, verify the bucket is gone with `tosutil stat tos://<bucket> -e=tos-cn-beijing.volces.com -re=cn-beijing` and require HTTP 404 evidence.

5. Finished `volcenginecc_vefaas_release` resources are operational records. If destroy fails with `release already in final status: finished`, remove only the release record from Terraform state, then destroy the function.

6. The inline function ZIP must be valid base64. A single copied character error failed function creation with `InvalidParameter: The specified parameter failed to do base64 decode`.

## Import IDs

```bash
terraform import volcenginecc_tos_bucket_notification.main <bucket-name>
terraform import volcenginecc_tos_bucket.main <bucket-name>
terraform import volcenginecc_vefaas_function.target <function-id>
terraform import volcenginecc_vefaas_release.target <function-id>
```
