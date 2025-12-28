# Development Plan: Option B - Full Kustomize Architecture

*Generated on 2025-12-08 by Vibe Feature MCP*
*Workflow: [epcc](https://mrsimpson.github.io/responsible-vibe-mcp/workflows/epcc)*

## Goal

Refactor the IDP platform to use **Full Kustomize Architecture** (Option B), minimizing Python code from ~1100 LOC to ~100 LOC while maximizing declarative configuration.

**Key Outcomes:**
- Replace Python placeholder replacement with Kustomize `replacements`
- Replace Python component toggles with Kustomize `components`
- Replace Python secret creation with Kustomize `secretGenerator`
- Create shell-based bootstrap script (~50 lines)
- Retain Python only for Dynatrace API calls (~100 lines)
- Enable adding new environments with just 2 files

---

## Explore

### Phase Entrance Criteria
- [x] Initial phase - no entrance criteria

### Tasks
- [x] Analyze current installer code structure
- [x] Identify what can move to Kustomize vs must remain Python/Shell
- [x] Document target directory structure
- [x] Create detailed analysis document (`docs/OPTION-B-KUSTOMIZE-ANALYSIS.md`)

### Findings

**Current State:**
- `minikube_installer.py`: ~680 lines
- `cluster_installer.py`: ~435 lines
- Total Python: ~1100 LOC with 60% duplication

**What Moves to Kustomize:**
| Current (Python) | Target (Kustomize) |
|------------------|-------------------|
| `do_file_replace()` | `replacements` + `configMapGenerator` |
| `os.rename()` for toggles | `components` |
| `create_k8s_secret()` | `secretGenerator` |
| Environment detection | Overlay directories |

**What Remains Python (~100 LOC):**
- Dynatrace API token creation (HTTP API)
- Dynatrace asset upload (OAuth flow)

**What Becomes Shell (~50 LOC):**
- Cluster creation (minikube/kind/k3d)
- ArgoCD bootstrap
- Token generation
- kubectl wait commands

### Completed
- [x] Created development plan file
- [x] Read and analyzed `minikube_installer.py` (680 lines)
- [x] Read and analyzed `cluster_installer.py` (435 lines)
- [x] Documented findings in `docs/OPTION-B-KUSTOMIZE-ANALYSIS.md`

---

## Plan

### Phase Entrance Criteria
- [x] Current Python code analyzed and understood
- [x] Target Kustomize features identified (replacements, components, secretGenerator)
- [x] Directory structure designed
- [x] Analysis document created and reviewed

### Tasks
- [x] Define migration phases with dependencies
- [x] Identify files to create/modify/delete
- [x] Plan backward compatibility approach
- [x] Define validation strategy

---

### Migration Phases (Detailed)

#### Phase 1: Manifest Base Structure
**Dependencies:** None
**Risk:** Low - additive only

Create `gitops/manifests/base/kustomization.yaml` that references existing platform directories:
```yaml
resources:
  - platform/namespaces
  - platform/argoconfig
  - platform/backstage
  - platform/opentelemetry
  - platform/ingress-nginx
  - platform/argo-rollouts
  - platform/kubeaudit
  - platform/cronJobs
```

**Note:** Keep existing `platform/` structure, just add kustomization wrapper.

#### Phase 2: Kustomize Components (Optional Features)
**Dependencies:** Phase 1
**Risk:** Medium - changes how optional features are enabled

| Component | Source | Condition |
|-----------|--------|-----------|
| `components/dynatrace/` | `platform/dynatrace/` | Has DT credentials |
| `components/keptn/` | `platform/keptn/` | INSTALL_KEPTN=true |
| `components/nodeport-services/` | New patches | Local clusters only |

#### Phase 3: Environment Overlays
**Dependencies:** Phase 1, Phase 2
**Risk:** Medium - core configuration change

| Overlay | Components Included | Config Source |
|---------|---------------------|---------------|
| `overlays/minikube/` | nodeport-services | `config/minikube.env` |
| `overlays/codespaces/` | dynatrace, keptn | `config/codespaces.env` |
| `overlays/kind/` | dynatrace, keptn | `config/kind.env` |

#### Phase 4: Config Files
**Dependencies:** None (parallel with Phase 1-3)
**Risk:** Low - simple key-value files

Extract from Python to `config/*.env`:
```
REPO_URL=https://github.com/...
TARGET_REVISION=main
CLUSTER_TYPE=minikube
BASE_DOMAIN=minikube
ARGOCD_PORT=30100
BACKSTAGE_PORT=30105
```

#### Phase 5: Bootstrap Script
**Dependencies:** Phase 1-4
**Risk:** High - replaces Python orchestration

`bootstrap.sh` responsibilities:
1. Cluster creation (minikube/kind/k3d switch)
2. Namespace creation
3. ArgoCD installation via `kustomize build gitops/bootstrap/...`
4. Secret application via `kustomize build gitops/manifests/overlays/...`
5. Platform root app deployment
6. ArgoCD token generation for Backstage
7. Optional: Dynatrace setup via `scripts/dynatrace.py`

#### Phase 6: Dynatrace Python Module
**Dependencies:** None (parallel)
**Risk:** Low - extraction only

Extract from installers to `scripts/dynatrace.py`:
- `create_dt_api_token()` → `create_api_token()`
- `upload_dt_document_asset()` → `upload_asset()`
- `upload_dt_workflow_asset()` → merged into `upload_asset()`
- OAuth token exchange logic

#### Phase 7: Cleanup
**Dependencies:** Phase 5 tested successfully
**Risk:** High - removes fallback

- Delete `minikube_installer.py`
- Delete `cluster_installer.py`
- Archive `environments/`, `config/`, `secrets/` Python modules
- Update documentation

---

### File Changes

#### CREATE (New Files)
| File | Purpose |
|------|---------|
| `gitops/manifests/base/kustomization.yaml` | Root manifest aggregator |
| `gitops/manifests/components/dynatrace/kustomization.yaml` | DT component |
| `gitops/manifests/components/keptn/kustomization.yaml` | Keptn component |
| `gitops/manifests/components/nodeport-services/kustomization.yaml` | NodePort patches |
| `gitops/manifests/overlays/minikube/kustomization.yaml` | Minikube config |
| `gitops/manifests/overlays/codespaces/kustomization.yaml` | Codespaces config |
| `gitops/manifests/overlays/kind/kustomization.yaml` | Kind config |
| `gitops/bootstrap/base/kustomization.yaml` | ArgoCD bootstrap |
| `gitops/bootstrap/overlays/*/kustomization.yaml` | Per-env ArgoCD config |
| `config/minikube.env` | Minikube variables |
| `config/codespaces.env` | Codespaces variables |
| `config/kind.env` | Kind variables |
| `bootstrap.sh` | Main entry point |
| `scripts/dynatrace.py` | DT API module |
| `secrets/README.md` | Secret file instructions |

#### MODIFY (Existing Files)
| File | Change |
|------|--------|
| `gitops/platform-minikube.yml` | Point to new overlay path |
| `gitops/platform-codespaces.yml` | Point to new overlay path |
| `README.md` | New usage instructions |
| `CLAUDE.md` | New structure documentation |
| `.gitignore` | Add `secrets/*` (except README) |

#### DELETE (After Testing)
| File | Replacement |
|------|-------------|
| `minikube_installer.py` | `bootstrap.sh` |
| `cluster_installer.py` | `bootstrap.sh` |
| `environments/*.py` | Kustomize overlays |
| `config/*.py` | `config/*.env` |
| `secrets/manager.py` | Kustomize secretGenerator |

---

### Backward Compatibility

**Approach:** Parallel operation during transition

1. **Phase 1-4:** Old installers still work, new structure is additive
2. **Phase 5:** Both `bootstrap.sh` AND old installers available
3. **Phase 7:** Old installers removed only after `bootstrap.sh` validated

**Rollback Plan:**
- Git revert to pre-cleanup commit restores old installers
- Keep old installers in separate branch for reference

---

### Validation Strategy

#### Per-Phase Validation

| Phase | Validation Command | Success Criteria |
|-------|-------------------|------------------|
| 1 | `kustomize build gitops/manifests/base` | No errors, outputs all manifests |
| 2 | `kustomize build gitops/manifests/base --enable-alpha-plugins` | Components loadable |
| 3 | `kustomize build gitops/manifests/overlays/minikube` | Full manifest with env values |
| 4 | `cat config/minikube.env` | All required vars present |
| 5 | `./bootstrap.sh minikube` (dry-run) | Script syntax valid |
| 6 | `python scripts/dynatrace.py --help` | Module loads |

#### Integration Validation

```bash
# Full dry-run (no cluster changes)
kustomize build gitops/manifests/overlays/minikube | kubectl apply --dry-run=client -f -

# Diff against running cluster
kustomize build gitops/manifests/overlays/minikube | kubectl diff -f -

# Full bootstrap test
./bootstrap.sh minikube
kubectl get applications -n argocd  # All should sync
```

---

### Completed
- [x] Define migration phases with dependencies
- [x] Identify files to create/modify/delete
- [x] Plan backward compatibility approach
- [x] Define validation strategy

---

## Code

### Phase Entrance Criteria
- [x] Migration phases defined with clear dependencies
- [x] File changes documented (create/modify/delete)
- [x] Backward compatibility approach agreed
- [x] Validation strategy defined

### Tasks

#### Phase 1: Base Structure
- [x] Create `gitops/manifests/base/kustomization.yaml`
- [x] Create kustomization.yaml for each platform subdirectory
- [x] Verify with `kustomize build gitops/manifests/base` (61 resources)

#### Phase 2: Optional Features (Changed Approach)
- [x] ~~Components~~ → Use direct resource references instead
- [x] Create `gitops/manifests/platform/dynatrace/kustomization.yaml`
- [x] Create `gitops/manifests/platform/keptn/kustomization.yaml`
- [x] Fix workflow.yml missing metadata.name

#### Phase 3: Overlays
- [x] Create `gitops/manifests/overlays/minikube/kustomization.yaml` (61 resources)
- [x] Create `gitops/manifests/overlays/codespaces/kustomization.yaml` (97 resources)
- [x] Create `gitops/manifests/overlays/kind/kustomization.yaml` (97 resources)
- [x] Verify overlays build correctly

#### Phase 4: Config
- [x] Create `config/minikube.env`
- [x] Create `config/codespaces.env`
- [x] Create `config/kind.env`
- [x] Create `secrets/README.md`
- [x] Update `.gitignore` for secrets

#### Phase 5: Bootstrap
- [x] Create `bootstrap.sh` (161 lines)
- [x] Test syntax with `bash -n bootstrap.sh`
- [x] Test kustomize manifests on minikube cluster (62 resources, no errors)

#### Phase 6: Dynatrace Module
- [x] Create `scripts/dynatrace.py` (219 lines)
- [x] Test module loads and --help works

#### Phase 7: Cleanup
- [x] Verify all ArgoCD apps sync with new structure
- [x] Remove `minikube_installer.py`
- [x] Remove `cluster_installer.py`
- [ ] Archive old Python modules (optional - kept for reference)

#### Documentation
- [x] Update README.md (added Local Development section)
- [ ] Update CLAUDE.md

### Completed
- [x] Created 13 kustomization.yaml files
- [x] Created bootstrap.sh (161 lines shell)
- [x] Created scripts/dynatrace.py (219 lines Python)
- [x] Created config/*.env files
- [x] Created secrets/README.md
- [x] Updated .gitignore
- [x] **Code reduction: 1116 → 380 lines (66%)**
- [x] Tested: `kubectl apply --dry-run=server` - 62 resources validated
- [x] Tested: Live apply on minikube - all apps synced (except dynatrace - no credentials)

---

## Commit

### Phase Entrance Criteria
- [x] All code tasks completed
- [x] `kustomize build` validates for all overlays
- [x] Bootstrap tested on at least one environment
- [x] Old Python installers removed

### Tasks
- [x] Remove debug statements (checked - all print statements are legitimate logging)
- [x] Update README with new usage instructions
- [ ] Update CLAUDE.md with new structure (deferred)
- [x] Final validation run (all 3 overlays build successfully)
- [x] Create commit with summary

### Completed
- [x] Final kustomize validation: minikube OK, codespaces OK, kind OK
- [x] Code cleanup reviewed - no debug artifacts found

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Use Kustomize replacements over envsubst | Native Kustomize, no external tools |
| Keep DT API calls in Python | HTTP API too complex for shell |
| Shell script for bootstrap | Simple, transparent, debuggable |
| Phase commits at transitions | Clean history, easy rollback |
| Keep existing platform/ structure | Minimize disruption, just add kustomization wrapper |
| Parallel operation during migration | Safe rollback if issues found |
| **Direct resources over components** | Kustomize components have security restrictions on external paths; direct resource references simpler |

---

## Notes

**Reference Documents:**
- `docs/OPTION-B-KUSTOMIZE-ANALYSIS.md` - Full analysis
- `docs/ARCHITECTURE-REFACTORING-ANALYSIS.md` - Options comparison

**Validation Commands:**
```bash
# Preview manifests
kustomize build gitops/manifests/overlays/minikube

# Diff against cluster
kustomize build gitops/manifests/overlays/minikube | kubectl diff -f -
```

**Edge Cases to Handle:**
1. Missing secrets files → Clear error message in bootstrap.sh
2. Unsupported environment → List available overlays
3. DT credentials optional → Skip DT setup gracefully
4. ArgoCD token generation failure → Retry logic

---
*This plan is maintained by the LLM. Tool responses provide guidance on which section to focus on and what tasks to work on.*
