# MOD-002: Migrate platform.yml to Helm

**P1-HIGH** | Medium effort

[← Back to Stories](../USER-STORIES.md) | [Analysis Details](../IMPROVEMENT-ANALYSIS.md)

---

## Problem

`platform.yml` uses Kustomize (`gitops/applications/`) while others use Helm (`gitops/platform-apps`). Unify to Helm.

## Acceptance Criteria

- [x] Create `values-codespaces.yaml` with codespaces-specific settings
- [x] Update `platform.yml` to use Helm chart with valueFiles
- [x] Codespaces deployment works with new configuration
- [x] Compare Kustomize vs Helm output for parity (keptn added to Helm)
- [x] Chainsaw static tests pass

## Validate

```bash
# Output comparison
kustomize build gitops/applications/overlays/codespaces > /tmp/kustomize.yaml
helm template platform gitops/platform-apps -f values.yaml -f values-codespaces.yaml > /tmp/helm.yaml
diff /tmp/kustomize.yaml /tmp/helm.yaml

# Chainsaw tests (static - no cluster required)
cd tests/functional && chainsaw test ./07-kustomize-build
```
