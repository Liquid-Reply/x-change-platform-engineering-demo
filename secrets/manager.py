"""
Secrets manager for loading and managing platform secrets.
"""

import os
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any, List

import yaml


logger = logging.getLogger(__name__)


class SecretsNotFoundError(Exception):
    """Raised when required secrets cannot be found."""
    pass


class SecretsValidationError(Exception):
    """Raised when secrets validation fails."""
    pass


@dataclass
class DynatraceSecrets:
    """Dynatrace-related secrets."""
    rw_api_token: str           # DT_RW_API_TOKEN
    oauth_client_id: str        # DT_OAUTH_CLIENT_ID
    oauth_client_secret: str    # DT_OAUTH_CLIENT_SECRET
    oauth_account_urn: str      # DT_OAUTH_ACCOUNT_URN
    env_name: str               # DT_ENV_NAME (e.g., 'abc12345')
    env: str                    # DT_ENV (e.g., 'live', 'sprint', 'dev')


@dataclass
class GitHubSecrets:
    """GitHub-related secrets."""
    token: str                  # GITHUB_TOKEN


@dataclass
class PlatformSecrets:
    """All platform secrets."""
    dynatrace: Optional[DynatraceSecrets]
    github: Optional[GitHubSecrets]

    def has_dynatrace(self) -> bool:
        """Check if Dynatrace secrets are available."""
        return self.dynatrace is not None

    def has_github(self) -> bool:
        """Check if GitHub secrets are available."""
        return self.github is not None


class SecretsManager:
    """
    Unified secrets manager for loading secrets from multiple sources.

    Supports:
    - Environment variables (default for Codespaces)
    - Local YAML file (for minikube)
    - Hybrid (env vars with YAML fallback)
    """

    # Required Dynatrace environment variables
    DT_REQUIRED_VARS = [
        'DT_RW_API_TOKEN',
        'DT_ENV_NAME',
        'DT_ENV',
        'DT_OAUTH_CLIENT_ID',
        'DT_OAUTH_CLIENT_SECRET',
        'DT_OAUTH_ACCOUNT_URN',
    ]

    # GitHub variables
    GITHUB_VARS = ['GITHUB_TOKEN']

    def __init__(
        self,
        source: str = 'auto',
        secrets_file: Optional[str] = None,
        require_dynatrace: bool = False,
        require_github: bool = False
    ):
        """
        Initialize SecretsManager.

        Args:
            source: Secrets source - 'env', 'file', or 'auto' (try env, then file)
            secrets_file: Path to secrets YAML file (for 'file' source)
            require_dynatrace: Raise error if Dynatrace secrets missing
            require_github: Raise error if GitHub secrets missing
        """
        self.source = source
        self.secrets_file = secrets_file
        self.require_dynatrace = require_dynatrace
        self.require_github = require_github
        self._secrets: Optional[PlatformSecrets] = None
        self._file_data: Dict[str, Any] = {}

    def load(self) -> PlatformSecrets:
        """
        Load secrets from configured source.

        Returns:
            PlatformSecrets containing all loaded secrets

        Raises:
            SecretsNotFoundError: If required secrets are missing
        """
        if self._secrets is not None:
            return self._secrets

        if self.source == 'env':
            self._secrets = self._load_from_env()
        elif self.source == 'file':
            self._secrets = self._load_from_file()
        else:  # 'auto'
            # Try environment first, then file
            self._secrets = self._load_from_env()
            if not self._secrets.has_dynatrace() and self.secrets_file:
                logger.info("Dynatrace secrets not in env, trying file...")
                file_secrets = self._load_from_file()
                if file_secrets.has_dynatrace():
                    self._secrets = PlatformSecrets(
                        dynatrace=file_secrets.dynatrace,
                        github=self._secrets.github or file_secrets.github
                    )

        self._validate()
        return self._secrets

    def _load_from_env(self) -> PlatformSecrets:
        """Load secrets from environment variables."""
        logger.info("Loading secrets from environment variables...")

        # Try to load Dynatrace secrets
        dt_secrets = None
        if all(os.environ.get(var) for var in self.DT_REQUIRED_VARS):
            dt_secrets = DynatraceSecrets(
                rw_api_token=os.environ['DT_RW_API_TOKEN'],
                oauth_client_id=os.environ['DT_OAUTH_CLIENT_ID'],
                oauth_client_secret=os.environ['DT_OAUTH_CLIENT_SECRET'],
                oauth_account_urn=os.environ['DT_OAUTH_ACCOUNT_URN'],
                env_name=os.environ['DT_ENV_NAME'],
                env=os.environ['DT_ENV'],
            )
            logger.info("Dynatrace secrets loaded from environment")
        else:
            missing = [v for v in self.DT_REQUIRED_VARS if not os.environ.get(v)]
            logger.debug(f"Missing Dynatrace env vars: {missing}")

        # Try to load GitHub secrets
        gh_secrets = None
        if os.environ.get('GITHUB_TOKEN'):
            gh_secrets = GitHubSecrets(token=os.environ['GITHUB_TOKEN'])
            logger.info("GitHub secrets loaded from environment")

        return PlatformSecrets(dynatrace=dt_secrets, github=gh_secrets)

    def _load_from_file(self) -> PlatformSecrets:
        """Load secrets from YAML file."""
        if not self.secrets_file:
            return PlatformSecrets(dynatrace=None, github=None)

        secrets_path = Path(self.secrets_file)
        if not secrets_path.exists():
            logger.warning(f"Secrets file not found: {secrets_path}")
            return PlatformSecrets(dynatrace=None, github=None)

        logger.info(f"Loading secrets from file: {secrets_path}")

        try:
            with open(secrets_path, 'r') as f:
                self._file_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise SecretsValidationError(f"Invalid YAML in secrets file: {e}")

        # Load Dynatrace secrets
        dt_data = self._file_data.get('dynatrace', {})
        dt_secrets = None
        if dt_data:
            try:
                dt_secrets = DynatraceSecrets(
                    rw_api_token=dt_data.get('rw_api_token', ''),
                    oauth_client_id=dt_data.get('oauth_client_id', ''),
                    oauth_client_secret=dt_data.get('oauth_client_secret', ''),
                    oauth_account_urn=dt_data.get('oauth_account_urn', ''),
                    env_name=dt_data.get('env_name', ''),
                    env=dt_data.get('env', 'live'),
                )
                if all([dt_secrets.rw_api_token, dt_secrets.env_name]):
                    logger.info("Dynatrace secrets loaded from file")
                else:
                    dt_secrets = None
            except Exception as e:
                logger.warning(f"Could not load Dynatrace secrets from file: {e}")

        # Load GitHub secrets
        gh_data = self._file_data.get('github', {})
        gh_secrets = None
        if gh_data and gh_data.get('token'):
            gh_secrets = GitHubSecrets(token=gh_data['token'])
            logger.info("GitHub secrets loaded from file")

        return PlatformSecrets(dynatrace=dt_secrets, github=gh_secrets)

    def _validate(self) -> None:
        """Validate that required secrets are present."""
        if self.require_dynatrace and not self._secrets.has_dynatrace():
            raise SecretsNotFoundError(
                "Dynatrace secrets required but not found.\n"
                "Set environment variables or create secrets-minikube.yaml file."
            )

        if self.require_github and not self._secrets.has_github():
            raise SecretsNotFoundError(
                "GitHub secrets required but not found.\n"
                "Set GITHUB_TOKEN environment variable."
            )

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a specific secret value by key.

        Args:
            key: Secret key (e.g., 'DT_RW_API_TOKEN', 'GITHUB_TOKEN')
            default: Default value if not found

        Returns:
            Secret value or default
        """
        secrets = self.load()

        # Map common keys to secrets
        key_map = {
            'DT_RW_API_TOKEN': lambda s: s.dynatrace.rw_api_token if s.dynatrace else None,
            'DT_OAUTH_CLIENT_ID': lambda s: s.dynatrace.oauth_client_id if s.dynatrace else None,
            'DT_OAUTH_CLIENT_SECRET': lambda s: s.dynatrace.oauth_client_secret if s.dynatrace else None,
            'DT_OAUTH_ACCOUNT_URN': lambda s: s.dynatrace.oauth_account_urn if s.dynatrace else None,
            'DT_ENV_NAME': lambda s: s.dynatrace.env_name if s.dynatrace else None,
            'DT_ENV': lambda s: s.dynatrace.env if s.dynatrace else None,
            'GITHUB_TOKEN': lambda s: s.github.token if s.github else None,
        }

        getter = key_map.get(key)
        if getter:
            value = getter(secrets)
            return value if value else default

        return default

    def create_k8s_secret(
        self,
        name: str,
        namespace: str,
        data: Dict[str, str],
        delete_existing: bool = True
    ) -> bool:
        """
        Create a Kubernetes secret.

        Args:
            name: Secret name
            namespace: Namespace to create secret in
            data: Key-value pairs for secret data
            delete_existing: Delete existing secret first

        Returns:
            True if successful
        """
        if delete_existing:
            subprocess.run(
                ["kubectl", "-n", namespace, "delete", "secret", name, "--ignore-not-found"],
                capture_output=True
            )

        cmd = ["kubectl", "-n", namespace, "create", "secret", "generic", name]
        for key, value in data.items():
            cmd.append(f"--from-literal={key}={value}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to create secret {name}: {result.stderr}")
            return False

        logger.info(f"Created secret {name} in namespace {namespace}")
        return True

    def get_k8s_secrets_spec(self) -> List[Dict[str, Any]]:
        """
        Get specifications for all platform Kubernetes secrets.

        Returns:
            List of secret specifications with name, namespace, and data
        """
        secrets = self.load()
        specs = []

        if secrets.has_github():
            specs.append({
                'name': 'github-token',
                'namespace': 'argocd',
                'data': {'token': secrets.github.token}
            })

        if secrets.has_dynatrace():
            dt = secrets.dynatrace

            # ArgoCD notifications secret
            specs.append({
                'name': 'argocd-notifications-secret',
                'namespace': 'argocd',
                'data': {
                    'dynatrace-url': f'https://{dt.env_name}.live.dynatrace.com',
                    'dynatrace-token': ''  # Will be filled with generated token
                }
            })

            # OAuth details for bizevent
            oauth_data = {
                'dtTenant': f'https://{dt.env_name}.live.dynatrace.com',
                'oAuthClientID': dt.oauth_client_id,
                'oAuthClientSecret': dt.oauth_client_secret,
                'accountURN': dt.oauth_account_urn,
            }
            specs.append({
                'name': 'dt-bizevent-oauth-details',
                'namespace': 'dynatrace',
                'data': oauth_data
            })
            specs.append({
                'name': 'dt-bizevent-oauth-details',
                'namespace': 'opentelemetry',
                'data': oauth_data
            })

        return specs


def get_secrets_manager(
    profile: Optional[Dict[str, Any]] = None,
    require_dynatrace: bool = False
) -> SecretsManager:
    """
    Factory function to create appropriate SecretsManager.

    Args:
        profile: Configuration profile
        require_dynatrace: Whether Dynatrace secrets are required

    Returns:
        Configured SecretsManager instance
    """
    if profile is None:
        profile = {}

    secrets_config = profile.get('secrets', {})
    source = secrets_config.get('source', 'auto')

    # Determine secrets file path
    secrets_file = None
    if source in ('local', 'file', 'auto'):
        local_file = secrets_config.get('local_file', 'secrets-minikube.yaml')
        secrets_file = Path.cwd() / local_file
        if not secrets_file.exists():
            # Also check in config directory
            secrets_file = Path.cwd() / 'config' / local_file
            if not secrets_file.exists():
                secrets_file = None

    return SecretsManager(
        source='auto',  # Always try env first, then file
        secrets_file=str(secrets_file) if secrets_file else None,
        require_dynatrace=require_dynatrace,
    )
