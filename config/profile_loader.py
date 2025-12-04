"""
Profile loader for environment-specific configurations.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional, Any

import yaml


logger = logging.getLogger(__name__)


class ProfileNotFoundError(Exception):
    """Raised when a profile file cannot be found."""
    pass


class ProfileValidationError(Exception):
    """Raised when profile validation fails."""
    pass


class ProfileLoader:
    """
    Loads and validates environment configuration profiles.

    Profiles are YAML files that define environment-specific settings
    for cluster configuration, ports, components, and secrets.
    """

    # Default profiles directory relative to project root
    DEFAULT_PROFILES_DIR = "config/profiles"

    # Required profile fields
    REQUIRED_FIELDS = ['environment']

    # Known environments
    KNOWN_ENVIRONMENTS = ['minikube', 'codespaces']

    def __init__(self, profiles_dir: Optional[str] = None):
        """
        Initialize ProfileLoader.

        Args:
            profiles_dir: Path to profiles directory. If None, uses default.
        """
        if profiles_dir:
            self.profiles_dir = Path(profiles_dir)
        else:
            # Find project root (where config/ directory is)
            self.profiles_dir = self._find_profiles_dir()

    def _find_profiles_dir(self) -> Path:
        """
        Find the profiles directory.

        Looks for config/profiles relative to:
        1. Current working directory
        2. Script location

        Returns:
            Path to profiles directory

        Raises:
            ProfileNotFoundError: If profiles directory not found
        """
        # Try current working directory
        cwd_path = Path.cwd() / self.DEFAULT_PROFILES_DIR
        if cwd_path.exists():
            return cwd_path

        # Try relative to this file
        file_path = Path(__file__).parent / "profiles"
        if file_path.exists():
            return file_path

        # Try one level up from this file
        parent_path = Path(__file__).parent.parent / self.DEFAULT_PROFILES_DIR
        if parent_path.exists():
            return parent_path

        raise ProfileNotFoundError(
            f"Could not find profiles directory. Tried:\n"
            f"  - {cwd_path}\n"
            f"  - {file_path}\n"
            f"  - {parent_path}"
        )

    def load(self, environment: str) -> Dict[str, Any]:
        """
        Load a profile by environment name.

        Args:
            environment: Environment name (e.g., 'minikube', 'codespaces')

        Returns:
            Profile configuration dictionary

        Raises:
            ProfileNotFoundError: If profile file not found
            ProfileValidationError: If profile is invalid
        """
        profile_path = self.profiles_dir / f"{environment}.yaml"

        if not profile_path.exists():
            # Also try .yml extension
            profile_path = self.profiles_dir / f"{environment}.yml"

        if not profile_path.exists():
            available = self.list_available()
            raise ProfileNotFoundError(
                f"Profile '{environment}' not found at {self.profiles_dir}.\n"
                f"Available profiles: {available}"
            )

        logger.info(f"Loading profile from: {profile_path}")

        try:
            with open(profile_path, 'r') as f:
                profile = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ProfileValidationError(f"Invalid YAML in profile: {e}")

        self._validate(profile, environment)

        return profile

    def _validate(self, profile: Dict[str, Any], expected_env: str) -> None:
        """
        Validate a profile configuration.

        Args:
            profile: Profile dictionary to validate
            expected_env: Expected environment name

        Raises:
            ProfileValidationError: If validation fails
        """
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in profile:
                raise ProfileValidationError(
                    f"Profile missing required field: {field}"
                )

        # Verify environment matches
        if profile.get('environment') != expected_env:
            raise ProfileValidationError(
                f"Profile environment mismatch: "
                f"expected '{expected_env}', got '{profile.get('environment')}'"
            )

        # Validate ports if present
        ports = profile.get('ports', {})
        for name, port in ports.items():
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ProfileValidationError(
                    f"Invalid port '{name}': {port}"
                )

        # Validate components are boolean if present
        components = profile.get('components', {})
        for name, enabled in components.items():
            if not isinstance(enabled, bool):
                raise ProfileValidationError(
                    f"Component '{name}' must be boolean, got: {type(enabled).__name__}"
                )

    def list_available(self) -> list:
        """
        List available profile names.

        Returns:
            List of profile names (without extension)
        """
        if not self.profiles_dir.exists():
            return []

        profiles = []
        for path in self.profiles_dir.glob("*.yaml"):
            profiles.append(path.stem)
        for path in self.profiles_dir.glob("*.yml"):
            if path.stem not in profiles:
                profiles.append(path.stem)

        return sorted(profiles)

    def load_or_default(self, environment: str) -> Dict[str, Any]:
        """
        Load a profile, returning defaults if not found.

        Args:
            environment: Environment name

        Returns:
            Profile dictionary (may be default values)
        """
        try:
            return self.load(environment)
        except ProfileNotFoundError:
            logger.warning(f"Profile '{environment}' not found, using defaults")
            return self._get_defaults(environment)

    def _get_defaults(self, environment: str) -> Dict[str, Any]:
        """
        Return default configuration for an environment.

        Args:
            environment: Environment name

        Returns:
            Default profile dictionary
        """
        defaults = {
            'environment': environment,
            'ports': {
                'argocd': 30100,
                'backstage': 30105,
                'demo_app': 80,
            },
            'components': {
                'argocd': True,
                'backstage': True,
                'cert_manager': True,
                'ingress': True,
                'opentelemetry': True,
                'dynatrace': False,
                'keptn': False,
                'openfeature': False,
                'kubeaudit_cronjobs': False,
            },
            'secrets': {
                'source': 'local',
            },
        }

        # Environment-specific defaults
        if environment == 'codespaces':
            defaults['components']['dynatrace'] = True
            defaults['components']['keptn'] = True
            defaults['components']['openfeature'] = True
            defaults['components']['kubeaudit_cronjobs'] = True
            defaults['secrets']['source'] = 'eso'

        return defaults


def get_profile_for_environment(environment: str) -> Dict[str, Any]:
    """
    Convenience function to load a profile.

    Args:
        environment: Environment name

    Returns:
        Profile configuration dictionary
    """
    loader = ProfileLoader()
    return loader.load_or_default(environment)
