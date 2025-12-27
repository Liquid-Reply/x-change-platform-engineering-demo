# Functional Tests

This directory contains functional tests for the IDP platform using [Chainsaw](https://kyverno.github.io/chainsaw/), a declarative Kubernetes end-to-end testing framework.

## Prerequisites

1. **Install Chainsaw**:
   ```bash
   # Using Go
   go install github.com/kyverno/chainsaw@latest

   # Using Homebrew (macOS)
   # Note: Homebrew core has a different tool named chainsaw, use the full tap path
   brew install kyverno/chainsaw/chainsaw

   # Using Krew (kubectl plugin manager)
   kubectl krew install chainsaw
   ```

2. **Running cluster**: Tests require a running Kubernetes cluster with the IDP platform deployed.

3. **kubectl configured**: Ensure kubectl is configured to access your cluster.

## Test Categories

| Test | Description | Type | Duration |
|------|-------------|------|----------|
| `01-platform-namespaces` | Verifies all required namespaces exist | Runtime | ~5s |
| `02-argocd-health` | Checks ArgoCD deployments are healthy | Runtime | ~10s |
| `03-argocd-apps-sync` | Validates ArgoCD applications are synced | Runtime | ~30s |
| `04-backstage-health` | Verifies Backstage deployment is running | Runtime | ~10s |
| `05-ingress-controller` | Checks Gateway API controller (Envoy Gateway) | Runtime | ~10s |
| `06-secrets-present` | Validates required secrets exist | Runtime | ~5s |
| `07-kustomize-build` | Tests Kustomize overlays build correctly | Static | ~30s |
| `08-gateway-api` | Comprehensive Gateway API validation | Mixed | ~60s |

### Test Types

- **Static**: Can run without a cluster (validates manifests, templates, Helm charts)
- **Runtime**: Requires a running cluster with deployed resources
- **Mixed**: Contains both static and runtime validation steps

## Running Tests

### Run All Tests
```bash
cd tests/functional
chainsaw test .
```

### Run Specific Test
```bash
chainsaw test ./01-platform-namespaces
```

### Run Multiple Tests
```bash
chainsaw test ./01-platform-namespaces ./02-argocd-health
```

### Run Static Tests Only (No Cluster Required)
```bash
chainsaw test ./07-kustomize-build ./08-gateway-api
```

### Run with Minimal Output
```bash
chainsaw test . --quiet
```

### Run with Custom Timeout
```bash
chainsaw test . --assert-timeout 5m
```

### Generate Report
```bash
chainsaw test . --report-format JSON --report-name results
```

## Gateway API Tests (08-gateway-api)

The `08-gateway-api` test suite provides comprehensive validation for the Gateway API migration:

### Static Validation Steps (no cluster required)
| Step | Description |
|------|-------------|
| `validate-envoy-gateway-kustomize` | Kustomize build produces Gateway resource |
| `validate-argo-rollouts-gateway-api` | Argo Rollouts has Gateway API plugin config |
| `validate-httproute-template` | HTTPRoute template has correct structure |
| `validate-rollout-template` | Rollout template uses Gateway API plugin |
| `validate-helm-chart` | Helm chart includes envoy-gateway apps |

### Runtime Validation Steps (requires cluster)
| Step | Description |
|------|-------------|
| `check-gateway-api-crds` | Gateway API CRDs are installed |
| `verify-gatewayclass` | GatewayClass is accepted |
| `verify-gateway` | Gateway is programmed |
| `test-httproute-routing` | End-to-end HTTPRoute routing works |
| `validate-argo-rollouts-gateway-plugin` | Rollouts ConfigMap has plugin |
| `validate-gateway-api-rbac` | RBAC for HTTPRoute access exists |

Runtime steps gracefully skip if Gateway API CRDs are not installed.

## Environment Compatibility

These tests are designed to work with all supported environments:

- **Minikube**: Local Kubernetes via Minikube
- **Kind**: Kubernetes in Docker
- **Codespaces**: GitHub Codespaces

The tests verify the common baseline platform components that exist in all environments. Environment-specific components (like Dynatrace or Keptn in Codespaces) are not tested here.

## Test Structure

Each test follows the Chainsaw format:

```yaml
apiVersion: chainsaw.kyverno.io/v1alpha1
kind: Test
metadata:
  name: test-name
spec:
  description: What this test validates
  steps:
    - name: step-name
      try:
        - assert:
            resource: {...}  # Resource assertions
        - script:
            content: |       # Shell script checks
              #!/bin/bash
              ...
```

## Writing New Tests

1. Create a new directory: `09-your-test-name/`
2. Create `chainsaw-test.yaml` with your test definition
3. Use `assert` for declarative resource checks
4. Use `script` for complex validation logic
5. For environment-independent tests, use graceful skips:
   ```bash
   if ! kubectl get crd <resource> >/dev/null 2>&1; then
     echo "SKIP: CRD not installed"
     exit 0
   fi
   ```
6. Run locally to validate before committing

## Troubleshooting

### Test Timeouts
Increase timeout with `--assert-timeout`:
```bash
chainsaw test . --assert-timeout 10m
```

### Debug Failures
Run with verbose output and keep resources on failure:
```bash
chainsaw test . --verbose --skip-delete
```

### View Test Logs
Chainsaw captures pod logs on failure. Check the test output or use:
```bash
kubectl logs -n <namespace> -l <selector>
```

### Gateway API Tests Skipping
If Gateway API runtime tests are skipping, ensure:
1. Gateway API CRDs are installed: `kubectl get crd gateways.gateway.networking.k8s.io`
2. Envoy Gateway is deployed: `kubectl get deploy -n envoy-gateway-system`
3. GatewayClass exists: `kubectl get gatewayclass eg`
