# Volcenginecc RDS SQL Server Example

Lifecycle-verified example path:

```text
assets/examples/volcenginecc-rdsmssql/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed SQL Server Basic instance and private CIDR allowlist. Creation and clean no-op planning are verified; destroy has a documented RDS backend release caveat and must not be treated as clean-verified until the service-managed security group release path converges reliably. A 2026-05-31 retry with the 60s destroy delay still left a service-managed MSSQL security group after the instance, allowlist, route table, subnet, and ENIs were gone.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_rdsmssql_instance` | Managed SQL Server instance for application state |
| `volcenginecc_rdsmssql_allow_list` | Private CIDR allowlist for database access |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table` | Minimal network dependency for the instance |
| `time_sleep` | Fixed 60s create/destroy delay between network readiness and SQL Server lifecycle |

## Verified command sequence

The example shape was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-rdsmssql
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_mssql_password=...
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy -input=false
```

Observed apply result: VPC, subnet, route table, allowlist, and Basic SQL Server 2019 Standard instance created successfully. A follow-up `terraform plan -detailed-exitcode` returned `No changes`.

Observed timings in `cn-beijing`: SQL Server instance create took 4m37s in the first successful run and 4m45s in the 2026-05-31 retry. Instance delete returned success after 10-12s, but backend cleanup continued after the Terraform delete operation returned.

## Why the example includes `time_sleep`

Terraform HCL cannot express a real `while` loop that polls cloud state during apply or destroy. The portable Terraform pattern is a fixed wait using the `hashicorp/time` provider:

```hcl
resource "time_sleep" "network_release_delay" {
  depends_on = [
    volcenginecc_rdsmssql_allow_list.app,
    volcenginecc_vpc_route_table.main,
  ]

  create_duration  = "60s"
  destroy_duration = "60s"
}

resource "volcenginecc_rdsmssql_instance" "main" {
  # ...
  depends_on = [time_sleep.network_release_delay]
}
```

This dependency shape does two things:

1. On create, Terraform waits 60s after the VPC/subnet/route table and allowlist are created before creating the SQL Server instance. This avoids the RDS MSSQL `VpcIDNotFound` consistency window seen in earlier retries.
2. On destroy, Terraform deletes the SQL Server instance first, then destroys `time_sleep` and waits 60s before removing the allowlist, route table, subnet, and VPC. This gives RDS time to detach ENIs and allowlist associations.

The fixed delay is not a guarantee. The 2026-05-31 retry proved that the delay is enough for the allowlist, custom route table, and subnet in that run, but VPC deletion still failed because the service-managed MSSQL security group remained. If the service-managed security group remains after 60s, rerun `terraform destroy` after the cloud-side checks below and keep the temporary state if VPC deletion still fails.

## Pitfalls found during verification

1. `rds.mssql.3il.x8.medium.s1` in `cn-beijing-a` supports `SQLServer_2019_Std`, `Basic`, and `storage_space = 20`. Earlier failures were permission or consistency issues, not a zone/spec mismatch.

2. `super_account_password` is sensitive in plan output but still stored in Terraform state. Pass it through `TF_VAR_mssql_password` or a secure variable source, and never commit state or binary plan files.

3. `user_allow_list` is a string field for SQL Server allowlists. Use a single CIDR string or comma-separated CIDRs, not a Terraform list.

4. Destroy can return before RDS has fully released dependent resources. In the verified runs, the instance disappeared from `DescribeDBInstances`, ENIs dropped to zero, and the allowlist was deleted, but the VPC was still blocked by an RDS service-managed security group named `sg-for-<vpc-id>` with description `Mssql Managed Security Group`.

5. Do not manually delete the RDS service-managed security group. The VPC API rejects it with `Forbidden` / `The specified security group is a service-managed security group.`

6. If VPC deletion fails with `InvalidVpc.InUse` and the only dependency is the RDS service-managed security group, wait and retry destroy. The 2026-05-31 retry still failed after an extra 60s wait, so treat repeated failures as a service-side cleanup issue rather than a Terraform graph issue. Keep the temporary Terraform state until cleanup completes.

## Destroy cleanup SOP

When destroy fails after the SQL Server instance delete, poll cloud-side state every 60 seconds:

```bash
while true; do
  ve rdsmssql DescribeDBInstances --body '{"InstanceName":"<instance-name>","PageNumber":1,"PageSize":10}'
  ve vpc DescribeNetworkInterfaces --VpcId <vpc-id>
  ve rdsmssql DescribeAllowLists --body '{"AllowListName":"<allow-list-name>","PageNumber":1,"PageSize":10}'
  ve vpc DescribeSecurityGroups --VpcId <vpc-id>
  sleep 60
done
```

Proceed when:

- `DescribeDBInstances` returns `Total: 0`
- `DescribeNetworkInterfaces` returns `TotalCount: 0`
- the allowlist has `AssociatedInstanceNum = 0` or has already been deleted
- no service-managed `Mssql Managed Security Group` remains in the VPC

Then rerun:

```bash
terraform destroy -input=false
```

If only the service-managed security group remains for more than several minutes, keep the state directory and record the VPC/security-group IDs in `references/volcenginecc-blocked.md`.

## Import IDs

```bash
terraform import volcenginecc_rdsmssql_allow_list.app <allow-list-id>
terraform import volcenginecc_rdsmssql_instance.main <instance-id>
```
