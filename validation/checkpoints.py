"""
Validation checkpoints for IDP platform installation.

Each checkpoint verifies a specific aspect of the installation.
"""

import subprocess
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List


logger = logging.getLogger(__name__)


@dataclass
class CheckpointResult:
    """Result of a validation checkpoint."""
    passed: bool
    message: str
    details: Optional[str] = None


class ValidationCheckpoint(ABC):
    """Base class for validation checkpoints."""

    def __init__(self, name: str, description: str):
        """
        Initialize checkpoint.

        Args:
            name: Short checkpoint name
            description: Human-readable description
        """
        self.name = name
        self.description = description

    @abstractmethod
    def validate(self) -> CheckpointResult:
        """
        Run the validation.

        Returns:
            CheckpointResult with pass/fail status
        """
        pass

    def _run_kubectl(self, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Run kubectl command and return result."""
        cmd = ["kubectl"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class ClusterCheckpoint(ValidationCheckpoint):
    """Validate that the Kubernetes cluster is running."""

    def __init__(self, cluster_type: str = "minikube"):
        """
        Initialize cluster checkpoint.

        Args:
            cluster_type: Type of cluster ('minikube' or 'kind')
        """
        super().__init__(
            name="cluster",
            description=f"Verify {cluster_type} cluster is running"
        )
        self.cluster_type = cluster_type

    def validate(self) -> CheckpointResult:
        """Check if cluster is running and accessible."""
        try:
            if self.cluster_type == "minikube":
                result = subprocess.run(
                    ["minikube", "status"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0 and "Running" in result.stdout:
                    return CheckpointResult(
                        passed=True,
                        message="Minikube cluster is running",
                        details=result.stdout
                    )
                return CheckpointResult(
                    passed=False,
                    message="Minikube cluster is not running",
                    details=result.stderr or result.stdout
                )
            else:  # kind
                result = subprocess.run(
                    ["kind", "get", "clusters"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0 and "kind" in result.stdout:
                    return CheckpointResult(
                        passed=True,
                        message="Kind cluster exists",
                        details=result.stdout
                    )
                return CheckpointResult(
                    passed=False,
                    message="Kind cluster not found",
                    details=result.stderr
                )
        except subprocess.TimeoutExpired:
            return CheckpointResult(
                passed=False,
                message="Cluster check timed out"
            )
        except FileNotFoundError:
            return CheckpointResult(
                passed=False,
                message=f"{self.cluster_type} CLI not found"
            )


class NamespaceCheckpoint(ValidationCheckpoint):
    """Validate that required namespaces exist."""

    def __init__(self, namespaces: List[str]):
        """
        Initialize namespace checkpoint.

        Args:
            namespaces: List of required namespace names
        """
        super().__init__(
            name="namespaces",
            description=f"Verify namespaces exist: {', '.join(namespaces)}"
        )
        self.namespaces = namespaces

    def validate(self) -> CheckpointResult:
        """Check if all required namespaces exist."""
        try:
            result = self._run_kubectl(["get", "namespaces", "-o", "name"])
            if result.returncode != 0:
                return CheckpointResult(
                    passed=False,
                    message="Could not list namespaces",
                    details=result.stderr
                )

            existing = result.stdout
            missing = []
            for ns in self.namespaces:
                if f"namespace/{ns}" not in existing:
                    missing.append(ns)

            if missing:
                return CheckpointResult(
                    passed=False,
                    message=f"Missing namespaces: {', '.join(missing)}",
                    details=existing
                )

            return CheckpointResult(
                passed=True,
                message=f"All {len(self.namespaces)} namespaces exist"
            )
        except Exception as e:
            return CheckpointResult(
                passed=False,
                message=f"Namespace check failed: {e}"
            )


class DeploymentCheckpoint(ValidationCheckpoint):
    """Validate that a deployment is running."""

    def __init__(self, name: str, namespace: str):
        """
        Initialize deployment checkpoint.

        Args:
            name: Deployment name
            namespace: Namespace containing the deployment
        """
        super().__init__(
            name=f"deployment-{name}",
            description=f"Verify deployment {name} in {namespace}"
        )
        self.deployment_name = name
        self.namespace = namespace

    def validate(self) -> CheckpointResult:
        """Check if deployment exists and has ready replicas."""
        try:
            result = self._run_kubectl([
                "-n", self.namespace,
                "get", "deployment", self.deployment_name,
                "-o", "jsonpath={.status.readyReplicas}"
            ])

            if result.returncode != 0:
                return CheckpointResult(
                    passed=False,
                    message=f"Deployment {self.deployment_name} not found",
                    details=result.stderr
                )

            ready_replicas = result.stdout.strip()
            if ready_replicas and int(ready_replicas) > 0:
                return CheckpointResult(
                    passed=True,
                    message=f"Deployment {self.deployment_name} has {ready_replicas} ready replicas"
                )

            return CheckpointResult(
                passed=False,
                message=f"Deployment {self.deployment_name} has no ready replicas",
                details=f"Ready replicas: {ready_replicas}"
            )
        except Exception as e:
            return CheckpointResult(
                passed=False,
                message=f"Deployment check failed: {e}"
            )


class SecretCheckpoint(ValidationCheckpoint):
    """Validate that a secret exists."""

    def __init__(self, name: str, namespace: str, required_keys: Optional[List[str]] = None):
        """
        Initialize secret checkpoint.

        Args:
            name: Secret name
            namespace: Namespace containing the secret
            required_keys: Optional list of required data keys
        """
        super().__init__(
            name=f"secret-{name}",
            description=f"Verify secret {name} in {namespace}"
        )
        self.secret_name = name
        self.namespace = namespace
        self.required_keys = required_keys or []

    def validate(self) -> CheckpointResult:
        """Check if secret exists and has required keys."""
        try:
            result = self._run_kubectl([
                "-n", self.namespace,
                "get", "secret", self.secret_name,
                "-o", "jsonpath={.data}"
            ])

            if result.returncode != 0:
                return CheckpointResult(
                    passed=False,
                    message=f"Secret {self.secret_name} not found",
                    details=result.stderr
                )

            if not self.required_keys:
                return CheckpointResult(
                    passed=True,
                    message=f"Secret {self.secret_name} exists"
                )

            # Check for required keys
            data = result.stdout
            missing_keys = []
            for key in self.required_keys:
                if f'"{key}"' not in data:
                    missing_keys.append(key)

            if missing_keys:
                return CheckpointResult(
                    passed=False,
                    message=f"Secret {self.secret_name} missing keys: {', '.join(missing_keys)}"
                )

            return CheckpointResult(
                passed=True,
                message=f"Secret {self.secret_name} has all required keys"
            )
        except Exception as e:
            return CheckpointResult(
                passed=False,
                message=f"Secret check failed: {e}"
            )


class ServiceCheckpoint(ValidationCheckpoint):
    """Validate that a service exists and is accessible."""

    def __init__(self, name: str, namespace: str, port: Optional[int] = None):
        """
        Initialize service checkpoint.

        Args:
            name: Service name
            namespace: Namespace containing the service
            port: Optional port to verify
        """
        super().__init__(
            name=f"service-{name}",
            description=f"Verify service {name} in {namespace}"
        )
        self.service_name = name
        self.namespace = namespace
        self.port = port

    def validate(self) -> CheckpointResult:
        """Check if service exists."""
        try:
            result = self._run_kubectl([
                "-n", self.namespace,
                "get", "service", self.service_name,
                "-o", "jsonpath={.spec.ports[*].port}"
            ])

            if result.returncode != 0:
                return CheckpointResult(
                    passed=False,
                    message=f"Service {self.service_name} not found",
                    details=result.stderr
                )

            ports = result.stdout.strip()
            if self.port and str(self.port) not in ports:
                return CheckpointResult(
                    passed=False,
                    message=f"Service {self.service_name} does not expose port {self.port}",
                    details=f"Available ports: {ports}"
                )

            return CheckpointResult(
                passed=True,
                message=f"Service {self.service_name} exists",
                details=f"Ports: {ports}"
            )
        except Exception as e:
            return CheckpointResult(
                passed=False,
                message=f"Service check failed: {e}"
            )


class URLCheckpoint(ValidationCheckpoint):
    """Validate that a URL is accessible."""

    def __init__(self, name: str, url: str, expected_status: int = 200):
        """
        Initialize URL checkpoint.

        Args:
            name: Checkpoint name
            url: URL to check
            expected_status: Expected HTTP status code
        """
        super().__init__(
            name=f"url-{name}",
            description=f"Verify URL {url} is accessible"
        )
        self.url = url
        self.expected_status = expected_status

    def validate(self) -> CheckpointResult:
        """Check if URL is accessible."""
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(self.url, method='HEAD')
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == self.expected_status:
                    return CheckpointResult(
                        passed=True,
                        message=f"URL {self.url} returned {response.status}"
                    )
                return CheckpointResult(
                    passed=False,
                    message=f"URL {self.url} returned {response.status}, expected {self.expected_status}"
                )
        except urllib.error.HTTPError as e:
            # Some status codes are still valid (e.g., 401 for auth-protected endpoints)
            if e.code == self.expected_status:
                return CheckpointResult(
                    passed=True,
                    message=f"URL {self.url} returned expected status {e.code}"
                )
            return CheckpointResult(
                passed=False,
                message=f"URL {self.url} returned {e.code}",
                details=str(e)
            )
        except Exception as e:
            return CheckpointResult(
                passed=False,
                message=f"URL check failed: {e}"
            )
