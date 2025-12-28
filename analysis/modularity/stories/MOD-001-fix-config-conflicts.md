# MOD-001: Fix Config Conflicts

**P0-CRITICAL** | Low effort

[← Back to Stories](../USER-STORIES.md) | [Analysis Details](../IMPROVEMENT-ANALYSIS.md)

---

## Problem

3 files define `targetRevision` with conflicting values. Remove duplicates, keep ONE source.

| Source | File | Current Value |
|--------|------|---------------|
| Shell env | `config/kind.env:15` | `gh_opus_kostumize2helm` |
| Root App | `platform-kind.yml:12` | `gh_opus_kostumize2helm` |
| Helm values | `values-kind.yaml:8` | `gh_opus_ngix2gateway` |

## Acceptance Criteria

- [x] Remove `TARGET_REVISION` from all `config/*.env` files
- [x] Remove `REPO_URL` from all `config/*.env` files
- [x] Ensure `platform-*.yml` and `values-*.yaml` use MATCHING targetRevision
- [x] Feature branches allowed (e.g., `gh_opus_ngix2gateway`) - just no conflicts
- [x] All Git config lives only in ArgoCD manifests (not .env files)
- [x] Helm template validates
- [x] Bootstrap works without Git variables (uses `git remote get-url origin`)

## Valid targetRevision Options

| Option | Use Case | Example |
|--------|----------|---------|
| Feature branch | Development | `gh_opus_ngix2gateway` |
| HEAD | Dynamic tracking | `HEAD` |
| Tag | Production | `v1.0.0` |

## Validate

```bash
# Config cleanup
grep -r "TARGET_REVISION" config/ && exit 1
grep -r "^REPO_URL" config/ && exit 1

# Helm validation
helm lint gitops/platform-apps

# Chainsaw tests (static - no cluster required)
cd tests/functional && chainsaw test ./07-kustomize-build
```
