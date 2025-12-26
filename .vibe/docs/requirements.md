# Requirements Document: Multi-Environment IDP Support

## Executive Summary

This document defines the requirements for the x-change-platform-engineering-demo IDP (Internal Development Platform) to support multiple Kubernetes environments: **GitHub Codespaces**, **minikube**, and **Kind (Kubernetes in Docker)**.

**Implementation Approach**: All environments use `bootstrap.sh` as the single entry point.

---

## REQ-KIND-1: Kind Environment Parity ✅ IMPLEMENTED

**User Story:** As a developer, I want to run the IDP on Kind so that I have a lightweight alternative to minikube that shares the Docker daemon.

**Acceptance Criteria:**

- ✅ WHEN the user runs `./bootstrap.sh kind` THEN the IDP SHALL create a Kind cluster with required port mappings
- ✅ WHEN `platform-kind.yml` exists THEN ArgoCD SHALL use it as the root application
- ✅ WHEN the cluster is created THEN ports 30100, 30105, 80, 4317, 4318 SHALL be mapped to localhost

**Validation:**
```bash
kind get clusters | grep -q "idp"
kubectl get nodes | grep -q "Ready"
curl -s http://localhost:30100  # ArgoCD
curl -s http://localhost:30105  # Backstage
```

---

## REQ-KIND-2: Kind Image Preloading ✅ IMPLEMENTED

**User Story:** As a developer, I want container images preloaded into Kind so that deployments are faster.

**Acceptance Criteria:**

- ✅ WHEN `CLUSTER_TYPE=kind` THEN bootstrap.sh SHALL preload critical images using `kind load docker-image`
- ✅ WHEN images are preloaded THEN ArgoCD, Backstage, and core images SHALL be available locally
- ✅ WHEN preloading fails for an image THEN bootstrap.sh SHALL warn but continue (graceful degradation)

**Implementation:** bootstrap.sh lines 153-177

---

## REQ-ENV-1: Bootstrap Entry Point ✅ IMPLEMENTED

**User Story:** As a developer, I want a single command to set up the IDP for any environment.

**Acceptance Criteria:**

- ✅ WHEN the user runs `./bootstrap.sh minikube` THEN a minikube cluster is created
- ✅ WHEN the user runs `./bootstrap.sh kind` THEN a Kind cluster is created
- ✅ WHEN running in Codespaces THEN `./bootstrap.sh codespaces` works

**Files:**
- `bootstrap.sh` - Main entry point
- `config/minikube.env` - Minikube environment variables
- `config/kind.env` - Kind environment variables
- `config/codespaces.env` - Codespaces environment variables

---

## REQ-ENV-2: Environment-Agnostic Configuration ✅ IMPLEMENTED

**User Story:** As a developer, I want the platform to work with minimal host-specific assumptions.

**Acceptance Criteria:**

- ✅ WHEN deploying to minikube/Kind THEN the IDP SHALL NOT require Codespaces environment variables
- ✅ WHEN deploying locally THEN the IDP SHALL use `localhost` as the base domain
- ✅ WHEN configuration is processed THEN per-environment values files are used

**Implementation:**
- `gitops/platform-apps/values-minikube.yaml`
- `gitops/platform-apps/values-kind.yaml`
- `gitops/platform-apps/values-codespaces.yaml`

---

## REQ-GITOPS-1: ArgoCD GitOps Deployment ✅ IMPLEMENTED

**User Story:** As a platform engineer, I want ArgoCD to manage all platform components via GitOps.

**Acceptance Criteria:**

- ✅ WHEN ArgoCD is deployed THEN sync wave ordering (Waves 1-6) is maintained
- ✅ WHEN a new application is onboarded THEN the ApplicationSet discovery pattern is used
- ✅ WHEN manifests are modified THEN ArgoCD detects and syncs changes automatically

**Root Applications:**
- `gitops/platform-minikube.yml`
- `gitops/platform-kind.yml`
- `gitops/platform-codespaces.yml`

---

## REQ-BACKSTAGE-1: Backstage In-Cluster Deployment ✅ IMPLEMENTED

**User Story:** As a developer, I want Backstage accessible locally for application onboarding.

**Acceptance Criteria:**

- ✅ WHEN Backstage is deployed THEN it runs in the `backstage` namespace
- ✅ WHEN Backstage is running THEN it is accessible via `http://localhost:30105`
- ✅ WHEN the Software Catalog is loaded THEN entities are discovered from git

---

## REQ-OTEL-1: Observability Integration ✅ IMPLEMENTED

**User Story:** As a platform engineer, I want OpenTelemetry integration for observability.

**Acceptance Criteria:**

- ✅ WHEN Dynatrace credentials are provided THEN OneAgent and OTEL collector are configured
- ✅ IF Dynatrace credentials are NOT provided THEN Dynatrace components are skipped gracefully
- ✅ WHEN OTEL collector is deployed THEN traces are accepted on ports 4317/4318

---

## REQ-SECRETS-1: Secrets Management ✅ IMPLEMENTED

**User Story:** As a developer, I want flexible secrets management for development.

**Acceptance Criteria:**

- ✅ WHEN deploying locally THEN gitignored `secrets/{env}.env` files are used
- ✅ WHEN secrets are created THEN they are placed in appropriate namespaces
- ✅ WHEN GitHub token is configured THEN ArgoCD can access private repos

---

## Supported Environments

| Environment | Entry Point | Root Application | Values File |
|-------------|-------------|------------------|-------------|
| Minikube | `./bootstrap.sh minikube` | `platform-minikube.yml` | `values-minikube.yaml` |
| Kind | `./bootstrap.sh kind` | `platform-kind.yml` | `values-kind.yaml` |
| Codespaces | `./bootstrap.sh codespaces` | `platform-codespaces.yml` | `values-codespaces.yaml` |

---

## Port Mappings

| Port | Service | Access |
|------|---------|--------|
| 30100 | ArgoCD | `http://localhost:30100` |
| 30105 | Backstage | `http://localhost:30105` |
| 80 | Ingress/Apps | `http://localhost:80` |
| 4317 | OTEL gRPC | Trace ingestion |
| 4318 | OTEL HTTP | Trace ingestion |

---

## Technical Constraints

| ID | Constraint | Description |
|----|------------|-------------|
| TC-1 | Docker required | For Kind and minikube docker driver |
| TC-2 | 4GB RAM minimum | Platform component requirements |
| TC-3 | kubectl required | Kubernetes CLI |
| TC-4 | Helm required | For ArgoCD application management |

---

## Validation Checkpoints

| Phase | Checkpoint | Command |
|-------|------------|---------|
| 1 | Cluster running | `kubectl get nodes` |
| 2 | ArgoCD accessible | `curl http://localhost:30100` |
| 3 | Backstage accessible | `curl http://localhost:30105` |
| 4 | Apps synced | `kubectl get applications -n argocd` |
| 5 | Secrets exist | `kubectl get secrets -n argocd` |
