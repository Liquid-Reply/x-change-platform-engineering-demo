"""
GitHub Codespaces environment implementation.
"""

import os
import subprocess
import logging
from typing import Dict, List, Optional

from environments.base import EnvironmentBase


logger = logging.getLogger(__name__)


class CodespacesError(Exception):
    """Exception raised for Codespaces-related errors."""
    pass


class CodespacesEnvironment(EnvironmentBase):
    """
    Environment implementation for GitHub Codespaces with Kind cluster.

    Provides Codespaces-specific configuration including:
    - Port forwarding domain handling
    - Kind cluster management
    - Codespace-aware URL generation
    """

    def __init__(self, profile: Optional[dict] = None):
        """
        Initialize CodespacesEnvironment.

        Args:
            profile: Configuration profile dict

        Raises:
            CodespacesError: If not running in Codespaces
        """
        super().__init__(profile)
        self._validate_codespaces_environment()
        self._codespace_name = os.environ.get("CODESPACE_NAME")
        self._port_forwarding_domain = os.environ.get(
            "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN",
            ".app.github.dev"
        )

    def _validate_codespaces_environment(self) -> None:
        """Verify we're running in GitHub Codespaces."""
        if not os.environ.get("CODESPACE_NAME"):
            raise CodespacesError(
                "Not running in GitHub Codespaces. "
                "CODESPACE_NAME environment variable is not set."
            )

    def get_name(self) -> str:
        """Return environment name."""
        return "codespaces"

    def get_codespace_name(self) -> str:
        """Return the Codespace name."""
        return self._codespace_name

    def get_port_forwarding_domain(self) -> str:
        """Return the Codespaces port forwarding domain."""
        return self._port_forwarding_domain

    def get_base_url(self) -> str:
        """
        Return base URL/domain for applications.

        Uses Codespaces port forwarding format.
        """
        return f"{self._codespace_name}-{self.ports.demo_app}{self._port_forwarding_domain}"

    def get_service_url(self, service: str, port: int) -> str:
        """
        Return URL for a specific service.

        Uses Codespaces port forwarding URL format:
        https://{codespace_name}-{port}.app.github.dev
        """
        return f"https://{self._codespace_name}-{port}{self._port_forwarding_domain}"

    def create_cluster(self) -> bool:
        """
        Create a Kind cluster for Codespaces.

        Returns:
            True if cluster creation succeeded

        Raises:
            CodespacesError: If cluster creation fails
        """
        config_file = self.profile.get('cluster', {}).get(
            'config_file',
            '.devcontainer/kind-cluster.yml'
        )
        timeout = self.profile.get('cluster', {}).get('timeout', '300s')

        logger.info("Creating Kind cluster...")

        cmd = [
            "kind", "create", "cluster",
            "--config", config_file,
            "--wait", timeout
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                logger.error(f"Cluster creation failed: {result.stderr}")
                raise CodespacesError(f"Failed to create Kind cluster: {result.stderr}")

            logger.info("Kind cluster created successfully")
            return True

        except subprocess.TimeoutExpired:
            raise CodespacesError("Cluster creation timed out after 10 minutes")

    def delete_cluster(self) -> bool:
        """
        Delete the Kind cluster.

        Returns:
            True if deletion succeeded
        """
        logger.info("Deleting Kind cluster...")

        result = subprocess.run(
            ["kind", "delete", "cluster"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.warning(f"Cluster deletion warning: {result.stderr}")

        return True

    def get_placeholder_values(self) -> Dict[str, str]:
        """
        Return environment-specific placeholder substitutions.

        Provides all Codespaces-specific values for template substitution.
        """
        return {
            # Core identifiers
            "CODESPACE_NAME_PLACEHOLDER": self._codespace_name,

            # Port forwarding domain
            "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN_PLACEHOLDER": self._port_forwarding_domain,

            # Port numbers
            "ARGOCD_PORT_NUMBER_PLACEHOLDER": str(self.ports.argocd),
            "BACKSTAGE_PORT_NUMBER_PLACEHOLDER": str(self.ports.backstage),
            "DEMO_APP_PORT_NUMBER_PLACEHOLDER": str(self.ports.demo_app),
        }

    def get_enabled_components(self) -> List[str]:
        """
        Return list of enabled components.

        Codespaces enables most components by default since
        it has more resources than a typical local machine.
        """
        components = self.profile.get('components', {})

        # Default components for Codespaces (full feature set)
        defaults = {
            'argocd': True,
            'backstage': True,
            'cert_manager': True,
            'ingress': True,
            'opentelemetry': True,
            'dynatrace': True,
            'keptn': True,
            'openfeature': True,
            'kubeaudit_cronjobs': True,
        }

        # Check for INSTALL_KEPTN environment variable override
        install_keptn = os.environ.get("INSTALL_KEPTN", "true").lower()
        if install_keptn in ("false", "no", "0"):
            defaults['keptn'] = False

        enabled = []
        for component, default_enabled in defaults.items():
            if components.get(component, default_enabled):
                enabled.append(component)

        return enabled

    def get_cluster_command(self) -> str:
        """Return the CLI command for cluster management."""
        return "kind"

    def is_cluster_running(self) -> bool:
        """
        Check if Kind cluster is running.

        Returns:
            True if cluster is running
        """
        result = subprocess.run(
            ["kind", "get", "clusters"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and "kind" in result.stdout

    def get_kubectl_context(self) -> str:
        """Return the kubectl context name for this cluster."""
        return "kind-kind"

    def get_github_info(self) -> Dict[str, str]:
        """
        Get GitHub repository information from environment.

        Returns:
            Dict with org, repo, and full repository path
        """
        github_repo = os.environ.get("GITHUB_REPOSITORY", "")
        repo_name = os.environ.get("RepositoryName", "")

        org = ""
        if "/" in github_repo:
            org = github_repo.split("/")[0]

        return {
            "org": org,
            "repo": repo_name,
            "full_path": github_repo,
            "git_url": f"https://github.com/{github_repo}.git" if github_repo else ""
        }
