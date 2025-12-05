# Running the IDP Demo on Minikube

This guide explains how to run the Internal Development Platform demo locally using minikube instead of GitHub Codespaces.

## Prerequisites

| Tool | Minimum Version | Check Command |
|------|-----------------|---------------|
| minikube | 1.30.0 | `minikube version` |
| kubectl | 1.27.0 | `kubectl version --client` |
| Docker | 20.10+ | `docker --version` |
| Python | 3.8+ | `python3 --version` |

**Hardware**: 4GB RAM, 2 CPUs minimum (8GB/4 CPUs recommended)

## Quick Start

### 1. Configure Secrets

```bash
# Copy the example secrets file
cp secrets-minikube.yaml.example secrets-minikube.yaml

# Edit with your values
# Required: github.token (for ArgoCD repository access)
# Optional: dynatrace.* (for observability features)
```

**Minimal secrets-minikube.yaml** (without Dynatrace):
```yaml
github:
  token: "ghp_your_github_personal_access_token"
```

### 2. Run the Installer

```bash
# Full installation (with Dynatrace)
python3 minikube_installer.py

# Without Dynatrace (minimal setup)
python3 minikube_installer.py --skip-dynatrace
```

The installer will:
- Start/configure minikube cluster
- Enable required addons (ingress, metrics-server)
- Deploy ArgoCD and platform components
- Run validation checkpoints

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
# Start installer
python3 minikube_installer.py [--skip-dynatrace] [--profile <name>]

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
rm -f secrets-minikube.yaml  # Keep your secrets safe elsewhere
python3 minikube_installer.py --skip-dynatrace
```

## Differences from Codespaces

| Aspect | Codespaces | Minikube |
|--------|------------|----------|
| Cluster | Kind | Minikube |
| URLs | `*.app.github.dev` | `localhost:port` |
| Secrets | Environment variables | `secrets-minikube.yaml` |
| Dynatrace | Required | Optional |
| Keptn | Enabled | Disabled by default |

## File Structure (New)

```
├── minikube_installer.py      # Entry point for minikube
├── secrets-minikube.yaml.example
├── environments/              # Environment abstraction
│   ├── base.py               # Abstract base class
│   ├── minikube.py           # Minikube implementation
│   └── codespaces.py         # Codespaces implementation
├── config/
│   └── profiles/             # Environment profiles
│       ├── minikube.yaml
│       └── codespaces.yaml
├── secrets/                   # Secrets management
│   └── manager.py
└── validation/                # Installation validation
    ├── checkpoints.py
    └── runner.py
```

## Contributing

The codebase now supports multiple environments via an abstraction layer. To add a new environment:

1. Create `environments/<name>.py` implementing `EnvironmentBase`
2. Create `config/profiles/<name>.yaml`
3. Update `EnvironmentFactory` detection logic
