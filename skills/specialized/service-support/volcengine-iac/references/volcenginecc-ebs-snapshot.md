# Volcenginecc EBS Snapshot Example

Verified example path:

```text
assets/examples/volcenginecc-ebs-snapshot/main.tf
```

Use this example when a deployment needs Terraform-managed manual snapshots for standalone EBS data disks, such as backup validation, golden data volumes, or pre-migration checkpoints.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_storageebs_volume` | Standalone data disk used as the snapshot source |
| `volcenginecc_storageebs_snapshot` | Manual snapshot of a single data disk |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-ebs-snapshot
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -input=false
terraform destroy
```

Observed timings: volume create about 16s, snapshot create about 2m6s, snapshot destroy about 7s, volume destroy about 1m15s.

## Pitfalls found during verification

1. Snapshot creation waits for the snapshot to become available. Even a 10 GiB empty standalone volume took about two minutes.

2. Keep `volcenginecc_storageebs_volume.description` omitted unless the target region has been re-tested. The ECS example previously found simple descriptions can fail with `InvalidDescriptionFormat`.

3. Use `pay_type = "post"` for the lightweight example. It matches the verified EBS volume settings used by the ECS example.

4. `volcenginecc_storageebs_snapshot_group` is covered by the companion example [`assets/examples/volcenginecc-ebs-snapshot-group/main.tf`](../assets/examples/volcenginecc-ebs-snapshot-group/main.tf). It requires attached disks; standalone data disks in `available` status are not valid snapshot group sources.

## Import IDs

```bash
terraform import volcenginecc_storageebs_volume.data vol-xxxxxxxx
terraform import volcenginecc_storageebs_snapshot.data snap-xxxxxxxx
```
