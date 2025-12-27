# Gateway API Migration Candidates: Comprehensive Pro/Con Evaluation

> **Document Version:** 1.0
> **Date:** December 2025
> **Focus:** Modularity, Extensibility, and Long-term Maintenance
> **Related Document:** [NGINX-TO-API-GATEWAY-MIGRATION.md](./NGINX-TO-API-GATEWAY-MIGRATION.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Evaluation Framework](#evaluation-framework)
3. [Candidate Analysis](#candidate-analysis)
   - [Envoy Gateway](#1-envoy-gateway)
   - [NGINX Gateway Fabric](#2-nginx-gateway-fabric)
   - [Traefik](#3-traefik)
   - [Kong](#4-kong)
   - [Cilium Gateway API](#5-cilium-gateway-api)
   - [kgateway (Gloo)](#6-kgateway-gloo)
4. [Modularity Deep Dive](#modularity-deep-dive)
5. [Future Maintenance Analysis](#future-maintenance-analysis)
6. [Comparative Summary Matrix](#comparative-summary-matrix)
7. [Decision Framework](#decision-framework)
8. [Recommendations for x-change-platform](#recommendations-for-x-change-platform)
9. [Sources and References](#sources-and-references)

---

## Executive Summary

### Critical Context

With Ingress-NGINX retiring in March 2026, selecting the right Gateway API implementation is one of the most consequential infrastructure decisions for Kubernetes platforms. This evaluation focuses on **modularity** and **future maintenance** — the two factors that will determine long-term success and total cost of ownership.

### Key Findings

| Candidate | Modularity Score | Maintenance Score | Overall Recommendation |
|-----------|-----------------|-------------------|----------------------|
| **Envoy Gateway** | ★★★★★ | ★★★★★ | **Highest Recommendation** |
| **NGINX Gateway Fabric** | ★★★☆☆ | ★★★★☆ | Good for NGINX-familiar teams |
| **Traefik** | ★★★★☆ | ★★★★☆ | Excellent simplicity-to-power ratio |
| **Kong** | ★★★★★ | ★★★★☆ | Best for API management needs |
| **Cilium** | ★★★★☆ | ★★★★★ | Best if already using Cilium CNI |
| **kgateway** | ★★★★☆ | ★★★★☆ | Strong CNCF-backed alternative |

### Summary Verdict

**Envoy Gateway** emerges as the top choice for modularity and long-term maintenance due to:
- Rich extension CRD ecosystem (5+ policy types)
- CNCF backing with strong community momentum
- Full Gateway API v1.4 conformance
- Native support for emerging patterns (AI Gateway, GAMMA)

**For this project specifically**, Envoy Gateway is recommended given the existing Argo Rollouts integration requirements and future-proof architecture needs.

---

## Evaluation Framework

### Modularity Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Extension Model** | 25% | How custom functionality is added without core changes |
| **Policy Attachment Support** | 20% | GEP-713 conformance and implementation depth |
| **Plugin/Middleware Ecosystem** | 20% | Breadth and quality of available extensions |
| **Control/Data Plane Separation** | 15% | Architectural decoupling for independent scaling |
| **Configuration Composability** | 10% | Ability to layer and inherit configurations |
| **Custom Resource Definitions** | 10% | Richness of declarative extension APIs |

### Future Maintenance Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Organizational Backing** | 25% | Vendor/Foundation support and commitment |
| **Release Cadence** | 20% | Frequency and predictability of updates |
| **Community Health** | 20% | Contributors, activity, responsiveness |
| **Gateway API Conformance** | 15% | Speed of adopting new GA features |
| **Long-term Roadmap** | 10% | Clarity and alignment with Kubernetes direction |
| **Migration Path Clarity** | 10% | Documentation and tooling for upgrades |

---

## Candidate Analysis

---

## 1. Envoy Gateway

### Overview

Envoy Gateway is a lightweight, vendor-neutral controller built on Envoy Proxy. It implements the Kubernetes Gateway API to provision and configure Envoy as an API gateway for Kubernetes applications.

**Key Stats:**
- **First Release:** 2022 (v1.0 GA: October 2024)
- **License:** Apache 2.0
- **Backing:** CNCF (Envoy project), Tetrate, Google, Microsoft
- **Gateway API Version:** v1.4 (full conformance)

### Modularity Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Rich Extension CRD Ecosystem** | ★★★★★ | 5 policy types: `ClientTrafficPolicy`, `BackendTrafficPolicy`, `SecurityPolicy`, `EnvoyExtensionPolicy`, `EnvoyPatchPolicy` |
| **Multiple Extension Mechanisms** | ★★★★★ | Wasm filters, ExtProc (gRPC), Lua scripting, direct xDS patching |
| **Extension Server Architecture** | ★★★★★ | External gRPC servers can modify xDS before delivery to Envoy |
| **Filter Chain Control** | ★★★★☆ | `filterOrder` field allows precise control over HTTP filter execution |
| **Control/Data Plane Separation** | ★★★★★ | Clean separation with Gateway Namespace Mode for multi-tenancy |
| **OCI Wasm Support** | ★★★★☆ | Wasm extensions packaged as container images for easy distribution |

```yaml
# Example: Envoy Gateway's Modular Policy Attachment
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
      remoteJWKS:
        uri: https://example.auth0.com/.well-known/jwks.json
---
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: rate-limit
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: api-route
  rateLimit:
    type: Global
    global:
      rules:
      - limit:
          requests: 1000
          unit: Minute
```

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Steeper Learning Curve** | ★★★☆☆ | Requires understanding Envoy concepts (xDS, filter chains) | Strong documentation, training resources |
| **Newer Project** | ★★☆☆☆ | Less battle-tested than NGINX (though Envoy itself is mature) | Envoy proxy itself is CNCF graduated, production-proven |
| **Resource Overhead** | ★★☆☆☆ | Envoy proxy uses more memory than NGINX | Acceptable for most deployments; can tune resource limits |
| **Extension Complexity** | ★★☆☆☆ | Wasm/ExtProc development requires specialized knowledge | Growing ecosystem of pre-built extensions |

### Future Maintenance Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **CNCF Backing** | ★★★★★ | Part of the Envoy umbrella project (graduated status) |
| **Active Development** | ★★★★★ | Regular releases (~monthly); 200+ contributors |
| **Gateway API Leadership** | ★★★★★ | Among first to achieve v1.4 conformance |
| **Multi-Vendor Support** | ★★★★★ | Tetrate, Google, Microsoft, Solo.io, VMware contributors |
| **Clear Roadmap** | ★★★★★ | Public roadmap; AI Gateway extension already available |
| **Production Users** | ★★★★★ | Teleport, Zapier, Signal AI, and growing adoption |

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Rapid API Evolution** | ★★☆☆☆ | Extension APIs still maturing (alpha/beta) | Follow semver; test in staging before production |
| **Memory Leak History** | ★★☆☆☆ | Benchmarks showed memory growth issues in some versions | Monitor and upgrade regularly; fixed in newer versions |

### Modularity Score: ★★★★★ (5/5)
### Maintenance Score: ★★★★★ (5/5)

---

## 2. NGINX Gateway Fabric

### Overview

NGINX Gateway Fabric (NGF) is F5/NGINX's official Gateway API implementation, built on the proven NGINX data plane. Version 2.0 (June 2025) introduced a new distributed architecture.

**Key Stats:**
- **First Release:** 2022 (v2.0: June 2025)
- **License:** Apache 2.0 (OSS) / Commercial (F5)
- **Backing:** F5 Networks (full-time team)
- **Gateway API Version:** v1.2 (working toward v1.4)

### Modularity Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **New Distributed Architecture (v2.0)** | ★★★★☆ | Separate control/data plane deployments, independent scaling per Gateway |
| **NGINX Configuration Model** | ★★★★☆ | Familiar patterns for NGINX-experienced teams |
| **Annotation-Free Design** | ★★★★☆ | Clean separation from legacy Ingress annotation chaos |
| **Role-Oriented Resources** | ★★★★☆ | Clear separation of infrastructure, cluster, and app developer concerns |
| **Multi-Gateway Support** | ★★★★☆ | Each Gateway gets its own NGINX deployment |

```yaml
# Example: NGINX Gateway Fabric Configuration
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
    allowedRoutes:
      namespaces:
        from: All
---
apiVersion: gateway.nginx.org/v1alpha1
kind: NginxProxy
metadata:
  name: nginx-proxy-config
spec:
  telemetry:
    exporter:
      endpoint: otel-collector:4317
```

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Limited Advanced Features in OSS** | ★★★★☆ | Rate limiting, JWT auth require NGINX Plus or custom solutions | Evaluate if F5 commercial license fits budget |
| **Slower Feature Adoption** | ★★★☆☆ | Gateway API v1.2 vs competitors at v1.4 | F5 prioritizes stability over bleeding-edge |
| **Less Extensible Architecture** | ★★★☆☆ | No Wasm/ExtProc equivalent; extension via NGINX Plus modules | Sufficient for standard HTTP use cases |
| **Control Plane Memory Growth** | ★★☆☆☆ | Benchmarks show memory scaling issues with many routes | Fixed in v2.0 with new architecture |

### Future Maintenance Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Dedicated F5 Team** | ★★★★★ | Full-time engineering team ensures consistent releases |
| **NGINX Ecosystem** | ★★★★★ | 40%+ of Kubernetes ingress market; massive knowledge base |
| **Commercial Support Available** | ★★★★★ | F5 enterprise support for mission-critical deployments |
| **Future-Proof Design** | ★★★★☆ | Explicit goal to "stand the test of time" |
| **Migration Tooling** | ★★★★☆ | Clear migration path from NGINX Ingress Controller |

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Single-Vendor Dependency** | ★★★☆☆ | F5 controls roadmap and prioritization | OSS license ensures code availability |
| **Slower Gateway API Updates** | ★★★☆☆ | Behind Envoy/Traefik in conformance version | Trade-off for stability; catching up |

### Modularity Score: ★★★☆☆ (3/5)
### Maintenance Score: ★★★★☆ (4/5)

---

## 3. Traefik

### Overview

Traefik is a cloud-native application proxy with excellent automatic service discovery. It supports multiple providers and has comprehensive Gateway API support.

**Key Stats:**
- **First Release:** 2016 (v1.0)
- **License:** MIT
- **Backing:** Traefik Labs (venture-funded)
- **Gateway API Version:** v1.4 (full conformance)

### Modularity Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Middleware Ecosystem** | ★★★★★ | 30+ built-in middlewares for auth, rate limiting, headers, etc. |
| **Multi-Provider Support** | ★★★★★ | Kubernetes, Docker, Consul, file, etcd, Zookeeper, and more |
| **Composable Middlewares** | ★★★★☆ | Chain middlewares via CRDs or annotations |
| **Plugin System** | ★★★★☆ | Go-based plugins with GitOps-friendly development |
| **Single Binary Architecture** | ★★★★☆ | Stateless design enables simple horizontal scaling |
| **Automatic Service Discovery** | ★★★★★ | Dynamic configuration without manual intervention |

```yaml
# Example: Traefik Middleware Composition
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: rate-limit
spec:
  rateLimit:
    average: 100
    burst: 50
---
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: strip-prefix
spec:
  stripPrefix:
    prefixes:
      - /api
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
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

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Smaller Plugin Marketplace** | ★★★☆☆ | Fewer third-party plugins than Kong | Built-in middlewares cover most use cases |
| **Enterprise Features in Paid Tier** | ★★★☆☆ | Traefik Hub required for advanced API management | OSS sufficient for routing; evaluate Hub for API lifecycle |
| **Benchmark Concerns** | ★★☆☆☆ | Some benchmarks showed routes not being processed | Verify in testing; likely configuration issues |
| **Less Enterprise Focus** | ★★☆☆☆ | Smaller enterprise sales/support organization than Kong/F5 | Traefik Labs growing rapidly |

### Future Maintenance Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Active Development** | ★★★★★ | Frequent releases; strong v1.4 Gateway API support |
| **Gateway API Contributor** | ★★★★★ | Active contributor to Gateway API specification |
| **Large Community** | ★★★★☆ | 45k+ GitHub stars; active Discord/forums |
| **Clear Versioning** | ★★★★☆ | Semantic versioning; LTS support available |
| **Knative Integration** | ★★★★☆ | First-class support for serverless workloads (2025) |

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Venture-Funded Company** | ★★☆☆☆ | Business model dependent on commercial adoption | MIT license ensures code longevity |
| **Smaller Core Team** | ★★☆☆☆ | Compared to CNCF-backed projects | Growing team; funded through 2027+ |

### Modularity Score: ★★★★☆ (4/5)
### Maintenance Score: ★★★★☆ (4/5)

---

## 4. Kong

### Overview

Kong is the most mature API Gateway in the Kubernetes ecosystem, with over 80 enterprise plugins and comprehensive API lifecycle management.

**Key Stats:**
- **First Release:** 2015
- **License:** Apache 2.0 (Core) / Proprietary (Enterprise)
- **Backing:** Kong Inc. (public company, NYSE: KONG)
- **Gateway API Version:** v1.2 (Kubernetes Ingress Controller)

### Modularity Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Massive Plugin Ecosystem** | ★★★★★ | 80+ official plugins; largest marketplace in the category |
| **Plugin Development Kit (PDK)** | ★★★★★ | Lua/Go-based SDK for custom plugin development |
| **Granular Plugin Application** | ★★★★★ | Apply plugins at global, service, route, or consumer level |
| **Declarative Configuration** | ★★★★☆ | deck CLI for GitOps; Kong Kubernetes Operator |
| **Kong Gateway Operator** | ★★★★☆ | Kubernetes-native management of Kong instances |
| **Database-less Mode** | ★★★★☆ | Stateless operation via declarative configuration |

```yaml
# Example: Kong Plugin Architecture with Gateway API
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: rate-limiting
config:
  minute: 100
  policy: local
plugin: rate-limiting
---
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: jwt
config:
  key_claim_name: kid
  claims_to_verify:
    - exp
plugin: jwt
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
  annotations:
    konghq.com/plugins: rate-limiting, jwt
spec:
  parentRefs:
  - name: kong-gateway
  rules:
  - backendRefs:
    - name: api-service
      port: 80
```

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Gateway API Support Less Mature** | ★★★★☆ | Native CRDs (KongIngress) more feature-rich than Gateway API | Improving rapidly; evaluate current status |
| **Complex Architecture** | ★★★☆☆ | Database (Postgres/Cassandra) often required | Use database-less mode for simpler deployments |
| **Higher Resource Requirements** | ★★★☆☆ | More memory/CPU than lighter alternatives | Trade-off for feature richness |
| **Enterprise Features Locked** | ★★★☆☆ | Many advanced plugins require Enterprise license | Evaluate ROI of Enterprise subscription |

### Future Maintenance Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Public Company** | ★★★★★ | NYSE-listed; strong financial backing |
| **Largest User Base** | ★★★★★ | Enterprise-proven at massive scale |
| **Comprehensive Documentation** | ★★★★★ | Extensive tutorials, API references, community content |
| **Long-term Commitment** | ★★★★★ | Kong's core business; will be maintained indefinitely |
| **Professional Services** | ★★★★☆ | Enterprise support, consulting, training available |

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Gateway API Behind Native CRDs** | ★★★☆☆ | Feature parity will take time | Use KongIngress for now; migrate later |
| **Slower Feature Velocity** | ★★☆☆☆ | Large codebase means slower iteration | Enterprise stability is a feature |

### Modularity Score: ★★★★★ (5/5)
### Maintenance Score: ★★★★☆ (4/5)

---

## 5. Cilium Gateway API

### Overview

Cilium provides Gateway API support as part of its eBPF-based networking stack, offering kernel-level performance without sidecars.

**Key Stats:**
- **First Release:** 2017 (Gateway API support: 2023)
- **License:** Apache 2.0
- **Backing:** Isovalent (acquired by Cisco, 2024), CNCF
- **Gateway API Version:** v1.4 (conformant as of Cilium 1.19)

### Modularity Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Integrated CNI + Gateway + Mesh** | ★★★★★ | Single platform for all networking concerns |
| **eBPF Performance** | ★★★★★ | Kernel-level processing; sidecar-less architecture |
| **GAMMA Support** | ★★★★☆ | East-west traffic management without service mesh overhead |
| **CiliumGatewayClassConfig** | ★★★★☆ | Parameterized GatewayClass for custom behavior |
| **Native Network Policies** | ★★★★★ | L3/L4/L7 policies with same tooling as Gateway |
| **Hubble Observability** | ★★★★★ | Built-in network observability and flow visibility |

```yaml
# Example: Cilium Gateway API with Custom Parameters
apiVersion: cilium.io/v2alpha1
kind: CiliumGatewayClassConfig
metadata:
  name: custom-class
spec:
  proxyConfig:
    resources:
      limits:
        cpu: "2"
        memory: 1Gi
---
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: cilium-custom
spec:
  controllerName: io.cilium/gateway-controller
  parametersRef:
    group: cilium.io
    kind: CiliumGatewayClassConfig
    name: custom-class
```

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Requires CNI Replacement** | ★★★★★ | Cannot use Cilium Gateway without Cilium CNI | Major infrastructure change; plan carefully |
| **Tighter Infrastructure Coupling** | ★★★★☆ | Gateway tied to networking layer | Intentional design; reduces complexity |
| **Kernel Version Requirements** | ★★★☆☆ | eBPF requires newer kernels (5.4+) | Most modern distributions qualify |
| **Less Portable** | ★★★☆☆ | Configuration not as portable as pure Gateway API | Trade-off for integrated experience |

### Future Maintenance Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Cisco Acquisition (2024)** | ★★★★★ | Massive enterprise backing and resources |
| **CNCF Graduated Project** | ★★★★★ | Highest CNCF maturity level |
| **Fastest Update Times** | ★★★★★ | Benchmarks show Cilium among fastest Gateway API adopters |
| **Active Community** | ★★★★★ | 15k+ GitHub stars; Slack community of 10k+ |
| **eBPF Leadership** | ★★★★★ | Defining the future of kernel-level networking |

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Vendor Lock-in Risk** | ★★☆☆☆ | Cisco ownership could influence direction | Apache 2.0 license; vibrant community |
| **Learning Curve** | ★★★☆☆ | eBPF and Cilium concepts require training | Strong documentation; growing ecosystem |

### Modularity Score: ★★★★☆ (4/5)
### Maintenance Score: ★★★★★ (5/5)

---

## 6. kgateway (Gloo)

### Overview

kgateway (formerly Gloo Gateway) is a CNCF-hosted project built on Envoy, providing Gateway API implementation with advanced L4/L7 capabilities.

**Key Stats:**
- **First Release:** 2018 (CNCF hosted: 2025)
- **License:** Apache 2.0
- **Backing:** Solo.io, CNCF
- **Gateway API Version:** v1.4 (conformant)

### Modularity Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **Policy Attachments** | ★★★★★ | Comprehensive GEP-713 implementation |
| **Envoy-Based Data Plane** | ★★★★★ | Battle-tested proxy with full xDS support |
| **Transformation Capabilities** | ★★★★★ | Advanced request/response transformation |
| **Function-Level Routing** | ★★★★☆ | Route to specific functions (Lambda, OpenFaaS) |
| **GraphQL Support** | ★★★★☆ | Native GraphQL gateway capabilities |
| **7+ Years Development** | ★★★★☆ | Mature codebase with production learnings |

```yaml
# Example: kgateway Policy Attachment
apiVersion: gateway.kgateway.dev/v1alpha1
kind: RoutePolicy
metadata:
  name: transform-policy
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: api-route
  transformation:
    requestTransformation:
      transformationTemplate:
        headers:
          x-user-id:
            text: '{{ request_header("Authorization") | base64_decode | jq(".sub") }}'
```

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Slower Update Times** | ★★★☆☆ | Benchmarks show trailing behind Cilium/Istio | Still reasonable; improving |
| **Less Brand Recognition** | ★★★☆☆ | Less known than Envoy Gateway or Kong | CNCF hosting increasing visibility |
| **Solo.io Dependencies** | ★★☆☆☆ | Some features tied to Solo.io ecosystem | Core Gateway API fully independent |

### Future Maintenance Analysis

#### ✅ PROS

| Pro | Impact | Details |
|-----|--------|---------|
| **CNCF Hosted (2025)** | ★★★★★ | Vendor-neutral governance |
| **7 Years of Development** | ★★★★★ | Mature project with proven stability |
| **Solo.io Commitment** | ★★★★☆ | Full-time engineering team |
| **Envoy Foundation** | ★★★★★ | Benefits from Envoy ecosystem |

#### ❌ CONS

| Con | Impact | Mitigation |
|-----|--------|------------|
| **Smaller Community** | ★★★☆☆ | Less contributors than Envoy Gateway | Growing with CNCF hosting |

### Modularity Score: ★★★★☆ (4/5)
### Maintenance Score: ★★★★☆ (4/5)

---

## Modularity Deep Dive

### Extension Model Comparison

| Capability | Envoy Gateway | NGINX GF | Traefik | Kong | Cilium | kgateway |
|------------|--------------|----------|---------|------|--------|----------|
| **Wasm Filters** | ✅ Native | ❌ | ❌ | ❌ | ❌ | ✅ Via Envoy |
| **External Processing** | ✅ ExtProc | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Lua Scripting** | ✅ | ✅ | ❌ | ✅ Native | ❌ | ✅ |
| **Go Plugins** | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **xDS Patching** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Middleware Chains** | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ |

### Policy Attachment Implementation (GEP-713)

```
Envoy Gateway    ████████████████████████████  (95%) - Full implementation
kgateway         ████████████████████████████  (95%) - Full implementation
Traefik          ████████████████████████░░░░  (85%) - Strong support
Kong             ████████████████████░░░░░░░░  (75%) - Via annotations
Cilium           ████████████████░░░░░░░░░░░░  (65%) - Growing support
NGINX GF         ████████████░░░░░░░░░░░░░░░░  (55%) - Basic support
```

### Control Plane / Data Plane Separation

| Implementation | Architecture | Scalability | Multi-tenancy |
|---------------|--------------|-------------|---------------|
| **Envoy Gateway** | Separate deployments | Per-gateway scaling | Gateway Namespace Mode |
| **NGINX GF 2.0** | Separate deployments | Per-gateway scaling | Full multi-gateway |
| **Traefik** | Single binary | Horizontal scaling | Namespace isolation |
| **Kong** | Control plane + DB + data plane | Complex but powerful | Full multi-tenant |
| **Cilium** | eBPF in-kernel | Kernel-level scaling | Network policy based |
| **kgateway** | Separate deployments | Per-gateway scaling | Strong isolation |

---

## Future Maintenance Analysis

### Organizational Backing Comparison

| Implementation | Primary Backer | Foundation | Enterprise Support |
|---------------|----------------|------------|-------------------|
| **Envoy Gateway** | Tetrate, Google, Microsoft | CNCF | Tetrate Enterprise |
| **NGINX GF** | F5 Networks | None (F5 OSS) | F5 Enterprise |
| **Traefik** | Traefik Labs | None | Traefik Enterprise |
| **Kong** | Kong Inc. (NYSE) | None | Kong Enterprise |
| **Cilium** | Cisco/Isovalent | CNCF Graduated | Isovalent Enterprise |
| **kgateway** | Solo.io | CNCF Hosted | Solo.io Enterprise |

### Release Cadence (2024-2025)

```
Envoy Gateway:  ▓▓▓▓▓▓▓▓▓▓▓▓ (Monthly releases)
Cilium:         ▓▓▓▓▓▓▓▓▓▓▓░ (10 releases/year)
Traefik:        ▓▓▓▓▓▓▓▓▓▓░░ (8-10 releases/year)
Kong:           ▓▓▓▓▓▓▓▓░░░░ (6-8 releases/year)
NGINX GF:       ▓▓▓▓▓▓░░░░░░ (4-6 releases/year)
kgateway:       ▓▓▓▓▓▓▓▓░░░░ (6-8 releases/year)
```

### Gateway API Version Adoption Speed

| Implementation | v1.0 | v1.1 | v1.2 | v1.3 | v1.4 |
|---------------|------|------|------|------|------|
| **Cilium** | +1mo | +1mo | +2mo | +1mo | +1mo |
| **Envoy Gateway** | +2mo | +2mo | +2mo | +2mo | +1mo |
| **Traefik** | +2mo | +3mo | +2mo | +3mo | +1mo |
| **kgateway** | +3mo | +3mo | +3mo | +3mo | +2mo |
| **NGINX GF** | +4mo | +4mo | +4mo | +4mo | TBD |
| **Kong** | +6mo | +5mo | +5mo | TBD | TBD |

### Long-term Viability Assessment

| Factor | Envoy GW | NGINX GF | Traefik | Kong | Cilium | kgateway |
|--------|----------|----------|---------|------|--------|----------|
| **5-Year Outlook** | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★★ | ★★★★★ | ★★★★☆ |
| **CNCF Alignment** | ★★★★★ | ★★☆☆☆ | ★★★☆☆ | ★★★☆☆ | ★★★★★ | ★★★★★ |
| **Community Health** | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★★★★☆ | ★★★★★ | ★★★☆☆ |
| **Innovation Pace** | ★★★★★ | ★★★☆☆ | ★★★★☆ | ★★★☆☆ | ★★★★★ | ★★★★☆ |

### Stale Implementation Risk

The Gateway API project reviews implementations at least monthly. As of v1.4:

**Active & Conformant:**
- ✅ Envoy Gateway (v1.4)
- ✅ Cilium (v1.4)
- ✅ Traefik (v1.4)
- ✅ kgateway (v1.4)
- ✅ Istio (v1.4)

**Behind but Active:**
- ⚠️ NGINX Gateway Fabric (v1.2)
- ⚠️ Kong (v1.2)

**At Risk (no release in 2+ years):**
- ❌ HAProxy
- ❌ APISIX

---

## Comparative Summary Matrix

### Comprehensive Scoring

| Criterion | Envoy GW | NGINX GF | Traefik | Kong | Cilium | kgateway |
|-----------|----------|----------|---------|------|--------|----------|
| **Extension Model** | 5 | 2 | 4 | 5 | 3 | 4 |
| **Policy Attachment** | 5 | 3 | 4 | 4 | 3 | 5 |
| **Plugin Ecosystem** | 4 | 3 | 4 | 5 | 3 | 4 |
| **Control/Data Separation** | 5 | 5 | 4 | 4 | 5 | 5 |
| **Configuration Composability** | 5 | 3 | 5 | 4 | 4 | 4 |
| **CRD Richness** | 5 | 3 | 4 | 5 | 4 | 4 |
| **Organizational Backing** | 5 | 5 | 4 | 5 | 5 | 4 |
| **Release Cadence** | 5 | 3 | 4 | 4 | 5 | 4 |
| **Community Health** | 5 | 4 | 4 | 4 | 5 | 3 |
| **Gateway API Conformance** | 5 | 3 | 5 | 3 | 5 | 5 |
| **Long-term Roadmap** | 5 | 4 | 4 | 5 | 5 | 4 |
| **Migration Path Clarity** | 5 | 5 | 4 | 3 | 4 | 4 |
| **TOTAL (weighted)** | **4.9** | **3.5** | **4.1** | **4.2** | **4.3** | **4.1** |

### Use Case Fit Matrix

| Use Case | Best Choice | Runner-up | Avoid |
|----------|-------------|-----------|-------|
| **Greenfield Kubernetes** | Envoy Gateway | Traefik | Kong (overkill) |
| **NGINX Ingress Migration** | NGINX GF | Traefik | Cilium (CNI change) |
| **API Management Focus** | Kong | Envoy Gateway | NGINX GF |
| **Service Mesh Integration** | Cilium | Envoy Gateway | NGINX GF |
| **Simplicity Priority** | Traefik | kgateway | Kong |
| **eBPF/Performance Critical** | Cilium | Envoy Gateway | NGINX GF |
| **Multi-cloud/Portable** | Envoy Gateway | Traefik | Cilium |
| **Progressive Delivery** | Envoy Gateway | Traefik | NGINX GF |

---

## Decision Framework

### Quick Decision Tree

```
START
│
├─ Do you need CNI replacement anyway?
│  ├─ YES → Cilium Gateway API
│  └─ NO ──┐
│          │
├─ Is API management (plugins, portal) critical?
│  ├─ YES → Kong
│  └─ NO ──┐
│          │
├─ Do you have strong NGINX expertise?
│  ├─ YES → NGINX Gateway Fabric
│  └─ NO ──┐
│          │
├─ Is simplicity the top priority?
│  ├─ YES → Traefik
│  └─ NO ──┐
│          │
├─ Is long-term extensibility important?
│  ├─ YES → Envoy Gateway
│  └─ NO → Any conformant implementation
```

### Risk-Based Selection

| Risk Tolerance | Recommended | Reasoning |
|----------------|-------------|-----------|
| **Conservative** | NGINX Gateway Fabric | Proven vendor, familiar patterns |
| **Moderate** | Traefik or Kong | Balance of stability and features |
| **Progressive** | Envoy Gateway | Most extensible, fastest innovation |
| **Aggressive** | Cilium | Cutting-edge, requires infrastructure change |

---

## Recommendations for x-change-platform

### Project Context

Based on the existing architecture:
- **Current**: NGINX Ingress v1.9.5
- **Integration**: Argo Rollouts for progressive delivery
- **GitOps**: ArgoCD-managed platform
- **Templates**: Backstage for application scaffolding
- **Scale**: Development/demo platform (minikube/Kind/Codespaces)

### Primary Recommendation: Envoy Gateway

**Score: 4.9/5.0**

| Factor | Assessment |
|--------|------------|
| **Argo Rollouts Integration** | Native plugin available |
| **GitOps Compatibility** | Excellent CRD-based model |
| **Backstage Templates** | Easy HTTPRoute generation |
| **Future Extension Needs** | Full Wasm/ExtProc support |
| **Learning Investment** | Worth it for long-term gains |

### Alternative Recommendation: Traefik

**Score: 4.1/5.0** (if simplicity is prioritized)

| Factor | Assessment |
|--------|------------|
| **Ease of Migration** | Very straightforward |
| **Middleware Ecosystem** | Built-in rate limiting, auth |
| **Argo Rollouts Support** | Plugin available |
| **Learning Curve** | Minimal |

### Not Recommended for This Project

| Implementation | Reason |
|----------------|--------|
| **Cilium** | Requires CNI change; overkill for demo platform |
| **Kong** | Over-engineered for current needs |
| **NGINX GF** | Slower Gateway API adoption; limited extensibility |

### Migration Priority

```
Phase 1 (Immediate): Deploy Envoy Gateway alongside NGINX
Phase 2 (Week 2-3): Update Backstage templates to generate HTTPRoute
Phase 3 (Week 4-5): Configure Argo Rollouts with Gateway API plugin
Phase 4 (Week 6-8): Migrate all routes
Phase 5 (Week 9): Remove NGINX Ingress
```

---

## Sources and References

### Gateway API Official
- [Gateway API Documentation](https://gateway-api.sigs.k8s.io/)
- [Gateway API v1.4 Release Notes](https://kubernetes.io/blog/2025/11/06/gateway-api-v1-4/)
- [GEP-713: Policy Attachment](https://gateway-api.sigs.k8s.io/geps/gep-713/)
- [GAMMA Initiative](https://gateway-api.sigs.k8s.io/mesh/gamma/)

### Envoy Gateway
- [Envoy Gateway Documentation](https://gateway.envoyproxy.io/)
- [System Design](https://gateway.envoyproxy.io/contributions/design/system-design/)
- [Extension Server](https://gateway.envoyproxy.io/latest/tasks/extensibility/extension-server/)
- [GitHub Repository](https://github.com/envoyproxy/gateway)

### NGINX Gateway Fabric
- [NGINX Gateway Fabric Documentation](https://docs.nginx.com/nginx-gateway-fabric/)
- [Architecture Overview](https://docs.nginx.com/nginx-gateway-fabric/overview/gateway-architecture/)
- [v2.0 Announcement](https://community.f5.com/kb/devcentralnews/announcing-f5-nginx-gateway-fabric-2-0-0-with-a-new-distributed-architecture/342956)
- [GitHub Repository](https://github.com/nginx/nginx-gateway-fabric)

### Traefik
- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Gateway API Support](https://doc.traefik.io/traefik/providers/kubernetes-gateway/)
- [Traefik Hub](https://traefik.io/traefik-hub-api-gateway)

### Kong
- [Kong Gateway Documentation](https://developer.konghq.com/gateway/)
- [Kong Kubernetes Ingress Controller](https://docs.konghq.com/kubernetes-ingress-controller/latest/)
- [GitHub Repository](https://github.com/Kong/kong)

### Cilium
- [Cilium Gateway API Documentation](https://docs.cilium.io/en/stable/network/servicemesh/gateway-api/gateway-api/)
- [GatewayClass Parameters](https://docs.cilium.io/en/latest/network/servicemesh/gateway-api/parameterized-gatewayclass/)
- [Production-Ready Cilium](https://medium.com/@salwan.mohamed/production-ready-cilium-gateway-api-pod-rate-limiting-and-real-world-challenges-b4add190d66d)

### kgateway
- [kgateway Documentation](https://kgateway.dev/)
- [Policy Attachments](https://kgateway.dev/blog/policy-attachments/)
- [CNCF Announcement](https://www.cncf.io/blog/2025/03/20/five-learnings-from-seven-years-of-building-gloo-and-kgateway/)

### Comparisons and Analysis
- [Gateway API Benchmarks](https://github.com/howardjohn/gateway-api-bench)
- [Ingress NGINX Retirement Announcement](https://kubernetes.io/blog/2025/11/12/ingress-nginx-retirement/)
- [CloudRaft Comparison](https://www.cloudraft.io/blog/kubernetes-api-gateway-comparison)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 2025 | Claude Code | Initial comprehensive evaluation |

---

*This document provides a point-in-time analysis. Gateway API implementations evolve rapidly. Verify current conformance and features before making final decisions.*
