# Architecture Document: Codespaces-to-Minikube Migration

*Based on arc42 template - focused sections for infrastructure migration*

---

## 1. Introduction and Goals

### 1.1 Requirements Overview

Migrate the IDP demo from GitHub Codespaces/Kind to minikube while preserving:
- GitOps deployment via ArgoCD (sync waves 0-6)
- In-cluster Backstage developer portal
- Dynatrace + OpenTelemetry observability (optional)
- Per-namespace security isolation

See [requirements.md](requirements.md) for detailed REQ-1 through REQ-8.

### 1.2 Quality Goals

| Priority | Quality Goal | Scenario |
|----------|--------------|----------|
| 1 | **Portability** | Platform runs on any machine with minikube installed |
| 2 | **Maintainability** | Single codebase supports Codespaces AND minikube |
| 3 | **Reliability** | Validation checkpoints ensure correct deployment |
| 4 | **Flexibility** | Components toggleable for resource-constrained environments |

### 1.3 Stakeholders

| Role | Expectations |
|------|--------------|
| Platform Engineer | Single-command cluster setup, GitOps preserved |
| Developer | Local IDP experience matches Codespaces |
| Demo Presenter | Portable demo for customer presentations |

---

## 2. Architecture Constraints

### 2.1 Technical Constraints

| ID | Constraint | Rationale |
|----|------------|-----------|
| TC-1 | Minikube >= 1.30.0 | Required for ingress addon, metrics-server |
| TC-2 | Docker or Podman driver | Minikube container runtime |
| TC-3 | Python 3.8+ | Installer script compatibility |
| TC-4 | 4GB RAM, 2 CPUs minimum | Platform component requirements |
| TC-5 | kubectl >= 1.27.0 | API compatibility |

### 2.2 Organizational Constraints

| ID | Constraint | Rationale |
|----|------------|-----------|
| OC-1 | Preserve existing sync wave ordering | Minimize disruption to GitOps flow |
| OC-2 | Codespaces remains supported | Existing users unaffected |
| OC-3 | No changes to Backstage scaffolder templates | Application onboarding unchanged |

---

## 3. Context and Scope

### 3.1 Business Context

```
┌─────────────────────────────────────────────────────────────────┐
│                     Developer Workstation                        │
│  ┌───────────────┐                                              │
│  │   minikube    │◄─── kubectl, browser                         │
│  │   cluster     │                                              │
│  │  ┌─────────┐  │     ┌─────────────┐                         │
│  │  │ ArgoCD  │◄─┼─────│ Git Repo    │ (GitOps source)         │
│  │  └─────────┘  │     └─────────────┘                         │
│  │  ┌─────────┐  │                                              │
│  │  │Backstage│◄─┼───── Developer (self-service portal)        │
│  │  └─────────┘  │                                              │
│  │  ┌─────────┐  │     ┌─────────────┐                         │
│  │  │  OTEL   │──┼────►│ Dynatrace   │ (optional)              │
│  │  └─────────┘  │     └─────────────┘                         │
│  └───────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Technical Context

| Interface | Protocol | Port | Purpose |
|-----------|----------|------|---------|
| ArgoCD UI | HTTPS/HTTP | 30100 | GitOps management |
| Backstage UI | HTTPS/HTTP | 30105 | Developer portal |
| Demo Apps | HTTP | 80 | Customer applications |
| OTEL gRPC | gRPC | 4317 | Trace ingestion |
| OTEL HTTP | HTTP | 4318 | Trace ingestion |

---

## 4. Solution Strategy

### 4.1 Selected Approach: Hybrid Helm for Applications

**Decision**: Use Helm to manage ArgoCD Application definitions while preserving Kustomize for platform manifests.

**Rationale**:
1. Replaced ~170 lines of Kustomize JSON patches with ~55 lines of Helm template
2. Adding new environments requires only 1 values file (vs. full overlay directory)
3. Single source of truth for all 11 platform applications in `gitops/platform-apps/`
4. Preserves existing Kustomize manifests - no migration risk
5. Supports 4 application source patterns: local, localMulti, helm, multiSource

**Implementation**:
- `gitops/platform-apps/` Helm chart manages all 11 ArgoCD Applications
- Per-environment values files: `values-minikube.yaml`, `values-codespaces.yaml`, `values-kind.yaml`
- Root applications (`platform-minikube.yml`, `platform-codespaces.yml`) use Helm source type

### 4.2 Key Architectural Decisions

| ADR | Decision | Alternatives Rejected |
|-----|----------|----------------------|
| ADR-1 | Environment abstraction via Python classes | Direct CLI replacement (fragile), Full Kustomize (too much effort) |
| ADR-2 | Profile-based configuration (YAML) | Environment variables only (limited), Hardcoded values (inflexible) |
| ADR-3 | Minikube ingress addon | Custom NGINX install (complexity), NodePort only (no path routing) |
| ADR-4 | Self-signed certificates via cert-manager | No TLS (insecure), Manual certs (maintenance) |
| ADR-5 | `secrets-minikube.yaml` gitignored fallback | ESO-only (requires cloud backend), Plain secrets (no abstraction) |

---

## 5. Building Block View

### 5.1 Level 1: Platform Applications Helm Chart

```
┌─────────────────────────────────────────────────────────────────────┐
│                    gitops/platform-apps/ (Helm Chart)                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │  Chart.yaml    │  │  values.yaml   │  │  values-{env}.yaml     │ │
│  │  (metadata)    │  │  (11 apps)     │  │  (env overrides)       │ │
│  └────────────────┘  └───────┬────────┘  └───────────┬────────────┘ │
│                              │                       │              │
│                      ┌───────▼───────────────────────▼────────────┐ │
│                      │        templates/applications.yaml          │ │
│                      │     (renders all 11 ArgoCD Applications)    │ │
│                      └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Level 2: Application Source Patterns

| Pattern | Source Type | Applications | Description |
|---------|-------------|--------------|-------------|
| A | `local` | namespaces, argoconfig, dynatrace, ingress-nginx, argo-rollouts, backstage | `spec.source` pointing to local Kustomize path |
| A2 | `localMulti` | kubeaudit | `spec.sources[0]` for API consistency |
| B | `helm` | cert-manager, workflows, openfeature | External Helm chart only |
| C | `multiSource` | opentelemetry | Both local path and external Helm chart |

### 5.3 Environment Values Structure

```yaml
# values.yaml - Default values for all environments
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "main"
  project: "default"
  server: "https://kubernetes.default.svc"

applications:
  namespaces:
    enabled: true
    syncWave: "1"
    sourceType: "local"
    path: "gitops/manifests/platform/namespaces"
    namespace: "argocd"
  # ... (11 applications total)

# values-minikube.yaml - Environment override
global:
  targetRevision: "gh_opus_kostumize2helm"  # Feature branch
```

---

## 6. Runtime View

### 6.1 Cluster Setup Sequence

```
User                minikube_installer.py          minikube CLI         kubectl
 │                          │                          │                   │
 │──run installer──────────►│                          │                   │
 │                          │──detect environment─────►│                   │
 │                          │◄─────minikube found──────│                   │
 │                          │                          │                   │
 │                          │──load profile───────────►│                   │
 │                          │◄────minikube.yaml────────│                   │
 │                          │                          │                   │
 │                          │──minikube start─────────►│                   │
 │                          │◄────cluster ready────────│                   │
 │                          │                          │                   │
 │                          │──enable addons──────────►│                   │
 │                          │◄────addons enabled───────│                   │
 │                          │                          │                   │
 │                          │──────────────────────────┼──create secrets──►│
 │                          │                          │                   │
 │                          │──────────────────────────┼──apply argocd────►│
 │                          │                          │                   │
 │◄───setup complete────────│                          │                   │
```

### 6.2 Validation Checkpoint Sequence

```
Phase 1: Cluster        → minikube status | grep Running
Phase 2: Namespaces     → kubectl get ns | grep -E "argocd|backstage"
Phase 3: ArgoCD         → curl http://$(minikube ip):30100
Phase 4: Secrets        → kubectl get secrets -n argocd
Phase 5: Platform Apps  → kubectl get applications -n argocd | grep Synced
Phase 6: Backstage      → curl http://$(minikube ip):30105
Phase 7: OTEL           → kubectl get pods -n opentelemetry | grep Running
Phase 8: Ingress        → curl http://$(minikube ip)
Phase 9: Customer App   → Create app via Backstage UI
Phase 10: Security      → kubectl get networkpolicies -A
```

---

## 7. Deployment View

### 7.1 Infrastructure Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Developer Workstation                           │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     minikube VM/Container                        ││
│  │  ┌──────────────────────────────────────────────────────────┐   ││
│  │  │                  Kubernetes Cluster                       │   ││
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │   ││
│  │  │  │   argocd    │ │  backstage  │ │    opentelemetry    │ │   ││
│  │  │  │  namespace  │ │  namespace  │ │     namespace       │ │   ││
│  │  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │   ││
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │   ││
│  │  │  │cert-manager │ │   ingress   │ │   customer-apps/*   │ │   ││
│  │  │  │  namespace  │ │  namespace  │ │    namespaces       │ │   ││
│  │  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │   ││
│  │  └──────────────────────────────────────────────────────────┘   ││
│  │                              │                                   ││
│  │                      NodePort Services                           ││
│  │                    30100, 30105, 80                              ││
│  └──────────────────────────────┼──────────────────────────────────┘│
│                                 │                                    │
│                          localhost:30100 (ArgoCD)                    │
│                          localhost:30105 (Backstage)                 │
│                          localhost:80 (Apps via Ingress)             │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Port Mapping Strategy

| Service | NodePort | Access Method |
|---------|----------|---------------|
| ArgoCD | 30100 | `minikube service argocd-server -n argocd --url` or `localhost:30100` |
| Backstage | 30105 | `minikube service backstage -n backstage --url` or `localhost:30105` |
| Demo Apps | 80 | Ingress controller → `http://$(minikube ip)/app-path` |

---

## 8. Cross-cutting Concepts

### 8.1 Environment Detection Strategy

```python
# Pseudocode for environment detection
def detect_environment():
    if os.getenv("CODESPACE_NAME"):
        return CodespacesEnvironment()
    elif shutil.which("minikube"):
        return MinikubeEnvironment()
    else:
        raise EnvironmentNotSupportedError("No supported environment detected")
```

### 8.2 URL Substitution Pattern

| Placeholder | Codespaces Value | Minikube Value |
|-------------|------------------|----------------|
| `CODESPACE_NAME_PLACEHOLDER` | `${CODESPACE_NAME}` | `minikube` |
| `BASE_DOMAIN_PLACEHOLDER` | `${CODESPACE_NAME}-80.app.github.dev` | `$(minikube ip).nip.io` or `localhost` |
| `ARGOCD_URL_PLACEHOLDER` | `https://${CODESPACE_NAME}-30100.app.github.dev` | `http://localhost:30100` |
| `BACKSTAGE_URL_PLACEHOLDER` | `https://${CODESPACE_NAME}-30105.app.github.dev` | `http://localhost:30105` |

### 8.3 Secrets Management

```
┌─────────────────────────────────────────────────────────────────┐
│                     Secrets Flow                                 │
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │secrets-minikube  │     │ External Secrets │                  │
│  │    .yaml         │     │    Operator      │                  │
│  │  (gitignored)    │     │  (cloud backend) │                  │
│  └────────┬─────────┘     └────────┬─────────┘                  │
│           │                        │                             │
│           └──────────┬─────────────┘                             │
│                      ▼                                           │
│           ┌──────────────────┐                                   │
│           │  SecretsManager  │                                   │
│           │  (abstraction)   │                                   │
│           └────────┬─────────┘                                   │
│                    ▼                                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Kubernetes Secrets                             │ │
│  │  argocd/github-token  backstage/backstage-secrets          │ │
│  │  dynatrace/tokens     opentelemetry/dt-credentials         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 8.4 Component Toggle Mechanism

```yaml
# In profile or environment variables
components:
  keptn: ${INSTALL_KEPTN:-false}
  openfeature: ${INSTALL_OPENFEATURE:-false}
  kubeaudit_cronjobs: ${INSTALL_KUBEAUDIT:-false}
  dynatrace: ${INSTALL_DYNATRACE:-true}  # Optional, graceful degradation
```

Implementation: ArgoCD Application manifests include conditional sync based on component flags.

---

## 9. Architecture Decisions

### ADR-1: Environment Abstraction over Direct CLI Replacement

**Context**: Need to support both Codespaces and minikube environments.

**Decision**: Create an abstraction layer with environment-specific implementations rather than forking the installer script.

**Consequences**:
- (+) Single codebase to maintain
- (+) Easy to add new environments (EKS, GKE)
- (+) Clear separation of concerns
- (-) Additional abstraction layer complexity

### ADR-2: NodePort + Ingress Hybrid Access

**Context**: Need to expose services for local access without external load balancer.

**Decision**: Use NodePort for ArgoCD/Backstage (stable ports), Ingress for demo apps (path-based routing).

**Consequences**:
- (+) Predictable ports for management UIs
- (+) Flexible path-based routing for apps
- (-) Requires minikube ingress addon

### ADR-3: nip.io for DNS Resolution

**Context**: Need DNS names for ingress without modifying /etc/hosts.

**Decision**: Use `$(minikube ip).nip.io` for automatic DNS resolution.

**Consequences**:
- (+) No host file modifications required
- (+) Works with wildcard certificates
- (-) Requires internet connectivity for DNS resolution
- (-) Alternative: `localhost` with `minikube tunnel`

---

## 10. Quality Requirements

### 10.1 Quality Scenarios

| ID | Quality | Scenario | Measure |
|----|---------|----------|---------|
| QS-1 | Portability | Developer runs platform on MacOS, Linux, Windows | Platform starts successfully on all three |
| QS-2 | Reliability | Network interruption during setup | Setup can be resumed without corruption |
| QS-3 | Performance | Cluster startup time | < 5 minutes on recommended hardware |
| QS-4 | Usability | First-time setup | Single command, clear error messages |

---

## 11. Risks and Technical Debt

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Minikube driver compatibility | Medium | High | Document tested drivers (docker, podman) |
| Memory constraints on developer machines | High | Medium | Component toggles, resource limits |
| nip.io DNS availability | Low | Medium | Fallback to localhost + tunnel |
| Divergence between Codespaces and minikube | Medium | High | Shared test suite, CI for both |

---

## 12. Glossary

| Term | Definition |
|------|------------|
| IDP | Internal Development Platform |
| GitOps | Infrastructure and application deployment via Git |
| Sync Wave | ArgoCD ordering mechanism for dependent applications |
| ESO | External Secrets Operator |
| nip.io | Wildcard DNS service that maps IPs to hostnames |
| NodePort | Kubernetes service type exposing on static port |
