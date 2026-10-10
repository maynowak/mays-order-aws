# MAYS-INSTALLER-METADATA-PARALLEL-CONSISTENCY-01

## 1. Executive Summary
Installer-Metadatenverwaltung in Mays-Orders-AWS ist partiell konsolidiert. PlanMetadata, DeploymentId und InstallationContext existieren, Workspace-Auswahl wird aber nicht hart validiert. Mays-RIS nutzt ein vergleichbares aber robusteres TerraformRunner-Pattern mit explizitem Workspace-Ensure und Fehlererzeugung. Inkonsistenzen bestehen bei Workspace ↔ State ↔ Plan Verknüpfung.

## 2. Git Baselines
Orders: maynowak/mays-order-aws, main, HEAD 38a9220
RIS: maynowak/Mays-Recruiting-Intelligence-System, main, Commit aktuell, HEAD nicht lokal verifiziert

## 3. Installer Metadata Inventory - Orders

### Installer Identity
- InstallationContext installer/core/context.py:37
- DeploymentContext deployment_identity.py
- DeploymentId
- PlanMetadata, PlanDiscovery, PlanSequenceManager

### Felder
project_name → InstallationContext.project_name → __post_init__ setzt terraform_workspace
environment → InstallationContext.environment
deployment_version → DeploymentContext
development_phase → DeploymentContext
terraform_workspace → InstallationContext.terraform_workspace, TERRAFORM_WORKSPACE env
AWS account/region → AWSExecutionContext
Terraform backend → terraform/backend.tf
Remote State Key → env:/{workspace}/terraform.tfstate
PlanMetadata → aus Plan-Dateiname
PlanSequenceManager → Sequence-Nummer
OwnershipAnalyzer → Tag-basiert

Quelle jeweils: InstallationContext.from_env, __post_init__, TerraformRunner.__init__

Speicherung: .mays-installer/runs/{RUN_ID}/context.json, Plan-Dateien in runs/*/plans/

## 4. Metadata Source-of-Truth Matrix
InstallationContext ist zentrale Quelle, aber Workspace wird in __post_init__ abgeleitet und im Environment gesetzt. TerraformRunner liest TERRAFORM_WORKSPACE erneut. Keine zentrale Validierung Workspace ↔ Project.

## 5. Metadata Persistence and Recovery
Context wird bei jedem Run gespeichert. PlanMetadata wird aus Filename geparst, nicht aus State. Kein Recovery-Mechanismus der Workspace ↔ State konsistent prüft.

## 6. Parallel Installation Lifecycle
Parallelitäts-Upgrade dokumentiert in docs/reports/09-02-PARALLEL-INSTALLER-UPGRADE-EXECUTION_LOG.md, 09-03-FULL-PARALLEL-INSTALLER-AUDIT-EXECUTION_LOG.md, DETAILLIERTER-BERICHT-CICD-INSTALLER-PARALLEL.md
Mechanismen: workspace per project_name, workspace_key_prefix env:, PlanDiscovery per DeploymentId

Unvollständig: Keine harte Verknüpfung Workspace-Existenz vor Init, keine Plan-State-Konsistenzprüfung

## 7. PlanDiscovery Integration
PlanDiscovery findet Pläne via DeploymentId Filter, prüft aber nicht Workspace oder State Key. validate_plan_context prüft nur DeploymentId aus Filename.

## 8. Orders vs RIS Comparison

MECHANISMUS | ORDERS IMPLEMENTATION | RIS IMPLEMENTATION | DIFFERENCE
Project→Workspace | project_name = workspace | workspace_for_project(project_name) verbatim | identisch
Workspace Ensure | TerraformRunner.run_and_get_result select/new, Fehler schlucken | TerraformRunner._ensure_workspace mit explizitem Raise bei Fehler | RIS robuster
Workspace Env | os.environ Mutation in __post_init__ | TERRAFORM_WORKSPACE nur im Child-Process env | RIS sauberer
init & Workspace | workspace wird vor init selektiert | init läuft mit ensure_workspace=False | RIS korrekt getrennt
Plan Discovery | PlanDiscovery per DeploymentId | nicht vorhanden als Klasse, Orchestrator-basiert | unterschiedlich

## 9. Identified Metadata Inconsistencies
- Workspace Selection Fehler werden in Orders ignoriert
- Keine Verifikation dass Plan mit dem korrekten Workspace/State erzeugt wurde
- PlanDiscovery garantiert Metadaten-Identität aber nicht tatsächliche State-Identität
- TerraformRunner hat doppelte run_and_get_result Definitionen

## 10. Relation to Privacy-Test Incident
Workspace existierte nicht, PlanDiscovery fand Plan mit Matching DeploymentId aus vorherigem Run, TerraformRunner wählte falschen Workspace, State von mays-orders wurde benutzt. Metadaten allein hätten den Fehler nicht verhindert.

## 11. Existing Reusable Mechanisms
- RIS TerraformRunner._ensure_workspace mit explizitem Fehler-Handling
- Workspace-Derivation verbatim aus project_name
- BackendConfig mit expliziten Pflichtfeldern

## 12. Minimal Consolidation Recommendation
Workspace Ensure mit hartem Abbruch übernehmen, Terraform init von Workspace-Operation trennen, PlanDiscovery um State-Key-Validierung erweitern.

## 13. Final Status
Overall YELLOW
INSTALLER METADATA: YELLOW
PROJECT IDENTITY: YELLOW
PARALLEL PERSISTENCE: YELLOW
PLAN DISCOVERY: YELLOW
WORKSPACE METADATA: BLOCKED
REMOTE STATE METADATA: YELLOW
