# Requirements Document: Gateway API Migration

## Executive Summary

This document defines the requirements for migrating the x-change-platform from **NGINX Ingress Controller v1.9.5** to **Envoy Gateway** implementing the Kubernetes Gateway API standard.

**Critical Timeline**: NGINX Ingress Controller retires **March 2026**
**Target Implementation**: Envoy Gateway (Gateway API v1.4 conformant)
**Migration Strategy**: Dual-Stack (parallel deployment with gradual service migration)

---

## Migration Context

### Current State Analysis

| Component | Current Value |
|-----------|---------------|
| Ingress Controller | NGINX Ingress v1.9.5 |
| IngressClass | `nginx` (k8s.io/ingress-nginx) |
| Service Type | NodePort (ports 80, 443) |
| Sync Wave | 3 |
| Namespace | ingress-nginx |
| Rollout Strategy | Argo Rollouts Canary (replica-based, not traffic-weighted) |

### NGINX Annotations in Use

| Annotation | Purpose | Gateway API Equivalent |
|------------|---------|----------------------|
| `kubernetes.io/ingress.class: nginx` | IngressClass selection | `parentRefs` in HTTPRoute |
| `nginx.ingress.kubernetes.io/ssl-redirect: "false"` | Disable SSL redirect | HTTPRoute RedirectFilter |
| `nginx.ingress.kubernetes.io/force-ssl-redirect: "false"` | Disable forced SSL | HTTPRoute RedirectFilter |
| `nginx.ingress.kubernetes.io/use-regex: "true"` | Enable regex paths | HTTPRoute PathPrefix/RegularExpression |
| `nginx.ingress.kubernetes.io/rewrite-target: /$2` | URL rewriting | HTTPRoute URLRewriteFilter |

### Current Ingress Path Pattern
```
/${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}(/)*(.*)
```
- Uses regex capture groups for URL rewriting
- PathType: `ImplementationSpecific`

---

## Functional Requirements

### REQ-GW-1: Gateway API Controller Deployment

**Priority**: Must-Have

**User Story:** As a platform engineer, I want Envoy Gateway deployed alongside NGINX Ingress so that I can migrate services incrementally.

**Acceptance Criteria:**

- [ ] WHEN `envoy-gateway` is enabled in `values.yaml` THEN the Envoy Gateway controller SHALL be deployed via Helm
- [ ] WHEN the controller is running THEN it SHALL register a GatewayClass resource
- [ ] WHEN a Gateway resource references the GatewayClass THEN status SHALL show `Accepted: True`
- [ ] WHEN both NGINX and Envoy Gateway are running THEN they SHALL NOT conflict

**Technical Specification:**
- Helm Chart: `oci://docker.io/envoyproxy/gateway-helm`
- Version: v1.3.0
- Namespace: `envoy-gateway-system`
- Sync Wave: 3 (parallel with ingress-nginx)
- Source Type: `helm`

---

### REQ-GW-2: GatewayClass and Gateway Configuration

**Priority**: Must-Have

**User Story:** As a platform engineer, I want a properly configured Gateway resource that accepts traffic for all customer applications.

**Acceptance Criteria:**

- [x] WHEN GatewayClass `eg` exists THEN status SHALL show `Accepted: True`
- [ ] WHEN Gateway `platform-gateway` is created THEN it SHALL have HTTP (80) listener
- [ ] WHEN listener `http` is configured THEN it SHALL allow routes from All namespaces
- [ ] WHEN Gateway is deployed THEN it SHALL use NodePort service type (consistent with NGINX)

**Gateway Resource Specification:**
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

---

### REQ-GW-3: HTTPRoute Template for Customer Apps

**Priority**: Must-Have

**User Story:** As a developer, I want Backstage templates to generate HTTPRoute resources so that new applications use Gateway API.

**Acceptance Criteria:**

- [ ] WHEN Backstage scaffolds a new application THEN an HTTPRoute resource SHALL be generated
- [ ] WHEN the HTTPRoute is created THEN it SHALL reference `platform-gateway` in `envoy-gateway-system`
- [ ] WHEN the HTTPRoute specifies a path THEN it SHALL match the current URL pattern
- [ ] WHEN URL rewriting is needed THEN HTTPRoute URLRewriteFilter SHALL strip the prefix

**HTTPRoute Template Pattern:**
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
    - name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
      port: 80
```

---

### REQ-GW-4: Argo Rollouts Gateway API Integration

**Priority**: Must-Have

**User Story:** As a platform engineer, I want Argo Rollouts to use Gateway API for traffic-weighted canary deployments.

**Acceptance Criteria:**

- [ ] WHEN Argo Rollouts is configured THEN the Gateway API traffic router plugin SHALL be installed
- [ ] WHEN a Rollout uses canary strategy THEN traffic weights SHALL be managed via HTTPRoute
- [ ] WHEN canary weight is set to 10% THEN 10% of traffic SHALL route to canary pods
- [ ] WHEN rollout completes THEN HTTPRoute SHALL route 100% to stable service

**Current Rollout (replica-based - no traffic routing):**
```yaml
strategy:
  canary:
    steps:
    - setWeight: 50
    - pause: {duration: 5s}
    - setWeight: 100
```

**Target Rollout (Gateway API traffic-weighted):**
```yaml
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

---

### REQ-GW-5: Stable and Canary Service Resources

**Priority**: Must-Have

**User Story:** As a platform engineer, I want separate stable and canary Services for traffic splitting.

**Acceptance Criteria:**

- [ ] WHEN a customer app is deployed THEN stable Service SHALL exist (`*-stable`)
- [ ] WHEN a customer app is deployed THEN canary Service SHALL exist (`*-canary`)
- [ ] WHEN Argo Rollouts manages traffic THEN it SHALL update HTTPRoute weights
- [ ] WHEN the current single Service exists THEN it SHALL be split into stable/canary

**Service Template Updates Required:**
- Current: Single Service (`${{ values.projectName }}-${{ values.teamIdentifier }}`)
- Target: Two Services (`*-stable` and `*-canary`) + root Service for non-canary access

---

### REQ-GW-6: Dual-Stack Migration Support

**Priority**: Must-Have

**User Story:** As a platform engineer, I want both NGINX Ingress and Envoy Gateway running simultaneously.

**Acceptance Criteria:**

- [ ] WHEN both controllers are deployed THEN they SHALL use separate namespaces
- [ ] WHEN an Ingress resource exists THEN NGINX SHALL handle it
- [ ] WHEN an HTTPRoute exists THEN Envoy Gateway SHALL handle it
- [ ] WHEN a service has both Ingress and HTTPRoute THEN both SHALL be functional
- [ ] WHEN migration is complete THEN NGINX Ingress SHALL be cleanly removable

---

## Non-Functional Requirements

### REQ-NFR-1: Zero Downtime Migration

**Priority**: Must-Have

**Acceptance Criteria:**

- [ ] WHEN services are migrated THEN no request errors SHALL occur
- [ ] WHEN rollback is needed THEN previous state SHALL be restorable within 5 minutes
- [ ] WHEN HTTPRoute is created THEN it SHALL be validated before traffic shift

---

### REQ-NFR-2: Observability Parity

**Priority**: Should-Have

**Acceptance Criteria:**

- [ ] WHEN Envoy Gateway handles traffic THEN Prometheus metrics SHALL be available
- [ ] WHEN OpenTelemetry is configured THEN traces SHALL flow through Envoy
- [ ] WHEN Dynatrace is enabled THEN Envoy metrics SHALL be exportable

---

### REQ-NFR-3: GitOps Compatibility

**Priority**: Must-Have

**Acceptance Criteria:**

- [ ] WHEN Envoy Gateway is added to `values.yaml` THEN ArgoCD SHALL deploy it
- [ ] WHEN manifests are modified THEN ArgoCD SHALL detect and sync changes
- [ ] WHEN sync wave ordering is applied THEN Gateway SHALL deploy at wave 3

---

## Integration Requirements

### REQ-INT-1: ArgoCD Application Definition

**Priority**: Must-Have

**Acceptance Criteria:**

- [ ] WHEN `envoy-gateway` is in `values.yaml` THEN ArgoCD Application SHALL be created
- [ ] WHEN source type is `helm` THEN OCI Helm chart SHALL be referenced
- [ ] WHEN namespace is specified THEN `envoy-gateway-system` SHALL be used

**Application Definition:**
```yaml
# In gitops/platform-apps/values.yaml
envoy-gateway:
  enabled: true
  syncWave: "3"
  sourceType: "helm"
  helmRepo: "oci://docker.io/envoyproxy"
  chart: "gateway-helm"
  chartVersion: "v1.3.0"
  namespace: "envoy-gateway-system"
```

---

### REQ-INT-2: Backstage Template Updates

**Priority**: Must-Have

**Acceptance Criteria:**

- [ ] WHEN `simplenodeservice` template exists THEN `httproute.yml` SHALL be added
- [ ] WHEN template kustomization is updated THEN HTTPRoute SHALL be included
- [ ] WHEN dual-stack is active THEN both `ingress.yml` and `httproute.yml` SHALL exist

---

### REQ-INT-3: Argo Rollouts Plugin Configuration

**Priority**: Must-Have

**Acceptance Criteria:**

- [ ] WHEN Argo Rollouts ConfigMap is updated THEN Gateway API plugin SHALL be registered
- [ ] WHEN plugin binary is specified THEN correct version SHALL be referenced
- [ ] WHEN Rollout uses plugin THEN traffic routing SHALL function

**ConfigMap Update:**
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

---

## Stakeholders

| Role | Responsibility | Priority |
|------|----------------|----------|
| Platform Engineers | Implement migration, configure Gateway | Primary |
| Developers | Use templates, deploy applications | Consumer |
| DevOps/SRE | Monitor platform health | Operational |

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Service availability during migration | 100% | No error spikes in monitoring |
| HTTPRoute acceptance rate | 100% | All HTTPRoutes show `Accepted: True` |
| Argo Rollouts canary success | 100% | Traffic weights applied correctly |
| Migration completion | Before March 2026 | NGINX Ingress removed |
| Rollback time | < 5 minutes | Tested procedure |

---

## Technical Constraints

| ID | Constraint | Rationale |
|----|------------|-----------|
| TC-GW-1 | Gateway API v1 | GA resources required |
| TC-GW-2 | Envoy Gateway v1.3.0 | Full feature support |
| TC-GW-3 | Helm source type | Consistent with cert-manager, workflows |
| TC-GW-4 | Sync Wave 3 | Deploy with NGINX for dual-stack |
| TC-GW-5 | NodePort service | Match current NGINX exposure |

---

## Out of Scope

| Item | Reason |
|------|--------|
| GRPCRoute | No gRPC services currently |
| TCPRoute/UDPRoute | All services are HTTP-based |
| Service Mesh (GAMMA) | Future enhancement |
| mTLS | Future enhancement |
| Rate limiting policies | Post-migration enhancement |
| JWT authentication | Post-migration enhancement |

---

## Validation Commands

```bash
# Verify Gateway API CRDs
kubectl get crds | grep gateway.networking.k8s.io

# Verify GatewayClass
kubectl get gatewayclasses

# Verify Gateway
kubectl get gateways -n envoy-gateway-system

# Verify HTTPRoutes
kubectl get httproutes -A

# Verify Envoy Gateway pods
kubectl get pods -n envoy-gateway-system

# Test traffic routing
curl -v http://localhost/<app-path>
```
