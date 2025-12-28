# Cloud Provider Adaptation Guide

**Analysis Date:** 2025-12-27
**Target Platforms:** AWS EKS, Azure AKS, Google GKE

---

## Executive Summary

The X-Change Platform Engineering Demo is designed for local Kubernetes environments (minikube, Kind, Codespaces). This guide outlines the modifications needed to deploy on managed Kubernetes services.

**Overall Adaptation Complexity:** Medium
**Estimated Effort:** 2-4 days for complete cloud migration

---

## 1. Current Architecture Constraints

### 1.1 Local-Specific Dependencies

| Dependency | Current Value | Cloud Requirement |
|------------|---------------|-------------------|
| Service Type | NodePort | LoadBalancer or Ingress |
| Port Mapping | Fixed ports (30100, 30105) | Dynamic or ALB/NLB |
| Node Labels | `ingress-ready=true` | Not applicable |
| Cluster Creation | minikube/kind commands | Cloud CLI (eksctl, az, gcloud) |
| Image Preload | Docker load | Not needed (registry access) |

### 1.2 Files Requiring Modification

| File | Changes Needed | Complexity |
|------|----------------|------------|
| `bootstrap.sh` | Cloud-specific cluster creation | High |
| `values.yaml` | Service type parameterization | Low |
| `values-{cloud}.yaml` | Cloud-specific overrides | Medium |
| `.devcontainer/kind-cluster.yml` | Not applicable for cloud | N/A |
| `config/{cloud}.env` | New cloud config files | Low |

---

## 2. AWS EKS Adaptation

### 2.1 Prerequisites

```bash
# Required tools
brew install eksctl aws-cli kubectl helm
aws configure  # Set up AWS credentials
```

### 2.2 Cluster Creation

**New file: `bootstrap-eks.sh`**

```bash
#!/bin/bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-idp-demo}"
REGION="${AWS_REGION:-us-west-2}"
NODE_TYPE="${NODE_TYPE:-t3.large}"
NODE_COUNT="${NODE_COUNT:-3}"

# Create EKS cluster
eksctl create cluster \
  --name "${CLUSTER_NAME}" \
  --region "${REGION}" \
  --node-type "${NODE_TYPE}" \
  --nodes "${NODE_COUNT}" \
  --managed \
  --with-oidc \
  --alb-ingress-access

# Install AWS Load Balancer Controller (for Gateway API)
eksctl create iamserviceaccount \
  --cluster="${CLUSTER_NAME}" \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --attach-policy-arn=arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy \
  --approve

# Continue with standard bootstrap...
```

### 2.3 New Configuration File

**New file: `config/eks.env`**

```bash
# EKS environment configuration
CLUSTER_TYPE=eks
CLUSTER_NAME=idp-demo
BASE_DOMAIN=eks.example.com

# EKS-specific settings
AWS_REGION=us-west-2
SERVICE_TYPE=LoadBalancer

# Ports (not used with LoadBalancer, kept for compatibility)
ARGOCD_PORT=443
BACKSTAGE_PORT=443
DEMO_APP_PORT=80

# Git repository
REPO_URL=https://github.com/your-org/x-change-platform-engineering-demo.git
TARGET_REVISION=main
```

### 2.4 Helm Values Override

**New file: `gitops/platform-apps/values-eks.yaml`**

```yaml
# AWS EKS environment overrides
global:
  targetRevision: "main"
  serviceType: LoadBalancer

# EKS-specific annotations for load balancers
annotations:
  service.beta.kubernetes.io/aws-load-balancer-type: nlb
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
```

### 2.5 Gateway API on EKS

Envoy Gateway works on EKS with AWS Load Balancer Controller:

```yaml
# Gateway modification for EKS
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: platform-gateway
  namespace: envoy-gateway-system
  annotations:
    # AWS NLB integration
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  gatewayClassName: eg
  listeners:
  - name: http
    protocol: HTTP
    port: 80
  - name: https
    protocol: HTTPS
    port: 443
    tls:
      certificateRefs:
      - name: platform-tls
```

---

## 3. Azure AKS Adaptation

### 3.1 Prerequisites

```bash
# Required tools
brew install azure-cli kubectl helm
az login
az account set --subscription <subscription-id>
```

### 3.2 Cluster Creation

**New file: `bootstrap-aks.sh`**

```bash
#!/bin/bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-idp-demo}"
RESOURCE_GROUP="${RESOURCE_GROUP:-idp-demo-rg}"
LOCATION="${LOCATION:-eastus}"
NODE_COUNT="${NODE_COUNT:-3}"
NODE_SIZE="${NODE_SIZE:-Standard_D2s_v3}"

# Create resource group
az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}"

# Create AKS cluster
az aks create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${CLUSTER_NAME}" \
  --node-count "${NODE_COUNT}" \
  --node-vm-size "${NODE_SIZE}" \
  --enable-managed-identity \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group "${RESOURCE_GROUP}" --name "${CLUSTER_NAME}"

# Continue with standard bootstrap...
```

### 3.3 New Configuration File

**New file: `config/aks.env`**

```bash
# AKS environment configuration
CLUSTER_TYPE=aks
CLUSTER_NAME=idp-demo
RESOURCE_GROUP=idp-demo-rg
BASE_DOMAIN=aks.example.com

# AKS-specific settings
LOCATION=eastus
SERVICE_TYPE=LoadBalancer

# Ports (not used with LoadBalancer)
ARGOCD_PORT=443
BACKSTAGE_PORT=443
DEMO_APP_PORT=80

# Git repository
REPO_URL=https://github.com/your-org/x-change-platform-engineering-demo.git
TARGET_REVISION=main
```

### 3.4 Helm Values Override

**New file: `gitops/platform-apps/values-aks.yaml`**

```yaml
# Azure AKS environment overrides
global:
  targetRevision: "main"
  serviceType: LoadBalancer

# AKS-specific annotations
annotations:
  service.beta.kubernetes.io/azure-load-balancer-internal: "false"
```

---

## 4. Google GKE Adaptation

### 4.1 Prerequisites

```bash
# Required tools
brew install --cask google-cloud-sdk
gcloud init
gcloud auth login
```

### 4.2 Cluster Creation

**New file: `bootstrap-gke.sh`**

```bash
#!/bin/bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-idp-demo}"
PROJECT="${GCP_PROJECT:-my-project}"
ZONE="${GCP_ZONE:-us-central1-a}"
NODE_COUNT="${NODE_COUNT:-3}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-4}"

# Create GKE cluster
gcloud container clusters create "${CLUSTER_NAME}" \
  --project="${PROJECT}" \
  --zone="${ZONE}" \
  --num-nodes="${NODE_COUNT}" \
  --machine-type="${MACHINE_TYPE}" \
  --enable-ip-alias \
  --workload-pool="${PROJECT}.svc.id.goog"

# Get credentials
gcloud container clusters get-credentials "${CLUSTER_NAME}" \
  --project="${PROJECT}" \
  --zone="${ZONE}"

# Continue with standard bootstrap...
```

---

## 5. Required Helm Chart Modifications

### 5.1 Service Type Parameterization

**Modify: `gitops/platform-apps/values.yaml`**

```yaml
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "main"
  project: "default"
  server: "https://kubernetes.default.svc"

  # NEW: Cloud-agnostic settings
  serviceType: NodePort  # Override to LoadBalancer for cloud

  # NEW: Cloud provider (local, eks, aks, gke)
  cloudProvider: local
```

### 5.2 Service Template Update

Backstage service could be templated to support different service types:

```yaml
# gitops/manifests/platform/backstage/service.yml (or Helm template)
apiVersion: v1
kind: Service
metadata:
  name: backstage
  namespace: backstage
spec:
  type: {{ .Values.global.serviceType | default "NodePort" }}
  ports:
  - port: 7007
    targetPort: 7007
    {{- if eq .Values.global.serviceType "NodePort" }}
    nodePort: 30105
    {{- end }}
  selector:
    app: backstage
```

---

## 6. Secrets Management for Cloud

### 6.1 Current Approach
- Secrets stored in `secrets/{env}.env` files
- Loaded by bootstrap.sh and created as Kubernetes secrets

### 6.2 Cloud-Native Secrets Recommendations

#### AWS EKS: Secrets Manager Integration

```yaml
# Install External Secrets Operator
applications:
  external-secrets:
    enabled: true
    syncWave: "2"
    sourceType: "helm"
    helmRepo: "https://charts.external-secrets.io"
    chart: "external-secrets"
    chartVersion: "0.9.0"
    namespace: "external-secrets"
```

#### Azure AKS: Key Vault Integration

```yaml
# Use CSI driver for Azure Key Vault
applications:
  azure-keyvault-csi:
    enabled: true
    syncWave: "2"
    sourceType: "helm"
    helmRepo: "https://azure.github.io/secrets-store-csi-driver-provider-azure/charts"
    chart: "csi-secrets-store-provider-azure"
    chartVersion: "1.5.0"
    namespace: "kube-system"
```

---

## 7. Networking Considerations

### 7.1 Gateway API Compatibility Matrix

| Cloud | Gateway API Support | Notes |
|-------|---------------------|-------|
| EKS | Yes (with Envoy Gateway) | Works with AWS LB Controller |
| AKS | Yes | Native support available |
| GKE | Yes (beta) | GKE Gateway Controller available |

### 7.2 DNS Configuration

For cloud deployments, DNS should be configured:

```bash
# Example: AWS Route53
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456789 \
  --change-batch file://dns-records.json
```

---

## 8. Migration Checklist

### 8.1 Pre-Migration

- [ ] Choose cloud provider (EKS/AKS/GKE)
- [ ] Set up cloud CLI and credentials
- [ ] Create new config file (config/{cloud}.env)
- [ ] Create new values file (values-{cloud}.yaml)
- [ ] Set up secrets management strategy

### 8.2 Cluster Setup

- [ ] Run cloud-specific bootstrap script
- [ ] Verify cluster creation
- [ ] Install ArgoCD
- [ ] Configure DNS (optional)

### 8.3 Application Deployment

- [ ] Apply root Application (platform-{cloud}.yml)
- [ ] Wait for sync completion
- [ ] Verify all applications healthy
- [ ] Test external access

### 8.4 Post-Migration

- [ ] Set up monitoring (CloudWatch/Azure Monitor/Cloud Monitoring)
- [ ] Configure alerting
- [ ] Document cloud-specific runbooks
- [ ] Update CI/CD for cloud deployment

---

## 9. Cost Considerations

| Component | Local | EKS | AKS | GKE |
|-----------|-------|-----|-----|-----|
| Control Plane | Free | $0.10/hr | Free | $0.10/hr |
| Nodes (3x) | Free | ~$0.20/hr | ~$0.15/hr | ~$0.15/hr |
| Load Balancer | N/A | ~$0.02/hr | ~$0.02/hr | ~$0.02/hr |
| Data Transfer | Free | $0.09/GB | $0.05/GB | $0.12/GB |

**Estimated Monthly Cost (3-node cluster):** $200-400/month

---

## 10. Summary

The X-Change Platform Engineering Demo can be adapted for cloud deployment with moderate effort. Key changes:

1. **Cluster creation:** Replace minikube/kind with cloud CLI
2. **Service types:** Parameterize for LoadBalancer
3. **Secrets:** Integrate cloud-native secrets management
4. **Networking:** Gateway API works across all major clouds
5. **Configuration:** Add cloud-specific config and values files

The modular Helm-based architecture makes these adaptations straightforward, as most changes are configuration-level rather than architectural.
