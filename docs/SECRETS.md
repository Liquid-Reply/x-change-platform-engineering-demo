# Secret Management

## Overview

```
secrets/<env>.env  ──►  bootstrap.sh  ──►  K8s Secrets
     │                       │
     │                       ├──► github-token (argocd)
     │                       ├──► backstage-secrets (backstage)
     │                       └──► dt-details (opentelemetry)
     │
     └──► scripts/dynatrace.py (if DT_ENV_NAME set)
              └──► DT token generation + asset upload
```

## Setup

```bash
cp secrets/template.env secrets/minikube.env
vim secrets/minikube.env  # Add GITHUB_TOKEN (required)
./bootstrap.sh minikube
```

## Secret File Format

```bash
# secrets/<env>.env

# Required
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Optional: Dynatrace
DT_ENV_NAME=abc12345
DT_ENV=live
DT_RW_API_TOKEN=dt0c01.xxx
DT_OAUTH_CLIENT_ID=dt0s02.xxx
DT_OAUTH_CLIENT_SECRET=xxx
DT_OAUTH_ACCOUNT_URN=urn:dtaccount:xxx
```

## K8s Secrets Created

| Secret | Namespace | Required |
|--------|-----------|----------|
| `github-token` | argocd | Yes |
| `backstage-secrets` | backstage | Yes |
| `dt-details` | opentelemetry | No (placeholder if no DT) |

## Files

```
secrets/
├── template.env      # Example (committed)
├── minikube.env      # Your secrets (gitignored)
└── README.md
```
