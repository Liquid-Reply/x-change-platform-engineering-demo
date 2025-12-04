#!/usr/bin/env python3
"""
IDP Platform Cluster Installer

Universal installer that works in both GitHub Codespaces and local minikube environments.
Automatically detects the environment and uses appropriate configuration.

For direct minikube usage, prefer: python3 minikube_installer.py
"""

import os
import sys
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to use new abstraction, fall back to legacy for Codespaces
try:
    from environments import EnvironmentFactory
    from config import ProfileLoader
    from secrets.manager import get_secrets_manager
    USE_ABSTRACTION = True
except ImportError:
    USE_ABSTRACTION = False
    logger.info("Environment abstraction not available, using legacy mode")

# Import legacy utils (still needed for DT functions)
from utils import *

ARGOCD_VERSION = "v2.12.2"


def run_legacy_codespaces_install():
    """
    Legacy installation for GitHub Codespaces.

    This preserves the original behavior for Codespaces environments.
    """
    # Validate environment variables
    if (
        DT_RW_API_TOKEN is None or
        DT_ENV_NAME is None or
        DT_ENV is None or
        DT_OAUTH_CLIENT_ID is None or
        DT_OAUTH_CLIENT_SECRET is None or
        DT_OAUTH_ACCOUNT_URN is None
    ):
        exit("Missing mandatory environment variables. Cannot proceed. Exiting.")

    # Build DT environment URLs
    DT_TENANT_APPS, DT_TENANT_LIVE = build_dt_urls(dt_env_name=DT_ENV_NAME, dt_env=DT_ENV)

    # Get correct SSO URL
    DT_SSO_TOKEN_URL = get_sso_token_url(dt_env=DT_ENV)

    # Create other DT tokens
    DT_ALL_INGEST_TOKEN = create_dt_api_token(token_name="[devrel demo] DT_ALL_INGEST_TOKEN", scopes=[
        "bizevents.ingest",
        "events.ingest",
        "logs.ingest",
        "metrics.ingest",
        "openTelemetryTrace.ingest",
        "DataExport",
        "entities.read",
        "settings.read",
        "settings.write",
        "activeGateTokenManagement.create"
    ], dt_rw_api_token=DT_RW_API_TOKEN, dt_tenant_live=DT_TENANT_LIVE)

    DT_OP_TOKEN = create_dt_api_token(token_name="[devrel demo] DT_OP_TOKEN", scopes=[
        "InstallerDownload",
        "DataExport",
        "entities.read",
        "settings.read",
        "settings.write",
        "activeGateTokenManagement.create"
    ], dt_rw_api_token=DT_RW_API_TOKEN, dt_tenant_live=DT_TENANT_LIVE)

    DT_MONACO_TOKEN = create_dt_api_token(token_name="[devrel demo] DT_MONACO_TOKEN", scopes=[
        "settings.read",
        "settings.write",
        "slo.read",
        "slo.write",
        "DataExport",
        "ExternalSyntheticIntegration",
        "ReadConfig",
        "WriteConfig"
    ], dt_rw_api_token=DT_RW_API_TOKEN, dt_tenant_live=DT_TENANT_LIVE)

    # Keptn toggle
    INSTALL_KEPTN = os.environ.get("INSTALL_KEPTN", "true")

    if INSTALL_KEPTN.lower() == "false" or INSTALL_KEPTN.lower() == "no":
        try:
            os.rename(src="gitops/applications/platform/keptn.yml",
                     dst="gitops/applications/platform/keptn.yml.BAK")
            os.rename(src="gitops/manifests/platform/keptn/keptn-metrics.yml",
                     dst="gitops/manifests/platform/keptn/keptn-metrics.yml.BAK")
            os.rename(src="gitops/manifests/platform/keptn/otelcol-keptnconfig.yml",
                     dst="gitops/manifests/platform/keptn/otelcol-keptnconfig.yml.BAK")
            git_commit(target_file="-A", commit_msg="do not install Keptn", push=True)
        except:
            print("Exception caught renaming Keptn files. Continuing.")

    # Set DT GEOLOCATION
    DT_GEOLOCATION = get_geolocation(dt_env=DT_ENV)

    # Delete cluster first
    run_command(["kind", "delete", "cluster"])

    # Find and replace placeholders
    do_file_replace(pattern="./**/*.y*ml", find_string="DT_TENANT_LIVE_PLACEHOLDER",
                   replace_string=DT_TENANT_LIVE, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="DT_TENANT_LIVE_PLACEHOLDER",
                   replace_string=DT_TENANT_LIVE, recursive=True)
    git_commit(target_file="-A", commit_msg="update DT_TENANT_LIVE_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="DT_TENANT_APPS_PLACEHOLDER",
                   replace_string=DT_TENANT_APPS, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="DT_TENANT_APPS_PLACEHOLDER",
                   replace_string=DT_TENANT_APPS, recursive=True)
    do_file_replace(pattern="./apptemplates/docs/*.md", find_string="DT_TENANT_APPS_PLACEHOLDER",
                   replace_string=DT_TENANT_APPS, recursive=False)
    git_commit(target_file="-A", commit_msg="update DT_TENANT_APPS_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="GITHUB_DOT_COM_REPO_PLACEHOLDER",
                   replace_string=GITHUB_DOT_COM_REPO, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="GITHUB_DOT_COM_REPO_PLACEHOLDER",
                   replace_string=GITHUB_DOT_COM_REPO, recursive=True)
    git_commit(target_file="-A", commit_msg="update GITHUB_DOT_COM_REPO_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="GEOLOCATION_PLACEHOLDER",
                   replace_string=DT_GEOLOCATION, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="GEOLOCATION_PLACEHOLDER",
                   replace_string=DT_GEOLOCATION, recursive=True)
    git_commit(target_file="-A", commit_msg="update GEOLOCATION_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="GITHUB_REPOSITORY_PLACEHOLDER",
                   replace_string=GITHUB_ORG_SLASH_REPOSITORY, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="GITHUB_REPOSITORY_PLACEHOLDER",
                   replace_string=GITHUB_ORG_SLASH_REPOSITORY, recursive=True)
    do_file_replace(pattern="./apptemplates/docs/*.md", find_string="GITHUB_REPOSITORY_PLACEHOLDER",
                   replace_string=GITHUB_ORG_SLASH_REPOSITORY, recursive=False)
    git_commit(target_file="-A", commit_msg="update GITHUB_REPOSITORY_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="GITHUB_REPO_NAME_PLACEHOLDER",
                   replace_string=GITHUB_REPO_NAME, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="GITHUB_REPO_NAME_PLACEHOLDER",
                   replace_string=GITHUB_REPO_NAME, recursive=True)
    git_commit(target_file="-A", commit_msg="update GITHUB_REPO_NAME_PLACEHOLDER", push=False)

    github_org = get_github_org(github_repo=GITHUB_ORG_SLASH_REPOSITORY)
    do_file_replace(pattern="./**/*.y*ml", find_string="GITHUB_ORG_NAME_PLACEHOLDER",
                   replace_string=github_org, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="GITHUB_ORG_NAME_PLACEHOLDER",
                   replace_string=github_org, recursive=True)
    git_commit(target_file="-A", commit_msg="update GITHUB_ORG_NAME_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="CODESPACE_NAME_PLACEHOLDER",
                   replace_string=CODESPACE_NAME, recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="CODESPACE_NAME_PLACEHOLDER",
                   replace_string=CODESPACE_NAME, recursive=True)
    do_file_replace(pattern="./apptemplates/docs/*.md", find_string="CODESPACE_NAME_PLACEHOLDER",
                   replace_string=CODESPACE_NAME, recursive=False)
    git_commit(target_file="-A", commit_msg="update CODESPACE_NAME_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="ARGOCD_PORT_NUMBER_PLACEHOLDER",
                   replace_string=f"{ARGOCD_PORT_NUMBER}", recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="ARGOCD_PORT_NUMBER_PLACEHOLDER",
                   replace_string=f"{ARGOCD_PORT_NUMBER}", recursive=True)
    do_file_replace(pattern="./apptemplates/docs/*.md", find_string="ARGOCD_PORT_NUMBER_PLACEHOLDER",
                   replace_string=f"{ARGOCD_PORT_NUMBER}", recursive=False)
    git_commit(target_file="-A", commit_msg="update ARGOCD_PORT_NUMBER_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="DEMO_APP_PORT_NUMBER_PLACEHOLDER",
                   replace_string=f"{DEMO_APP_PORT_NUMBER}", recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="DEMO_APP_PORT_NUMBER_PLACEHOLDER",
                   replace_string=f"{DEMO_APP_PORT_NUMBER}", recursive=True)
    git_commit(target_file="-A", commit_msg="update DEMO_APP_PORT_NUMBER_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml", find_string="BACKSTAGE_PORT_NUMBER_PLACEHOLDER",
                   replace_string=f"{BACKSTAGE_PORT_NUMBER}", recursive=True)
    do_file_replace(pattern="./**/*.json", find_string="BACKSTAGE_PORT_NUMBER_PLACEHOLDER",
                   replace_string=f"{BACKSTAGE_PORT_NUMBER}", recursive=True)
    git_commit(target_file="-A", commit_msg="update BACKSTAGE_PORT_NUMBER_PLACEHOLDER", push=False)

    do_file_replace(pattern="./**/*.y*ml",
                   find_string="GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN_PLACEHOLDER",
                   replace_string=GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN, recursive=True)
    do_file_replace(pattern="./**/*.json",
                   find_string="GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN_PLACEHOLDER",
                   replace_string=GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN, recursive=True)
    do_file_replace(pattern="./apptemplates/docs/*.md",
                   find_string="GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN_PLACEHOLDER",
                   replace_string=GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN, recursive=False)
    git_commit(target_file="-A", commit_msg="update GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN_PLACEHOLDER",
              push=True)

    # Upload DT Assets
    type_nb = "notebook"
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/notebooks/analyze-argocd-notification-events.json",
                            name="[devrel demo] ArgoCD: Analyze Notification Events",
                            type=type_nb, dt_tenant_apps=DT_TENANT_APPS)
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/notebooks/argocd-log-analytics.json",
                            name="[devrel demo] ArgoCD: Log Analytics",
                            type=type_nb, dt_tenant_apps=DT_TENANT_APPS)
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/notebooks/platform-engineering-walkthrough.json",
                            name="[devrel demo] Platform Engineering Demo Walkthrough",
                            type=type_nb, dt_tenant_apps=DT_TENANT_APPS)

    type_db = "dashboard"
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/dashboards/argocd-lifecycle-dashboard.json",
                            name="[devrel demo] ArgoCD: Lifecycle Dashboard",
                            type=type_db, dt_tenant_apps=DT_TENANT_APPS)
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/dashboards/argocd-platform-observability.json",
                            name="[devrel demo] ArgoCD: Platform Observability",
                            type=type_db, dt_tenant_apps=DT_TENANT_APPS)
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/dashboards/backstage-error-analysis.json",
                            name="[devrel demo] Backstage: Error Analysis",
                            type=type_db, dt_tenant_apps=DT_TENANT_APPS)
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/dashboards/platform-observability-cockpit.json",
                            name="[devrel demo] Platform Observability Cockpit",
                            type=type_db, dt_tenant_apps=DT_TENANT_APPS)
    upload_dt_document_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/dashboards/team-ownership-dashboard.json",
                            name="[devrel demo] Team Ownership Dashboard",
                            type=type_db, dt_tenant_apps=DT_TENANT_APPS)

    upload_dt_workflow_asset(sso_token_url=DT_SSO_TOKEN_URL,
                            path="dynatraceassets/workflows/lifecycle-events-workflow.json",
                            name="[devrel demo] Lifecycle Events Workflow",
                            dt_tenant_apps=DT_TENANT_APPS)

    # Create Kind cluster
    output = run_command(["kind", "create", "cluster", "--config",
                         ".devcontainer/kind-cluster.yml", "--wait", STANDARD_TIMEOUT])

    # Create namespaces
    namespaces = ["argocd", "opentelemetry", "backstage", "monaco", "dynatrace"]
    for namespace in namespaces:
        output = run_command(["kubectl", "create", "namespace", namespace])

    # Create secrets
    output = run_command(["kubectl", "-n", "argocd", "create", "secret", "generic",
                         "github-token", f"--from-literal=token={GITHUB_TOKEN}"])

    output = run_command(["kubectl", "-n", "dynatrace", "create", "secret", "generic",
                         "dt-bizevent-oauth-details",
                         f"--from-literal=dtTenant={DT_TENANT_LIVE}",
                         f"--from-literal=oAuthClientID={DT_OAUTH_CLIENT_ID}",
                         f"--from-literal=oAuthClientSecret={DT_OAUTH_CLIENT_SECRET}",
                         f"--from-literal=accountURN={DT_OAUTH_ACCOUNT_URN}"])
    output = run_command(["kubectl", "-n", "opentelemetry", "create", "secret", "generic",
                         "dt-bizevent-oauth-details",
                         f"--from-literal=dtTenant={DT_TENANT_LIVE}",
                         f"--from-literal=oAuthClientID={DT_OAUTH_CLIENT_ID}",
                         f"--from-literal=oAuthClientSecret={DT_OAUTH_CLIENT_SECRET}",
                         f"--from-literal=accountURN={DT_OAUTH_ACCOUNT_URN}"])

    # Install ArgoCD
    print(f"Installing argo cd version: {ARGOCD_VERSION}")
    output = run_command(["kubectl", "apply", "-n", "argocd", "-f",
                         f"https://raw.githubusercontent.com/argoproj/argo-cd/{ARGOCD_VERSION}/manifests/install.yaml"])

    output = run_command(["kubectl", "wait", "--for=condition=Available=True",
                         "deployments", "-n", "argocd", "--all", f"--timeout={STANDARD_TIMEOUT}"])

    # Configure ArgoCD
    output = run_command(["kubectl", "apply", "-n", "argocd", "-f",
                         "gitops/manifests/platform/argoconfig/argocd-cm.yml"])
    output = run_command(["kubectl", "apply", "-n", "argocd", "-f",
                         "gitops/manifests/platform/argoconfig/argocd-no-tls.yml"])
    output = run_command(["kubectl", "apply", "-n", "argocd", "-f",
                         "gitops/manifests/platform/argoconfig/argocd-nodeport.yml"])

    # Create argocd-notifications-secret
    output = run_command(["kubectl", "-n", "argocd", "delete", "secret",
                         "argocd-notifications-secret", "--ignore-not-found"])
    output = run_command(["kubectl", "-n", "argocd", "create", "secret", "generic",
                         "argocd-notifications-secret",
                         f"--from-literal=dynatrace-url={DT_TENANT_LIVE}",
                         f"--from-literal=dynatrace-token={DT_ALL_INGEST_TOKEN}"])
    output = run_command(["kubectl", "-n", "argocd", "scale",
                         "deploy/argocd-notifications-controller", "--replicas=0"])
    output = run_command(["kubectl", "-n", "argocd", "scale",
                         "deploy/argocd-notifications-controller", "--replicas=1"])

    # Restart ArgoCD server
    output = run_command(["kubectl", "-n", "argocd", "scale",
                         "deployment/argocd-server", "--replicas", "0"])
    output = run_command(["kubectl", "-n", "argocd", "scale",
                         "deployment/argocd-server", "--replicas", "1"])

    # Wait for server
    output = run_command(["kubectl", "-n", "argocd", "wait",
                         "--for=jsonpath={.status.readyReplicas}=1",
                         "deployment", "--selector=app.kubernetes.io/name=argocd-server",
                         "--timeout", "2m"])

    # Apply platform
    output = run_command(["kubectl", "apply", "-f", "gitops/platform.yml"])

    # Wait for argocd secret
    wait_for_artifact_to_exist(namespace="argocd", artifact_type="secret",
                              artifact_name="argocd-initial-admin-secret")

    # Configure ArgoCD CLI
    output = run_command(["kubectl", "config", "set-context", "--current", "--namespace=argocd"])
    output = run_command(["argocd", "login", "argo", "--core"])

    # Wait for alice account
    count = 1
    get_argo_accounts_output = ""
    while count < WAIT_FOR_ACCOUNTS_TIMEOUT and "alice" not in get_argo_accounts_output:
        print(f"Waiting for argo account alice to exist. Wait count: {count}")
        count += 1
        get_argo_accounts_output = run_command(["argocd", "account", "list"]).stdout
        time.sleep(1)

    if get_argo_accounts_output == "":
        exit("ArgoCD Account alice does not exist. Cannot proceed.")

    ARGOCD_TOKEN = run_command(["argocd", "account", "generate-token",
                               "--account", "alice"]).stdout

    if ARGOCD_TOKEN is None or ARGOCD_TOKEN == "":
        exit(f"ARGOCD_TOKEN is empty: {ARGOCD_TOKEN}. Cannot proceed!")

    output = run_command(["kubectl", "config", "set-context", "--current", "--namespace=default"])

    # Create remaining secrets
    output = run_command(["kubectl", "-n", "opentelemetry", "create", "secret", "generic",
                         "dt-details",
                         f"--from-literal=DT_URL={DT_TENANT_LIVE}",
                         f"--from-literal=DT_OTEL_ALL_INGEST_TOKEN={DT_ALL_INGEST_TOKEN}"])

    output = run_command(["kubectl", "-n", "backstage", "create", "secret", "generic",
                         "backstage-secrets",
                         f"--from-literal=BASE_DOMAIN={CODESPACE_NAME}",
                         f"--from-literal=BACKSTAGE_PORT_NUMBER={BACKSTAGE_PORT_NUMBER}",
                         f"--from-literal=ARGOCD_PORT_NUMBER={ARGOCD_PORT_NUMBER}",
                         f"--from-literal=ARGOCD_TOKEN={ARGOCD_TOKEN}",
                         f"--from-literal=GITHUB_TOKEN={GITHUB_TOKEN}",
                         f"--from-literal=GITHUB_ORG={github_org}",
                         f"--from-literal=GITHUB_REPO={GITHUB_REPO_NAME}",
                         f"--from-literal=GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN={GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}",
                         f"--from-literal=DT_TENANT_NAME={DT_ENV_NAME}",
                         f"--from-literal=DT_TENANT_LIVE={DT_TENANT_LIVE}",
                         f"--from-literal=DT_TENANT_APPS={DT_TENANT_APPS}",
                         f"--from-literal=DT_SSO_TOKEN_URL={DT_SSO_TOKEN_URL}",
                         f"--from-literal=DT_OAUTH_CLIENT_ID={DT_OAUTH_CLIENT_ID}",
                         f"--from-literal=DT_OAUTH_CLIENT_SECRET={DT_OAUTH_CLIENT_SECRET}",
                         f"--from-literal=DT_OAUTH_ACCOUNT_URN={DT_OAUTH_ACCOUNT_URN}",
                         f"--from-literal=DT_ALL_INGEST_TOKEN={DT_ALL_INGEST_TOKEN}"])

    output = run_command(["kubectl", "-n", "dynatrace", "create", "secret", "generic",
                         "platform-engineering-demo",
                         f"--from-literal=apiToken={DT_OP_TOKEN}",
                         f"--from-literal=dataIngestToken={DT_ALL_INGEST_TOKEN}"])

    output = run_command(["kubectl", "-n", "monaco", "create", "secret", "generic",
                         "monaco-secret", f"--from-literal=monacoToken={DT_MONACO_TOKEN}"])
    output = run_command(["kubectl", "-n", "dynatrace", "create", "secret", "generic",
                         "monaco-secret", f"--from-literal=monacoToken={DT_MONACO_TOKEN}"])

    # Wait for Backstage
    wait_for_artifact_to_exist(namespace="backstage", artifact_type="deployment",
                              artifact_name="backstage")

    # Restart Backstage
    output = run_command(["kubectl", "-n", "backstage", "rollout", "restart",
                         "deployment/backstage"])
    output = run_command(["kubectl", "-n", "backstage", "rollout", "status",
                         "deployment/backstage", f"--timeout={STANDARD_TIMEOUT}"])

    # Send startup ping
    send_startup_ping()

    print("=" * 60)
    print("Installation complete!")
    print(f"ArgoCD: https://{CODESPACE_NAME}-{ARGOCD_PORT_NUMBER}{GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}")
    print(f"Backstage: https://{CODESPACE_NAME}-{BACKSTAGE_PORT_NUMBER}{GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}")
    print("=" * 60)


def main():
    """Main entry point - auto-detects environment and runs appropriate installer."""

    # Check if we're in Codespaces
    if os.environ.get("CODESPACE_NAME"):
        logger.info("Detected GitHub Codespaces environment")
        run_legacy_codespaces_install()
    elif USE_ABSTRACTION:
        # Use new abstraction layer for minikube
        logger.info("Using environment abstraction layer")
        logger.info("For minikube, consider using: python3 minikube_installer.py")

        try:
            from environments import EnvironmentFactory
            env = EnvironmentFactory.detect()
            logger.info(f"Detected environment: {env.get_name()}")

            if env.get_name() == "minikube":
                # Redirect to minikube installer
                import subprocess
                result = subprocess.run([sys.executable, "minikube_installer.py"] + sys.argv[1:])
                sys.exit(result.returncode)
            else:
                run_legacy_codespaces_install()
        except Exception as e:
            logger.error(f"Environment detection failed: {e}")
            logger.info("Falling back to legacy Codespaces install")
            run_legacy_codespaces_install()
    else:
        # No abstraction available and not in Codespaces
        logger.error("Not in Codespaces and environment abstraction not available")
        logger.error("Please run in GitHub Codespaces or install the environments package")
        sys.exit(1)


if __name__ == "__main__":
    main()
