# MO-BUILDER-INSTALLER-UPGRADE-READINESS-01

**Upgrade-Fähigkeit von Mays-Orders-AWS Builder und Installer — Analyse**

**Datum:** 2026-11-03
**Branch:** `main` · **Referenz:** `f597d1486292f7bd8bcaa7ac3e96276f091f9a07` (`f597d14`)
**Modus:** ausschließlich Analyse (keine AWS-Operationen, keine Codeänderungen, kein Commit, kein Push)
**RIS:** nur als Integrationsbeispiel betrachtet, nicht verändert

---

## 1. Executive Summary

**Der Installer kann heute einen bestehenden Stack aktualisieren — aber nur als „roher"
Terraform-Apply gegen den vorhandenen State, ohne Upgrade-Begriff, Versionsbindung oder
Schutz vor Datenverlust durch Replacement.** Der Builder erzeugt eigenständige Projekte und
kann sie mit `--force` überschreiben, hat aber **keinen Upgrade-Modus** (kein Diff, keine
Konfigurationsübernahme, keine Modulversionen).

| Bereich | Reifegrad |
|---|---|
| Plan/Apply gegen bestehenden State (technisch) | **IMPLEMENTED** (Terraform + `plan --remote` + Manifest) |
| Schutz vor versehentlichem Destroy | **IMPLEMENTED** (Deploy-Safety blockt Destroys) |
| Schutz vor Replacements (Datenverlust) | **PARTIALLY** (nur Warnung, kein Block) |
| Erkennung „installiert vs. neu" | **PARTIALLY** (Namens-/Backend-Heuristik, kein State-Read) |
| Erkennung der installierten Version | **NOT IMPLEMENTED** (Version kommt aus CLI, nicht aus dem Stack) |
| Kompatibilitätsprüfung / Versionsvergleich | **NOT IMPLEMENTED** (Klassen vorhanden, aber ungenutzt) |
| Change-Klassifikation (safe/critical) | **PARTIALLY** (Summary + 2 Regeln) |
| Wiederaufnahme/Resume nach Fehler | **NOT IMPLEMENTED** |
| Builder-Upgrade (Diff, Config-Erhalt) | **NOT IMPLEMENTED** |

**Dokumentationslücke:** `docs/INSTALLER-LIFECYCLE.md` beschreibt `OwnershipAnalyzer`,
`TagSet` und „HARD STOP on MIGRATION_REQUIRED" als vorhanden; der Code definiert diese
Klassen, **verwendet sie aber nicht** (tote Upgrade-Primitive).

**Abschlussstatus:** `UPGRADE READINESS ANALYZED — READY FOR DEVELOPMENT PLANNING`

---

## 2. Builder-Fähigkeitsmatrix

| Fähigkeit | Status | Evidence / Begründung |
|---|---|---|
| Modulversionierung | **NOT IMPLEMENTED** | `module_builder/__init__.py:15` (`__version__ = "0.1.0"` nur für den Builder); `module_builder/catalog.py:29-44` enthält keine Modulversionen, nur `dir`/`deps` |
| Modulabhängigkeiten | **IMPLEMENTED** | `catalog.py:126-196` (`validate_selection_closure`, `resolve_with_deps`, fail-closed) |
| Konfigurationsdateien | **PARTIALLY IMPLEMENTED** | Erzeugt `terraform.tfvars.example` und `README`; **kein** Erhalt einer bestehenden `terraform.tfvars` |
| Änderungen an Modulparametern | **PARTIALLY IMPLEMENTED** | Parameter werden aus dem Quell-Root kopiert (`builder.py:556-600`); unbekannte/entfernte Variablen führen erst beim `terraform plan` zum Fehler |
| Kompatibilität älterer Konfigurationen | **NOT IMPLEMENTED** | Kein Vergleich mit einem früheren Build (Manifest wird überschrieben) |
| Generierung neuer Terraform-Konfigurationen | **IMPLEMENTED** | `build()`/`build_module()` (`builder.py:419-690`, `845-1075`); `--force` schützt fremde Dateien (`builder.py:8-9, 525-529`) |
| Entfernte/umbenannte Module | **NOT IMPLEMENTED** | Katalog statisch; Builder **löscht nie** Dateien (kein `rmtree`/`unlink`); alte Modulverzeichnisse bleiben liegen |
| Umgang mit bestehenden Ressourcen | **NOT IMPLEMENTED** | Builder hat bewusst keinen AWS-/State-Bezug (`spec.py:15-18`; `builder.py:665`: „backend not included") |
| Migrationsanforderungen | **NOT IMPLEMENTED** | keine Migrationslogik |
| Provenance | **PARTIALLY IMPLEMENTED** | `module-builder.manifest.json` (`builder.py:645-680`) mit `builder_version`, `preset`, `modules`, `project_name`, `generated_at`, Quell-Commit, Artefakt-Hashes, Dateiliste — **kein** Bezug auf ein Vorgänger-Build |
| Upgrade-/Diff-Modus | **NOT IMPLEMENTED** | kein `--upgrade`, kein Vergleich zweier Manifeste |

**Fazit Builder:** brauchbar für **Neu-Generierung** (inkl. `--force`), nicht für
**kontrollierte Upgrades** bestehender generierter Projekte. Zwei Lücken sind sicherheitsrelevant:
kein Erhalt lokaler Konfiguration und kein Entfernen veralteter Moduldateien.

---

## 3. Installer-Fähigkeitsmatrix

| Fähigkeit | Status | Evidence / Begründung |
|---|---|---|
| Erkennung bestehender Installation | **PARTIALLY IMPLEMENTED** | `validate` prüft Backend-Heuristik + AWS-Namenskollisionen (`context.py:299-315`, `561-605`, `639-716`); **kein** State-Read, keine Ressourcenzählung |
| Erkennung des vorhandenen Terraform-State | **PARTIALLY IMPLEMENTED** | `remote_state_lifecycle.py:114-136` (Backend-Erkennung), `:158-169` (nur **lokale** State-Dateien); Remote-State wird erst durch `terraform init/plan` gelesen |
| Backend-/Workspace-Zuordnung | **IMPLEMENTED** | `backend.tf`-Vertrag (`installer/core/plan_contract.py`), Workspace = `project_name`, fail-closed (`context.py`, `runner.py:413-471`), `env:/<ws>/tfstate` |
| Installation vs. Upgrade | **NOT IMPLEMENTED** | kein Modus-Unterschied; derselbe `deploy`-Pfad |
| Terraform-Plan für bestehende Ressourcen | **IMPLEMENTED** | `plan --remote` refresht den State; Plan zeigt Update/Replace/Delete |
| Plan-Manifest / Versionsbindung | **PARTIALLY IMPLEMENTED** | Manifest bindet Account/Projekt/Environment/Region/Workspace/Backend/State-Key/Operation/SHA-256 (`installer/core/plan_manifest.py`); **`git_commit` ist derzeit `null`** (CLI übergibt keinen), **keine** MO-Version/`from→to` |
| Policy Gate bei UPDATE | **PARTIALLY IMPLEMENTED** | Gate prüft ressourcenweise auch `update`/`replace` (`validate-plan.py:166` ff.); Namespace-/Tag-/Shape-Regeln greifen, aber **kein** Replacement-Block |
| Policy Gate bei REPLACE | **NOT IMPLEMENTED (als Block)** | Kein `replace`-Verbot; nur generische Shape-Checks |
| Schutz bestehender Ressourcen | **PARTIALLY IMPLEMENTED** | Deploy-Safety blockt **Destroys** (`plan_analysis.py:278-296`), **Replacements nur WARNING** (`:298-310`); kein Schutz für Datenressourcen (DynamoDB/S3/Cognito) |
| Umgang mit Datenmigrationen | **NOT IMPLEMENTED** | Keine Datenmigration (nur State-Migrations-Guard `state_guard.py`) |
| Idempotenz | **IMPLEMENTED (Terraform)** | Plan/Apply idempotent; Installer selbst fügt nichts hinzu |
| Fehlerbehandlung | **PARTIALLY IMPLEMENTED** | fail-closed Gates (Manifest, Policy, Safety, Cleanup); keine Rollback-/Resume-Logik |
| Wiederaufnahme unterbrochener Upgrades | **NOT IMPLEMENTED** | kein Resume/Retry (`grep resume/retry` → nur GUI-Text); erneuter Lauf = neuer Plan |
| **Deploy als Upgrade-Werkzeug** | **PARTIALLY USABLE** | ja, wenn Plan gegen den **bestehenden** State erzeugt wird (`plan --remote`), Manifest gültig ist und der Plan-Review Replacements/Destroys prüft; ohne Versions-/Replace-Schutz ist es „manuell kontrolliert" |

**Fazit Installer:** Der technische Upgrade-Pfad existiert (Plan gegen Remote-State →
Manifest → Deploy), ist aber nicht als Upgrade modelliert und schützt nicht vor den
gefährlichsten Fällen (Tabellen-/Bucket-/Pool-Replacement, fehlende Versionsbindung).

---

## 4. Upgrade-Szenarien (A–J)

Legende: ✅ unterstützt · 🟡 teilweise · ❌ nicht implementiert · ⚠️ Risiko

| # | Szenario | Unterstützt? | Technisch möglich? | Risiken | Erweiterungen | Testbarkeit |
|---|---|---|---|---|---|---|
| A | Bestehende Installation **ohne Änderungen** (No-op) | 🟡 | ja | keiner; No-op wird nur durch Plan-Review erkannt (kein „0 changes"-Gate) | No-op-Erkennung + Manifest „no changes" | lokal/AWS leicht |
| B | Neue **optionale Ressourcen** (z. B. DLQ, GSI3, Alarm) | ✅ | ja (RC4-Neuaufbau belegt) | Plan-Umfang, Tag-/Policy-Regeln | Change-Klassifikation | AWS (Plan/Apply auf Bestand) |
| C | **Änderung bestehender** Ressourcen (Attribute, Retention, Visibility) | 🟡 | ja (Terraform-Update) | unbeabsichtigte Nebeneffekte (SQS-Retry, Lambda-Hash) | Diff-Report „was ändert sich fachlich" | AWS |
| D | **Neue/veränderte Modulparameter** | 🟡 | ja | unbekannte Variablen ⇒ Plan-Fehler; entfernte Variablen ⇒ Plan-Fehler; keine Vorabprüfung | Variable-Schema-/Kompatibilitätscheck | lokal (validate) |
| E | **Datenbank-Schemaänderung** (GSI, Attribute, Key) | 🟡 | GSI-Add ja; Key-/Tabellenwechsel ⇒ **Replace** | **Datenverlust** bei Replace; keine Migration/Backfill | Replace-Block für `aws_dynamodb_table`, Migrations-Gates | AWS, aufwändig |
| F | **IAM-Rollen/-Policies ändern** | ✅ | ja | Policy-Inhalte sind im Plan oft „known after apply" → Gate prüft nur Namen | inhaltliche Prüfung wo plan-bekannt; Wildcard-Regel | lokal/AWS |
| G | **Externer Cognito-Pool** | 🟡 | Builder: `external_cognito` (Orders-Service-Preset); Complete-Preset verwaltet eigenen Pool | Wechsel MANAGED→EXTERNAL **löscht** den verwalteten Pool (dokumentiert) | Installer-Flag/Plan-Gate für Pool-Replacement | AWS, riskant |
| H | **CloudFront** | ❌ (nicht Teil des MO-Stacks) | n/a | — | — | nicht anwendbar (RIS-Domäne) |
| I | **Upgrade mit erforderlichem Replacement** | ❌ (kein Block) | ja, aber gefährlich | Tabellen-/Bucket-/Pool-Replace ⇒ Datenverlust; nur WARNING | P0: Replace-Block + explizites `--allow-replace <address>` | AWS, Test mit Wegwerf-Stack |
| J | **Fehlgeschlagenes/unterbrochenes Upgrade** | ❌ | manuell (erneuter Plan/Apply) | inkonsistenter Zwischenstand, Orphans | Resume/Checkpoint, „upgrade status"-Report, Recovery-Runbook | AWS, Fehlerinjektion |

---

## 5. Sicherheits- und Kompatibilitätslücken

| ID | Lücke | Schwere | Bewertung |
|---|---|---|---|
| G-01 | **Kein Replacement-Block** für zustandsbehaftete Ressourcen (DynamoDB-Tabelle, S3-Buckets, Cognito-Pool, SQS) | **hoch** | Deploy-Safety meldet Replacements nur als WARNING (`plan_analysis.py:298-310`); Policy Gate blockt sie nicht |
| G-02 | **Keine Versionsbindung**: Manifest `git_commit=null`, keine MO-Version, keine `from→to`-Version | hoch | Ein Plan kann mit beliebigem Code-Stand erzeugt und später angewendet werden; „welche Version läuft?" ist nicht beantwortbar |
| G-03 | **Keine Erkennung der installierten Version** | hoch | `--deployment-version` ist ein CLI-Freitext (Default `0.1.0`, `context.py:125`); kein Tag/Output im Stack |
| G-04 | **Kompatibilitätsprüfung ungenutzt** | mittel | `DevelopmentState.compare` (`deployment_identity.py:139`) und `VersionComparison` existieren, werden aber nirgends aufgerufen |
| G-05 | **Ownership-Analyse ungenutzt** | mittel | `OwnershipAnalyzer`/`ResourceOwnership` (`deployment_identity.py:742-830`) und `TagSet` (`:387`) sind tote Primitive; Docs (`INSTALLER-LIFECYCLE.md:474-481`) behaupten Nutzung |
| G-06 | **Kein Datenmigrations-Konzept** | hoch | GSI-/Attribut-Migrationen (Backfill) fehlen; Legacy-`running`-Backfill ist bekannt offen |
| G-07 | **Kein No-op-/Drift-Gate** | mittel | „0 changes" wird nicht erzwungen; Drift wird nur im Plan sichtbar |
| G-08 | **Builder ohne Upgrade-Semantik** | mittel | `--force` überschreibt Builder-Dateien ohne Diff/Backup; lokale `terraform.tfvars` bleiben unangetastet (gut), aber Änderungen an Variablen werden nicht gemeldet; veraltete Modulordner bleiben |
| G-09 | **Kein Resume** | mittel | Nach Teilfehler bleibt der State-Zwischenstand; kein Checkpoint, kein Wiederaufnahme-Report |
| G-10 | **Policy Gate prüft Policy-Inhalte nur, wenn plan-bekannt** | niedrig | dokumentiert (E2B), IAM-Wildcards in `aws_iam_policy` sind im Plan meist unknown |

---

## 6. Bereits vorhandene Wiederverwendungsmöglichkeiten

| Baustein | Wiederverwendung für Upgrades |
|---|---|
| `plan --remote` + Manifest (Account/Region/Workspace/Backend/SHA-256) | Upgrade-Plan mit Identitätsbindung; nur noch `from/to`-Version ergänzen |
| Deploy-Safety (`evaluate_plan_safety`) | Blockt Destroys; um Replace-Regeln erweiterbar |
| Policy Gate (`validate-plan.py`) | Namespace/Tag/Shape auch für Updates; um Replace-Regeln erweiterbar |
| `DevelopmentState.compare` / `VersionComparison` | fertige Versionslogik (SAME/PATCH/MINOR/MAJOR/MIGRATION_REQUIRED) — nur verdrahten |
| `OwnershipAnalyzer` / `TagSet` | Ressourcen-Ownership könnte aus Tags/ARNs klassifiziert werden (aktuell ungenutzt) |
| `PlanMetadata` / `PlanDiscovery` (Version/Phase im Dateinamen) | Basis für Upgrade-Reporting und Plan-Historie |
| Cleanup-Vertrag (`cleanup_contract.py`, Runbook) | Rückbau-/Recovery-Regeln bereits definiert |
| Builder-Manifest (`module-builder.manifest.json`) | Provenance + Dateiliste als Diff-Basis für einen Builder-Upgrade-Modus |

---

## 7. Priorisierte Roadmap

### P0 — Sicherheits- und Datenverlustschutz
1. **Replace-Gate für zustandsbehaftete Ressourcen**: `evaluate_plan_safety` bzw. Policy Gate
   blockiert `replace`/`delete` für `aws_dynamodb_table`, `aws_s3_bucket`, `aws_cognito_user_pool`,
   `aws_sqs_queue`, sofern nicht explizit per `--allow-replace <address>` (mit Grund/Manifest)
   freigegeben.
2. **Versions-/Commit-Bindung**: `git_commit` + MO-Version (`installer_version`) im Manifest
   füllen; Manifest zusätzlich `target_version`.
3. **No-op- und Drift-Gate**: Plan mit Änderungen nur nach expliziter Bestätigung; „0 changes"
   als eigener Status.

### P1 — Upgrade-Grundfunktionen
4. **Upgrade-Modus** (`plan --upgrade --from <version> --to <version>`), der
   `DevelopmentState.compare` nutzt und bei `MIGRATION_REQUIRED`/`INCOMPATIBLE` **hart stoppt**.
5. **Change-Klassifikation** im Plan-Report: `safe` / `review` / `critical` (Destroys, Replacements,
   IAM-Erweiterungen, Datenressourcen).
6. **Installed-Version im Stack**: Tag/Output (z. B. `MoVersion`) beim Apply setzen, von
   `Upgrade`-Check lesen (read-only über `terraform output`/AWS-Tags).

### P2 — Komfort und Automatisierung
7. **Builder-Upgrade-Modus**: Manifest-Diff (builder_version, modules, Dateien), Bericht
   „hinzugefügt/entfernt/geändert", optional `--prune` (nur Builder-eigene Dateien),
   `terraform.tfvars`-Erhalt + Warnung bei Variablenänderungen.
8. **Upgrade-Report** (Markdown/JSON) aus Plan-JSON: Änderungen nach Modul, Risiko, offene Punkte.
9. **Policy-Gate-Erweiterung**: IAM-Policy-Inhalte prüfen, wenn plan-bekannt; Wildcard-Regel
   auch für `aws_iam_policy`.

### P3 — Erweiterte Migration und Recovery
10. **Datenmigrationen** (GSI-Backfill, Attribut-Migration, Legacy-`running`): eigenes, idempotentes
    Migrationskommando mit Dry-Run und Fortschrittsreport.
11. **Resume/Checkpoint** für unterbrochene Deploys (Plan-ID, State-Zwischenstand, Fortsetzen
    nur mit demselben Manifest).
12. **Rollback-Plan** (Restore aus Backup/PITR) und Post-Upgrade-Verifikationssuite.

---

## 8. Empfehlung für einen minimalen Upgrade-PoC

**Ziel:** Nachweis, dass ein bestehender MO-Stack mit dem vorhandenen Installer auf `f597d14`
aktualisiert werden kann, ohne Datenverlust.

**Voraussetzungen (separater Checkpoint, AWS-Schreibfreigabe):**
- Wegwerf-Projekt (z. B. `mays-orders-rc5-upgtest`) mit eigenem Workspace;
- Ausgangsstand aus älterem Commit (z. B. `086a8be`) gebaut/deployed;
- danach `plan --remote` mit `f597d14`:
  - erwartet: GSI3-Add (in-place), DLQ-Create, Lambda-Hash-Updates (API+Worker),
    IAM-Ergänzung, +1 Alarm; **0 Destroys**, **0 Replacements**;
- Apply des gespeicherten Plans, danach **No-op-Plan** (`0/0/0`);
- Stichproben: Tabelle intakt, Queue-/Lambda-Attribute, Alarm;
- danach Destroy + State-Cleanup wie im Cleanup-Vertrag.

**Akzeptanzkriterien:**
- Plan enthält 0 Destroy/Replace;
- Manifest gültig (Account/Region/Workspace/SHA-256);
- No-op nach Apply;
- keine RIS-/Shared-Änderung;
- vollständiger Rückbau.

**Nicht Teil des PoC:** Datenmigration, externe Cognito-Pools, Builder-Upgrade.

---

## 9. Referenzen (Code)

| Thema | Datei |
|---|---|
| Builder-Katalog/Abhängigkeiten | `module_builder/catalog.py:29-196` |
| Builder-Build/Force/Manifest | `module_builder/builder.py:419-690`, `845-1075` |
| Builder-Preset/Backend-Ausschluss | `module_builder/spec.py:15-62` |
| Installer-Validate-Checks | `installer/core/context.py:299-315`, `561-716` |
| Remote-State-Heuristik | `installer/core/remote_state_lifecycle.py:114-169` |
| Plan-Metadaten/Discovery | `installer/core/deployment_identity.py:243-360`, `662-739` |
| Dormante Upgrade-Primitive | `installer/core/deployment_identity.py:139-156`, `387-470`, `742-830` |
| Deploy-Safety (Destroy/Replace) | `installer/terraform/plan_analysis.py:278-310` |
| Plan-Manifest | `installer/core/plan_manifest.py` |
| Policy Gate | `terraform/policy/validate-plan.py:160-260` |
| Remote-Plan/Init/Timeouts | `installer/cli/main.py:548-616`, `installer/terraform/runner.py` |

---

**Status:** `UPGRADE READINESS ANALYZED — READY FOR DEVELOPMENT PLANNING`

Keine Implementierung, keine AWS-Operation, kein Commit, kein Push. **STOP.**
