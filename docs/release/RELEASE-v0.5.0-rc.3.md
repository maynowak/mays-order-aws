# Release v0.5.0-rc.3 — Mays-Orders-AWS

> **Engineering Release Dossier · v0.5.0-rc.3**
> *Ein Baukasten wird zum Vertrag: Module Builder, portable IAM und eine RIS-Integration, die im fremden Konto besteht.*

**Release:** v0.5.0-rc.3 (Pre-Release Candidate)
**Datum:** 2026-10-31
**Release-Basis:** v0.5.0-rc.2 → `5cf50a0`
**Tag-Ziel:** Packaging-Commit dieses Dossiers auf `main` (SHA nach Commit: `git log -1 --format=%H`)
**Projekt:** Mays-Orders-AWS · Repository `maynowak/mays-order-aws`
**Integrationsbranch:** `feature/mo-module-contract-ris-dev2-2026` (erhalten, nicht gelöscht)
**Produktive Privacy-Aktivierung:** **BLOCKED** (unverändert)

---

## 1. Release Overview

v0.5.0-rc.3 ist das **Module-Builder- und Integrations-Release**. Es macht aus dem
bisherigen Monolithen einen wiederverwendbaren, vertraglich beschriebenen Terraform-
Baustein und belegt dessen Nutzbarkeit außerhalb dieses Repos: Der
**Mays-Recruiting-Intelligence-System (RIS)**-Consumer hat den gepinnten Builder
in einem **fremden AWS-Testkonto** vollständig durchlaufen — Plan, Apply, Live-Tests
inklusive `SQS → Worker → DynamoDB`, No-Op, Destroy und Cleanup.

**Kernpunkte:** Module Builder mit zwei Presets (`complete`, `orders-service`) ·
frei wählbare Module (`--modules`, `--with-deps`) · Policy-Gate in generierten
Projekten · Orders-Service-Modulvertrag · EXTERNAL-Cognito-Modus · portable
IAM-Boundary · SQS-Wildcard-Policy entfernt (F-03) · deterministische
Lambda-Artefakte · 90 Builder- / 76 Lambda- / 81 Installer-Tests ·
RIS-AWS-E2E bestanden.

## 2. Changes seit v0.5.0-rc.2

49 Commits (46 ohne Merge), gegliedert nach Thema:

### Module Builder
| Commit | Inhalt |
|---|---|
| `995f912` | Foundation: `python -m module_builder`, Preset `complete`, fail-closed Preflight, Manifest mit Artefakt-Hashes |
| `92be267` | Reproduzierbares `cognito_backup.zip` (deterministischer Build) |
| `da80271` | Policy-Gate in generierte Projekte übernommen (`validate-plan.py` + projektspezifische `resource-policy.json`) |
| `c0ac0f1` | B1: freie Modulauswahl `--modules`, Katalog, fail-closed Abhängigkeitsprüfung |
| `0e0ae71` | B2: `--with-deps` transitive Pflicht-Dependencies, deterministisch |
| `736886a` | CLI-Cleanup: totes `--no-policy-check` entfernt |
| `337cdbf`/`2d5cf2d` | Nutzer-Doku für den Modulbau integriert und auffindbar gemacht |

### Terraform-Verträge & Modularisierung
| Commit | Inhalt |
|---|---|
| `5c70374`/`94097e2` | Optionales, count-gated SQS-Recht im IAM-Modul; SQS-Wiring nur bei Auswahl |
| `9ec7f84` | Root-Outputs `sqs_queue_url`, `sqs_queue_arn`, `sqs_worker_lambda_arn` |
| `4f0ab17` | Orders-Service-Modulvertrag (feste 7-Modul-Komposition) |
| `54de18d` | EXTERNAL-Cognito-Modus (MANAGED bleibt Default) |
| `9627eb2` | GAP-02/GAP-06: `sqs_queue_name`-Output + plan-stabiles IAM-SQS-Gate |

### Security & Portabilität
| Commit | Inhalt |
|---|---|
| `ccf22a3`/`a46b189` | IAM-Portabilität FIX-01: Worker-Boundary portable, Builder folgt |
| `f3e78d0` | IAM-Portabilität FIX-02: kein hartcodiertes Konto mehr im Root-Default |
| `a2fb385` | **F-03 behoben:** SQS-Resource-Policy mit `Principal = "*"` entfernt — Zugriff nur über IAM-Identitäts-Policies |

### Release-Vorbereitung RC.3
| Commit | Inhalt |
|---|---|
| `686eb39` … `ca1fa16` | RC.3-Serie P00–P06: Baseline, Merge-Readiness, Merge, Release-Baseline, Builder-Verifikation, RIS-Evidence |

### Hygiene
| Commit | Inhalt |
|---|---|
| `6fd76e4` | Versehentlich committete Plan-Artefakte/State-Reste entfernt, `.gitignore` gehärtet |
| `640f4f0` | `terraform/main.tf` formatiert (Whitespace) |

## 3. Module Builder (Release-Kern)

```bash
# vollständige Standalone-Bereitstellung (11 Module)
python -m module_builder build --target ./out --project-name my-project

# wiederverwendbares Orders-Service-Modul (7 Module)
python -m module_builder build --target ./out --preset orders-service --project-name my-project

# freie Auswahl / mit Pflicht-Dependencies
python -m module_builder build --target ./out --modules dynamodb iam lambda
python -m module_builder build --target ./out --modules lambda --with-deps
```

Eigenschaften:

- **Eigenständig:** kopiert Kindmodule, Root-Wiring und Artefakte; **kein** `backend.tf`,
  **kein** State, **keine** Repo-Abhängigkeit; relative Modulquellen.
- **Fail-closed:** fehlende Artefakte brechen ab, bevor etwas geschrieben wird — keine Dummies.
- **Allowlist-Copy:** nur `*.tf`, deklarierte Artefakte/Quellen, Seed-Dateien; State-/Plan-/Lock-
  Muster werden nie kopiert.
- **Zielschutz:** nicht-leeres Ziel nur mit `--force`, und auch dann werden nur Builder-eigene
  Dateien überschrieben — gelöscht wird nie.
- **Policy-Gate eingebaut:** `terraform/policy/validate-plan.py` + `resource-policy.json`
  (Projektname eingesetzt), Exit 1 blockiert Deployments.
- **Provenance:** `module-builder.manifest.json` mit Builder-Version, Preset, Modulen,
  Quell-Commit, SHA-256 der Artefakte und vollständiger Dateiliste.

## 4. Terraform-Modulverträge

**Preset `complete`** — 11 Module: api, cloudtrail, cognito, cognito_backup,
cognito_backup_automation, dynamodb, iam, lambda, monitoring, sqs, sqs-worker.

**Preset `orders-service`** — feste 7-Modul-Komposition (nicht abwählbar):
Orders-API + Handler, Worker, SQS, eigene DynamoDB-Tabelle, IAM, Cognito.

| Vertrag | Inhalt |
|---|---|
| Inputs (6) | `project_name`, `tags`, `monitoring_enabled`, `log_retention_days`, `lambda_execution_boundary`, `external_cognito` |
| Outputs (20) | API (endpoint/id/stage/authorizer), DynamoDB (name/arn), SQS (url/arn/name), Worker-ARN, Lambda (name/arn/invoke), IAM (role name/arn), Cognito (pool id/arn/endpoint/client/group) |
| Cognito | `null` = MANAGED (eigener Pool), Objekt = EXTERNAL (vorhandener Pool, keine Cognito-Ressourcen) |
| Modul-Modus | lokales Modul, kein Provider-Block, Artefakte über `path.module`, Tag-Parität via `local.default_tags` |
| Nicht im Vertrag | Monitoring, CloudTrail, Cognito-Backups, Seed, Remote-Backend, Policy-Gate-Ausführung (Root des Consumers) |

## 5. IAM-Portabilität

- `lambda_execution_boundary` ist **optional** und defaultet im generierten Modul auf `null`
  (keine konto-spezifische Policy-Vorgabe mehr); Validierung erzwingt bei Setzen das
  ARN-Format `arn:aws:iam::<12 Ziffern>:policy/...`.
- Root-Installation behält die Variable, aber ohne hartcodierten Fremd-Default.
- **Praxisbeleg:** RIS installierte den Stand erfolgreich in Account `262370457690` —
  also in einem Konto, das nicht die Quelle der früheren Defaults ist.

## 6. SQS-Security-Fix F-03

Vorher: `aws_sqs_queue_policy` mit `Principal = "*"` und ohne Condition — jeder Principal
hätte senden/empfangen/löschen dürfen. Jetzt (`a2fb385`): Policy entfernt; Zugriff
ausschließlich über die IAM-Identitäts-Policies der Rollen (Least Privilege).

Bestätigt durch zwei unabhängige Quellen: lokale Prüfung (`Principal` kommt in
`terraform/modules/sqs/main.tf` nur noch im Kommentar vor) und den RIS-Acceptance-Report
(F-03 dort als **RESOLVED (MO-Vertrag)** geführt, nachdem der gepinnte Stand deployt wurde).

## 7. Lambda-Artefakte

| Element | Wert |
|---|---|
| Quelle | `lambda/src/index.py` (Handler `index.handler`, Runtime `python3.14`) |
| Build | `cd lambda && python3 build_zip.py` → `lambda/dist/lambda.zip` |
| SHA-256 (Release-Stand) | `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b` |
| Reproduzierbarkeit | deterministischer Build; Hash im Builder-Manifest je generiertem Projekt |

## 8. RIS-Consumer-Integration

| Element | Wert |
|---|---|
| RIS-Repo | `maynowak/Mays-Recruiting-Intelligence-System` |
| Branch | `feature/mo-module-installer-ris-dev2-2026` @ `73965e3` |
| Builder-Pin | `1dbb0cb` (Legacy-Composite-Pin `5cf50a0`, abgelöst) |
| Integration | `python -m installer.build_mays_orders_module --project-name <p>` → generiertes Modul + `patch_iam_sqs_gate()` |
| Wrapper-Schutz | bricht laut ab, wenn das plan-stabile `count = var.sqs_enabled ? 1 : 0`-Muster fehlt |

**Code-Identität zum Release:** `git merge-base --is-ancestor 1dbb0cb main` ✔;
`git diff -w 1dbb0cb..main -- terraform/ lambda/ module_builder/ installer/ scripts/`
ist **leer** (ohne `-w` nur 10+/10− Whitespace in `terraform/main.tf`).

## 9. RIS-AWS-E2E-Evidence

`docs/reports/RIS-MO-RC-01-CONSUMER-ACCEPTANCE.md` (2026-10-30), Account
`262370457690`, Region `eu-central-1`, Workspace `ris-dev2`:

| Test | Ergebnis |
|---|---|
| Init (Backend S3 + DDB-Lock) | PASS (Exit 0, 21 Module, aws 6.67.0) |
| Plan | PASS — **169 add, 0 change, 0 destroy**, kein Replace |
| Apply | PASS (Exit 0, 183 Ressourcen) |
| Post-Deploy No-Op | PASS — „No changes" |
| Live-Tests T-01…T-07 | **7/7 PASS** (Cognito, 401-Enforcement, Handler, Reader, 12 DDB-Tabellen, 6 Queues) |
| **SQS → Worker → DynamoDB** | **PASS** — Status `PENDING → CONFIRMED`, Queue danach leer |
| Destroy | PASS (Exit 0) |
| Cleanup | CLEAN — 0 Laufzeitressourcen; nur Backend (S3-Bucket, Lock-Tabelle) erhalten |

Evidence-Dateien: `docs/reports/evidence/RIS-MO-RC-01-2026/{03,05,06,08,09}-*.txt`,
`plan-ris-dev2.txt`, `tf-outputs.json`.

## 10. Lokale Regression (2026-10-31 erneut ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| Lambda Unit Tests | **76/76 PASS** (`PYTHONPATH=src python3 -m unittest discover -s tests`) |
| Module Builder Tests | **90/90 PASS** |
| Installer Unit Tests | **81/81 PASS** |
| `terraform init -backend=false` | Exit 0 |
| `terraform validate` | PASS |
| `terraform fmt -check -recursive` | Exit 0 |
| Generiertes `orders-service`-Modul (Gegencheck) | init 0 · validate PASS · fmt-check 0 |

## 11. Security und Governance

- Keine AWS-Mutationen in dieser Release-Vorbereitung; **kein** Apply/Destroy durch MO.
- Keine Änderung am RIS-Repository, keine Consumer-Pin-Änderung, keine Branch-Löschung.
- Keine Force-Pushes, kein Reset/Clean, keine neuen Features, kein Eingriff in Anwendungscode.
- Integrationsbranch `feature/mo-module-contract-ris-dev2-2026` bleibt erhalten (lokal + remote).
- Tags `v0.5.0-rc.1` (`f6e737b`) und `v0.5.0-rc.2` (`5cf50a0`) unverändert.

## 12. Bekannte Einschränkungen

1. **Privacy-Produktivbetrieb: BLOCKED** — dauerhaftes Secret-Management und Rotation
   fehlen weiterhin (5–8 PT geschätzt).
2. **Keine allgemeine Multi-Account-Produktionsreife belegt.** Die erfolgreiche Installation
   in *einem* Testkonto ist ein Portabilitätsbeleg, kein Beweis für beliebige Konten
   (Quotas, SCPs, Boundary-Policies, Org-Restriktionen bleiben Consumer-Verantwortung).
3. **F-01:** Ein *explizit gesetzter* Boundary-ARN ist nicht cross-account-portabel;
   der Default ist `null`. Betriebsfrage des Consumers.
4. **EXTERNAL-Cognito:** `cognito_user_pool_id/arn/group_name` liefern im EXTERNAL-Modus
   `null` (dokumentierte Inkompatibilität); optionale Zusatzfelder sind offen.
   MANAGED→EXTERNAL-Migration ist bewusst **nicht** automatisiert.
5. **RIS-Pin** steht noch auf `1dbb0cb`; ein Nachziehen auf den Release-Commit ist
   rein kosmetisch (code-identisch) und nicht Teil dieses Releases.
6. **Builder liefert kein Backend** — Konsumenten konfigurieren ihr eigenes Remote-Backend.
7. **Ownership-Klassifikation** des Collision-Preflights bleibt namensbasiert (Phase 2 offen).
8. **S3 `mays-orders-ci-artifacts-dev`** (+ CodeBuild): Ownership weiterhin ungeklärt.
9. **GitHub-Veröffentlichung** ist menschlich: Tag und Release werden nicht durch den Agenten erstellt.

## 13. Nächste Schritte

1. Menschliche Freigabe → `git tag v0.5.0-rc.3 <release-commit>` + `git push origin v0.5.0-rc.3`.
2. GitHub-Pre-Release anlegen (Release Notes aus diesem Dossier).
3. RIS: Builder-Pin optional auf den Release-Commit ziehen.
4. Secrets Manager + Rotation für `PRIVACY_INTERNAL_SECRET` → Production-Privacy-Gate.
5. Collision-Preflight Phase 2 (MANAGED/UNMANAGED über `terraform show -json`).
6. Finale Abnahme v0.5.0 nach Schließen der Produktions-Blocker.

---

**Dokumentenstatus:** Gestaltete Markdown-Ausgabe des Release-Dossiers; das PDF
(`RELEASE-v0.5.0-rc.3.pdf`) wurde aus demselben Inhalt gesetzt (LibreOffice).
