# Responsible Vibe Workflow Instructions

You are an AI assistant that helps users develop software features using the responsible-vibe-mcp server.

**IMPORTANT**: Call whats_next() after each user message to get phase-specific instructions and maintain the development workflow.

Each tool call returns a JSON response with an "instructions" field. Follow these instructions immediately after you receive them.

Do not use your own task management tools. Use the development plan which you will retrieve via whats_next() for all task tracking and project management.

# Repository Guidelines

## Project Structure & Module Organization
- `gitops/` owns the GitOps flow: root app (`platform.yml`), platform apps (`applications/platform`), manifests (`manifests/platform`), and Monaco configs.
- `apptemplates/simplenodeservice-content/` is the Backstage scaffolder source (rollout/ingress/service YAML, Monaco config, Backstage entity templates); new apps land under `customer-apps/*/` and are auto-discovered by the ApplicationSet.
- `backstagetemplates/` holds platform-level Backstage entities; `dynatraceassets/` contains dashboards, notebooks, and workflows uploaded during install.
- `.devcontainer/` bootstraps Codespaces; `cluster_installer.py` orchestrates install, token creation, and placeholder substitution; `renew_api_token.py` handles daily DT token expiry.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` – install Python deps for installer and pytest hooks.
- `python3 cluster_installer.py` – recreate Kind + ArgoCD + Backstage, apply Monaco assets, and substitute placeholders (expects DT/GitHub env vars in Codespaces).
- `python3 renew_api_token.py` – refresh DT tokens (expire ~24h).
- `pytest codespaces_test.py` or `pytest -k <name>` – integration checks; assumes cluster is up and `kubectl` points to Kind. Use `--export-traces` when debugging OTEL collector readiness.

## Coding Style & Naming Conventions
- Python: PEP 8, prefer type hints, keep sensitive strings out of logs (mirror `SENSITIVE_WORDS` filter in `utils.py`).
- YAML/JSON: 2-space indent, lowercase K8s resource names, keep install-time placeholders (`DT_TENANT_LIVE_PLACEHOLDER`, `GITHUB_REPOSITORY_PLACEHOLDER`, etc.) intact.
- Docs: concise Markdown; reference images from `images/`.

## Testing Guidelines
- Tests live in `codespaces_test.py` and expect the full platform; run after `cluster_installer.py` completes (setup is ~10 minutes on Codespaces).
- Required env vars before installer/tests: `DT_RW_API_TOKEN`, `DT_ENV_NAME`, `DT_ENV`, `DT_OAUTH_CLIENT_ID`, `DT_OAUTH_CLIENT_SECRET`, `DT_OAUTH_ACCOUNT_URN`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`.
- Argo sync order matters: platform apps → DT operator → OTEL/Keptn/ingress → Backstage → customer apps; rerun targeted tests after touching corresponding waves.

## Commit & Pull Request Guidelines
- Write imperative commits (e.g., `add argocd notification tweak`); group related manifest edits.
- PRs: describe changes, validation steps (commands/tests), and platform impact (cluster behavior, Backstage template changes, DT assets). Add screenshots for UI/template updates.
- Link issues/templates affected; never commit secrets or generated tokens. Respect auto-merge behavior for Backstage-generated PRs.

## Security & Configuration Tips
- Keep secrets in Codespaces/repo secrets; do not widen RBAC beyond existing roles. When disabling components (e.g., Keptn), follow the rename-to-`.BAK` approach in `cluster_installer.py` so ArgoCD ignores manifests without deleting live resources.
- Observe OTEL/Dynatrace hooks: PreSync applies Monaco; PostSync runs KubeAudit. Validate modifications with `kubectl get workflows -n argocd` and DT traces/logs.
