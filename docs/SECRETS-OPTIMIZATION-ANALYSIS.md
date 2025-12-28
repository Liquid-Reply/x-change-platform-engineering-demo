# Secret Management Optimization Analysis

## Current State: Three Redundant Systems

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CURRENT SECRET INPUT MECHANISMS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. YAML Format              2. Single File           3. ENV Format          │
│  ─────────────              ─────────────            ──────────────          │
│  secrets-minikube.yaml      secrets/github-token     secrets/dt-credentials │
│  (nested structure)         (plain text)             (KEY=VALUE)            │
│          │                        │                        │                │
│          ▼                        ▼                        ▼                │
│  secrets/manager.py ◄──────── UNUSED!                                       │
│  (Python class)               bootstrap.sh ◄───────── scripts/dynatrace.py │
│          │                        │                        │                │
│          ▼                        ▼                        ▼                │
│       NOTHING              K8s Secrets              DT Token Gen            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Analysis Summary

| Component | Format | Consumer | Status |
|-----------|--------|----------|--------|
| `secrets-minikube.yaml.example` | YAML | Documentation only | **UNUSED** |
| `secrets-minikube.yaml` | YAML | `secrets/manager.py` | **DEAD CODE** |
| `secrets/manager.py` | Python | Nothing imports it | **DELETE** |
| `secrets/__init__.py` | Python | Only exports manager | **DELETE** |
| `secrets/github-token` | Plain text | `bootstrap.sh` | **ACTIVE** |
| `secrets/dt-credentials.env` | ENV | `scripts/dynatrace.py` | **ACTIVE** |

### Key Finding: `secrets/manager.py` is Completely Unused

```bash
# Search for imports from secrets module
grep -r "from secrets import\|import secrets" *.py
# Result: No matches (except secrets/__init__.py itself)
```

The Python `SecretsManager` class was designed to read `secrets-minikube.yaml` but:
- No Python file imports it
- `bootstrap.sh` handles all K8s secret creation
- It's 390 lines of dead code

### Documentation Inconsistency

| Source | Says to Use |
|--------|-------------|
| `README-MINIKUBE.md` | `secrets-minikube.yaml` (YAML format) |
| `secrets/README.md` | `secrets/github-token` + `secrets/dt-credentials.env` |
| `bootstrap.sh` | `secrets/github-token` (actual behavior) |

---

## Proposed Optimization

### Target State: Single `.env` File Per Environment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      OPTIMIZED SECRET INPUT                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                      secrets/<env>.env                                       │
│                      ─────────────────                                       │
│                      GITHUB_TOKEN=ghp_xxx                                    │
│                      DT_ENV_NAME=abc123                                      │
│                      DT_RW_API_TOKEN=dt0c01.xxx                              │
│                      ...                                                     │
│                             │                                                │
│              ┌──────────────┴──────────────┐                                 │
│              ▼                              ▼                                │
│        bootstrap.sh                  scripts/dynatrace.py                   │
│              │                              │                                │
│              ▼                              ▼                                │
│        K8s Secrets                    DT Token Gen                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Create New Structure

```bash
# New files to create
secrets/
├── template.env          # Example with documentation
├── minikube.env          # User's actual secrets (gitignored)
├── codespaces.env        # Codespaces secrets (gitignored)
└── README.md             # Updated documentation
```

**`secrets/template.env`** content:
```bash
# IDP Platform Secrets
# Copy to secrets/<env>.env and fill values

# Required: GitHub Personal Access Token
GITHUB_TOKEN=

# Optional: Dynatrace (leave empty to skip)
DT_ENV_NAME=
DT_ENV=live
DT_RW_API_TOKEN=
DT_OAUTH_CLIENT_ID=
DT_OAUTH_CLIENT_SECRET=
DT_OAUTH_ACCOUNT_URN=
```

### Phase 2: Update `bootstrap.sh`

**Current** (lines 26-27, 66):
```bash
[[ -f "${SCRIPT_DIR}/secrets/github-token" ]] || error "Missing secrets/github-token"
GITHUB_TOKEN=$(cat "${SCRIPT_DIR}/secrets/github-token")
```

**After**:
```bash
SECRETS_FILE="${SCRIPT_DIR}/secrets/${ENV}.env"
[[ -f "${SECRETS_FILE}" ]] || error "Missing ${SECRETS_FILE}. Copy from secrets/template.env"

# Load secrets
set -a
source "${SECRETS_FILE}"
set +a

[[ -n "${GITHUB_TOKEN:-}" ]] || error "GITHUB_TOKEN not set in ${SECRETS_FILE}"
```

### Phase 3: Update `scripts/dynatrace.py`

**Current** (line 23):
```python
def load_credentials(creds_file="secrets/dt-credentials.env"):
```

**After**:
```python
def load_credentials(env="minikube"):
    """Load credentials from secrets/<env>.env"""
    creds_file = f"secrets/{env}.env"
```

### Phase 4: Delete Obsolete Files

```bash
# Files to delete
rm secrets-minikube.yaml.example
rm secrets-minikube.yaml           # If exists (gitignored)
rm secrets/manager.py
rm secrets/__init__.py
rm secrets/github-token            # Migrate content first!
rm secrets/dt-credentials.env      # Migrate content first!
```

### Phase 5: Update Documentation

| File | Changes |
|------|---------|
| `README-MINIKUBE.md` | Replace YAML instructions with `.env` format |
| `secrets/README.md` | Simplify to single file approach |
| `docs/SECRETS.md` | Already updated (current doc) |
| `config/profiles/minikube.yaml` | Remove `secrets.local_file` reference |

### Phase 6: Update `.gitignore`

**Current**:
```gitignore
secrets-minikube.yaml
secrets-*.yaml
secrets/*
!secrets/README.md
```

**After**:
```gitignore
# Secrets (env files contain sensitive data)
secrets/*.env
!secrets/template.env
```

---

## Migration Checklist

- [ ] Create `secrets/template.env`
- [ ] Update `bootstrap.sh` to source `secrets/${ENV}.env`
- [ ] Update `scripts/dynatrace.py` to use new path
- [ ] Test with minikube environment
- [ ] Delete `secrets/manager.py` and `secrets/__init__.py`
- [ ] Delete `secrets-minikube.yaml.example`
- [ ] Update `README-MINIKUBE.md`
- [ ] Update `secrets/README.md`
- [ ] Update `.gitignore`
- [ ] Update `config/profiles/minikube.yaml` (remove secrets.local_file)
- [ ] Test full bootstrap flow

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing users | Medium | Document migration path clearly |
| Losing secrets during migration | High | Warn users to backup before update |
| Codespaces compatibility | Low | Codespaces uses env vars, not files |

---

## Benefits

1. **Simplicity**: One file format (`.env`) instead of three
2. **Consistency**: Same format as `config/<env>.env`
3. **Less code**: Delete 390 lines of unused Python
4. **Clarity**: One source of truth per environment
5. **Tooling**: `.env` files work with standard tools (direnv, dotenv, etc.)
