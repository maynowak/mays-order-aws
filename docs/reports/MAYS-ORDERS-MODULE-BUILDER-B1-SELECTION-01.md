# MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01

**Checkpoint:** MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01
**Datum:** 2026-10-18
**Baseline:** main `d6469b5` (Hardening-01)
**Scope:** B1 — freie Modulauswahl über `--modules` (KEINE automatische Abhängigkeitsauflösung; B2 stoppt)
**Status:** IMPLEMENTED / VERIFIED — 44/44 Builder-Tests, Live-Validierungen (terraform fmt/init/validate) auf Einzel-/Kombinations-/Vollauswahl PASS, 129/129 Installer- + 76/76 Lambda-Regression, Git CLEAN

## 1. Modulabhängigkeiten (verifizierte Analyse)

Direkte `module.<x>`-Referenzen je Root-Modulblock (`terraform/main.tf`, per
Brace-Matching + Referenz-Scan maschinell verifiziert):

```text
dynamodb                    -> (keine)
sqs                         -> (keine)
cognito                     -> (keine)
cloudtrail                  -> (keine)
cognito_backup              -> (keine)
iam                         -> dynamodb, sqs
lambda                      -> dynamodb, iam, sqs
sqs_worker                  -> dynamodb, sqs
api                         -> cognito, lambda
monitoring                  -> api, dynamodb, lambda
cognito_backup_automation   -> cognito, cognito_backup
```

## 2. Modulkatalog (stabile Namen)

Katalog-Autorität: `module_builder/catalog.py` — **stabile Namen = Terraform-
Modulnamen aus main.tf** (Verzeichnis-Name intern; `sqs_worker` liegt im
Verzeichnis `sqs-worker`):

`api, cloudtrail, cognito, cognito_backup, cognito_backup_automation, dynamodb,
iam, lambda, monitoring, sqs, sqs_worker`

Eigenständig verwendbar (keine Deps): `dynamodb, sqs, cognito, cloudtrail,
cognito_backup`.

## 3. CLI-Bedienung

```bash
# Volle Auswahl = Preset-Verhalten (unverändert):
python -m module_builder build --target ./generated/my-orders \
  --project-name my-orders --preset complete

# B1: freie Auswahl (alle Deps explizit — keine stille Ergänzung):
python -m module_builder build --target ./generated/custom-orders \
  --project-name custom-orders --modules dynamodb,sqs,iam,lambda

# Einzelmodul (unabhängig verwendbar):
python -m module_builder build --target ./generated/db-only \
  --project-name db-only --modules dynamodb --validate
```

**Regeln (fail-closed):**
- `--modules` und `--preset` schließen sich gegenseitig aus (argparse-Exit 2).
- Unbekannte Module → Abbruch mit vollständiger Liste verfügbarer Namen.
- Doppelte Module → Abbruch.
- Fehlende Pflichtabhängigkeiten → Abbruch mit **vollständiger Diagnose je
  Modul** („'lambda' benötigt: dynamodb, iam, sqs (fehlt: …)") und Hinweis auf
  B2. **Keine automatische Ergänzung** — bewusste B1-Regel.

## 4. Generierungslogik (auswahlgetrieben)

- **Nur gewählte Modulverzeichnisse** werden kopiert.
- **main.tf** wird aus Blöcken neu komponiert (Block-Splitter mit Brace-Matching,
  fail-closed bei nicht geschlossenem Block): `locals`/`provider` immer;
  `module X` nur bei Auswahl; `resource`/`moved`/`output` nur wenn ALLE
  `module.*`-Referenzen ausgewählt sind (Seed-Ressource → braucht dynamodb;
  moved-Blöcke → brauchen ihre Backup-Module).
- **variables.tf** wird auf die erforderlichen Variablen gefiltert (immer:
  `project_name`, `aws_region`, `tags`; modul-zugeordnet: Seed-, Monitoring-,
  Backup-Schalter; projektname-Default-Substitution bleibt).
- **outputs.tf** wird referenzbasiert gefiltert (nur Outputs auf gewählte Module).
- **Lambda-Artefakte/Quellen nur bei Bedarf:** `lambda.zip` + `lambda/src` +
  `build_zip.py` nur bei `lambda`/`sqs_worker`; `cognito_backup.zip` + Package +
  Handler + `build_cognito_backup_zip.py` nur bei `cognito_backup_automation`;
  Seed-Dateien nur bei `dynamodb`.
- **Policy-Gate** wird **immer** mitgeliefert (unverändert, Projektnamen-
  substituiert — keine Abschwächung).
- **Manifest:** `"preset": "custom"` + `"modules": [<sortierte Auswahl>]`.

**Bestehendes Verhalten erhalten:** `--preset complete` läuft weiterhin über den
verbatim-Pfad (byte-identisch zum Foundation-Stand); `--validate`, `--force`
(nicht-leerer Zielordner wird ohne `--force` abgelehnt; fremde Dateien bleiben
unberührt) und Determinismus unverändert.

## 5. Testresultate (alle real ausgeführt, 2026-10-18)

| Prüfung | Ergebnis |
|---|---|
| Builder-Unit-Tests (44: 30 Bestand + 14 B1-neu: Einzelmodul, Kombination, transitive/fehlende Deps, unbekannt/doppelt, keine stille Ergänzung, Vollauswahl ≡ Complete, Manifest, Determinismus, Sauberkeit, CLI) | **44/44 PASS** |
| Live `--modules dynamodb --validate` (15 Dateien) | terraform fmt/init/validate PASS |
| Live `--modules dynamodb,sqs,iam,sqs_worker --validate` (31 Dateien) | PASS |
| Live Vollauswahl (11 Module) `--validate` | PASS |
| Live Fail-closed (Deps/Duplikat/Unbekannt/MutEx) | korrekte Abbrüche |
| Äquivalenz Vollauswahl ≡ Preset complete (Modul-/Variablen-/Output-Mengen) | identisch ✓ |
| Installer-Regression | **129/129 PASS** |
| Lambda-Regression | **76/76 PASS** |
| Secrets/States/Plans im Zielordner | keine ✓ |

## 6. Einschränkungen

1. **Keine Abhängigkeitsauflösung** (bewusst, B2): Deps müssen explizit genannt
   werden; die Fehlermeldung listet sie vollständig.
2. **Namen sind Blocknamen** (z. B. `sqs_worker`, nicht Verzeichnis `sqs-worker`)
   — in der Unknown-Error-Meldung vollständig aufgelistet.
3. Bei **unvollständiger Vollauswahl** (z. B. ohne `cognito_backup`) entfallen
   zugehörige Variablen/Outputs/moved-Blöcke bewusst — ein späteres ergänzendes
   Nachbauen in denselben Ordner per `--force` ist möglich, aber der
   `--force`-Schutz gehört zur Freigabe.
4. `terraform fmt -check` auf generierten Custom-Projekten ist live verifiziert;
   der Block-Splitter setzt balancierte `${…}`-Interpolationen voraus
   (fail-closed bei nicht geschlossenem Block).

## 7. Offene Punkte (B2-Kandidaten)

- **B2:** automatische Abhängigkeitsauflösung (Dep-Closure) hinter expliziter
  Opt-in-Flag; anschließend evtl. Transitäts-Hinweise im Manifest.
- Preset `minimal`/weitere Presets auf Katalog-Basis.
- S3-Artefakt-Sourcing; `cognito_backup`-Pfad auf `var.filename`.

## 8. Git

Implementierung + Tests + Doku in einem Commit auf `main`; Git CLEAN danach;
keine Release-Tags.
