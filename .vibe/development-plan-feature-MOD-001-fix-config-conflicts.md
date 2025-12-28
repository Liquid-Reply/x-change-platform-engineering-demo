# Development Plan: MOD-002 Migrate platform.yml to Helm

*Generated on 2025-12-28 by Vibe Feature MCP*
*Workflow: [epcc](https://mrsimpson.github.io/responsible-vibe-mcp/workflows/epcc)*

## Goal

**P1-HIGH**: Migrate `platform.yml` (codespaces) from Kustomize to Helm for consistency with kind/minikube environments.

**Current State**:
- `platform.yml` → Kustomize (`gitops/applications/overlays/codespaces`)
- `platform-kind.yml` → Helm (`gitops/platform-apps` + `values-kind.yaml`)
- `platform-minikube.yml` → Helm (`gitops/platform-apps` + `values-minikube.yaml`)

**Target State**: All environments use Helm chart with environment-specific values files.

## Explore

### Findings

**Kustomize Overlay (codespaces)**:
- Location: `gitops/applications/overlays/codespaces/kustomization.yaml`
- Base: `gitops/applications/base`
- Patches: repoURL for 8 apps (argoconfig, argo-rollouts, backstage, dynatrace, ingress-nginx, namespaces, kubeaudit, opentelemetry)

**Helm Chart**:
- Location: `gitops/platform-apps/`
- Default values: `values.yaml` (13 applications)
- Environment overrides: `values-{env}.yaml`

**Key Differences**:
| Aspect | Kustomize (codespaces) | Helm (kind/minikube) |
|--------|------------------------|----------------------|
| Apps managed | 11 from base | 13 in values.yaml |
| envoy-gateway | Not present | Enabled |
| ingress-nginx | Enabled | Disabled |
| targetRevision | main | feature branch |

**Migration Approach**:
1. Create `values-codespaces.yaml` with codespaces overrides
2. Update `platform.yml` to use Helm chart
3. Keep ingress-nginx enabled for codespaces (if needed) or migrate to Gateway API

### Tasks
- [x] Read platform.yml current configuration
- [x] Read codespaces Kustomize overlay
- [x] Read Helm chart values.yaml
- [x] Compare Kustomize vs Helm applications
- [x] Determine codespaces-specific overrides needed

### Completed
- [x] Created development plan file
- [x] Explored current configuration
- [x] Identified Keptn gap (codespaces has it, Helm doesn't)

## Plan

### Phase Entrance Criteria
- [x] Kustomize overlay structure understood
- [x] Helm chart structure understood
- [x] Application differences documented

### Implementation Strategy

**Step 1: Add Keptn to Helm chart** (values.yaml)
- Add `keptn` application with sourceType: "local"
- Path: `gitops/manifests/platform/keptn`
- Default: disabled (only enabled in codespaces)

**Step 2: Create values-codespaces.yaml**
```yaml
global:
  targetRevision: "main"

applications:
  keptn:
    enabled: true  # Codespaces-only
  ingress-nginx:
    enabled: false  # Use Gateway API instead
  envoy-gateway:
    enabled: true
  envoy-gateway-config:
    enabled: true
```

**Step 3: Update platform.yml** (rename to platform-codespaces.yml for consistency)
- Change from Kustomize to Helm
- Point to `gitops/platform-apps` with `values-codespaces.yaml`

### Tasks
- [x] Define implementation strategy
- [x] Identify codespaces-specific overrides

### Completed
- [x] Implementation strategy documented

## Code

### Phase Entrance Criteria
- [x] Implementation plan approved
- [x] Codespaces-specific values identified
- [x] Migration strategy documented

### Tasks
- [x] Add keptn application to values.yaml
- [x] Create values-codespaces.yaml
- [x] Update platform.yml to use Helm chart
- [x] Validate with helm template
- [x] Run Chainsaw tests

### Completed
- [x] Added keptn to values.yaml (disabled by default)
- [x] Created values-codespaces.yaml with keptn enabled, ingress-nginx disabled
- [x] Updated platform.yml to use Helm with values-codespaces.yaml
- [x] Helm lint passes
- [x] Helm template renders with keptn
- [x] Chainsaw tests pass (7.32s)

## Commit

### Phase Entrance Criteria
- [x] values-codespaces.yaml created
- [x] platform.yml updated to use Helm
- [x] Helm template validates
- [x] Chainsaw tests pass

### Tasks
- [x] Final validation
- [x] Document key decisions

### Completed
- [x] All acceptance criteria met
- [x] Key decisions documented

## Key Decisions

1. **Keptn added to Helm chart**: Added `keptn` application to `values.yaml` with `enabled: false` by default. Only codespaces enables it via `values-codespaces.yaml`.

2. **Consistent architecture**: All three environments (kind, minikube, codespaces) now use the same Helm chart pattern with environment-specific values files.

3. **Gateway API for codespaces**: Codespaces now uses Gateway API (envoy-gateway) instead of ingress-nginx, matching kind/minikube.

## Notes
Reference: [MOD-002 Story](analysis/modularity/stories/MOD-002-migrate-platform-yml.md)

---
*This plan is maintained by the LLM. Tool responses provide guidance on which section to focus on and what tasks to work on.*
