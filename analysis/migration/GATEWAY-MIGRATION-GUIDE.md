# Comprehensive Analysis: Migrating from NGINX Ingress to API Gateway

> **Document Version:** 1.0
> **Date:** December 2025
> **Scope:** General migration strategies and project-specific recommendations for x-change-platform-engineering-demo

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Background: The Ingress-NGINX Retirement](#background-the-ingress-nginx-retirement)
3. [Understanding the Current Landscape](#understanding-the-current-landscape)
4. [Gateway API: The Future Standard](#gateway-api-the-future-standard)
5. [Gateway API Implementations Comparison](#gateway-api-implementations-comparison)
6. [Current Project Architecture Analysis](#current-project-architecture-analysis)
7. [Migration Strategies](#migration-strategies)
8. [Project-Specific Migration Plan](#project-specific-migration-plan)
9. [Security Considerations](#security-considerations)
10. [Integration with GitOps and Progressive Delivery](#integration-with-gitops-and-progressive-delivery)
11. [Risk Assessment and Mitigation](#risk-assessment-and-mitigation)
12. [Recommendations](#recommendations)
13. [Appendix: Resources and References](#appendix-resources-and-references)

---

## Executive Summary

### Critical Timeline

**Ingress-NGINX will be retired in March 2026.** After this date, there will be no security patches, bug fixes, or updates. This affects approximately 40-50% of Kubernetes clusters worldwide, including this project.

### Key Findings

| Aspect | Current State | Recommended Future State |
|--------|--------------|-------------------------|
| **Ingress Controller** | NGINX Ingress v1.9.5 | Gateway API Implementation |
| **API Standard** | Ingress API (frozen) | Gateway API v1.4+ (active development) |
| **Traffic Routing** | Annotation-based | Native resource-based |
| **Multi-tenancy** | Limited RBAC | Role-oriented by design |
| **Progressive Delivery** | Requires workarounds | Native traffic splitting |

### Recommended Migration Target

Based on comprehensive analysis, **Envoy Gateway** emerges as the safest long-term migration target due to:
- Active CNCF project with strong community support
- Full Gateway API conformance
- Production-ready (v1.0+ released)
- Seamless integration with Argo Rollouts
- Extensible for advanced traffic management

Alternative recommendations based on specific needs:
- **NGINX Gateway Fabric**: Best for teams with existing NGINX expertise
- **Traefik**: Best for ease of migration and dynamic service discovery
- **Kong**: Best for enterprise API management features
- **Cilium**: Best for eBPF-based performance and service mesh integration

---

## Background: The Ingress-NGINX Retirement

### Timeline of Events

| Date | Event |
|------|-------|
| November 2023 | Gateway API reaches v1.0 GA |
| November 2025 | Kubernetes announces Ingress-NGINX retirement |
| March 2026 | **Final EOL - No more updates** |
| Post-March 2026 | Repository moves to read-only |

### Why This Matters

The Ingress API has been the de facto standard for HTTP routing in Kubernetes since its early days. However, it has fundamental limitations:

1. **Limited Expressiveness**: Only supports host/path-based routing
2. **Annotation Overload**: Advanced features require vendor-specific annotations
3. **No Portability**: Switching providers means rewriting all annotations
4. **Single Resource Model**: Combines infrastructure and application concerns
5. **No Native Multi-tenancy**: Conflict-prone in shared environments

### The Driving Forces for Change

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ingress API Limitations                       │
├─────────────────────────────────────────────────────────────────┤
│  • Path/Host routing only          • No weighted traffic split  │
│  • Annotation chaos                • No header-based routing    │
│  • Vendor lock-in                  • No gRPC/TCP/UDP support    │
│  • No role separation              • No cross-namespace routing │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Gateway API Solution                          │
├─────────────────────────────────────────────────────────────────┤
│  • Multi-protocol support          • Native traffic splitting   │
│  • Role-oriented resources         • Header/query matching      │
│  • Portable across providers       • Cross-namespace grants     │
│  • Extensible via policies         • gRPC, TCP, UDP routes      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Understanding the Current Landscape

### Ingress Controller vs. API Gateway: Key Differences

| Aspect | Ingress Controller | API Gateway |
|--------|-------------------|-------------|
| **Primary Focus** | L7 HTTP routing | Full API lifecycle management |
| **Traffic Direction** | North-South | North-South + East-West |
| **Authentication** | Via annotations/external | Built-in (OAuth, JWT, mTLS) |
| **Rate Limiting** | Limited/annotation-based | Native, configurable |
| **Observability** | Basic metrics | Rich telemetry, tracing |
| **Protocol Support** | HTTP/HTTPS mainly | HTTP, gRPC, WebSocket, TCP, UDP |
| **Configuration** | Ingress resources | Gateway API resources |

### The Convergence Trend

Modern solutions increasingly blur these boundaries:

```
                    ┌──────────────────────────────────┐
                    │   Modern API Gateway Solutions    │
                    │                                   │
                    │  Kong, Traefik, Ambassador, etc.  │
                    │                                   │
                    │  ┌─────────────────────────────┐  │
                    │  │   Ingress Controller       │  │
                    │  │   Functionality            │  │
                    │  ├─────────────────────────────┤  │
                    │  │   + API Gateway Features   │  │
                    │  │   + Rate Limiting          │  │
                    │  │   + Authentication         │  │
                    │  │   + Traffic Management     │  │
                    │  └─────────────────────────────┘  │
                    └──────────────────────────────────┘
```

---

## Gateway API: The Future Standard

### Architecture Overview

The Gateway API introduces a modular, role-oriented architecture:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Gateway API Resources                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   INFRASTRUCTURE PROVIDER                                             │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  GatewayClass                                               │   │
│   │  • Defines controller implementation                         │   │
│   │  • Provider-specific parameters                              │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│   CLUSTER OPERATOR           ▼                                       │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Gateway                                                     │   │
│   │  • Entry point configuration                                 │   │
│   │  • Listener definitions (ports, protocols, TLS)             │   │
│   │  • References GatewayClass                                   │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│   APPLICATION DEVELOPER      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Routes (HTTPRoute, GRPCRoute, TCPRoute, TLSRoute, UDPRoute)│   │
│   │  • Application-specific routing rules                        │   │
│   │  • Traffic splitting, header matching                        │   │
│   │  • Backend references                                        │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Route Types

| Route Type | Status | Use Case |
|------------|--------|----------|
| **HTTPRoute** | GA | HTTP/HTTPS traffic routing |
| **GRPCRoute** | GA | gRPC service routing |
| **TLSRoute** | Experimental | TLS passthrough routing |
| **TCPRoute** | Experimental | Raw TCP traffic |
| **UDPRoute** | Experimental | UDP traffic (DNS, gaming) |

### Key Capabilities

#### 1. Advanced Traffic Matching

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: advanced-routing
spec:
  parentRefs:
  - name: my-gateway
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api/v2
      headers:
      - name: X-Canary
        value: "true"
      queryParams:
      - name: version
        value: "beta"
    backendRefs:
    - name: api-canary
      port: 8080
      weight: 100
```

#### 2. Native Traffic Splitting

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: canary-split
spec:
  parentRefs:
  - name: my-gateway
  rules:
  - backendRefs:
    - name: app-stable
      port: 80
      weight: 90
    - name: app-canary
      port: 80
      weight: 10
```

#### 3. Cross-Namespace Routing with ReferenceGrant

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-gateway-to-backend
  namespace: backend-team
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: frontend-team
  to:
  - group: ""
    kind: Service
```

### Policy Attachment (Extensibility)

```yaml
apiVersion: gateway.networking.k8s.io/v1alpha2
kind: BackendTLSPolicy
metadata:
  name: mtls-policy
spec:
  targetRef:
    group: ""
    kind: Service
    name: backend-service
  tls:
    caCertRefs:
    - name: backend-ca
      group: ""
      kind: ConfigMap
    hostname: backend.internal
```

---

## Gateway API Implementations Comparison

### Comprehensive Feature Matrix

| Feature | Envoy Gateway | NGINX Gateway Fabric | Traefik | Kong | Cilium |
|---------|--------------|---------------------|---------|------|--------|
| **Gateway API Version** | v1.4 | v1.2 | v1.4 | v1.2 | v1.3 |
| **HTTPRoute** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **GRPCRoute** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **TCPRoute** | ✅ | ⚠️ Partial | ✅ | ✅ | ✅ |
| **UDPRoute** | ✅ | ❌ | ✅ | ⚠️ | ✅ |
| **TLSRoute** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Traffic Splitting** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Header Matching** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Rate Limiting** | ✅ Extension | ⚠️ Limited | ✅ Middleware | ✅ Plugin | ✅ |
| **Authentication** | ✅ Extension | ⚠️ Limited | ✅ Middleware | ✅ Plugin | ⚠️ |
| **mTLS** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **OIDC/JWT** | ✅ Extension | ❌ | ✅ | ✅ | ❌ |
| **Argo Rollouts Plugin** | ✅ | ✅ | ✅ | ⚠️ | ⚠️ |
| **License** | Apache 2.0 | Apache 2.0 | MIT | Apache 2.0 | Apache 2.0 |
| **Commercial Support** | Tetrate | F5 | Traefik Labs | Kong Inc | Isovalent/Cisco |

### Detailed Implementation Analysis

#### Envoy Gateway

**Strengths:**
- Built on battle-tested Envoy Proxy
- Full Gateway API v1.4 conformance
- Rich extension CRDs for advanced features
- Strong CNCF backing and community
- Production-ready since v1.0 (2024)
- AI Gateway extension available

**Weaknesses:**
- Steeper learning curve for Envoy concepts
- Newer project compared to alternatives
- Resource overhead from Envoy proxy

**Best For:** Organizations wanting a future-proof, extensible solution with enterprise features

**Production Users:** Teleport, Zapier, Signal AI

```yaml
# Envoy Gateway Rate Limiting Example
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: rate-limit-policy
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: my-route
  rateLimit:
    type: Global
    global:
      rules:
      - clientSelectors:
        - headers:
          - name: x-user-id
            type: Distinct
        limit:
          requests: 100
          unit: Minute
```

#### NGINX Gateway Fabric

**Strengths:**
- Built on proven NGINX performance
- Easy migration from NGINX Ingress
- Strong documentation
- F5 enterprise support available
- Familiar configuration patterns

**Weaknesses:**
- Limited advanced features in OSS version
- Slower feature adoption vs Envoy Gateway
- Less extensible architecture

**Best For:** Teams with existing NGINX expertise wanting minimal disruption

```yaml
# NGINX Gateway Fabric Example
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: nginx-gateway
spec:
  gatewayClassName: nginx
  listeners:
  - name: http
    port: 80
    protocol: HTTP
    hostname: "*.example.com"
```

#### Traefik

**Strengths:**
- Excellent automatic service discovery
- Easy to configure and operate
- Full middleware ecosystem
- Strong Gateway API contribution (v1.4 support)
- Native Let's Encrypt integration
- Multi-provider support

**Weaknesses:**
- Less enterprise-focused than Kong
- Lighter on advanced API management features
- Smaller enterprise ecosystem

**Best For:** Teams prioritizing ease of use and automatic configuration

```yaml
# Traefik with Gateway API and Middleware
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-route
spec:
  parentRefs:
  - name: traefik-gateway
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api
    filters:
    - type: ExtensionRef
      extensionRef:
        group: traefik.io
        kind: Middleware
        name: rate-limit
    backendRefs:
    - name: api-service
      port: 8080
```

#### Kong

**Strengths:**
- Most mature API Gateway ecosystem
- 80+ enterprise plugins
- Strong API management capabilities
- GraphQL support
- Developer portal
- Enterprise-grade security features

**Weaknesses:**
- More complex setup
- Gateway API support less mature than native CRDs
- Higher resource requirements
- Some features require Enterprise license

**Best For:** Organizations needing comprehensive API management beyond just routing

```yaml
# Kong Rate Limiting with Gateway API
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: rate-limit
config:
  minute: 100
  policy: local
plugin: rate-limiting
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
  annotations:
    konghq.com/plugins: rate-limit
spec:
  parentRefs:
  - name: kong-gateway
  rules:
  - backendRefs:
    - name: api-service
      port: 80
```

#### Cilium

**Strengths:**
- eBPF-based performance (kernel-level)
- Integrated CNI + Gateway + Service Mesh
- Sidecar-less architecture
- Strong network security features
- GAMMA initiative for east-west traffic

**Weaknesses:**
- Requires CNI replacement
- More complex prerequisites
- Tighter coupling to infrastructure
- Some GAMMA features still maturing

**Best For:** Organizations already using or planning to use Cilium as CNI

---

## Current Project Architecture Analysis

### NGINX Ingress Configuration Overview

Based on detailed codebase exploration, here is the current state:

```
gitops/
├── manifests/platform/ingress-nginx/
│   ├── deploy.yml          # Full ingress-nginx deployment (v1.9.5)
│   └── kustomization.yaml  # Kustomize wrapper
├── applications/base/
│   └── ingress-nginx.yml   # ArgoCD Application (Sync Wave 3)
└── platform-apps/
    └── values.yaml         # Application definition (sourceType: local)
```

### Current Configuration Details

| Aspect | Configuration |
|--------|--------------|
| **Version** | ingress-nginx v1.9.5 |
| **Controller Class** | k8s.io/ingress-nginx |
| **IngressClass Name** | nginx |
| **Service Type** | NodePort |
| **Ports** | 80 (HTTP), 443 (HTTPS) |
| **Sync Wave** | 3 (early platform deployment) |
| **Admission Control** | ValidatingWebhook enabled |
| **Snippet Annotations** | Disabled (security) |
| **Namespace** | ingress-nginx (isolated) |
| **Health Checks** | Liveness + Readiness probes |
| **RBAC** | Cluster-wide watching |

### Ingress Resource Pattern (Customer Apps)

Current customer app template (`apptemplates/simplenodeservice-content/ingress.yml`):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
  namespace: "${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
  labels:
    dt.owner: "${{ values.teamIdentifier }}"
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "false"
    nginx.ingress.kubernetes.io/use-regex: "true"
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  rules:
    - http:
        paths:
          - path: /${{ projectName }}-${{ teamIdentifier }}-${{ releaseStage }}(/)*(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
                port:
                  number: 80
```

### Current Traffic Flow

```
External Request (localhost:80)
         │
         ▼
┌─────────────────────────────┐
│ Ingress-NGINX NodePort      │
│ Service (port 80)           │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Ingress-NGINX Controller    │
│ Pod (port 80)               │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Ingress Resource Rules      │
│ (path-based routing)        │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Customer App Service        │
│ (port 80)                   │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Customer Application Pod    │
│ (via Argo Rollout)          │
└─────────────────────────────┘
```

### Integration Points

| Component | Integration Type | Migration Impact |
|-----------|-----------------|------------------|
| **ArgoCD** | Application resource | Low - Replace application definition |
| **Argo Rollouts** | Traffic routing | Medium - Requires Gateway API plugin |
| **Backstage** | Template generation | Medium - Update ingress templates |
| **Customer Apps** | Ingress resources | High - Convert all ingresses |
| **Dynatrace** | Observability | Low - Update instrumentation |

### Annotations to Convert

| NGINX Annotation | Gateway API Equivalent |
|-----------------|----------------------|
| `nginx.ingress.kubernetes.io/ssl-redirect` | HTTPRoute RedirectFilter |
| `nginx.ingress.kubernetes.io/rewrite-target` | HTTPRoute URLRewriteFilter |
| `nginx.ingress.kubernetes.io/use-regex` | HTTPRoute PathPrefix with regex |
| `kubernetes.io/ingress.class` | parentRefs in HTTPRoute |

---

## Migration Strategies

### Strategy 1: Big Bang Migration

**Description:** Complete replacement of ingress-nginx with Gateway API in a single deployment.

```
┌─────────────────┐
│  Current State  │
│  (NGINX Ingress)│
└────────┬────────┘
         │
         │ Single Cut-over
         │
         ▼
┌─────────────────┐
│   Target State  │
│  (Gateway API)  │
└─────────────────┘
```

**Pros:**
- Clean, single migration
- No dual-stack complexity
- Clear timeline

**Cons:**
- High risk
- All-or-nothing
- Requires comprehensive testing
- Potential downtime

**Recommended For:** Development/staging environments only

### Strategy 2: Dual-Stack Migration (Recommended)

**Description:** Run both controllers simultaneously, migrate services incrementally.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Phase 1: Parallel Deploy                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│    ┌─────────────┐                    ┌─────────────┐           │
│    │   NGINX     │                    │  Gateway    │           │
│    │  Ingress    │    (coexist)       │    API      │           │
│    │  (IP: A)    │                    │  (IP: B)    │           │
│    └──────┬──────┘                    └──────┬──────┘           │
│           │                                   │                  │
│           └──────────────┬───────────────────┘                  │
│                          │                                       │
│                          ▼                                       │
│              ┌───────────────────────┐                          │
│              │    Backend Services   │                          │
│              └───────────────────────┘                          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   Phase 2: Gradual Migration                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│    ┌─────────────┐                    ┌─────────────┐           │
│    │   NGINX     │   ←── Services     │  Gateway    │           │
│    │  Ingress    │   migrating ───►   │    API      │           │
│    │ (reducing)  │                    │ (growing)   │           │
│    └─────────────┘                    └─────────────┘           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Phase 3: Complete Migration                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│    ┌─────────────┐                    ┌─────────────┐           │
│    │   NGINX     │                    │  Gateway    │           │
│    │  Ingress    │    (removed)       │    API      │           │
│    │     ❌      │                    │   (only)    │           │
│    └─────────────┘                    └─────────────┘           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- Reversible at any stage
- Gradual risk reduction
- Service-by-service validation
- Zero downtime possible

**Cons:**
- Dual maintenance period
- Resource duplication
- Longer timeline

**Recommended For:** Production environments (this project)

### Strategy 3: Shadow/Mirror Migration

**Description:** Mirror traffic to Gateway API while NGINX handles production.

```
                    ┌─────────────────────┐
                    │  Incoming Traffic   │
                    └──────────┬──────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
               ▼                               ▼
    ┌─────────────────────┐      ┌─────────────────────┐
    │  NGINX Ingress      │      │   Gateway API       │
    │  (Primary - 100%)   │      │  (Shadow - Mirror)  │
    └──────────┬──────────┘      └──────────┬──────────┘
               │                             │
               ▼                             ▼
    ┌─────────────────────┐      ┌─────────────────────┐
    │  Production Response│      │  Validation Only    │
    │  (returned to user) │      │  (responses dropped)│
    └─────────────────────┘      └─────────────────────┘
```

**Pros:**
- Production traffic unchanged
- Real-world validation
- Compare routing decisions

**Cons:**
- Complex setup
- Double backend load
- Requires traffic mirroring capability

**Recommended For:** High-traffic, mission-critical services

---

## Project-Specific Migration Plan

### Recommended Approach: Dual-Stack with Envoy Gateway

Given the project's architecture (GitOps, Argo Rollouts, Backstage integration), the recommended migration path uses Envoy Gateway with a dual-stack approach.

### Phase 0: Preparation

#### 0.1 Prerequisites Checklist

- [ ] Review all existing Ingress resources
- [ ] Document all NGINX-specific annotations in use
- [ ] Inventory customer apps using ingress
- [ ] Test ingress2gateway tool on current configurations
- [ ] Set up monitoring/alerting baselines
- [ ] Create rollback procedures

#### 0.2 Install ingress2gateway

```bash
# Install the migration tool
brew install ingress2gateway

# Or via Go
go install github.com/kubernetes-sigs/ingress2gateway@v0.4.0
```

#### 0.3 Analyze Current Ingress Resources

```bash
# Export current ingress configurations
kubectl get ingress -A -o yaml > current-ingresses.yaml

# Run ingress2gateway analysis
ingress2gateway print --providers=ingress-nginx \
  --input-file=current-ingresses.yaml \
  --output-file=converted-gateway-resources.yaml
```

### Phase 1: Gateway API Controller Deployment

#### 1.1 Create New Platform App Definition

Add to `gitops/platform-apps/values.yaml`:

```yaml
applications:
  # ... existing apps ...

  envoy-gateway:
    enabled: true
    name: envoy-gateway
    namespace: envoy-gateway-system
    sourceType: helm
    helm:
      repo: oci://docker.io/envoyproxy
      chart: gateway-helm
      version: v1.5.0
    syncWave: "3"
    createNamespace: true
    values:
      config:
        envoyGateway:
          gateway:
            controllerName: gateway.envoyproxy.io/gatewayclass-controller
```

#### 1.2 Create GatewayClass

Create `gitops/manifests/platform/envoy-gateway/gatewayclass.yaml`:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: envoy-gateway
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
```

#### 1.3 Create Gateway Resource

Create `gitops/manifests/platform/envoy-gateway/gateway.yaml`:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: platform-gateway
  namespace: envoy-gateway-system
spec:
  gatewayClassName: envoy-gateway
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
  - name: https
    protocol: HTTPS
    port: 443
    tls:
      mode: Terminate
      certificateRefs:
      - name: platform-tls
        kind: Secret
    allowedRoutes:
      namespaces:
        from: All
```

### Phase 2: Update Backstage Templates

#### 2.1 Create HTTPRoute Template

Update `apptemplates/simplenodeservice-content/` to include Gateway API resources:

Create `httproute.yaml`:

```yaml
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
  hostnames:
  - "${{ values.projectName }}-${{ values.teamIdentifier }}.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
      port: 80
```

#### 2.2 Update Kustomization

Update template's `kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  # Remove: - ingress.yaml
  - httproute.yaml  # Add Gateway API route
  - rollout.yaml
```

### Phase 3: Argo Rollouts Integration

#### 3.1 Install Gateway API Plugin

Update Argo Rollouts ConfigMap:

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

#### 3.2 Update Rollout Template

Update customer app rollout template to use Gateway API:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
spec:
  strategy:
    canary:
      canaryService: "${{ values.projectName }}-${{ values.teamIdentifier }}-canary"
      stableService: "${{ values.projectName }}-${{ values.teamIdentifier }}-stable"
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
```

### Phase 4: Gradual Traffic Migration

#### 4.1 Migrate Platform Services First

1. Update Backstage to use HTTPRoute
2. Update ArgoCD UI exposure (if using ingress)
3. Validate and monitor

#### 4.2 Migrate Customer Apps

For each customer app:

```bash
# 1. Generate HTTPRoute from existing Ingress
ingress2gateway print \
  --providers=ingress-nginx \
  --namespace=<customer-app-namespace> \
  --output-file=httproute.yaml

# 2. Review and adjust the generated HTTPRoute

# 3. Apply HTTPRoute (both routes exist)
kubectl apply -f httproute.yaml

# 4. Verify traffic through Gateway API
kubectl get httproute -n <namespace>

# 5. Update DNS or switch traffic

# 6. Remove old Ingress resource
kubectl delete ingress <name> -n <namespace>
```

#### 4.3 Monitoring During Migration

Key metrics to monitor:

```yaml
# Prometheus queries
- name: "Request Success Rate"
  query: |
    sum(rate(envoy_http_downstream_rq_completed{
      response_code_class="2xx"
    }[5m])) /
    sum(rate(envoy_http_downstream_rq_completed[5m]))

- name: "Request Latency P99"
  query: |
    histogram_quantile(0.99,
      sum(rate(envoy_http_downstream_rq_time_bucket[5m])) by (le)
    )

- name: "Error Rate"
  query: |
    sum(rate(envoy_http_downstream_rq_completed{
      response_code_class="5xx"
    }[5m]))
```

### Phase 5: Cleanup

#### 5.1 Remove NGINX Ingress

After all services migrated and validated:

1. Update `gitops/platform-apps/values.yaml`:

```yaml
applications:
  ingress-nginx:
    enabled: false  # Disable
```

2. Remove ingress-nginx manifests:

```bash
rm -rf gitops/manifests/platform/ingress-nginx/
rm gitops/applications/base/ingress-nginx.yml
```

3. Remove from Kustomize overlays:

```yaml
# gitops/applications/overlays/*/kustomization.yaml
resources:
  # Remove: - ../../base/ingress-nginx.yml
```

4. Update ArgoCD to sync and prune

### Timeline Recommendation

| Phase | Duration | Milestone |
|-------|----------|-----------|
| **Phase 0: Preparation** | 1-2 weeks | Analysis complete, tools ready |
| **Phase 1: Gateway Deploy** | 1 week | Gateway API running alongside NGINX |
| **Phase 2: Template Updates** | 1-2 weeks | Backstage templates updated |
| **Phase 3: Rollouts Integration** | 1 week | Canary deployments working |
| **Phase 4: Traffic Migration** | 2-4 weeks | All services migrated |
| **Phase 5: Cleanup** | 1 week | NGINX removed |
| **Total** | 7-11 weeks | Complete migration |

**Target Completion:** Before March 2026 (with buffer)

---

## Security Considerations

### Authentication & Authorization

#### Gateway API Security Features

| Feature | Support Level | Implementation |
|---------|--------------|----------------|
| **TLS Termination** | Native | Gateway listener configuration |
| **mTLS** | BackendTLSPolicy | Backend-to-Gateway encryption |
| **JWT Validation** | Extension (Envoy) | SecurityPolicy CRD |
| **OAuth2/OIDC** | Extension (Envoy) | SecurityPolicy CRD |
| **Basic Auth** | Extension | Middleware/Filter |
| **API Key** | Extension (Kong) | Plugin |
| **Rate Limiting** | Extension | BackendTrafficPolicy |

#### Envoy Gateway Security Example

```yaml
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: SecurityPolicy
metadata:
  name: jwt-auth
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: api-route
  jwt:
    providers:
    - name: auth0
      issuer: https://example.auth0.com/
      audiences:
      - api.example.com
      remoteJWKS:
        uri: https://example.auth0.com/.well-known/jwks.json
```

### Rate Limiting Configuration

```yaml
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: global-rate-limit
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: platform-gateway
  rateLimit:
    type: Global
    global:
      rules:
      - clientSelectors:
        - headers:
          - name: x-api-key
            type: Distinct
        limit:
          requests: 1000
          unit: Minute
```

### Security Best Practices

1. **Enable mTLS for backend communication**
2. **Use short-lived JWT tokens** (< 15 min expiration)
3. **Implement rate limiting** at gateway level
4. **Enable audit logging** for security events
5. **Use ReferenceGrant** for cross-namespace restrictions
6. **Regular security scanning** of gateway configurations

---

## Integration with GitOps and Progressive Delivery

### ArgoCD Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitOps Flow                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Git Repository                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  gitops/                                                   │  │
│  │  ├── platform-apps/values.yaml    (Gateway definitions)   │  │
│  │  ├── manifests/platform/                                   │  │
│  │  │   └── envoy-gateway/           (Gateway resources)     │  │
│  │  └── customer-apps/                                        │  │
│  │      └── */httproute.yaml         (HTTPRoutes)            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                         ArgoCD                             │  │
│  │  • Syncs Gateway resources                                 │  │
│  │  • Manages HTTPRoutes                                      │  │
│  │  • Triggers Argo Rollouts                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      Kubernetes                            │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │  │
│  │  │  Gateway   │  │ HTTPRoute  │  │   Argo Rollout     │   │  │
│  │  │  Resource  │──│  Resource  │──│  (canary/blue-green)│  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Progressive Delivery with Gateway API

#### Canary Deployment Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    Canary Deployment Steps                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Step 1: Initial State (100% Stable)                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  HTTPRoute weights: stable=100, canary=0                    │ │
│  │  Traffic: ████████████████████████████████████████ 100%     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Step 2: Canary 10%                                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  HTTPRoute weights: stable=90, canary=10                    │ │
│  │  Stable:  ████████████████████████████████████ 90%          │ │
│  │  Canary:  ████ 10%                                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Step 3: Analysis (Prometheus metrics check)                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  If error_rate < 1% && latency_p99 < 500ms: continue        │ │
│  │  Else: rollback to 100% stable                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Step 4: Progressive increase (30% → 60% → 100%)                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Automated promotion based on analysis results              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

#### Argo Rollouts Analysis Template

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate-analysis
spec:
  metrics:
  - name: success-rate
    interval: 30s
    successCondition: result[0] >= 0.99
    failureLimit: 3
    provider:
      prometheus:
        address: http://prometheus:9090
        query: |
          sum(rate(envoy_http_downstream_rq_completed{
            response_code_class="2xx",
            route_name="{{args.route-name}}"
          }[1m])) /
          sum(rate(envoy_http_downstream_rq_completed{
            route_name="{{args.route-name}}"
          }[1m]))
```

---

## Risk Assessment and Mitigation

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Traffic routing errors** | Medium | High | Gradual migration, comprehensive testing |
| **Performance degradation** | Low | High | Load testing, monitoring baselines |
| **Feature parity gaps** | Medium | Medium | Pre-migration annotation audit |
| **Team learning curve** | High | Medium | Training, documentation |
| **Rollback complexity** | Low | High | Keep NGINX until full validation |
| **Integration failures** | Medium | High | Staging environment testing |
| **Timeline overrun** | Medium | Medium | Start early, buffer time |

### Mitigation Strategies

#### 1. Gradual Migration

- Migrate non-critical services first
- Validate each service before proceeding
- Maintain rollback capability throughout

#### 2. Comprehensive Testing

```yaml
# Chainsaw test for Gateway API
apiVersion: chainsaw.kyverno.io/v1alpha1
kind: Test
metadata:
  name: gateway-api-validation
spec:
  steps:
  - name: verify-gateway
    try:
    - assert:
        resource:
          apiVersion: gateway.networking.k8s.io/v1
          kind: Gateway
          metadata:
            name: platform-gateway
          status:
            conditions:
            - type: Accepted
              status: "True"
  - name: verify-httproute
    try:
    - assert:
        resource:
          apiVersion: gateway.networking.k8s.io/v1
          kind: HTTPRoute
          metadata:
            name: test-route
          status:
            parents:
            - conditions:
              - type: Accepted
                status: "True"
```

#### 3. Monitoring & Alerting

```yaml
# Alert rules for migration
groups:
- name: gateway-migration
  rules:
  - alert: GatewayHighErrorRate
    expr: |
      sum(rate(envoy_http_downstream_rq_completed{
        response_code_class="5xx"
      }[5m])) > 0.01
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "High error rate on Gateway API"

  - alert: GatewayLatencySpike
    expr: |
      histogram_quantile(0.99,
        sum(rate(envoy_http_downstream_rq_time_bucket[5m])) by (le)
      ) > 1000
    for: 5m
    labels:
      severity: warning
```

#### 4. Rollback Procedure

```bash
#!/bin/bash
# Emergency rollback script

# 1. Scale down Gateway API controller
kubectl scale deployment envoy-gateway -n envoy-gateway-system --replicas=0

# 2. Update DNS/LoadBalancer to point to NGINX
# (implementation depends on environment)

# 3. Re-enable NGINX if disabled
kubectl scale deployment ingress-nginx-controller -n ingress-nginx --replicas=1

# 4. Notify team
echo "Rollback complete. Gateway API disabled, NGINX restored."
```

---

## Recommendations

### Primary Recommendation: Envoy Gateway

Based on comprehensive analysis, **Envoy Gateway** is recommended as the primary migration target for this project.

#### Justification

| Criteria | Envoy Gateway Score | Reasoning |
|----------|-------------------|-----------|
| **Long-term viability** | ★★★★★ | CNCF project, active development |
| **Gateway API conformance** | ★★★★★ | Full v1.4 support |
| **Argo Rollouts integration** | ★★★★★ | Native plugin support |
| **Extensibility** | ★★★★★ | Rich extension CRDs |
| **Performance** | ★★★★☆ | Envoy proxy overhead acceptable |
| **Learning curve** | ★★★☆☆ | Requires Envoy knowledge |
| **Community support** | ★★★★★ | Large, active community |

### Alternative Recommendations

| Scenario | Recommended Alternative |
|----------|------------------------|
| **NGINX expertise on team** | NGINX Gateway Fabric |
| **Simplicity priority** | Traefik |
| **Enterprise API management needs** | Kong |
| **Using Cilium CNI** | Cilium Gateway API |

### Action Items Summary

#### Immediate (Next 2 Weeks)

1. [ ] Install ingress2gateway tool
2. [ ] Audit all current Ingress resources and annotations
3. [ ] Create test environment with Envoy Gateway
4. [ ] Run ingress2gateway on current configs
5. [ ] Document annotation mapping gaps

#### Short-term (Weeks 3-6)

6. [ ] Deploy Envoy Gateway to staging
7. [ ] Update Backstage templates
8. [ ] Configure Argo Rollouts Gateway API plugin
9. [ ] Migrate first non-critical service
10. [ ] Establish monitoring baselines

#### Medium-term (Weeks 7-11)

11. [ ] Migrate remaining platform services
12. [ ] Migrate customer applications
13. [ ] Comprehensive load testing
14. [ ] Security audit of new configuration
15. [ ] Remove NGINX Ingress

#### Post-Migration

16. [ ] Documentation update
17. [ ] Team training completion
18. [ ] Runbook updates
19. [ ] Disaster recovery testing

---

## Appendix: Resources and References

### Official Documentation

- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/)
- [Envoy Gateway](https://gateway.envoyproxy.io/)
- [NGINX Gateway Fabric](https://docs.nginx.com/nginx-gateway-fabric/)
- [Traefik Gateway API](https://doc.traefik.io/traefik/providers/kubernetes-gateway/)
- [Kong Gateway API](https://docs.konghq.com/kubernetes-ingress-controller/latest/)
- [Cilium Gateway API](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/)

### Migration Guides

- [Official Ingress-NGINX Migration Guide](https://gateway-api.sigs.k8s.io/guides/getting-started/migrating-from-ingress-nginx/)
- [General Ingress Migration Guide](https://gateway-api.sigs.k8s.io/guides/getting-started/migrating-from-ingress/)
- [ingress2gateway Tool](https://github.com/kubernetes-sigs/ingress2gateway)
- [Migrating to Envoy Gateway](https://tetrate.io/blog/migrating-from-ingress-nginx-to-envoy-gateway/)

### Community Resources

- [Gateway API GitHub](https://github.com/kubernetes-sigs/gateway-api)
- [Envoy Gateway GitHub](https://github.com/envoyproxy/gateway)
- [Argo Rollouts Gateway API Plugin](https://rollouts-plugin-trafficrouter-gatewayapi.readthedocs.io/)

### Articles and Tutorials

- [The End of an Era: Migrating from Ingress NGINX to Gateway API](https://ramasankarmolleti.com/2025/11/28/the-end-of-an-era-migrating-from-ingress-nginx-to-gateway-api/)
- [Complete Guide: Migrating from NGINX Ingress to Gateway API](https://collabnix.com/complete-guide-migrating-from-nginx-ingress-to-kubernetes-gateway-api-in-2025/)
- [Gateway API vs Ingress: The Future of Kubernetes Networking](https://konghq.com/blog/engineering/gateway-api-vs-ingress)
- [Canary Deployments with Gateway API and Argo Rollouts](https://kgateway.dev/blog/canary-deployments-argo-rollouts/)

### Tools

| Tool | Purpose | Link |
|------|---------|------|
| **ingress2gateway** | Convert Ingress to Gateway API | [GitHub](https://github.com/kubernetes-sigs/ingress2gateway) |
| **kubectl gateway** | kubectl plugin for Gateway API | [GitHub](https://github.com/kubernetes-sigs/gateway-api/tree/main/cmd/kubectl-gateway) |
| **Chainsaw** | Kubernetes E2E testing | [GitHub](https://github.com/kyverno/chainsaw) |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 2025 | Claude Code | Initial comprehensive analysis |

---

*This document was generated with research-backed analysis. Always verify recommendations against your specific requirements and test thoroughly in non-production environments before migration.*
