# MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-02

**Vollständige Beseitigung kontospezifischer IAM-Defaults**

## Ausgangszustand nach FIX-01

- `terraform/modules/sqs-worker/variables.tf`: Default `null` → portabel
- `terraform/variables.tf`: Default weiterhin `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`
- Root-Installation abhängig von ursprünglichem Konto

## Durchgeführte Änderung

**Datei:** `terraform/variables.tf`
- Variable `lambda_execution_boundary` Default von hartcodiertem ARN auf `null` gesetzt
- Validation für ARN-Format beibehalten
- Keine neue Konto-ID eingeführt

**Auswirkung:**
- Root-Konfiguration ist nun konto-unabhängig
- Boundary muss explizit vom Betreiber gesetzt werden oder bleibt `null`
- Module Builder übernimmt Variable unverändert, generiertes Modul bleibt portabel

## Sicherheitsentscheidung

- Permissions Boundary ist optional
- Falls Sicherheitsvertrag eine verpflichtende Boundary verlangt, muss der Betreiber den Wert explizit in `terraform.tfvars` setzen
- Keine stillschweigende Abschwächung ohne Dokumentation

## Tests

- Module Builder Tests: 90 OK
- Terraform fmt/init/validate: PASS
- Generiertes orders-service Modul: Variable default `null`

## Risiken

- Bestehende Root-Installationen ohne expliziten Variablenwert verlieren Boundary
- Dokumentation/Updater erforderlich

## Dateien geändert

- `terraform/variables.tf`
