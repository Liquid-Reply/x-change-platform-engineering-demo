# Requirements Document: Codespaces-to-Minikube Migration

## Executive Summary

This document defines the requirements for migrating the x-change-platform-engineering-demo IDP (Internal Development Platform) from GitHub Codespaces/Kind to minikube, enabling portable local Kubernetes development.

---

## REQ-1: Cluster Lifecycle Management

**User Story:** As a platform engineer, I want to create and manage a minikube cluster with a single command so that I can quickly set up the IDP demo locally.

**Acceptance Criteria:**

- WHEN the user runs `minikube_installer.py` (or equivalent) THEN the IDP SHALL create a minikube cluster with required addons (ingress, metrics-server)
- WHEN the cluster already exists THEN the IDP SHALL offer to delete and recreate OR reuse existing cluster
- WHEN minikube is not installed THEN the IDP SHALL display clear installation instructions
- WHILE the cluster is being created, WHEN port mappings are configured THEN the IDP SHALL expose ports 30100 (ArgoCD), 30105 (Backstage), and 80 (apps)

**Validation Checkpoint:**
```bash
# Test: Cluster creation succeeds
minikube status | grep -q "Running"
kubectl get nodes | grep -q "Ready"
```

---

## REQ-2: Environment-Agnostic Configuration

**User Story:** As a developer, I want the platform to work with minimal host-specific assumptions so that I can run it on any machine with minikube installed.

**Acceptance Criteria:**

- WHEN deploying to minikube THEN the IDP SHALL NOT require `CODESPACE_NAME` environment variable
- WHEN deploying to minikube THEN the IDP SHALL NOT require `GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN`
- WHEN deploying locally THEN the IDP SHALL use `localhost` or `$(minikube ip)` as the base domain
- WHEN configuration placeholders are processed THEN the IDP SHALL support both Codespaces AND minikube environments via overlay/profile mechanism

**Validation Checkpoint:**
```bash
# Test: No Codespaces-specific variables required
env | grep -v CODESPACE | grep -v GITHUB_CODESPACES
python3 minikube_installer.py  # Should succeed without Codespaces env vars
```

---

## REQ-3: GitOps Preservation

**User Story:** As a platform engineer, I want ArgoCD to manage all platform components via GitOps so that the deployment remains declarative and auditable.

**Acceptance Criteria:**

- WHEN ArgoCD is deployed THEN the IDP SHALL maintain the existing sync wave ordering (Waves 0-6)
- WHEN a new application is onboarded THEN the IDP SHALL use the existing ApplicationSet discovery pattern
- WHEN manifests are modified THEN ArgoCD SHALL detect and sync changes automatically
- WHILE ArgoCD is running THEN the IDP SHALL provide access via `http://localhost:30100` or `http://$(minikube ip):30100`

**Validation Checkpoint:**
```bash
# Test: ArgoCD is accessible and applications are synced
kubectl get applications -n argocd | grep -q "Synced"
curl -s http://$(minikube ip):30100 | grep -q "Argo CD"
```

---

## REQ-4: Backstage In-Cluster Deployment

**User Story:** As a developer, I want Backstage to run in-cluster and be accessible locally so that I can use the self-service portal for application onboarding.

**Acceptance Criteria:**

- WHEN Backstage is deployed THEN the IDP SHALL run Backstage in the `backstage` namespace
- WHEN Backstage is deployed THEN the IDP SHALL configure URLs for local access (not Codespaces domains)
- WHEN Backstage is running THEN the IDP SHALL provide access via `http://localhost:30105` or `http://$(minikube ip):30105`
- WHEN the Software Catalog is loaded THEN Backstage SHALL discover entities from the git repository

**Validation Checkpoint:**
```bash
# Test: Backstage is accessible and functional
kubectl get pods -n backstage | grep -q "Running"
curl -s http://$(minikube ip):30105 | grep -q "Backstage"
```

---

## REQ-5: Observability Integration

**User Story:** As a platform engineer, I want Dynatrace and OpenTelemetry integration to work locally so that I can demonstrate observability capabilities.

**Acceptance Criteria:**

- WHEN Dynatrace credentials are provided THEN the IDP SHALL configure OneAgent and OTEL collector
- IF Dynatrace credentials are NOT provided THEN the IDP SHALL skip Dynatrace components gracefully
- WHEN OTEL collector is deployed THEN the IDP SHALL accept traces on ports 4317 (gRPC) and 4318 (HTTP)
- WHEN Monaco configurations are applied THEN the IDP SHALL create Dynatrace dashboards, SLOs, and synthetic monitors

**Validation Checkpoint:**
```bash
# Test: OTEL collector is running (Dynatrace optional)
kubectl get pods -n opentelemetry | grep -q "Running"
# Test: Can send test trace
curl -X POST http://$(minikube ip):4318/v1/traces -H "Content-Type: application/json" -d '{}'
```

---

## REQ-6: Secrets Management

**User Story:** As a developer, I want flexible secrets management so that I can use simple local secrets for development and ESO for production-like setups.

**Acceptance Criteria:**

- WHEN deploying locally THEN the IDP SHALL support a gitignored `secrets-minikube.yaml` file
- WHERE External Secrets Operator is available THEN the IDP SHALL support ESO with AWS/GCP/Azure/Vault backends
- WHEN secrets are created THEN the IDP SHALL create them in the appropriate namespaces (argocd, backstage, dynatrace, opentelemetry, monaco)
- WHEN tokens expire THEN the IDP SHALL provide a renewal mechanism (`renew_api_token.py` or equivalent)

**Validation Checkpoint:**
```bash
# Test: Required secrets exist
kubectl get secrets -n argocd | grep -q "github-token"
kubectl get secrets -n backstage | grep -q "backstage-secrets"
# Test: Secrets-minikube.yaml is gitignored
grep -q "secrets-minikube.yaml" .gitignore
```

---

## REQ-7: Component Toggle Support

**User Story:** As a developer running on limited resources, I want to disable non-essential components so that the platform runs efficiently on minikube.

**Acceptance Criteria:**

- WHEN `INSTALL_KEPTN=false` THEN the IDP SHALL skip Keptn installation
- WHERE resources are limited THEN the IDP SHALL support disabling: Keptn, OpenFeature, KubeAudit cronjobs
- WHEN a component is disabled THEN ArgoCD SHALL NOT create an Application for that component
- WHEN all essential components are enabled THEN the IDP SHALL deploy: ArgoCD, Backstage, Ingress, cert-manager, OTEL

**Validation Checkpoint:**
```bash
# Test: Component toggle works
INSTALL_KEPTN=false python3 minikube_installer.py
kubectl get applications -n argocd | grep -v keptn  # Keptn should not exist
```

---

## REQ-8: Security and Isolation

**User Story:** As a platform engineer, I want per-namespace isolation for customer applications so that multi-tenant security is demonstrated.

**Acceptance Criteria:**

- WHEN a customer app namespace is created THEN the IDP SHALL apply NetworkPolicies
- WHEN a customer app namespace is created THEN the IDP SHALL enforce PodSecurity admission (baseline or restricted)
- WHERE image policy controls are available THEN the IDP SHALL restrict allowed image registries
- WHEN deploying to minikube THEN the IDP SHALL use cert-manager with self-signed certificates

**Validation Checkpoint:**
```bash
# Test: NetworkPolicies exist for customer namespaces
kubectl get networkpolicies -A | grep -q "customer"
# Test: PodSecurity is enforced
kubectl get ns customer-app-namespace -o yaml | grep -q "pod-security"
```

---

## Scope Definition

### In-Scope
- Minikube cluster creation and configuration
- ArgoCD GitOps deployment (existing sync waves)
- Backstage in-cluster with local URLs
- Dynatrace/OTEL integration (optional, graceful degradation)
- Secrets management (local fallback + ESO-ready)
- Component toggles (Keptn, OpenFeature, KubeAudit)
- Per-namespace security (NetworkPolicies, PodSecurity)
- cert-manager with self-signed certificates
- Application templating (preserve Backstage scaffolder placeholders)

### Out-of-Scope
- Production deployment configurations
- Multi-cluster federation
- External DNS integration
- Cloud-specific load balancers
- ACME certificate issuance (self-signed acceptable)
- GitHub Actions workflow modifications
- Codespaces environment removal (becomes optional overlay)

---

## Constraints and Dependencies

### Technical Constraints
| Constraint | Description |
|------------|-------------|
| TC-1 | Minikube must be installed on host machine |
| TC-2 | Docker or Podman driver required for minikube |
| TC-3 | Minimum 4GB RAM, 2 CPUs for minikube VM |
| TC-4 | kubectl must be installed and configured |
| TC-5 | Python 3.8+ required for installer scripts |

### External Dependencies
| Dependency | Version | Purpose |
|------------|---------|---------|
| minikube | >= 1.30.0 | Local Kubernetes cluster |
| kubectl | >= 1.27.0 | Kubernetes CLI |
| ArgoCD | 2.12.2 | GitOps deployment |
| Backstage | (as defined) | Developer portal |
| cert-manager | >= 1.12.0 | Certificate management |
| NGINX Ingress | (as defined) | Ingress controller |

---

## Refactoring Options Analysis

### Option A: Minimal Adaptation (Lowest Effort)
**Approach**: Replace Kind commands with minikube equivalents; substitute Codespaces placeholders with localhost/minikube-ip.

| Aspect | Details |
|--------|---------|
| **Changes** | Modify `cluster_installer.py` to use minikube CLI; update placeholder values |
| **Pros** | Minimal code changes; quick to implement |
| **Cons** | Maintains imperative substitution pattern; two code paths to maintain |
| **Effort** | Low (1-2 days) |
| **Risk** | Medium - divergent codepaths may cause maintenance burden |

**Files Modified**:
- `cluster_installer.py` (~50 lines)
- `utils.py` (~20 lines)
- `.devcontainer/` → `.minikube/` (new directory)

### Option B: Environment Abstraction Layer (Medium Effort)
**Approach**: Introduce an abstraction layer that detects environment (Codespaces vs minikube vs generic K8s) and configures accordingly.

| Aspect | Details |
|--------|---------|
| **Changes** | New `environment.py` module; config profiles; conditional logic |
| **Pros** | Single codebase supports multiple environments; extensible |
| **Cons** | More complex; requires refactoring existing scripts |
| **Effort** | Medium (3-5 days) |
| **Risk** | Low-Medium - well-tested abstraction reduces errors |

**New Files**:
- `environments/base.py` - Abstract environment class
- `environments/codespaces.py` - Codespaces-specific config
- `environments/minikube.py` - Minikube-specific config
- `config/profiles/` - Environment profile YAML files

### Option C: Full Declarative/Controller-Based (Highest Effort, Most Stable)
**Approach**: Replace imperative `cluster_installer.py` with Kubernetes-native declarative configuration using Kustomize overlays or Helm values.

| Aspect | Details |
|--------|---------|
| **Changes** | Kustomize base + overlays; ArgoCD ApplicationSets with generators; ConfigMap-driven configuration |
| **Pros** | Fully declarative; GitOps-native; no imperative scripts for manifest generation |
| **Cons** | Significant refactoring; learning curve for Kustomize patterns |
| **Effort** | High (1-2 weeks) |
| **Risk** | Low - declarative approach is more predictable |

**New Structure**:
```
gitops/
  base/                    # Base manifests
  overlays/
    codespaces/            # Codespaces-specific patches
    minikube/              # Minikube-specific patches
  kustomization.yaml
```

### Recommended Approach: Option B (Environment Abstraction)

**Rationale**:
1. Balances effort vs. stability
2. Maintains existing code structure (familiar)
3. Enables future environment additions (EKS, GKE, AKS)
4. Preserves imperative token creation (required for Dynatrace API)
5. Allows incremental migration toward Option C

---

## Validation Checkpoints Summary

| Phase | Checkpoint | Validation Command |
|-------|------------|-------------------|
| 1. Cluster | Minikube running | `minikube status` |
| 2. Namespaces | All namespaces created | `kubectl get ns` |
| 3. ArgoCD | ArgoCD accessible | `curl http://$(minikube ip):30100` |
| 4. Secrets | All secrets exist | `kubectl get secrets -A` |
| 5. Platform Apps | All apps synced | `kubectl get applications -n argocd` |
| 6. Backstage | Backstage accessible | `curl http://$(minikube ip):30105` |
| 7. OTEL | Collector running | `kubectl get pods -n opentelemetry` |
| 8. Ingress | Ingress functional | `curl http://$(minikube ip)` |
| 9. Customer App | App onboarding works | Create app via Backstage |
| 10. Security | Policies applied | `kubectl get networkpolicies -A` |

