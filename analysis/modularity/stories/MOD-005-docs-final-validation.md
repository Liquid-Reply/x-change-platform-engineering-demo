# MOD-005: Docs + Final Validation

**P2-MEDIUM** | Medium effort

[← Back to Stories](../USER-STORIES.md) | [Analysis Details](../IMPROVEMENT-ANALYSIS.md)

---

## Problem

Run after MOD-001–004 complete. Documentation needs updating and final validation required.

## Acceptance Criteria

- [ ] CLAUDE.md reflects new configuration approach
- [ ] README files reference correct paths
- [ ] References to deleted directories removed
- [ ] Single source of truth architecture documented
- [ ] All Chainsaw functional tests pass
- [ ] Helm template validates for all environments
- [ ] Bootstrap works for minikube, kind, codespaces
- [ ] ArgoCD syncs successfully

## Final Validation Script

```bash
#!/bin/bash
set -e

# Config consolidation
grep -r "TARGET_REVISION" config/ && exit 1
grep -r "^REPO_URL" config/ && exit 1

# Directories removed
[ -d "config/profiles" ] && exit 1
[ -d "gitops/applications" ] && exit 1

# Helm validation
helm lint gitops/platform-apps
for env in minikube kind codespaces; do
  helm template platform gitops/platform-apps \
    -f gitops/platform-apps/values.yaml \
    -f gitops/platform-apps/values-${env}.yaml > /dev/null
done

# Chainsaw tests
cd tests/functional && chainsaw test .
```
