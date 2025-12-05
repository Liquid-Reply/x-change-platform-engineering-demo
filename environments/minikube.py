"""
Minikube environment implementation.
"""

import os
import subprocess
import shutil
import logging
from typing import Dict, List, Optional

from environments.base import EnvironmentBase


logger = logging.getLogger(__name__)


class MinikubeError(Exception):
    """Exception raised for minikube-related errors."""
    pass


class MinikubeEnvironment(EnvironmentBase):
    """
    Environment implementation for local minikube deployment.

    Provides minikube-specific cluster management, URL generation,
    and configuration for running the IDP platform locally.
    """

    def __init__(self, profile: Optional[dict] = None):
        """
        Initialize MinikubeEnvironment.

        Args:
            profile: Configuration profile dict

        Raises:
            MinikubeError: If minikube is not installed
        """
        super().__init__(profile)
        self._minikube_ip: Optional[str] = None
        self._validate_minikube_installed()

    def _validate_minikube_installed(self) -> None:
        """Verify minikube CLI is available."""
        if not shutil.which('minikube'):
            raise MinikubeError(
                "minikube is not installed. Please install minikube first:\n"
                "  macOS: brew install minikube\n"
                "  Linux: curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64\n"
                "  Windows: choco install minikube"
            )

    def get_name(self) -> str:
        """Return environment name."""
        return "minikube"

    def get_minikube_ip(self) -> str:
        """
        Get the minikube cluster IP address.

        Returns:
            IP address of the minikube cluster

        Raises:
            MinikubeError: If unable to get IP
        """
        if self._minikube_ip:
            return self._minikube_ip

        try:
            result = subprocess.run(
                ["minikube", "ip"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                self._minikube_ip = result.stdout.strip()
                return self._minikube_ip
            else:
                # Cluster might not be running, return localhost as fallback
                logger.warning("Could not get minikube IP, using localhost")
                return "127.0.0.1"
        except subprocess.TimeoutExpired:
            logger.warning("Timeout getting minikube IP, using localhost")
            return "127.0.0.1"
        except Exception as e:
            logger.warning(f"Error getting minikube IP: {e}, using localhost")
            return "127.0.0.1"

    def get_base_url(self) -> str:
        """
        Return base URL/domain for applications.

        Uses nip.io for automatic DNS resolution if configured,
        otherwise returns localhost.
        """
        use_nip_io = self.profile.get('urls', {}).get('use_nip_io', False)
        if use_nip_io:
            return f"{self.get_minikube_ip()}.nip.io"
        return "localhost"

    def get_service_url(self, service: str, port: int) -> str:
        """
        Return URL for a specific service.

        For minikube, services are accessed via localhost with NodePort.
        """
        base = self.get_base_url()
        if base == "localhost" or "127.0.0.1" in base:
            return f"http://localhost:{port}"
        else:
            # Using nip.io or similar
            return f"http://{base}:{port}"

    def create_cluster(self) -> bool:
        """
        Create a new minikube cluster.

        Returns:
            True if cluster creation succeeded

        Raises:
            MinikubeError: If cluster creation fails
        """
        config = self.get_cluster_config()

        logger.info("Creating minikube cluster...")
        logger.info(f"  Driver: {config.driver}")
        logger.info(f"  CPUs: {config.cpus}")
        logger.info(f"  Memory: {config.memory}MB")

        cmd = [
            "minikube", "start",
            f"--driver={config.driver}",
            f"--cpus={config.cpus}",
            f"--memory={config.memory}",
        ]

        # Add extra ports if configured
        extra_ports = self.profile.get('cluster', {}).get('extra_ports', [])
        if extra_ports:
            ports_str = ",".join(str(p) for p in extra_ports)
            cmd.append(f"--ports={ports_str}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout for cluster creation
            )

            if result.returncode != 0:
                logger.error(f"Cluster creation failed: {result.stderr}")
                raise MinikubeError(f"Failed to create minikube cluster: {result.stderr}")

            logger.info("Minikube cluster created successfully")

            # Enable addons
            self._enable_addons(config.addons)

            # Clear cached IP
            self._minikube_ip = None

            return True

        except subprocess.TimeoutExpired:
            raise MinikubeError("Cluster creation timed out after 10 minutes")

    def _enable_addons(self, addons: List[str]) -> None:
        """Enable minikube addons."""
        for addon in addons:
            logger.info(f"Enabling addon: {addon}")
            result = subprocess.run(
                ["minikube", "addons", "enable", addon],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                logger.warning(f"Failed to enable addon {addon}: {result.stderr}")

    def delete_cluster(self) -> bool:
        """
        Delete the minikube cluster.

        Returns:
            True if deletion succeeded
        """
        logger.info("Deleting minikube cluster...")

        result = subprocess.run(
            ["minikube", "delete"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.warning(f"Cluster deletion warning: {result.stderr}")

        # Clear cached IP
        self._minikube_ip = None

        return True

    def get_placeholder_values(self) -> Dict[str, str]:
        """
        Return environment-specific placeholder substitutions.

        Maps Codespaces-specific placeholders to minikube equivalents.
        """
        base_url = self.get_base_url()

        return {
            # Core identifiers
            "CODESPACE_NAME_PLACEHOLDER": "minikube",

            # Port forwarding domain (not applicable for minikube)
            "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN_PLACEHOLDER": "",

            # URLs - these stay as placeholders, actual URLs use localhost:port
            "ARGOCD_URL_PLACEHOLDER": self.get_argocd_url(),
            "BACKSTAGE_URL_PLACEHOLDER": self.get_backstage_url(),

            # Port numbers
            "ARGOCD_PORT_NUMBER_PLACEHOLDER": str(self.ports.argocd),
            "BACKSTAGE_PORT_NUMBER_PLACEHOLDER": str(self.ports.backstage),
            "DEMO_APP_PORT_NUMBER_PLACEHOLDER": str(self.ports.demo_app),
        }

    def get_enabled_components(self) -> List[str]:
        """
        Return list of enabled components.

        Reads from profile configuration, with sensible defaults
        for resource-constrained local environments.
        """
        components = self.profile.get('components', {})

        # Default components for minikube (minimal footprint)
        defaults = {
            'argocd': True,
            'backstage': True,
            'cert_manager': True,
            'ingress': True,
            'opentelemetry': True,
            'dynatrace': False,  # Optional
            'keptn': False,      # Disabled by default for resources
            'openfeature': False,
            'kubeaudit_cronjobs': False,
        }

        enabled = []
        for component, default_enabled in defaults.items():
            if components.get(component, default_enabled):
                enabled.append(component)

        return enabled

    def get_cluster_command(self) -> str:
        """Return the CLI command for cluster management."""
        return "minikube"

    def is_cluster_running(self) -> bool:
        """
        Check if minikube cluster is running.

        Returns:
            True if cluster is running
        """
        result = subprocess.run(
            ["minikube", "status"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and "Running" in result.stdout

    def get_kubectl_context(self) -> str:
        """Return the kubectl context name for this cluster."""
        return "minikube"

    def get_github_info(self) -> Dict[str, str]:
        """
        Get GitHub repository information.

        For minikube, tries multiple sources:
        1. Environment variables (GITHUB_REPOSITORY)
        2. Profile configuration
        3. Git remote origin URL (local repo detection)

        Returns:
            Dict with org, repo, full_path, and git_url keys.
        """
        # First try parent implementation (env vars and profile)
        info = super().get_github_info()

        # If we got valid info, return it
        if info.get('git_url'):
            return info

        # Fallback: read from git remote
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                return self._parse_git_remote(remote_url)
        except Exception as e:
            logger.warning(f"Could not get git remote: {e}")

        # Return empty info if all else fails
        logger.warning("Could not determine GitHub repository info")
        return {"org": "", "repo": "", "full_path": "", "git_url": ""}

    def _parse_git_remote(self, remote_url: str) -> Dict[str, str]:
        """
        Parse git remote URL to extract org/repo info.

        Handles both SSH and HTTPS formats:
        - git@github.com:org/repo.git
        - https://github.com/org/repo.git
        - git@custom.github.com:org/repo.git
        """
        import re

        # SSH format: git@host:org/repo.git
        ssh_match = re.match(r'git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$', remote_url)
        if ssh_match:
            org, repo = ssh_match.groups()
            # Convert SSH to HTTPS URL for ArgoCD
            https_url = f"https://github.com/{org}/{repo}.git"
            return {
                "org": org,
                "repo": repo,
                "full_path": f"{org}/{repo}",
                "git_url": https_url
            }

        # HTTPS format: https://github.com/org/repo.git
        https_match = re.match(r'https://[^/]+/([^/]+)/([^/]+?)(?:\.git)?$', remote_url)
        if https_match:
            org, repo = https_match.groups()
            git_url = remote_url if remote_url.endswith('.git') else f"{remote_url}.git"
            return {
                "org": org,
                "repo": repo,
                "full_path": f"{org}/{repo}",
                "git_url": git_url
            }

        logger.warning(f"Could not parse git remote URL: {remote_url}")
        return {"org": "", "repo": "", "full_path": "", "git_url": ""}

    def start_tunnel(self) -> subprocess.Popen:
        """
        Start minikube tunnel for LoadBalancer services.

        Returns:
            Popen object for the tunnel process

        Note:
            Tunnel requires sudo/admin privileges on most systems.
        """
        logger.info("Starting minikube tunnel (may require sudo)...")
        return subprocess.Popen(
            ["minikube", "tunnel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
