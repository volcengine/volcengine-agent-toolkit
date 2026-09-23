# Install LogCollector as a Kubernetes DaemonSet

Official guide: [Install LogCollector with DaemonSet](https://www.volcengine.com/docs/6470/109796)

Use this path when LogCollector should run on selected Kubernetes nodes while TLS collector rules remain managed through the TLS API or `volclog`. If rules must be declared through `LogCollectorRule` custom resources, use [kubernetes-controller.md](kubernetes-controller.md).

## Preflight

```bash
kubectl config current-context
kubectl auth can-i create daemonsets -n <namespace>
kubectl get nodes -o wide
```

Confirm:

- exact cluster context, namespace, and target node set
- node CPU architectures and image support
- container runtime log paths and any host paths to mount
- taints/tolerations, node selectors, affinity, and security controls
- package/image registry and TLS endpoint reachability from target nodes
- Label host identity shared by the DaemonSet and TLS host group
- current installer or Chart version from the official guide

Do not store plaintext AK/SK in a values file, manifest, repository, generated answer, or shell history. Prefer a supported Kubernetes Secret reference or controlled temporary injection.

## Script installation

The source workflow uses this public download pattern:

```bash
wget "https://logcollector-<region>.tos-<region>.volces.com/logcollector.tgz" \
  -O /tmp/logcollector.tgz
tar -xzf /tmp/logcollector.tgz -C /tmp
chmod 755 /tmp/logcollector/logcollector.sh
/tmp/logcollector/logcollector.sh --help
```

For a private network, confirm the corresponding `.ivolces.com` URL in the current official guide. Review the generated resources before applying them.

Use only flags reported by the downloaded version. A representative shape is:

```bash
/tmp/logcollector/logcollector.sh install \
  --region <region> \
  --endpoint <explicit-tls-endpoint> \
  --secret_id <securely-injected-secret-id> \
  --secret_key <securely-injected-secret-key> \
  --label <host-identifier> \
  --namespace <namespace> \
  --logcollector_data <absolute-host-path>
```

Do not execute this skeleton until its flags, secret handling, and effects match the current installer.

## Helm installation

Resolve the Chart reference, Chart version, image tag, and values keys from the current official guide. Inspect before installing:

```bash
helm show values <chart-reference> --version <chart-version>
helm template <release-name> <chart-reference> \
  --version <chart-version> \
  --namespace <namespace> \
  -f <values-file>
```

Review ServiceAccount/RBAC, DaemonSet selectors, tolerations, hostPath mounts, security context, resources, image, endpoint, identity, and secret references. Use `helm install` only after the rendered resources match the confirmed target.

## Collection rule

Derive the rule from the actual source:

- node or container file: use the exact mounted path and the correct host/container-file input type
- container stdout/stderr: use the stdout input type, selected stream, and exact namespace/workload/container filters
- never use a blank filter that can collect every Pod

Read [config-validation.md](config-validation.md), then [tls-resources.md](tls-resources.md). The rule and DaemonSet must agree on paths, identity, namespace, and workload selectors.

Do not collect LogCollector's own stdout by default. Use it only for an explicitly requested temporary POC, with an exact workload filter, two short observation windows, and a teardown plan.

## Verify

```bash
kubectl -n <namespace> get daemonset <daemonset-name> -o wide
kubectl -n <namespace> get pods -l <exact-label-selector> -o wide
kubectl -n <namespace> describe daemonset <daemonset-name>
kubectl -n <namespace> logs daemonset/<daemonset-name> --tail=200
```

Success requires:

- desired/current/ready counts match the intended node set
- no persistent crash, image-pull, mount, RBAC, or scheduling errors
- each intended node has a ready Pod
- actual mounts and runtime paths match the collector rule
- [verification.md](verification.md) confirms heartbeat, binding, and Topic ingestion

## Upgrade and uninstall

For Helm, render and inspect an upgrade before applying it:

```bash
helm upgrade <release-name> <chart-reference> \
  --version <chart-version> \
  --namespace <namespace> \
  -f <values-file> \
  --dry-run
```

For script installations, use the lifecycle command shipped with the installed version. Before uninstalling, identify the exact release/resources and the resulting collection gap. Do not bulk-delete unknown resources.

