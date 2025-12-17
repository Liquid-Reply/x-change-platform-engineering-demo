{{/*
Common labels for all applications
*/}}
{{- define "platform-apps.labels" -}}
dt.owner: "platform_team"
{{- end }}

{{/*
Sync policy block - shared across all applications
*/}}
{{- define "platform-apps.syncPolicy" -}}
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
{{- end }}
