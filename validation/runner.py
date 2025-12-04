"""
Validation runner for executing checkpoint suites.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from validation.checkpoints import (
    ValidationCheckpoint,
    CheckpointResult,
    ClusterCheckpoint,
    NamespaceCheckpoint,
    DeploymentCheckpoint,
    SecretCheckpoint,
    ServiceCheckpoint,
)


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Complete validation run result."""
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    results: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: str = ""

    def summary(self) -> str:
        """Return human-readable summary."""
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Validation {status}: {self.passed_count}/{self.total} checkpoints passed "
            f"({self.duration_seconds:.1f}s)"
        )

    def details(self) -> str:
        """Return detailed results."""
        lines = [self.summary(), ""]
        for r in self.results:
            status = "✓" if r['passed'] else "✗"
            lines.append(f"  {status} {r['name']}: {r['message']}")
            if r.get('details') and not r['passed']:
                for line in r['details'].split('\n')[:3]:
                    lines.append(f"      {line}")
        return "\n".join(lines)


class ValidationRunner:
    """
    Runs validation checkpoint suites.

    Provides predefined checkpoint suites for different installation phases
    and supports custom checkpoint lists.
    """

    def __init__(self, environment: str = "minikube"):
        """
        Initialize validation runner.

        Args:
            environment: Environment type ('minikube' or 'codespaces')
        """
        self.environment = environment

    def run(self, checkpoints: List[ValidationCheckpoint]) -> ValidationResult:
        """
        Run a list of validation checkpoints.

        Args:
            checkpoints: List of checkpoints to run

        Returns:
            ValidationResult with all checkpoint results
        """
        start = datetime.now()
        results = []
        passed_count = 0

        for checkpoint in checkpoints:
            logger.info(f"Running checkpoint: {checkpoint.name}")
            try:
                result = checkpoint.validate()
                results.append({
                    'name': checkpoint.name,
                    'description': checkpoint.description,
                    'passed': result.passed,
                    'message': result.message,
                    'details': result.details,
                })
                if result.passed:
                    passed_count += 1
                    logger.info(f"  ✓ {result.message}")
                else:
                    logger.warning(f"  ✗ {result.message}")
            except Exception as e:
                logger.error(f"  ✗ Checkpoint failed with exception: {e}")
                results.append({
                    'name': checkpoint.name,
                    'description': checkpoint.description,
                    'passed': False,
                    'message': f"Exception: {e}",
                    'details': None,
                })

        duration = (datetime.now() - start).total_seconds()

        return ValidationResult(
            passed=passed_count == len(checkpoints),
            total=len(checkpoints),
            passed_count=passed_count,
            failed_count=len(checkpoints) - passed_count,
            results=results,
            duration_seconds=duration,
            timestamp=start.isoformat(),
        )

    def get_cluster_checkpoints(self) -> List[ValidationCheckpoint]:
        """Get checkpoints for cluster validation."""
        cluster_type = "kind" if self.environment == "codespaces" else "minikube"
        return [ClusterCheckpoint(cluster_type=cluster_type)]

    def get_namespace_checkpoints(self) -> List[ValidationCheckpoint]:
        """Get checkpoints for namespace validation."""
        required_namespaces = ["argocd", "backstage", "opentelemetry", "monaco", "dynatrace"]
        return [NamespaceCheckpoint(namespaces=required_namespaces)]

    def get_argocd_checkpoints(self) -> List[ValidationCheckpoint]:
        """Get checkpoints for ArgoCD validation."""
        return [
            DeploymentCheckpoint("argocd-server", "argocd"),
            DeploymentCheckpoint("argocd-repo-server", "argocd"),
            DeploymentCheckpoint("argocd-applicationset-controller", "argocd"),
            SecretCheckpoint("argocd-initial-admin-secret", "argocd"),
            ServiceCheckpoint("argocd-server", "argocd"),
        ]

    def get_backstage_checkpoints(self) -> List[ValidationCheckpoint]:
        """Get checkpoints for Backstage validation."""
        return [
            DeploymentCheckpoint("backstage", "backstage"),
            SecretCheckpoint("backstage-secrets", "backstage"),
            ServiceCheckpoint("backstage", "backstage"),
        ]

    def get_secrets_checkpoints(self, include_dynatrace: bool = True) -> List[ValidationCheckpoint]:
        """Get checkpoints for secrets validation."""
        checkpoints = [
            SecretCheckpoint("github-token", "argocd", ["token"]),
            SecretCheckpoint("backstage-secrets", "backstage"),
        ]

        if include_dynatrace:
            checkpoints.extend([
                SecretCheckpoint("dt-bizevent-oauth-details", "dynatrace"),
                SecretCheckpoint("dt-bizevent-oauth-details", "opentelemetry"),
                SecretCheckpoint("dt-details", "opentelemetry"),
                SecretCheckpoint("platform-engineering-demo", "dynatrace"),
                SecretCheckpoint("monaco-secret", "monaco"),
                SecretCheckpoint("argocd-notifications-secret", "argocd"),
            ])

        return checkpoints

    def get_full_checkpoints(self, include_dynatrace: bool = True) -> List[ValidationCheckpoint]:
        """Get complete checkpoint suite for full validation."""
        checkpoints = []
        checkpoints.extend(self.get_cluster_checkpoints())
        checkpoints.extend(self.get_namespace_checkpoints())
        checkpoints.extend(self.get_argocd_checkpoints())
        checkpoints.extend(self.get_backstage_checkpoints())
        checkpoints.extend(self.get_secrets_checkpoints(include_dynatrace))
        return checkpoints

    def validate_phase(self, phase: str, include_dynatrace: bool = True) -> ValidationResult:
        """
        Run validation for a specific installation phase.

        Args:
            phase: Phase name ('cluster', 'namespaces', 'argocd', 'backstage', 'secrets', 'full')
            include_dynatrace: Include Dynatrace-specific checks

        Returns:
            ValidationResult for the phase
        """
        phase_checkpoints = {
            'cluster': self.get_cluster_checkpoints,
            'namespaces': self.get_namespace_checkpoints,
            'argocd': self.get_argocd_checkpoints,
            'backstage': self.get_backstage_checkpoints,
            'secrets': lambda: self.get_secrets_checkpoints(include_dynatrace),
            'full': lambda: self.get_full_checkpoints(include_dynatrace),
        }

        getter = phase_checkpoints.get(phase)
        if not getter:
            raise ValueError(f"Unknown phase: {phase}. Valid: {list(phase_checkpoints.keys())}")

        checkpoints = getter() if callable(getter) else getter
        return self.run(checkpoints)


def validate_installation(
    environment: str = "minikube",
    phase: str = "full",
    include_dynatrace: bool = True
) -> ValidationResult:
    """
    Convenience function to validate installation.

    Args:
        environment: Environment type
        phase: Validation phase
        include_dynatrace: Include Dynatrace checks

    Returns:
        ValidationResult
    """
    runner = ValidationRunner(environment=environment)
    return runner.validate_phase(phase, include_dynatrace)
