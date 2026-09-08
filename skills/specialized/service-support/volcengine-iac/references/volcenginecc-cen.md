# Volcenginecc CEN Example

Verified example path:

```text
assets/examples/volcenginecc-cen/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed Cloud Enterprise Network with a VPC attachment for cross-VPC, cross-region, or hybrid-network expansion.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_cen_cen` | CEN instance with a VPC network-instance attachment |
| `volcenginecc_vpc_vpc` | Disposable VPC attachment target for the verified baseline |

## Not in the default example

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_cen_bandwidth_package` | Not applied | Creates billable inter-region bandwidth; verify only with an explicit bandwidth requirement. |
| `volcenginecc_cen_inter_region_bandwidth` | Dependency/billable blocked | Requires a CEN bandwidth package and a deliberate inter-region path. |
| `volcenginecc_cen_route_entry` | Dependency-blocked | Requires a verified target network instance and route design. |
| `volcenginecc_cen_service_route_entry` | Dependency-blocked | Requires a service VPC route target. |
| `volcenginecc_cen_grant_instance` | Cross-account blocked | Requires another account's CEN ID and owner ID. |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-cen
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_account_id=<account-id>
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -detailed-exitcode -input=false
terraform destroy -auto-approve -input=false
terraform state list
```

Observed timings in `cn-beijing`: VPC create took about 7 seconds, CEN create took about 28 seconds, CEN destroy took about 11 seconds, and VPC destroy took about 10 seconds.

## Pitfalls found during verification

1. `cen:CreateCen` permission is required. Earlier attempts failed at the permission boundary after the temporary VPC had already been created.

2. `instances.instance_owner_id` is required for a VPC attachment. Pass it through `TF_VAR_account_id`; do not hardcode an account ID into reusable examples.

3. Keep the baseline untagged with provider `0.0.46` unless tags are required. Several generated `volcenginecc` tag schemas have Optional+Computed readback quirks; this verified shape produced a clean no-op without tags.

4. Destroy order matters. Delete the CEN before the attached VPC; Terraform handled this correctly when the VPC ID was referenced inside `instances`.

## Import IDs

```bash
terraform import volcenginecc_cen_cen.main <cen-id>
```
