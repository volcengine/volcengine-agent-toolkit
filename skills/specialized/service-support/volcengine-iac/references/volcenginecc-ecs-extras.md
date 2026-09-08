# Volcenginecc ECS Extras Example

Verified example path:

```text
assets/examples/volcenginecc-ecs-extras/main.tf
```

Use this example when a Volcengine deployment needs ECS placement controls or an HPC placement primitive without creating an ECS instance. These resources are useful inputs for later ECS launch templates and instance placement.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_ecs_deployment_set` | Hardware-level instance spread for high availability |
| `volcenginecc_ecs_hpc_cluster` | HPC cluster placement container for RDMA/high-performance workloads |

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-ecs-extras
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

Observed apply result: both resources created within seconds. A follow-up plan returned `No changes` after removing the unstable `group_count` field from the deployment set. Destroy removed both resources and final state was empty.

Observed IDs in the verification account:

```text
deployment_set_id = dps-<id>
hpc_cluster_id    = hpcCluster-<id>
```

## Pitfalls found during verification

1. For `strategy = "Availability"`, do not set `group_count`. Setting `group_count = 7` created the deployment set but read back as `0`, causing the next plan to force replacement.

2. `deployment_set_group_number = 1` was accepted with `strategy = "Availability"` and did not drift in the verified no-op plan.

3. `volcenginecc_ecs_hpc_cluster` can be created standalone with `name`, `zone_id`, `description`, `project_name`, and tags. It does not require a VPC or ECS instance for the baseline object.

4. HPC clusters are region/AZ capability dependent. Re-test zone availability before wiring one into a production GPU/RDMA instance launch path.

## Import IDs

```bash
terraform import volcenginecc_ecs_deployment_set.availability dps-xxxxxxxx
terraform import volcenginecc_ecs_hpc_cluster.main hpcCluster-xxxxxxxx
```
