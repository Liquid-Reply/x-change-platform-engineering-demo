"""
Factory for creating environment instances.
"""

import os
import shutil
import logging
from typing import Optional, Type

from environments.base import EnvironmentBase


logger = logging.getLogger(__name__)


class EnvironmentNotSupportedError(Exception):
    """Raised when no supported environment is detected."""
    pass


class EnvironmentFactory:
    """
    Factory for detecting and creating environment instances.

    Automatically detects the current environment and creates
    the appropriate environment implementation.
    """

    # Registry of environment classes
    _environments: dict = {}

    @classmethod
    def register(cls, name: str, env_class: Type[EnvironmentBase]) -> None:
        """
        Register an environment class.

        Args:
            name: Environment identifier
            env_class: Environment implementation class
        """
        cls._environments[name] = env_class

    @classmethod
    def detect(cls, profile: Optional[dict] = None) -> EnvironmentBase:
        """
        Detect the current environment and create appropriate instance.

        Detection order:
        1. CODESPACE_NAME env var -> Codespaces
        2. minikube CLI available -> Minikube
        3. kind CLI available -> Generic Kind (falls back to Codespaces)

        Args:
            profile: Optional configuration profile

        Returns:
            Appropriate EnvironmentBase implementation

        Raises:
            EnvironmentNotSupportedError: If no supported environment detected
        """
        # Import here to avoid circular imports
        from environments.codespaces import CodespacesEnvironment
        from environments.minikube import MinikubeEnvironment

        # Check for explicit environment override
        env_override = os.environ.get("IDP_ENVIRONMENT")
        if env_override:
            logger.info(f"Environment override: {env_override}")
            if env_override.lower() == "minikube":
                return MinikubeEnvironment(profile)
            elif env_override.lower() == "codespaces":
                return CodespacesEnvironment(profile)

        # Auto-detect environment
        logger.info("Auto-detecting environment...")

        # Check for Codespaces first (most specific)
        if os.environ.get("CODESPACE_NAME"):
            logger.info("Detected: GitHub Codespaces")
            return CodespacesEnvironment(profile)

        # Check for minikube
        if shutil.which("minikube"):
            logger.info("Detected: minikube")
            return MinikubeEnvironment(profile)

        # Check for kind as fallback
        if shutil.which("kind"):
            logger.info("Detected: kind (using Codespaces environment without Codespaces features)")
            # For local kind usage, we'd need a generic Kind environment
            # For now, raise an error suggesting minikube
            raise EnvironmentNotSupportedError(
                "Kind detected but not running in Codespaces. "
                "Please use minikube for local development:\n"
                "  brew install minikube  # macOS\n"
                "  Or set IDP_ENVIRONMENT=minikube to force minikube mode"
            )

        raise EnvironmentNotSupportedError(
            "No supported environment detected.\n"
            "Please install one of:\n"
            "  - minikube: For local Kubernetes development\n"
            "  - Use GitHub Codespaces for cloud-based development"
        )

    @classmethod
    def create(cls, environment: str, profile: Optional[dict] = None) -> EnvironmentBase:
        """
        Create a specific environment instance by name.

        Args:
            environment: Environment name ('minikube', 'codespaces')
            profile: Optional configuration profile

        Returns:
            Environment instance

        Raises:
            EnvironmentNotSupportedError: If environment not supported
        """
        from environments.codespaces import CodespacesEnvironment
        from environments.minikube import MinikubeEnvironment

        environments = {
            'minikube': MinikubeEnvironment,
            'codespaces': CodespacesEnvironment,
        }

        env_class = environments.get(environment.lower())
        if not env_class:
            raise EnvironmentNotSupportedError(
                f"Unknown environment: {environment}. "
                f"Supported: {list(environments.keys())}"
            )

        return env_class(profile)

    @classmethod
    def list_available(cls) -> list:
        """
        List available environment types.

        Returns:
            List of environment names that can be used
        """
        available = []

        # Check Codespaces
        if os.environ.get("CODESPACE_NAME"):
            available.append("codespaces (current)")
        else:
            available.append("codespaces (requires GitHub Codespaces)")

        # Check minikube
        if shutil.which("minikube"):
            available.append("minikube (installed)")
        else:
            available.append("minikube (not installed)")

        return available
