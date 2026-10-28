# MAYS-ORDERS-MODULE-IAM-PORTABILITY-AUDIT-01

**Audit des Module Builders hinsichtlich AWS-Kontoportabilität für RIS `ris-dev2`**

## 1. Git-Baseline

- Repository: `maynowak/mays-order-aws`
- Lokaler Pfad: `/home/dci-student/projects/Mays-Orders-AWS`
- Branch: `feature/mo-module-contract-ris-dev2-2026`
- HEAD: `9627eb2f43087ab07dd7cc98a21febca142cb3b6`
- Working Tree: clean
- Referenz-Commit: `9627eb2f43087ab07dd7cc98a21febca142cb3b6` ✓ übereinstimmend

Keine Änderungen an `main`, Release-Tags oder produktiven AWS-Ressourcen. Nur read-only-Audit.

## 2. Untersuchter Befund F-01

**Datei:** `terraform/modules/sqs-worker/variables.tf:35`

```hcl
variable "lambda_execution_boundary" {
  description = "IAM permissions boundary"
  type        = string
  default     = "arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary"
}
```

**Verwendung:**
- `terraform/modules/sqs-worker/iam.tf:53`: `permissions_boundary = var.lambda_execution_boundary`
- Modul: `aws_iam_role.worker` (Lambda Execution Role für SQS-Worker)
- Im Root `terraform/main.tf` wird das Modul `sqs_worker` ohne expliziten Wert für `lambda_execution_boundary` instanziiert → Default wird übernommen.

**Auswirkungen:**
1. Welche IAM-Rolle verwendet die Boundary? → `aws_iam_role.worker` in `sqs-worker`
2. Wie wird der Default vom Module Builder übernommen? → Builder kopiert `terraform/modules/sqs-worker/variables.tf` unverändert via `_copy_tf_tree`; kein Override
3. Kann der Consumer die Boundary explizit konfigurieren? → **Nein**. Die Variable ist ein internes Modul-Variable des Child-Moduls `sqs_worker`. Der Orders-Service-Vertrag (`ORDERS_SERVICE_VARIABLES`) enthält `lambda_execution_boundary` nicht. Top-Level-Variablen: `project_name`, `tags`, `monitoring_enabled`, `log_retention_days`, `external_cognito`.
4. Wird die Boundary beim Generieren festgeschrieben? → Ja, als Default im kopierten Modul.
5. Auswirkung beim Terraform Apply in anderem AWS-Konto? → `permissions_boundary` referenziert ARN aus Konto `240571105849`. In `ris-dev2` (anderes Konto) existiert diese Policy nicht → `aws_iam_role` Create schlägt mit `InvalidPermissionsBoundary` fehl. Selbst wenn Policy mit gleichem Namen existiert, hat sie eine andere ARN.
6. Ist die Boundary im Zielkonto vorhanden oder wird sie erzeugt? → Weder noch. Es erfolgt keine Erstellung; die Referenz ist hart.
7. Sicherheitsvertrag erhalten? → Nein. Portabilität verletzt; Sicherheitsmechanismus wird implizit deaktiviert oder bricht Plan/Apply ab.

**Einstufung:** Kontoabhängigkeit hoch, Risiko **HOCH**

## 3. Vollständiger IAM- und Account-Audit

### Suchkriterien
- Feste 12-stellige AWS-Konto-IDs in `terraform/modules/`
- `arn:aws:iam::` mit Account-ID
- `permissions_boundary` Verwendung
- Statische Rollen-/Policy-ARNs
- Kontoabhängige Trust/Resource Policies

### Ergebnis

| ID | Datei | Ressource | Fund | Kontoabhängigkeit | Risiko |
|---|---|---|---|---|---|
| F-01 | `terraform/modules/sqs-worker/variables.tf:35` | `lambda_execution_boundary` default | `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary` | Konto-ARN hardcoded | **HOCH** |
| F-02 | `terraform/modules/sqs-worker/iam.tf:53` | `aws_iam_role.worker.permissions_boundary` | Verweis auf var | Vererbt F-01 | **HOCH** |
| F-03 | `terraform/backend.tf:3` | S3 Backend Bucket | `mays-orders-tfstate-central-240571105849` | Konto in Name | **NIEDRIG** (nicht vom Builder kopiert) |
| F-04 | `terraform/bootstrap/variables.tf:10` | Bootstrap Bucket Default | `mays-orders-tfstate-central-240571105849` | Konto in Name | **NIEDRIG** (Root-Setup, nicht Modul) |
| F-05 | `ci/pipeline/main.tf:428` | CodeConnections ARN | `arn:aws:codeconnections:eu-central-1:240571105849:...` | CI-Kontext | **NIEDRIG** (nicht Modul) |

Weitere IAM-Referenzen in Modulen:
- **Keine weiteren festen `arn:aws:iam::` mit Account-ID** gefunden in `terraform/modules/`.
- Alle anderen ARN-Verweise sind dynamisch via `data.aws_caller_identity.current.account_id` oder `var.*` (cloudtrail, cognito_backup_automation).
- Keine statischen Role-/Policy-ARNs in Module-Inputs/Outputs.
- `permissions_boundary` kommt ausschließlich in `sqs-worker` vor.
- `module_builder/` enthält keine festen AWS-ARNs.

### Module Builder Inputs

**ORDERS_SERVICE-Vertrag (MAYS-ORDERS-MODULE-CONTRACT-01):**
- Preset `orders-service` → Module: `api`, `cognito`, `dynamodb`, `iam`, `lambda`, `sqs`, `sqs_worker`
- Top-Level-Variablen: `project_name`, `tags`, `monitoring_enabled`, `log_retention_days`, `external_cognito`
- `lambda_execution_boundary` ist **nicht** Teil des Vertrags, daher nicht konfigurierbar für den Consumer.

**Copy-Verhalten:**
- `_copy_tf_tree` kopiert alle `*.tf` aus `terraform/modules/<dir>` unverändert.
- Keine Transformation von Variablen-Defaults im Builder.
- Ergebnis: Default-ARN wird 1:1 in das generierte Modul übernommen.

## 4. Portabilitätsanforderungen Bewertung

| Anforderung | Status | Begründung |
|---|---|---|
| P-01 Konto-Unabhängigkeit | **VERLETZT** | F-01 führt zu zwingender Abhängigkeit von Policy im Konto `240571105849` |
| P-02 Explizite IAM-Konfiguration | **VERLETZT** | Boundary nicht über Modulvertrag konfigurierbar |
| P-03 Sichere Defaults | **KRITISCH** | Default ist konto-spezifisch; Deaktivierung nicht dokumentiert |
| P-04 Terraform-Planbarkeit | **GEFÄHRDET** | Plan schlägt im fremden Konto fehl |
| P-05 ARN-Vertrag | **ERFÜLLT** | Outputs für Lambda/SQS/DynamoDB bleiben erhalten |
| P-06 Rückwärtskompatibilität | **GEFÄHRDET** | Änderung erforderlich, aber kontrollierbar |
| P-07 RIS-Kompatibilität | **VERLETZT** | `ris-dev2` kann Modul ohne Patch nicht nutzen |

## 5. Lösungsvarianten

### Variante A: Consumer übergibt vorhandene Boundary-ARN

- Variable `lambda_execution_boundary` wird zum Top-Level-Input des Orders-Service-Moduls.
- Default wird auf `null` gesetzt → wenn `null`, keine Boundary gesetzt.
- Child-Modul `sqs-worker` erhält Variable als Input mit `default = null`.
- **Sicherheit:** Hoch (Boundary optional/gefordert je Policy)
- **Portabilität:** Hoch
- **Rückwärtskompatibilität:** Erfordert Breaking Change (Default `null` vs. vorheriger Default). Migrationspfad nötig.
- **Aufwand:** Mittel (Vertragsänderung, Child-Modul Anpassung)

### Variante B: Boundary wird im Zielkonto erzeugt

- Modul enthält eine optionale `permissions_boundary` Komponente: wenn `create_permissions_boundary = true` (Default `false`), wird eine `aws_iam_policy` mit vorgegebenem Managed-Policy-Dokument im Zielkonto erzeugt.
- Default ARN wird entfernt, stattdessen `aws_iam_policy` Ressource.
- **Sicherheit:** Hoch (Boundary bleibt aktiv, aber im Zielkonto)
- **Portabilität:** Hoch
- **Rückwärtskompatibilität:** Gut (opt-in)
- **Aufwand:** Hoch (Policy-Dokument muss gepflegt werden)

### Variante C: Dokumentierter Betriebsmodus ohne Boundary

- Default wird auf `null` gesetzt, `permissions_boundary` optional.
- Dokumentation: Boundary ist empfohlener Sicherheitsmechanismus; ohne Boundary läuft Modul, entspricht bestehender Sicherheitslage im Root-Stack (Root nutzt keine Boundary für `iam` Modul).
- **Sicherheit:** Absenkung möglich, wenn Consumer Boundary nicht setzt → erfordert Governance
- **Portabilität:** Hoch
- **Rückwärtskompatibilität:** Hoch (Default `null` verhält sich wie bisher wenn Consumer nichts ändert? Nein, bisheriger Default war fest. Also Breaking.)
- **Aufwand:** Niedrig

### Empfehlung

**Variante A mit sicherem Default `null` und expliziter Validierung:**

1. `lambda_execution_boundary` wird als optionale Variable im Orders-Service-Vertrag aufgenommen: `string` mit `default = null`.
2. In `terraform/modules/sqs-worker/variables.tf`: Default auf `null` ändern.
3. In `terraform/modules/sqs-worker/iam.tf`: `permissions_boundary = var.lambda_execution_boundary` → Terraform akzeptiert `null` (keine Boundary gesetzt).
4. Dokumentation: Falls Organisation Boundary erzwingen will, muss sie ARN des Zielkontos angeben.
5. Für maximale Sicherheit kann zusätzlich Variante B als Opt-in angeboten werden (zukünftiger Release).

Begründung: Portabilität ohne Sicherheitsabsenkung (Boundary bleibt optional nutzbar), kein neues Policy-Dokument im Modul (keine Drift), minimaler Change, klarer Vertrag.

## 6. Tests und Nachweise

Ausgeführte Prüfungen (lokal, nicht destruktiv):

1. **Builder Regression Tests**
   - Befehl: `python3 -m unittest module_builder.tests.test_module_builder`
   - Ergebnis: `Ran 90 tests ... OK`
   - Nachweis: Module Builder Funktionalität intakt

2. **Orders-Service Generierung**
   - Befehl: `python3 -m module_builder build --target /tmp/test-orders-module --project-name testproj --preset orders-service --force`
   - Ergebnis: Modul erfolgreich generiert
   - Nachweis: `cat /tmp/test-orders-module/modules/sqs-worker/variables.tf | grep lambda_execution_boundary` bestätigt Default ARN `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`

3. **Hardcoded Account ID Suche**
   - Befehl: `grep -R -E "arn:aws:iam::[0-9]{12}:" terraform/modules --include="*.tf"`
   - Ergebnis: Nur F-01 gefunden

4. **Permissions Boundary Suche**
   - Befehl: `grep -R -n "permissions_boundary" . --include="*.tf"`
   - Ergebnis: Nur `terraform/modules/sqs-worker/iam.tf:53`

5. **Terraform Validate (ohne AWS)**
   - Nicht ausgeführt für generiertes Modul (kein `terraform init` nötig für Audit). `terraform validate` wäre ohne Provider-Konfiguration nicht aussagekräftig.

**Hinweis:** `terraform validate` ist kein Nachweis für erfolgreiche AWS-Deployment.

## 7. Offene Risiken

- Wenn Default nicht geändert wird, schlägt jeder Terraform Apply im Zielkonto `ris-dev2` fehl.
- Sicherheitsvertrag: Entfernen der Boundary ohne Ersatz senkt Sicherheit.
- Rückwärtskompatibilität: Änderungen am Modulvertrag betreffen bestehende Consumer des Root-Stacks.
- Dokumentation: Der aktuelle Default suggeriert, dass Boundary bereits vorhanden ist → falsche Erwartung.

## 8. Konkrete Implementierungsaufgaben (nach Freigabe)

1. `terraform/modules/sqs-worker/variables.tf`: Default `lambda_execution_boundary` auf `null` setzen.
2. `terraform/modules/sqs-worker/iam.tf`: `permissions_boundary` bleibt, akzeptiert `null`.
3. Orders-Service-Vertrag erweitern:
   - `module_builder/spec.py`: `ORDERS_SERVICE_VARIABLES` um `lambda_execution_boundary` ergänzen (optional, default null).
   - `ORDERS_SERVICE_README_TEMPLATE` aktualisieren.
4. Module Builder: Variable in `variables.tf` des generierten Moduls aufnehmen.
5. Tests anpassen: Builder-Tests prüfen Default-Null.
6. Dokumentation: `docs/reports/MAYS-ORDERS-MODULE-IAM-PORTABILITY-AUDIT-01.md` + Modul-README aktualisieren.
7. Auditlog-Eintrag erstellen.

## 9. Sicherheitsgrenzen eingehalten

- Kein `terraform apply`/`destroy`
- Keine State-Migration
- Keine Änderungen an AWS IAM
- Keine Änderungen im RIS-Repository
- Keine Release-Tags verändert
- Keine automatische Entfernung von Permissions Boundaries

---

**Audit abgeschlossen am:** 2026-10-22  
**Auditor:** OpenCode  
**Status:** Befund bestätigt, Implementierung ausstehend auf Freigabe
