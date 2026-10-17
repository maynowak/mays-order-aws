# MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01

**Checkpoint:** MAYS-ORDERS-MODULE-BUILDER-FOUNDATION-01
**Datum:** 2026-10-17
**Baseline:** Remote main `3e10fb7` · Release `v0.5.0-rc.2`
**Scope:** Python-CLI-Builder, der aus den bestehenden Mays-Orders-AWS-Komponenten eine eigenständige Terraform-Bereitstellung erzeugt. **Kein Terraform-Meta-Modul, kein GitHub-Sourcing.**
**Status:** IMPLEMENTED / VERIFIED — 23/23 Builder-Tests, Live-Build mit terraform-Validierung PASS, 129/129 Installer- + 76/76 Lambda-Regression, Git CLEAN

## 1. Builder-Architektur

```text
python -m module_builder build --target <ZIEL> --project-name <NAME> [--preset complete] [--force] [--validate]

module_builder/
├── __main__.py      # python -m Entry-Point
├── cli.py           # argparse (build, presets) — Installer-Konventionen
├── spec.py          # Preset-Registry: was 'complete' kopiert (Single Source of Truth)
├── builder.py       # Kern: Phase A verify (fail-closed) → Phase B execute (allowlist-copy)
└── validation.py    # optional --validate: terraform fmt -check, init -backend=false, validate
```

**Sicherheitsmodell:**
- **Phase A (verify):** ALLE Quell-Inputs werden geprüft, BEVOR geschrieben wird. Fehlt ein Artefakt → Abbruch mit klarer Meldung + Lösungshinweis (`cd lambda && python3 build_zip.py`); kein Partial-Target, **keine Dummy-Artefakte**.
- **Phase B (execute):** ausschließlich Allowlist-Kopien (`*.tf`, `README.md`, deklarierte Artefakte/Quellen/Seed-Dateien). Dateien mit State-/Plan-/Lock-/Credential-Mustern werden prinzipbedingt nie kopiert.
- **Zielordner-Schutz:** nicht-leeres Ziel ohne `--force` → Abbruch. Mit `--force` werden nur Builder-eigene Dateien überschrieben; fremde Dateien bleiben unberührt, gelöscht wird nie.
- **Keine AWS-Mutationen:** der Builder selbst kontaktiert kein AWS; `--validate` ist read-only (`fmt -check`, `init -backend=false`, `validate`). Kein apply/destroy, keine State-Migration.

## 2. CLI-Bedienung

```bash
# Verfügbare Presets listen
python -m module_builder presets

# Eigenständige Bereitstellung erzeugen (mit terraform-Validierung)
python -m module_builder build \
  --target ./generated/my-orders \
  --project-name my-orders \
  --preset complete --validate

# Nicht-leeren Zielordner überschreiben (nur Builder-eigene Dateien)
python -m module_builder build --target ./generated/my-orders --project-name my-orders --force
```

Validierung des Projektnamens spiegelt exakt die Terraform-Regex
`^[a-z0-9][a-z0-9-]*$` (mind. 3 Zeichen) aus `variables.tf`.

## 3. Generierte Verzeichnisstruktur (Live-Build, 56 Dateien)

```text
my-orders/
├── terraform/
│   ├── versions.tf                # ← aus main.tf extrahiert (required_version/providers)
│   ├── main.tf                    # Root-Verdrahtung (11 Module, Seed, locals, provider)
│   ├── variables.tf               # project_name-Default = gewählter Name
│   ├── outputs.tf                 # 15 Outputs (verbatim)
│   ├── terraform.tfvars.example   # Beispiel-Konfiguration
│   ├── README.md                  # Kopie der Modul-Doku (terraform/README.md)
│   └── modules/<11 Module>/*.tf   # api, cloudtrail, cognito, cognito_backup,
│                                  # cognito_backup_automation, dynamodb, iam, lambda,
│                                  # monitoring, sqs, sqs-worker
├── lambda/
│   ├── dist/lambda.zip            # Artefakt (sha256 b1018a3b… = RC-Hash)
│   ├── dist/cognito_backup.zip    # Artefakt (492b0c54…)
│   ├── src/*.py                   # Quelle (Reproduzierbarkeit)
│   └── build_zip.py               # Rebuild: cd lambda && python3 build_zip.py
├── database/seed/                 # Demo-Seed (opt-in via var.seed_example_data)
├── scripts/seed_orders.py
├── README.md                      # generiert (Quickstart, Privacy BLOCKED, Backend-Hinweis)
└── module-builder.manifest.json   # Provenance: Preset, Projekt, Dateien, Artefakt-Hashes
```

**Keine Abhängigkeit zum Quell-Repository:** Modul-Quellen bleiben relativ
(`source = "./modules/…"`), kein `git::`, keine Repo-Pfade in .tf-Dateien.
**Backend wird absichtlich NICHT mitgeneriert** (lokaler State; Consumer
konfiguriert sein eigenes Remote-Backend) — `backend.tf` wird nie kopiert.

## 4. Modulabhängigkeiten (beibehaltene Root-Verdrahtung)

```text
dynamodb ─┬→ iam (table/gsi ARNs)        ─┬→ lambda (role, table, queue_url)
          │                              │
sqs ──────┴→ iam (queue_arn)             │   lambda.zip (path.root/../../lambda/dist)
sqs → sqs-worker (queue arn/name, table, lambda.zip)
cognito → api (pool endpoint, client id) ← lambda (invoke_arn, function_name)
api + lambda + dynamodb → monitoring (api_id, stage, function, table)
cognito → cognito_backup → cognito_backup_automation (pool, bucket, name)
dynamodb → terraform_data.seed_orders (opt-in, seed file + scripts/seed_orders.py)
```

Pfad-Verträge bleiben durch Layout-Spiegelung (terraform/ + lambda/ + database/ +
scripts/ im Ziel) intakt — inklusive der Modul-internen
`${path.root}/../lambda/dist/cognito_backup.zip`-Referenz (cognito_backup).

## 5. Testresultate (alle real ausgeführt, 2026-10-17)

| Prüfung | Ergebnis |
|---|---|
| Builder-Unit-Tests (`module_builder/tests/test_module_builder.py`, 23 Tests: fail-closed Artefakt/Präset/Name/Zielordner, Force schützt Fremddateien, Layout, versions.tf-Split, Name-Substitution, keine backend.tf/state/plan/lock, keine Repo-Referenz, Manifest, README, Determinismus, Transformationen, CLI) | **23/23 PASS** |
| Live-Build `--validate` (Ziel `/tmp/opencode/generated/my-orders`) | **PASS** — 49 Dateien, terraform `fmt -check`, `init -backend=false`, `validate` GREEN |
| Artefakt-Integrität | lambda.zip `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b` = Quell-Hash (RC-Artefakt) |
| Wiederholbarkeit | Zwei Builds → Bäume identisch (Diff zuvor zeigte nur terraform-init-Artefakte des `--validate`-Laufs, keine Builder-Ausgaben) |
| Regression Installer (inkl. collision/guide/artifact/parallel/discovery/runner) | **129/129 PASS** |
| Regression Lambda | **76/76 PASS** |
| AWS unverändert | **BESTÄTIGT** — kein apply/destroy/init-mit-Backend, kein AWS-API-Kontakt durch den Builder |

## 6. Einschränkungen

1. **MVP nur `--preset complete`** — freie Modulauswahl folgt in Plan B.
2. **`cognito_backup.zip` hat keine .py-Quelle im Repo** (historisch gebaut); der
   Builder kopiert das freigegebene Artefakt und dokumentiert den Hash im
   Manifest — Rebuild nur über die historische Freigabe (bekannte Lücke, Plan-B-Kandidat).
3. **Terraform-Namens-Quirk:** die Quell-Regex `^[a-z0-9][a-z0-9-]*$` erlaubt
   einen trailing Bindestrich, obwohl der Terraform-Fehlertext mehr behauptet —
   der Builder spiegelt die Regex exakt (keine heimliche Verschärfung).
4. **`--validate` erzeugt terraform-init-Artefakte** (`.terraform/`, lock) im
   Ziel — erwartetesterraform-Verhalten, keine Builder-Ausgaben (Determinismus
   exkludiert sie korrekt).
5. Policy-Gate/Installer werden nicht mitgeneriert (MO-spezifische Ops-Tools);
   generierter README verweist auf Freigabe-Disziplin. Collision-Preflight
   liegt im MO-Installer, nicht im generierten Projekt.
6. Privacy-Produktivaktivierung bleibt **BLOCKED** (im generierten README + Manifest verankert).

## 7. Offene Punkte für Plan B

1. **Freie Modulauswahl** (`--modules dynamodb,api,…`) auf Basis von `spec.py` —
   Abhängigkeitsprüfung (iam braucht dynamodb+sqs; api braucht lambda+cognito) fail-closed.
2. `sqs`/`sqs-worker`-Modul-Härtung (eigene Variablen/Outputs) für Einzelnutzung.
3. **S3-Artefakt-Sourcing** (`s3_bucket`/`s3_key` als `filename`-Alternative) —
   entkoppelt generierte Projekte vom lokalen Zip-Pfad.
4. `cognito_backup`-Pfad auf `var.filename` umstellen (Muster: lambda-Modul).
5. Preset `minimal` (ohne cloudtrail/monitoring/backup) + Preset-Versionsierung
   im Manifest.
6. Integration in den Installer (`installer` ruft Builder) oder als eigenständiges
   Produktions-Tool mit CI-Checks (fmt/validate je Preset).

## 8. Git

Implementierung + Doku in **einem Commit** auf `main` (keine neuen Release-Tags),
Git-Status danach CLEAN. Details im Abschlussbericht des Chat-Protokolls.
