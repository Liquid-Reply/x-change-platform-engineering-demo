# Development Plan: Kustomize to Helm Migration (Option 3)

*Generated on 2025-12-15 by Vibe Feature MCP*
*Workflow: [epcc](https://mrsimpson.github.io/responsible-vibe-mcp/workflows/epcc)*

## Goal

Implement **Option 3: Hybrid Approach** - Helm for ArgoCD Applications, Kustomize for Platform Manifests.

**Key Outcomes:**
- Replace ~400 lines of JSON patches in Kustomize overlays with ~200 lines of Helm templates
- Create unified `gitops/platform-apps/` Helm chart for all 11 ArgoCD Applications
- Support 3 application source types: Local Kustomize, External Helm Chart, Multi-Source Hybrid
- Create per-environment values files (values-minikube.yaml, values-codespaces.yaml, values-kind.yaml)
- Preserve existing `gitops/manifests/` Kustomize structure (unchanged)
- Enable adding new environments with just 1 values file

**Reference Documents:**
- `docs/KUSTOMIZE-TO-HELM-MIGRATION-ANALYSIS.md` - Options analysis
- `docs/HELM-APPS-IMPLEMENTATION-GUIDE.md` - Detailed implementation guide

---

## Explore

### Phase Entrance Criteria
- [x] Initial phase - no entrance criteria

### Tasks
- [x] Verify current 11 ArgoCD Application definitions in `gitops/applications/base/`
- [x] Understand the 3 application source patterns (Local, External Helm, Multi-Source)
- [x] Review current Kustomize overlay structure and JSON patches
- [x] Identify environment-specific values from existing overlays
- [x] Confirm implementation guide accuracy against current codebase

### Findings

**All 11 Applications Verified and Categorized:**

| App Name | Pattern | Source Type | Sync Wave | Needs URL Patch |
|----------|---------|-------------|-----------|-----------------|
| namespaces | A | `spec.source` (local) | 1 | Yes |
| argoconfig | A | `spec.source` (local) | 1 | Yes |
| dynatrace | A | `spec.source` (local) | 2 | Yes |
| ingress-nginx | A | `spec.source` (local) | 3 | Yes |
| argo-rollouts | A | `spec.source` (local) | 3 | Yes |
| backstage | A | `spec.source` (local) | 6 | Yes |
| kubeaudit | A2 | `spec.sources[0]` (local) | 4 | Yes |
| opentelemetry | C | `spec.sources` (local + Helm) | 3 | Yes |
| cert-manager | B | `spec.sources` (Helm only) | 3 | No |
| workflows | B | `spec.sources` (Helm only) | 3 | No |
| openfeature | B | `spec.sources` (Helm only) | 4 | No |

**Pattern Summary:**
- **Pattern A**: 6 apps with `spec.source` (singular) pointing to local path
- **Pattern A2**: 1 app (kubeaudit) with `spec.sources[0]` pointing to local path
- **Pattern B**: 3 apps with `spec.sources` pointing to external Helm charts only
- **Pattern C**: 1 app (opentelemetry) with multi-source (local + Helm)

**Current Overlay Structure:**
- `overlays/minikube/` - 97 lines, patches repoURL + targetRevision
- `overlays/codespaces/` - 73 lines, patches only repoURL
- Total: ~170 lines of JSON patches

**Environment-Specific Values (extracted from overlays):**
| Value | Minikube | Codespaces |
|-------|----------|------------|
| repoURL | Same repo | Same repo |
| targetRevision | `gh_codespace2k8s_opus` | `main` (default) |

**Key Observations:**
1. Only 8 of 11 apps need URL patching (external Helm apps don't)
2. `kubeaudit` uses `sources` array but only has one local source
3. External Helm apps (cert-manager, workflows, openfeature) have no environment variance
4. Main differences between environments: `targetRevision` (branch)

### Completed
- [x] Created development plan file
- [x] Verified all 11 ArgoCD Application definitions
- [x] Categorized apps by source pattern (A, A2, B, C)
- [x] Reviewed overlay JSON patches structure
- [x] Extracted environment-specific values

---

## Plan

### Phase Entrance Criteria
- [x] All 11 ArgoCD Applications analyzed and categorized
- [x] Three source patterns understood and documented
- [x] Environment-specific values extracted from overlays
- [x] Implementation guide validated against current state

### Tasks
- [x] Define Helm chart structure for `gitops/platform-apps/`
- [x] Design values.yaml schema for all 3 application types
- [x] Plan template structure (_helpers.tpl, application templates)
- [x] Define migration sequence (which apps first)
- [x] Plan validation strategy

---

### 1. Helm Chart Structure

```
gitops/platform-apps/
├── Chart.yaml                    # Chart metadata (name, version, description)
├── values.yaml                   # Default values (shared across environments)
├── values-minikube.yaml          # Minikube-specific overrides
├── values-codespaces.yaml        # Codespaces-specific overrides
├── values-kind.yaml              # Kind-specific overrides
└── templates/
    ├── _helpers.tpl              # Helper templates (labels, names, syncPolicy)
    └── applications.yaml         # Single template rendering all 11 apps
```

**Design Decision:** Single `applications.yaml` template iterating over apps list (simpler than 11 separate files).

---

### 2. Values Schema

```yaml
# values.yaml - Shared defaults
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "main"
  project: "default"
  server: "https://kubernetes.default.svc"

applications:
  # Pattern A: Local path with spec.source (singular)
  namespaces:
    enabled: true
    syncWave: "1"
    sourceType: "local"           # Uses spec.source
    path: "gitops/manifests/platform/namespaces"
    namespace: "argocd"

  # Pattern A2: Local path with spec.sources (array)
  kubeaudit:
    enabled: true
    syncWave: "4"
    sourceType: "localMulti"      # Uses spec.sources[0]
    path: "gitops/manifests/platform/kubeaudit"
    namespace: "kubeaudit"

  # Pattern B: External Helm only
  cert-manager:
    enabled: true
    syncWave: "3"
    sourceType: "helm"            # Uses spec.sources with chart
    helmRepo: "https://charts.jetstack.io"
    chart: "cert-manager"
    chartVersion: "v1.14.3"
    namespace: "cert-manager"
    helmValues: |
      installCRDs: true

  # Pattern C: Multi-source (local + Helm)
  opentelemetry:
    enabled: true
    syncWave: "3"
    sourceType: "multiSource"     # Uses spec.sources with both
    path: "gitops/manifests/platform/opentelemetry"
    helmRepo: "https://open-telemetry.github.io/opentelemetry-helm-charts"
    chart: "opentelemetry-collector"
    chartVersion: "0.71.0"
    namespace: "opentelemetry"
    helmValues: |
      # ... (inline values)
```

**Environment Override Example (values-minikube.yaml):**
```yaml
global:
  targetRevision: "gh_codespace2k8s_opus"
```

---

### 3. Template Structure

**`_helpers.tpl`:**
- `platform-apps.labels` - Common labels (dt.owner)
- `platform-apps.syncPolicy` - Shared sync policy block
- `platform-apps.retryPolicy` - Shared retry block

**`applications.yaml`:**
```yaml
{{- range $name, $app := .Values.applications }}
{{- if $app.enabled }}
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{ $name }}
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: {{ $app.syncWave | quote }}
  labels:
    dt.owner: "platform_team"
spec:
  {{- if eq $app.sourceType "local" }}
  source:
    repoURL: {{ $.Values.global.repoURL | quote }}
    targetRevision: {{ $.Values.global.targetRevision }}
    path: {{ $app.path | quote }}
  {{- else if eq $app.sourceType "localMulti" }}
  sources:
    - repoURL: {{ $.Values.global.repoURL | quote }}
      targetRevision: {{ $.Values.global.targetRevision }}
      path: {{ $app.path | quote }}
  {{- else if eq $app.sourceType "helm" }}
  sources:
    - repoURL: {{ $app.helmRepo | quote }}
      targetRevision: {{ $app.chartVersion }}
      chart: {{ $app.chart }}
      helm:
        values: |
{{ $app.helmValues | indent 10 }}
  {{- else if eq $app.sourceType "multiSource" }}
  sources:
    - repoURL: {{ $.Values.global.repoURL | quote }}
      targetRevision: {{ $.Values.global.targetRevision }}
      path: {{ $app.path | quote }}
    - repoURL: {{ $app.helmRepo | quote }}
      targetRevision: {{ $app.chartVersion }}
      chart: {{ $app.chart }}
      helm:
        values: |
{{ $app.helmValues | indent 10 }}
  {{- end }}
  destination:
    namespace: {{ $app.namespace }}
    server: {{ $.Values.global.server | quote }}
  project: {{ $.Values.global.project }}
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    retry:
      limit: 5
      backoff:
        duration: 5s
        maxDuration: 3m0s
        factor: 2
{{- end }}
{{- end }}
```

---

### 4. Migration Sequence

**Phase 1:** Create chart with Pattern A apps (lowest risk)
- namespaces, argoconfig, dynatrace, ingress-nginx, argo-rollouts, backstage

**Phase 2:** Add Pattern B apps (external Helm, no URL patching needed)
- cert-manager, workflows, openfeature

**Phase 3:** Add Pattern A2 and C apps (different source structure)
- kubeaudit, opentelemetry

**Phase 4:** Validate and clean up
- Test all environments
- Remove old Kustomize overlays

---

### 5. Validation Strategy

| Step | Command | Success Criteria |
|------|---------|-----------------|
| 1 | `helm lint gitops/platform-apps` | No errors |
| 2 | `helm template platform-apps gitops/platform-apps -f values-minikube.yaml` | Valid YAML, 11 Applications |
| 3 | `helm template ... \| kubectl apply --dry-run=client -f -` | All resources valid |
| 4 | `helm template ... \| kubectl apply --dry-run=server -f -` | Server accepts all |
| 5 | Live deploy on minikube | All apps sync successfully |

---

### Completed
- [x] Helm chart structure defined
- [x] Values schema designed for all 4 patterns (A, A2, B, C)
- [x] Template structure planned
- [x] Migration sequence determined
- [x] Validation strategy defined

---

## Code

### Phase Entrance Criteria
- [x] Helm chart structure designed
- [x] Values schema defined for all application types
- [x] Template patterns documented
- [x] Migration sequence determined

### Tasks

#### Phase 1: Chart Foundation
- [x] Create `gitops/platform-apps/Chart.yaml`
- [x] Create `gitops/platform-apps/templates/_helpers.tpl`
- [x] Create `gitops/platform-apps/templates/applications.yaml`

#### Phase 2: Values Files
- [x] Create `gitops/platform-apps/values.yaml` (all 11 apps)
- [x] Create `gitops/platform-apps/values-minikube.yaml`
- [x] Create `gitops/platform-apps/values-codespaces.yaml`
- [x] Create `gitops/platform-apps/values-kind.yaml`

#### Phase 3: Validation
- [x] Run `helm lint gitops/platform-apps` ✓ (0 errors)
- [x] Run `helm template` for minikube and verify 11 Applications ✓
- [x] Run `kubectl apply --dry-run=server` against cluster ✓ (all 11 configured)
- [x] Compare output with current Kustomize build ✓ (functionally equivalent)

#### Phase 4: Integration
- [x] Update `gitops/platform-minikube.yml` to use Helm chart
- [x] Update `gitops/platform-codespaces.yml` to use Helm chart
- [ ] Push changes to git and verify ArgoCD syncs
- [ ] Verify all ArgoCD apps sync successfully

### Completed
- [x] Chart.yaml, _helpers.tpl, applications.yaml created
- [x] values.yaml with all 11 apps (4 patterns: local, localMulti, helm, multiSource)
- [x] Environment values files for minikube, codespaces, kind
- [x] Validation passed: lint, template, dry-run, comparison
- [x] Platform files updated to point to Helm chart (minikube, codespaces)
- [ ] **PENDING**: Push to git for ArgoCD to sync

---

## Commit

### Phase Entrance Criteria
- [x] All Helm templates created and validated
- [x] Environment values files created for minikube, codespaces, kind
- [x] `helm template` produces valid manifests
- [x] `kubectl apply --dry-run=server` succeeds
- [ ] Live testing on minikube passes (requires git push)

### Tasks
- [ ] Remove debug statements
- [ ] Update documentation (README.md, CLAUDE.md)
- [ ] Final validation run
- [ ] Create commit with summary
- [ ] Clean up old Kustomize overlays (after backup)

### Completed
*None yet*

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Helm for Apps only, not manifests | Preserves existing platform manifests, minimizes risk |
| Single chart with conditionals | Simpler than multiple charts, all apps in one place |
| Values files per environment | Clear separation, easy to add new environments |

---

## Notes

**Application Categories:**
| Category | Apps | Source Type |
|----------|------|-------------|
| Pattern A: Local Kustomize | 6 apps | `repoURL` + `path` to local manifests |
| Pattern B: External Helm | 3 apps | `repoURL` to Helm repo + `chart` |
| Pattern C: Multi-Source | 2 apps | Multiple sources (Helm + local values) |

**Validation Commands:**
```bash
# Preview Helm output
helm template platform-apps gitops/platform-apps -f gitops/platform-apps/values-minikube.yaml

# Dry-run against cluster
helm template platform-apps gitops/platform-apps -f gitops/platform-apps/values-minikube.yaml | kubectl apply --dry-run=server -f -
```

---
*This plan is maintained by the LLM. Tool responses provide guidance on which section to focus on and what tasks to work on.*
