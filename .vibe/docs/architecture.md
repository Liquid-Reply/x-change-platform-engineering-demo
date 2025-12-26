# Architecture Document: Multi-Environment IDP

*Based on arc42 template - focused on infrastructure and GitOps*

---

## 1. Introduction and Goals

### 1.1 Requirements Overview

The IDP demo supports three Kubernetes environments:
- **GitHub Codespaces** - Cloud-based development
- **minikube** - Local VM-based Kubernetes
- **Kind** - Kubernetes in Docker (lightweight local)

All environments use `bootstrap.sh` as the single entry point with environment-specific configurations.

### 1.2 Quality Goals

| Priority | Quality Goal | Scenario |
|----------|--------------|----------|
| 1 | **Portability** | Platform runs on any machine with Docker |
| 2 | **Maintainability** | Single bootstrap script supports all environments |
| 3 | **Reliability** | Validation checkpoints ensure correct deployment |
| 4 | **Flexibility** | Components toggleable for resource-constrained environments |

---

## 2. Architecture Constraints

### 2.1 Technical Constraints

| ID | Constraint | Rationale |
|----|------------|-----------|
| TC-1 | Docker required | Required for Kind, optional for minikube |
| TC-2 | 4GB RAM, 2 CPUs minimum | Platform component requirements |
| TC-3 | kubectl >= 1.27.0 | API compatibility |
| TC-4 | Helm >= 3.0 | ArgoCD Application management |

### 2.2 Organizational Constraints

| ID | Constraint | Rationale |
|----|------------|-----------|
| OC-1 | Preserve existing sync wave ordering | Minimize disruption to GitOps flow |
| OC-2 | All environments supported equally | Same features across minikube/Kind/Codespaces |
| OC-3 | No changes to Backstage scaffolder templates | Application onboarding unchanged |

---

## 3. Context and Scope

### 3.1 System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                     Developer Workstation                        │
│  ┌───────────────┐                                              │
│  │   Kind or     │◄─── kubectl, browser                         │
│  │   minikube    │                                              │
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
| ArgoCD UI | HTTP | 30100 | GitOps management |
| Backstage UI | HTTP | 30105 | Developer portal |
| Demo Apps | HTTP | 80 | Customer applications |
| OTEL gRPC | gRPC | 4317 | Trace ingestion |
| OTEL HTTP | HTTP | 4318 | Trace ingestion |

---

## 4. Solution Strategy

### 4.1 Implementation Approach: Bootstrap + Helm

**Decision**: Use `bootstrap.sh` + Helm chart for ArgoCD Applications.

**Key Components**:
1. `bootstrap.sh` - Single entry point for all environments
2. `gitops/platform-apps/` - Helm chart managing 11 ArgoCD Applications
3. `gitops/platform-{env}.yml` - Per-environment root Application
4. `config/{env}.env` - Per-environment variables

**Rationale**:
- Single codebase supports all environments
- Adding new environment requires only: values file + root app + env config
- Preserves existing Kustomize manifests

### 4.2 Key Architectural Decisions

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-1 | bootstrap.sh as single entry point | Simple, shell-native, no Python dependencies |
| ADR-2 | Helm for ArgoCD Applications | Declarative, environment-specific values |
| ADR-3 | Per-environment root applications | Clean separation, easy to add environments |
| ADR-4 | Image preloading for Kind | Faster deployments, offline capability |

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

### 5.2 Application Source Patterns

| Pattern | Source Type | Applications |
|---------|-------------|--------------|
| local | `spec.source` with local path | namespaces, argoconfig, dynatrace, ingress-nginx, argo-rollouts, backstage |
| localMulti | `spec.sources[0]` | kubeaudit |
| helm | External Helm chart only | cert-manager, workflows, openfeature |
| multiSource | Local + external Helm | opentelemetry |

### 5.3 File Structure

```
gitops/
├── platform-minikube.yml      # Root Application (minikube)
├── platform-kind.yml          # Root Application (Kind)
├── platform-codespaces.yml    # Root Application (Codespaces)
├── platform-apps/             # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml            # Default values (11 apps)
│   ├── values-minikube.yaml   # Minikube overrides
│   ├── values-kind.yaml       # Kind overrides
│   ├── values-codespaces.yaml # Codespaces overrides
│   └── templates/
│       ├── _helpers.tpl
│       └── applications.yaml
└── manifests/platform/        # Kustomize manifests (unchanged)

config/
├── minikube.env               # Minikube environment variables
├── kind.env                   # Kind environment variables
└── codespaces.env             # Codespaces environment variables

secrets/
├── minikube.env               # Minikube secrets (gitignored)
├── kind.env                   # Kind secrets (gitignored)
└── template.env               # Template for secrets
```

---

## 6. Runtime View

### 6.1 Bootstrap Sequence

```
User                    bootstrap.sh              Cluster CLI        kubectl
 │                          │                          │                │
 │──./bootstrap.sh kind────►│                          │                │
 │                          │                          │                │
 │                          │──source config/kind.env─►│                │
 │                          │                          │                │
 │                          │──kind create cluster────►│                │
 │                          │◄────cluster ready────────│                │
 │                          │                          │                │
 │                          │──kind load docker-image─►│ (image preload)│
 │                          │                          │                │
 │                          │──────────────────────────┼──create ns────►│
 │                          │                          │                │
 │                          │──────────────────────────┼──install argo──►│
 │                          │                          │                │
 │                          │──────────────────────────┼──apply root app►│
 │                          │                          │                │
 │◄───setup complete────────│                          │                │
```

### 6.2 Validation Checkpoints

| Phase | Checkpoint | Command |
|-------|------------|---------|
| 1 | Cluster running | `kubectl get nodes` |
| 2 | Namespaces created | `kubectl get ns` |
| 3 | ArgoCD accessible | `curl http://localhost:30100` |
| 4 | Secrets exist | `kubectl get secrets -n argocd` |
| 5 | Platform apps synced | `kubectl get applications -n argocd` |
| 6 | Backstage accessible | `curl http://localhost:30105` |

---

## 7. Deployment View

### 7.1 Infrastructure Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Developer Workstation                           │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                 Kind/minikube Cluster                            ││
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

---

## 8. Cross-cutting Concepts

### 8.1 Environment Configuration

| Environment | Cluster Type | Base URL | Image Loading |
|-------------|--------------|----------|---------------|
| minikube | VM | `$(minikube ip)` or `localhost` | `minikube image load` |
| Kind | Docker | `localhost` | `kind load docker-image` |
| Codespaces | Cloud | `*.app.github.dev` | N/A (cloud) |

### 8.2 Graceful Degradation

| Component | Missing Condition | Behavior |
|-----------|-------------------|----------|
| Dynatrace | No DT credentials | Skip Dynatrace apps, log info |
| Keptn | `INSTALL_KEPTN=false` | Skip Keptn installation |
| OTEL | No DT endpoint | Deploy collector in standalone mode |

---

## 9. Risks and Technical Debt

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Docker driver compatibility | Medium | High | Document tested configurations |
| Memory constraints | High | Medium | Component toggles, resource limits |
| Network issues in Kind | Medium | Medium | Image preloading reduces external deps |

---

## 10. Glossary

| Term | Definition |
|------|------------|
| IDP | Internal Development Platform |
| GitOps | Infrastructure and application deployment via Git |
| Kind | Kubernetes in Docker - runs K8s using Docker containers |
| Sync Wave | ArgoCD ordering mechanism for dependent applications |
| NodePort | Kubernetes service type exposing on static port |
| HostPort | Docker port mapping exposing container ports to host |
