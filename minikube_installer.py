#!/usr/bin/env python3
"""
Minikube IDP Platform Installer

Sets up the Internal Development Platform on a local minikube cluster.
This is the main entry point for minikube-based deployments.

Usage:
    python3 minikube_installer.py [--skip-dynatrace] [--profile PATH]
"""

import argparse
import logging
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from environments import EnvironmentFactory, EnvironmentNotSupportedError
from config import ProfileLoader, ProfileNotFoundError
from secrets import SecretsManager
from secrets.manager import get_secrets_manager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ArgoCD version to install
ARGOCD_VERSION = "v2.12.2"

# Timeout for Kubernetes operations
STANDARD_TIMEOUT = "300s"


def run_command(args, ignore_errors=False, sensitive=False):
    """
    Run a shell command and return the result.

    Args:
        args: Command arguments as a list
        ignore_errors: Don't exit on non-zero return code
        sensitive: Don't print output (contains secrets)

    Returns:
        subprocess.CompletedProcess result
    """
    import subprocess

    result = subprocess.run(args, capture_output=True, text=True)

    if not sensitive:
        if result.stdout:
            print(result.stdout)

    if not ignore_errors and result.returncode > 0:
        logger.error(f"Command failed: {' '.join(args)}")
        logger.error(f"Error: {result.stderr}")
        sys.exit(1)

    return result


def wait_for_artifact(namespace, artifact_type, artifact_name, timeout=60):
    """Wait for a Kubernetes artifact to exist."""
    for i in range(timeout):
        result = run_command(
            ["kubectl", "-n", namespace, "get", f"{artifact_type}/{artifact_name}"],
            ignore_errors=True
        )
        if result.returncode == 0:
            logger.info(f"Found {artifact_type}/{artifact_name} in {namespace}")
            return True
        logger.info(f"Waiting for {artifact_type}/{artifact_name}... ({i+1}/{timeout})")
        time.sleep(1)

    logger.error(f"Timeout waiting for {artifact_type}/{artifact_name}")
    return False


def do_file_replace(pattern, find_string, replace_string, recursive=False):
    """Replace strings in files matching pattern."""
    import glob

    for filepath in glob.iglob(pattern, recursive=recursive):
        try:
            with open(filepath, "r") as f:
                content = f.read()

            if find_string in content:
                content = content.replace(find_string, replace_string)
                with open(filepath, "w") as f:
                    f.write(content)
                logger.debug(f"Replaced in: {filepath}")
        except Exception as e:
            logger.warning(f"Could not process {filepath}: {e}")


def git_commit(message, push=False):
    """Commit changes to git."""
    run_command(["git", "add", "-A"], ignore_errors=True)
    run_command(["git", "commit", "-m", message], ignore_errors=True)
    if push:
        run_command(["git", "push"], ignore_errors=True)


class PlatformInstaller:
    """
    Main installer class for the IDP platform.

    Handles cluster creation, component installation, and configuration
    for minikube-based deployments.
    """

    def __init__(self, environment, profile, secrets_manager, skip_dynatrace=False):
        """
        Initialize the installer.

        Args:
            environment: Environment instance (MinikubeEnvironment)
            profile: Configuration profile dict
            secrets_manager: SecretsManager instance
            skip_dynatrace: Skip Dynatrace integration
        """
        self.env = environment
        self.profile = profile
        self.secrets = secrets_manager
        self.skip_dynatrace = skip_dynatrace

        # Generated tokens (will be populated during install)
        self.dt_all_ingest_token = None
        self.dt_op_token = None
        self.dt_monaco_token = None
        self.argocd_token = None

    def run(self):
        """Run the full installation process."""
        logger.info(f"Starting IDP platform installation for: {self.env.get_name()}")
        logger.info(f"ArgoCD URL will be: {self.env.get_argocd_url()}")
        logger.info(f"Backstage URL will be: {self.env.get_backstage_url()}")

        # Step 1: Validate prerequisites
        self._validate_prerequisites()

        # Step 2: Configure Dynatrace (optional)
        if not self.skip_dynatrace:
            self._setup_dynatrace_tokens()

        # Step 3: Handle component toggles
        self._handle_component_toggles()

        # Step 4: Replace placeholders in files
        self._replace_placeholders()

        # Step 5: Upload Dynatrace assets (if enabled)
        if not self.skip_dynatrace and self.secrets.load().has_dynatrace():
            self._upload_dynatrace_assets()

        # Step 6: Create cluster
        self._create_cluster()

        # Step 7: Create namespaces
        self._create_namespaces()

        # Step 8: Create secrets
        self._create_kubernetes_secrets()

        # Step 9: Install ArgoCD
        self._install_argocd()

        # Step 10: Apply platform
        self._apply_platform()

        # Step 11: Wait for Backstage and restart
        self._finalize_backstage()

        # Step 12: Run validation
        validation_result = self._run_validation()

        logger.info("=" * 60)
        logger.info("Installation complete!")
        logger.info(f"ArgoCD: {self.env.get_argocd_url()}")
        logger.info(f"Backstage: {self.env.get_backstage_url()}")
        logger.info("")
        logger.info(validation_result.summary())
        logger.info("=" * 60)

        if not validation_result.passed:
            logger.warning("Some validation checks failed. Review details above.")

    def _run_validation(self):
        """Run post-installation validation."""
        from validation.runner import ValidationRunner

        logger.info("Running post-installation validation...")

        runner = ValidationRunner(environment=self.env.get_name())
        include_dt = not self.skip_dynatrace and self.secrets.load().has_dynatrace()
        result = runner.validate_phase("full", include_dynatrace=include_dt)

        logger.info(result.details())
        return result

    def _validate_prerequisites(self):
        """Validate all prerequisites are met."""
        logger.info("Validating prerequisites...")

        # Check cluster tool is available
        if not self.env.is_cluster_running():
            logger.info("No existing cluster found (this is fine)")

        # Check kubectl
        result = run_command(["kubectl", "version", "--client"], ignore_errors=True)
        if result.returncode != 0:
            logger.error("kubectl is not installed")
            sys.exit(1)

        logger.info("Prerequisites validated")

    def _setup_dynatrace_tokens(self):
        """Create Dynatrace API tokens if credentials are available."""
        from utils import create_dt_api_token, build_dt_urls

        platform_secrets = self.secrets.load()
        if not platform_secrets.has_dynatrace():
            logger.warning("Dynatrace secrets not available - skipping DT token creation")
            return

        dt = platform_secrets.dynatrace
        _, dt_tenant_live = build_dt_urls(dt_env_name=dt.env_name, dt_env=dt.env)

        logger.info("Creating Dynatrace API tokens...")

        self.dt_all_ingest_token = create_dt_api_token(
            token_name="[minikube] DT_ALL_INGEST_TOKEN",
            scopes=[
                "bizevents.ingest", "events.ingest", "logs.ingest",
                "metrics.ingest", "openTelemetryTrace.ingest",
                "DataExport", "entities.read", "settings.read",
                "settings.write", "activeGateTokenManagement.create"
            ],
            dt_rw_api_token=dt.rw_api_token,
            dt_tenant_live=dt_tenant_live
        )

        self.dt_op_token = create_dt_api_token(
            token_name="[minikube] DT_OP_TOKEN",
            scopes=[
                "InstallerDownload", "DataExport", "entities.read",
                "settings.read", "settings.write", "activeGateTokenManagement.create"
            ],
            dt_rw_api_token=dt.rw_api_token,
            dt_tenant_live=dt_tenant_live
        )

        self.dt_monaco_token = create_dt_api_token(
            token_name="[minikube] DT_MONACO_TOKEN",
            scopes=[
                "settings.read", "settings.write", "slo.read", "slo.write",
                "DataExport", "ExternalSyntheticIntegration", "ReadConfig", "WriteConfig"
            ],
            dt_rw_api_token=dt.rw_api_token,
            dt_tenant_live=dt_tenant_live
        )

        logger.info("Dynatrace tokens created successfully")

    def _handle_component_toggles(self):
        """Handle component enable/disable based on profile."""
        enabled = self.env.get_enabled_components()
        logger.info(f"Enabled components: {enabled}")

        # Disable Keptn if not in enabled list
        if 'keptn' not in enabled:
            logger.info("Disabling Keptn (not in enabled components)")
            self._disable_component_files([
                "gitops/applications/platform/keptn.yml",
                "gitops/manifests/platform/keptn/keptn-metrics.yml",
                "gitops/manifests/platform/keptn/otelcol-keptnconfig.yml",
            ])

        # Disable kubeaudit cronjobs if not enabled
        if 'kubeaudit_cronjobs' not in enabled:
            logger.info("Disabling kubeaudit cronjobs")
            # These would be handled by ArgoCD ApplicationSet, so no file rename needed

    def _disable_component_files(self, files):
        """Rename files to disable ArgoCD from picking them up."""
        for filepath in files:
            if os.path.exists(filepath):
                try:
                    os.rename(filepath, f"{filepath}.disabled")
                    logger.debug(f"Disabled: {filepath}")
                except Exception as e:
                    logger.warning(f"Could not disable {filepath}: {e}")

    def _replace_placeholders(self):
        """Replace all placeholders in manifest files."""
        logger.info("Replacing placeholders in manifests...")

        # Get placeholder values from environment
        placeholders = self.env.get_placeholder_values()

        # Add Dynatrace placeholders if available
        platform_secrets = self.secrets.load()
        if platform_secrets.has_dynatrace():
            from utils import build_dt_urls, get_geolocation
            dt = platform_secrets.dynatrace
            dt_tenant_apps, dt_tenant_live = build_dt_urls(dt.env_name, dt.env)
            dt_geolocation = get_geolocation(dt.env)

            placeholders.update({
                "DT_TENANT_LIVE_PLACEHOLDER": dt_tenant_live,
                "DT_TENANT_APPS_PLACEHOLDER": dt_tenant_apps,
                "GEOLOCATION_PLACEHOLDER": dt_geolocation or "",
            })

        # Add GitHub placeholders
        github_info = self.env.get_github_info()
        repo_url = github_info.get('git_url', '')
        # Get current git branch for targetRevision
        branch_result = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], ignore_errors=True)
        target_revision = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"

        placeholders.update({
            "GITHUB_DOT_COM_REPO_PLACEHOLDER": repo_url,
            "GITHUB_REPOSITORY_PLACEHOLDER": github_info.get('full_path', ''),
            "GITHUB_ORG_NAME_PLACEHOLDER": github_info.get('org', ''),
            "GITHUB_REPO_NAME_PLACEHOLDER": github_info.get('repo', ''),
            # Kustomize overlay placeholders for ArgoCD applications
            "REPO_URL_PLACEHOLDER": repo_url,
            "TARGET_REVISION_PLACEHOLDER": target_revision,
        })

        # Do the replacements
        for placeholder, value in placeholders.items():
            if value:  # Only replace if we have a value
                do_file_replace("./**/*.y*ml", placeholder, value, recursive=True)
                do_file_replace("./**/*.json", placeholder, value, recursive=True)
                do_file_replace("./apptemplates/docs/*.md", placeholder, value, recursive=False)

        # Commit changes
        git_commit("Update placeholders for minikube environment", push=True)
        logger.info("Placeholders replaced and committed")

    def _upload_dynatrace_assets(self):
        """Upload dashboards, notebooks, and workflows to Dynatrace."""
        from utils import (
            upload_dt_document_asset, upload_dt_workflow_asset,
            get_sso_token_url, build_dt_urls
        )

        platform_secrets = self.secrets.load()
        dt = platform_secrets.dynatrace
        dt_tenant_apps, _ = build_dt_urls(dt.env_name, dt.env)
        sso_token_url = get_sso_token_url(dt.env)

        logger.info("Uploading Dynatrace assets...")

        # Notebooks
        notebooks = [
            ("dynatraceassets/notebooks/analyze-argocd-notification-events.json",
             "[minikube] ArgoCD: Analyze Notification Events"),
            ("dynatraceassets/notebooks/argocd-log-analytics.json",
             "[minikube] ArgoCD: Log Analytics"),
            ("dynatraceassets/notebooks/platform-engineering-walkthrough.json",
             "[minikube] Platform Engineering Demo Walkthrough"),
        ]
        for path, name in notebooks:
            if os.path.exists(path):
                upload_dt_document_asset(sso_token_url, path, name, "notebook", dt_tenant_apps)

        # Dashboards
        dashboards = [
            ("dynatraceassets/dashboards/argocd-lifecycle-dashboard.json",
             "[minikube] ArgoCD: Lifecycle Dashboard"),
            ("dynatraceassets/dashboards/argocd-platform-observability.json",
             "[minikube] ArgoCD: Platform Observability"),
            ("dynatraceassets/dashboards/backstage-error-analysis.json",
             "[minikube] Backstage: Error Analysis"),
            ("dynatraceassets/dashboards/platform-observability-cockpit.json",
             "[minikube] Platform Observability Cockpit"),
            ("dynatraceassets/dashboards/team-ownership-dashboard.json",
             "[minikube] Team Ownership Dashboard"),
        ]
        for path, name in dashboards:
            if os.path.exists(path):
                upload_dt_document_asset(sso_token_url, path, name, "dashboard", dt_tenant_apps)

        # Workflows
        workflows = [
            ("dynatraceassets/workflows/lifecycle-events-workflow.json",
             "[minikube] Lifecycle Events Workflow"),
        ]
        for path, name in workflows:
            if os.path.exists(path):
                upload_dt_workflow_asset(sso_token_url, path, name, dt_tenant_apps)

        logger.info("Dynatrace assets uploaded")

    def _create_cluster(self):
        """Create the minikube cluster."""
        logger.info("Creating minikube cluster...")

        # Delete existing cluster first
        self.env.delete_cluster()

        # Create new cluster
        self.env.create_cluster()

        logger.info("Cluster created successfully")

    def _create_namespaces(self):
        """Create required Kubernetes namespaces."""
        namespaces = ["argocd", "opentelemetry", "backstage", "monaco", "dynatrace"]

        logger.info(f"Creating namespaces: {namespaces}")
        for ns in namespaces:
            run_command(["kubectl", "create", "namespace", ns], ignore_errors=True)

    def _create_kubernetes_secrets(self):
        """Create all required Kubernetes secrets."""
        logger.info("Creating Kubernetes secrets...")

        platform_secrets = self.secrets.load()

        # GitHub token secret for ArgoCD
        if platform_secrets.has_github():
            self.secrets.create_k8s_secret(
                "github-token", "argocd",
                {"token": platform_secrets.github.token}
            )

        # Dynatrace secrets (if available)
        if platform_secrets.has_dynatrace() and not self.skip_dynatrace:
            from utils import build_dt_urls
            dt = platform_secrets.dynatrace
            _, dt_tenant_live = build_dt_urls(dt.env_name, dt.env)

            # Bizevent OAuth secrets
            oauth_data = {
                "dtTenant": dt_tenant_live,
                "oAuthClientID": dt.oauth_client_id,
                "oAuthClientSecret": dt.oauth_client_secret,
                "accountURN": dt.oauth_account_urn,
            }
            self.secrets.create_k8s_secret("dt-bizevent-oauth-details", "dynatrace", oauth_data)
            self.secrets.create_k8s_secret("dt-bizevent-oauth-details", "opentelemetry", oauth_data)

        logger.info("Base secrets created")

    def _install_argocd(self):
        """Install and configure ArgoCD."""
        logger.info(f"Installing ArgoCD {ARGOCD_VERSION}...")

        # Install ArgoCD
        run_command([
            "kubectl", "apply", "-n", "argocd", "-f",
            f"https://raw.githubusercontent.com/argoproj/argo-cd/{ARGOCD_VERSION}/manifests/install.yaml"
        ])

        # Wait for deployments
        run_command([
            "kubectl", "wait", "--for=condition=Available=True",
            "deployments", "-n", "argocd", "--all", f"--timeout={STANDARD_TIMEOUT}"
        ])

        # Apply ArgoCD configuration
        run_command(["kubectl", "apply", "-n", "argocd", "-f",
                    "gitops/manifests/platform/argoconfig/argocd-cm.yml"])
        run_command(["kubectl", "apply", "-n", "argocd", "-f",
                    "gitops/manifests/platform/argoconfig/argocd-no-tls.yml"])
        run_command(["kubectl", "apply", "-n", "argocd", "-f",
                    "gitops/manifests/platform/argoconfig/argocd-nodeport.yml"])

        # Create notifications secret
        platform_secrets = self.secrets.load()
        if platform_secrets.has_dynatrace() and self.dt_all_ingest_token:
            from utils import build_dt_urls
            dt = platform_secrets.dynatrace
            _, dt_tenant_live = build_dt_urls(dt.env_name, dt.env)

            self.secrets.create_k8s_secret(
                "argocd-notifications-secret", "argocd",
                {
                    "dynatrace-url": dt_tenant_live,
                    "dynatrace-token": self.dt_all_ingest_token
                }
            )

        # Restart notifications controller
        run_command(["kubectl", "-n", "argocd", "scale",
                    "deploy/argocd-notifications-controller", "--replicas=0"])
        run_command(["kubectl", "-n", "argocd", "scale",
                    "deploy/argocd-notifications-controller", "--replicas=1"])

        # Restart ArgoCD server
        run_command(["kubectl", "-n", "argocd", "scale",
                    "deployment/argocd-server", "--replicas", "0"])
        run_command(["kubectl", "-n", "argocd", "scale",
                    "deployment/argocd-server", "--replicas", "1"])

        # Wait for server
        run_command([
            "kubectl", "-n", "argocd", "wait",
            "--for=jsonpath={.status.readyReplicas}=1",
            "deployment", "--selector=app.kubernetes.io/name=argocd-server",
            "--timeout", "2m"
        ])

        logger.info("ArgoCD installed and configured")

    def _apply_platform(self):
        """Apply the platform GitOps configuration."""
        logger.info("Applying platform configuration...")

        # Use minikube-specific platform file with Kustomize overlay
        run_command(["kubectl", "apply", "-f", "gitops/platform-minikube.yml"])

        # Wait for ArgoCD secret
        wait_for_artifact("argocd", "secret", "argocd-initial-admin-secret")

        # Generate ArgoCD token for Backstage
        run_command(["kubectl", "config", "set-context", "--current", "--namespace=argocd"])
        run_command(["argocd", "login", "argo", "--core"], ignore_errors=True)

        # Wait for alice account
        for i in range(60):
            result = run_command(["argocd", "account", "list"], ignore_errors=True)
            if "alice" in result.stdout:
                break
            logger.info(f"Waiting for alice account... ({i+1}/60)")
            time.sleep(1)

        # Generate token
        result = run_command(["argocd", "account", "generate-token", "--account", "alice"],
                           sensitive=True)
        self.argocd_token = result.stdout.strip()

        run_command(["kubectl", "config", "set-context", "--current", "--namespace=default"])

        logger.info("Platform configuration applied")

    def _finalize_backstage(self):
        """Create Backstage secrets and restart it."""
        logger.info("Finalizing Backstage setup...")

        platform_secrets = self.secrets.load()
        github_info = self.env.get_github_info()

        # Build Backstage secrets
        backstage_data = {
            "BASE_DOMAIN": "minikube",
            "BACKSTAGE_PORT_NUMBER": str(self.env.ports.backstage),
            "ARGOCD_PORT_NUMBER": str(self.env.ports.argocd),
            "ARGOCD_TOKEN": self.argocd_token or "",
            "GITHUB_TOKEN": platform_secrets.github.token if platform_secrets.has_github() else "",
            "GITHUB_ORG": github_info.get('org', ''),
            "GITHUB_REPO": github_info.get('repo', ''),
            "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "",  # Not used in minikube
        }

        # Add Dynatrace details if available
        if platform_secrets.has_dynatrace():
            from utils import build_dt_urls, get_sso_token_url
            dt = platform_secrets.dynatrace
            dt_tenant_apps, dt_tenant_live = build_dt_urls(dt.env_name, dt.env)

            backstage_data.update({
                "DT_TENANT_NAME": dt.env_name,
                "DT_TENANT_LIVE": dt_tenant_live,
                "DT_TENANT_APPS": dt_tenant_apps,
                "DT_SSO_TOKEN_URL": get_sso_token_url(dt.env),
                "DT_OAUTH_CLIENT_ID": dt.oauth_client_id,
                "DT_OAUTH_CLIENT_SECRET": dt.oauth_client_secret,
                "DT_OAUTH_ACCOUNT_URN": dt.oauth_account_urn,
                "DT_ALL_INGEST_TOKEN": self.dt_all_ingest_token or "",
            })

        self.secrets.create_k8s_secret("backstage-secrets", "backstage", backstage_data)

        # Create OpenTelemetry secret
        if platform_secrets.has_dynatrace() and self.dt_all_ingest_token:
            from utils import build_dt_urls
            dt = platform_secrets.dynatrace
            _, dt_tenant_live = build_dt_urls(dt.env_name, dt.env)

            self.secrets.create_k8s_secret(
                "dt-details", "opentelemetry",
                {
                    "DT_URL": dt_tenant_live,
                    "DT_OTEL_ALL_INGEST_TOKEN": self.dt_all_ingest_token
                }
            )

        # Create OneAgent and Monaco secrets
        if platform_secrets.has_dynatrace() and self.dt_op_token and self.dt_monaco_token:
            self.secrets.create_k8s_secret(
                "platform-engineering-demo", "dynatrace",
                {
                    "apiToken": self.dt_op_token,
                    "dataIngestToken": self.dt_all_ingest_token
                }
            )
            self.secrets.create_k8s_secret("monaco-secret", "monaco",
                                          {"monacoToken": self.dt_monaco_token})
            self.secrets.create_k8s_secret("monaco-secret", "dynatrace",
                                          {"monacoToken": self.dt_monaco_token})

        # Wait for Backstage deployment
        wait_for_artifact("backstage", "deployment", "backstage")

        # Restart Backstage
        run_command(["kubectl", "-n", "backstage", "rollout", "restart", "deployment/backstage"])
        run_command(["kubectl", "-n", "backstage", "rollout", "status",
                    "deployment/backstage", f"--timeout={STANDARD_TIMEOUT}"])

        logger.info("Backstage configured and restarted")


def main():
    parser = argparse.ArgumentParser(
        description="Install IDP platform on minikube"
    )
    parser.add_argument(
        "--skip-dynatrace",
        action="store_true",
        help="Skip Dynatrace integration (run without observability)"
    )
    parser.add_argument(
        "--profile",
        default="minikube",
        help="Profile name or path to profile file"
    )

    args = parser.parse_args()

    try:
        # Load profile
        logger.info(f"Loading profile: {args.profile}")
        loader = ProfileLoader()
        profile = loader.load_or_default(args.profile)

        # Detect/create environment
        logger.info("Detecting environment...")
        env = EnvironmentFactory.create("minikube", profile)

        # Setup secrets manager
        secrets_manager = get_secrets_manager(
            profile=profile,
            require_dynatrace=not args.skip_dynatrace
        )

        # Run installer
        installer = PlatformInstaller(
            environment=env,
            profile=profile,
            secrets_manager=secrets_manager,
            skip_dynatrace=args.skip_dynatrace
        )
        installer.run()

    except (EnvironmentNotSupportedError, ProfileNotFoundError) as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Installation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
