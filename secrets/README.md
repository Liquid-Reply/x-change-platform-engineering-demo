# Secrets Directory

Platform secrets are stored as `.env` files in this directory.

## Setup

```bash
# Copy the template
cp secrets/template.env secrets/minikube.env

# Edit with your values
vim secrets/minikube.env

# Run bootstrap
./bootstrap.sh minikube
```

## File Structure

```
secrets/
├── template.env      # Example (committed to git)
├── minikube.env      # Your minikube secrets (gitignored)
├── codespaces.env    # Codespaces secrets (gitignored)
└── README.md         # This file
```

## Required Values

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope |

## Optional: Dynatrace

| Variable | Description |
|----------|-------------|
| `DT_ENV_NAME` | Environment ID (e.g., `abc12345`) |
| `DT_ENV` | Environment type: `live`, `sprint`, `dev` |
| `DT_RW_API_TOKEN` | Read-write API token |
| `DT_OAUTH_CLIENT_ID` | OAuth client ID |
| `DT_OAUTH_CLIENT_SECRET` | OAuth client secret |
| `DT_OAUTH_ACCOUNT_URN` | Account URN |

## Security

- Files matching `secrets/*.env` are gitignored (except `template.env`)
- Never commit actual secrets
- Rotate tokens regularly
