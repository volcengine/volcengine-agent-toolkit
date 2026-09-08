# Volcenginecc ECS Launch Template Version Example

Verified example path:

```text
assets/examples/volcenginecc-ecs-launch-template-version/main.tf
```

Use this example when a Volcengine deployment needs to add a standalone ECS launch template version to an existing launch template. The example includes a minimal VPC, subnet, route table, security group, and launch template so it can be verified independently.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_ecs_launch_template` | Base ECS launch template that owns version 1 |
| `volcenginecc_ecs_launch_template_version` | Additional launch template version for image/type/user-data changes |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`, image `image-z0dpqndnmy8rpzcad9rz`, and instance type `ecs.g4i.large`:

```bash
cd assets/examples/volcenginecc-ecs-launch-template-version
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform apply
terraform plan -detailed-exitcode -input=false
terraform destroy
```

Observed apply result: VPC, subnet, route table, security group, launch template, and launch template version created successfully. The standalone version number was `2`. After one security group convergence apply and removing the empty ingress set from the example, a follow-up plan returned `No changes`. Destroy removed all 6 resources and final state was empty.

Observed IDs in the verification account:

```text
launch_template_id             = lt-<template-id>
launch_template_version_number = 2
```

## Pitfalls found during verification

1. Do not set `ingress_permissions = []` on `volcenginecc_vpc_security_group`. The provider reads the omitted empty set differently from an explicitly configured empty set, causing an endless in-place diff.

2. A newly created security group can read back a default egress rule once. If the desired egress rule differs, run a convergence apply and verify the next plan is clean.

3. `user_data` must be Base64-encoded. The verified values decode to simple shell echo commands and do not contain secrets.

4. Keep `volumes`, `eip`, `scheduled_instance`, deployment set IDs, and HPC cluster IDs out of the baseline version example unless those dependencies are explicitly needed and re-verified. The generated docs include many optional nested fields that read back with provider defaults.

5. `ecs_launch_template_version` needs a real `launch_template_id`. Use `volcenginecc_ecs_launch_template.main.launch_template_id` or import an existing launch template before adding versions.

## Import IDs

```bash
terraform import volcenginecc_ecs_launch_template.main lt-xxxxxxxx
terraform import volcenginecc_ecs_launch_template_version.second 'lt-xxxxxxxx|2'
```
