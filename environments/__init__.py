"""
Environment abstraction layer for IDP platform deployment.

Supports multiple environments:
- Codespaces: GitHub Codespaces with Kind cluster
- Minikube: Local minikube deployment
"""

from environments.base import EnvironmentBase, ClusterConfig, PortConfig
from environments.factory import EnvironmentFactory, EnvironmentNotSupportedError
from environments.codespaces import CodespacesEnvironment
from environments.minikube import MinikubeEnvironment

__all__ = [
    'EnvironmentBase',
    'ClusterConfig',
    'PortConfig',
    'EnvironmentFactory',
    'EnvironmentNotSupportedError',
    'CodespacesEnvironment',
    'MinikubeEnvironment',
]
