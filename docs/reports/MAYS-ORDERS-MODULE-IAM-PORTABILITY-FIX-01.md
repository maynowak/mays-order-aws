# MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-01

**Behebung des IAM-Portabilitätsfehlers F-01**

## Ausgangsproblem

Audit `MAYS-ORDERS-MODULE-IAM-PORTABILITY-AUDIT-01` bestätigte F-01:
- `terraform/modules/sqs-worker/variables.tf` enthielt fest verdrahtete Permissions Boundary `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`
- Default wurde 1:1 in generiertes `orders-service` Modul übernommen
- Consumer in fremdem AWS-Konto (`ris-dev2`) kann Modul nicht ohne Patch nutzen

## Technische Ursache

- Modul-Variable `lambda_execution_boundary` hatte konto-spezifischen Default
- Kein Top-Level-Vertragseintrag im Orders-Service Preset
- Builder kopierte Modul unverändert → Portabilität verletzt

## Implementierte Änderungen

### 1. Modul `sqs-worker` portabel machen
**Datei:** `terraform/modules/sqs-worker/variables.tf`
- Default von hartcodiertem ARN auf `null` geändert
- Beschreibung aktualisiert
- Validation ergänzt: ARN muss `arn:aws:iam::<12-digit>:policy/` Format haben oder `null`

### 2. Root-Projekt Kompatibilität erhalten
**Datei:** `terraform/variables.tf`
- Neue Variable `lambda_execution_boundary` mit Default `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`
- Validation wie oben
- Erhält bestehendes Sicherheitsverhalten im Root-Stack

**Datei:** `terraform/main.tf`
- Modul `sqs_worker` Instanziierung um `lambda_execution_boundary = var.lambda_execution_boundary` erweitert

### 3. Modulvertrag erweitern
**Datei:** `module_builder/spec.py`
- `ORDERS_SERVICE_VARIABLES` um `lambda_execution_boundary` erweitert

**Datei:** `module_builder/catalog.py`
- `VARIABLE_MODULES["lambda_execution_boundary"] = ["sqs_worker"]` hinzugefügt

**Datei:** `module_builder/builder.py`
- Default für `lambda_execution_boundary` im generierten Orders-Service Modul auf `null` überschrieben
- Sicherstellt, dass generiertes Modul keinen konto-spezifischen Default enthält

### 4. Tests angepasst
**Datei:** `module_builder/tests/test_module_builder.py`
- Erwartete Variablenmenge aktualisiert (6 statt 5 Inputs)
- Regressionstests bleiben grün

## Neues Input-Verhalten

| Eingabe | Erwartetes Ergebnis |
|---|---|
| Gültige Boundary-ARN des Zielkontos | Boundary wird Worker-Rolle zugewiesen |
| `null` (Default im generierten Modul) | Keine Boundary gesetzt |
| Ungültiges ARN-Format | Terraform Validation Fehler vor Plan |
| Root-Projekt ohne Überschreibung | Behält bestehende Boundary aus `terraform/variables.tf` Default |

**Sicherheitsentscheidung bei `null`:**
- Generiertes Modul erlaubt `null` → keine Boundary
- Root-Projekt behält Default-Boundary → bestehende Sicherheitsanforderung erhalten
- Consumer kann explizit Boundary setzen → Portabilität + Sicherheit optional

## Rückwärtskompatibilität

- Root-Orders-Service: unverändert, Default Boundary bleibt aktiv
- Bestehende Consumer mit explizitem Wert: unverändert
- `complete` Preset: unverändert, Variable wird mitgeführt
- `sqs_enabled` Gate: unverändert, planstabil

## Testergebnisse

**Module Builder Tests**
- `python3 -m unittest module_builder.tests.test_module_builder`
- Ergebnis: `Ran 90 tests ... OK`
- Exit-Code: 0

**Generierungstest**
- Preset `orders-service` → `/tmp/test-orders-module2`
- `variables.tf` enthält `lambda_execution_boundary` mit `default = null`
- `main.tf` enthält `lambda_execution_boundary = var.lambda_execution_boundary`
- Modul `sqs-worker/variables.tf` Default `null`

**Terraform-Prüfungen**
- `terraform fmt -check -recursive` → PASS
- `terraform init -backend=false` → SUCCESS
- `terraform validate` → Success! The configuration is valid.

## Auswirkungen auf RIS `ris-dev2`

- Orders-Service Modul kann ohne Patch in `ris-dev2` integriert werden
- RIS kann optional `lambda_execution_boundary` mit eigener Konto-ARN setzen oder weglassen
- Kein internes Terraform-Patching erforderlich
- Komponentenname `ris-dev2-mays-orders` bleibt kompatibel

## Verbleibende Risiken

- Wenn Consumer Boundary setzt, muss ARN zum Zielkonto gehören → Validation prüft nur Format, keine Konto-Übereinstimmung ohne Data Source
- Sicherheitsentscheidung `null` liegt beim Consumer → Dokumentation erforderlich

## Dateien geändert

- `terraform/modules/sqs-worker/variables.tf`
- `terraform/variables.tf`
- `terraform/main.tf`
- `module_builder/spec.py`
- `module_builder/catalog.py`
- `module_builder/builder.py`
- `module_builder/tests/test_module_builder.py`

**Commit:** wird nach Abschluss erzeugt
