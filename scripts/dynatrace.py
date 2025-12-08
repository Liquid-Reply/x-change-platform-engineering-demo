#!/usr/bin/env python3
"""
Dynatrace API Integration Module

Minimal Python for Dynatrace operations that cannot be done in shell:
- API token creation (HTTP API)
- Asset upload (OAuth flow)

Usage:
    python3 scripts/dynatrace.py --env minikube --create-tokens
    python3 scripts/dynatrace.py --env minikube --upload-assets
"""

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


def load_credentials(creds_file="secrets/dt-credentials.env"):
    """Load Dynatrace credentials from env file."""
    creds = {}
    if not os.path.exists(creds_file):
        return creds
    with open(creds_file) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                creds[k] = v
    return creds


def build_tenant_url(env_name, env_type="live"):
    """Build Dynatrace tenant URL."""
    if env_type == "sprint":
        return f"https://{env_name}.sprint.apps.dynatracelabs.com"
    elif env_type == "dev":
        return f"https://{env_name}.dev.apps.dynatracelabs.com"
    return f"https://{env_name}.live.dynatrace.com"


def create_api_token(tenant_url, rw_token, name, scopes):
    """Create a Dynatrace API token."""
    url = f"{tenant_url}/api/v2/apiTokens"
    data = json.dumps({"name": name, "scopes": scopes}).encode()

    req = Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Api-Token {rw_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("token")
    except HTTPError as e:
        print(f"Token creation failed: {e.code} - {e.read().decode()}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"Connection failed: {e.reason}", file=sys.stderr)
        return None


def get_oauth_token(sso_url, client_id, client_secret, account_urn):
    """Get OAuth bearer token for Dynatrace APIs."""
    data = urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": f"account-idm-read account-idm-write document:documents:write document:documents:read automation:workflows:write automation:workflows:read",
        "resource": account_urn
    }).encode()

    req = Request(sso_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("access_token")
    except (HTTPError, URLError) as e:
        print(f"OAuth failed: {e}", file=sys.stderr)
        return None


def upload_document(tenant_apps, bearer_token, filepath, name, doc_type):
    """Upload a document (dashboard/notebook) to Dynatrace."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}", file=sys.stderr)
        return False

    with open(filepath) as f:
        content = f.read()

    url = f"{tenant_apps}/platform/document/v1/documents"
    data = json.dumps({
        "name": name,
        "type": doc_type,
        "content": content,
        "isPrivate": False
    }).encode()

    req = Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {bearer_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=60) as resp:
            print(f"Uploaded {doc_type}: {name}")
            return True
    except HTTPError as e:
        if e.code == 409:
            print(f"Already exists: {name}")
            return True
        print(f"Upload failed: {e.code} - {e.read().decode()}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Dynatrace API integration")
    parser.add_argument("--env", default="minikube", help="Environment name")
    parser.add_argument("--create-tokens", action="store_true", help="Create API tokens")
    parser.add_argument("--upload-assets", action="store_true", help="Upload dashboards/notebooks")
    parser.add_argument("--creds", default="secrets/dt-credentials.env", help="Credentials file")
    args = parser.parse_args()

    creds = load_credentials(args.creds)
    if not creds.get("DT_RW_API_TOKEN") or not creds.get("DT_ENV_NAME"):
        print("No Dynatrace credentials found, skipping setup")
        return 0

    tenant_url = build_tenant_url(creds["DT_ENV_NAME"], creds.get("DT_ENV", "live"))
    tenant_apps = f"https://{creds['DT_ENV_NAME']}.apps.dynatrace.com"

    if args.create_tokens:
        print(f"Creating tokens for {tenant_url}...")

        tokens = {}
        tokens["DT_ALL_INGEST_TOKEN"] = create_api_token(
            tenant_url, creds["DT_RW_API_TOKEN"],
            f"[{args.env}] DT_ALL_INGEST_TOKEN",
            ["bizevents.ingest", "events.ingest", "logs.ingest",
             "metrics.ingest", "openTelemetryTrace.ingest",
             "DataExport", "entities.read", "settings.read",
             "settings.write", "activeGateTokenManagement.create"]
        )

        tokens["DT_OP_TOKEN"] = create_api_token(
            tenant_url, creds["DT_RW_API_TOKEN"],
            f"[{args.env}] DT_OP_TOKEN",
            ["InstallerDownload", "DataExport", "entities.read",
             "settings.read", "settings.write", "activeGateTokenManagement.create"]
        )

        tokens["DT_MONACO_TOKEN"] = create_api_token(
            tenant_url, creds["DT_RW_API_TOKEN"],
            f"[{args.env}] DT_MONACO_TOKEN",
            ["settings.read", "settings.write", "slo.read", "slo.write",
             "DataExport", "ExternalSyntheticIntegration", "ReadConfig", "WriteConfig"]
        )

        # Write tokens to file for use by bootstrap.sh
        output_file = f"secrets/dt-tokens-{args.env}.env"
        with open(output_file, "w") as f:
            for k, v in tokens.items():
                if v:
                    f.write(f"{k}={v}\n")
        print(f"Tokens written to {output_file}")

    if args.upload_assets:
        print(f"Uploading assets to {tenant_apps}...")

        bearer = get_oauth_token(
            "https://sso.dynatrace.com/sso/oauth2/token",
            creds.get("DT_OAUTH_CLIENT_ID", ""),
            creds.get("DT_OAUTH_CLIENT_SECRET", ""),
            creds.get("DT_OAUTH_ACCOUNT_URN", "")
        )

        if not bearer:
            print("OAuth authentication failed", file=sys.stderr)
            return 1

        # Notebooks
        notebooks = [
            ("dynatraceassets/notebooks/analyze-argocd-notification-events.json",
             f"[{args.env}] ArgoCD: Analyze Notification Events"),
            ("dynatraceassets/notebooks/argocd-log-analytics.json",
             f"[{args.env}] ArgoCD: Log Analytics"),
            ("dynatraceassets/notebooks/platform-engineering-walkthrough.json",
             f"[{args.env}] Platform Engineering Demo Walkthrough"),
        ]
        for path, name in notebooks:
            upload_document(tenant_apps, bearer, path, name, "notebook")

        # Dashboards
        dashboards = [
            ("dynatraceassets/dashboards/argocd-lifecycle-dashboard.json",
             f"[{args.env}] ArgoCD: Lifecycle Dashboard"),
            ("dynatraceassets/dashboards/argocd-platform-observability.json",
             f"[{args.env}] ArgoCD: Platform Observability"),
            ("dynatraceassets/dashboards/backstage-error-analysis.json",
             f"[{args.env}] Backstage: Error Analysis"),
            ("dynatraceassets/dashboards/platform-observability-cockpit.json",
             f"[{args.env}] Platform Observability Cockpit"),
            ("dynatraceassets/dashboards/team-ownership-dashboard.json",
             f"[{args.env}] Team Ownership Dashboard"),
        ]
        for path, name in dashboards:
            upload_document(tenant_apps, bearer, path, name, "dashboard")

    return 0


if __name__ == "__main__":
    sys.exit(main())
