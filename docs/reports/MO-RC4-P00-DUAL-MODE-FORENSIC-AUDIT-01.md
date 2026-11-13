# MO-RC4-P00-DUAL-MODE-FORENSIC-AUDIT-01

**AWS_MANAGED/KMS vs. APP_MANAGED — Forensic Read-only Audit**

**Datum:** 2026-11-13
**Repository:** `maynowak/mays-order-aws`
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `1ef244b771e76f9fa21af736b9d387033ffcf351`
**Modus:** read-only Repository-/Git-Audit; keine AWS-Mutation, kein Terraform
Apply, keine Produktcode-/RIS-Änderung, kein Branch-Wechsel, kein Merge/Push.

```text
RC4 DUAL-MODE AUDIT COMPLETE
Implementierungsbefund: AWS_MANAGED = MISSING; APP_MANAGED = MISSING
```

## 1. Executive Summary

Die beiden RC4-Sicherheitsvarianten sind **nicht implementiert**. Vorhanden sind:

- P00-/P01-**Design- und Planungsdokumente**,
- die bestehende Privacy-Authentifizierung über die **Env-Variable**
  `PRIVACY_INTERNAL_SECRET`,
- AWS-eigene Baseline-Verschlüsselung (DynamoDB AWS-owned, SQS SSE-SQS),
- der RC4-Order-Kern mit lokal/live verifizierten Tests.

Nicht vorhanden sind:

- `secret_provider.py` / Secrets-Manager-Provider,
- `aws_kms_key` / Key-Policy / KMS-Wiring,
- DynamoDB SSE-KMS und SQS SSE-KMS,
- Rotation, Retention/TTL und Cancel-Retention,
- APP_MANAGED HMAC-/Schlüsselverwaltung,
- P00-spezifische Tests und AWS-Testnachweise.

Die Task-Annahme „bereits entwickelte Varianten“ trifft für **Code** nicht zu.
Es existieren **Designs**, keine deploybare Implementierung. Die vorhandene
Env-Secret-Lösung ist **keine** der beiden P00-Varianten.

---

## 2. Git-, Branch- und Worktree-Bestand

### 2.1 Aktueller Stand

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `1ef244b771e76f9fa21af736b9d387033ffcf351` |
| Working Tree | CLEAN |
| Branch-Wechsel | keiner |

### 2.2 Relevante Branches

| Branch | HEAD | P00/KMS-Befund |
|---|---|---|
| `feature/mo-rc4-kms-privacy-retention` | lokal `f597d14`; origin `62f6b19` | nur P00/P01-Dokumente; **kein P00-Code** |
| `test/mo-rc4-testsuite-hardening-10a` | `1ef244b` | aktueller Order-Core; **kein P00-Code** |
| `main` | `f597d14` | keine P00-Implementierung |
| weitere Branches | keine KMS-/SecretProvider-/Rotation-Implementierung | keine relevanten Codeänderungen |

### 2.3 Worktrees

| Worktree | HEAD/Branch | Relevanz |
|---|---|---|
| `/home/dci-student/projects/Mays-Orders-AWS` | `feature/mo-rc4-teststack-baseline-01` | kein P00-Code |
| `/tmp/opencode/rc3-baseline` | `086a8be` detached | RC3-Baseline |
| `/tmp/opencode/rc3-version-marker` | `test/mo-rc4-p3a-backup-execute-01` | Backup/RC3 |
| `/tmp/opencode/rc4-apply-00125ee` | `00125ee` detached | Apply-Snapshot |
| `/tmp/opencode/rc4-apply-ffbebe9` | `ffbebe9` detached | Apply-Snapshot |
| `/tmp/opencode/rc4-upgrade-plan` | aktueller Testbranch | aktueller Audit-Branch |

Keine ungesicherten Änderungen, kein Branch-Wechsel durchgeführt.

### 2.4 Git-Evidenz

- `git log --all -S'AWS_MANAGED'` → nur `62f6b19` (Dokumentation).
- `git log --all -S'APP_MANAGED'` → nur `62f6b19` (Dokumentation).
- `git log --all -S'secret_provider'` → nur Dokumentations-/Plan-Commits.
- `git log --all -- lambda/src/secret_provider.py lambda/src/rotation_handler.py` → keine Treffer.
- `git ls-tree` über alle Branches: keine Dateien
  `lambda/src/secret_provider.py`, `lambda/src/rotation_handler.py`,
  `terraform/modules/kms/*`, `terraform/modules/privacy_secret/*`.
- `git grep` über `feature/mo-rc4-kms-privacy-retention`, `test/...` und `main`:
  AWS_MANAGED/APP_MANAGED nur in Architektur-/P00-/P01-Dokumenten.

---

## 3. AWS_MANAGED / KMS — Komponentenbewertung

| Komponente | Status | Beleg / Befund |
|---|---|---|
| SecretProvider | **MISSING** | Keine `secret_provider.py`; `order_service.py:159` liest weiter Env |
| Secrets Manager | **MISSING** | Keine `aws_secretsmanager_secret*`-Ressource |
| KMS-Key | **MISSING** | Kein `aws_kms_key` im Produkt-Terraform |
| Key-Policy | **MISSING** | Keine Key-Ressource/Policy |
| DynamoDB SSE-KMS | **MISSING** | Kein `server_side_encryption`/CMK; AWS-owned Default |
| SQS SSE-KMS | **MISSING** | Nur SSE-SQS; kein `kms_master_key_id` |
| Handler-IAM KMS | **MISSING** | Keine `kms:*`-Rechte |
| Worker-IAM KMS | **MISSING** | Keine `kms:*`-Rechte |
| Terraform-Wiring | **MISSING** | Keine KMS-/Secret-Module oder Root-Variablen |
| Module-Builder-Integration | **MISSING** | Katalog/Presets ohne KMS-/Privacy-Secret-Module |
| Installer-Integration | **MISSING** | Keine KMS-/Retention-/Secret-Provider-Flags |
| Rotation | **MISSING** | Kein Rotation-Handler, keine Rotation-Ressource |
| Retention/TTL | **MISSING** | Kein `ttl`, kein `retentionUntil`, keine Retention-Policy |
| Security-Tests | **MISSING** | Keine P00-spezifischen Tests |
| AWS-Testnachweis | **MISSING** | Kein deployter KMS-/Secrets-Manager-Stack |
| P00-Design | **PARTIAL** | Design/Plan vorhanden, keine Implementierung |

### Bestehende AWS-Baseline (nicht mit P00 verwechseln)

- DynamoDB: AWS-owned Verschlüsselung, kein CMK.
- SQS: SSE-SQS (AWS-managed), kein KMS-Master-Key.
- S3/CloudTrail/Cognito-Backup: SSE-S3, nicht P00-KMS.
- `ci/iam/main.tf` enthält ein optionales `kms_key_arn` für
  CI-Artefaktverschlüsselung. Das ist **keine** P00-Implementierung und
  erzeugt keinen Key; bei leerem ARN ist die Resource `"*"` (bestehendes
  CI-Risiko, nicht RC4-P00).
- Privacy liest `PRIVACY_INTERNAL_SECRET` aus Env und vergleicht per
  `secrets.compare_digest`; das ist Shared-Secret-Authentifizierung, kein
  AWS_MANAGED-Provider.

---

## 4. APP_MANAGED / manuelle Variante

| Komponente | Status | Befund |
|---|---|---|
| Externe Schlüsselbereitstellung | **MISSING** | Nur Design in `MO-RC4-P01-SECRET-PROVIDER-DESIGN.md` |
| Schlüsselreferenzen | **MISSING** | Keine `PRIVACY_SECRET_PROVIDER`-/Key-Ref-Implementierung |
| HMAC-/Authentifizierungsverfahren | **MISSING** | Keine HMAC-Implementierung; bestehendes Env-Token ist kein APP_MANAGED |
| Schlüsselversionierung | **MISSING** | Kein `keyId`/`keyVersion`-Code |
| Manuelle Rotation | **MISSING** | Kein Rotationsverfahren/Handler |
| Wiederanlauf nach Unterbrechung | **MISSING** | Kein Provider-/Recovery-Code |
| Fail-closed | **PARTIAL** | Bestehende Env-Secret-Prüfung ist fail-closed, aber nicht APP_MANAGED |
| Sicherheits-/Regressionstests | **MISSING** | Keine APP_MANAGED-Tests |
| Design | **PARTIAL** | Phase 2a HMAC-Idee dokumentiert; **nicht RC4-Pflicht** |

`MO-RC4-P01-SECRET-PROVIDER-DESIGN.md` bezeichnet APP_MANAGED ausdrücklich als
Phase 2 und „nicht RC4-Pflicht“. Es gibt keinen Code, keine Tests und keinen
AWS-Nachweis.

---

## 5. Reports-/Auditlog-Abgleich

| Quelle | Aussage | Bewertung |
|---|---|---|
| `MO-RC4-P00-MODULE-PLAN.md` | P-01…P-15 als Plan, inkl. KMS/Secrets/Retention | **PLANUNG**, keine Implementierung |
| `MO-RC4-P00-OPEN-QUESTIONS.md` | Q-12/Q-09/Q-13 etc. offen | **OFFEN** |
| `MO-RC4-P01-SECRET-PROVIDER-DESIGN.md` | AWS_MANAGED Phase 1, APP_MANAGED Phase 2 | **DESIGN / PROPOSED** |
| `MO-RC4-P01-ORPHAN-CLEANUP-DESIGN.md` | Retention-/Orphan-Design | **DESIGN / OPEN** |
| `ORDER-ERASURE-RETENTION-DECISIONS.md` | keine Fristen/TTL/Ledger | **OPEN** |
| `MO-RC4-G1-EVIDENCE-SCOPE.md` | P-01/P-04/P-08/P-15 nicht implementiert | **bestätigt** |
| `MO-RC4-RELEASE-GATE-01.md` | P00 Scope offen, keine KMS/Secrets | **bestätigt** |
| Spätere Implementierungs-/Testberichte | keine P00-Code-/AWS-Nachweise gefunden | **keine Überholung** |

Es gibt **keinen** späteren Report, der eine P00-Implementierung belegt.

---

## 6. RC4-Gap-Matrix

| Funktion | AWS_MANAGED | APP_MANAGED | Codebeleg | Testbeleg | AWS-Beleg | Tatsächlich fehlend |
|---|---|---|---|---|---|---|
| SecretProvider | **MISSING** | **MISSING** | keiner | keiner | keiner | `lambda/src/secret_provider.py` |
| Secrets Manager | **MISSING** | **MISSING** | keine Ressource | keiner | keiner | `terraform/modules/privacy_secret/*` |
| KMS CMK/Policy | **MISSING** | **MISSING** | keine Ressource | keiner | keiner | `terraform/modules/kms/*` |
| DynamoDB SSE-KMS | **MISSING** | n/a | `terraform/modules/dynamodb/main.tf` ohne SSE | keiner | keiner | CMK-Wiring |
| SQS SSE-KMS | **MISSING** | n/a | `terraform/modules/sqs/main.tf` ohne KMS | keiner | keiner | `kms_master_key_id`/Policy |
| Handler-IAM KMS/Secrets | **MISSING** | **MISSING** | `terraform/modules/iam/main.tf` | keiner | keiner | IAM-Statements |
| Worker-IAM KMS | **MISSING** | n/a | `terraform/modules/sqs-worker/iam.tf` | keiner | keiner | IAM-Statements |
| Rotation | **MISSING** | **MISSING** | kein Handler/keine Ressource | keiner | keiner | `rotation_handler.py` + IaC |
| Retention/TTL | **MISSING** | **MISSING** | kein Feld/TTL | keiner | keiner | Datenmodell + Terraform |
| Installer-Flags | **MISSING** | **MISSING** | keine Flags | keiner | keiner | Installer-Kontext |
| Builder-Integration | **MISSING** | **MISSING** | Katalog ohne Module | keiner | keiner | Katalog/Presets |
| Security-Tests | **MISSING** | **MISSING** | keine Testdateien | keiner | keiner | Test-Suiten |
| AWS-Verifikation | **MISSING** | **MISSING** | — | — | keiner | deployter Teststack |

### Exakte fehlende Pfade

```text
lambda/src/secret_provider.py
lambda/src/rotation_handler.py
lambda/tests/test_secret_provider.py
lambda/tests/test_rotation_handler.py
terraform/modules/kms/
terraform/modules/privacy_secret/
installer/**/*kms* / *retention* / *secret_provider*
module_builder/**/*kms* / *privacy_secret*
```

Diese Pfade existieren in keinem Branch/Worktree.

---

## 7. Antworten auf die Prüffragen

1. **Ist die KMS-Variante bereits fertig implementiert?**
   **NEIN.** Es gibt keine KMS-/Secrets-Manager-/Provider-Implementierung.

2. **Ist sie lokal getestet?**
   **NEIN.** Es gibt keine P00-spezifischen Tests; die vorhandenen 1.174 Tests
   betreffen den Order-Kern und die Env-Secret-Baseline.

3. **Wurde sie in AWS getestet?**
   **NEIN.** Kein KMS-/Secrets-Manager-Teststack, kein Deploy, kein
   AWS-Nachweis. Die vorhandenen RC4-Live-Nachweise betreffen Order/Privacy
   mit temporärem Env-Secret, nicht P00.

4. **Ist APP_MANAGED bereits implementiert?**
   **NEIN.** Nur Design/Phase-2-Analyse; kein HMAC-, Key-Ref-, Versionierungs-
   oder Rotationscode.

5. **Welche Variante ist für RC4 tatsächlich vorgesehen?**
   Laut `MO-RC4-P01-SECRET-PROVIDER-DESIGN.md` ist **AWS_MANAGED Phase 1** die
   RC4-Empfehlung; APP_MANAGED ist Phase 2 und ausdrücklich **nicht
   RC4-Pflicht**. Der RC4-Release-Gate-Bericht hält den P00-Scope jedoch offen;
   daher ist auch die AWS_MANAGED-Zuordnung noch nicht formal freigegeben.

6. **Was fehlt RC4 gegenüber dem bereits fertigen RC3 wirklich?**
   - SecretProvider/Secrets Manager
   - KMS CMK/Key-Policy und KMS-Wiring
   - DynamoDB-/SQS-SSE-KMS
   - KMS-/Secrets-IAM
   - Rotation
   - Retention/TTL/Cancel-Retention
   - P00-Sicherheits- und AWS-Tests
   - Installer-/Builder-Integration

7. **Welche Arbeiten sind bereits erledigt und dürfen nicht wiederholt werden?**
   - P00-Baseline, Modulplan, offene Fragen
   - P01-Contract-Inventory, SecretProvider-Design, Orphan-/Retention-Design,
     ADR-008 (PROPOSED)
   - RC4-Order-Kern P02/P02A/P02C/P02E/P02F/P02G/P02H/P02I
   - G3-FIX, G3-LIVE-B1, Owner-Isolation, B2 Live/Cleanup
   - Lokale 1.174 PASS und B2 14/1-SKIP-Nachweis

---

## 8. Release-/Scope-Bewertung

- **AWS_MANAGED:** Design vorhanden, Code/Tests/AWS fehlen → **MISSING**.
- **APP_MANAGED:** Design vorhanden, Code/Tests fehlen → **MISSING**.
- **RC3-Order-Kern:** vorhanden, getestet, live verifiziert; nicht erneut
  implementieren.
- **P00-Scope:** nicht formal entschieden. Eine Scope-Reduktion ist nicht
  autorisiert.
- **RC4-Modul:** ohne P00-Scope-Entscheidung weiterhin **CONDITIONAL**.
- **Produktion:** ohne P00/SEC-06/Retention **NO-GO**.

---

## 9. Abschlussstatus

```text
RC4 DUAL-MODE AUDIT COMPLETE
AWS_MANAGED: MISSING
APP_MANAGED: MISSING
```

Der Audit ist vollständig; die Evidenzlage ist ausreichend, um beide Varianten
als **nicht implementiert** zu klassifizieren. Es wurden keine Funktionen
implementiert, keine AWS-Ressourcen verändert und keine Tests wiederholt.

**STOP — keine Implementierung, kein Terraform Apply, kein RIS, kein
Release-Tag, kein Push/Merge.**

---

## 10. Commit / Working Tree

| Feld | Wert |
|---|---|
| Dokumentations-Commit | `b529dac58355958417c0de1578e79140d8952967` |
| Working Tree nach Commit | CLEAN |

Keine Produkt-, AWS-, Terraform-, RIS- oder CI-Änderung.
