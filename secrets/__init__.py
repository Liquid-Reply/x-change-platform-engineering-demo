"""
Secrets management package for IDP platform.

Provides unified secrets loading from multiple sources:
- Environment variables (Codespaces, CI/CD)
- Local YAML files (minikube)
- External Secrets Operator (production)
"""

from secrets.manager import SecretsManager, SecretsNotFoundError

__all__ = ['SecretsManager', 'SecretsNotFoundError']
