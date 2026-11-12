# MO-RC3-RC4-G3-LIVE-DEPLOY-01B

**Controlled Lambda Deployment & Verification**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Deployment:** `34a8d9fba62ac753eed1399490fc82ac359e0df6`
**Modus:** autorisierte, eng begrenzte Lambda-Code-Deployments auf zwei
RC4-Testfunktionen; **keine** Live-E2E-Tests, keine Konfigurations-, IAM-,
SQS-, DynamoDB-, Cognito-, Secret- oder Terraform-Mutation, kein Push/Merge.

```text
STATUS: DEPLOYED & VERIFIED
Live-E2E: NOT EXECUTED
```

---

## 1. Executive Summary

Das lokal verifizierte G3-FIX-Artefakt wurde auf genau zwei Funktionen des
RC4-Teststacks deployed:

- `mays-orders-rc4-test-handler`
- `mays-orders-rc4-test-sqs-worker`

Beide Funktionen verwenden jetzt:

```text
CodeSha256 FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=
CodeSize   36583
Version    $LATEST
```

Die Lambda-Konfigurationen, ESM, Queues, DynamoDB/GSI3 und CloudWatch-Alarme
blieben unverändert. Es wurden keine Live-Orders, SQS-Nachrichten, Cognito-
Benutzer oder Tests erzeugt. Die Pipeline wurde nicht gestartet.

---

## 2. Preflight

| Prüfung | Ergebnis |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `34a8d9fba62ac753eed1399490fc82ac359e0df6` |
| Working Tree | CLEAN |
| AWS Account | `240571105849` |
| Identity | `arn:aws:iam::240571105849:user/Mayaws` |
| Region | `eu-central-1` |
| Neues ZIP SHA-256 | `1584ee0dcccd0b042277827184575a1876c159c75a7a0e95ccd29b4fe5a37e44` |
| Neues ZIP Base64 | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Rollback ZIP SHA-256 | `bd6f279538c077d6fe1778d8a7ed67b0a6760314416030429de5e14a69dcd323` |
| Rollback ZIP Base64 | `vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=` |

### Vorher

| Funktion | Version | RevisionId | CodeSha256 | State |
|---|---|---|---|---|
| Handler | `$LATEST` | `1e1b3e1f-0d47-4192-9d9a-da09405f8f41` | `vW8nl…` | Active/Successful |
| Worker | `$LATEST` | `6293e2a8-18db-4de8-b0e3-103ce4bfa826` | `vW8nl…` | Active/Successful |

Handler-Konfiguration: `index.handler`, `python3.14`, 10 s, 128 MB,
`mays-orders-rc4-test-handler-role`, Env `ORDERS_TABLE`,
`SQS_QUEUE_URL`, `ORDERS_PROJECT_NAME`.

Worker-Konfiguration: `sqs_handler.handler`, `python3.14`, 10 s, 128 MB,
`mays-orders-rc4-test-sqs-worker-role`, Env `ORDERS_TABLE`.

ESM `dbde8c61-c116-42f1-97e6-782edd900c3d` Enabled, Batch 5,
`ReportBatchItemFailures`; Queue/DLQ 0/0; keine Aliasse/Versionen.

---

## 3. Ausgeführte AWS-Operationen

Nur die folgenden beiden Mutationen wurden ausgeführt:

```bash
aws lambda update-function-code \
  --profile mayaws --region eu-central-1 \
  --function-name mays-orders-rc4-test-handler \
  --zip-file fileb:///tmp/opencode/g3fix-new-lambda.zip \
  --revision-id 1e1b3e1f-0d47-4192-9d9a-da09405f8f41
```

```bash
aws lambda update-function-code \
  --profile mayaws --region eu-central-1 \
  --function-name mays-orders-rc4-test-sqs-worker \
  --zip-file fileb:///tmp/opencode/g3fix-new-lambda.zip \
  --revision-id 6293e2a8-18db-4de8-b0e3-103ce4bfa826
```

Anschließend jeweils:

```bash
aws lambda wait function-updated ...
```

Kein `--publish`, keine Alias-/Versionsänderung, keine
Konfigurationsänderung.

---

## 4. Post-Deployment-Verifikation

| Prüfung | Ergebnis |
|---|---|
| Handler CodeSha256 | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Worker CodeSha256 | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Handler State/LastUpdate | `Active` / `Successful` |
| Worker State/LastUpdate | `Active` / `Successful` |
| Handler RevisionId | `c559246f-3aca-4966-b252-04389e401fd3` |
| Worker RevisionId | `96dba311-042f-465d-b967-6530886281dd` |
| Handler `LastModified` | `2026-11-12T16:59:11Z` |
| Worker `LastModified` | `2026-11-12T16:59:23Z` |
| Handler/Runtime/Timeout/Memory/Role | unverändert |
| Worker/Runtime/Timeout/Memory/Role | unverändert |
| Environment | unverändert; kein neues Secret |
| ESM | Enabled, Batch 5, `ReportBatchItemFailures` |
| Main Queue / DLQ | 0/0 und 0/0 |
| DynamoDB | ACTIVE, 0 Items |
| GSI3 | ACTIVE, KEYS_ONLY |
| CloudWatch | 7 RC4-Alarme OK |
| API-Routen | unverändert |
| Pipeline | `directAWSGit` Deploy-Stage `Stopped`; keine Auslösung durch CLI |

---

## 5. Terraform Drift / Reconciliation

Read-only, ohne Apply:

```bash
TF_WORKSPACE=mays-orders-rc4-test AWS_PROFILE=mayaws \
terraform -chdir=terraform plan -lock=false -refresh=false -input=false -no-color \
  -var project_name=mays-orders-rc4-test \
  -var deployment_version=0.2.0 \
  -var enable_cognito_backup=false \
  -var enable_cognito_backup_automation=false \
  -var seed_example_data=false \
  -var monitoring_enabled=true
```

Ergebnis:

```text
Plan: 0 to add, 2 to change, 0 to destroy.
```

Die einzigen geplanten Änderungen sind die erwarteten Lambda-Driftwerte:

```text
module.lambda.aws_lambda_function.handler
  source_code_hash: vW8nl… -> FYTuDcz…

module.sqs_worker.aws_lambda_function.worker
  source_code_hash: vW8nl… -> FYTuDcz…
```

Das ist die erwartete Terraform-Reconciliation des direkten Lambda-Updates;
**kein Apply** wurde ausgeführt. Ein erster lokaler Plan ohne die korrekten
Projektvariablen wurde verworfen; er hatte einen falschen Projektkontext
(`mays-orders` statt `mays-orders-rc4-test`) und wurde nicht angewendet.

---

## 6. Rollback-Evidence

Rollback-Artefakt:

```text
/tmp/opencode/g3fix-old-lambda.zip
SHA-256 bd6f279538c077d6fe1778d8a7ed67b0a6760314416030429de5e14a69dcd323
Base64  vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=
```

Rollback wurde **nicht** benötigt. Die vorbereiteten Kommandos sind im
G3-LIVE-DEPLOY-01A-Bericht dokumentiert; bei Bedarf würde ein Update mit
diesem ZIP und dem jeweils aktuellen RevisionId-Schutz erfolgen.

---

## 7. Sicherheits- und Boundary-Nachweis

| Prüfung | Ergebnis |
|---|---|
| AWS-Mutationen | **nur die zwei autorisierten Lambda-Code-Updates** |
| Lambda-Konfigurationsänderung | **NEIN** |
| IAM-/Secret-/Cognito-Änderung | **NEIN** |
| SQS Send/Receive/Delete/Purge | **NEIN** |
| DynamoDB Write/Delete | **NEIN** |
| Lambda Invoke / Live-E2E | **NEIN** |
| Terraform Apply/Destroy | **NEIN** |
| Pipeline-Auslösung | **NEIN** |
| Git Push/Merge | **NEIN** |
| Produkt-/RIS-Ressource | **NEIN** |

Der Teststack war vor und nach dem Deployment leer; es wurden keine
Testdaten erzeugt.

---

## 8. Verbleibende Punkte

- Live-E2E-Tests bleiben separat freigabepflichtig.
- Privacy bleibt durch fehlendes Secret/Invoke-Recht blockiert.
- Terraform-Reconciliation (`0 add / 2 change`) ist vor einem späteren
  Terraform-Apply separat zu entscheiden; kein Apply in diesem Auftrag.
- DLQ/Recovery/Compatibility-Live-Matrix noch nicht ausgeführt.
- P00, API-Idempotenz, Processing-Aktivierung und SEC-06 bleiben offene
  Releaseentscheidungen.

---

## 9. Auditlog / Git

Vorgesehener Auditlog-Eintrag:

```text
MO-RC3-RC4-G3-LIVE-DEPLOY-01B → docs/reports/MO-RC3-RC4-G3-LIVE-DEPLOY-01B.md
(autorisiertes Lambda-Code-Update nur Handler+Worker auf G3-FIX-ZIP
1584ee0d…/FYTuDcz…; RevisionIds 1e1b…/6293… → c559…/96db…;
CodeSha vorher vW8nl…, nachher FYTu…; State Active/Successful; Konfiguration/
ESM/Queues/GSI3/Alarme unverändert; Terraform read-only Plan 0 add/2 change
nur source_code_hash, kein Apply; Rollback-Artefakt vorhanden, nicht benötigt;
keine Live-E2E, kein Push/Merge)
```

Vorgesehene Doku-Commits:

```text
Deployment-Vorbereitung: 34a8d9f
Bericht/Auditlog:       (dieser Commit)
```

Der finale Working-Tree-Status wird nach dem Commit geprüft.

```text
STATUS: DEPLOYED & VERIFIED
LIVE-E2E: NOT EXECUTED
```
