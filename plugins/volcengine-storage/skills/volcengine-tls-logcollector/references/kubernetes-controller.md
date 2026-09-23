# Install LogCollector Controller and manage CRD rules

Official guide: [Install LogCollector CRD](https://www.volcengine.com/docs/6470/1158004)

The Controller watches `LogCollectorRule` resources and synchronizes their lifecycle to TLS collection configuration. It is not a replacement for the DaemonSet that runs collection on nodes.

## Choose this path only when

- collection rules should be declared and maintained as Kubernetes custom resources
- the operator has permission to install CRDs, cluster-scoped RBAC, and the Controller Deployment
- the selected Controller, CRD, and LogCollector versions are compatible

Use [kubernetes-daemonset.md](kubernetes-daemonset.md) when only the collector process belongs in Kubernetes and rules remain managed through `volclog` or the TLS console.

## Preflight

```bash
kubectl config current-context
kubectl auth can-i create customresourcedefinitions.apiextensions.k8s.io
kubectl auth can-i create clusterroles.rbac.authorization.k8s.io
kubectl auth can-i create deployments -n <namespace>
```

Resolve the exact version, image, package/Chart reference, and namespace from the current official guide. Do not rely on an old manifest or mix CRD schema, Controller image, and RBAC from different releases.

Do not persist plaintext AK/SK in manifests or Helm values. Prefer the installation method's supported Kubernetes Secret reference.

## Render before installing

For Helm:

```bash
helm show values <controller-chart-reference> --version <chart-version>
helm template <release-name> <controller-chart-reference> \
  --version <chart-version> \
  --namespace <namespace> \
  -f <values-file>
```

Review at least:

- `LogCollectorRule` CRD schema and scope
- namespace and ServiceAccount
- ClusterRole and ClusterRoleBinding permissions
- Secret/ConfigMap references for region, endpoint, and authentication
- Controller Deployment image, selectors, resources, and security context

If the official package includes an installation script, inspect its `--help` and generated resources before applying it. Use only flags reported by that version.

## Author rules from the live CRD

Never guess custom-resource fields. Read the live schema and the official example for the same version:

```bash
kubectl explain logcollectorrule --recursive
kubectl get crd collectrules.logging.vke.volcengine.com -o yaml
```

Before applying a `LogCollectorRule`:

1. Resolve the target Project, Topic, and host group.
2. Collect representative log samples.
3. Use [config-validation.md](config-validation.md) to validate regex, delimiter, path, timestamp, index, or processor behavior.
4. Map only the validated semantics into fields present in the live CRD.
5. Render and review the YAML, including namespace, selectors, source paths/stream, parser, and target Topic.

Do not create a broad namespace/workload match. Do not collect Controller or LogCollector self-logs unless the user explicitly requested a temporary POC and accepted its feedback-loop and cleanup requirements.

## Verify Controller and synchronization

```bash
kubectl get crd collectrules.logging.vke.volcengine.com
kubectl -n <namespace> get deployment,pods -l app=logcollector-controller
kubectl -n <namespace> logs deployment/logcollector-controller --tail=200
kubectl get logcollectorrules -A
kubectl -n <rule-namespace> get logcollectorrule <rule-name> -o yaml
```

Check the custom resource's status and Controller logs, then use `volclog` to reconcile the service-side rule and binding. Finish with [verification.md](verification.md); a successful CR apply alone does not prove ingestion.

## Conflict and uninstall safety

Existing CRDs, ClusterRoles, ClusterRoleBindings, and releases may be owned by another installation or team. Do not delete them to make an install pass. Resolve ownership and choose adoption or a maintenance-window migration.

Before uninstalling:

1. list all `LogCollectorRule` objects
2. map them to service-side rules and determine retention behavior
3. identify cluster-scoped resources shared by other namespaces or releases
4. confirm whether the CRD will remain

Deleting a CRD can delete every custom resource of that type. Treat CRD deletion as a separate destructive decision requiring explicit confirmation.

