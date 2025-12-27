# Architecture Document: Gateway API Migration

*Based on arc42 template - focused on Gateway API target architecture*

---

## 1. Introduction and Goals

### 1.1 Requirements Overview

This architecture documents the migration from NGINX Ingress Controller to **Kubernetes Gateway API** using **Envoy Gateway** as the implementation. The Gateway API provides a standardized, extensible approach to traffic management that supersedes the legacy Ingress API.

**Migration Timeline**: NGINX Ingress Controller retirement March 2026

### 1.2 Quality Goals

| Priority | Quality Goal | Scenario |
|----------|--------------|----------|
| 1 | **Standardization** | Use Kubernetes Gateway API v1 (GA) for all ingress traffic |
| 2 | **Traffic Control** | Weight-based canary deployments via HTTPRoute |
| 3 | **Extensibility** | Platform ready for future Gateway API features (GRPCRoute, policies) |
| 4 | **GitOps Native** | All Gateway resources managed via ArgoCD |

### 1.3 Stakeholders

| Role | Concern |
|------|---------|
| Platform Engineers | Gateway configuration, Argo Rollouts integration |
| Developers | HTTPRoute templates via Backstage |
| SRE | Traffic observability, rollback procedures |

---

## 2. Architecture Constraints

### 2.1 Technical Constraints

| ID | Constraint | Rationale | Validated |
|----|------------|-----------|-----------|
| TC-GW-1 | Gateway API v1.0+ | GA resources required for production | Yes |
| TC-GW-2 | Envoy Gateway v1.3.0+ | Full Gateway API conformance | Yes |
| TC-GW-3 | ArgoCD v2.12+ | OCI Helm registry support | Partial* |
| TC-GW-4 | Argo Rollouts v1.6+ | Gateway API plugin support | Yes |
| TC-GW-5 | Kubernetes 1.27+ | Gateway API CRD compatibility | Yes |

*Note: ArgoCD OCI Helm support requires manual Helm installation for Envoy Gateway

### 2.2 Implementation Constraints (Discovered)

| ID | Constraint | Discovery | Workaround |
|----|------------|-----------|------------|
| IC-1 | GatewayClass not auto-created | Helm chart v1.3.0 does not create GatewayClass | Include GatewayClass in manifests |
| IC-2 | OCI Helm in ArgoCD | ArgoCD v2.12.2 has OCI registry issues | Install Envoy Gateway via Helm CLI |
| IC-3 | LoadBalancer pending in Kind/minikube | No cloud LoadBalancer provider | Use NodePort or port-forward |

### 2.3 Organizational Constraints

| ID | Constraint | Rationale |
|----|------------|-----------|
| OC-1 | Sync Wave 3 for Gateway | Deploy with other networking components |
| OC-2 | Backstage templates generate HTTPRoute | Developer self-service unchanged |
| OC-3 | Argo Rollouts manages traffic weights | Canary deployments via HTTPRoute |

---

## 3. System Context

### 3.1 Target Architecture Context

```
                    ┌─────────────────────────────────────────────────────┐
                    │                  External Traffic                    │
                    │              (HTTP/HTTPS requests)                   │
                    └─────────────────────┬───────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              Envoy Gateway Service                   │
                    │           (NodePort 80 / LoadBalancer)               │
                    │            Namespace: envoy-gateway-system           │
                    └─────────────────────┬───────────────────────────────┘
                                          │
                    ┌─────────────────────▼───────────────────────────────┐
                    │                                                      │
                    │  ┌────────────────────────────────────────────────┐ │
                    │  │            Gateway Controller                   │ │
                    │  │     (watches GatewayClass, Gateway, HTTPRoute)  │ │
                    │  └────────────────────┬───────────────────────────┘ │
                    │                       │                              │
                    │  ┌────────────────────▼───────────────────────────┐ │
                    │  │              Envoy Proxy Pods                   │ │
                    │  │         (data plane - routes traffic)           │ │
                    │  └────────────────────┬───────────────────────────┘ │
                    │                       │                              │
                    └───────────────────────┼──────────────────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              │                             │                             │
              ▼                             ▼                             ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │   HTTPRoute A   │         │   HTTPRoute B   │         │   HTTPRoute C   │
    │  /app-a-prod    │         │  /app-b-prod    │         │  /app-c-prod    │
    │ (ns: app-a-prod)│         │ (ns: app-b-prod)│         │ (ns: app-c-prod)│
    └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
             │                           │                           │
    ┌────────▼────────┐         ┌────────▼────────┐         ┌────────▼────────┐
    │ stable: 100%    │         │ stable: 70%     │         │ stable: 100%    │
    │ canary: 0%      │         │ canary: 30%     │         │ canary: 0%      │
    │ (Argo Rollouts) │         │ (mid-rollout)   │         │ (Argo Rollouts) │
    └─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 3.2 Component Interactions

| Component | Protocol | Purpose |
|-----------|----------|---------|
| Gateway Controller | Kubernetes API | Watches Gateway API resources |
| Envoy Proxy | HTTP/HTTPS | Routes traffic to backend services |
| Argo Rollouts | Kubernetes API | Updates HTTPRoute weights during canary |
| Backstage | Git | Scaffolds HTTPRoute templates |

---

## 4. Solution Strategy

### 4.1 Gateway API Resource Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            GatewayClass: eg                                  │
│                 controllerName: gateway.envoyproxy.io/gatewayclass-controller│
│                              (cluster-scoped)                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Gateway: platform-gateway                                 │
│                  Namespace: envoy-gateway-system                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Listener: http                                                       │    │
│  │   Protocol: HTTP                                                     │    │
│  │   Port: 80                                                           │    │
│  │   allowedRoutes:                                                     │    │
│  │     namespaces:                                                      │    │
│  │       from: All    ◄─── Accepts HTTPRoutes from any namespace        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌───────────────────────────────┐  ┌───────────────────────────────┐
│ HTTPRoute: app-team1          │  │ HTTPRoute: app-team2          │
│ Namespace: app-team1-prod     │  │ Namespace: app-team2-prod     │
│ parentRefs:                   │  │ parentRefs:                   │
│   - name: platform-gateway    │  │   - name: platform-gateway    │
│     namespace: envoy-gw-sys   │  │     namespace: envoy-gw-sys   │
└───────────────────────────────┘  └───────────────────────────────┘
```

### 4.2 Traffic Routing Pattern

```yaml
# HTTPRoute with Argo Rollouts traffic splitting
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-team1
  namespace: app-team1-prod
spec:
  parentRefs:
  - name: platform-gateway
    namespace: envoy-gateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /app-team1-prod
    filters:
    - type: URLRewrite
      urlRewrite:
        path:
          type: ReplacePrefixMatch
          replacePrefixMatch: /
    backendRefs:
    - name: app-team1-stable    # Managed by Argo Rollouts
      port: 80
      weight: 100               # ◄── Updated during canary
    - name: app-team1-canary    # Managed by Argo Rollouts
      port: 80
      weight: 0                 # ◄── Updated during canary
```

### 4.3 Key Architectural Decisions

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-GW-1 | Single Gateway for all apps | Simplicity; multi-gateway not required |
| ADR-GW-2 | Cross-namespace routing via `from: All` | Apps in own namespaces reference central Gateway |
| ADR-GW-3 | PathPrefix + URLRewrite | Matches NGINX rewrite-target behavior |
| ADR-GW-4 | Stable/Canary Service pattern | Required for Argo Rollouts traffic routing |
| ADR-GW-5 | Envoy Gateway via Helm CLI | ArgoCD OCI issues require manual installation |

---

## 5. Building Block View

### 5.1 Level 1: Platform Gateway Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          envoy-gateway-system namespace                      │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Envoy Gateway Controller                         │ │
│  │                         (Deployment: envoy-gateway)                     │ │
│  │  - Watches: GatewayClass, Gateway, HTTPRoute, Service                   │ │
│  │  - Creates: Envoy Proxy pods per Gateway                                │ │
│  │  - Configures: xDS for Envoy data plane                                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Envoy Proxy Pod (per Gateway)                        │ │
│  │              (envoy-envoy-gateway-system-platform-gateway-*)            │ │
│  │  - Containers: envoy-gateway (sidecar), envoy (proxy)                   │ │
│  │  - Service: LoadBalancer/NodePort exposing port 80                      │ │
│  │  - Receives xDS config from controller                                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Gateway Resource                                │ │
│  │                       (platform-gateway)                                │ │
│  │  - GatewayClass: eg                                                     │ │
│  │  - Listener: http (port 80, protocol HTTP)                              │ │
│  │  - Status: Accepted=True, Programmed=True                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Level 2: Customer Application Namespace

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    app-team1-prod namespace (customer app)                   │
│                                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │     HTTPRoute       │  │   Service: stable   │  │   Service: canary   │  │
│  │   (app-team1)       │  │  (app-team1-stable) │  │  (app-team1-canary) │  │
│  │                     │  │                     │  │                     │  │
│  │ parentRefs:         │  │ selector:           │  │ selector:           │  │
│  │  platform-gateway   │  │  app: userinterface │  │  app: userinterface │  │
│  │                     │  │                     │  │                     │  │
│  │ backendRefs:        │  │ port: 80            │  │ port: 80            │  │
│  │  - stable (100%)    │  │ targetPort: 8080    │  │ targetPort: 8080    │  │
│  │  - canary (0%)      │  │                     │  │                     │  │
│  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘  │
│             │                        │                        │             │
│             │              ┌─────────┴────────────────────────┘             │
│             │              │                                                │
│             │              ▼                                                │
│  ┌──────────▼──────────────────────────────────────────────────────────┐   │
│  │                         Argo Rollout                                 │   │
│  │                        (app-team1)                                   │   │
│  │  strategy:                                                           │   │
│  │    canary:                                                           │   │
│  │      stableService: app-team1-stable                                 │   │
│  │      canaryService: app-team1-canary                                 │   │
│  │      trafficRouting:                                                 │   │
│  │        plugins:                                                      │   │
│  │          argoproj-labs/gatewayAPI:                                   │   │
│  │            httpRoute: app-team1                                      │   │
│  │            namespace: app-team1-prod                                 │   │
│  │      steps:                                                          │   │
│  │        - setWeight: 10  ──► HTTPRoute updated: stable=90, canary=10  │   │
│  │        - pause: 30s                                                  │   │
│  │        - setWeight: 30  ──► HTTPRoute updated: stable=70, canary=30  │   │
│  │        - pause: 30s                                                  │   │
│  │        - setWeight: 100 ──► HTTPRoute updated: stable=0, canary=100  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      ReplicaSet (stable)                              │   │
│  │                      ReplicaSet (canary)                              │   │
│  │               (managed by Argo Rollouts controller)                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Argo Rollouts Gateway API Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          argo-rollouts namespace                             │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Argo Rollouts Controller                             │ │
│  │                                                                         │ │
│  │  ConfigMap: argo-rollouts-config                                        │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │ │
│  │  │ trafficRouterPlugins:                                             │  │ │
│  │  │   - name: "argoproj-labs/gatewayAPI"                              │  │ │
│  │  │     location: "https://github.com/argoproj-labs/                  │  │ │
│  │  │       rollouts-plugin-trafficrouter-gatewayapi/releases/          │  │ │
│  │  │       download/v0.5.0/gateway-api-plugin-linux-amd64"             │  │ │
│  │  └───────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  │  ClusterRole: argo-rollouts-gateway-api                                 │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │ │
│  │  │ rules:                                                            │  │ │
│  │  │   - apiGroups: [gateway.networking.k8s.io]                        │  │ │
│  │  │     resources: [httproutes]                                       │  │ │
│  │  │     verbs: [get, list, watch, patch, update]                      │  │ │
│  │  └───────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Runtime View

### 6.1 Request Flow

```
Client Request: GET /app-team1-prod/api/users
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    Envoy Gateway Service (NodePort 80)                     │
└───────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         Envoy Proxy Pod                                    │
│  1. Match request path: /app-team1-prod/*                                  │
│  2. Apply URLRewrite filter: /app-team1-prod/api/users → /api/users        │
│  3. Select backend based on weights:                                       │
│     - app-team1-stable:80 (weight: 100) ◄── Selected                       │
│     - app-team1-canary:80 (weight: 0)                                      │
└───────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│              Service: app-team1-stable (app-team1-prod namespace)          │
│                        port: 80 → targetPort: 8080                         │
└───────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    Pod (Argo Rollout stable ReplicaSet)                    │
│                         containerPort: 8080                                │
│                    Request: GET /api/users                                 │
└───────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Canary Deployment Flow

```
Developer pushes new image version
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    ArgoCD detects change, syncs Rollout                    │
└───────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    Argo Rollouts Controller                                │
│                                                                            │
│  Step 1: setWeight: 10                                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  PATCH httproutes/app-team1 -n app-team1-prod                        │ │
│  │    backendRefs:                                                      │ │
│  │      - name: app-team1-stable                                        │ │
│  │        weight: 90                                                    │ │
│  │      - name: app-team1-canary                                        │ │
│  │        weight: 10    ◄── 10% traffic to canary                       │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  Step 2: pause: 30s (observe metrics)                                      │
│                                                                            │
│  Step 3: setWeight: 30                                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  PATCH httproutes/app-team1 -n app-team1-prod                        │ │
│  │    backendRefs:                                                      │ │
│  │      - name: app-team1-stable                                        │ │
│  │        weight: 70                                                    │ │
│  │      - name: app-team1-canary                                        │ │
│  │        weight: 30    ◄── 30% traffic to canary                       │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ... continues until weight: 100                                           │
│                                                                            │
│  Final: Promote canary to stable, reset weights                            │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Deployment View

### 7.1 Target Namespace Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ envoy-gateway-system (sync-wave: 3)                                     ││
│  │  ├── Deployment: envoy-gateway (controller)                             ││
│  │  ├── Pod: envoy-*-platform-gateway-* (data plane, auto-created)         ││
│  │  ├── Service: envoy-*-platform-gateway-* (LoadBalancer/NodePort)        ││
│  │  ├── GatewayClass: eg                                                   ││
│  │  └── Gateway: platform-gateway                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ argo-rollouts (sync-wave: 3)                                            ││
│  │  ├── Deployment: argo-rollouts                                          ││
│  │  ├── ConfigMap: argo-rollouts-config (Gateway API plugin)               ││
│  │  ├── ClusterRole: argo-rollouts-gateway-api                             ││
│  │  └── ClusterRoleBinding: argo-rollouts-gateway-api                      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ app-team1-prod (customer app namespace)                                 ││
│  │  ├── HTTPRoute: app-team1                                               ││
│  │  ├── Service: app-team1-stable                                          ││
│  │  ├── Service: app-team1-canary                                          ││
│  │  └── Rollout: app-team1                                                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ app-team2-prod, app-team3-prod, ... (additional customer apps)          ││
│  │  └── Same pattern: HTTPRoute + stable/canary Services + Rollout         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 GitOps Resource Management

| Resource | Location | Managed By |
|----------|----------|------------|
| GatewayClass | `gitops/manifests/platform/envoy-gateway/` | ArgoCD |
| Gateway | `gitops/manifests/platform/envoy-gateway/` | ArgoCD |
| Envoy Gateway Helm | Manual install (OCI issue) | Helm CLI |
| Rollouts ConfigMap | `gitops/manifests/platform/argo-rollouts/` | ArgoCD |
| Gateway API RBAC | `gitops/manifests/platform/argo-rollouts/` | ArgoCD |
| HTTPRoute template | `apptemplates/simplenodeservice-content/` | Backstage |
| Services template | `apptemplates/simplenodeservice-content/` | Backstage |
| Rollout template | `apptemplates/simplenodeservice-content/` | Backstage |

---

## 8. Cross-cutting Concepts

### 8.1 URL Rewriting (NGINX → Gateway API)

| NGINX Annotation | Gateway API Equivalent |
|------------------|----------------------|
| `rewrite-target: /$2` | `URLRewrite` filter with `ReplacePrefixMatch` |
| `use-regex: "true"` | `PathPrefix` match type (regex not needed) |
| `ssl-redirect: "false"` | Not applicable (HTTP only in initial migration) |

**Example Transformation:**
```
NGINX:  path: /app-team1-prod(/)*(.*) + rewrite-target: /$2
        Request: /app-team1-prod/api/users → /api/users

Gateway API: PathPrefix: /app-team1-prod + ReplacePrefixMatch: /
             Request: /app-team1-prod/api/users → /api/users
```

### 8.2 Traffic Weight Management

```
                    Argo Rollouts Controller
                            │
                            │ watches Rollout CR
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Rollout: app-team1                         │
│  spec.strategy.canary.steps:                                      │
│    - setWeight: 10                                                │
│    - pause: 30s                                                   │
│    - setWeight: 30                                                │
│    - setWeight: 100                                               │
└──────────────────────────────────────────────────────────────────┘
                            │
                            │ updates HTTPRoute via Gateway API plugin
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     HTTPRoute: app-team1                          │
│  spec.rules[0].backendRefs:                                       │
│    - name: app-team1-stable                                       │
│      weight: 90  ◄── Rollouts controller patches this             │
│    - name: app-team1-canary                                       │
│      weight: 10  ◄── Rollouts controller patches this             │
└──────────────────────────────────────────────────────────────────┘
                            │
                            │ Envoy Gateway watches HTTPRoute
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Envoy Proxy Data Plane                       │
│  Weighted round-robin: 90% stable, 10% canary                     │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 Observability Integration

| Metric Source | Collection Method |
|---------------|-------------------|
| Envoy Proxy | Prometheus metrics (`:19001/stats/prometheus`) |
| Gateway status | `kubectl get gateway -o jsonpath='{.status}'` |
| HTTPRoute status | `kubectl get httproute -o jsonpath='{.status}'` |
| Rollout progress | `kubectl argo rollouts status <name>` |

---

## 9. Validation and Testing

### 9.1 Chainsaw Functional Tests

| Test | Type | Purpose |
|------|------|---------|
| validate-envoy-gateway-kustomize | Static | Kustomize build produces Gateway |
| validate-argo-rollouts-gateway-api | Static | Plugin config and RBAC exist |
| validate-httproute-template | Static | Template has correct structure |
| validate-rollout-template | Static | Rollout uses Gateway API plugin |
| validate-helm-chart | Static | Helm chart includes envoy-gateway apps |
| check-gateway-api-crds | Runtime | CRDs installed in cluster |
| verify-gateway | Runtime | Gateway is programmed |
| test-httproute-routing | Runtime | End-to-end traffic routing works |

### 9.2 Validation Commands

```bash
# Verify Gateway API CRDs
kubectl get crds | grep gateway.networking.k8s.io

# Verify GatewayClass accepted
kubectl get gatewayclass eg -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}'

# Verify Gateway programmed
kubectl get gateway platform-gateway -n envoy-gateway-system

# Verify HTTPRoute accepted
kubectl get httproute -A -o wide

# Test traffic routing
curl http://<gateway-service>/app-team1-prod/api/health
```

---

## 10. Risks and Technical Debt

### 10.1 Known Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ArgoCD OCI Helm support | Resolved | High | Manual Helm install documented |
| GatewayClass not auto-created | Resolved | Medium | Include in GitOps manifests |
| LoadBalancer pending (local) | Expected | Low | Use NodePort for local development |
| Gateway API version changes | Low | Medium | Pin to v1.3.0, monitor for updates |

### 10.2 Technical Debt

| Item | Priority | Remediation |
|------|----------|-------------|
| Manual Envoy Gateway install | Medium | Wait for ArgoCD OCI fix or use multiSource |
| GatewayClass in separate manifest | Low | Could be added to Helm chart via PR |
| No TLS configuration | Medium | Add HTTPS listener post-migration |

---

## 11. Glossary

| Term | Definition |
|------|------------|
| **Gateway API** | Kubernetes SIG-Network standard for ingress and service mesh |
| **GatewayClass** | Cluster-scoped resource defining Gateway controller |
| **Gateway** | Namespaced resource defining listeners and routing scope |
| **HTTPRoute** | Route configuration for HTTP traffic to backend services |
| **Envoy Gateway** | CNCF implementation of Gateway API using Envoy proxy |
| **Envoy Proxy** | High-performance L7 proxy, data plane for Gateway |
| **PathPrefix** | Gateway API match type for URL path prefix matching |
| **URLRewrite** | Gateway API filter to modify request URL before routing |
| **backendRefs** | HTTPRoute field specifying target services and weights |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-27 | Initial Gateway API target architecture |
| 1.1 | 2025-12-27 | Updated with implementation learnings and constraints |
