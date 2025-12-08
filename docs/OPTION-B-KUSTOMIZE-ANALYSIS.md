# Option B: Full Kustomize Architecture

**Goal:** Minimize Python code, maximize declarative Kustomize configuration.

---

## Current vs Target

| Aspect | Current | Target |
|--------|---------|--------|
| Python LOC | ~1100 (2 installers) | ~100 (DT API only) |
| Placeholder handling | Python find/replace | Kustomize replacements |
| Environment config | Hardcoded in Python | Overlay directories |
| Optional components | File renaming | Kustomize components |
| Secrets | kubectl create in Python | secretGenerator + envsubst |
| Bootstrap | Python orchestration | Shell script (~50 lines) |

---

## Target Directory Structure

```
.
├── bootstrap.sh                    # Single entry point (~50 lines)
├── scripts/
│   └── dynatrace.py               # DT API calls only (~100 lines)
├── config/
│   ├── minikube.env               # Environment variables
│   ├── codespaces.env
│   ├── kind.env
│   └── k3d.env
├── secrets/                        # Gitignored, local secrets
│   ├── github-token
│   ├── dt-credentials.env         # Optional
│   └── README.md
├── gitops/
│   ├── bootstrap/                 # ArgoCD installation
│   │   ├── base/
│   │   │   ├── kustomization.yaml
│   │   │   └── install.yaml       # ArgoCD v2.12.2 manifests
│   │   └── overlays/
│   │       ├── minikube/
│   │       │   └── kustomization.yaml
│   │       └── codespaces/
│   │           └── kustomization.yaml
│   ├── platform/                  # Root app-of-apps
│   │   ├── base/
│   │   │   ├── kustomization.yaml
│   │   │   └── platform-app.yaml
│   │   └── overlays/
│   │       ├── minikube/
│   │       │   └── kustomization.yaml
│   │       └── codespaces/
│   │           └── kustomization.yaml
│   ├── applications/              # (exists) ArgoCD Applications
│   │   ├── base/
│   │   └── overlays/
│   │       ├── minikube/
│   │       └── codespaces/
│   └── manifests/
│       ├── base/                  # NEW: Common manifests
│       │   ├── kustomization.yaml
│       │   ├── namespaces/
│       │   ├── argoconfig/
│       │   ├── backstage/
│       │   ├── opentelemetry/
│       │   └── ingress-nginx/
│       ├── components/            # NEW: Optional features
│       │   ├── dynatrace/
│       │   │   ├── kustomization.yaml
│       │   │   └── dynakube.yaml
│       │   ├── keptn/
│       │   │   └── kustomization.yaml
│       │   └── nodeport-services/
│       │       └── kustomization.yaml
│       └── overlays/              # NEW: Environment-specific
│           ├── minikube/
│           │   ├── kustomization.yaml
│           │   ├── secrets.yaml   # secretGenerator
│           │   └── patches/
│           ├── codespaces/
│           │   └── kustomization.yaml
│           ├── kind/
│           │   └── kustomization.yaml
│           └── k3d/
│               └── kustomization.yaml
```

---

## Key Kustomize Features

### 1. Replacements (No Python Needed)

Replace `config/minikube.env`:
```bash
REPO_URL=https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git
TARGET_REVISION=main
CLUSTER_TYPE=minikube
BASE_DOMAIN=minikube
ARGOCD_PORT=30100
BACKSTAGE_PORT=30105
```

`gitops/manifests/overlays/minikube/kustomization.yaml`:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

components:
  - ../../components/nodeport-services

# Generate ConfigMap from env file (loaded at build time)
configMapGenerator:
  - name: platform-config
    envs:
      - ../../../../config/minikube.env

# Use replacements to inject values from ConfigMap
replacements:
  - source:
      kind: ConfigMap
      name: platform-config
      fieldPath: data.REPO_URL
    targets:
      - select:
          kind: Application
        fieldPaths:
          - spec.source.repoURL
        options:
          create: false
  - source:
      kind: ConfigMap
      name: platform-config
      fieldPath: data.TARGET_REVISION
    targets:
      - select:
          kind: Application
        fieldPaths:
          - spec.source.targetRevision
        options:
          create: false
```

### 2. Components (Optional Features)

`gitops/manifests/components/dynatrace/kustomization.yaml`:
```yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component

resources:
  - dynakube.yaml
  - workflow.yaml

# Dynatrace-specific patches
patches:
  - target:
      kind: Namespace
      name: dynatrace
    patch: |-
      - op: add
        path: /metadata/labels/dynatrace
        value: "true"
```

Enable in overlay:
```yaml
# gitops/manifests/overlays/minikube/kustomization.yaml
components:
  - ../../components/dynatrace
  - ../../components/nodeport-services
```

### 3. Secret Generation

`gitops/manifests/overlays/minikube/kustomization.yaml`:
```yaml
secretGenerator:
  - name: github-token
    namespace: argocd
    files:
      - token=../../../../secrets/github-token
    options:
      disableNameSuffixHash: true

  - name: backstage-secrets
    namespace: backstage
    envs:
      - ../../../../secrets/backstage.env
    options:
      disableNameSuffixHash: true
```

---

## Bootstrap Script

`bootstrap.sh` (~50 lines):
```bash
#!/bin/bash
set -euo pipefail

ENV=${1:-minikube}
ARGOCD_VERSION="v2.12.2"

echo "=== IDP Platform Bootstrap: $ENV ==="

# 1. Validate
[[ -f "config/${ENV}.env" ]] || { echo "Unknown env: $ENV"; exit 1; }
[[ -f "secrets/github-token" ]] || { echo "Missing secrets/github-token"; exit 1; }

# 2. Load environment config
export $(grep -v '^#' "config/${ENV}.env" | xargs)

# 3. Create cluster
case $ENV in
  minikube)
    minikube delete --profile idp 2>/dev/null || true
    minikube start --profile idp --cpus=4 --memory=8192 --driver=docker
    minikube profile idp
    kubectl label nodes idp ingress-ready=true --overwrite
    ;;
  kind)
    kind delete cluster --name idp 2>/dev/null || true
    kind create cluster --name idp --config .devcontainer/kind-cluster.yml --wait 5m
    ;;
  k3d)
    k3d cluster delete idp 2>/dev/null || true
    k3d cluster create idp -p "80:80@loadbalancer" --wait
    ;;
esac

# 4. Create namespaces
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace backstage --dry-run=client -o yaml | kubectl apply -f -

# 5. Bootstrap ArgoCD (Kustomize handles config)
kustomize build "gitops/bootstrap/overlays/${ENV}" | kubectl apply -f -
kubectl wait --for=condition=Available deployment -n argocd --all --timeout=5m

# 6. Apply secrets (Kustomize generates from local files)
kustomize build "gitops/manifests/overlays/${ENV}" | \
  kubectl apply -f - --selector='kind=Secret' 2>/dev/null || true

# 7. Apply platform root app (ArgoCD takes over)
kustomize build "gitops/platform/overlays/${ENV}" | kubectl apply -f -

# 8. Generate ArgoCD token for Backstage
kubectl config set-context --current --namespace=argocd
argocd login argo --core 2>/dev/null || true

for i in {1..60}; do
  argocd account list 2>/dev/null | grep -q alice && break
  echo "Waiting for alice account... ($i/60)"
  sleep 2
done

ARGOCD_TOKEN=$(argocd account generate-token --account alice 2>/dev/null)
kubectl -n backstage create secret generic argocd-token \
  --from-literal=ARGOCD_TOKEN="$ARGOCD_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl config set-context --current --namespace=default

# 9. Optional: Dynatrace setup
if [[ -f "secrets/dt-credentials.env" ]]; then
  echo "Setting up Dynatrace..."
  python3 scripts/dynatrace.py --env "$ENV"
fi

echo "=== Bootstrap complete ==="
echo "ArgoCD: http://localhost:${ARGOCD_PORT:-30100}"
echo "Backstage: http://localhost:${BACKSTAGE_PORT:-30105}"
```

---

## Minimal Python: Dynatrace Only

`scripts/dynatrace.py` (~100 lines):
```python
#!/usr/bin/env python3
"""Dynatrace API integration - the only Python needed."""

import os
import sys
import json
import argparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def load_credentials(env_file="secrets/dt-credentials.env"):
    """Load DT credentials from env file."""
    creds = {}
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    creds[k] = v
    return creds

def create_api_token(tenant_url, rw_token, name, scopes):
    """Create a Dynatrace API token."""
    url = f"{tenant_url}/api/v2/apiTokens"
    data = json.dumps({"name": name, "scopes": scopes}).encode()
    req = Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Api-Token {rw_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())["token"]
    except HTTPError as e:
        print(f"Token creation failed: {e.read().decode()}", file=sys.stderr)
        return None

def upload_asset(tenant_url, oauth_creds, path, name, asset_type):
    """Upload dashboard/notebook to Dynatrace."""
    # OAuth token exchange + upload logic
    pass  # Simplified for analysis

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="minikube")
    parser.add_argument("--create-tokens", action="store_true")
    parser.add_argument("--upload-assets", action="store_true")
    args = parser.parse_args()

    creds = load_credentials()
    if not creds.get("DT_RW_API_TOKEN"):
        print("No DT credentials found, skipping Dynatrace setup")
        return

    tenant = f"https://{creds['DT_ENV_NAME']}.{creds.get('DT_ENV', 'live')}.dynatrace.com"

    if args.create_tokens:
        tokens = {
            "DT_ALL_INGEST_TOKEN": create_api_token(tenant, creds["DT_RW_API_TOKEN"],
                f"[{args.env}] DT_ALL_INGEST_TOKEN",
                ["bizevents.ingest", "events.ingest", "logs.ingest",
                 "metrics.ingest", "openTelemetryTrace.ingest"]),
        }
        # Write tokens to file for Kustomize secretGenerator
        with open(f"secrets/dt-tokens-{args.env}.env", "w") as f:
            for k, v in tokens.items():
                if v:
                    f.write(f"{k}={v}\n")

    if args.upload_assets:
        # Upload dashboards, notebooks, workflows
        pass

if __name__ == "__main__":
    main()
```

---

## Adding New Environment

**Example: Add k3d support**

### Step 1: Create config file
`config/k3d.env`:
```bash
REPO_URL=https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git
TARGET_REVISION=main
CLUSTER_TYPE=k3d
BASE_DOMAIN=localhost
ARGOCD_PORT=30100
BACKSTAGE_PORT=30105
INGRESS_TYPE=loadbalancer
```

### Step 2: Create overlay
`gitops/manifests/overlays/k3d/kustomization.yaml`:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

components:
  # k3d uses LoadBalancer, not NodePort
  - ../../components/loadbalancer-services

configMapGenerator:
  - name: platform-config
    envs:
      - ../../../../config/k3d.env
```

### Step 3: Run
```bash
./bootstrap.sh k3d
```

**Total effort: 2 files, ~20 lines**

---

## Migration Path

| Phase | Task | Files Changed |
|-------|------|---------------|
| 1 | Create `gitops/manifests/base/` | Move existing manifests |
| 2 | Create `gitops/manifests/components/` | Extract dynatrace, keptn |
| 3 | Create `gitops/manifests/overlays/` | New kustomization.yaml per env |
| 4 | Create `config/*.env` | Extract from Python |
| 5 | Create `bootstrap.sh` | New file (~50 lines) |
| 6 | Create `scripts/dynatrace.py` | Extract DT-only code |
| 7 | Delete old installers | Remove ~1000 lines Python |

---

## Comparison: Python vs Kustomize

### Placeholder Replacement

**Before (Python):**
```python
def _replace_placeholders(self):
    placeholders = self.env.get_placeholder_values()
    for placeholder, value in placeholders.items():
        do_file_replace("./**/*.y*ml", placeholder, value, recursive=True)
```
*Problem: Modifies files in repo, requires git commit*

**After (Kustomize):**
```yaml
configMapGenerator:
  - name: env-config
    envs: [config/minikube.env]

replacements:
  - source: {kind: ConfigMap, name: env-config, fieldPath: data.REPO_URL}
    targets:
      - select: {kind: Application}
        fieldPaths: [spec.source.repoURL]
```
*Benefit: No file modification, values injected at build time*

---

### Component Toggles

**Before (Python):**
```python
if 'keptn' not in enabled:
    os.rename("gitops/applications/platform/keptn.yml",
              "gitops/applications/platform/keptn.yml.disabled")
```
*Problem: Mutates repo state*

**After (Kustomize):**
```yaml
# gitops/manifests/overlays/minikube/kustomization.yaml
components:
  # - ../../components/keptn  # Commented out = disabled
  - ../../components/nodeport-services
```
*Benefit: Declarative, no file mutation*

---

### Secrets

**Before (Python):**
```python
self.secrets.create_k8s_secret("backstage-secrets", "backstage", {
    "GITHUB_TOKEN": platform_secrets.github.token,
    "ARGOCD_TOKEN": self.argocd_token,
    # ...12 more fields
})
```

**After (Kustomize):**
```yaml
secretGenerator:
  - name: backstage-secrets
    namespace: backstage
    envs:
      - ../../../../secrets/backstage.env
    options:
      disableNameSuffixHash: true
```
*Benefit: Secrets in files (gitignored), not in code*

---

## What Cannot Be Kustomize

| Task | Reason | Solution |
|------|--------|----------|
| Cluster creation | Shell commands | `bootstrap.sh` |
| ArgoCD token generation | Interactive CLI | `bootstrap.sh` |
| DT API token creation | HTTP API calls | `scripts/dynatrace.py` |
| DT asset upload | HTTP API + OAuth | `scripts/dynatrace.py` |
| Wait for resources | Polling | `kubectl wait` in shell |

---

## Validation

Test kustomize output without applying:
```bash
# Preview manifests
kustomize build gitops/manifests/overlays/minikube

# Preview applications
kustomize build gitops/applications/overlays/minikube

# Diff against cluster
kustomize build gitops/manifests/overlays/minikube | kubectl diff -f -
```

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Python code | ~1100 LOC | ~100 LOC |
| Shell code | 0 | ~50 LOC |
| Kustomize files | 3 | ~15 |
| Add new env | 5+ locations | 2 files |
| File mutations | Yes (git commits) | No |
| Secret handling | Hardcoded | File-based |
| Component toggles | File rename | Declarative |
