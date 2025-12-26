# Running the IDP Demo on Kind

This guide explains how to run the Internal Development Platform demo locally using Kind (Kubernetes in Docker) instead of GitHub Codespaces.

## Why Kind?

Kind is a lightweight alternative to minikube that:
- Uses Docker containers as Kubernetes nodes
- Shares the host Docker daemon (faster image access)
- Has simpler networking (direct localhost port mapping)
- Starts faster and uses less resources

## Prerequisites

| Tool | Minimum Version | Check Command |
|------|-----------------|---------------|
| Kind | 0.20.0 | `kind version` |
| kubectl | 1.27.0 | `kubectl version --client` |
| Docker | 20.10+ | `docker --version` |
| Helm | 3.0+ | `helm version` |

**Hardware**: 4GB RAM minimum (8GB recommended)

### Install Kind

```bash
# macOS
brew install kind

# Linux
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

## Quick Start

### 1. Configure Secrets

```bash
# Copy the template
cp secrets/template.env secrets/kind.env

# Edit with your GitHub token
vim secrets/kind.env
```

**Minimal secrets/kind.env** (without Dynatrace):
```bash
GITHUB_TOKEN=ghp_your_github_personal_access_token
```

### 2. Run Bootstrap

```bash
./bootstrap.sh kind
```

The bootstrap will:
- Create Kind cluster with port mappings
- Preload container images (faster deployments)
- Install ArgoCD and platform components
- Create Kubernetes secrets
- Optionally set up Dynatrace (if credentials provided)

### 3. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| ArgoCD | http://localhost:30100 | admin / `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" \| base64 -d` |
| Backstage | http://localhost:30105 | - |
| Demo Apps | http://localhost:80/{app-path} | - |

## Command Reference

```bash
# Bootstrap the platform
./bootstrap.sh kind

# Check cluster status
kind get clusters
kubectl get nodes

# View ArgoCD applications
kubectl get applications -n argocd

# Delete cluster completely
kind delete cluster --name idp

# Recreate from scratch
kind delete cluster --name idp && ./bootstrap.sh kind
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Docker Host                         │
│  ┌───────────────────────────────────────────────┐  │
│  │            Kind Cluster (idp)                  │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │  │
│  │  │   ArgoCD    │ │  Backstage  │ │   OTEL   │ │  │
│  │  │   :30100    │ │   :30105    │ │:4317/4318│ │  │
│  │  └─────────────┘ └─────────────┘ └──────────┘ │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │  │
│  │  │cert-manager │ │   ingress   │ │cust-apps │ │  │
│  │  └─────────────┘ └─────────────┘ └──────────┘ │  │
│  └───────────────────────────────────────────────┘  │
│                        │                             │
│            Docker port forwarding                    │
└────────────────────────┼─────────────────────────────┘
                         │
              localhost:30100 (ArgoCD)
              localhost:30105 (Backstage)
              localhost:80 (Apps via Ingress)
              localhost:4317/4318 (OTEL)
```

## Port Mappings

Defined in `.devcontainer/kind-cluster.yml`:

| Host Port | Container Port | Service |
|-----------|---------------|---------|
| 80 | 80 | Ingress (customer apps) |
| 4317 | 4317 | OTEL gRPC |
| 4318 | 4318 | OTEL HTTP |
| 30100 | 30100 | ArgoCD |
| 30105 | 30105 | Backstage |

## Image Preloading

Kind preloads these images for faster deployments:

```bash
ghcr.io/katharinasick/backstage-playground:1.2.4
ghcr.io/dynatrace-oss/bizevent-pusher:v1.1.1
quay.io/argoproj/argocd:v2.12.2
ghcr.io/dexidp/dex:v2.38.0
redis:7.0.15-alpine
```

To manually load additional images:
```bash
docker pull <image>
kind load docker-image <image> --name idp
```

## Troubleshooting

### Cluster won't start
```bash
# Check Docker is running
docker info

# Delete and recreate
kind delete cluster --name idp
./bootstrap.sh kind
```

### Services not accessible
```bash
# Check port mappings
docker port idp-control-plane

# Check services
kubectl get svc -A | grep NodePort

# Restart port-forward if needed
kubectl port-forward -n argocd svc/argocd-server 30100:443
```

### ArgoCD can't reach GitHub
```bash
# Check network from inside cluster
kubectl run test --rm -it --restart=Never --image=curlimages/curl -- curl -s https://github.com

# Check ArgoCD repo server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server
```

### Apps stuck syncing
```bash
# Check ArgoCD application status
kubectl get applications -n argocd

# Check specific app
kubectl describe application <app-name> -n argocd

# Force refresh
kubectl -n argocd patch application <app-name> -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}' --type=merge
```

### Reset everything
```bash
kind delete cluster --name idp
./bootstrap.sh kind
```

## Differences from Minikube

| Aspect | Kind | Minikube |
|--------|------|----------|
| Runtime | Docker containers | VM or Docker |
| Port access | Direct localhost mapping | `minikube ip` or tunnel |
| Image loading | `kind load docker-image` | `minikube image load` |
| Startup time | ~30 seconds | ~1-2 minutes |
| Resource usage | Lower | Higher |
| Networking | Docker bridge | VM network |

## Differences from Codespaces

| Aspect | Codespaces | Kind |
|--------|------------|------|
| Location | Cloud (GitHub) | Local (Docker) |
| URLs | `*.app.github.dev` | `localhost:port` |
| Secrets | Environment variables | `secrets/kind.env` |
| Dynatrace | Required | Optional |
| Setup time | ~10 minutes | ~2-3 minutes |

## File Structure

```
├── bootstrap.sh               # Main entry point
├── config/
│   ├── kind.env              # Environment config (non-secret)
│   └── profiles/
│       └── kind.yaml         # Kind-specific settings
├── secrets/
│   ├── template.env          # Template (copy to kind.env)
│   └── kind.env              # Your secrets (gitignored)
├── .devcontainer/
│   └── kind-cluster.yml      # Kind cluster configuration
└── gitops/
    ├── platform-kind.yml     # Root ArgoCD Application (Kind)
    ├── platform-apps/        # Helm chart for 11 ArgoCD Applications
    │   ├── Chart.yaml
    │   ├── values.yaml       # All applications (shared defaults)
    │   ├── values-kind.yaml  # Kind-specific overrides
    │   └── templates/
    │       └── applications.yaml
    └── manifests/platform/   # Kubernetes manifests (Kustomize)
```

## Adding Dynatrace Integration

To enable full observability with Dynatrace:

```bash
# Edit secrets/kind.env
cat >> secrets/kind.env << 'EOF'
DT_ENV_NAME=abc12345
DT_ENV=live
DT_RW_API_TOKEN=dt0c01.xxx
DT_OAUTH_CLIENT_ID=dt0s02.xxx
DT_OAUTH_CLIENT_SECRET=xxx
DT_OAUTH_ACCOUNT_URN=urn:dtaccount:xxx
EOF

# Recreate cluster
kind delete cluster --name idp
./bootstrap.sh kind
```

## Contributing

### Adding a New Environment

The platform uses Helm to manage ArgoCD Applications:

1. **Create values file**: `gitops/platform-apps/values-<env>.yaml`
   ```yaml
   global:
     targetRevision: "main"  # or specific branch
   ```

2. **Create root application**: `gitops/platform-<env>.yml`
   ```yaml
   spec:
     source:
       path: "gitops/platform-apps"
       helm:
         valueFiles:
           - values-<env>.yaml
   ```

3. **Create config file**: `config/<env>.env`
4. **Optional**: Create `config/profiles/<env>.yaml` for additional settings
