# MO-INSTALLER-UPGRADE-SAFETY-P0A-01

**Upgrade-Safety-Gate im Installer (DELETE/REPLACE-Schutz, Migrationsplanung)**

**Datum:** 2026-11-03
**Branch:** `feature/mo-installer-upgrade-safety-p0a` (von `main` @ `f597d14`)
**Basis-HEAD:** `f597d1486292f7bd8bcaa7ac3e96276f091f9a07`
**Modus:** lokale Implementierung + Tests, kein AWS, kein Terraform Apply/Destroy, kein Push

---

## 1. Executive Summary

Der Installer blockiert jetzt **verbindlich** das Löschen oder Ersetzen
zustandsbehafteter Ressourcen in Deploy-Plänen — bei der Planerstellung **und**
erneut unmittelbar vor dem Apply eines gespeicherten Plans. Ein gültiges
Manifest/SHA-256 allein genügt nicht mehr. Bei einer Blockade entsteht ein
strukturierter **Migrationsplan** (JSON + Markdown) im Run-Verzeichnis; es wird
**keine** Migration ausgeführt.

Der bestehende Destroy-Lifecycle bleibt erhalten und ist gegen Missbrauch als
Bypass abgesichert: `destroy --plan …` akzeptiert nur echte Destroy-Pläne.

```text
P0A COMPLETE — UPGRADE REPLACE PROTECTION VERIFIED
```

---

## 2. Implementierte Komponenten

| Komponente | Datei | Zweck |
|---|---|---|
| Schutzklassifikation + Plan-Analyse | `installer/core/upgrade_safety.py` | Aktionsbasierte Erkennung (`delete`, `create+delete`, `delete+create`), fail-closed bei fehlenden/unbekannten Informationen, `replace_paths` |
| Migrationsplan-Generator | `installer/core/upgrade_safety.py` | `build_migration_plan`, `render_migration_plan_markdown`, `write_migration_plan` (Schema-Version 1, `approved: false`) |
| Gate bei Planerstellung | `installer/cli/main.py::_cmd_plan` | Analyse des erzeugten Plans; bei Blockade Exit 1, **kein Manifest** |
| Gate vor Apply (gespeicherter Plan) | `installer/cli/main.py::_cmd_deploy` | Analyse nach Manifest-Prüfung, vor Kopieren/Apply |
| Destroy-Bypass-Schutz | `installer/cli/main.py::_cmd_destroy` + `_verify_destroy_plan` | nur echte Destroy-Pläne (`delete`/`no-op`/`read`) werden angewendet |
| Fehlermeldung | `format_block_message` | `UPGRADE_BLOCKED_MIGRATION_REQUIRED` mit Adresse, Typ, Aktionen, Datenverlustfolge, Migrationspflicht |

---

## 3. Wiederverwendete Komponenten

| Bestehend | Nutzung |
|---|---|
| Terraform-Plan-JSON (`terraform show -json`) | einzige Quelle der Aktionsklassifikation |
| Plan-Manifest (`plan_manifest.py`) | Identität/SHA-256 weiterhin geprüft — **zusätzlich** zum neuen Gate |
| `evaluate_plan_safety` (Plan Analyzer) | unverändert; blockt weiterhin Destroys im Deploy-Plan |
| Policy Gate | unverändert (Namespace/Tags/Shape) |
| Run-Verzeichnis (`RunDirectoryManager`) | Ablage des Migrationsplans |
| `_make_runner`/`show_plan` | Plan-JSON-Auswertung |

**Bewusst nicht verwendet:** `OwnershipAnalyzer`, `TagSet`, `DevelopmentState.compare`
— sie bleiben unverdrahtet (siehe §9 und die korrigierte Dokumentation).

---

## 4. Geschützte Ressourcentypen

| Typ | DELETE | REPLACE | Begründung |
|---|---|---|---|
| `aws_dynamodb_table` | **BLOCK** | **BLOCK** | Order-Items |
| `aws_s3_bucket` | **BLOCK** | **BLOCK** | Objekte/Versionen |
| `aws_cognito_user_pool` | **BLOCK** | **BLOCK** | Benutzer/Gruppen/Clients |
| `aws_sqs_queue` | **BLOCK** | **BLOCK** | Nachrichten |

Aktionen werden aus `resource_changes[].change.actions` gelesen. `create+delete`
und `delete+create` (Terraform-Replace-Reihenfolgen) werden gleich behandelt.
`replace_paths` werden – soweit vorhanden – in den Bericht übernommen.
Nicht geschützte Typen (Lambda, API, IAM) bleiben dem bestehenden Safety-Review
überlassen (Destroys im Deploy-Plan werden dort weiterhin blockiert).

---

## 5. Gate-Integration (Ablauf)

```text
INSTALLER plan (deploy)
  → terraform plan (Remote)
  → Plan archivieren
  → GATE: show -json → analyze_plan
        SAFE               → Manifest + Erfolg
        MIGRATION_REQUIRED → upgrade-migration-plan.{json,md}, Exit 1, KEIN Manifest
        UNKNOWN            → UPGRADE_BLOCKED_PLAN_UNREADABLE, Exit 1

INSTALLER deploy --plan <gespeichert>
  → Manifest/SHA-256 prüfen
  → GATE erneut (derselbe Plan, unabhängig vom Hash)
  → erst danach Kopie/Integrität/Apply

INSTALLER destroy --plan <gespeichert>
  → Manifest (Operation destroy) prüfen
  → Destroy-Plan-Guard (nur delete/no-op/read)
  → bestehende Destroy-Sicherheit (State-Ziel, Cleanup-Vertrag) → Apply
```

**Fail-closed:** fehlendes/unlesbares Plan-JSON, fehlende `resource_changes`,
fehlende Aktionen oder unbekannte Aktionswerte ⇒ Abbruch, keine Warnung.

---

## 6. Migrationsplan-Schema

`upgrade-migration-plan.json` (Auszug, wie implementiert):

```json
{
  "schemaVersion": 1,
  "status": "MIGRATION_REQUIRED",
  "project": "mays-orders-rc4",
  "environment": "development",
  "workspace": "mays-orders-rc4",
  "sourceVersion": null,
  "targetVersion": null,
  "planSha256": "<sha256>",
  "resources": [
    {
      "address": "module.dynamodb.aws_dynamodb_table.orders",
      "type": "aws_dynamodb_table",
      "actions": ["create", "delete"],
      "replacePaths": ["name"],
      "risk": "CRITICAL",
      "reason": "Ersetzen von aws_dynamodb_table wuerde Order-Daten (Items) der Tabelle zerstoeren.",
      "requiresMigration": true
    }
  ],
  "approved": false
}
```

`upgrade-migration-plan.md` enthält die geforderten 10 Abschnitte
(Ausgangs-/Zielumgebung, Planidentität, kritische Änderungen, Datenverlustrisiken,
betroffene Ressourcen, Strategien A–D, Vorbedingungen, Abnahmekriterien, offene
Entscheidungen) und den Hinweis „keine Ausführungsfreigabe".

---

## 7. Testergebnisse

| Suite | Ergebnis |
|---|---|
| `installer/tests/test_upgrade_safety.py` | **32 PASS** |
| `installer/tests/test_upgrade_gate_cli.py` | **11 PASS** |
| Installer-Gesamtsuite (20 Module) | **315 PASS** |
| Builder / Lambda | unverändert (nicht berührt) |

Abgedeckte Fälle:

- **Positiv:** No-op, neue Tabelle, neuer Bucket, kompatibles Update, GSI-Add,
  expliziter Destroy-Plan.
- **Negativ:** DELETE/REPLACE für DynamoDB, S3, Cognito, SQS; fehlendes Plan-JSON;
  unbekannte Aktion; unlesbares JSON; ungültige Planstruktur; Deploy-Plan über
  `destroy`; gespeicherter Plan mit kritischem Replace (Gate greift erneut);
  **Apply wird bei BLOCKED nicht aufgerufen** (Mock-Assertion).
- Migrationsplan-JSON-Schema, Dateien, Markdown-Abschnitte, Blockmeldung.

---

## 8. Git-Commits (Branch `feature/mo-installer-upgrade-safety-p0a`)

| Commit | Inhalt |
|---|---|
| `2e7911e` | `docs(upgrade)`: Readiness-Analyse (aus vorherigem Auftrag, nachgezogen) |
| `92d9d87` | `feat(installer)`: Schutzklassifikation + Migrationsplan (Core + 32 Tests) |
| `c3f832d` | `feat(installer)`: Gate bei Plan/Apply + Destroy-Bypass-Schutz (+11 Tests) |
| (folgt) | `docs(installer)`: Lifecycle-Doku korrigiert/ergänzt + dieser Report |

Kein Push, kein Merge nach `main`.

---

## 9. Bekannte Einschränkungen

| ID | Einschränkung | Auswirkung |
|---|---|---|
| L-01 | Keine Versionsbindung: `sourceVersion`/`targetVersion` = `null`, `git_commit` im Manifest derzeit `null` | „Welche Version läuft?" bleibt offen |
| L-02 | Keine automatische Kompatibilitätsprüfung (`DevelopmentState.compare` ungenutzt) | Upgrade-Eignung wird nicht automatisch bewertet |
| L-03 | Keine Ownership-Klassifikation (`OwnershipAnalyzer` ungenutzt) | fremde Ressourcen werden nicht automatisch erkannt |
| L-04 | Kein Rollback/Resume; Migration bleibt manuell | Wiederaufnahme nach Fehlern ist Operator-Aufgabe |
| L-05 | Nicht geschützte Typen (Lambda/API/IAM) nur über bestehende Safety/Review | Replacements dort nur Warnung |
| L-06 | Gate benötigt lesbares Plan-JSON (`terraform show`); ohne initialisiertes Terraform bricht es fail-closed ab | korrekt, aber Voraussetzung |

---

## 10. Empfehlungen P0B / P0C

**P0B (Sicherheit/Versionen):**
1. `git_commit` + `installer_version` im Manifest füllen; `targetVersion` binden.
2. Installierte Version im Stack ablegen (Tag/Output) und beim Upgrade lesen.
3. Replace-Gate auf weitere Datenressourcen prüfen (z. B. künftige KMS-Keys,
   Secrets, Buckets mit Versionierung) — nur mit belastbarer Begründung.

**P0C (Upgrade-Komfort):**
4. `plan --upgrade --from <v> --to <v>` mit `DevelopmentState.compare`
   (hartes STOP bei `MIGRATION_REQUIRED`).
5. Change-Klassifikation im Plan-Report (`safe`/`review`/`critical`).
6. Builder-Upgrade-Modus (Manifest-Diff, `--prune`, tfvars-Erhalt).
7. Resume/Checkpoint und Post-Upgrade-No-op-Verifikation.

---

## 11. Status

```text
P0A COMPLETE — UPGRADE REPLACE PROTECTION VERIFIED
```

Schutzprüfungen sind implementiert und getestet; kein AWS-Zugriff, kein Apply,
kein Destroy, kein Push. **STOP.**
