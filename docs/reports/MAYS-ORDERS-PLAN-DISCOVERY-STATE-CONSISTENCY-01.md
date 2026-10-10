# MAYS-ORDERS-PLAN-DISCOVERY-STATE-CONSISTENCY-01

## 1. Git Baseline
Repo: maynowak/mays-order-aws
Branch: main
Git HEAD: 521a1ee
Working Tree: clean nach Push

## 2. Komponenten-Inventar

### PlanDiscovery
File: installer/core/deployment_identity.py
Class: PlanDiscovery
Init: __init__(base_dir: Path = Path(".mays-installer/runs"))
Methods:
- find_plans(deployment_id, operation, version?, development_phase?): List[PlanIdentity]
- find_latest_plan(...): Optional[PlanIdentity]
- validate_plan_context(plan_path, expected_deployment_id): tuple[bool,str]

Suchverzeichnis: .mays-installer/runs/*/plans/
Dateinamenkonvention: PlanMetadata.parse_filename
Filter:
- DeploymentId
- Operation
- Version
- DevelopmentPhase
Sequence-Auswahl: sort by metadata.sequence_number descending

Aufrufstellen:
- installer/cli/main.py:597,599-605
- installer/cli/main.py:622-624
- installer/cli/main.py:665,876,919
- installer/cli/gui.py:19

### InstallationContext
File: installer/core/context.py:37
__post_init__:81
Workspace Auto-Select:
if not terraform_workspace or terraform_workspace=="default":
    terraform_workspace = project_name
os.environ["TERRAFORM_WORKSPACE"] = terraform_workspace

from_env:107 liest PROJECT_NAME, TERRAFORM_WORKSPACE

### TerraformRunner
File: installer/terraform/runner.py:94
__init__: workspace aus os.environ["TERRAFORM_WORKSPACE"] oder Parameter
run_and_get_result:460-487
Workspace Selection vor jedem Terraform Command:
terraform workspace select <workspace>
if returncode !=0 → terraform workspace new <workspace>
Returncode Prüfung: select Fehler führt zu new, kein expliziter Abort bei Fehler

### Remote State Lifecycle
File: installer/core/remote_state_lifecycle.py:43
RemoteStateLifecycleDetector
detect() – nur Lesend, keine Migration

Backend Konfiguration:
terraform/backend.tf
bucket: mays-orders-tfstate-central-240571105849
key: terraform.tfstate
workspace_key_prefix: env:
Erwarteter State Key für Testprojekt: env:/mays-orders-privacy-test/terraform.tfstate

## 3. Tatsächlicher Installer-Kontrollfluss

Aus Code Analyse:

InstallationContext.from_env() → __post_init__ setzt workspace aus project_name und exportiert TERRAFORM_WORKSPACE
Validation → AWSExecutionContext validiert
TerraformRunner.__init__ liest TERRAFORM_WORKSPACE
TerraformRunner.run_and_get_result → workspace select/new vor jedem Command
terraform init → terraform validate → terraform plan
PlanMetadata wird aus Plan-Filename geparst
PlanDiscovery.find_latest_plan wird für Deploy verwendet
PlanDiscovery.validate_plan_context prüft DeploymentId Übereinstimmung
Policy Gate → Plan Analyse → Approval → Apply

Hypothese Abweichung: Workspace Selection erfolgt in run_and_get_result, das bei init/plan aufgerufen wird. Wenn Workspace nicht existiert, wird er erstellt. Fehler werden nicht hart abgebrochen.

## 4. PlanDiscovery Aufrufstellen

installer/cli/main.py
- _deploy: auto-detect latest plan via PlanDiscovery.find_latest_plan
- _deploy: validate_plan_context vor Kopieren
- _destroy: find_latest_plan
- _plan: keine Discovery
- GUI: Import nur

## 5. Workspace Lifecycle

Festlegung:
InstallationContext.__post_init__ 81-90 setzt terraform_workspace = project_name wenn default
InstallationContext.from_env liest PROJECT_NAME

Erstellung:
TerraformRunner.run_and_get_result 468-485
terraform workspace select → wenn Fehler → terraform workspace new
Kein expliziter Returncode Check nach new

Auswahl:
TerraformRunner.run_and_get_result führt select/new vor jedem Terraform Command aus

Bestätigung:
Kein separater Check ob workspace tatsächlich aktiv ist nach select/new
Terraform workspace list wird nicht verifiziert

Fehlerbehandlung:
Ausnahmen werden mit pass schlucken, kein Abbruch
Returncode Prüfung fehlt für workspace new

Plan mit falschem Workspace:
Ja möglich wenn workspace select/new fehlschlägt und kein Abbruch erfolgt

## 6. Remote State Consistency

Verbindung:
Terraform Workspace ↔ S3 State Key via workspace_key_prefix env:
DeploymentId kommt aus InstallationContext.get_deployment_context → account_id, project, environment

Plan Metadata enthält DeploymentId, version, phase, operation, sequence

PlanDiscovery validiert nur DeploymentId aus Filename, nicht:
- tatsächlicher Workspace
- tatsächlicher State-Key
- dass Plan mit dem State erzeugt wurde

Plan kann gültige Deployment-Metadaten haben und trotzdem mit falschem State erzeugt worden sein.

## 7. Plan Integrity

Mechanismen vorhanden:
- Plan Metadata aus Filename
- Deployment Identity Filter
- PlanDiscovery.validate_plan_context
- PlanSequenceManager
- Policy Gate evaluate_plan_safety

Nicht garantiert:
- Plan wurde mit dem richtigen Terraform-State erzeugt
- Plan verändert nur Ressourcen des Projekts
- Workspace ↔ State ↔ DeploymentId Konsistenz

A. Plan gehört laut Metadaten zum Projekt: JA
B. Plan wurde tatsächlich mit dem richtigen Terraform-State erzeugt: NEIN, nicht verifiziert
C. Plan verändert ausschließlich Ressourcen des Projekts: NEIN, nicht verifiziert

## 8. Regression Analyse

Bekannter Fehler:
Ziel-Workspace mays-orders-privacy-test existierte nicht bei Plan-Erzeugung.
TerraformRunner hat workspace select/new vor init ausgeführt, aber select fehlgeschlagen und new nicht erfolgreich verifiziert.
Terraform verwendete bestehenden Workspace mays-orders.
State env:/mays-orders/terraform.tfstate wurde verwendet.
Cognito Ressourcen mit IDs eu-central-1_xhjl0PxEH und 5tac9c0uh5q6d5tjdse94jpf8s wurden als UPDATE erkannt.

Ursache:
- Workspace-Erstellung fehlgeschlagen oder zu spät
- Kein harter Abbruch bei workspace select/new Fehler
- Keine Verifizierung des aktiven Workspaces nach Auswahl
- PlanDiscovery prüft nur Metadaten, nicht Workspace/State Konsistenz

Vorhandene Funktion die hätte verhindern müssen:
Kein harter Gate für Workspace-Existenz vor init

## 9. Tests

Unit Tests existieren, keine Ausführung ohne Risiko.

## 10. Befunde

PlanDiscovery:
- Implementiert, aber prüft nur Filename Metadaten
- Kein Workspace/State Tie

Workspace Selection:
- Wird in run_and_get_result durchgeführt
- Fehler werden nicht hart abgebrochen
- Keine Bestätigung der tatsächlichen Auswahl

Remote State Consistency:
- Workspace Key Prefix korrekt konfiguriert
- Keine Verknüpfung zwischen Plan Metadata und State Key

Plan Metadata:
- Vollständig aus Filename
- Keine Integritätsprüfung gegen State

Plan Ownership:
- DeploymentId Filter vorhanden
- Kein Ownership Check gegen AWS Ressourcen Tags

## 11. Status Bewertung

PLAN DISCOVERY: YELLOW – existiert, aber prüft nicht State/Workspace Konsistenz
WORKSPACE SELECTION: BLOCKED – Fehler werden ignoriert, kein Abbruch
REMOTE STATE CONSISTENCY: YELLOW – Konfiguration ok, Verifikation fehlt
PLAN METADATA: GREEN – vollständig implementiert
PLAN OWNERSHIP: YELLOW – DeploymentId Filter vorhanden, aber keine Ressourcen-Ownership Verifikation

Overall: YELLOW

## 12. Minimal notwendige Empfehlungen

- Workspace select/new mit Returncode Prüfung und harter Abbruch bei Fehler
- Workspace Bestätigung nach Auswahl via `terraform workspace show`
- PlanDiscovery erweitern um Workspace/State-Key Validierung
- Plan Integrity um State-Key Verifikation ergänzen

Keine Codeänderungen in diesem Auftrag.
