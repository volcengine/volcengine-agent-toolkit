# Volcenginecc EBS Snapshot Group Example

Verified example path:

```text
assets/examples/volcenginecc-ebs-snapshot-group/main.tf
```

Use this example when a deployment needs an EBS snapshot consistency group for an ECS instance volume. The example creates a short-lived ECS instance and snapshots its system volume so the snapshot group can be verified from scratch without an external attached disk prerequisite.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_storageebs_snapshot_group` | Crash-consistent snapshot group for one or more disks attached to the same ECS instance |
| `volcenginecc_ecs_instance` | Temporary source instance whose system volume is snapshotted |
| `volcenginecc_ecs_keypair` | Minimal keypair dependency for the temporary ECS instance |
| `volcenginecc_vpc_vpc`, `volcenginecc_vpc_subnet`, `volcenginecc_vpc_route_table`, `volcenginecc_vpc_security_group` | Minimal network dependency for the temporary ECS instance |

For standalone data disk snapshots, use [`assets/examples/volcenginecc-ebs-snapshot/main.tf`](../assets/examples/volcenginecc-ebs-snapshot/main.tf).

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`, zone `cn-beijing-a`, image `image-z0dpqndnmy8rpzcad9rz`, and instance type `ecs.g4i.large`:

```bash
cd assets/examples/volcenginecc-ebs-snapshot-group
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -detailed-exitcode -input=false
terraform destroy
terraform state list
```

Observed first apply result after removing the invalid snapshot group description: ECS instance `i-<instance-id>`, system volume `vol-<id>`, and snapshot group `sg-<volume-id>` created successfully. A follow-up plan returned `No changes`, and destroy removed all seven resources; final Terraform state was empty.

Observed fresh apply result from an empty state with the final example shape: ECS instance `i-<instance-id>`, system volume `vol-<id>`, and snapshot group `sg-<volume-id>` created successfully. Destroy removed the snapshot group, ECS instance, keypair, security group, route table, subnet, and VPC; final Terraform state was empty.

## Pitfalls found during verification

1. Do not set `description` on `volcenginecc_storageebs_snapshot_group` with provider `0.0.46`. A plain English description failed with:

   ```text
   EventTime: 2026-05-30T10:00:58+08:00
   TaskID: task-<id>
   InvalidRequest: InvalidParameter.Description: The specified description is invalid.
   TypeName: Volcengine::StorageEBS::SnapshotGroup
   Operation: CREATE
   OperationStatus: FAILED
   ```

2. `volcenginecc_storageebs_snapshot_group` requires attached volumes. Standalone `volcenginecc_storageebs_volume` resources in `available` status are not valid snapshot group sources. Multiple `volume_ids` must be attached to the same ECS instance.

3. The fresh apply proved snapshot group create and destroy from an ECS system volume, but the fresh follow-up plan still showed in-place pseudo-diffs on parent `volcenginecc_ecs_instance` and `volcenginecc_vpc_security_group` Optional+Computed fields. The snapshot group itself did not show drift. Treat this example as verified for snapshot group lifecycle, but inspect any parent ECS/security-group diffs before applying them.

4. Snapshot group creation took about 1m26s for a single 20 GiB system volume. Destroy took 11-15s for the snapshot group itself before the ECS/network cleanup.

5. The example uses the ECS system volume to keep prerequisites small. For application data consistency, prefer explicit data disks attached to the same ECS instance and pass those disk IDs in `volume_ids`.

## Import IDs

```bash
terraform import volcenginecc_storageebs_snapshot_group.system sg-xxxxxxxx
```
