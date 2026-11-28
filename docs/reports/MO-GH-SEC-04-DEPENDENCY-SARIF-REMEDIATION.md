# MO-GH-SEC-04 — Dependency Detector & SARIF Remediation

**Status:** `LOCAL REMEDIATION VERIFIED / GITHUB SCAN VERIFICATION PENDING`

**Datum:** 2026-11-28
**Branch:** `feature/mo-github-security-cleanup-01`
**Baseline:** `37aba96` (MO-GH-SEC-01)
**Main-Basis:** `8830da2` (unverändert)
**Scope:** `security/dependency_detector.py`, `security/sarif_adapter.py`,
`installer/tests/test_installer.py`, Dokumentation.

## Ergebnis

Die drei lokalen Remediation-Schritte sind umgesetzt, getestet und als separate
Commits auf dem Feature-Branch abgelegt:

| Schritt | Commit | Inhalt |
|---|---|---|
| 1 | `dd5ff62` | Terraform-korrekte `~>`-Semantik, SemVer-Vergleich, kombinierte Constraints, Pre-Releases, numerische Sortierung; falsche Testerwartungen korrigiert |
| 2 | `1534a98` | Lock-basierte Auflösung: Declared Constraint, Locked Version, Latest Available, Latest Compatible; Lock-Drift/-Missing/-Violation, Registry-Fehler/-Incomplete explizit |
| 3 | `e2bfe88` | SARIF-Remediation: repository-relative URIs, stabile Rule-IDs/Fingerprints, Kategorie `dependency-check`, keine `CURRENT`-Findings |
| 4 | dieser Report | Verifikation, Vorher-/Nachher-Vergleich, Auditlog/PROJECT_STATUS |

Es wurden **keine Dependency-Versionen**, keine Workflows, keine
Order-Modul-Dateien, keine AWS-Ressourcen und keine Terraform-Konfiguration
geändert. Es gab **kein** Alert-Dismissal, keinen Main-Merge, kein
AWS-Deployment und keine Terraform-Operation.

## Behobene Baseline-Befunde

### 1. `~>`-Semantik

Die bisherige Implementierung behandelte `~> 1.2.3` als `< 1.2.4` und
`~> 0.11` als `< 0.12`. Terraform erlaubt dagegen:

| Constraint | Korrekte Bedeutung |
|---|---|
| `~> 0.11` | `>= 0.11.0`, `< 1.0.0` |
| `~> 0.11.0` | `>= 0.11.0`, `< 0.12.0` |
| `~> 6.0` | `>= 6.0.0`, `< 7.0.0` |
| `~> 1.2.3` | `>= 1.2.3`, `< 1.3.0` |

Zusätzlich werden kombinierte Constraints (`>= 6.0, < 7.0`,
`~> 1.2, != 1.2.3`), SemVer-Pre-Releases (`1.2.3-alpha < 1.2.3`) und
numerische Sortierung (`1.10.0 > 1.2.0`) unterstützt. Die alten
Test-Erwartungen in `installer/tests/test_installer.py` wurden fachlich
korrigiert; die falschen Assertions sind nicht mehr vorhanden.

### 2. Lock-basierte Dependency-Auflösung

Der Detector liest jetzt `terraform/.terraform.lock.hcl` und unterscheidet:

- **Declared Constraint** (`terraform/main.tf`)
- **Locked Version** (`.terraform.lock.hcl`)
- **Latest Available** (neueste Registry-Version)
- **Latest Compatible** (neueste Version innerhalb des Declared Constraint)

Statuswerte:

| Status | Bedeutung | SARIF |
|---|---|---|
| `CURRENT` | Lock erfüllt Constraint, kein kompatibles Update | **kein Finding** |
| `UPDATE_AVAILABLE` | neueres kompatibles Update verfügbar | `note` |
| `CONSTRAINT_UNSATISFIED` | Locked Version verletzt Declared Constraint | `error` |
| `LOCK_MISSING` | Provider fehlt im Lock | `warning` |
| `LOCK_CONSTRAINT_DRIFT` | Lock-Constraints weichen von Declared Constraint ab; Update unterdrückt | `warning` |
| `REGISTRY_INCOMPLETE` | Registry liefert keine/ältere Version als Lock | `warning` |
| `LOOKUP_ERROR` | Registry-Abfrage fehlgeschlagen | `warning` |
| `ERROR` | ungültiger Constraint/Lock oder anderer Fehler | `error` |

Damit werden falsche Update-/Downgrade-Empfehlungen verhindert. Ein
Registry-Ergebnis, dessen höchste Version älter als die Lock-Version ist, führt
zu `REGISTRY_INCOMPLETE` und **nicht** zu einer Downgrade-Empfehlung. Eine
Lock-/Constraint-Abweichung führt zu `LOCK_CONSTRAINT_DRIFT`; bis zur
Reconciliation wird kein Update empfohlen.

### 3. SARIF-Remediation

`security/sarif_adapter.py` erzeugt jetzt:

- **repository-relative** `artifactLocation.uri` (z. B. `terraform/main.tf`),
  auch wenn der Detector absolute Pfade liefert;
- stabile Rule-IDs `SEC01-<TYPE>-<STATUS>` und stabile
  `partialFingerprints` (`dependencyIdentity/v1`, SHA-256 über Typ/Name/Quelle/
  Rule-ID);
- konsistente Tool-Identität (`Mays-Orders-AWS Security Dependency Detector`,
  Version `2.0.0`) und `automationDetails.id = "dependency-check"` passend zur
  Workflow-Kategorie;
- **keine** SARIF-Results für `CURRENT`-Dependencies;
- actionable Findings für `UPDATE_AVAILABLE`, `CONSTRAINT_UNSATISFIED`,
  `LOCK_MISSING`, `LOCK_CONSTRAINT_DRIFT`, `REGISTRY_INCOMPLETE`,
  `LOOKUP_ERROR`, `ERROR`, `CHANGED`, `UNKNOWN`;
- Properties für Declared/Locked/Latest Available/Latest Compatible.

## Vorher-/Nachher-Vergleich (reproduzierbares Fixture)

Fixture: `terraform/main.tf` mit AWS `>= 6.0` und time `~> 0.11`;
`.terraform.lock.hcl` mit AWS `6.65.0` (`~> 6.0`) und time `0.14.2`
(`~> 0.11`). Die Baseline-Simulation verwendet den Detector-Stand `37aba96`
und die damalige unsortierte „erste Registry-Version“ (AWS `3.24.1`,
time `0.14.2`). Der korrigierte Lauf sortiert numerisch und berücksichtigt das
Lock.

**Baseline (`37aba96`, simuliert):**

```json
{
  "status": "DEPENDENCY_CHANGE_DETECTED",
  "summary": "2 dependency constraint(s) unsatisfied",
  "dependencies": [
    {"name": "aws",  "status": "CONSTRAINT_UNSATISFIED", "declared": ">= 6.0"},
    {"name": "time", "status": "CONSTRAINT_UNSATISFIED", "declared": "~> 0.11"}
  ]
}
```

**Korrigiert (`e2bfe88`):**

```json
{
  "status": "DEPENDENCY_CHANGE_DETECTED",
  "summary": "1 dependency warning(s) require review",
  "dependencies": [
    {
      "name": "aws",
      "status": "LOCK_CONSTRAINT_DRIFT",
      "declared": ">= 6.0",
      "locked": "6.65.0",
      "latest_available": "6.65.0",
      "latest_compatible": "6.65.0"
    },
    {
      "name": "time",
      "status": "CURRENT",
      "declared": "~> 0.11",
      "locked": "0.14.2",
      "latest_available": "0.14.2",
      "latest_compatible": "0.14.2"
    }
  ]
}
```

Damit sind die beiden Baseline-Fehlalarme reproduzierbar beseitigt:

- **Alert #296 (AWS, `CONSTRAINT_UNSATISFIED`):** Die korrigierte Auflösung
  erzeugt für AWS keinen Constraint-Fehler mehr. Wegen der echten
  Constraint-Drift (`main.tf` `>= 6.0` vs. Lock `~> 6.0`) erscheint stattdessen
  ein `LOCK_CONSTRAINT_DRIFT`-Warning. Der alte Fehler-Alert sollte beim
  nächsten korrigierten Scan automatisch schließen; der Drift-Warning ist ein
  tatsächlicher Handlungsbedarf und kein Scanner-Fehlalarm.
- **Alert #298 (time, `CURRENT`-Note):** `CURRENT` wird nicht mehr als
  SARIF-Result emittiert. Der alte Note-Alert sollte automatisch schließen.

Die GitHub-Scan-Verifikation ist noch offen, weil sie einen Workflow-Lauf auf
`main`/PR mit Upload des korrigierten SARIF voraussetzt. Es wurde kein
Workflow geändert und kein Alert manuell geschlossen.

## Ausgeführte Verifikation

| Prüfung | Ergebnis |
|---|---|
| `python3 -m unittest -q installer.tests.test_installer.TestDependencyDetector installer.tests.test_installer.TestSarifAdapter` | **33/33 OK** (20 Detector + 13 SARIF) |
| `python3 -m unittest installer.tests.test_installer` | **98/98 OK** |
| `python3 -m unittest discover -s installer/tests` | **691 Tests, OK (skipped=2)**, 8,176 s |
| Lambda `python3 -m compileall -q src tests` | **PASS** |
| Lambda `PYTHONPATH=src python3 -m unittest discover -s tests` | **456/456 OK** |
| Lambda `python3 build_zip.py` | **PASS**, `dist/lambda.zip` 47.552 Bytes, SHA-256 `117299c97c775038fa2ccdedf3ecc2515a3d2c2e6a537bf9ede3fff1a5b425af` |
| `python3 -m unittest discover -s module_builder/tests` | **129/129 OK** |
| `cd scripts && python3 -m unittest discover -s tests` | **28/28 OK** |
| `python3 -m unittest tests.test_e2e_harness tests.test_privacy_e2e_harness` | **32/32 OK** (lokal, ohne AWS) |
| `git diff --check` | **PASS** |
| Secret-Audit | **keine Credentials**; Regex-Treffer waren ausschließlich Test-Assertions auf Feldnamen (`aws_secret_access_key` etc.) |

**Nicht ausgeführt / abgegrenzt:**

- Keine AWS-Operation, kein `terraform plan/apply/destroy`, kein Deployment.
- Keine Live-E2E-Tests (benötigen deployte Infrastruktur, Cognito-Testidentität
  und Credentials); nur die lokalen E2E-Harnesses wurden ausgeführt.
- `python3 -m unittest discover -s cognito_backup/tests` findet keine
  `unittest`-Tests (die Dateien sind pytest-/Skript-Stil); daher nicht als
  Regressionsevidenz gezählt.
- Keine Workflow-Orchestrierungsänderung; die GitHub-Scan-Verifikation bleibt
  offen.

## Geänderte Dateien

- `security/dependency_detector.py`
- `security/sarif_adapter.py`
- `installer/tests/test_installer.py`
- `docs/reports/MO-GH-SEC-04-DEPENDENCY-SARIF-REMEDIATION.md`
- `docs/AI_AUDITLOG.md`
- `docs/PROJECT_STATUS.md`
- `docs/wiki/08-entwicklung-und-qualitaet.md` (Testzahlen)
- `docs/wiki/11-dokumentationsportal.md` (Report-Link)

**Nicht geändert:** `.github/workflows/**`, `terraform/main.tf`,
`terraform/.terraform.lock.hcl`, `lambda/src/**`, `lambda/tests/**`,
AWS-/Cognito-/IAM-Ressourcen, Security-Settings.

## Risiken und Restpunkte

1. **GitHub-Scan-Verifikation ausstehend:** Der korrigierte SARIF muss durch
   einen Workflow-Lauf hochgeladen werden. Erst danach kann bestätigt werden,
   dass #296/#298 automatisch schließen und welche neuen Findings entstehen.
2. **AWS-Constraint-Drift:** `terraform/main.tf` deklariert `>= 6.0`, der Lock
   hält `~> 6.0`. Das ist ein echter Konfigurations-/Lock-Drift. Die
   Reconciliation (Lock neu erzeugen oder Constraint bewusst angleichen) ist
   eine separate, freigabepflichtige Änderung; sie wurde hier nicht
   vorgenommen.
3. **Registry-Nichtdeterminismus:** Die Auflösung sortiert und behandelt
   Fehler/ältere Daten explizit, aber die tatsächlich verfügbaren Versionen
   hängen von der Registry zum Scanzeitpunkt ab.
4. **Kein Alert-Dismissal:** Alte Alerts werden nicht manuell geschlossen;
   die automatische Auflösung durch korrigierte Scans bleibt abzuwarten.

## Nächste Aktionen

1. Feature-Branch pushen (dieser Checkpoint).
2. Korrigierten Scan auf `main`/PR auslösen; #296/#298 und neue
   `LOCK_CONSTRAINT_DRIFT`-Findings prüfen.
3. AWS-/Lock-Constraint-Drift in einem separaten, freigegebenen Task
   reconciliieren.
4. Mit `MO-GH-SEC-02` (CI-Orchestrierung) gemäß Baseline-Reihenfolge fortfahren.

**Abschlussstatus:** `LOCAL REMEDIATION VERIFIED / GITHUB SCAN VERIFICATION PENDING`
