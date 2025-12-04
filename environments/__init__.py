"""
Environment abstraction layer for IDP platform deployment.

Supports multiple environments:
- Codespaces: GitHub Codespaces with Kind cluster
- Minikube: Local minikube deployment
"""

from environments.base import EnvironmentBase
from environments.factory import EnvironmentFactory, EnvironmentNotSupportedError
from environments.codespaces import CodespacesEnvironment
from environments.minikube import MinikubeEnvironment

__all__ = [
    'EnvironmentBase',
    'EnvironmentFactory',
    'EnvironmentNotSupportedError',
    'CodespacesEnvironment',
    'MinikubeEnvironment'
]
