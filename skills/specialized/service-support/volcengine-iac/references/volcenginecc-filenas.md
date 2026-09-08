# Volcenginecc FileNAS Example

Verified example path:

```text
assets/examples/volcenginecc-filenas/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed NFS file system for shared application files, VKE/ECS shared storage, or persistent artifacts.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_filenas_instance` | Managed FileNAS NFS file system |

## Not in the default example

| Resource | Status | Reason |
|---|---|---|
| `volcenginecc_filenas_snapshot` | Create/delete verified, but not no-op clean | Provider `0.0.46` repeatedly plans `retention_days` changes because the generated schema marks it read-only while also setting a default. |
| `volcenginecc_filenas_mount_point` | Dependency-blocked | Requires a `permission_group_id`; provider `0.0.46` has no `volcenginecc` permission group resource. Use an existing permission group or create it outside Terraform before managing mount points. |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-filenas
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy -input=false -auto-approve
terraform state list
```

Observed apply result: one `volcenginecc_filenas_instance` was created successfully in `cn-beijing-a` with `file_system_type = "Extreme"`, `protocol_type = "NFS"`, `storage_type = "Standard"`, and `capacity.total = 105`. A follow-up plan returned `No changes`. Destroy removed the file system and final state was empty.

Observed timings in `cn-beijing`: FileNAS instance create took about 29 seconds. Destroy took about 28 seconds.

## Pitfalls found during verification

1. `ve filenas DescribeZones` uses `Status = "OnSale"` for usable SKUs. `Status = "UnSold"` means not for sale, not "not sold out". A first `Capacity/NFS/Standard` attempt in `cn-beijing-a` failed with `InvalidSaleStatus.NotSale`.

2. The verified baseline is `file_system_type = "Extreme"`, `protocol_type = "NFS"`, `storage_type = "Standard"`, `zone_id = "cn-beijing-a"`, and `capacity.total = 105`.

3. Avoid `tags` in the FileNAS example with provider `0.0.46`. Supplying `type = "Custom"` caused a one-time tag update because readback omitted `type`; omitting tags produced a clean no-op plan.

4. `volcenginecc_filenas_snapshot` can create and delete, but it is not cleanly no-op in provider `0.0.46`. After creation, plans repeatedly showed `retention_days = -1 -> 2147483647` because the generated schema defines `retention_days` as computed/read-only and also sets a default.

5. `volcenginecc_filenas_mount_point` cannot be a from-scratch `volcenginecc` example yet because it requires `permission_group_id` and this provider version does not expose a FileNAS permission group resource. The `ve filenas CreatePermissionGroup` API exists, but mixing a CLI-created prerequisite into a verified Terraform-only example would hide an unmanaged dependency.

## Import IDs

```bash
terraform import volcenginecc_filenas_instance.main <file-system-id>
terraform import volcenginecc_filenas_snapshot.manual <snapshot-id>
terraform import volcenginecc_filenas_mount_point.app <file-system-id>|<mount-point-id>
```
