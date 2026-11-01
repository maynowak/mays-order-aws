# MO-RC4-P00-MODULE-PLAN

**Entwicklungsplan RC4 — KMS, Privacy-Secret-Management und Retention**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention` (Basis `086a8be`)
**Leitregel:** Jede Erweiterung ist **additiv und per Default AUS**. Ein Build mit
RC3-Defaults muss plan-identisch bleiben (RIS-Kompatibilität).

## 1. Planungstabelle

| ID | Modul | Ist-Zustand | Geplante Änderung | Abhängigkeiten | Risiken | Tests | Priorität |
|---|---|---|---|---|---|---|---|
| **P-01** | SecretProvider (Lambda) | Secret nur direkt aus `os.environ` (`order_service.py:114`), fail-closed | Neuer Provider-Vertrag `get_secret()` mit Backends `env` (Default) und `secretsmanager`; Cold-Start-Cache; kein stiller Fallback | keine (boto3 vorhanden) | Verhaltensänderung bei aktiviertem Provider; Fehlerpfad muss fail-closed bleiben | Unit: Provider-Auswahl, Fehler, Cache, Log-Hygiene | **P0** |
| **P-02** | AWS Secrets Manager (IaC) | keine Ressource | Optionales Modul `privacy_secret`: `aws_secretsmanager_secret` + Version, Name `${project}_name/privacy-internal-secret`, `recovery_window_in_days = 7`, Zufallswert über `random_password` (ephemeral) | P-04 (Key), P-10 (Policy-Gate), Installer-Var | **Secret im TF-State möglich** → `lifecycle.ignore_changes` + ephemeral erzeugen; Koste +0,40 $/Monat | `terraform validate/plan` (backend=false + Policy-Gate), Unit-Test Provider gegen Secret-ARN | **P0** |
| **P-03** | Secret-Rotation | keine | `aws_secretsmanager_secret_rotation` + Rotator-Lambda (`lambda/src/rotation_handler.py`, eigenes ZIP), `rotate_immediately=false`, Default **AUS**; manuelle Rotation dokumentiert | P-02, P-07 (IAM), P-11 (Bundle) | Rotator-Lambda = neue AWS-Ressource + zweites Artefakt; Rotation kann laufende Instanzen brechen (Cache!) | Unit: Rotator-Handler, Provider-Cache-Invalidierung; Plan-Negativtest | **P1** |
| **P-04** | KMS-Key (CMK) | kein `aws_kms_key` im Repo | Neues Modul `kms`: `aws_kms_key` (ENCRYPT_DECRYPT, `enable_key_rotation = true`), Alias `${project_name}/orders`, Key-Policy nach Least Privilege | Policy-Gate-Allowlist (P-15) | Key-Löschung ist irreversibel (`deletion_window_in_days` ≥ 7); Kosten 1 $/Monat/Key + Requests | `terraform validate`; Key-Policy-Unit (JSON-Assertions) | **P0** |
| **P-05** | DynamoDB Encryption | AWS-owned Default, kein SSE-Block | `server_side_encryption { enabled = true, kms_key_arn = var.kms_key_arn }` nur wenn Key gesetzt; PITR bleibt | P-04 | Umstellung auf CMK ist Update mit Re-Encryption; kann lange dauern; Rollback nur mit neuem Key | Plan-Assertion (SSE-Block vorhanden/abwesend), Provider-Mock | **P0** |
| **P-06** | SQS Encryption | AWS-managed (SSE-SQS), keine Konfiguration | `kms_master_key_id` + `kms_data_key_reuse_period_seconds` optional; Key-Policy muss SQS-Principal erlauben | P-04, P-07 | Falsche Key-Policy → Nachrichten unzustellbar (Producer/Consumer AccessDenied) | Plan-Assertion; SQS-Modul-Unit (HCL-Snapshot) | **P0** |
| **P-07** | Worker-/Handler-IAM (KMS) | keine `kms:*`-Rechte | `kms:Decrypt`, `kms:GenerateDataKey` (bei Bedarf `Encrypt`) auf Key-ARN — nur wenn Key gesetzt (count-gated, wie SQS-Gate) | P-04 | Zu breite KMS-Rechte (`Resource: "*"`) wären ein Security-Regress | IAM-Dokument-Unit: Aktionen/Resources exakt; Negativtest ohne Key | **P0** |
| **P-08** | Tenant Retention Policy (Datenmodell) | kein `retentionUntil`, kein TTL, kein Tenant-Feld | `retentionUntil` (ISO-8601) + `ttl` (Epoch) je Order; Retention-Tage aus Policy/Variable; optional `tenantId` (siehe Q-05) | Q-05-Entscheidung, P-09 | Schema-Erweiterung berührt API-Antworten (`isTestData`-Muster: nur intern?); Breaking-Change-Gefahr; TTL löscht asynchron (bis 48 h Verzug) | Unit: Default-Frist, Überschreiben, TTL-Wert; API-Contract-Test | **P1** |
| **P-09** | Cancel Lifecycle | `PENDING/CONFIRMED→CANCELLED` ohne Retention-Folgen | Bei `CANCELLED`: `retentionUntil` gemäß Policy (z. B. 30 Tage) setzen, optional sofortige PII-Anonymisierung via Flag; Doku der Semantik | P-08 | Fachliche Entscheidung nötig (Widerruf vs. Aufbewahrungspflicht); Datenverlust bei zu kurzer Frist | State-Machine-Tests erweitert; Erase-/Anonymize-Integrationstest | **P1** |
| **P-10** | Installer-Konfiguration | Variablen `project_name`, `aws_region`, `tags`, Monitoring/Seed/Boundary | Neue optionale Schalter: `privacy_secret_enabled`, `kms_enabled`, `retention_days`, `retention_on_cancel_days`; Kontextvalidierung (Key + Secret konsistent) | P-02, P-04, P-11 | Viele neue Flags → Kombinationsfehler; Installer-Tests müssen Matrix abdecken | Installer-Unit: Flag-Matrix, Plan-Preflight-Verweigerung bei Inkonsistenz | **P1** |
| **P-11** | Module-Builder-Integration | Katalog 11 Module, Presets, Policy-Gate-Kopie | Katalog-Einträge `kms`, `privacy_secret` (+ Deps `dynamodb`/`sqs`/`lambda`/`iam`), Variablen-Mapping, Manifest-Notizen, Presets bleiben default-aus | P-02, P-04, P-15 | Zyklische/fehlende Deps; Nicht-Auswahl darf keine Wiring-Reste lassen (bestehendes Stripping) | Builder-Unit: Auswahl/Deps/Stripping; Live-`terraform validate` auf 3 Varianten | **P2** |
| **P-12** | RIS-Kompatibilität | Pin `1dbb0cb` (RC3-code-identisch), 6 Inputs / 20 Outputs | Keine Vertragsänderung; neue Inputs **optional mit Default AUS**; keine neuen Pflicht-Outputs; Doku-Absatz im Consumer-Handoff | P-02…P-11 | Neuer Pflicht-Input = Breaking Change für gepinnten Consumer | `git diff`-basierter Vertragstest: Inputs/Outputs-Namen unverändert bei Defaults | **P0** |
| **P-13** | Security-Tests | 76 Lambda / 81 Installer / 90 Builder grün | Neue Test-Suiten: Secret-Provider, Rotation, Key-Policy, IAM-KMS, Policy-Gate-Negativfälle, „kein Klartext-Secret in Env/Logs/State" | P-01…P-11 | Tests, die AWS bräuchten, sind unzulässig → nur Mocks/Plan-Assertions | s. je Item + eigener Gate-Report | **P1** |
| **P-14** | Release-Gates RC4 | RC3: 18 Gates, Dossier MD+PDF | RC4-Gate-Matrix erweitert (Secrets/KMS/Retention), Dossier + PDF, Changelog/Notes | alle | Dokumentationslast am Ende | Doku-Review + `git diff --check` + Secret-Audit | **P1** |
| **P-15** | Policy-Gate-Allowlist | kennt kein KMS/Secrets | Allowlist erweitern (`aws_kms_key`, `aws_kms_alias`, `aws_secretsmanager_secret*`); neue Regeln: Key-Rotation an, Secret-Rotation dokumentiert, kein `Principal:"*"` | Governance-Freigabe | Aufweichung des Gates = Sicherheitsregress; muss begründet & getestet sein | Gate-Positiv-/Negativtests (Exit 0/1) | **P0** |

**Geschätzter Gesamtaufwand:** ~18,5 PT (P0-Anteil ≈ 7,0 PT).

## 2. Detailblätter

### P-01 — SecretProvider-Vertrag

- **Dateien:** neu `lambda/src/secret_provider.py`; geändert `lambda/src/order_service.py` (`_require_privacy_auth`), `lambda/tests/test_order_service.py`, neu `lambda/tests/test_secret_provider.py`.
- **Bestehender Vertrag:** `internal_secret = os.environ.get("PRIVACY_INTERNAL_SECRET")`; fehlt → `validation_error("Internal secret not configured")`; Vergleich via `secrets.compare_digest`.
- **Geplanter Vertrag:** `get_privacy_secret() -> str` mit `PRIVACY_SECRET_PROVIDER` ∈ {`env` (Default), `secretsmanager`}; `PRIVACY_SECRET_ID` (ARN/Name). Cache pro Cold Start. Bei `secretsmanager` + Fehler → **Exception** (fail-closed), kein Env-Fallback.
- **Migrationsbedarf:** keiner (Default `env` = heutiges Verhalten).
- **Sicherheitsanforderungen:** Secret nie loggen; `compare_digest` bleibt; Cache nur im Prozessspeicher; keine Ausgabe in Fehlermeldungen (nur Secret-Name).
- **Teststrategie:** Fake-Client (kein AWS), Provider-Auswahl, fehlende Konfiguration, Decrypt-Fehler, Cache-Treffer, Log-Assertion (Secret nicht enthalten).
- **Akzeptanz:** 76+ Tests grün; `env`-Pfad bitgleich zum Vorzustand; `secretsmanager`-Pfad liefert denselben Vergleich; kein Secret in Logs/Responses.
- **Aufwand:** 1,0 PT.

### P-02 — AWS Secrets Manager (IaC)

- **Dateien:** neu `terraform/modules/privacy_secret/{main.tf,variables.tf,outputs.tf,README.md}`; `terraform/main.tf` (Modulblock, count-gated), `terraform/variables.tf`, `terraform/outputs.tf`.
- **Bestehender Vertrag:** kein Secret in IaC; Lambda-Env kennt das Secret nicht.
- **Geplanter Vertrag:** `privacy_secret_enabled` (bool, default `false`), `privacy_secret_value` **nicht** als Root-Variable (stattdessen `random_password` ephemeral); Outputs `privacy_secret_arn`, `privacy_secret_name`; Lambda-Env erhält `PRIVACY_SECRET_PROVIDER=secretsmanager` + `PRIVACY_SECRET_ID=<arn>` **nur** bei Aktivierung.
- **Migrationsbedarf:** keine (Default aus). Bei Aktivierung: `random_password` → Secret-Version → Lambda-Env-Update → Deploy-Reihenfolge im Plan prüfen.
- **Sicherheitsanforderungen:** kein Klartext im State (ephemeral), `recovery_window_in_days = 7`, keine Ausgabe des Werts, Zugriff nur über die Handler-Rolle (`secretsmanager:GetSecretValue` auf exakten ARN).
- **Teststrategie:** `terraform validate`, Plan-Assertion (Secret-Ressource vorhanden/abwesend), Policy-Gate-Positivlauf, Unit-Test der Env-Ableitung im Builder.
- **Akzeptanz:** Default-Plan identisch zu RC3; aktivierter Plan enthält Secret + Env ohne Klartext; Gate PASS.
- **Aufwand:** 1,5 PT.

### P-03 — Secret-Rotation

- **Dateien:** neu `lambda/src/rotation_handler.py`, `lambda/build_zip.py` (Bundle `rotation`), `terraform/modules/privacy_secret/rotation.tf`, `module_builder/spec.py` (Artefaktliste).
- **Bestehender Vertrag:** keine Rotation.
- **Geplanter Vertrag:** `privacy_secret_rotation_enabled` (default `false`); Rotator erhält `AWSCURRENT`/`AWSPENDING`-Protokoll (4-Schritt), Provider-Cache wird über Env-Update/Lambda-Restart invalidiert.
- **Migrationsbedarf:** keine; Aktivierung erfordert zusätzliches ZIP im Build.
- **Sicherheitsanforderungen:** Rotator nur `secretsmanager:GetSecretValue/PutSecretValue/DescribeSecret/UpdateSecretVersionStage` auf exaktes Secret; `lambda:InvokeFunction` durch Secrets Manager via Resource-Policy.
- **Teststrategie:** Handler-Unit mit Fake-Client (alle 4 Schritte + Fehlerfälle), Plan-Assertion, Doku der manuellen Rotation.
- **Akzeptanz:** Rotation im Test-Env nachweisbar (später, AWS); ohne Aktivierung keinerlei Änderung.
- **Aufwand:** 2,5 PT.

### P-04 — KMS-Key (CMK)

- **Dateien:** neu `terraform/modules/kms/{main.tf,variables.tf,outputs.tf,README.md}`; `terraform/main.tf`, `terraform/variables.tf` (`kms_key_arn` als overridbarer Input, `kms_enabled`).
- **Bestehender Vertrag:** kein Key; `kms_key_arn` existiert nicht.
- **Geplanter Vertrag:** bei `kms_enabled=true` eigener Key; alternativ externer ARN via `kms_key_arn` (BYOK-Muster wie Boundary).
- **Migrationsbedarf:** keine; Key ist additiv.
- **Sicherheitsanforderungen:** `enable_key_rotation = true`; Key-Policy: Root-Account-Admin, `kms:ViaService`-Conditions für `dynamodb.*`/`sqs.*`; kein `Principal: "*"`.
- **Teststrategie:** `terraform validate`, Key-Policy-JSON-Assertions im Unit-Test, Gate-Positivlauf.
- **Akzeptanz:** Key optional, Rotation an, Policy least-privilege, Gate PASS.
- **Aufwand:** 1,0 PT.

### P-05 — DynamoDB Encryption (SSE-KMS)

- **Dateien:** `terraform/modules/dynamodb/main.tf`, `variables.tf`, `terraform/main.tf` (Wiring).
- **Bestehender Vertrag:** AWS-owned Key, kein Block.
- **Geplanter Vertrag:** `server_side_encryption` nur bei gesetztem Key; sonst Block weglassen (Plan-Identität).
- **Migrationsbedarf:** Bestandstabelle wird auf CMK umgestellt (Update, Re-Encryption; Dauer abhängig von Größe).
- **Sicherheitsanforderungen:** Key-Policy muss den DynamoDB-Service-Prinzipal erlauben; sonst `AccessDenied` beim Lesen.
- **Teststrategie:** Plan-Assertion mit/ohne Key; Negativtest (Key gesetzt, Policy fehlt → Gate/Plan-Fehler).
- **Akzeptanz:** Default-Plan unverändert; mit Key erscheint genau ein SSE-Block am Table.
- **Aufwand:** 1,0 PT.

### P-06 — SQS Encryption (SSE-KMS)

- **Dateien:** `terraform/modules/sqs/main.tf`, `variables.tf`, `terraform/main.tf`.
- **Bestehender Vertrag:** SSE-SQS (AWS-managed), keine Felder.
- **Geplanter Vertrag:** `kms_master_key_id` nur bei Key; `kms_data_key_reuse_period_seconds` dokumentiert (Default 300).
- **Migrationsbedarf:** keine bei Default; bei Aktivierung muss der Plan die Queue in-place aktualisieren (kein Replace).
- **Sicherheitsanforderungen:** Key-Policy `sqs:*` für Producer-/Consumer-Rollen; `kms:Decrypt/GenerateDataKey` in beiden Rollen.
- **Teststrategie:** Plan-Assertion; IAM-Unit (siehe P-07).
- **Akzeptanz:** Default unverändert; aktiviert: `kms_master_key_id` gesetzt, Policies konsistent.
- **Aufwand:** 0,5 PT.

### P-07 — Worker-/Handler-IAM (KMS)

- **Dateien:** `terraform/modules/iam/main.tf` (+ `variables.tf`), `terraform/modules/sqs-worker/iam.tf` (+ `variables.tf`), `terraform/main.tf`.
- **Bestehender Vertrag:** kein `kms:*`; SQS-Recht count-gated über `sqs_enabled`.
- **Geplanter Vertrag:** zusätzliches Statement nur bei gesetztem `kms_key_arn` (gleiches Muster: plan-bekanntes Gate, ARN als Resource).
- **Migrationsbedarf:** keine.
- **Sicherheitsanforderungen:** exakte Aktionen (`kms:Decrypt`, `kms:GenerateDataKey`), Resource = Key-ARN, keine Wildcard.
- **Teststrategie:** IAM-Dokument-Assertions (Aktionen/Resources), Plan-Assertion.
- **Akzeptanz:** ohne Key keine KMS-Ressource; mit Key exakt zwei Statements (Handler/Worker), je 2 Aktionen.
- **Aufwand:** 0,5 PT.

### P-08 — Tenant Retention Policy (Datenmodell)

- **Dateien:** `lambda/src/order_types.py`, `order_service.py`, `validation.py`, `sqs_handler.py` (Update-Pfad), `database/`-Doku, `order-lifecycle/transition-rules.md`.
- **Bestehender Vertrag:** Order-Item ohne `retentionUntil`/`ttl`; Privacy-Erase verlangt explizite Policy.
- **Geplanter Vertrag:** `retentionUntil` (ISO) + `ttl` (Epoch) ab Erstellung/Bereinigung; Retention-Tage aus `retention_days` (Default z. B. 365) und `retention_on_cancel_days` (z. B. 30).
- **Migrationsbedarf:** Bestandsdaten haben kein Feld → „unbefristet" oder Backfill-Skript (separat, nicht Teil von RC4-Code).
- **Sicherheitsanforderungen:** PII-Minimierung, keine Fristverkürzung ohne Policy, TTL nur auf abgeleitete Epoch (kein Datums-Parsing im TTL).
- **Teststrategie:** Unit (Default/Override/TTL-Berechnung), API-Contract (Felder nicht öffentlich preisgeben, Muster wie `isTestData`).
- **Akzeptanz:** neue Orders tragen korrekte Frist; Bestand unverändert; Erase berücksichtigt Frist.
- **Aufwand:** 2,0 PT.

### P-09 — Cancel Lifecycle

- **Dateien:** `lambda/src/state_machine.py`, `order_service.py`, `order-lifecycle/state-machine.md`, `transition-rules.md`.
- **Bestehender Vertrag:** Cancels nur aus `PENDING`/`CONFIRMED`, keine Folgen.
- **Geplanter Vertrag:** Konsistentes Übergangsmodell (unverändert) + Retention-Frist setzen, optional PII-Anonymisierung sofort (`retention_on_cancel_immediate_anonymize`, Default `false`).
- **Migrationsbedarf:** keiner.
- **Sicherheitsanforderungen:** keine Löschung ohne Policy; Audit-Felder (`cancelledAt`) dokumentieren.
- **Teststrategie:** State-Machine-Matrix, Anonymize-Assertions.
- **Akzeptanz:** Übergangsmatrix unverändert; Frist korrekt gesetzt; Opt-in-Anonymisierung wirkt.
- **Aufwand:** 1,5 PT.

### P-10 — Installer-Konfiguration

- **Dateien:** `installer/cli/main.py`, `installer/core/context.py`, `installer/validation/*`, `installer/tests/test_installer.py`.
- **Bestehender Vertrag:** Flags `--project-name/--profile/--region/--yes/--guide`; `validate/plan/…`.
- **Geplanter Vertrag:** `--privacy-secret-enabled`, `--kms-enabled`, `--retention-days`, `--retention-on-cancel-days`; Preflight verweigert `privacy_secret_enabled` ohne Key/mit fehlender Policy.
- **Migrationsbedarf:** keiner (Defaults aus).
- **Sicherheitsanforderungen:** keine Secrets auf der Kommandozeile; Werte nur als Schalter/Fristen.
- **Teststrategie:** Flag-Matrix, Preflight-Negativfälle.
- **Akzeptanz:** 81+ Tests grün; Default-Aufruf unverändert.
- **Aufwand:** 1,0 PT.

### P-11 — Module-Builder-Integration

- **Dateien:** `module_builder/catalog.py`, `spec.py`, `builder.py` (Nur-Auswahl-Filter), `tests/test_module_builder.py`, `terraform/policy/*` (Kopie).
- **Bestehender Vertrag:** 11 Module, `complete`/`orders-service`, `--modules`, `--with-deps`.
- **Geplanter Vertrag:** neue Katalogeinträge `kms`, `privacy_secret` mit Deps; beide **nicht** in `orders-service` (Vertragsstabilität); in `complete` optional (default aus) oder als eigenes Preset `orders-service-hardened` (Q-03).
- **Migrationsbedarf:** keiner.
- **Sicherheitsanforderungen:** generierte Projekte erben erweitertes Gate; keine Secrets im Manifest.
- **Teststrategie:** Auswahl/Deps/Stripping, Live-`terraform validate` (3 Varianten), Manifest-Assertion.
- **Akzeptanz:** 90+ Tests grün; `orders-service`-Output unverändert; neue Module auswählbar.
- **Aufwand:** 1,5 PT.

### P-12 — RIS-Kompatibilität

- **Dateien:** `docs/reports/MO-CONSUMER-HANDOFF-01.md` (Nachtrag), `docs/release/RELEASE-v0.5.0-rc.4*` (später).
- **Bestehender Vertrag:** 6 Inputs, 20 Outputs, Default AUS.
- **Geplanter Vertrag:** unverändert; neue optionale Inputs ausschließlich im `complete`-Preset bzw. im Orders-Modul mit Default `false`/`null`.
- **Migrationsbedarf:** keiner; RIS-Pin kann unverändert bleiben.
- **Sicherheitsanforderungen:** Default-Build darf keine zusätzlichen AWS-Ressourcen planen.
- **Teststrategie:** Namens-Diff der Inputs/Outputs (Skript), `terraform plan`-Vergleich Default.
- **Akzeptanz:** Input-/Output-Namen identisch; Default-Plan ohne neue Ressourcen.
- **Aufwand:** 0,5 PT.

### P-13 — Security-Tests

- **Dateien:** `lambda/tests/test_secret_provider.py`, `lambda/tests/test_rotation_handler.py`, `terraform/modules/*/tests` (soweit Muster existiert), `installer/tests/*`, `module_builder/tests/*`.
- **Bestehender Vertrag:** 247 Tests gesamt (76/81/90).
- **Geplanter Vertrag:** +30–40 Tests; kein Test darf AWS kontaktieren.
- **Migrationsbedarf:** keiner.
- **Sicherheitsanforderungen:** Log-/Response-Assertions auf Abwesenheit von Secrets; State-Assertion (kein Klartext).
- **Teststrategie:** Fake-Clients, JSON-Assertions auf HCL-Strings, Policy-Gate-Positiv/Negativ.
- **Akzeptanz:** alle Suiten grün, keine Netzwerk-/AWS-Aufrufe, Secret-Audit clean.
- **Aufwand:** 1,5 PT.

### P-14 — Release-Gates RC4

- **Dateien:** `docs/release/RELEASE-GATES-v0.5.0-rc.4.md`, `docs/release/RELEASE-v0.5.0-rc.4.md/.pdf`, `docs/CHANGELOG.md`, `docs/RELEASE_NOTES.md`, `docs/AI_AUDITLOG.md`, `docs/PROJECT_STATUS.md`.
- **Bestehender Vertrag:** RC3-Gate-Report (18 Gates) als Muster.
- **Geplanter Vertrag:** erweiterte Matrix (Secrets/KMS/Retention), explizite Trennung RC/Produktion.
- **Migrationsbedarf:** keiner.
- **Sicherheitsanforderungen:** keine Secrets im Dossier; Evidence-Verweise statt Behauptungen.
- **Teststrategie:** Doku-Review, `git diff --check`, Secret-Audit.
- **Akzeptanz:** Dossier + PDF + Gate-Report konsistent, Entscheidung dokumentiert.
- **Aufwand:** 1,0 PT.

### P-15 — Policy-Gate-Erweiterung

- **Dateien:** `terraform/policy/resource-policy.json`, `terraform/policy/validate-plan.py`, `terraform/policy/`-Tests (neu), `module_builder`-Kopie.
- **Bestehender Vertrag:** Allowlist ohne KMS/Secrets; S3-SSE-Regel vorhanden.
- **Geplanter Vertrag:** Allowlist + `aws_kms_key`, `aws_kms_alias`, `aws_secretsmanager_secret`, `aws_secretsmanager_secret_version`, `aws_secretsmanager_secret_rotation`; neue Regeln: `enable_key_rotation == true`, kein `recovery_window_in_days == 0`, keine `Principal: "*"`.
- **Migrationsbedarf:** Gate-Version erhöhen; generierte Projekte erhalten die neue Gate-Kopie.
- **Sicherheitsanforderungen:** Erweiterung nur mit Begründung + Negativtests (ein nicht erlaubter Typ bleibt FAIL).
- **Teststrategie:** Positiv-/Negativ-Plans (JSON-Fixtures), Exit-Code 0/1.
- **Akzeptanz:** KMS/Secrets erlaubt mit Regeln; alle bisherigen Typen unverändert; FAIL-Fälle belegt.
- **Aufwand:** 1,0 PT.

## 3. Abhängigkeitsgraph (Reihenfolge)

```text
P-15 (Gate-Allowlist) ──┬─> P-04 (KMS) ──┬─> P-05 (DDB SSE)
                        │                ├─> P-06 (SQS SSE)
                        │                └─> P-07 (IAM/KMS)
                        └─> P-02 (Secret) ──> P-01 (Provider) ──> P-03 (Rotation)
P-08 (Retention) ──> P-09 (Cancel)
P-10 (Installer) ← P-02, P-04
P-11 (Builder)   ← P-02, P-04, P-15
P-12 (RIS)       ← alle (nur Prüfung)
P-13, P-14       ← alles
```

**Empfohlene Implementierungsreihenfolge:** P-15 → P-04 → P-07 → P-05 → P-06 →
P-01 → P-02 → P-10 → P-03 → P-08 → P-09 → P-11 → P-12 → P-13 → P-14.

## 4. Nicht im RC4-Scope (bewusst)

- Keine Multi-Region-/Global-Table-Replikation.
- Kein eigenes HSM/CloudHSM.
- Keine automatische Rotation von *Dritten* (DynamoDB/SQS Keys werden über KMS-Rotation gedreht).
- Keine RIS-Änderungen, keine Pin-Änderung.
- Keine AWS-Ausführung (Apply/Destroy) ohne gesonderte Freigabe.
