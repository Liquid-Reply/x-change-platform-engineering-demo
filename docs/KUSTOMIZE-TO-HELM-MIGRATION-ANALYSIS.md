# Kustomize to Helm Migration Analysis

## Executive Summary

This document provides a deep analysis of the current GitOps structure using Kustomize and evaluates multiple migration options to Helm. The analysis considers architectural patterns, operational complexity, ArgoCD integration, and long-term maintainability.

**Key Finding**: The repository uses a sophisticated hybrid approach with Kustomize for custom platform manifests and Helm for upstream components. A full Helm migration requires careful consideration of the two distinct templating systems in use: **Kustomize overlays** (for environment customization) and **Backstage Nunjucks templating** (for application scaffolding).

---

## Table of Contents

1. [Current Architecture Deep Dive](#current-architecture-deep-dive)
2. [Kustomize Usage Patterns](#kustomize-usage-patterns)
3. [Migration Options](#migration-options)
4. [Detailed Option Evaluation](#detailed-option-evaluation)
5. [Recommendation Matrix](#recommendation-matrix)
6. [Implementation Considerations](#implementation-considerations)
7. [Risk Assessment](#risk-assessment)

---

## Current Architecture Deep Dive

### Directory Structure Overview

```
gitops/
├── platform.yml                    # Root Application (Kind)
├── platform-codespaces.yml         # Root Application (Codespaces)
├── platform-minikube.yml           # Root Application (Minikube)
├── applications/
│   ├── base/                       # ArgoCD Application definitions
│   │   ├── kustomization.yaml      # Lists 11 Application resources
│   │   ├── argoconfig.yml          # Wave 1 - ArgoCD config
│   │   ├── dynatrace.yml           # Wave 2 - Dynatrace
│   │   ├── opentelemetry.yml       # Wave 3 - OTEL (multi-source)
│   │   ├── backstage.yml           # Wave 6 - Backstage
│   │   └── ...                     # Other platform Applications
│   └── overlays/
│       ├── codespaces/             # GitHub Codespaces patches
│       ├── minikube/               # Minikube patches
│       └── (kind implied in base)
├── manifests/
│   ├── base/                       # Base manifest aggregator
│   │   └── kustomization.yaml      # References ../platform/*
│   ├── overlays/
│   │   ├── codespaces/             # Dynatrace + Keptn enabled
│   │   ├── minikube/               # Minimal (no Dynatrace)
│   │   └── kind/                   # Dynatrace enabled
│   └── platform/                   # Actual Kubernetes manifests
│       ├── argoconfig/             # 12 files - ArgoCD configuration
│       ├── backstage/              # 3 files - Deployment, Service, ConfigMap
│       ├── dynatrace/              # 2 files - Dynatrace CRD + Workflow
│       ├── opentelemetry/          # 1 file  - Service only (Helm handles rest)
│       ├── argo-rollouts/          # 1 file  - Argo Rollouts config
│       ├── ingress-nginx/          # 1 file  - Deploy config
│       ├── keptn/                  # 2 files - Keptn metrics
│       ├── kubeaudit/              # 1 file  - Security config
│       └── namespaces/             # 10 files - Namespace definitions
└── monaco/                         # Dynatrace Monaco configuration
```

### Two-Layer Architecture Pattern

The repository implements a **two-layer Kustomize architecture**:

```
Layer 1: ArgoCD Applications (gitops/applications/)
├── Defines WHAT gets deployed (ArgoCD Application CRDs)
├── Uses Kustomize to patch repository URLs per environment
└── Entry point: platform-{env}.yml → applications/overlays/{env}

Layer 2: Kubernetes Manifests (gitops/manifests/)
├── Defines HOW things are deployed (actual K8s resources)
├── Uses Kustomize to compose components per environment
└── Referenced by: each Application's spec.source.path
```

### Application Source Patterns

**Pattern A: Kustomize-Only** (7 applications)
```yaml
# argoconfig.yml, dynatrace.yml, backstage.yml, namespaces.yml, etc.
spec:
  source:
    repoURL: "https://github.com/..."
    path: "gitops/manifests/platform/{component}"
```

**Pattern B: Helm Chart Reference** (3 applications)
```yaml
# cert-manager.yml, argoworkflows.yml, openfeature.yml
spec:
  source:
    repoURL: 'https://charts.jetstack.io'  # External Helm repo
    chart: cert-manager
    targetRevision: v1.13.0
    helm:
      values: |
        installCRDs: true
```

**Pattern C: Multi-Source (Helm + Kustomize)** (2 applications)
```yaml
# opentelemetry.yml, kubeaudit.yml
spec:
  sources:
    - repoURL: "https://github.com/..."      # Local Kustomize
      path: "gitops/manifests/platform/opentelemetry"
    - repoURL: 'https://open-telemetry.github.io/...'  # External Helm
      chart: opentelemetry-collector
      helm:
        values: |
          mode: daemonset
          ...
```

### Kustomize Features in Use

| Feature | Location | Usage |
|---------|----------|-------|
| `resources` | All kustomization.yaml | List of YAML files to include |
| JSON Patches | `applications/overlays/*/` | Patch `repoURL` and `targetRevision` |
| Base + Overlays | Both layers | Environment customization |
| Component composition | `manifests/base/` | Aggregate platform components |

**NOT Used**:
- `patchesStrategicMerge`
- `configMapGenerator` / `secretGenerator`
- `commonLabels` / `commonAnnotations`
- `images` transformer
- `vars` / `replacements`
- `transformers`
- `components`

---

## Kustomize Usage Patterns

### Pattern 1: Application URL Patching

The primary Kustomize use case is patching ArgoCD Application definitions with environment-specific repository URLs and target revisions:

```yaml
# gitops/applications/overlays/minikube/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

patches:
  - target:
      kind: Application
      name: argoconfig
    patch: |-
      - op: replace
        path: /spec/source/repoURL
        value: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
      - op: replace
        path: /spec/source/targetRevision
        value: "gh_codespace2k8s_opus"
```

**Complexity Analysis**: This pattern is verbose but explicit. Each of 11 applications requires 2 patches (repoURL + targetRevision), resulting in ~200 lines of YAML patches per environment overlay.

### Pattern 2: Optional Component Inclusion

Overlays selectively include optional components:

```yaml
# gitops/manifests/overlays/codespaces/kustomization.yaml
resources:
  - ../../base
  - ../../platform/dynatrace  # Included in Codespaces
  - ../../platform/keptn      # Included in Codespaces

# gitops/manifests/overlays/minikube/kustomization.yaml
resources:
  - ../../base
  - dt-details-placeholder.yaml  # Placeholder secret only
  # Dynatrace and Keptn NOT included
```

### Pattern 3: Simple Resource Aggregation

Most component kustomization.yaml files are simple resource lists:

```yaml
# gitops/manifests/platform/backstage/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - config.yml
  - deployment.yml
  - service.yml
```

**Observation**: These could be replaced with ArgoCD's native directory manifest discovery (no Kustomize needed).

---

## Migration Options

### Option 1: Full Helm Migration (Umbrella Chart)

**Approach**: Create a single umbrella Helm chart that wraps all platform components.

```
helm/
├── Chart.yaml
├── values.yaml
├── values-codespaces.yaml
├── values-minikube.yaml
├── values-kind.yaml
└── templates/
    ├── applications/
    │   ├── argoconfig.yaml
    │   ├── backstage.yaml
    │   └── ...
    └── manifests/
        ├── argoconfig/
        ├── backstage/
        └── ...
```

**Values Structure**:
```yaml
# values.yaml
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "main"

components:
  dynatrace:
    enabled: true
  keptn:
    enabled: false

backstage:
  image: ghcr.io/katharinasick/backstage-playground:1.2.4

argocd:
  nodePort: 30100
```

### Option 2: Helm Subcharts per Component

**Approach**: Create individual Helm charts for each component, coordinated by a parent chart.

```
charts/
├── platform/           # Parent umbrella chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── charts/         # Dependency charts
├── argoconfig/         # Subchart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
├── backstage/          # Subchart
├── dynatrace/          # Subchart
└── ...
```

### Option 3: Hybrid (Helm for Apps, Keep Kustomize for Manifests)

**Approach**: Convert only the Application definitions to Helm, keep manifest Kustomize structure.

```
gitops/
├── applications-helm/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-codespaces.yaml
│   └── templates/
│       ├── _helpers.tpl
│       └── *.yaml
└── manifests/          # Keep existing Kustomize structure
```

### Option 4: ApplicationSet with Generators

**Approach**: Replace Kustomize overlays with ArgoCD ApplicationSet generators.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: platform-components
spec:
  generators:
    - matrix:
        generators:
          - list:
              elements:
                - component: argoconfig
                  syncWave: "1"
                - component: dynatrace
                  syncWave: "2"
                # ...
          - git:
              repoURL: https://github.com/...
              directories:
                - path: environments/*
  template:
    metadata:
      name: '{{component}}-{{path.basename}}'
    spec:
      source:
        repoURL: '{{repoURL}}'
        path: 'gitops/manifests/platform/{{component}}'
```

### Option 5: Keep Kustomize, Improve Structure

**Approach**: Refactor existing Kustomize to use advanced features and reduce duplication.

Improvements:
- Use `replacements` instead of JSON patches
- Use `configMapGenerator` for environment-specific configs
- Use Kustomize `components` for optional features
- Centralize common labels/annotations

---

## Detailed Option Evaluation

### Option 1: Full Helm Migration (Umbrella Chart)

| Aspect | Evaluation |
|--------|------------|
| **Complexity** | High - All manifests need template conversion |
| **Migration Effort** | 60-80 hours estimated |
| **ArgoCD Integration** | Native Helm support, single Application |
| **Reusability** | High - Values files for all customization |
| **Testing** | `helm template` + helm unittest |
| **Rollback** | Clean - Git revert of values.yaml |
| **Learning Curve** | Moderate - Go templating required |
| **Secret Management** | Helm secrets, SOPS, or external-secrets |
| **Multi-tenancy** | Values files per tenant |

**Pros**:
- Single source of truth for all configuration
- Native ArgoCD Helm support
- Better IDE support (Helm language server)
- Rich ecosystem (helm-docs, helm-unittest)
- Versioned releases with `helm history`

**Cons**:
- Go template syntax more complex than Kustomize
- Debugging template errors harder
- Massive initial migration effort
- Loss of Kustomize's patch-based approach
- Backstage templates still use different syntax

**Code Transformation Example**:
```yaml
# BEFORE: Kustomize (argoconfig.yml)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"
  name: argoconfig

# AFTER: Helm (templates/applications/argoconfig.yaml)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"
  name: {{ include "platform.fullname" . }}-argoconfig
  labels:
    {{- include "platform.labels" . | nindent 4 }}
spec:
  source:
    repoURL: {{ .Values.global.repoURL | quote }}
    targetRevision: {{ .Values.global.targetRevision | quote }}
    path: {{ .Values.argoconfig.path | default "gitops/manifests/platform/argoconfig" | quote }}
```

---

### Option 2: Helm Subcharts per Component

| Aspect | Evaluation |
|--------|------------|
| **Complexity** | Very High - Most complex option |
| **Migration Effort** | 80-120 hours estimated |
| **ArgoCD Integration** | Complex dependency management |
| **Reusability** | Highest - Individual chart versioning |
| **Testing** | Per-chart testing possible |
| **Rollback** | Per-component rollback possible |
| **Learning Curve** | High - Chart dependencies, version resolution |
| **Secret Management** | Per-chart or global |
| **Multi-tenancy** | Complex value merging |

**Pros**:
- Maximum modularity and reusability
- Independent component versioning
- Can publish to Helm registry
- Team ownership per chart
- Mix with community charts

**Cons**:
- Highest complexity
- Chart version dependency hell
- Longer sync times
- Harder to reason about full state
- Overkill for internal platform

**Architecture**:
```yaml
# charts/platform/Chart.yaml
apiVersion: v2
name: platform
version: 1.0.0
dependencies:
  - name: argoconfig
    version: "1.x.x"
    repository: "file://../argoconfig"
  - name: backstage
    version: "1.x.x"
    repository: "file://../backstage"
    condition: backstage.enabled
  - name: dynatrace
    version: "1.x.x"
    repository: "file://../dynatrace"
    condition: dynatrace.enabled
```

---

### Option 3: Hybrid (Helm for Apps, Kustomize for Manifests)

| Aspect | Evaluation |
|--------|------------|
| **Complexity** | Low-Medium - Limited scope |
| **Migration Effort** | 15-25 hours estimated |
| **ArgoCD Integration** | Works well - both supported |
| **Reusability** | Moderate - Apps templated, manifests static |
| **Testing** | Both Kustomize and Helm testing |
| **Rollback** | Standard git-based |
| **Learning Curve** | Low - Leverages existing knowledge |
| **Secret Management** | Unchanged |
| **Multi-tenancy** | Values files for app config |

**Pros**:
- **Lowest migration risk**
- Addresses main pain point (URL patching)
- Preserves existing manifest structure
- Both tools well-supported by ArgoCD
- Incremental migration possible

**Cons**:
- Still maintaining two templating systems
- Not "pure" either approach
- Team needs both skill sets

**Structure**:
```
gitops/
├── applications-chart/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-codespaces.yaml
│   ├── values-minikube.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── argoconfig.yaml
│       ├── backstage.yaml
│       └── ...
├── manifests/              # UNCHANGED - Keep Kustomize
│   ├── base/
│   ├── overlays/
│   └── platform/
└── platform-*.yml          # Update to use Helm Application
```

**New Platform Application**:
```yaml
# platform-minikube.yml (updated)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform
spec:
  source:
    repoURL: "https://github.com/..."
    path: "gitops/applications-chart"
    helm:
      valueFiles:
        - values.yaml
        - values-minikube.yaml
```

---

### Option 4: ApplicationSet with Generators

| Aspect | Evaluation |
|--------|------------|
| **Complexity** | Medium - ArgoCD-native approach |
| **Migration Effort** | 20-30 hours estimated |
| **ArgoCD Integration** | Native - Uses ApplicationSet |
| **Reusability** | High - Generator patterns |
| **Testing** | argocd-applicationset-controller testing |
| **Rollback** | Git-based |
| **Learning Curve** | Medium - ApplicationSet generators |
| **Secret Management** | Unchanged |
| **Multi-tenancy** | Matrix generators for tenants |

**Pros**:
- ArgoCD-native solution
- Eliminates Kustomize for Application layer
- Powerful generator combinations
- Built-in support for multi-cluster
- Good for standardized deployments

**Cons**:
- Moves logic into ArgoCD CRD
- Less portable (ArgoCD lock-in)
- Complex generator debugging
- Limited transformation capabilities
- Still need Kustomize/Helm for manifests

**Implementation**:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: platform-apps
spec:
  generators:
    - matrix:
        generators:
          - list:
              elements:
                - name: argoconfig
                  wave: "1"
                  path: gitops/manifests/platform/argoconfig
                - name: backstage
                  wave: "6"
                  path: gitops/manifests/platform/backstage
                # ... all components
          - list:
              elements:
                - env: minikube
                  revision: gh_codespace2k8s_opus
                - env: codespaces
                  revision: main
  template:
    metadata:
      name: '{{name}}'
      annotations:
        argocd.argoproj.io/sync-wave: '{{wave}}'
    spec:
      source:
        repoURL: https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git
        targetRevision: '{{revision}}'
        path: '{{path}}'
```

---

### Option 5: Improved Kustomize

| Aspect | Evaluation |
|--------|------------|
| **Complexity** | Low - Refactoring only |
| **Migration Effort** | 10-15 hours estimated |
| **ArgoCD Integration** | Native Kustomize support |
| **Reusability** | Moderate improvement |
| **Testing** | kustomize build validation |
| **Rollback** | Git-based |
| **Learning Curve** | Lowest - Same tool |
| **Secret Management** | Unchanged |
| **Multi-tenancy** | Better overlay patterns |

**Pros**:
- Lowest risk and effort
- No new tooling required
- Team already familiar
- Incremental improvements

**Cons**:
- Doesn't solve fundamental limitations
- Still verbose patch syntax
- Limited templating capabilities
- No conditional logic without components

**Improvements**:
```yaml
# Use replacements instead of JSON patches
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

replacements:
  - source:
      kind: ConfigMap
      name: env-config
      fieldPath: data.repoURL
    targets:
      - select:
          kind: Application
        fieldPaths:
          - spec.source.repoURL
          - spec.sources.*.repoURL

configMapGenerator:
  - name: env-config
    literals:
      - repoURL=https://github.com/...
      - targetRevision=main
```

---

## Recommendation Matrix

### Scoring (1-5, higher is better)

| Criterion | Weight | Opt 1 | Opt 2 | Opt 3 | Opt 4 | Opt 5 |
|-----------|--------|-------|-------|-------|-------|-------|
| Migration Risk | 20% | 2 | 1 | 4 | 3 | 5 |
| Long-term Maintainability | 25% | 4 | 5 | 3 | 4 | 3 |
| Operational Complexity | 15% | 3 | 2 | 4 | 3 | 4 |
| ArgoCD Integration | 15% | 4 | 4 | 4 | 5 | 4 |
| Team Learning Curve | 10% | 3 | 2 | 4 | 3 | 5 |
| Flexibility | 15% | 5 | 5 | 3 | 4 | 2 |
| **Weighted Score** | 100% | **3.35** | **3.15** | **3.60** | **3.60** | **3.55** |

### Recommendation by Use Case

| Scenario | Recommended Option |
|----------|-------------------|
| **Quick win, minimal risk** | Option 5 (Improved Kustomize) |
| **Balanced approach** | **Option 3 (Hybrid)** |
| **Full standardization needed** | Option 1 (Full Helm) |
| **Multi-cluster expansion planned** | Option 4 (ApplicationSet) |
| **Publishing charts externally** | Option 2 (Subcharts) |

---

## Implementation Considerations

### Backstage Template Compatibility

**Critical**: The application templates in `apptemplates/` use Backstage Nunjucks templating (`${{ values.* }}`), NOT Kustomize or Helm:

```yaml
# apptemplates/simplenodeservice-content/rollout.yml
metadata:
  name: "${{ values.projectName }}-${{ values.teamIdentifier }}"
  namespace: "${{ values.projectName }}-${{ values.teamIdentifier }}-${{ values.releaseStage }}"
```

**Implications**:
1. These templates are processed by **Backstage Scaffolder**, not Kustomize/Helm
2. Migration to Helm would NOT affect these templates
3. Customer apps in `customer-apps/*/` are rendered outputs (no templating)
4. Helm migration only affects `gitops/applications/` and `gitops/manifests/`

### ArgoCD Application vs ApplicationSet

**Current**: Each platform component has its own ArgoCD Application

**With ApplicationSet**: Single ApplicationSet generates all Applications

**Trade-off**: ApplicationSet is DRY but loses per-app customization granularity

### Secret Management

Current secrets are created by `cluster_installer.py`:
- `backstage-secrets` in `backstage` namespace
- `dt-details` in multiple namespaces
- ArgoCD credentials

**Helm Approach**: Consider:
- External Secrets Operator
- Sealed Secrets
- SOPS with helm-secrets plugin
- Vault integration

### Testing Strategy

| Option | Testing Approach |
|--------|-----------------|
| Helm | `helm template`, helm-unittest, Pluto |
| Kustomize | `kustomize build`, kubeconform |
| ApplicationSet | argocd CLI, dry-run |

---

## Risk Assessment

### Migration Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing deployments | Medium | High | Feature branch, staging first |
| ArgoCD sync failures | Medium | Medium | Validate with `argocd app diff` |
| Secret mismanagement | Low | High | Keep secret creation separate |
| Team skill gaps | Medium | Medium | Training, documentation |
| Backstage integration breaks | Low | High | Template testing workflow |

### Technical Debt Considerations

**Current Technical Debt**:
1. Verbose JSON patches (~200 lines per overlay)
2. Duplicated Application definitions
3. No automated testing of Kustomize builds
4. Manual URL replacement by installer script

**Debt Reduction by Option**:
- **Option 1**: Eliminates patch verbosity, but adds Helm complexity
- **Option 3**: Reduces Application layer debt significantly
- **Option 5**: Moderate reduction with existing tooling

---

## Conclusion

### Primary Recommendation: Option 3 (Hybrid Approach)

**Rationale**:
1. **Addresses the main pain point**: URL patching verbosity in Application definitions
2. **Preserves working manifest structure**: No need to rewrite all K8s resources
3. **Lowest risk**: Incremental change, easy rollback
4. **ArgoCD-native**: Both Helm and Kustomize well-supported
5. **Maintainable**: Clear separation of concerns

### Secondary Recommendation: Option 4 (ApplicationSet)

If staying within ArgoCD ecosystem is preferred, ApplicationSet with matrix generators provides similar benefits without introducing Helm.

### Implementation Phases

**Phase 1** (Week 1-2):
- Create Helm chart for Application definitions
- Test with minikube environment
- Validate ArgoCD sync behavior

**Phase 2** (Week 3):
- Migrate all three environments
- Update documentation
- Team training

**Phase 3** (Optional, Future):
- Evaluate manifest layer migration
- Consider subchart approach for reusable components

---

## Appendix: File-by-File Migration Guide (Option 3)

### Files to Create

```
gitops/applications-chart/
├── Chart.yaml
├── values.yaml
├── values-codespaces.yaml
├── values-minikube.yaml
├── values-kind.yaml
└── templates/
    ├── _helpers.tpl
    ├── argoconfig.yaml
    ├── argorollouts.yaml
    ├── argoworkflows.yaml
    ├── backstage.yaml
    ├── cert-manager.yaml
    ├── dynatrace.yaml
    ├── ingress-nginx.yaml
    ├── kubeaudit.yaml
    ├── namespaces.yaml
    ├── openfeature.yaml
    └── opentelemetry.yaml
```

### Files to Modify

```
gitops/
├── platform.yml                    # Update to use Helm
├── platform-codespaces.yml         # Update to use Helm
├── platform-minikube.yml           # Update to use Helm
```

### Files to Archive/Remove

```
gitops/applications/                # Archive entire directory
├── base/
│   └── *.yml (11 files)
│   └── kustomization.yaml
└── overlays/
    └── */kustomization.yaml (3 files)
```

### Files Unchanged

```
gitops/manifests/                   # Keep entire directory
apptemplates/                       # Keep - Backstage templates
customer-apps/                      # Keep - Generated apps
```

---

*Document generated: 2025-12-15*
*Analysis scope: x-change-platform-engineering-demo repository*
