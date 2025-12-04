"""
Abstract base class for environment-specific configuration.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ClusterConfig:
    """Configuration for cluster creation."""
    driver: str = "docker"
    cpus: int = 2
    memory: int = 4096
    addons: List[str] = None

    def __post_init__(self):
        if self.addons is None:
            self.addons = []


@dataclass
class PortConfig:
    """Port configuration for services."""
    argocd: int = 30100
    backstage: int = 30105
    demo_app: int = 80


class EnvironmentBase(ABC):
    """
    Abstract base class for environment-specific configuration.

    Each environment (Codespaces, Minikube, etc.) implements this interface
    to provide environment-specific behavior while maintaining a common API.
    """

    def __init__(self, profile: Optional[dict] = None):
        """
        Initialize the environment.

        Args:
            profile: Optional configuration profile dict loaded from YAML
        """
        self.profile = profile or {}
        self.ports = PortConfig(
            argocd=self.profile.get('ports', {}).get('argocd', 30100),
            backstage=self.profile.get('ports', {}).get('backstage', 30105),
            demo_app=self.profile.get('ports', {}).get('demo_app', 80)
        )

    @abstractmethod
    def get_name(self) -> str:
        """
        Return environment name.

        Returns:
            Environment identifier (e.g., 'minikube', 'codespaces')
        """
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        """
        Return base URL/domain for applications.

        Returns:
            Base domain for service URLs
        """
        pass

    @abstractmethod
    def get_service_url(self, service: str, port: int) -> str:
        """
        Return URL for a specific service.

        Args:
            service: Service name (e.g., 'argocd', 'backstage')
            port: Service port number

        Returns:
            Full URL to access the service
        """
        pass

    @abstractmethod
    def create_cluster(self) -> bool:
        """
        Create or configure the Kubernetes cluster.

        Returns:
            True if cluster creation succeeded

        Raises:
            ClusterError: If cluster creation fails
        """
        pass

    @abstractmethod
    def delete_cluster(self) -> bool:
        """
        Delete the existing cluster.

        Returns:
            True if cluster deletion succeeded
        """
        pass

    @abstractmethod
    def get_placeholder_values(self) -> Dict[str, str]:
        """
        Return environment-specific placeholder substitutions.

        Returns:
            Dict mapping placeholder names to their values
        """
        pass

    @abstractmethod
    def get_enabled_components(self) -> List[str]:
        """
        Return list of enabled components for this environment.

        Returns:
            List of component names that should be deployed
        """
        pass

    @abstractmethod
    def get_cluster_command(self) -> str:
        """
        Return the CLI command used for cluster management.

        Returns:
            Command name (e.g., 'kind', 'minikube')
        """
        pass

    def get_argocd_url(self) -> str:
        """Return ArgoCD service URL."""
        return self.get_service_url('argocd', self.ports.argocd)

    def get_backstage_url(self) -> str:
        """Return Backstage service URL."""
        return self.get_service_url('backstage', self.ports.backstage)

    def get_demo_app_base_url(self) -> str:
        """Return base URL for demo applications."""
        return self.get_service_url('demo', self.ports.demo_app)

    def is_component_enabled(self, component: str) -> bool:
        """
        Check if a specific component is enabled.

        Args:
            component: Component name to check

        Returns:
            True if component should be deployed
        """
        return component in self.get_enabled_components()

    def get_cluster_config(self) -> ClusterConfig:
        """
        Get cluster configuration from profile.

        Returns:
            ClusterConfig with cluster settings
        """
        cluster = self.profile.get('cluster', {})
        return ClusterConfig(
            driver=cluster.get('driver', 'docker'),
            cpus=cluster.get('cpus', 2),
            memory=cluster.get('memory', 4096),
            addons=cluster.get('addons', [])
        )
