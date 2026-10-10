# MAYS-ORDERS-MULTIPROJECT-CLI-FIX-AND-TEST-01

## Root Cause
InstallationContext.__post_init__ leitete Terraform-Workspace aus project_name ab, bevor CLI-Argument project_name überschrieben wurde.

## Fix
installer/cli/main.py _create_context angepasst:
- Workspace nach Setzen von project_name erneut auf project_name setzen
- TERRAFORM_WORKSPACE Umgebungsvariable synchron aktualisiert

Keine Änderung an Multiprojekt-Architektur.

## Regression Tests
A. mays-orders -> eigener Workspace: PASS
B. mays-orders-privacy-test -> eigener Workspace: PASS
C. Unterschiedliche Projektnamen -> unterschiedliche Workspaces: PASS
D. AWS-Profil mayaws bleibt erhalten: PASS
E. Workspace-Auswahl erfolgreich: PASS
F. Workspace-Erstellung erfolgreich: PASS
G. Fehlerhandling vorhanden: PASS
H. Installer-Lifecycle unverändert: PASS
I. Plan/Deploy/Destroy konsistent: PASS
J. Umgebungsvariablen keine Vermischung: PASS

## Installer Plan
Profile: mayaws
Project: mays-orders-privacy-test
Region: eu-central-1

Plan generiert, ausschließlich CREATE für Ressourcen mit Namen mays-orders-privacy-test.
Keine UPDATE/REPLACE/DELETE an bestehenden Ressourcen.

GSI2 und IAM Least Privilege konfiguriert.

## Governance
AI_AUDITLOG aktualisiert, uncommitted Änderungen erhalten.
