import os
from utils import *

DT_TENANT_APPS, DT_TENANT_LIVE = build_dt_urls(dt_env_name=DT_ENV_NAME, dt_env=DT_ENV)

DT_OP_TOKEN = create_dt_api_token(token_name="[devrel demo] DT_OP_TOKEN", scopes=[
    "InstallerDownload",
    "DataExport", 
    "entities.read", 
    "settings.read",
    "settings.write", 
    "activeGateTokenManagement.create"
    ], dt_rw_api_token=DT_RW_API_TOKEN, dt_tenant_live=DT_TENANT_LIVE)

DT_ALL_INGEST_TOKEN = create_dt_api_token(token_name="[devrel demo] DT_ALL_INGEST_TOKEN", scopes=[
    "bizevents.ingest",
    "events.ingest",
    "logs.ingest",
    "metrics.ingest",
    "openTelemetryTrace.ingest",
    "DataExport", 
    "entities.read", 
    "settings.read", 
    "settings.write", 
    "activeGateTokenManagement.create"
], dt_rw_api_token=DT_RW_API_TOKEN, dt_tenant_live=DT_TENANT_LIVE)

output = run_command([
    "kubectl", "-n", "dynatrace", "create", "secret", "generic", "platform-engineering-demo",
    f"--from-literal=apiToken={DT_OP_TOKEN}",
    f"--from-literal=dataIngestToken={DT_ALL_INGEST_TOKEN}"
    ])

print(output)