# VKE Private CR Nginx Run

This reference records the real IaC run for creating a CR repository, pushing the official nginx image, and deploying it to VKE. It is intentionally about the non-obvious parts only.

Example path:

```text
assets/examples/volcengine-vke-cr-nginx/
```

## Verified Run

The run was executed in `cn-beijing` with:

- VKE cluster: `cd8eftab7q4mm67qeep8g`
- CR registry: `iac-vke-nginx-demo`
- CR endpoint: `iac-vke-nginx-demo-cn-beijing.cr.volces.com`
- Repository URI: `iac-vke-nginx-demo-cn-beijing.cr.volces.com/app/nginx`
- Final deployed image: `.../app/nginx:official-nginx-1.27-amd64`

Observed workload result:

```text
deployment.apps/nginx   1/1   1   1
pod/nginx-...           1/1   Running   0
deployment "nginx" successfully rolled out
```

The nginx pod pulled from private CR with an explicit `imagePullSecret` and returned the default nginx welcome page through `kubectl exec deploy/nginx -- wget -qO- http://127.0.0.1/`. The `cr-credential-controller` addon was installed and running, but secretless injection was not isolated in this run.

## Commands

Apply infra:

```bash
cd assets/examples/volcengine-vke-cr-nginx/infra
export VOLCENGINE_ACCESS_KEY=...
export VOLCENGINE_SECRET_KEY=...
export VOLCENGINE_REGION=cn-beijing
export TF_VAR_node_password_base64="$(printf '%s' 'use-a-real-node-password' | base64)"
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
terraform output -raw kubeconfig | base64 -d > ../kubeconfig.yaml
```

Apply workload:

```bash
cd ../workload
export TF_VAR_kubeconfig_path="$(cd .. && pwd)/kubeconfig.yaml"
export TF_VAR_registry_endpoint="$(cd ../infra && terraform output -raw registry_endpoint)"
export TF_VAR_repository_uri="$(cd ../infra && terraform output -raw repository_uri)"
export TF_VAR_cr_username="$(cd ../infra && terraform output -raw cr_username)"
export TF_VAR_cr_token="$(cd ../infra && terraform output -raw cr_token)"
# Optional: expose nginx publicly for manual verification.
# export TF_VAR_service_type=LoadBalancer
terraform init -backend=false -input=false
terraform validate
terraform plan -out=tfplan.binary -input=false
terraform apply -input=false tfplan.binary
KUBECONFIG=../kubeconfig.yaml kubectl -n iac-nginx rollout status deploy/nginx
KUBECONFIG=../kubeconfig.yaml kubectl -n iac-nginx get svc nginx
KUBECONFIG=../kubeconfig.yaml kubectl -n iac-nginx exec deploy/nginx -- wget -qO- http://127.0.0.1/ | sed -n '1,8p'
```

Destroy workload before infra:

```bash
cd assets/examples/volcengine-vke-cr-nginx/workload
terraform destroy -input=false -auto-approve
```

If `manage_core_dns_addon = true`, remove `core-dns` from state before destroying infra. VKE rejects direct deletion of this required addon, but deletes it with the cluster:

```bash
cd ../infra
terraform state rm 'volcenginecc_vke_addon.core_dns[0]'
terraform destroy -input=false -auto-approve
```

## Pitfalls

1. VKE cluster creation is long-running. In the verified runs, the control plane stayed in Terraform `Still creating...` for several minutes and completed at about 9 minutes. Treat that as normal unless the cloud-side status reports an error.

2. `core-dns` is required for normal Kubernetes service discovery. In the verified run it needed enough worker CPU: default `core-dns` requested `2 CPU / 4Gi` per pod with two replicas, and an `ecs.g4i.large` node only had `1900m` allocatable CPU. Adding one `ecs.g4i.2xlarge` node pool let `core-dns` become `2/2 Running`.

3. `core-dns` cannot be destroyed as a standalone VKE addon. Cloud Control returned `OperationDenied.RequiredAddon`. Keep it out of Terraform state for clean destroy, or run `terraform state rm 'volcenginecc_vke_addon.core_dns[0]'` before cluster destroy.

4. `cr-credential-controller` is the VKE addon that removes the need to put CR pull passwords in every workload. Empty config failed with `InvalidParameter.Config`; the working shape was:

```hcl
config = jsonencode({
  CrConfigmapData = {
    Namespace      = "*"
    ServiceAccount = "*"
    Registries = [{
      Instance = volcengine_cr_registry.main.name
      Region   = var.region
      Domains  = [local.registry_endpoint]
    }]
  }
})
```

5. VKE ECS nodes in this example are `linux/amd64`; the nginx image pushed to CR must also be `linux/amd64`. Do not trust the local Docker tag on Apple Silicon. The first push used local `nginx:1.27-alpine` as `linux/arm64`, and the VKE amd64 node failed with `exec /docker-entrypoint.sh: exec format error`. The workload example removes the local tag, pulls `--platform linux/amd64`, checks `docker image inspect`, then pushes.

6. The Terraform Docker provider's `docker_image.platform` still reused the existing local arm64 tag in the failed run. For this copy-from-Docker-Hub case, the verified path uses Terraform `null_resource` plus Docker CLI so the platform check is explicit.

7. CR authorization tokens expire quickly. If Docker push fails after the infra has been up for a while, refresh the data source and re-export the token:

```bash
cd infra
terraform apply -refresh-only -input=false -auto-approve
cd ../workload
export TF_VAR_cr_token="$(cd ../infra && terraform output -raw cr_token)"
```

8. Cloud Control VKE kubeconfig creation hit a transient `GetTask` connection reset during the run. The legacy `volcengine_vke_kubeconfig` resource created a public kubeconfig successfully in about 5 seconds.

9. Cloud Control VKE node pools with a nonzero desired size worked with `enabled = true`, `min_replicas = 0`, `desired_replicas = 1`, `max_replicas = 1`. The earlier `min = 1`, `desired = 1`, `max = 1` shape failed with `Mismatch.Replicas`.

10. The workload example defaults to the verified explicit `imagePullSecret` path. To validate the `cr-credential-controller` passwordless path, set `use_explicit_image_pull_secret = false` only after confirming the addon is `Running` and its config covers the target namespace, service account, registry instance, region, and domain.
