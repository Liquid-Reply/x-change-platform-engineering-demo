# MOD-003: Delete Legacy Apps

**P2-MEDIUM** | Low effort

[← Back to Stories](../USER-STORIES.md) | [Analysis Details](../IMPROVEMENT-ANALYSIS.md)

---

## Problem

16 files in `gitops/applications/` unused by Kind/Minikube. Includes `.BAK` and `.disabled` files.

## Acceptance Criteria

- [ ] MOD-002 complete and verified
- [ ] `gitops/applications/` directory deleted
- [ ] No references to `gitops/applications/` remain in codebase
- [ ] Chainsaw static tests pass

## Validate

```bash
# Directory removed
[ -d "gitops/applications" ] && exit 1

# No references remain
grep -r "gitops/applications" . --include="*.yml" --include="*.yaml" && exit 1

# Chainsaw tests (static - no cluster required)
cd tests/functional && chainsaw test ./07-kustomize-build
```
