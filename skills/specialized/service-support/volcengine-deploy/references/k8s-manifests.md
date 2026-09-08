# Kubernetes manifest templates

Generated K8s manifests must include the following best practices. By default, place YAML files under `.volcengine/k8s/`; a temporary clone of a remote Git URL may use `/tmp` first, but final state and reusable files should land under the repo's `.volcengine/`.

---

## 1. Namespace

```yaml
# k8s/00-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: <repo-name>
  labels:
    project: <repo-name>
    managed-by: volcengine-deploy
```

---

## 2. ConfigMap & Secret

Generate ConfigMap and Secret only after resolving runtime configuration. Values can come from `.env.example`, user input, IaC outputs, or CLI-created dependency outputs. Do not apply manifests that still contain placeholder connection strings.

```yaml
# k8s/01-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: <repo-name>-config
  namespace: <repo-name>
data:
  # Non-sensitive config
  NODE_ENV: "production"
  PORT: "<port>"
  LOG_LEVEL: "info"
---
apiVersion: v1
kind: Secret
metadata:
  name: <repo-name>-secret
  namespace: <repo-name>
type: Opaque
stringData:
  # Sensitive config (DB connections, etc.); replace with real values at generation time, never leave placeholders
  DATABASE_URL: "<resolved-database-url>"
  REDIS_URL: "<resolved-redis-url>"
```

Before `kubectl apply`, grep for unresolved placeholders:

```bash
! rg -n "<connection-string>|<redis-connection-string>|<resolved-" .volcengine/k8s
```

---

## 3. Deployment

```yaml
# k8s/02-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <repo-name>
  namespace: <repo-name>
  labels:
    app: <repo-name>
    project: <repo-name>
    managed-by: volcengine-deploy
spec:
  replicas: 2
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: <repo-name>
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: <repo-name>
    spec:
      # Anti-affinity: spread across different nodes
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - <repo-name>
              topologyKey: kubernetes.io/hostname
      # Graceful termination
      terminationGracePeriodSeconds: 30
      # VKE nodes are usually linux/amd64; the built/pushed image must match the node architecture
      nodeSelector:
        kubernetes.io/arch: amd64
      # Password-free CR pulls rely on the VKE addon cr-credential-controller; do not put CR passwords in app Secrets
      imagePullSecrets:
      - name: volcengine-cr-credential
      containers:
      - name: <repo-name>
        image: <cr-endpoint>/<namespace>/<repo-name>:<tag>
        ports:
        - containerPort: <port>
          name: http
          protocol: TCP
        # Environment variables
        envFrom:
        - configMapRef:
            name: <repo-name>-config
        - secretRef:
            name: <repo-name>-secret
        # Resource limits
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: "1"
            memory: 512Mi
        # Liveness probe: is the container still alive; only use httpGet once the app is confirmed to expose a health path
        livenessProbe:
          httpGet:
            path: <health-path>
            port: http
          initialDelaySeconds: 15
          periodSeconds: 20
          timeoutSeconds: 3
          failureThreshold: 3
        # Readiness probe: can it receive traffic; if there is no HTTP health path, use the tcpSocket template below
        readinessProbe:
          httpGet:
            path: <health-path>
            port: http
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3
        # Startup probe: slow-starting apps (Java, etc.)
        startupProbe:
          httpGet:
            path: <health-path>
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 30
        # Security context
        securityContext:
          runAsNonRoot: true
          readOnlyRootFilesystem: false
          allowPrivilegeEscalation: false
```

> **Adaptation notes**:
> - Do not assume the app has a `/health` endpoint by default; determine `health_path` from code, the Dockerfile HEALTHCHECK, framework defaults, or user input first
> - If the app has no HTTP health path, use a `tcpSocket` probe instead of `httpGet`
> - Java/Spring Boot apps may need a larger `startupProbe.failureThreshold` (slow startup)
> - Adjust resource limits to the app type (Java usually needs more memory)

TCP probe fallback:

```yaml
livenessProbe:
  tcpSocket:
    port: http
  initialDelaySeconds: 15
  periodSeconds: 20
readinessProbe:
  tcpSocket:
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
startupProbe:
  tcpSocket:
    port: http
  periodSeconds: 5
  failureThreshold: 30
```

---

## 4. Service

```yaml
# k8s/03-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: <repo-name>
  namespace: <repo-name>
  labels:
    app: <repo-name>
  annotations:
    # Volcengine CLB annotations
    service.beta.kubernetes.io/volcengine-loadbalancer-subnet-id: "<subnet-id>"
    service.beta.kubernetes.io/volcengine-loadbalancer-address-type: "PUBLIC"
spec:
  type: LoadBalancer
  selector:
    app: <repo-name>
  ports:
  - name: http
    port: 80
    targetPort: http
    protocol: TCP
```

> **Notes**:
> - The `LoadBalancer` type automatically creates a Volcengine CLB
> - The subnet-id annotation is required for the CLB to be created correctly
> - If public access is not needed, switch to the `ClusterIP` type

---

## 5. HPA (Horizontal Pod Autoscaler)

```yaml
# k8s/04-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: <repo-name>
  namespace: <repo-name>
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: <repo-name>
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Pods
        value: 2
        periodSeconds: 60
```

---

## 6. PDB (Pod Disruption Budget)

```yaml
# k8s/05-pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: <repo-name>
  namespace: <repo-name>
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: <repo-name>
```

---

## 7. NetworkPolicy (optional, recommended)

```yaml
# k8s/06-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: <repo-name>-policy
  namespace: <repo-name>
spec:
  podSelector:
    matchLabels:
      app: <repo-name>
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Allow inbound traffic only from the CLB
  - ports:
    - port: <port>
      protocol: TCP
  egress:
  # Allow DNS resolution
  - to: []
    ports:
    - port: 53
      protocol: UDP
    - port: 53
      protocol: TCP
  # Allow access to internal services such as databases
  - to:
    - ipBlock:
        cidr: 172.16.0.0/16
```

---

## File organization

Generated K8s manifests are numbered to ensure they apply in order:

```text
k8s/
├── 00-namespace.yaml
├── 01-config.yaml
├── 02-deployment.yaml
├── 03-service.yaml
├── 04-hpa.yaml
├── 05-pdb.yaml
└── 06-network-policy.yaml    # optional
```

One-shot deploy:
```bash
kubectl apply -f .volcengine/k8s/
```

---

## Gotchas (common VKE deployment failure modes)

Look up by symptom; act on the mapped cause directly rather than suspecting unrelated layers first.

| Symptom | Cause | Fix |
|---|---|---|
| `CreateKubeconfig` returns `OperationDenied` | cluster not yet `Running` | Poll `ListClusters` until `Status.Phase=Running` before fetching the kubeconfig |
| `Service` `LoadBalancer` stuck at `<pending>` | missing CLB subnet annotation | Add `service.beta.kubernetes.io/volcengine-loadbalancer-subnet-id` to the Service |
| `BLB no available backend` / no available backend nodes | Pod readinessProbe failing, often because the probed `/health` path does not exist | Use the actual detected health path, or switch the probe to `tcpSocket`; diagnose with `kubectl describe pod` + `kubectl logs` |
| Container exits immediately with `exec format error` | image architecture does not match the VKE node architecture | Rebuild/pull/push with the node architecture (usually `linux/amd64`) and inspect the image platform before rollout (see [`dockerfile-templates.md`](./dockerfile-templates.md)) |
| App is up but all config-dependent requests fail | ConfigMap/Secret was not generated from real values and left placeholders | Resolve `.env.example`/dependency outputs, regenerate the Secret, then rollout again; **never** apply placeholders into a Secret |
| Private CR image pull fails with `no basic auth` / `ImagePullBackOff` | `cr-credential-controller` not installed, or wrong registry credentials hardcoded in the manifest | Prefer `cr-credential-controller` for private CR pulls instead of putting registry passwords in the app manifest |
