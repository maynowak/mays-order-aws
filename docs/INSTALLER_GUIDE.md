# Mays-Orders-AWS — Installer-Handbuch

**Stand:** 11.10.2026 · **Referenz:** `v0.2.0-rc.1`  
**CLI:** `./Mays-Order-AWS-installer` (Repository-Root)

## 1. Zweck

Der Installer steuert den Terraform-Lebenszyklus mit **Preflight-Validierung, Plan-Erzeugung, Policy Gate, Kontextbindung, menschlicher Freigabe, Deployment und Destroy**. Er schützt vor versehentlichen Operationen im falschen AWS-Konto oder Terraform-Workspace. Er ersetzt weder IAM noch Terraform oder eine menschliche Freigabe.

## 2. Ablauf

```text
Source / Release-Tag
        │
        ▼
AWS-Identität + Projekt + Workspace prüfen
        │
        ▼
Lambda-Artefaktintegrität + Terraform validate
        │
        ▼
Terraform Plan → Policy Gate → Plan-/State-Kontextprüfung
        │
        ▼
Explizite Freigabe → Apply / Deploy
        │
        ▼
Smoke- und E2E-Tests → Evidence sichern
        │
        ▼
Destroy-Plan → Safety Gate → Explizite Destroy-Freigabe
        │
        ▼
Destroy → State- und AWS-Cleanup verifizieren
```

## 3. Voraussetzungen

Git, Python 3, Terraform entsprechend den Constraints in `terraform/`, AWS CLI mit konfiguriertem benannten Profil und passende IAM-Rechte. Zugangsdaten bleiben **außerhalb** des Repositories. Die Zielregion ist im Projekt typischerweise `eu-central-1`; sie muss für die konkrete Installation geprüft werden.

## 4. CLI und read-only Einstieg

```bash
./Mays-Order-AWS-installer --help
./Mays-Order-AWS-installer validate
./Mays-Order-AWS-installer plan
./Mays-Order-AWS-installer plan-destroy
```

Die tatsächliche Optionssyntax und Argumentreihenfolge immer mit `--help` der ausgecheckten Version abgleichen. `terraform init` kann lokale Dateien anlegen und Backend-Metadaten abrufen; Planung ist kein vollständiger Offline-Modus.

AWS-Identität explizit prüfen:

```bash
aws sts get-caller-identity --profile <AWS_PROFIL>
```

## 5. Sicherheitskontext

Vor **jeder** Mutation müssen zusammenpassen:

- AWS-Profil und per STS ermittelte Konto-ID;
- Region;
- Projektname und Terraform-Workspace;
- Backend und State-Key;
- gespeicherter Plan und aktueller State;
- Freigabe für **genau diesen** Plan und dieses Projekt.

**Historischer Testkontext (bereits gelöscht):** Profil `mayaws`, Konto `240571105849`, Region `eu-central-1`, Workspace `mays-orders-privacy-test`, Backend-Prefix `env:`. Diese Werte sind **keine universellen Installer-Defaults** für andere AWS-Konten.

Ein früherer Profilauflösungsfehler wurde behoben; der Installer muss widersprüchliche Identitätsinformationen fail-closed behandeln.

## 6. Mutationsschalter

Die bestehende README dokumentiert:

| Variable | Dokumentierter Wert | Funktion |
|---|---|---|
| `AWS_PROFILE` | `mayaws` | Benanntes Profil, per `--profile` überschreibbar |
| `AWS_REGION` | `eu-central-1` | Region |
| `ALLOW_AWS_OPERATIONS` | `false` | Erforderliche zusätzliche Freigabe für Mutationen |
| `DRY_RUN` | `true` | Standardmäßig kein tatsächlicher Apply/Destroy |

`--yes` überspringt **nur** eine interaktive Rückfrage, nicht die Sicherheitsprüfungen. Die tatsächlichen Defaults sind bei Änderungen am Installer-Code erneut zu prüfen.

### Dokumentierte Deploy-Syntax (nur nach Freigabe)

```bash
export ALLOW_AWS_OPERATIONS=true
export DRY_RUN=false
./Mays-Order-AWS-installer deploy --plan <GEPRUEFTER_PLAN> --yes
```

**Nicht blind ausführen.** Konto, Workspace, State, Policy Gate und Plan müssen zuvor explizit geprüft werden.

## 7. Terraform Policy Gate

Das Gate prüft definierte Ressourcen-, Regions-, Tagging- und Kostenregeln. **PASS** ist keine Kosten- oder IAM-Garantie. Ein FAIL darf nicht umgangen werden, um ein Deployment zu erzwingen.

Quellen: `docs/TERRAFORM_POLICY_GATE.md`, `terraform/policy/resource-policy.json`, `terraform/policy/validate-plan.py`.

## 8. Workspace-Isolation und Backups

Projektbezogene Terraform-Workspaces trennen die State-Dateien, auch wenn ein gemeinsames Backend verwendet wird. Vor einem Destroy ist die Isolierung gegen alle anderen Projekte nachzuweisen. Ein gemeinsamer Backend-Bucket darf nicht gelöscht werden, solange andere Workspaces ihn verwenden.

Cognito-Backup-Module können optional sein. Die Privacy-Testinstallation nutzte deaktivierte Backup-Module; andere Installationen können davon abweichen.

## 9. Lambda-Artefaktintegrität

Ein historischer Fehler entstand durch ein veraltetes `lambda/dist/lambda.zip`, obwohl der Quellcode bereits korrigiert war. Das **Staleness Gate** prüft deshalb das Paket gegen den Source vor der Planung.

```bash
cd lambda
python3 build_zip.py
```

Der dokumentierte Release-Hash für `v0.2.0-rc.1` lautet:

```text
b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b
```

Dieser Hash gilt für den dokumentierten Release Candidate, nicht für beliebige spätere Builds.

## 10. Kontrollierter Destroy

**Pflicht-Gates:** AWS-Identität, Region, Projekt, Workspace, Backend-State, unveränderter aktueller Plan, ausschließlich freigegebene Ressourcen, keine fremden Projektressourcen, gesicherte Evidence und explizite menschliche Freigabe.

```bash
# NUR nach ausdrücklicher Destroy-Freigabe:
export ALLOW_AWS_OPERATIONS=true
export DRY_RUN=false
./Mays-Order-AWS-installer destroy --plan <GEPRUEFTER_DESTROY_PLAN> --yes
```

Im dokumentierten Privacy-Test wurden 37 Ressourcen kontrolliert entfernt. Der betroffene Terraform-State war danach leer; die projektspezifischen DynamoDB-, Cognito-, Lambda-, SQS-, API-Gateway-, CloudWatch-, IAM- und S3-Ressourcen waren nicht mehr vorhanden. Das ist ein **historischer Nachweis**, keine Garantie für künftige Installationen.

## 11. Post-Deploy- und Post-Destroy-Prüfungen

**Nach Deploy:** Lambda-Code-Hash, JWT-Authentifizierung, API-Aufrufe, Statusübergänge, SQS-Worker, DynamoDB-Indizes, Logs und IAM-Berechtigungen verifizieren; Testdaten anschließend entfernen.

**Nach Destroy:** `terraform state list` im **richtigen Workspace** prüfen; projektspezifische AWS-Ressourcen suchen; asynchrone Löschungen und mögliche Kostenreste dokumentieren; fremde Workspaces und gemeinsame Backends unangetastet lassen.

## 12. Security und Einschränkungen

- Keine Secrets, Tokens, Terraform-State- oder Plan-Dateien committen.
- Secrets nicht in CLI-Argumenten, Logs oder Shell-History offenlegen.
- Policy Gate ersetzt nicht IAM, Kostenüberwachung oder menschliche Freigabe.
- Der interne Privacy-Invoke-Pfad ist **nicht produktiv freigegeben**.
- Dauerhaftes Secret-Management und Rotation sind offen.
- Neue Ressourcentypen erfordern neue Sicherheits- und Destroy-Tests.

## 13. Release-Testnachweise

| Prüfung | Ergebnis im RC-Checkpoint |
|---|---|
| Installer Unit Tests | 81 PASS |
| Lambda Unit Tests | 76 PASS |
| Artifact Integrity | 5 PASS |
| Terraform fmt / validate | PASS |
| Privacy AWS E2E | Historisch P-01 bis P-03 PASS |
| AWS Regression | Historisch 12/12 PASS |
| Destroy Lifecycle | 37 Deletes, State leer, 0 projektspezifische Reste |

## 14. Wartung und Dokumentationspflicht

Änderungen an CLI-Flags, Profilauflösung, Planformat, Workspace-Auswahl, Policy Gate oder Artefaktprüfung erfordern Aktualisierung dieses Guides, der README, der Reports und `docs/AI_AUDITLOG.md`. Abgeschlossene Arbeitsschritte werden nachvollziehbar committed.

**Weiterlesen:** [Produktübersicht](PRODUCT_OVERVIEW.md) · [Policy Gate](TERRAFORM_POLICY_GATE.md) · [Release Notes](RELEASE_NOTES.md) · [RC-Report](reports/MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01.md)
