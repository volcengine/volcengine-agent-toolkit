# Volcenginecc Auto Scaling Example

Lifecycle-verified example path:

```text
assets/examples/volcenginecc-autoscaling/main.tf
```

Use this example when a deployment needs the Auto Scaling control plane for ECS capacity management. It verifies a disabled zero-capacity scaling group, a launch-template-backed scaling configuration, and a lifecycle hook without creating scaled ECS instances.

This is not a clean no-op verified example with provider `volcengine/volcenginecc ~> 0.0.46`. It creates and cleans up successfully, but follow-up plans can show provider readback pseudo-diffs and default Terraform destroy ordering is wrong for an active scaling configuration. Read the pitfalls before applying or destroying it.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_autoscaling_scaling_group` | Scaling boundary for ECS instances, subnets, cooldown, min/max/desired counts, and launch template binding |
| `volcenginecc_autoscaling_scaling_configuration` | ECS instance shape used by the scaling group |
| `volcenginecc_autoscaling_scaling_lifecycle_hook` | Hook for scale-out lifecycle actions |
| `volcenginecc_autoscaling_scaling_policy` | Scheduled scaling rule (disabled, one-off near-future launch time) |
| `volcenginecc_ecs_launch_template` | Required by the Cloud Control scaling group create path even though generated docs mark it optional |
| `volcenginecc_ecs_keypair`, `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table`, `volcenginecc_vpc_security_group` | Minimal dependencies for launch template and scaling configuration |

`volcenginecc_autoscaling_scaling_policy` (scheduled) is included. It creates and reaches a clean self no-op with a near-future `launch_time` and `is_enabled_policy = false`. Provide `scheduled_launch_time` as a UTC `YYYY-MM-DDTHH:MMZ` value a few days out.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`, image `image-z0dpqndnmy8rpzcad9rz`, and instance type `ecs.g4i.large`:

```bash
cd assets/examples/volcenginecc-autoscaling
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -detailed-exitcode -input=false
```

Observed successful create path:

```text
VPC: vpc-<id>
Subnet: subnet-<id>
Route table: vtb-<id>
Security group: sg-<id>
Keypair: cc-iac-as-key
Launch template: lt-<id>
Scaling group: scg-<id>
Scaling configuration: scc-<id>
Lifecycle hook: sgh-<id>
```

The first full create/destroy run removed all nine resources with `Destroy complete! Resources: 9 destroyed.` and final Terraform state was empty.

A later policy retry created another group/config/hook set and confirmed cleanup behavior. Group `scg-<id>` and configuration `scc-<id>` were deleted, `ve autoscaling DescribeScalingGroups --ScalingGroupIds.1 scg-<id>` returned `TotalCount: 0`, `ve autoscaling DescribeScalingConfigurations --ScalingConfigurationIds.1 scc-<id>` returned `TotalCount: 0`, and final Terraform state was empty.

## Pitfalls found during verification

1. `launch_template_id` is effectively required for `volcenginecc_autoscaling_scaling_group` in the current Cloud Control path. Creating a scaling group without it failed even though generated docs mark it optional:

   ```text
   EventTime: 2026-05-30T10:14:57+08:00
   TaskID: task-<id>
   MissingParameter.LaunchTemplateId
   TypeName: Volcengine::AutoScaling::ScalingGroup
   Operation: CREATE
   OperationStatus: FAILED
   ```

2. The launch template used by Auto Scaling must include `launch_template_version.volumes`. Omitting it failed with:

   ```text
   EventTime: 2026-05-30T10:15:37+08:00
   TaskID: task-<id>
   MissingParameter.LaunchTemplateVolumes
   TypeName: Volcengine::ECS::LaunchTemplate
   Operation: CREATE
   OperationStatus: FAILED
   ```

3. `volcenginecc_autoscaling_scaling_policy` scheduled rules need a near-future `launch_time`; the time window, not the format, is the constraint. A far-future time fails:

   ```text
   launch_time = "2030-01-01T00:00Z"
   InvalidScheduledPolicyLaunchTime.Malformed
   ```

   A near-future UTC `YYYY-MM-DDTHH:MMZ` value (a few days out) with `is_enabled_policy = false` creates successfully and reaches a clean self no-op. Use the `scheduled_launch_time` variable.

4. A follow-up plan after create can show pseudo-diffs. Observed diffs included `volcenginecc_autoscaling_scaling_configuration` computed `eip`/`password`, `volcenginecc_autoscaling_scaling_group` readback of `launch_template_id = ""` and `launch_template_version = ""`, and an extra default egress rule on `volcenginecc_vpc_security_group`. Do not auto-apply these diffs without inspecting them.

5. Default Terraform destroy ordering can fail after `volcenginecc_autoscaling_scaling_configuration` becomes the group's active scaling configuration. Terraform tries to delete the configuration before the group, and the API rejects it:

   ```text
   EventTime: 2026-05-30T10:24:48+08:00
   TaskID: task-<id>
   InvalidScalingConfiguration.InUse: The specified ScalingConfiguration [scc-<id>] is in use.
   TypeName: Volcengine::AutoScaling::ScalingConfiguration
   Operation: DELETE
   OperationStatus: FAILED
   ```

   Recovery sequence used during verification:

   ```bash
   terraform state rm volcenginecc_autoscaling_scaling_configuration.app
   terraform destroy -target=volcenginecc_autoscaling_scaling_group.app -auto-approve -input=false
   ve autoscaling DescribeScalingConfigurations --ScalingConfigurationIds.1 <scaling_configuration_id>
   terraform destroy -auto-approve -input=false
   terraform state list
   ```

   Deleting the scaling group cascaded the active scaling configuration in the verified run. Confirm with `DescribeScalingConfigurations` before removing the rest of the stack.

6. Keep `min_instance_number = 0`, `max_instance_number = 0`, `desire_instance_number = 0`, and `is_enable_scaling_group = false` for low-cost validation. Raising desired capacity will create ECS instances and needs additional cleanup and health checks.

## Import IDs

```bash
terraform import volcenginecc_autoscaling_scaling_group.example scg-xxxxxxxx
terraform import volcenginecc_autoscaling_scaling_configuration.example scc-xxxxxxxx
terraform import volcenginecc_autoscaling_scaling_lifecycle_hook.example "scg-xxxxxxxx|sgh-xxxxxxxx"
terraform import volcenginecc_autoscaling_scaling_policy.example "scg-xxxxxxxx|sp-xxxxxxxx"
```
