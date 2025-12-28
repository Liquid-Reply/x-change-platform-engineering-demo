#!/bin/bash
#
# IDP Platform Bootstrap Script
# Minimal shell script replacing Python installers
#
# Usage: ./bootstrap.sh [minikube|codespaces|kind]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV="${1:-minikube}"
ARGOCD_VERSION="v2.12.2"
TIMEOUT="300s"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check if cluster exists
cluster_exists() {
  case "${CLUSTER_TYPE:-minikube}" in
    minikube)
      minikube status --profile "${CLUSTER_NAME:-idp}" &>/dev/null
      ;;
    kind)
      kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME:-idp}$"
      ;;
    *)
      return 1
      ;;
  esac
}

# Prompt for existing installation
prompt_existing_installation() {
  echo ""
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}  An existing '${CLUSTER_NAME}' cluster was found!${NC}"
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  echo ""
  echo "What would you like to do?"
  echo ""
  echo "  1) Delete and recreate  - Full reinstall (destroys existing cluster)"
  echo "  2) Keep and refresh     - Keep cluster, re-apply configurations"
  echo "  3) Keep and exit        - Exit without changes"
  echo ""

  while true; do
    read -rp "Select option [1-3]: " choice
    case "${choice}" in
      1)
        echo ""
        log "Will delete existing cluster and perform full installation..."
        INSTALL_MODE="full"
        return 0
        ;;
      2)
        echo ""
        log "Will keep existing cluster and refresh configurations..."
        INSTALL_MODE="refresh"
        return 0
        ;;
      3)
        echo ""
        log "Exiting without changes."
        exit 0
        ;;
      *)
        echo "Invalid option. Please enter 1, 2, or 3."
        ;;
    esac
  done
}

# Validate environment
[[ -f "${SCRIPT_DIR}/config/${ENV}.env" ]] || error "Unknown environment: ${ENV}. Available: minikube, codespaces, kind"

SECRETS_FILE="${SCRIPT_DIR}/secrets/${ENV}.env"
[[ -f "${SECRETS_FILE}" ]] || error "Missing ${SECRETS_FILE}. Copy from secrets/template.env"

log "=== IDP Platform Bootstrap: ${ENV} ==="

# Load environment config and secrets
set -a
source "${SCRIPT_DIR}/config/${ENV}.env"
source "${SECRETS_FILE}"
set +a

# Validate required secrets
[[ -n "${GITHUB_TOKEN:-}" ]] || error "GITHUB_TOKEN not set in ${SECRETS_FILE}"

# Check for existing installation and prompt user
INSTALL_MODE="full"
if cluster_exists; then
  prompt_existing_installation
fi

# 1. Create/reset cluster
if [[ "${INSTALL_MODE}" == "full" ]]; then
  log "Creating ${CLUSTER_TYPE} cluster..."
  case "${CLUSTER_TYPE}" in
    minikube)
      minikube delete --profile "${CLUSTER_NAME}" 2>/dev/null || true
      minikube start --profile "${CLUSTER_NAME}" --cpus=4 --memory=8192 --driver=docker
      minikube profile "${CLUSTER_NAME}"
      kubectl label nodes "${CLUSTER_NAME}" ingress-ready=true --overwrite
      ;;
    kind)
      kind delete cluster --name "${CLUSTER_NAME}" 2>/dev/null || true
      if [[ -f "${SCRIPT_DIR}/.devcontainer/kind-cluster.yml" ]]; then
        kind create cluster --name "${CLUSTER_NAME}" --config "${SCRIPT_DIR}/.devcontainer/kind-cluster.yml" --wait 5m
      else
        kind create cluster --name "${CLUSTER_NAME}" --wait 5m
      fi
      ;;
    *)
      error "Unsupported cluster type: ${CLUSTER_TYPE}"
      ;;
  esac

  # Preload images into cluster for faster deployments
  if [[ "${CLUSTER_TYPE}" == "minikube" ]]; then
    log "Preloading container images into minikube cache..."

    # Define images to preload
    declare -a IMAGES=(
      # Backstage and application templates
      "ghcr.io/katharinasick/backstage-playground:1.2.4"
      "ghcr.io/dynatrace-oss/bizevent-pusher:v1.1.1"
      # ArgoCD core images
      "quay.io/argoproj/argocd:v2.12.2"
      "ghcr.io/dexidp/dex:v2.38.0"
      "redis:7.0.15-alpine"
    )

    # Pull images to host Docker daemon first (if not already present)
    for image in "${IMAGES[@]}"; do
      docker pull "${image}" 2>/dev/null || warn "Failed to pull ${image}"
    done

    # Load images into minikube
    for image in "${IMAGES[@]}"; do
      minikube image load "${image}" --profile "${CLUSTER_NAME}" 2>/dev/null || warn "Failed to load ${image}"
      log "Loaded ${image} into minikube cache..."
    done

  elif [[ "${CLUSTER_TYPE}" == "kind" ]]; then
    log "Preloading container images into Kind cluster..."

    # Define images to preload (same as minikube)
    declare -a IMAGES=(
      # Backstage and application templates
      "ghcr.io/katharinasick/backstage-playground:1.2.4"
      "ghcr.io/dynatrace-oss/bizevent-pusher:v1.1.1"
      # ArgoCD core images
      "quay.io/argoproj/argocd:v2.12.2"
      "ghcr.io/dexidp/dex:v2.38.0"
      "redis:7.0.15-alpine"
    )

    # Pull images to host Docker daemon first (if not already present)
    for image in "${IMAGES[@]}"; do
      docker pull "${image}" 2>/dev/null || warn "Failed to pull ${image}"
    done

    # Load images into Kind cluster
    for image in "${IMAGES[@]}"; do
      kind load docker-image "${image}" --name "${CLUSTER_NAME}" 2>/dev/null || warn "Failed to load ${image}"
      log "Loaded ${image} into Kind cluster..."
    done
  fi
else
  log "Keeping existing ${CLUSTER_TYPE} cluster '${CLUSTER_NAME}'..."
fi

# 2. Create namespaces
log "Creating namespaces..."
for ns in argocd opentelemetry backstage monaco dynatrace; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f -
done

# 3. Create GitHub token secret
log "Creating GitHub token secret..."
kubectl -n argocd create secret generic github-token \
  --from-literal=token="${GITHUB_TOKEN}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 4. Install ArgoCD
log "Installing ArgoCD ${ARGOCD_VERSION}..."
kubectl apply -n argocd -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

# Patch imagePullPolicy to IfNotPresent for faster startup (avoid re-pulling cached images)
log "Patching ArgoCD deployments for faster image pulls..."
for deploy in argocd-dex-server argocd-server argocd-repo-server argocd-applicationset-controller argocd-notifications-controller argocd-redis; do
  kubectl patch deployment "$deploy" -n argocd --type=json -p='[
    {"op": "replace", "path": "/spec/template/spec/containers/0/imagePullPolicy", "value": "IfNotPresent"}
  ]' 2>/dev/null || true
done
# Patch dex-server init container separately
kubectl patch deployment argocd-dex-server -n argocd --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/initContainers/0/imagePullPolicy", "value": "IfNotPresent"}
]' 2>/dev/null || true

# Patch ArgoCD application-controller StatefulSet
log "Patching ArgoCD StatefulSet for faster image pulls..."
kubectl patch statefulset argocd-application-controller -n argocd --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/imagePullPolicy", "value": "IfNotPresent"}
]' 2>/dev/null || true

kubectl wait --for=condition=Available deployment -n argocd --all --timeout="${TIMEOUT}"

# 5. Configure ArgoCD
log "Configuring ArgoCD..."
kubectl apply -n argocd -f "${SCRIPT_DIR}/gitops/manifests/platform/argoconfig/argocd-cm.yml"
kubectl apply -n argocd -f "${SCRIPT_DIR}/gitops/manifests/platform/argoconfig/argocd-no-tls.yml"
kubectl apply -n argocd -f "${SCRIPT_DIR}/gitops/manifests/platform/argoconfig/argocd-nodeport.yml"

# Restart ArgoCD server to pick up config
kubectl -n argocd rollout restart deployment/argocd-server
kubectl -n argocd rollout status deployment/argocd-server --timeout="${TIMEOUT}"

# 6. Apply platform root app
log "Applying platform root app..."
kubectl apply -f "${SCRIPT_DIR}/gitops/platform-${ENV}.yml" 2>/dev/null || \
  kubectl apply -f "${SCRIPT_DIR}/gitops/platform-minikube.yml"

# 7. Wait for ArgoCD secret and generate token
log "Waiting for ArgoCD initialization..."
for i in {1..60}; do
  kubectl -n argocd get secret argocd-initial-admin-secret &>/dev/null && break
  echo "Waiting for argocd-initial-admin-secret... ($i/60)"
  sleep 2
done

# Generate ArgoCD token for Backstage
log "Generating ArgoCD token for Backstage..."
kubectl config set-context --current --namespace=argocd
argocd login argo --core 2>/dev/null || true

ARGOCD_TOKEN=""
for i in {1..60}; do
  if argocd account list 2>/dev/null | grep -q alice; then
    ARGOCD_TOKEN=$(argocd account generate-token --account alice 2>/dev/null) && break
  fi
  echo "Waiting for alice account... ($i/60)"
  sleep 2
done

kubectl config set-context --current --namespace=default

# 8. Create Backstage secrets
log "Creating Backstage secrets..."

# Set Dynatrace URLs with placeholders if DT_ENV_NAME is not configured
if [[ -n "${DT_ENV_NAME:-}" ]]; then
  DT_TENANT_LIVE_URL="https://${DT_ENV_NAME}.${DT_ENV:-live}.dynatrace.com"
  DT_TENANT_APPS_URL="https://${DT_ENV_NAME}.apps.dynatrace.com"
  DT_SSO_TOKEN_URL_VALUE="https://sso.dynatrace.com/sso/oauth2/token"
else
  DT_TENANT_LIVE_URL="https://placeholder.live.dynatrace.com"
  DT_TENANT_APPS_URL="https://placeholder.apps.dynatrace.com"
  DT_SSO_TOKEN_URL_VALUE="https://sso.dynatrace.com/sso/oauth2/token"
fi

kubectl -n backstage create secret generic backstage-secrets \
  --from-literal=BASE_DOMAIN="${BASE_DOMAIN}" \
  --from-literal=BACKSTAGE_PORT_NUMBER="${BACKSTAGE_PORT}" \
  --from-literal=ARGOCD_PORT_NUMBER="${ARGOCD_PORT}" \
  --from-literal=ARGOCD_TOKEN="${ARGOCD_TOKEN}" \
  --from-literal=GITHUB_TOKEN="${GITHUB_TOKEN}" \
  --from-literal=GITHUB_ORG="$(git -C "${SCRIPT_DIR}" remote get-url origin | sed -E 's|.*github.com[:/]([^/]+)/.*|\1|')" \
  --from-literal=GITHUB_REPO="$(git -C "${SCRIPT_DIR}" remote get-url origin | sed -E 's|.*github.com[:/][^/]+/([^/.]+).*|\1|')" \
  --from-literal=GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" \
  --from-literal=DT_TENANT_NAME="${DT_ENV_NAME:-placeholder}" \
  --from-literal=DT_TENANT_LIVE="${DT_TENANT_LIVE_URL}" \
  --from-literal=DT_TENANT_APPS="${DT_TENANT_APPS_URL}" \
  --from-literal=DT_SSO_TOKEN_URL="${DT_SSO_TOKEN_URL_VALUE}" \
  --from-literal=DT_OAUTH_CLIENT_ID="${DT_OAUTH_CLIENT_ID:-placeholder}" \
  --from-literal=DT_OAUTH_CLIENT_SECRET="${DT_OAUTH_CLIENT_SECRET:-placeholder}" \
  --from-literal=DT_OAUTH_ACCOUNT_URN="${DT_OAUTH_ACCOUNT_URN:-placeholder}" \
  --from-literal=DT_ALL_INGEST_TOKEN="${DT_ALL_INGEST_TOKEN:-placeholder}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 9. Optional: Dynatrace setup
if [[ -n "${DT_ENV_NAME:-}" ]] && [[ -n "${DT_RW_API_TOKEN:-}" ]]; then
  log "Setting up Dynatrace integration..."
  python3 "${SCRIPT_DIR}/scripts/dynatrace.py" --env "${ENV}" --create-tokens || warn "Dynatrace setup failed (optional)"
else
  log "Skipping Dynatrace setup (DT_ENV_NAME or DT_RW_API_TOKEN not set)"
fi

# 10. Wait for Backstage and restart
log "Waiting for Backstage deployment..."
for i in {1..120}; do
  kubectl -n backstage get deployment backstage &>/dev/null && break
  echo "Waiting for backstage deployment... ($i/120)"
  sleep 2
done

# Patch Backstage deployment for faster image pulls
log "Patching Backstage deployment for faster image pulls..."
kubectl patch deployment backstage -n backstage --type=json -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/imagePullPolicy", "value": "IfNotPresent"}
]' 2>/dev/null || true

kubectl -n backstage rollout restart deployment/backstage 2>/dev/null || true
kubectl -n backstage rollout status deployment/backstage --timeout="${TIMEOUT}" 2>/dev/null || true

# Done
log "=== Bootstrap complete ==="
echo ""
echo "ArgoCD:    http://localhost:${ARGOCD_PORT}"
echo "Backstage: http://localhost:${BACKSTAGE_PORT}"
echo ""
echo "ArgoCD password:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo ""
