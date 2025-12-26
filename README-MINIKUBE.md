# Running the IDP Demo on Minikube

This guide explains how to run the Internal Development Platform demo locally using minikube instead of GitHub Codespaces.

## Prerequisites

| Tool | Minimum Version | Check Command |
|------|-----------------|---------------|
| minikube | 1.30.0 | `minikube version` |
| kubectl | 1.27.0 | `kubectl version --client` |
| Docker | 20.10+ | `docker --version` |
| Helm | 3.0+ | `helm version` |

**Hardware**: 4GB RAM, 2 CPUs minimum (8GB/4 CPUs recommended)

## Quick Start

### 1. Configure Secrets

```bash
# Copy the template
cp secrets/template.env secrets/minikube.env

# Edit with your values
vim secrets/minikube.env
```

**Minimal secrets/minikube.env** (without Dynatrace):
```bash
GITHUB_TOKEN=ghp_your_github_personal_access_token
```

### 2. Run Bootstrap

```bash
./bootstrap.sh minikube
```

The bootstrap will:
- Start/configure minikube cluster
- Install ArgoCD and platform components
- Create Kubernetes secrets
- Optionally set up Dynatrace (if credentials provided)

### 3. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| ArgoCD | http://localhost:30100 | admin / `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" \| base64 -d` |
| Backstage | http://localhost:30105 | - |
| Demo Apps | http://localhost:80/{app-path} | - |

**Alternative access via minikube IP:**
```bash
minikube service argocd-server -n argocd --url
minikube service backstage -n backstage --url
```

## Command Reference

```bash
# Bootstrap the platform
./bootstrap.sh minikube

# Check cluster status
minikube status

# View ArgoCD applications
kubectl get applications -n argocd

# Stop cluster (preserves state)
minikube stop

# Delete cluster completely
minikube delete
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    minikube                          │
│  ┌─────────────┐ ┌─────────────┐ ┌───────────────┐  │
│  │   ArgoCD    │ │  Backstage  │ │ OpenTelemetry │  │
│  │   :30100    │ │   :30105    │ │  (optional)   │  │
│  └─────────────┘ └─────────────┘ └───────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌───────────────┐  │
│  │cert-manager │ │   ingress   │ │ customer-apps │  │
│  └─────────────┘ └─────────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────┘
         │              │              │
    localhost:30100  localhost:30105  localhost:80
```

## Configuration Profiles

Profiles are YAML files in `config/profiles/` that define environment-specific settings:

```yaml
# config/profiles/minikube.yaml
environment: minikube
cluster:
  driver: docker
  cpus: 2
  memory: 4096
  addons: [ingress, metrics-server]
components:
  argocd: true
  backstage: true
  dynatrace: false    # Toggle observability
  keptn: false        # Toggle for resource-constrained setups
```

## Troubleshooting

### Cluster won't start
```bash
minikube delete
minikube start --driver=docker --cpus=2 --memory=4096
```

### Services not accessible
```bash
# Ensure tunnel is running for ingress
minikube tunnel

# Or use NodePort directly
minikube service list
```

### ArgoCD apps stuck syncing
```bash
# Check ArgoCD logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server

# Force sync
kubectl -n argocd patch application <app-name> -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{}}}' --type=merge
```

### Reset everything
```bash
minikube delete
./bootstrap.sh minikube
```

## Differences from Codespaces

| Aspect | Codespaces | Minikube |
|--------|------------|----------|
| Cluster | Kind | Minikube |
| URLs | `*.app.github.dev` | `localhost:port` |
| Secrets | Environment variables | `secrets/minikube.env` |
| Dynatrace | Required | Optional |
| Keptn | Enabled | Disabled by default |

## File Structure

```
├── bootstrap.sh               # Main entry point
├── config/
│   ├── minikube.env          # Environment config (non-secret)
│   └── profiles/
│       └── minikube.yaml     # Minikube-specific settings
├── secrets/
│   ├── template.env          # Template (copy to minikube.env)
│   └── minikube.env          # Your secrets (gitignored)
└── gitops/
    ├── platform-minikube.yml  # Root ArgoCD Application (minikube)
    ├── platform-apps/         # Helm chart for 11 ArgoCD Applications
    │   ├── Chart.yaml
    │   ├── values.yaml        # All applications (shared defaults)
    │   ├── values-minikube.yaml   # Minikube overrides
    │   └── templates/
    │       └── applications.yaml
    └── manifests/platform/    # Kubernetes manifests (Kustomize)
```

## Contributing

### Adding a New Environment

The platform uses Helm to manage ArgoCD Applications, making it easy to add new environments:

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

3. **Optional**: Create `config/profiles/<env>.yaml` for bootstrap configuration
