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

# Validate environment
[[ -f "${SCRIPT_DIR}/config/${ENV}.env" ]] || error "Unknown environment: ${ENV}. Available: minikube, codespaces, kind"
[[ -f "${SCRIPT_DIR}/secrets/github-token" ]] || error "Missing secrets/github-token. See secrets/README.md"

log "=== IDP Platform Bootstrap: ${ENV} ==="

# Load environment config
set -a
source "${SCRIPT_DIR}/config/${ENV}.env"
set +a

# 1. Create/reset cluster
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

# 2. Create namespaces
log "Creating namespaces..."
for ns in argocd opentelemetry backstage monaco dynatrace; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f -
done

# 3. Create GitHub token secret
log "Creating GitHub token secret..."
GITHUB_TOKEN=$(cat "${SCRIPT_DIR}/secrets/github-token")
kubectl -n argocd create secret generic github-token \
  --from-literal=token="${GITHUB_TOKEN}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 4. Install ArgoCD
log "Installing ArgoCD ${ARGOCD_VERSION}..."
kubectl apply -n argocd -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
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
kubectl -n backstage create secret generic backstage-secrets \
  --from-literal=BASE_DOMAIN="${BASE_DOMAIN}" \
  --from-literal=BACKSTAGE_PORT_NUMBER="${BACKSTAGE_PORT}" \
  --from-literal=ARGOCD_PORT_NUMBER="${ARGOCD_PORT}" \
  --from-literal=ARGOCD_TOKEN="${ARGOCD_TOKEN}" \
  --from-literal=GITHUB_TOKEN="${GITHUB_TOKEN}" \
  --from-literal=GITHUB_ORG="$(echo "${REPO_URL}" | sed -E 's|https://github.com/([^/]+)/.*|\1|')" \
  --from-literal=GITHUB_REPO="$(echo "${REPO_URL}" | sed -E 's|https://github.com/[^/]+/([^/.]+).*|\1|')" \
  --from-literal=GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" \
  --from-literal=DT_TENANT_NAME="${DT_ENV_NAME:-placeholder}" \
  --from-literal=DT_TENANT_LIVE="${DT_ENV_NAME:+https://${DT_ENV_NAME}.${DT_ENV:-live}.dynatrace.com}" \
  --from-literal=DT_TENANT_APPS="${DT_ENV_NAME:+https://${DT_ENV_NAME}.apps.dynatrace.com}" \
  --from-literal=DT_SSO_TOKEN_URL="${DT_ENV_NAME:+https://sso.dynatrace.com/sso/oauth2/token}" \
  --from-literal=DT_OAUTH_CLIENT_ID="${DT_OAUTH_CLIENT_ID:-placeholder}" \
  --from-literal=DT_OAUTH_CLIENT_SECRET="${DT_OAUTH_CLIENT_SECRET:-placeholder}" \
  --from-literal=DT_OAUTH_ACCOUNT_URN="${DT_OAUTH_ACCOUNT_URN:-placeholder}" \
  --from-literal=DT_ALL_INGEST_TOKEN="${DT_ALL_INGEST_TOKEN:-placeholder}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 9. Optional: Dynatrace setup
if [[ -f "${SCRIPT_DIR}/secrets/dt-credentials.env" ]]; then
  log "Setting up Dynatrace integration..."
  python3 "${SCRIPT_DIR}/scripts/dynatrace.py" --env "${ENV}" --create-tokens || warn "Dynatrace setup failed (optional)"
fi

# 10. Wait for Backstage and restart
log "Waiting for Backstage deployment..."
for i in {1..120}; do
  kubectl -n backstage get deployment backstage &>/dev/null && break
  echo "Waiting for backstage deployment... ($i/120)"
  sleep 2
done

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
