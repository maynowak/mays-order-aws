# MO-RC4-P00-BASELINE

**Baseline & Ausgangsstand für RC4 (`feature/mo-rc4-kms-privacy-retention`)**

**Datum:** 2026-11-01
**Repository:** `maynowak/mays-order-aws`
**Ausgangsrelease:** v0.5.0-rc.3 (Packaging-Stand)
**Erwarteter RC3-Commit:** `086a8bea4c608724d400de834c21df5456b7ccac`

## 1. Git-Baseline (VERIFIED)

| Prüfung | Ergebnis |
|---|---|
| Repository-Pfad | `/home/dci-student/projects/Mays-Orders-AWS` |
| Remote | `origin` = `git@github.com:maynowak/mays-order-aws.git` (fetch+push) |
| Branch vor Start | `main` |
| HEAD vor Start | `086a8bea4c608724d400de834c21df5456b7ccac` |
| Working Tree | CLEAN (keine unversionierten/geänderten Dateien) |
| `origin/main` | `086a8bea4c608724d400de834c21df5456b7ccac` — **identisch**, keine Divergenz |
| RC3-Commit existiert | JA — `086a8be docs(release): package v0.5.0-rc.3 (Module Builder & RIS Integration)` |
| Änderungen seit RC3-Commit | **0 Commits** (`086a8be..HEAD` leer) |
| Getrackte State-/Plan-Artefakte | keine |
| Integrationsbranch | `feature/mo-module-contract-ris-dev2-2026` (lokal + `origin/`) vorhanden |

## 2. Tags und Releases

| Tag | Commit | Anmerkung |
|---|---|---|
| `v0.5.0-rc.1` | `f6e737b` | unverändert |
| `v0.5.0-rc.2` | `5cf50a0` | unverändert |
| `v0.5.0-rc.3` | — | **NICHT VORHANDEN** |

**Abweichung (dokumentiert, nicht kritisch):** Der RC3-Packaging-Commit `086a8be`
existiert, aber der Tag `v0.5.0-rc.3` wurde **nie erstellt** — P09 (Veröffentlichung)
wartet weiterhin auf menschliche Freigabe. `git tag --points-at 086a8be` liefert
keine Treffer. Für RC4 ist das unkritisch: Die Baseline ist der Commit, nicht der Tag.
**Konsequenz:** RC4 muss beim späteren Release den RC3-Tag entweder nachziehen
(auf `086a8be`, unverändert) oder bewusst ohne RC3-Tag weiterarbeiten — Entscheidung
offen (siehe `MO-RC4-P00-OPEN-QUESTIONS.md`, Q-01).

## 3. RC4-Branch (angelegt)

| Feld | Wert |
|---|---|
| Branch | `feature/mo-rc4-kms-privacy-retention` |
| Erstellt von | `086a8bea4c608724d400de834c21df5456b7ccac` (RC3-Commit) |
| Ausgangs-SHA | `086a8bea4c608724d400de834c21df5456b7ccac` |
| Vorher existierender RC4-Branch | **keiner** (weder lokal noch remote) — nichts überschrieben |
| Push | **nicht** erfolgt (kein Force-Push, keine Remote-Änderung) |
| RC3-Tags verändert | nein |

## 4. Erhalt des RC3-Stands (Auflage)

Der Branch startet **exakt** auf dem geprüften RC3-Commit. Damit sind erhalten:

- Module Builder (Preset `complete`, `orders-service`; `--modules`, `--with-deps`)
- Terraform-Verträge (7-Modul-Orders-Service, 6 Inputs / 20 Outputs)
- IAM-Portabilität (`lambda_execution_boundary` default `null`)
- SQS-Security-Fix F-03 (keine Wildcard-Resource-Policy)
- Lambda-Artefakte (deterministisch, `b1018a3b…`)
- RIS-Integrationsvertrag (Builder-Pin `1dbb0cb` code-identisch zu RC3)
- Policy-Gate (`terraform/policy/validate-plan.py` + `resource-policy.json`)

**Regel für RC4:** Alle Erweiterungen müssen **additiv und standardmäßig abgeschaltet**
sein, damit ein RC4-Build mit RC3-Defaults byte-/plan-identisch bleibt
(RIS-Kompatibilität, siehe Plan P-12).

## 5. Architektur-Inventar (Ist-Zustand)

Legende: **IMPLEMENTED** = Code vorhanden · **VERIFIED** = lokal/ AWS belegt ·
**PARTIAL** = teilweise · **PLANNED** = nur dokumentiert · **UNKNOWN** = unklar.

### 5.1 Verschlüsselung

| Element | Ist-Zustand | Status | Quelle |
|---|---|---|---|
| DynamoDB at rest | AWS-owned KMS (Default), **kein** `server_side_encryption`-Block, kein CMK | PARTIAL (Baseline-Schutz, kein Customer-Key) | `terraform/modules/dynamodb/main.tf` |
| DynamoDB PITR | `point_in_time_recovery { enabled = true }` | IMPLEMENTED | ebd. Z. 79 |
| DynamoDB TTL / Retention-Feld | **nicht vorhanden** (kein `ttl`, kein `retentionUntil`) | UNKNOWN → geplant | ebd. |
| SQS at rest | keine explizite Konfiguration → AWS-managed (SSE-SQS) | PARTIAL | `terraform/modules/sqs/main.tf` |
| S3 (CloudTrail, Cognito-Backup, TF-State) | SSE-S3 (`AES256`) explizit | IMPLEMENTED | `modules/cloudtrail`, `modules/cognito_backup`, `bootstrap/` |
| KMS CMK | **kein** `aws_kms_key`/Alias im gesamten Repo | UNKNOWN (nicht vorhanden) | `grep aws_kms` |
| Secrets Manager / SSM | **keine** Ressource, kein Code | UNKNOWN (nicht vorhanden) | `grep secretsmanager` |

### 5.2 IAM

| Element | Ist-Zustand | Status |
|---|---|---|
| Handler-Rolle | DynamoDB (Tabelle + GSI1/2), Logs, optional `sqs:SendMessage` (count-gated) | IMPLEMENTED / VERIFIED |
| Worker-Rolle | `dynamodb:GetItem/UpdateItem` (Tabellen-ARN), `sqs:Receive/Delete/GetQueueAttributes` (Queue-ARN), Logs | IMPLEMENTED / VERIFIED |
| Permissions Boundary | optional, `default = null`, ARN-Format validiert | IMPLEMENTED / VERIFIED |
| `kms:*` | **keine** KMS-Berechtigung in irgendeiner Rolle | UNKNOWN (fehlt) |
| Secrets Manager-Lesezugriff | **keine** | UNKNOWN (fehlt) |

### 5.3 Worker-Verträge

| Element | Ist-Zustand | Status |
|---|---|---|
| Handler-Lambda | `index.handler`, Env `ORDERS_TABLE`, `SQS_QUEUE_URL`, `ORDERS_PROJECT_NAME` | IMPLEMENTED |
| Worker-Lambda | `sqs_handler.handler`, Env nur `ORDERS_TABLE`; Event-Source-Mapping `batch_size = 5` | IMPLEMENTED / VERIFIED (RIS-E2E: `PENDING→CONFIRMED`) |
| Artefakt | **ein** gemeinsames `lambda/dist/lambda.zip` für Handler + Worker | IMPLEMENTED |
| Idempotenz/Retry | Worker-Update mit Versionsbedingung; SQS-Retry via Redrive (keine DLQ definiert) | PARTIAL (DLQ fehlt, dokumentiert) |

### 5.4 Privacy

| Element | Ist-Zustand | Status |
|---|---|---|
| Auth-Boundary | `_require_privacy_auth`: Projekt-Match, `authorized`, Berechtigungsflags, `compare_digest(internal_token, PRIVACY_INTERNAL_SECRET)` — fail-closed | IMPLEMENTED / VERIFIED (historisch, ephemeres Secret) |
| `PRIVACY_INTERNAL_SECRET` Herkunft | **nur** Lambda-Env, **keine** IaC-Provisionierung, kein Secrets Manager | **PARTIAL** — Produktionsbetrieb BLOCKED |
| Inspect/Export/Erase | implementiert inkl. PREVIEW/EXECUTE, Policies `ERASE`/`ANONYMIZE`/`RETAIN` | IMPLEMENTED / VERIFIED (historisch) |
| Retention-Policy | Operation verlangt **explizite** Policy; ohne Policy → `BLOCKED`; „Missing explicit retention policy" | PARTIAL (keine System-Policy, keine Fristen) |
| Rotation | keine | UNKNOWN (fehlt) |

### 5.5 Cancel & Retention-Semantik

| Element | Ist-Zustand | Status |
|---|---|---|
| Statusmodell | `PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED` | IMPLEMENTED / VERIFIED |
| Cancel-Übergänge | `PENDING→CANCELLED`, `CONFIRMED→CANCELLED`; ab `PROCESSING` ungültig (409) | IMPLEMENTED / VERIFIED (`state_machine.py`, `order-lifecycle/`) |
| Cancel-Nebenwirkungen | keine Retention-/Anonymisierungslogik, kein Aufräumpfad | PARTIAL |
| Retention-Fristen | **keine** (kein Feld, keine Frist, kein TTL, kein Sweep-Job) | UNKNOWN (fehlt) |
| Tenant-Begriff in MO | **kein** `tenantId` in Code/Schema (RIS führt Tenant separat) | UNKNOWN (bewusst? offene Frage Q-05) |

### 5.6 Installer & Module Builder

| Element | Ist-Zustand | Status |
|---|---|---|
| Installer-CLI | `./Mays-Order-AWS-installer {validate,plan,plan-destroy,deploy,destroy,state,output,identity,gui}`; Layers `cli/core/validation/terraform/run` | IMPLEMENTED / VERIFIED (81 Tests) |
| Sicherheits-Gates | Collision-Preflight, Plan-Integrität, Approval, Artifact-Integrity, Lock-Manager | IMPLEMENTED / VERIFIED |
| Module Builder | `python -m module_builder`, Presets `complete`/`orders-service`, `--modules`, `--with-deps`, Manifest mit SHA-256 | IMPLEMENTED / VERIFIED (90 Tests) |
| Modul-Katalog | 11 Modul-Namen + Deps (`catalog.py`), Policy-Gate-Kopie in Zielprojekte | IMPLEMENTED |
| Policy-Gate-Allowlist | enthält **kein** `aws_kms_key`, `aws_kms_alias`, `aws_secretsmanager_secret*`, `aws_iam_role_policy_attachment` | IMPLEMENTED (muss für RC4 erweitert werden) |

### 5.7 RIS-Integrationsvertrag

| Element | Ist-Zustand | Status |
|---|---|---|
| Builder-Pin (RIS) | `1dbb0cb` — code-identisch zu RC3 (`git diff -w` leer) | VERIFIED |
| Wrapper | `installer.build_mays_orders_module` + `patch_iam_sqs_gate()` erzwingt plan-stabiles `count = var.sqs_enabled ? 1 : 0` | VERIFIED |
| Live-E2E | RIS-MO-RC-01: Plan 169 add → Apply → No-Op → 7/7 Live-Tests → Destroy → CLEAN | VERIFIED AWS E2E |
| Vertragsstabilität | 6 Inputs / 20 Outputs; EXTERNAL-Cognito; neues Feature muss optional bleiben | VERIFIED |

## 6. Risiken aus dem Inventar (Kurzfassung)

| Risiko | Wirkung | Gegenmaßnahme im Plan |
|---|---|---|
| Secret nur als Lambda-Env | Wer `lambda:GetFunctionConfiguration` darf, liest das Secret; keine Rotation | P-01/P-02/P-03 (Provider + Secrets Manager + Rotation) |
| Kein CMK | Kein Key-Policy-Schutz, keine konto-/projektgetrennte Krypto-Kontrolle, kein Audit auf Key-Nutzung | P-05/P-06/P-07 |
| Policy-Gate-Allowlist zu eng | Jede KMS/Secrets-Ressource lässt `apply` am Gate scheitern (FAIL) | P-10 (Gate-Erweiterung, bewusst & dokumentiert) |
| Keine Retention-Fristen | DSGVO-Löschfristen nicht durchsetzbar; Erase nur manuell | P-08/P-09 |
| Kein `tenantId` in MO | Mandantengetrennte Retention nicht abbildbar ohne Schema-/API-Änderung | Q-05, ggf. P-08 optional |
| Ein Lambda-ZIP für zwei Handler | Neue Secret-Abhängigkeiten müssen in beiden Pfaden fail-closed bleiben | P-01, P-13 |
| RIS-Kompatibilität | Breaking Change am Modulvertrag bricht gepinnten Consumer | P-12 (Default-off, additive Outputs) |

## 7. Abweichungen zur Auftragserwartung

| Erwartung | Tatsächlich | Bewertung |
|---|---|---|
| RC3-Commit vorhanden | JA (`086a8be`) | OK |
| RC3 getaggt | **NEIN** | dokumentiert, kein Blocker für RC4-Entwicklung (Q-01) |
| RC4-Branch vorhanden | NEIN → neu angelegt | OK |
| Sauberer Startpunkt | JA (clean, kein Delta seit RC3) | OK |
