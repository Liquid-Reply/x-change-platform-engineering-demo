# Option 3 Implementation Guide: Helm for Apps, Kustomize for Manifests

## Abstract

This document provides a comprehensive guide for implementing the hybrid approach where ArgoCD Application definitions are managed via Helm while preserving the existing Kustomize-based manifest structure. This approach transforms **verbose JSON patch overlays** into **declarative values files**, dramatically reducing configuration complexity while maintaining operational stability.

### The Core Transformation

```
BEFORE (Kustomize):                      AFTER (Helm):
┌─────────────────────────┐              ┌─────────────────────────┐
│ applications/           │              │ platform-apps/          │
│ ├── base/              │              │ ├── Chart.yaml          │
│ │   ├── kustomization  │   ────►      │ ├── values.yaml         │
│ │   └── 11 app YAMLs   │              │ ├── values-minikube.yaml│
│ └── overlays/          │              │ ├── values-codespaces.yaml
│     ├── minikube/      │              │ └── templates/          │
│     │   └── 97 lines   │              │     └── 11 app YAMLs    │
│     └── codespaces/    │              └─────────────────────────┘
│         └── 73 lines   │
└─────────────────────────┘
          ~400 lines                              ~200 lines
         (with patches)                     (DRY, self-documenting)
```

---

## High-Level Process Overview

### Phase Model

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         IMPLEMENTATION PHASES                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: DESIGN & SCAFFOLDING                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Analyze current Application patterns (3 types identified)           │ │
│  │ • Design Helm chart structure and values schema                       │ │
│  │ • Create Chart.yaml and _helpers.tpl                                  │ │
│  │ • Define values.yaml with all configurable parameters                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    ▼                                         │
│  PHASE 2: TEMPLATE CONVERSION                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Convert each Application YAML to Helm template                      │ │
│  │ • Implement conditional rendering for optional components             │ │
│  │ • Handle multi-source applications specially                          │ │
│  │ • Preserve sync waves and all metadata                                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    ▼                                         │
│  PHASE 3: ENVIRONMENT VALUES                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Create values-minikube.yaml                                         │ │
│  │ • Create values-codespaces.yaml                                       │ │
│  │ • Create values-kind.yaml                                             │ │
│  │ • Document all environment-specific overrides                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    ▼                                         │
│  PHASE 4: ROOT APPLICATION UPDATE                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Update platform-minikube.yml to use Helm source                     │ │
│  │ • Update platform-codespaces.yml                                      │ │
│  │ • Update platform.yml (Kind)                                          │ │
│  │ • Configure valueFiles ordering                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    ▼                                         │
│  PHASE 5: VALIDATION & TESTING                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Local helm template validation                                      │ │
│  │ • ArgoCD diff preview (argocd app diff --local)                       │ │
│  │ • Staging environment deployment                                       │ │
│  │ • Production rollout                                                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    ▼                                         │
│  PHASE 6: CLEANUP & DOCUMENTATION                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ • Archive old applications/ directory                                 │ │
│  │ • Update installer scripts                                            │ │
│  │ • Update CLAUDE.md and documentation                                  │ │
│  │ • Team training                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Analysis

### Current Application Inventory

| Application | Source Type | Needs Repo Patch | External Chart | Sync Wave |
|-------------|-------------|------------------|----------------|-----------|
| namespaces | Single | Yes | No | 1 |
| argoconfig | Single | Yes | No | 1 |
| dynatrace | Single | Yes | No | 2 |
| argo-rollouts | Single | Yes | No | 3 |
| ingress-nginx | Single | Yes | No | 3 |
| workflows | Single (Helm) | No | argo-workflows | 3 |
| cert-manager | Single (Helm) | No | cert-manager | 3 |
| opentelemetry | Multi | Yes (first) | opentelemetry-collector | 3 |
| kubeaudit | Multi | Yes (first) | No | 4 |
| openfeature | Single (Helm) | No | open-feature-operator | 4 |
| backstage | Single | Yes | No | 6 |

### Three Application Patterns Identified

**Pattern A: Local Kustomize Source (6 apps)**
```yaml
spec:
  source:
    repoURL: "https://github.com/..."    # NEEDS TEMPLATING
    targetRevision: main                  # NEEDS TEMPLATING
    path: "gitops/manifests/platform/X"   # Static
```

**Pattern B: External Helm Chart (3 apps)**
```yaml
spec:
  sources:
    - repoURL: 'https://external-helm-repo'  # Static - no templating
      targetRevision: v1.0.0                  # Could be templated for version control
      chart: chart-name
      helm:
        values: |
          key: value
```

**Pattern C: Multi-Source Hybrid (2 apps)**
```yaml
spec:
  sources:
    - repoURL: "https://github.com/..."    # NEEDS TEMPLATING (first source)
      targetRevision: main                  # NEEDS TEMPLATING
      path: "gitops/manifests/platform/X"
    - repoURL: 'https://external-helm-repo'  # Static (second source)
      chart: chart-name
```

### What Gets Templated vs What Stays Static

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TEMPLATING DECISION MATRIX                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ALWAYS TEMPLATE (varies by environment):                                   │
│  ├── global.repoURL          → Git repository URL                          │
│  ├── global.targetRevision   → Branch/tag to deploy                        │
│  └── components.*.enabled    → Optional component toggles                  │
│                                                                             │
│  OPTIONALLY TEMPLATE (for flexibility):                                     │
│  ├── External chart versions → Pin or allow override                       │
│  ├── Helm values blocks      → Environment-specific configs                │
│  └── Sync policies           → Different retry/prune settings              │
│                                                                             │
│  NEVER TEMPLATE (static across environments):                               │
│  ├── Sync wave numbers       → Deployment order is universal               │
│  ├── Destination server      → Always kubernetes.default.svc               │
│  ├── ArgoCD project          → Always 'default'                            │
│  └── External repo URLs      → Same Helm repos everywhere                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Design

### Directory Structure

```
gitops/
├── platform-apps/                    # NEW: Helm chart for Applications
│   ├── Chart.yaml                    # Chart metadata
│   ├── values.yaml                   # Base/default values
│   ├── values-minikube.yaml          # Minikube overrides
│   ├── values-codespaces.yaml        # Codespaces overrides
│   ├── values-kind.yaml              # Kind overrides
│   └── templates/
│       ├── _helpers.tpl              # Template helpers
│       ├── argoconfig.yaml           # ArgoCD config application
│       ├── argo-rollouts.yaml        # Argo Rollouts application
│       ├── argo-workflows.yaml       # Argo Workflows application
│       ├── backstage.yaml            # Backstage application
│       ├── cert-manager.yaml         # Cert-manager application
│       ├── dynatrace.yaml            # Dynatrace application
│       ├── ingress-nginx.yaml        # Ingress-nginx application
│       ├── kubeaudit.yaml            # Kubeaudit application
│       ├── namespaces.yaml           # Namespaces application
│       ├── openfeature.yaml          # OpenFeature application
│       └── opentelemetry.yaml        # OpenTelemetry application
│
├── applications/                     # OLD: Archive after migration
│   └── ... (keep for rollback)
│
├── manifests/                        # UNCHANGED: Keep Kustomize structure
│   ├── base/
│   ├── overlays/
│   └── platform/
│
├── platform.yml                      # UPDATE: Point to Helm chart
├── platform-minikube.yml             # UPDATE: Point to Helm chart
└── platform-codespaces.yml           # UPDATE: Point to Helm chart
```

### Values Schema Design

```yaml
# values.yaml - Complete schema with defaults

# Global settings applied to all local-source applications
global:
  # Repository URL for this deployment
  # Override per environment in values-{env}.yaml
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"

  # Git reference (branch, tag, or commit)
  targetRevision: "main"

  # Common labels applied to all Applications
  labels:
    dt.owner: "platform_team"

  # Default ArgoCD project
  project: "default"

  # Default destination Kubernetes server
  destinationServer: "https://kubernetes.default.svc"

# Sync policy defaults (can be overridden per-component)
syncPolicy:
  automated:
    prune: true
    selfHeal: true
  retry:
    limit: 5
    backoff:
      duration: "5s"
      maxDuration: "3m0s"
      factor: 2

# Component-specific configuration
components:
  # ═══════════════════════════════════════════════════════════════════
  # PATTERN A: Local Kustomize Sources
  # ═══════════════════════════════════════════════════════════════════

  namespaces:
    enabled: true
    syncWave: "1"
    path: "gitops/manifests/platform/namespaces"
    destinationNamespace: "argocd"

  argoconfig:
    enabled: true
    syncWave: "1"
    path: "gitops/manifests/platform/argoconfig"
    destinationNamespace: "argocd"

  dynatrace:
    enabled: true  # Set to false for environments without DT credentials
    syncWave: "2"
    path: "gitops/manifests/platform/dynatrace"
    destinationNamespace: "dynatrace"

  argoRollouts:
    enabled: true
    syncWave: "3"
    path: "gitops/manifests/platform/argo-rollouts"
    destinationNamespace: "argo-rollouts"

  ingressNginx:
    enabled: true
    syncWave: "3"
    path: "gitops/manifests/platform/ingress-nginx"
    destinationNamespace: "ingress-nginx"

  backstage:
    enabled: true
    syncWave: "6"
    path: "gitops/manifests/platform/backstage"
    destinationNamespace: "backstage"

  # ═══════════════════════════════════════════════════════════════════
  # PATTERN B: External Helm Charts (no local repo reference)
  # ═══════════════════════════════════════════════════════════════════

  argoWorkflows:
    enabled: true
    syncWave: "3"
    chart:
      repoURL: "https://argoproj.github.io/argo-helm"
      name: "argo-workflows"
      version: "0.36.1"
    destinationNamespace: "argocd"
    values: |
      server:
        authMode: "server"

  certManager:
    enabled: true
    syncWave: "3"
    chart:
      repoURL: "https://charts.jetstack.io"
      name: "cert-manager"
      version: "v1.14.3"
    destinationNamespace: "cert-manager"
    values: |
      installCRDs: true

  openfeature:
    enabled: true
    syncWave: "4"
    chart:
      repoURL: "https://open-feature.github.io/open-feature-operator"
      name: "open-feature-operator"
      version: "v0.5.4"
    destinationNamespace: "open-feature-operator-system"
    values: ""  # No custom values currently

  # ═══════════════════════════════════════════════════════════════════
  # PATTERN C: Multi-Source (Local Kustomize + External Helm)
  # ═══════════════════════════════════════════════════════════════════

  opentelemetry:
    enabled: true
    syncWave: "3"
    # First source: local Kustomize
    path: "gitops/manifests/platform/opentelemetry"
    # Second source: external Helm chart
    chart:
      repoURL: "https://open-telemetry.github.io/opentelemetry-helm-charts"
      name: "opentelemetry-collector"
      version: "0.71.0"
    destinationNamespace: "opentelemetry"
    values: |
      extraEnvs:
        - name: DT_URL
          valueFrom:
            secretKeyRef:
              name: dt-details
              key: DT_URL
        - name: DT_OTEL_ALL_INGEST_TOKEN
          valueFrom:
            secretKeyRef:
              name: dt-details
              key: DT_OTEL_ALL_INGEST_TOKEN
      mode: daemonset
      presets:
        logsCollection:
          enabled: true
          includeCollectorLogs: true
        kubernetesAttributes:
          enabled: true
        kubeletMetrics:
          enabled: true
      config:
        receivers:
          otlp:
            protocols:
              grpc:
                endpoint: "0.0.0.0:4317"
              http:
                endpoint: "0.0.0.0:4318"
        exporters:
          otlphttp:
            endpoint: "$DT_URL/api/v2/otlp"
            headers:
              Authorization: "Api-Token $DT_OTEL_ALL_INGEST_TOKEN"
        service:
          pipelines:
            traces:
              receivers: [otlp]
              processors: []
              exporters: [otlphttp]
            metrics:
              receivers: [otlp]
              processors: []
              exporters: [otlphttp]
            logs:
              exporters: [otlphttp]

  kubeaudit:
    enabled: true
    syncWave: "4"
    path: "gitops/manifests/platform/kubeaudit"
    destinationNamespace: "kubeaudit"
    # Note: kubeaudit uses multi-source in base but second source
    # was removed, so it's effectively single-source now

  # ═══════════════════════════════════════════════════════════════════
  # OPTIONAL COMPONENTS (disabled by default)
  # ═══════════════════════════════════════════════════════════════════

  keptn:
    enabled: false  # Enable in codespaces overlay
    syncWave: "5"
    chart:
      repoURL: "https://charts.lifecycle.keptn.sh"
      name: "keptn"
      version: "0.3.0"
    destinationNamespace: "keptn"
```

### Environment Values Files

```yaml
# values-minikube.yaml
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "gh_codespace2k8s_opus"  # Feature branch

components:
  dynatrace:
    enabled: false  # No DT credentials in minikube
  keptn:
    enabled: false
```

```yaml
# values-codespaces.yaml
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "main"

components:
  dynatrace:
    enabled: true
  keptn:
    enabled: true
```

```yaml
# values-kind.yaml
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "main"

components:
  dynatrace:
    enabled: true
  keptn:
    enabled: false
```

---

## Template Implementation

### Helper Templates (_helpers.tpl)

```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "platform-apps.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create common labels for all Applications.
*/}}
{{- define "platform-apps.labels" -}}
{{- range $key, $value := .Values.global.labels }}
{{ $key }}: {{ $value | quote }}
{{- end }}
{{- end }}

{{/*
Create the sync policy block.
*/}}
{{- define "platform-apps.syncPolicy" -}}
syncPolicy:
  automated:
    prune: {{ .Values.syncPolicy.automated.prune }}
    selfHeal: {{ .Values.syncPolicy.automated.selfHeal }}
  retry:
    limit: {{ .Values.syncPolicy.retry.limit }}
    backoff:
      duration: {{ .Values.syncPolicy.retry.backoff.duration }}
      maxDuration: {{ .Values.syncPolicy.retry.backoff.maxDuration }}
      factor: {{ .Values.syncPolicy.retry.backoff.factor }}
{{- end }}

{{/*
Create a single-source spec for local Kustomize applications.
*/}}
{{- define "platform-apps.localSource" -}}
source:
  repoURL: {{ .repoURL | quote }}
  targetRevision: {{ .targetRevision | quote }}
  path: {{ .path | quote }}
{{- end }}

{{/*
Create a single-source spec for external Helm chart applications.
*/}}
{{- define "platform-apps.helmSource" -}}
sources:
  - repoURL: {{ .chart.repoURL | quote }}
    targetRevision: {{ .chart.version | quote }}
    chart: {{ .chart.name | quote }}
    {{- if .values }}
    helm:
      values: |
{{ .values | indent 8 }}
    {{- end }}
{{- end }}

{{/*
Create a multi-source spec for hybrid applications.
*/}}
{{- define "platform-apps.multiSource" -}}
sources:
  - repoURL: {{ .repoURL | quote }}
    targetRevision: {{ .targetRevision | quote }}
    path: {{ .path | quote }}
  - repoURL: {{ .chart.repoURL | quote }}
    targetRevision: {{ .chart.version | quote }}
    chart: {{ .chart.name | quote }}
    {{- if .values }}
    helm:
      values: |
{{ .values | indent 8 }}
    {{- end }}
{{- end }}
```

### Pattern A Template: Local Kustomize Source

```yaml
# templates/argoconfig.yaml
{{- if .Values.components.argoconfig.enabled }}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: argoconfig
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: {{ .Values.components.argoconfig.syncWave | quote }}
  labels:
    {{- include "platform-apps.labels" . | nindent 4 }}
spec:
  {{- include "platform-apps.localSource" (dict
      "repoURL" .Values.global.repoURL
      "targetRevision" .Values.global.targetRevision
      "path" .Values.components.argoconfig.path) | nindent 2 }}
  destination:
    namespace: {{ .Values.components.argoconfig.destinationNamespace }}
    server: {{ .Values.global.destinationServer | quote }}
  project: {{ .Values.global.project }}
  {{- include "platform-apps.syncPolicy" . | nindent 2 }}
{{- end }}
```

### Pattern B Template: External Helm Chart

```yaml
# templates/cert-manager.yaml
{{- if .Values.components.certManager.enabled }}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cert-manager
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: {{ .Values.components.certManager.syncWave | quote }}
  labels:
    {{- include "platform-apps.labels" . | nindent 4 }}
spec:
  {{- include "platform-apps.helmSource" (dict
      "chart" .Values.components.certManager.chart
      "values" .Values.components.certManager.values) | nindent 2 }}
  destination:
    namespace: {{ .Values.components.certManager.destinationNamespace }}
    server: {{ .Values.global.destinationServer | quote }}
  project: {{ .Values.global.project }}
  {{- include "platform-apps.syncPolicy" . | nindent 2 }}
{{- end }}
```

### Pattern C Template: Multi-Source Hybrid

```yaml
# templates/opentelemetry.yaml
{{- if .Values.components.opentelemetry.enabled }}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: opentelemetry
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: {{ .Values.components.opentelemetry.syncWave | quote }}
  labels:
    {{- include "platform-apps.labels" . | nindent 4 }}
spec:
  {{- include "platform-apps.multiSource" (dict
      "repoURL" .Values.global.repoURL
      "targetRevision" .Values.global.targetRevision
      "path" .Values.components.opentelemetry.path
      "chart" .Values.components.opentelemetry.chart
      "values" .Values.components.opentelemetry.values) | nindent 2 }}
  destination:
    namespace: {{ .Values.components.opentelemetry.destinationNamespace }}
    server: {{ .Values.global.destinationServer | quote }}
  project: {{ .Values.global.project }}
  {{- include "platform-apps.syncPolicy" . | nindent 2 }}
{{- end }}
```

---

## Root Application Update

### Before (Kustomize)

```yaml
# platform-minikube.yml (current)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform
  namespace: argocd
spec:
  source:
    path: "gitops/applications/overlays/minikube"
    repoURL: "https://github.com/..."
    targetRevision: gh_codespace2k8s_opus
  destination:
    namespace: argocd
    server: 'https://kubernetes.default.svc'
  project: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### After (Helm)

```yaml
# platform-minikube.yml (updated)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform
  namespace: argocd
  labels:
    dt.owner: "platform_team"
spec:
  source:
    path: "gitops/platform-apps"
    repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
    targetRevision: gh_codespace2k8s_opus
    helm:
      valueFiles:
        - values.yaml
        - values-minikube.yaml
  destination:
    namespace: argocd
    server: 'https://kubernetes.default.svc'
  project: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    retry:
      limit: 5
      backoff:
        duration: 5s
        maxDuration: 3m0s
        factor: 2
```

---

## Step-by-Step Implementation Process

### Step 1: Create Chart Scaffolding

```bash
# Create the Helm chart directory structure
mkdir -p gitops/platform-apps/templates

# Create Chart.yaml
cat > gitops/platform-apps/Chart.yaml << 'EOF'
apiVersion: v2
name: platform-apps
description: ArgoCD Applications for the IDP platform components
type: application
version: 1.0.0
appVersion: "1.0.0"
maintainers:
  - name: Platform Team
    email: platform@example.com
EOF
```

### Step 2: Create Base Values File

Create `gitops/platform-apps/values.yaml` with the complete schema shown above.

### Step 3: Create Helper Templates

Create `gitops/platform-apps/templates/_helpers.tpl` with the helper functions shown above.

### Step 4: Convert Each Application

For each of the 11 applications:

1. **Identify the pattern** (A, B, or C)
2. **Create the template file** using the appropriate pattern
3. **Verify with helm template**

```bash
# Test individual template rendering
helm template platform gitops/platform-apps \
  --show-only templates/argoconfig.yaml
```

### Step 5: Create Environment Values Files

```bash
# Create minikube values
cat > gitops/platform-apps/values-minikube.yaml << 'EOF'
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "gh_codespace2k8s_opus"

components:
  dynatrace:
    enabled: false
  keptn:
    enabled: false
EOF

# Create codespaces values
cat > gitops/platform-apps/values-codespaces.yaml << 'EOF'
global:
  repoURL: "https://github.com/Liquid-Reply/x-change-platform-engineering-demo.git"
  targetRevision: "main"

components:
  dynatrace:
    enabled: true
  keptn:
    enabled: true
EOF
```

### Step 6: Validate Complete Rendering

```bash
# Render all templates for minikube
helm template platform gitops/platform-apps \
  -f gitops/platform-apps/values.yaml \
  -f gitops/platform-apps/values-minikube.yaml \
  > /tmp/rendered-minikube.yaml

# Compare with current kustomize output
kustomize build gitops/applications/overlays/minikube \
  > /tmp/current-minikube.yaml

# Diff to verify equivalence
diff /tmp/current-minikube.yaml /tmp/rendered-minikube.yaml
```

### Step 7: Update Root Applications

Update `platform-minikube.yml`, `platform-codespaces.yml`, and `platform.yml` to use the Helm source.

### Step 8: Test in Staging

```bash
# Apply to a test cluster first
kubectl apply -f gitops/platform-minikube.yml

# Watch ArgoCD sync
argocd app get platform --refresh
argocd app sync platform --dry-run
```

### Step 9: Archive Old Structure

```bash
# Move old structure to archive (don't delete yet)
mkdir -p gitops/_archive
mv gitops/applications gitops/_archive/applications-kustomize-backup
```

---

## Validation Checklist

### Pre-Migration Checks

- [ ] All current Application YAMLs documented
- [ ] Kustomize build output captured as baseline
- [ ] ArgoCD Application statuses recorded
- [ ] Backup of current state created

### Template Validation

- [ ] `helm lint gitops/platform-apps` passes
- [ ] `helm template` renders without errors
- [ ] All 11 applications rendered when enabled
- [ ] Conditional disabling works (dynatrace, keptn)
- [ ] Sync waves preserved correctly
- [ ] Labels and annotations correct

### Functional Validation

- [ ] ArgoCD recognizes Helm source type
- [ ] Values files loaded in correct order
- [ ] Applications sync successfully
- [ ] No diff between old and new rendered output
- [ ] ApplicationSet (customer-apps) still works

### Post-Migration Checks

- [ ] All platform components healthy
- [ ] Backstage accessible and functional
- [ ] ArgoCD dashboard shows correct apps
- [ ] Installer script updated (if needed)
- [ ] Documentation updated

---

## Rollback Procedure

If issues arise:

```bash
# 1. Restore old root applications
git checkout HEAD~1 -- gitops/platform-minikube.yml
git checkout HEAD~1 -- gitops/platform-codespaces.yml
git checkout HEAD~1 -- gitops/platform.yml

# 2. Restore applications directory
mv gitops/_archive/applications-kustomize-backup gitops/applications

# 3. Force ArgoCD resync
argocd app sync platform --force

# 4. Verify recovery
argocd app list
```

---

## Installer Script Updates

The `cluster_installer.py` currently performs URL replacements across files. With Helm:

### Before (Kustomize patches)

The installer modifies `gitops/applications/overlays/*/kustomization.yaml` to replace placeholder URLs.

### After (Helm values)

The installer should modify:
1. `gitops/platform-apps/values-{env}.yaml` - Update `global.repoURL` and `global.targetRevision`
2. `gitops/platform-{env}.yml` - Update root Application's `spec.source.repoURL` and `targetRevision`

**Simplified approach**: Since values files are environment-specific anyway, the installer can generate them dynamically or use `--set` overrides in ArgoCD.

---

## Benefits Realized

### Quantitative Improvements

| Metric | Before (Kustomize) | After (Helm) | Improvement |
|--------|-------------------|--------------|-------------|
| Lines of config | ~400 | ~200 | 50% reduction |
| Files to maintain | 16 | 15 | 6% reduction |
| Patches per env | 8-10 | 0 | 100% elimination |
| Config duplication | High | Minimal | Significant |

### Qualitative Improvements

1. **Self-documenting**: Values schema serves as documentation
2. **IDE support**: Helm language server for autocomplete
3. **Testing**: `helm unittest` for template validation
4. **Versioning**: Chart version tracks configuration evolution
5. **Flexibility**: Easy to add new environments
6. **Debugging**: `helm template --debug` for troubleshooting

---

## Appendix: Complete File Listing

### Files to Create

```
gitops/platform-apps/
├── Chart.yaml
├── values.yaml
├── values-minikube.yaml
├── values-codespaces.yaml
├── values-kind.yaml
└── templates/
    ├── _helpers.tpl
    ├── argoconfig.yaml
    ├── argo-rollouts.yaml
    ├── argo-workflows.yaml
    ├── backstage.yaml
    ├── cert-manager.yaml
    ├── dynatrace.yaml
    ├── ingress-nginx.yaml
    ├── kubeaudit.yaml
    ├── namespaces.yaml
    ├── openfeature.yaml
    └── opentelemetry.yaml
```

### Files to Modify

```
gitops/platform.yml
gitops/platform-minikube.yml
gitops/platform-codespaces.yml
cluster_installer.py (URL replacement logic)
```

### Files to Archive

```
gitops/applications/              → gitops/_archive/applications-kustomize-backup/
├── base/
│   ├── kustomization.yaml
│   └── *.yml (11 files)
└── overlays/
    ├── codespaces/
    ├── minikube/
    └── (kind - if exists)
```

---

*Document Version: 1.0*
*Created: 2025-12-15*
*Scope: Option 3 Implementation - Helm for Apps, Kustomize for Manifests*
