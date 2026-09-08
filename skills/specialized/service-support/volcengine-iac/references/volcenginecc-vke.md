# Volcenginecc VKE Example

Verified example path:

```text
assets/examples/volcenginecc-vke/main.tf
```

Use this example when a Volcengine deployment needs a Terraform-managed VKE control plane, private kubeconfig, a zero-replica custom node pool definition, the default node pool, and a non-default managed addon. The custom node pool is intentionally configured with `desired_replicas = 0` so the example validates node pool IaC without creating worker ECS instances by default.

## Covered resources

| Resource | Deployment use |
|---|---|
| `volcenginecc_vke_cluster` | Managed Kubernetes control plane |
| `volcenginecc_vke_node_pool` | Node pool template for later worker scale-out |
| `volcenginecc_vke_default_node_pool` | Default node pool used when importing existing ECS instances |
| `volcenginecc_vke_addon` | Optional cluster addon managed outside the cluster's auto-installed defaults |
| `volcenginecc_vke_kubeconfig` | Short-lived private kubeconfig for cluster administration |

The example includes a minimal VPC, two subnets, and route table so it can be validated independently. In real deployments, wire VKE to the verified network foundation instead of creating a separate VPC.

## Verified command sequence

The example was verified in `cn-beijing` with provider `volcengine/volcenginecc ~> 0.0.46`:

```bash
cd assets/examples/volcenginecc-vke
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_node_password_base64="$(printf '%s' 'use-a-real-node-password' | base64)"
terraform fmt -check
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform plan -out=tfplan-noop.binary -input=false
terraform destroy
```

Observed apply result: VPC, two subnets, route table, VKE cluster, private kubeconfig, zero-replica custom node pool, default node pool, and managed `pod-identity-webhook` addon created successfully. A follow-up plan returned `No changes`. Destroy removed all resources and final state was empty.

Observed timings in `cn-beijing`: VKE cluster creation took about 9m7s-9m8s, kubeconfig creation about 16s, zero-replica node pool creation about 2m36s, default node pool creation about 15s, `pod-identity-webhook` addon creation about 5m26s, addon deletion about 5m17s, custom node pool deletion about 36s, and cluster deletion about 1m5s.

## Verified spec

The verified VKE spec is:

```hcl
kubernetes_version_create = "1.30"
pod_network_mode          = "Flannel"
pod_cidrs                 = ["172.20.0.0/16"]
service_cidrsv_4          = ["172.21.0.0/20"]
api_server_public_access  = false
```

The verified zero-replica node pool spec is:

```hcl
auto_scaling = {
  enabled          = false
  min_replicas     = 0
  max_replicas     = 1
  desired_replicas = 0
}

node_config = {
  instance_charge_type  = "PostPaid"
  image_id              = "image-yd6lmt386vgqef1r7xpu" # veLinux 2.0 64 bit
  instance_type_ids     = ["ecs.g4i.large"]
  public_access_enabled = false
}
```

The verified image came from:

```bash
ve vke ListSupportedImages --body '{"InstanceTypeIds":["ecs.g4i.large"],"KubernetesVersion":"1.30"}'
```

The verified addon came from:

```bash
ve vke ListSupportedAddons --body '{"Filter":{"PodNetworkModes":["Flannel"],"Versions.Compatibilities.KubernetesVersions":["1.30"]}}'
```

The committed addon uses `name = "pod-identity-webhook"`, `version = "v0.1.1"`, and `deploy_mode = "Managed"` because it is an on-demand managed addon that can run on a zero-worker cluster.

## Pitfalls found during verification

1. VKE cluster creation is long-running. The verified no-node cluster took about 9 minutes; do not assume Terraform is hung while the resource reports `Still creating`.

2. `vke_node_pool` requires `node_config` even when `desired_replicas = 0`. An omitted `node_config` failed with `MissingParameter.NodeConfig`.

3. An empty `node_config = {}` is treated as missing by Cloud Control. Include at least real node config fields.

4. `node_config.security.login` is required even for a zero-replica node pool. A config without it failed with `MissingParameter.NodeConfig.Security.Login`.

5. `auto_scaling.max_replicas = 0` is invalid. Use `min_replicas = 0`, `desired_replicas = 0`, and `max_replicas = 1` to create a zero-worker node pool template.

6. Node pool passwords are sensitive in Terraform output, but Terraform state still stores sensitive values. Do not commit `terraform.tfstate*`; delete throwaway verification directories after destroy.

7. `vke_kubeconfig.kubeconfig` is a base64 string in state and includes credentials. Treat it as a secret and prefer short `valid_duration` values for examples.

8. `vke_cluster.cluster_config.security_group_ids` is computed after cluster creation. Use it for node pool security groups instead of hardcoding temporary security group IDs.

9. The cluster auto-installs required addons such as managed `alb-ingress-controller`, managed `cloud-controller-manager`, and unmanaged `flannel`. Do not point `volcenginecc_vke_addon` at an already auto-installed required addon; use a deliberate on-demand addon such as `pod-identity-webhook`.

10. `volcenginecc_vke_addon` can take several minutes even after the addon is visible as `Running` from `ve vke ListAddons`. During verification, Terraform waited 5m26s on create and 5m17s on delete.

11. For real workload clusters, confirm addon intent separately from the minimal verification addon: `core-dns` is required for in-cluster DNS/service discovery, and `cr-credential-controller` avoids storing Volcengine CR image-pull passwords in workload manifests. The verified example used `pod-identity-webhook`; it did not lifecycle-test these two addons.

12. `volcenginecc_vke_default_node_pool` can be created on a zero-worker cluster, but it still needs `node_config.security.login` and should reuse `vke_cluster.cluster_config.security_group_ids`.

13. `volcenginecc_vke_node` is still dependency-bound. It adds an existing ECS instance to a node pool and was not included in this example because the verified path deliberately avoids creating worker ECS instances.

## Import IDs

```bash
terraform import volcenginecc_vke_cluster.main <cluster-id>
terraform import volcenginecc_vke_node_pool.zero <cluster-id>|<node-pool-id>
terraform import volcenginecc_vke_default_node_pool.default <cluster-id>|<node-pool-id>
terraform import volcenginecc_vke_addon.pod_identity_webhook <cluster-id>|pod-identity-webhook
terraform import volcenginecc_vke_kubeconfig.private <cluster-id>|<kubeconfig-id>
```
