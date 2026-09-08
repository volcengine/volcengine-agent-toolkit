# Volcenginecc EFS Example

Verified example path:

```text
assets/examples/volcenginecc-efs/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed EFS file system for shared datasets, application artifacts, or multi-node file access.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_efs_file_system` | Managed EFS file system |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-efs
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
terraform state list
```

Observed apply result: EFS file system `cc-iac-efs-retry` created successfully in `cn-beijing-a` with ID `efs-<efs-id>`, `instance_type = "Premium"`, `performance_density = "Premium_125"`, `bandwidth_mode = "Provisioned"`, and `provisioned_bandwidth = 300`. A follow-up plan returned `No changes`. Destroy removed the file system, final Terraform state was empty, and `ve efs DescribeFileSystems --body '{"FileSystemName":"cc-iac-efs-retry"}'` returned `TotalCount: 0`.

Observed timings in `cn-beijing`: EFS file system create took about 16 seconds. Destroy took about 15 seconds.

## Pitfalls found during verification

1. `efs:CreateFileSystem` permission is required. Earlier attempts failed at the permission boundary before any EFS resource was created.

2. Avoid `tags` in the EFS example with provider `0.0.46` if a clean no-op plan matters. Supplying `type = "Custom"` created successfully but read back without `type`, causing a follow-up diff. Removing the tag block produced a clean no-op plan.

3. Keep `performance.provisioned_bandwidth = 300` with `performance_density = "Premium_125"` for the verified baseline. Lower bandwidth or a different density was not part of this lifecycle verification.

4. The provider reads back `protocol_types = ["FSX", "NFS"]` and storage/charge details as computed fields. Do not copy those read-only fields into resource configuration.

## Import IDs

```bash
terraform import volcenginecc_efs_file_system.main <file-system-id>
```
