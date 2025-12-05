"""
Validation package for IDP platform installation.

Provides checkpoints and validation runners to verify
successful installation at each phase.
"""

from validation.checkpoints import (
    ValidationCheckpoint,
    CheckpointResult,
    ClusterCheckpoint,
    NamespaceCheckpoint,
    DeploymentCheckpoint,
    SecretCheckpoint,
    ServiceCheckpoint,
    URLCheckpoint,
)
from validation.runner import ValidationRunner, ValidationResult

__all__ = [
    'ValidationCheckpoint',
    'CheckpointResult',
    'ClusterCheckpoint',
    'NamespaceCheckpoint',
    'DeploymentCheckpoint',
    'SecretCheckpoint',
    'ServiceCheckpoint',
    'URLCheckpoint',
    'ValidationRunner',
    'ValidationResult',
]
