# Design Document: Codespaces-to-Minikube Migration

*Implementation design for Option B: Environment Abstraction Layer*

---

## 1. Naming Conventions

### 1.1 Python Modules and Classes

| Category | Convention | Example |
|----------|------------|---------|
| Modules | `snake_case` | `environment_base.py`, `minikube_env.py` |
| Classes | `PascalCase` | `MinikubeEnvironment`, `SecretsManager` |
| Abstract base | `*Base` suffix | `EnvironmentBase` |
| Environment impl | `*Environment` suffix | `CodespacesEnvironment`, `MinikubeEnvironment` |

### 1.2 Configuration Files

| Category | Convention | Example |
|----------|------------|---------|
| Profile configs | `{environment}.yaml` | `minikube.yaml`, `codespaces.yaml` |
| Secrets files | `secrets-{environment}.yaml` | `secrets-minikube.yaml` |
| Kustomize overlays | `overlays/{environment}/` | `overlays/minikube/` |

### 1.3 Kubernetes Resources

| Category | Convention | Example |
|----------|------------|---------|
| ConfigMaps | `{component}-config` | `backstage-config`, `argocd-config` |
| Secrets | `{component}-secrets` | `backstage-secrets`, `github-token` |
| Namespaces | Lowercase, hyphenated | `argocd`, `backstage`, `opentelemetry` |

---

## 2. Error Handling Design

### 2.1 Exception Hierarchy

```python
class IDPError(Exception):
    """Base exception for all IDP errors"""
    pass

class EnvironmentError(IDPError):
    """Environment detection/configuration errors"""
    pass

class ClusterError(IDPError):
    """Cluster lifecycle errors"""
    pass

class SecretsError(IDPError):
    """Secrets management errors"""
    pass

class ValidationError(IDPError):
    """Validation checkpoint failures"""
    pass
```

### 2.2 Error Propagation Strategy

| Layer | Behavior |
|-------|----------|
| Environment detection | Raise `EnvironmentError` with supported options |
| Cluster operations | Retry 3x with exponential backoff, then raise `ClusterError` |
| Secrets loading | Log warning if optional secret missing, raise if required |
| Validation | Collect all failures, report summary |

### 2.3 Graceful Degradation

| Component | Missing Condition | Behavior |
|-----------|-------------------|----------|
| Dynatrace | No DT credentials | Skip Dynatrace apps, log info |
| Keptn | `INSTALL_KEPTN=false` | Skip Keptn installation |
| OTEL | No DT endpoint | Deploy collector in standalone mode |

---

## 3. Architecture Patterns

### 3.1 Core Design Principles

| Principle | Application |
|-----------|-------------|
| **Strategy Pattern** | Environment-specific behavior via `EnvironmentBase` implementations |
| **Factory Pattern** | `EnvironmentFactory.detect()` creates appropriate environment |
| **Template Method** | Base class defines setup steps, subclasses override specifics |
| **Dependency Injection** | Profile loader injected into environment classes |

### 3.2 Module Structure

```
environments/
├── __init__.py
├── base.py              # EnvironmentBase abstract class
├── codespaces.py        # CodespacesEnvironment
├── minikube.py          # MinikubeEnvironment
├── factory.py           # EnvironmentFactory
└── profiles/
    ├── codespaces.yaml
    └── minikube.yaml

secrets/
├── __init__.py
├── manager.py           # SecretsManager
└── local_loader.py      # Load from secrets-*.yaml

validation/
├── __init__.py
├── checkpoints.py       # ValidationCheckpoint definitions
└── runner.py            # ValidationRunner
```

---

## 4. Component Design

### 4.1 EnvironmentBase Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class EnvironmentBase(ABC):
    """Abstract base class for environment-specific configuration"""

    @abstractmethod
    def get_name(self) -> str:
        """Return environment name (e.g., 'minikube', 'codespaces')"""
        pass

    @abstractmethod
    def get_base_url(self) -> str:
        """Return base URL for applications"""
        pass

    @abstractmethod
    def get_service_url(self, service: str, port: int) -> str:
        """Return URL for a specific service"""
        pass

    @abstractmethod
    def create_cluster(self) -> bool:
        """Create/configure the Kubernetes cluster"""
        pass

    @abstractmethod
    def get_placeholder_values(self) -> Dict[str, str]:
        """Return environment-specific placeholder substitutions"""
        pass

    @abstractmethod
    def get_enabled_components(self) -> List[str]:
        """Return list of enabled components for this environment"""
        pass
```

### 4.2 MinikubeEnvironment Implementation

```python
class MinikubeEnvironment(EnvironmentBase):
    def __init__(self, profile: dict):
        self.profile = profile
        self._minikube_ip: Optional[str] = None

    def get_name(self) -> str:
        return "minikube"

    def get_minikube_ip(self) -> str:
        if not self._minikube_ip:
            result = subprocess.run(
                ["minikube", "ip"],
                capture_output=True, text=True
            )
            self._minikube_ip = result.stdout.strip()
        return self._minikube_ip

    def get_base_url(self) -> str:
        use_nip_io = self.profile.get("urls", {}).get("use_nip_io", True)
        if use_nip_io:
            return f"{self.get_minikube_ip()}.nip.io"
        return "localhost"

    def get_service_url(self, service: str, port: int) -> str:
        return f"http://localhost:{port}"

    def create_cluster(self) -> bool:
        cluster_config = self.profile.get("cluster", {})
        cmd = [
            "minikube", "start",
            f"--driver={cluster_config.get('driver', 'docker')}",
            f"--cpus={cluster_config.get('cpus', 2)}",
            f"--memory={cluster_config.get('memory', 4096)}",
        ]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise ClusterError("Failed to create minikube cluster")

        # Enable addons
        for addon in cluster_config.get("addons", []):
            subprocess.run(["minikube", "addons", "enable", addon])

        return True

    def get_placeholder_values(self) -> Dict[str, str]:
        return {
            "CODESPACE_NAME_PLACEHOLDER": "minikube",
            "BASE_DOMAIN_PLACEHOLDER": self.get_base_url(),
            "ARGOCD_URL_PLACEHOLDER": self.get_service_url("argocd", 30100),
            "BACKSTAGE_URL_PLACEHOLDER": self.get_service_url("backstage", 30105),
        }

    def get_enabled_components(self) -> List[str]:
        components = self.profile.get("components", {})
        return [k for k, v in components.items() if v]
```

### 4.3 SecretsManager Design

```python
class SecretsManager:
    """Manages secrets for different environments"""

    def __init__(self, environment: EnvironmentBase, secrets_file: Optional[str] = None):
        self.environment = environment
        self.secrets_file = secrets_file or f"secrets-{environment.get_name()}.yaml"

    def load_secrets(self) -> Dict[str, Dict[str, str]]:
        """Load secrets from local file or return empty for ESO"""
        if not os.path.exists(self.secrets_file):
            logging.warning(f"Secrets file {self.secrets_file} not found")
            return {}

        with open(self.secrets_file) as f:
            return yaml.safe_load(f)

    def create_kubernetes_secrets(self, namespace_secrets: Dict[str, Dict[str, str]]):
        """Create Kubernetes secrets in appropriate namespaces"""
        for namespace, secrets in namespace_secrets.items():
            for secret_name, data in secrets.items():
                self._create_secret(namespace, secret_name, data)

    def _create_secret(self, namespace: str, name: str, data: dict):
        """Create a single Kubernetes secret"""
        # Ensure namespace exists
        subprocess.run(["kubectl", "create", "ns", namespace], capture_output=True)

        # Create secret
        cmd = ["kubectl", "create", "secret", "generic", name, "-n", namespace]
        for key, value in data.items():
            cmd.append(f"--from-literal={key}={value}")
        cmd.append("--dry-run=client")
        cmd.append("-o")
        cmd.append("yaml")

        # Apply with kubectl
        result = subprocess.run(cmd, capture_output=True, text=True)
        subprocess.run(["kubectl", "apply", "-f", "-"], input=result.stdout, text=True)
```

### 4.4 Secrets File Format

```yaml
# secrets-minikube.yaml (gitignored)
argocd:
  github-token:
    token: "ghp_xxxxxxxxxxxxxxxxxxxx"

backstage:
  backstage-secrets:
    GITHUB_TOKEN: "ghp_xxxxxxxxxxxxxxxxxxxx"
    POSTGRES_PASSWORD: "backstage"

dynatrace:
  dynatrace-tokens:
    DT_API_TOKEN: "dt0c01.xxxxxxxx"
    DT_PAAS_TOKEN: "dt0c01.xxxxxxxx"

opentelemetry:
  dt-credentials:
    DT_ENDPOINT: "https://abc12345.live.dynatrace.com/api/v2/otlp"
    DT_API_TOKEN: "dt0c01.xxxxxxxx"
```

---

## 5. Validation Checkpoint Design

### 5.1 Checkpoint Definition

```python
@dataclass
class ValidationCheckpoint:
    name: str
    phase: int
    command: str
    success_pattern: str
    timeout_seconds: int = 60
    optional: bool = False

CHECKPOINTS = [
    ValidationCheckpoint(
        name="Cluster Running",
        phase=1,
        command="minikube status",
        success_pattern="Running"
    ),
    ValidationCheckpoint(
        name="Namespaces Created",
        phase=2,
        command="kubectl get ns",
        success_pattern="argocd.*backstage"
    ),
    ValidationCheckpoint(
        name="ArgoCD Accessible",
        phase=3,
        command="curl -s http://localhost:30100",
        success_pattern="Argo CD"
    ),
    ValidationCheckpoint(
        name="Secrets Exist",
        phase=4,
        command="kubectl get secrets -n argocd",
        success_pattern="github-token"
    ),
    ValidationCheckpoint(
        name="Apps Synced",
        phase=5,
        command="kubectl get applications -n argocd",
        success_pattern="Synced"
    ),
    ValidationCheckpoint(
        name="Backstage Running",
        phase=6,
        command="curl -s http://localhost:30105",
        success_pattern="Backstage"
    ),
    ValidationCheckpoint(
        name="OTEL Collector Running",
        phase=7,
        command="kubectl get pods -n opentelemetry",
        success_pattern="Running",
        optional=True
    ),
]
```

### 5.2 Validation Runner

```python
class ValidationRunner:
    def __init__(self, checkpoints: List[ValidationCheckpoint]):
        self.checkpoints = checkpoints
        self.results: List[Tuple[ValidationCheckpoint, bool, str]] = []

    def run_phase(self, phase: int) -> bool:
        """Run all checkpoints for a specific phase"""
        phase_checkpoints = [c for c in self.checkpoints if c.phase == phase]
        all_passed = True

        for checkpoint in phase_checkpoints:
            passed, output = self._run_checkpoint(checkpoint)
            self.results.append((checkpoint, passed, output))

            if not passed and not checkpoint.optional:
                all_passed = False
                logging.error(f"Checkpoint failed: {checkpoint.name}")
            elif passed:
                logging.info(f"Checkpoint passed: {checkpoint.name}")

        return all_passed

    def _run_checkpoint(self, checkpoint: ValidationCheckpoint) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                checkpoint.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=checkpoint.timeout_seconds
            )
            output = result.stdout + result.stderr
            passed = re.search(checkpoint.success_pattern, output) is not None
            return passed, output
        except subprocess.TimeoutExpired:
            return False, "Timeout"
```

---

## 6. File Modification Strategy

### 6.1 Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `cluster_installer.py` | Major refactor | Import environment abstraction, delegate to env class |
| `utils.py` | Minor changes | Add environment-aware placeholder replacement |
| `.gitignore` | Add entry | `secrets-minikube.yaml` |

### 6.2 New Files to Create

| File | Purpose |
|------|---------|
| `environments/__init__.py` | Package init |
| `environments/base.py` | EnvironmentBase abstract class |
| `environments/minikube.py` | MinikubeEnvironment class |
| `environments/codespaces.py` | CodespacesEnvironment (refactored from existing) |
| `environments/factory.py` | Environment detection factory |
| `config/profiles/minikube.yaml` | Minikube configuration profile |
| `config/profiles/codespaces.yaml` | Codespaces configuration profile |
| `secrets/manager.py` | SecretsManager class |
| `validation/checkpoints.py` | Validation checkpoint definitions |
| `validation/runner.py` | Validation execution |
| `minikube_installer.py` | Entry point for minikube setup |
| `secrets-minikube.yaml.example` | Template for local secrets |

### 6.3 Placeholder Substitution Changes

Current pattern in `utils.py`:
```python
def replace_placeholders(content: str) -> str:
    # Hardcoded Codespaces values
    content = content.replace("CODESPACE_NAME_PLACEHOLDER", os.getenv("CODESPACE_NAME"))
```

New pattern:
```python
def replace_placeholders(content: str, environment: EnvironmentBase) -> str:
    placeholders = environment.get_placeholder_values()
    for placeholder, value in placeholders.items():
        content = content.replace(placeholder, value)
    return content
```

---

## 7. Quality Attribute Implementation

### 7.1 Portability

| Strategy | Implementation |
|----------|----------------|
| OS-agnostic paths | Use `pathlib.Path` instead of string concatenation |
| Shell command abstraction | Wrap subprocess calls, handle OS differences |
| Driver detection | Auto-detect docker vs podman |

### 7.2 Maintainability

| Strategy | Implementation |
|----------|----------------|
| Single responsibility | Each module handles one concern |
| Configuration over code | YAML profiles for environment-specific settings |
| Logging | Structured logging with levels (DEBUG, INFO, WARNING, ERROR) |

### 7.3 Testability

| Strategy | Implementation |
|----------|----------------|
| Dependency injection | Environment and secrets passed to functions |
| Mock-friendly interfaces | Abstract base classes enable test doubles |
| Validation checkpoints | Automated verification at each phase |

---

## 8. Implementation Phases

### Phase 1: Environment Abstraction (Day 1-2)
1. Create `environments/` package structure
2. Implement `EnvironmentBase` abstract class
3. Refactor existing Codespaces logic into `CodespacesEnvironment`
4. Implement `MinikubeEnvironment`
5. Create `EnvironmentFactory` with detection logic

### Phase 2: Configuration Profiles (Day 2)
1. Create `config/profiles/` directory
2. Define YAML schema for profiles
3. Implement profile loader
4. Create `minikube.yaml` and `codespaces.yaml` profiles

### Phase 3: Secrets Management (Day 3)
1. Create `secrets/` package
2. Implement `SecretsManager` class
3. Create `secrets-minikube.yaml.example` template
4. Add `.gitignore` entry for local secrets

### Phase 4: Installer Refactor (Day 3-4)
1. Create `minikube_installer.py` entry point
2. Refactor `cluster_installer.py` to use environment abstraction
3. Update `utils.py` for environment-aware placeholder replacement
4. Integrate validation checkpoints

### Phase 5: Validation & Testing (Day 4-5)
1. Implement validation checkpoint system
2. Create automated test script
3. Run full validation sequence
4. Document any issues and fixes

---

## 9. Implementation Notes

### 9.1 Backward Compatibility

- Existing `cluster_installer.py` continues to work in Codespaces
- Environment detection auto-selects Codespaces when `CODESPACE_NAME` is set
- No changes required for existing Codespaces users

### 9.2 Known Limitations

| Limitation | Workaround |
|------------|------------|
| minikube tunnel required for some features | Document in setup instructions |
| nip.io requires internet | Fallback to localhost available |
| Windows path handling | Use pathlib throughout |

### 9.3 Future Enhancements (Out of Scope)

- Full Kustomize overlays (Option C migration path)
- Cloud provider environments (EKS, GKE, AKS)
- Terraform-based infrastructure
