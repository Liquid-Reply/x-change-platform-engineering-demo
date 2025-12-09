# Functional Tests

This directory contains functional tests for the IDP platform using [Chainsaw](https://kyverno.github.io/chainsaw/), a declarative Kubernetes end-to-end testing framework.

## Prerequisites

1. **Install Chainsaw**:
   ```bash
   # Using Go
   go install github.com/kyverno/chainsaw@latest

   # Using Homebrew (macOS)
   brew tap kyverno/chainsaw https://github.com/kyverno/chainsaw

   # Using Krew (kubectl plugin manager)
   kubectl krew install chainsaw
   ```

2. **Running cluster**: Tests require a running Kubernetes cluster with the IDP platform deployed.

3. **kubectl configured**: Ensure kubectl is configured to access your cluster.

## Test Categories

| Test | Description | Duration |
|------|-------------|----------|
| `01-platform-namespaces` | Verifies all required namespaces exist | ~5s |
| `02-argocd-health` | Checks ArgoCD deployments are healthy | ~10s |
| `03-argocd-apps-sync` | Validates ArgoCD applications are synced | ~30s |
| `04-backstage-health` | Verifies Backstage deployment is running | ~10s |
| `05-ingress-controller` | Checks ingress-nginx is operational | ~5s |
| `06-secrets-present` | Validates required secrets exist | ~5s |
| `07-kustomize-build` | Tests Kustomize overlays build correctly | ~30s |

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

1. Create a new directory: `08-your-test-name/`
2. Create `chainsaw-test.yaml` with your test definition
3. Use `assert` for declarative resource checks
4. Use `script` for complex validation logic
5. Run locally to validate before committing

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
