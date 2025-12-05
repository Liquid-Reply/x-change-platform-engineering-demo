"""
Secrets management package for IDP platform.

Provides unified secrets loading from multiple sources:
- Environment variables (Codespaces, CI/CD)
- Local YAML files (minikube)
- External Secrets Operator (production)
"""

from secrets.manager import (
    SecretsManager,
    SecretsNotFoundError,
    SecretsValidationError,
    DynatraceSecrets,
    GitHubSecrets,
    PlatformSecrets,
    get_secrets_manager,
)

__all__ = [
    'SecretsManager',
    'SecretsNotFoundError',
    'SecretsValidationError',
    'DynatraceSecrets',
    'GitHubSecrets',
    'PlatformSecrets',
    'get_secrets_manager',
]
