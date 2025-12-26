# GitHub Token - Least Privilege Permissions

## Required Permissions

| Permission | Level | Used By |
|------------|-------|---------|
| `contents` | **write** | Backstage scaffolder (branches, commits), ArgoCD (read) |
| `pull_requests` | **write** | Backstage scaffolder (create PRs) |
| `metadata` | read | All (automatic) |

---

## Fine-Grained PAT (Recommended)

GitHub → Settings → Developer settings → Fine-grained tokens → Generate

| Setting | Value |
|---------|-------|
| Repository access | Only select repositories → `x-change-platform-engineering-demo` |
| Contents | Read and write |
| Pull requests | Read and write |

---

## Classic PAT (Alternative)

GitHub → Settings → Developer settings → Tokens (classic) → Generate

| Scope | Required |
|-------|----------|
| `repo` | ✅ (full access needed for private repos) |

---

## Apply Token

```bash
# Update secret
kubectl patch secret backstage-secrets -n backstage \
  -p="{\"data\":{\"GITHUB_TOKEN\":\"$(echo -n 'ghp_xxx' | base64)\"}}"

# Restart
kubectl rollout restart deployment/backstage -n backstage
```
