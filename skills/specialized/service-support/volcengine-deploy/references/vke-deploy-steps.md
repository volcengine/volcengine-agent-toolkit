# VKE Deployment Details

Execution runbook for the VKE branch. The main `SKILL.md` keeps only the control-flow skeleton and hard boundaries; this file carries the command-level pipeline. Template details live in [`k8s-manifests.md`](./k8s-manifests.md) and [`dockerfile-templates.md`](./dockerfile-templates.md); for deeper CLI detail, activate the `volcengine-cli` skill and follow its VKE and CR guidance; a real end-to-end run is in `volcengine-iac/references/volcengine-vke-cr-nginx.md`.

Do not skip steps or reorder them. The most common failures come from running a later step before an earlier one converges (e.g. `kubectl apply` before the kubeconfig exists, or generating a Deployment before the image is pushed).

## Execution pipeline

### 1. Provision or reuse VKE + CR

- `infra_management=iac`: use `volcengine-iac` outputs in `.volcengine/iac-outputs.json` for VPC/subnets/security group, `cluster_id`, CR registry/namespace/repository, and (when present) `kubeconfig_private`.
- CLI fast path: create or reuse VPC/subnet/security group, the VKE cluster + node pool, and a CR registry/namespace/repository, recording every CLI-created resource in `.volcengine/created-resources.json` immediately. Reuse a user-specified cluster/registry when given.

Do not hardcode node instance types. Build the image for the node architecture (default `linux/amd64` unless node-pool data proves otherwise).

### 2. Wait for the cluster, then fetch kubeconfig

Poll the cluster until it is running before any kubeconfig or workload call:

```bash
for _ in $(seq 1 60); do
  phase=$(ve vke ListClusters --body '{"Filter":{"Ids":["'"$cluster_id"'"]}}' \
    | jq -r '.Result.Items[0].Status.Phase // empty')
  [ "$phase" = "Running" ] && break
  sleep 15
done
[ "$phase" = "Running" ] || { echo "cluster not Running: $phase" >&2; exit 1; }
```

Then read kubeconfig from `.volcengine/iac-outputs.json` when present, otherwise create one:

```bash
ve vke CreateKubeconfig --ClusterId "$cluster_id" --Type Public
# Decode the returned Kubeconfig (base64) to a file and export KUBECONFIG.
```

`CreateKubeconfig` before the cluster is `Running` returns `OperationDenied` — that is why the poll above must succeed first. Use `--Type Private` only when the agent runs inside the VPC.

### 3. Verify addons

```bash
ve vke ListAddons --body '{"Filter":{"ClusterIds":["'"$cluster_id"'"]}}' \
  | jq -r '.Result.Items[].Name'
```

- `core-dns` must be present, or in-cluster service-name resolution fails. Install/repair it before relying on cluster DNS.
- Prefer `cr-credential-controller` for private CR image pulls. If it is absent, either install it or create an `imagePullSecret` from the CR token instead of hardcoding registry passwords into app manifests.

### 4. Build the image for the node architecture

Build with an explicit platform matching the nodes; do not trust the local Docker default on arm64 machines. See [`dockerfile-templates.md`](./dockerfile-templates.md) for templates and the `exec format error` gotcha.

```bash
docker buildx build --platform linux/amd64 -t "$image_ref" --load .
```

### 5. Authenticate to CR, push, and inspect the platform

```bash
token_json=$(ve cr GetAuthorizationToken --Registry "$registry_name")
cr_username=$(printf '%s' "$token_json" | jq -r '.Result.Username // empty')
cr_password=$(printf '%s' "$token_json" | jq -r '.Result.Token // empty')
[ -n "$cr_username" ] || { echo "CR token response missing Result.Username" >&2; exit 1; }

printf '%s' "$cr_password" | docker login "$registry_endpoint" --username "$cr_username" --password-stdin
docker push "$image_ref"
docker manifest inspect "$image_ref" | jq -r '.. | .architecture? // empty' | sort -u
```

If `docker login` returns 401, re-read `Result.Username`; never invent a fallback username. The token is temporary — re-run `GetAuthorizationToken` if push/pull starts failing after a long session. See the activated `volcengine-cli` skill's CR guidance.

### 6. Resolve env / Secret and dependency outputs

Resolve real values from `.env.example`, IaC outputs, or CLI-created dependency outputs before generating manifests. Never apply a Secret manifest that still contains placeholder connection strings. For managed dependency wiring (private endpoints, allowlists, `DATABASE_URL`/`REDIS_URL`), see [`supported-dependencies.md`](./supported-dependencies.md).

### 7. Generate manifests

Generate the Namespace/ConfigMap/Secret/Deployment/Service (and optional HPA/PDB/NetworkPolicy) from resolved values, with probes matched to the app and the CLB subnet annotation filled from outputs (not a placeholder). See [`k8s-manifests.md`](./k8s-manifests.md).

### 8. Run migrations as a Job (when needed)

When `migration_paths` is non-empty, run migrations as a Kubernetes Job and wait for completion before or alongside rollout, per the app's migration semantics. Do not bake migrations into the app container start in a way that races multiple replicas.

### 9. Apply and wait for rollout + LoadBalancer

```bash
kubectl apply -f .volcengine/k8s/
kubectl -n "$ns" rollout status deploy/"$app" --timeout=300s
# Wait for the CLB/EIP to be assigned:
for _ in $(seq 1 60); do
  lb=$(kubectl -n "$ns" get svc "$app" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
  [ -n "$lb" ] && break
  sleep 10
done
```

If the Service stays `<pending>`, the CLB subnet annotation is missing. If rollout stalls with `BLB no available backend`, the readinessProbe is failing — see the gotchas in [`k8s-manifests.md`](./k8s-manifests.md).

### 10. Verify the public endpoint and one core behavior

Verify `http://<lb>:<port><path>` from outside the cluster. HTTP 200 alone is not acceptance — check one core app behavior and `kubectl logs` where possible before reporting success.
