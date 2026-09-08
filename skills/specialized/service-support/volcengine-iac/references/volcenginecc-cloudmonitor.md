# Volcenginecc CloudMonitor Example

Verified example path:

```text
assets/examples/volcenginecc-cloudmonitor/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed CloudMonitor alert rule. The shipped rule is disabled and uses a Webhook notification target so the lifecycle can be verified without depending on account-local contact groups.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_cloudmonitor_rule` | CloudMonitor alert policy for ECS CPU monitoring |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-cloudmonitor
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
```

## Pitfalls found during verification

1. `cloudmonitor:CreateRule` permission is required. Earlier attempts failed at the permission boundary before the rule resource was created.

2. A notification route is required even when `enable_state = "disable"`. Creating a rule without a callback or non-empty contact group failed with `InvalidParam.Notification: 通知渠道和回调不能同时为空`.

3. The account default contact group existed but had no contacts. Binding it failed with `ContactGroupMemberEmpty`, so the verified example uses `alert_methods = ["Webhook"]` and a harmless placeholder Webhook URL.

4. The `period` field must use the numeric seconds string accepted by CloudMonitor. `period = "1m"` and `period = "60s"` both failed with `InvalidParam.Period`; `period = "60"` succeeded and produced a clean no-op plan.

5. Keep the reusable example disabled. Change `enable_state` and notification targets only for a real deployment after confirming the monitored namespace, metric, dimensions, and contact policy.

## Import IDs

```bash
terraform import volcenginecc_cloudmonitor_rule.ecs_cpu <rule-id>
```
