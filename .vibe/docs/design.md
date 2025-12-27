# Technical Design: Gateway API Migration

## Overview

This document describes the technical design for migrating from NGINX Ingress Controller to Envoy Gateway implementing Kubernetes Gateway API.

---

## 1. System Architecture

### 1.1 Current Architecture (NGINX Ingress)

```
                    ┌─────────────────────────────────────────┐
                    │              External Traffic           │
                    │            (localhost:80/443)           │
                    └─────────────────┬───────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │         ingress-nginx Service           │
                    │        (NodePort 80, 443)               │
                    │        Namespace: ingress-nginx         │
                    └─────────────────┬───────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │      ingress-nginx-controller Pod       │
                    │           (NGINX v1.9.5)                │
                    │   Watches: Ingress resources (all ns)   │
                    └─────────────────┬───────────────────────┘
                                      │
                           ┌──────────┴──────────┐
                           ▼                     ▼
              ┌─────────────────────┐ ┌─────────────────────┐
              │  Customer App A     │ │  Customer App B     │
              │  (Ingress rules)    │ │  (Ingress rules)    │
              │  namespace: app-a   │ │  namespace: app-b   │
              └─────────────────────┘ └─────────────────────┘
```

### 1.2 Target Architecture (Envoy Gateway + NGINX Dual-Stack)

```
                    ┌─────────────────────────────────────────┐
                    │              External Traffic           │
                    │            (localhost:80/443)           │
                    └──────────┬──────────────────┬───────────┘
                               │                  │
           ┌───────────────────┘                  └───────────────────┐
           │                                                          │
           ▼                                                          ▼
┌─────────────────────────────────┐              ┌─────────────────────────────────┐
│    ingress-nginx Service        │              │   Envoy Gateway Service         │
│   (NodePort - legacy apps)      │              │   (NodePort - migrated apps)    │
│   Namespace: ingress-nginx      │              │   Namespace: envoy-gateway-sys  │
└───────────────┬─────────────────┘              └───────────────┬─────────────────┘
                │                                                 │
                ▼                                                 ▼
┌─────────────────────────────────┐              ┌─────────────────────────────────┐
│  ingress-nginx-controller       │              │    Envoy Gateway Controller     │
│  Watches: Ingress (all ns)      │              │    + Envoy Proxy Pods           │
└───────────────┬─────────────────┘              │    Watches: HTTPRoute (all ns)  │
                │                                 └───────────────┬─────────────────┘
                │                                                 │
      ┌─────────┴─────────┐                             ┌─────────┴─────────┐
      ▼                   ▼                             ▼                   ▼
┌───────────┐       ┌───────────┐              ┌───────────┐       ┌───────────┐
│ Legacy App│       │ Legacy App│              │ New App   │       │ Migrated  │
│ (Ingress) │       │ (Ingress) │              │(HTTPRoute)│       │(HTTPRoute)│
└───────────┘       └───────────┘              └───────────┘       └───────────┘
```

### 1.3 Final Architecture (Envoy Gateway Only)

```
                    ┌─────────────────────────────────────────┐
                    │              External Traffic           │
                    │            (localhost:80/443)           │
                    └─────────────────┬───────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │      Envoy Gateway Service              │
                    │    (NodePort 80, 443)                   │
                    │    Namespace: envoy-gateway-system      │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
         ┌────────────────────┐              ┌────────────────────┐
         │  Gateway Controller│              │    Envoy Proxy     │
         │  (manages config)  │◄────────────►│    (data plane)    │
         └────────────────────┘              └─────────┬──────────┘
                                                       │
                                      ┌────────────────┼────────────────┐
                                      ▼                ▼                ▼
                            ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
                            │ HTTPRoute A   │ │ HTTPRoute B   │ │ HTTPRoute C   │
                            │ (app-a-ns)    │ │ (app-b-ns)    │ │ (app-c-ns)    │
                            └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
                                    ▼                 ▼                 ▼
                            ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
                            │ App A Svc     │ │ App B Svc     │ │ App C Svc     │
                            │ (stable/canary)│ │(stable/canary)│ │(stable/canary)│
                            └───────────────┘ └───────────────┘ └───────────────┘
```

---

## 2. Component Design

### 2.1 Envoy Gateway ArgoCD Application

**File:** `gitops/platform-apps/values.yaml`

```yaml
envoy-gateway:
  enabled: true
  syncWave: "3"
  sourceType: "helm"
  helmRepo: "oci://docker.io/envoyproxy/gateway-helm"
  chart: "gateway-helm"
  chartVersion: "v1.3.0"
  namespace: "envoy-gateway-system"
  createNamespace: true
  helmValues: |
    config:
      envoyGateway:
        gateway:
          controllerName: gateway.envoyproxy.io/gatewayclass-controller
```

**Design Decision:** Using `helm` sourceType to align with existing platform apps (cert-manager, workflows, openfeature).

### 2.2 GatewayClass Resource

**Note:** GatewayClass is created automatically by Envoy Gateway Helm chart with name `eg`.

### 2.3 Gateway Resource

**File:** `gitops/manifests/platform/envoy-gateway/gateway.yaml`

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: platform-gateway
  namespace: envoy-gateway-system
spec:
  gatewayClassName: eg
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
```

**Design Decisions:**
- Single Gateway for all customer apps (simplicity)
- Port 80 only initially (TLS is out of scope)
- `allowedRoutes.namespaces.from: All` - allows HTTPRoutes from any namespace

---

## 3. Template Design

### 3.1 HTTPRoute Template

**File:** `apptemplates/simplenodeservice-content/httproute.yml`

```yaml
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
  namespace: "${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
  labels:
    dt.owner: "${{ values.teamIdentifier }}"
spec:
  parentRefs:
  - name: platform-gateway
    namespace: envoy-gateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: "/${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
    filters:
    - type: URLRewrite
      urlRewrite:
        path:
          type: ReplacePrefixMatch
          replacePrefixMatch: /
    backendRefs:
    - name: "${{ values.projectName }}-${{ values.teamIdentifier }}-stable"
      port: 80
      weight: 100
    - name: "${{ values.projectName }}-${{ values.teamIdentifier }}-canary"
      port: 80
      weight: 0
```

### 3.2 Service Templates (Stable + Canary)

**File:** `apptemplates/simplenodeservice-content/services.yml`

```yaml
---
# Stable service - for Argo Rollouts traffic routing
apiVersion: v1
kind: Service
metadata:
  name: "${{ values.projectName }}-${{ values.teamIdentifier }}-stable"
  namespace: "${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
spec:
  selector:
    app.kubernetes.io/name: userinterface
  ports:
  - name: http
    port: 80
    targetPort: 8080
---
# Canary service - for Argo Rollouts traffic routing
apiVersion: v1
kind: Service
metadata:
  name: "${{ values.projectName }}-${{ values.teamIdentifier }}-canary"
  namespace: "${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
spec:
  selector:
    app.kubernetes.io/name: userinterface
  ports:
  - name: http
    port: 80
    targetPort: 8080
```

### 3.3 Updated Rollout Template

**File:** `apptemplates/simplenodeservice-content/rollout.yml`

```yaml
---
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
  namespace: "${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
spec:
  replicas: 2
  strategy:
    canary:
      stableService: "${{ values.projectName }}-${{ values.teamIdentifier }}-stable"
      canaryService: "${{ values.projectName }}-${{ values.teamIdentifier }}-canary"
      trafficRouting:
        plugins:
          argoproj-labs/gatewayAPI:
            httpRoute: "${{ values.projectName }}-${{ values.teamIdentifier }}"
            namespace: "${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
      steps:
      - setWeight: 10
      - pause: {duration: 30s}
      - setWeight: 30
      - pause: {duration: 30s}
      - setWeight: 60
      - pause: {duration: 30s}
      - setWeight: 100
  revisionHistoryLimit: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: userinterface
  template:
    # ... (existing pod template)
```

---

## 4. Argo Rollouts Plugin Configuration

### 4.1 Plugin Installation

**File:** `gitops/manifests/platform/argo-rollouts/rollouts-config.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argo-rollouts-config
  namespace: argo-rollouts
data:
  trafficRouterPlugins: |
    - name: "argoproj-labs/gatewayAPI"
      location: "https://github.com/argoproj-labs/rollouts-plugin-trafficrouter-gatewayapi/releases/download/v0.5.0/gateway-api-plugin-linux-amd64"
```

### 4.2 RBAC for Gateway API

**File:** `gitops/manifests/platform/argo-rollouts/gateway-api-rbac.yaml`

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argo-rollouts-gateway-api
rules:
- apiGroups:
  - gateway.networking.k8s.io
  resources:
  - httproutes
  verbs:
  - get
  - list
  - watch
  - patch
  - update
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argo-rollouts-gateway-api
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: argo-rollouts-gateway-api
subjects:
- kind: ServiceAccount
  name: argo-rollouts
  namespace: argo-rollouts
```

---

## 5. Directory Structure

### 5.1 New Files to Create

```
gitops/
├── manifests/platform/
│   ├── envoy-gateway/
│   │   ├── kustomization.yaml      # NEW
│   │   └── gateway.yaml            # NEW
│   ├── argo-rollouts/
│   │   ├── kustomization.yaml      # UPDATE
│   │   ├── rollouts.yml            # EXISTING
│   │   ├── rollouts-config.yaml    # NEW
│   │   └── gateway-api-rbac.yaml   # NEW
│   └── namespaces/
│       └── envoy-gateway-system.yaml  # NEW
└── platform-apps/
    └── values.yaml                 # UPDATE

apptemplates/
└── simplenodeservice-content/
    ├── httproute.yml               # NEW
    ├── services.yml                # NEW (replaces service.yml)
    ├── rollout.yml                 # UPDATE
    ├── kustomization.yaml          # UPDATE
    └── ingress.yml                 # KEEP (dual-stack)
```

---

## 6. Migration Sequence

### Phase 1: Infrastructure Setup
1. Create `envoy-gateway-system` namespace
2. Add Envoy Gateway to `values.yaml`
3. Deploy via ArgoCD sync
4. Verify GatewayClass and Gateway are `Accepted`

### Phase 2: Argo Rollouts Configuration
1. Add Gateway API plugin ConfigMap
2. Add RBAC for HTTPRoute access
3. Restart Argo Rollouts controller
4. Verify plugin is loaded

### Phase 3: Template Updates
1. Create `httproute.yml` template
2. Create `services.yml` (stable/canary)
3. Update `rollout.yml` with traffic routing
4. Update `kustomization.yaml`

### Phase 4: Validation
1. Deploy test application
2. Verify HTTPRoute is `Accepted`
3. Test canary rollout
4. Verify traffic splitting works

### Phase 5: Cleanup (Post-Validation)
1. Remove `ingress.yml` from templates
2. Disable NGINX Ingress in `values.yaml`
3. Delete ingress-nginx namespace

---

## 7. Rollback Procedure

1. **Re-enable NGINX Ingress** in `values.yaml`
2. **Restore Ingress templates** in kustomization
3. **Sync ArgoCD**
4. **Verify traffic flows through NGINX**

**Rollback Time Target:** < 5 minutes

---

## 8. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Helm sourceType for Envoy Gateway | Consistent with cert-manager, workflows |
| Single Gateway resource | Simplicity; multi-gateway not needed |
| Sync Wave 3 | Deploy alongside NGINX for dual-stack |
| Stable/Canary Services | Required for Argo Rollouts traffic routing |
| PathPrefix matching | Simpler than regex; meets requirements |
| URLRewrite filter | Replaces NGINX rewrite-target annotation |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-27 | Initial design document |
