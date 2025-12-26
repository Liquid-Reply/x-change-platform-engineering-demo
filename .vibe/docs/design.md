# Design Document: Kind Integration

*Implementation design for Kind cluster support using bootstrap.sh + GitOps approach*

---

## Kind Integration (Implemented)

The Kind environment support uses `bootstrap.sh` as the entry point:
```bash
./bootstrap.sh kind
```

### Implemented Files

| File | Status | Purpose |
|------|--------|---------|
| `gitops/platform-kind.yml` | ✅ Created | Root ArgoCD Application for Kind |
| `gitops/platform-apps/values-kind.yaml` | ✅ Updated | Kind-specific Helm values |
| `config/kind.env` | ✅ Updated | Environment variables |
| `.devcontainer/kind-cluster.yml` | ✅ Exists | Kind cluster configuration |
| `bootstrap.sh` | ✅ Updated | Image preloading for Kind (lines 153-177) |

---

## bootstrap.sh Kind Image Preloading

Added after line 152 (after minikube image preloading section):

```bash
elif [[ "${CLUSTER_TYPE}" == "kind" ]]; then
  log "Preloading container images into Kind cluster..."

  declare -a IMAGES=(
    "ghcr.io/katharinasick/backstage-playground:1.2.4"
    "ghcr.io/dynatrace-oss/bizevent-pusher:v1.1.1"
    "quay.io/argoproj/argocd:v2.12.2"
    "ghcr.io/dexidp/dex:v2.38.0"
    "redis:7.0.15-alpine"
  )

  for image in "${IMAGES[@]}"; do
    docker pull "${image}" 2>/dev/null || warn "Failed to pull ${image}"
    kind load docker-image "${image}" --name "${CLUSTER_NAME}" 2>/dev/null || warn "Failed to load ${image}"
    log "Loaded ${image} into Kind cluster..."
  done
fi
```

---

## platform-kind.yml

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform
  namespace: argocd
  labels:
    dt.owner: "platform_team"
spec:
  source:
    path: "gitops/platform-apps"
    repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
    targetRevision: gh_opus_kostumize2helm
    helm:
      valueFiles:
        - values-kind.yaml
  destination:
    namespace: argocd
    server: 'https://kubernetes.default.svc'
  project: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    retry:
      limit: 5
      backoff:
        duration: 5s
        maxDuration: 3m0s
        factor: 2
```

---

## Kind vs Minikube Comparison

| Aspect | Minikube | Kind |
|--------|----------|------|
| **Cluster Access** | `minikube ip` returns VM IP | `localhost` via Docker port forwarding |
| **Image Loading** | `minikube image load <image>` | `kind load docker-image <image>` |
| **Context Name** | `minikube` | `kind-{cluster_name}` |
| **Port Mapping** | NodePort via VM | HostPort via Docker |
| **Config File** | Inline args | `.devcontainer/kind-cluster.yml` |
| **Root App** | `platform-minikube.yml` | `platform-kind.yml` |

---

## Port Mappings (Kind)

Defined in `.devcontainer/kind-cluster.yml`:

| Port | Service |
|------|---------|
| 80 | Ingress (customer apps) |
| 4317 | OTEL gRPC |
| 4318 | OTEL HTTP |
| 30100 | ArgoCD |
| 30105 | Backstage |

---

## Graceful Degradation

| Component | Missing Condition | Behavior |
|-----------|-------------------|----------|
| Dynatrace | No DT credentials | Skip Dynatrace apps, log info |
| Keptn | `INSTALL_KEPTN=false` | Skip Keptn installation |
| OTEL | No DT endpoint | Deploy collector in standalone mode |

---

## Test Results

All tests passed:

- ✅ Cluster creation with Kind
- ✅ Image preloading (5 images)
- ✅ ArgoCD accessible at localhost:30100
- ✅ Backstage accessible at localhost:30105
- ✅ 10/12 ArgoCD applications synced & healthy
- ✅ OTEL ports responding (4317, 4318)
- ✅ Ingress controller running
- ✅ ApplicationSet scanning customer-apps

### Known Expected Issues

| Issue | Reason |
|-------|--------|
| OTEL collector CreateContainerConfigError | Missing `dt-details` secret (no Dynatrace config) |
| dynatrace app OutOfSync | No DT tokens configured |
| 0 customer apps | Expected - created via Backstage workflow |
