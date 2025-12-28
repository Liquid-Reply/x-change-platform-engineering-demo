# Obsolete Files Analysis

**Analysis Date:** 2025-12-27
**Branch:** gh_opus_ngix2gateway

---

## Overview

This document identifies files that may be candidates for removal, with validation analysis to prevent accidental deletion of required files.

---

## 1. Files Recommended for Deletion

### 1.1 Backup Files (.BAK)

| File | Reason | Validation | Safe to Delete |
|------|--------|------------|----------------|
| `gitops/applications/base/cron-jobs.yml.BAK` | Backup file | Not referenced in any kustomization.yaml | **YES** |
| `gitops/manifests/platform/cronJobs/kubebench.yml.BAK` | Backup file | Not referenced | **YES** |
| `gitops/manifests/platform/cronJobs/kubehunter.yml.BAK` | Backup file | Not referenced | **YES** |
| `gitops/manifests/platform/namespaces/cronjobs.yaml.BAK` | Backup file | Not referenced | **YES** |

**Validation Method:** Searched for references in kustomization files and shell scripts. None found.

### 1.2 Disabled Files

| File | Reason | Validation | Safe to Delete |
|------|--------|------------|----------------|
| `gitops/applications/base/keptn.yml.disabled` | Disabled feature | Keptn not in Helm chart values.yaml | **YES** |

**Validation Method:** Checked `gitops/platform-apps/values.yaml` - no Keptn application defined.

### 1.3 Development Copy Files

| File | Reason | Validation | Safe to Delete |
|------|--------|------------|----------------|
| `CLAUDE copy.md` | Duplicate of CLAUDE.md | Content duplication | **YES** |
| `.vibe/development-plan-gh_opus_kostumize2helm copy.md` | Development artifact | Branch-specific planning | **YES** |
| `.vibe/development-plan-gh_codespace2k8s_opus_kustomize copy.md` | Development artifact | Branch-specific planning | **YES** |

**Validation Method:** These are clearly development artifacts, not referenced in build or deploy processes.

---

## 2. Files Requiring Careful Evaluation

### 2.1 Legacy Kustomize Applications Directory

**Directory:** `gitops/applications/`

| File | Current Status | Used By | Recommendation |
|------|----------------|---------|----------------|
| `base/kustomization.yaml` | References 11 apps | platform.yml only | **KEEP TEMPORARILY** |
| `base/*.yml` (11 files) | Legacy app definitions | platform.yml only | **KEEP TEMPORARILY** |
| `overlays/minikube/` | Minikube overlay | Not used | **SAFE TO DELETE** |
| `overlays/codespaces/` | Codespaces overlay | platform.yml (default) | **KEEP** |

**Validation:**
```bash
# Only platform.yml references this directory:
grep -l "gitops/applications" gitops/*.yml
# Output: gitops/platform.yml

# platform-{minikube,kind,codespaces}.yml all use Helm chart:
grep "platform-apps" gitops/platform-*.yml
# All use gitops/platform-apps/ path
```

**Recommendation:**
- After merging Gateway API migration to main, migrate `platform.yml` to use Helm chart
- Then delete entire `gitops/applications/` directory

### 2.2 NGINX Ingress Files (Post-Migration)

**Directory:** `gitops/manifests/platform/ingress-nginx/`

| File | Lines | Status | Recommendation |
|------|-------|--------|----------------|
| `kustomization.yaml` | 5 | References deploy.yml | **DELETE AFTER MIGRATION** |
| `deploy.yml` | 663 | Full NGINX deployment | **DELETE AFTER MIGRATION** |

**Validation:**
- `ingress-nginx` is `enabled: false` in values.yaml
- Tests now reference Gateway API (envoy-gateway)
- Customer app templates use HTTPRoute, not Ingress

**Recommendation:** Safe to delete after:
1. Helm chart `ingress-nginx.enabled: false` is merged to main
2. All customer apps migrated to HTTPRoute

### 2.3 Namespace for ingress-nginx

**File:** `gitops/manifests/platform/namespaces/ingress-nginx.yaml`

| Status | Validation | Recommendation |
|--------|------------|----------------|
| Still deployed | May be referenced by overlays | **DELETE AFTER MIGRATION** |

**Validation:**
```bash
grep -r "ingress-nginx" gitops/manifests/
# Found in: overlays, base/kustomization.yaml
```

**Recommendation:** Remove after overlay cleanup.

---

## 3. Files to NOT Delete (False Positives)

### 3.1 Config Profile Files

**Directory:** `config/profiles/`

| File | Status | Recommendation |
|------|--------|----------------|
| `minikube.yaml` | Not currently used by bootstrap.sh | **KEEP** |
| `kind.yaml` | Not currently used by bootstrap.sh | **KEEP** |
| `codespaces.yaml` | Not currently used by bootstrap.sh | **KEEP** |

**Reason to Keep:**
- These provide good documentation of component toggles
- Could be implemented in bootstrap.sh for selective component installation
- Represent intentional architecture decision

### 3.2 Keptn Manifests

**Directory:** `gitops/manifests/platform/keptn/`

| Status | Used By | Recommendation |
|--------|---------|----------------|
| Active manifests | Kind overlay | **KEEP** |

**Validation:**
```yaml
# gitops/manifests/overlays/kind/kustomization.yaml includes:
resources:
  - ../../platform/keptn
```

### 3.3 Dynatrace Assets

**Directory:** `dynatraceassets/`

| Status | Recommendation |
|--------|----------------|
| Active integration | **KEEP** |

**Reason:** Used for optional Dynatrace integration in demos.

---

## 4. Deletion Commands

### Phase 1: Immediate (Safe Deletions)

```bash
# Backup files
rm -f gitops/applications/base/cron-jobs.yml.BAK
rm -f gitops/manifests/platform/cronJobs/kubebench.yml.BAK
rm -f gitops/manifests/platform/cronJobs/kubehunter.yml.BAK
rm -f gitops/manifests/platform/namespaces/cronjobs.yaml.BAK

# Disabled files
rm -f gitops/applications/base/keptn.yml.disabled

# Development copy files
rm -f "CLAUDE copy.md"
rm -f ".vibe/development-plan-gh_opus_kostumize2helm copy.md"
rm -f ".vibe/development-plan-gh_codespace2k8s_opus_kustomize copy.md"

# Unused overlay
rm -rf gitops/applications/overlays/minikube/
```

### Phase 2: Post-Migration (After Main Merge)

```bash
# NGINX Ingress (after Gateway API migration complete)
rm -rf gitops/manifests/platform/ingress-nginx/
rm -f gitops/manifests/platform/namespaces/ingress-nginx.yaml

# Update base kustomization to remove ingress-nginx reference
# Then delete legacy applications directory:
# rm -rf gitops/applications/
```

---

## 5. Impact Analysis

### 5.1 If Phase 1 Deletions Applied

| Impact | Severity | Notes |
|--------|----------|-------|
| Repository size | Reduced by ~10KB | Minor improvement |
| Developer confusion | Reduced | No more "what is this .BAK file?" |
| Git history | Preserved | Files remain in history |

### 5.2 If Phase 2 Deletions Applied

| Impact | Severity | Notes |
|--------|----------|-------|
| NGINX Ingress capability | Removed | By design (Gateway API migration) |
| Legacy app management | Removed | Helm chart is the new standard |
| Repository size | Reduced by ~700 lines | Significant cleanup |

---

## 6. Verification Checklist

Before deleting any file, verify:

- [ ] File is not referenced in any kustomization.yaml
- [ ] File is not sourced in any shell script
- [ ] File is not imported in any Helm template
- [ ] File is not referenced in documentation (or update docs)
- [ ] File removal does not break CI/CD pipelines
- [ ] Chainsaw tests still pass after removal

---

## 7. Summary

| Category | Count | Action |
|----------|-------|--------|
| Safe to delete now | 8 files + 1 directory | Phase 1 |
| Delete after migration | ~15 files | Phase 2 |
| Keep (false positives) | ~10 files | No action |
| Requires migration first | 1 directory (applications/) | After main merge |
