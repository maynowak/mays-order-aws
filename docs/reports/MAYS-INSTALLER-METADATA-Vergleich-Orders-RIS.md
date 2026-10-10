# MAYS-INSTALLER-METADATA-Vergleich Orders vs RIS

## Orders Installer Metadaten
InstallationContext installer/core/context.py
- project_name → terraform_workspace
- DeploymentId aus InstallationContext
- PlanMetadata aus Filename
- PlanDiscovery findet Pläne via DeploymentId
- TerraformRunner._ensure_workspace implementiert mit select/new/verify
- PlanSequenceManager für Sequenznummern

## RIS Installer Metadaten
Installer Struktur: installer/identity_context.py, installer/terraform_runner.py, installer/orchestrator.py, installer/ris.py
- identity_context.py: AwsExecutionContext mit profile/region/account_id/identity_arn
- terraform_runner.py: workspace_for_project, BackendConfig, TerraformRunner mit _ensure_workspace
- workspace derivation verbatim aus project_name
- TERRAFORM_WORKSPACE nur im Child-Process env
- init läuft ohne Workspace Operation
- BackendConfig mit expliziten Pflichtfeldern
- Keine PlanDiscovery Klasse, Orchestrator-basiert

## Vergleich

MECHANISMUS | ORDERS | RIS
Project→Workspace | project_name = workspace via __post_init__ | workspace_for_project(project_name) verbatim
Workspace Ensure | _ensure_workspace select/new/verify mit hartem Fehler | _ensure_workspace select/new/verify mit hartem Fehler
Workspace Env | os.environ Mutation in __post_init__ | TERRAFORM_WORKSPACE nur im Child-Process env
init & Workspace | Workspace Ensure vor init verhindert | init läuft mit ensure_workspace=False
Backend Config | Backend in terraform/backend.tf statisch | BackendConfig Objekt mit Pflichtfeldern
Plan Discovery | PlanDiscovery Klasse mit DeploymentId Filter | Orchestrator-basiert, keine separate Discovery Klasse
Metadata Persistenz | .mays-installer/runs/*/context.json + Plan Dateien | Artefakte via artifacts.py
Policy Gate | evaluate_plan_safety vorhanden | Nicht vergleichbar dokumentiert

## Fazit
RIS hat sauberere Trennung von Workspace und init, keine os.environ Mutation, BackendConfig explizit. Orders hat PlanDiscovery und DeploymentId Metadatenmodell, welches RIS nicht in dieser Form hat.

## Empfehlung
Workspace Ensure Pattern aus RIS übernehmen, os.environ Mutation vermeiden, BackendConfig Pattern prüfen.
