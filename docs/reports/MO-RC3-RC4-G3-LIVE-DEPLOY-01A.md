# MO-RC3-RC4-G3-LIVE-DEPLOY-01A

**Vorbereitung des kontrollierten Lambda-Code-Updates auf den RC4-Teststack**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `39c5feef9d49aec767cc639a00eae12f7a394f1c`
**Modus:** ausschließlich Vorbereitung und read-only AWS-Prüfung;
**keine AWS-Mutation, kein Lambda-Update, kein Terraform, kein Deployment,
keine Pipeline-Auslösung, kein Push/Merge.**

```text
STATUS: READY FOR DEPLOYMENT APPROVAL
DEPLOYMENT: NOT EXECUTED
```

---

## 1. Executive Summary

Das kontrollierte Lambda-Code-Update ist technisch vorbereitet:

- Lokales G3-FIX-ZIP: `1584ee0d…` / Lambda-Base64 `FYTuDcz…`.
- Aktuell deployed: `vW8nlTjAd9b+…` (altes ZIP `bd6f2795…`).
- Beide Funktionen sind `Active`, `$LATEST`, ohne Alias/Versionen.
- IAM `AdministratorAccess` erlaubt `lambda:UpdateFunctionCode` für beide
  Funktionen (read-only simuliert).
- Ein direktes `aws lambda update-function-code` löst **keine** CodePipeline
  aus; es ist ein manueller Teststack-Eingriff.
- Ein Rollback-Artefakt ist verfügbar (altes ZIP aus Git `75a32fc^`) und
  hash-identisch zum deployed Code.

Es wurde **nichts** deployed oder verändert. Der Status ist
`READY FOR DEPLOYMENT APPROVAL`, nicht „deployed“.

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `39c5feef9d49aec767cc639a00eae12f7a394f1c` |
| Working Tree | CLEAN |
| G3-FIX-Commit | `39c5fee` |
| Lokale Regression | 1.158 PASS + 28 Seed (aus G3-FIX) |
| Letzter Live-Stand | G3 4/4 PASS gegen **alten** deployed Code |

---

## 3. Bestätigte Zielressourcen

| Ressource | Identität |
|---|---|
| AWS-Profil | `mayaws` |
| Account | `240571105849` |
| Region | `eu-central-1` |
| API-Handler | `mays-orders-rc4-test-handler` |
| SQS-Worker | `mays-orders-rc4-test-sqs-worker` |
| Handler-ARN | `arn:aws:lambda:eu-central-1:240571105849:function:mays-orders-rc4-test-handler` |
| Worker-ARN | `arn:aws:lambda:eu-central-1:240571105849:function:mays-orders-rc4-test-sqs-worker` |
| Tabelle | `mays-orders-rc4-test` |
| Queue | `mays-orders-rc4-test-orders-queue` |
| DLQ | `mays-orders-rc4-test-orders-queue-dlq` |

Es werden keine anderen Funktionen, Konten oder Regionen verwendet.

---

## 4. Artefaktidentität

### 4.1 Lokales G3-FIX-Artefakt

| Eigenschaft | Wert |
|---|---|
| Pfad | `lambda/dist/lambda.zip` |
| Größe | 36.583 Bytes |
| SHA-256 | `1584ee0dcccd0b042277827184575a1876c159c75a7a0e95ccd29b4fe5a37e44` |
| Lambda-Base64 | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Build | `python3 build_zip.py` nach G3-FIX |

Enthaltene Fixes (lokal im ZIP geprüft):

- `order_service.py`: GSI2-Query nur `orderId`; vollständiges `GetItem` für
  `consumerId` (F-PRV-01).
- `recovery.py`: Scan-/Limit-Trennung, aktueller Zielstatus
  (GSI3-GAP-01/02/03).
- `index.py`: `_send_processing_recovery(order_id, status=...)`.

### 4.2 Aktuell deployed

| Funktion | Version | RevisionId | CodeSha256 | LastModified | CodeSize |
|---|---|---|---|---|---|
| Handler | `$LATEST` | `1e1b3e1f-0d47-4192-9d9a-da09405f8f41` | `vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=` | 2026-11-11T17:52:19Z | 35.918 |
| Worker | `$LATEST` | `6293e2a8-18db-4de8-b0e3-103ce4bfa826` | `vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=` | 2026-11-11T17:52:25Z | 35.918 |

Keine Aliasse, keine veröffentlichten Versionen.

### 4.3 Eindeutige Zuordnung

```text
Deployed CodeSha:     vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=
Altes ZIP (75a32fc^): bd6f279538c077d6fe1778d8a7ed67b0a6760314416030429de5e14a69dcd323
                      Base64 vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=  MATCH
Neues G3-FIX-ZIP:     FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=
                      MISMATCH → Update erforderlich
```

Damit ist die Deployment-Identität eindeutig: **alter Code deployed**.

---

## 5. Geplante Mutationen (nicht ausgeführt)

Nur nach ausdrücklicher Deployment-Freigabe:

```bash
# 1) Neues G3-FIX-Artefakt bereitstellen
cp /tmp/opencode/rc4-upgrade-plan/lambda/dist/lambda.zip \
   /tmp/opencode/g3fix-new-lambda.zip

# 2) Handler aktualisieren
aws lambda update-function-code \
  --profile mayaws --region eu-central-1 \
  --function-name mays-orders-rc4-test-handler \
  --zip-file fileb:///tmp/opencode/g3fix-new-lambda.zip

# 3) Worker aktualisieren
aws lambda update-function-code \
  --profile mayaws --region eu-central-1 \
  --function-name mays-orders-rc4-test-sqs-worker \
  --zip-file fileb:///tmp/opencode/g3fix-new-lambda.zip
```

**Kein `--publish`**: keine neuen Versionen/Aliasse werden erzeugt; beide
Funktionen bleiben `$LATEST`. Das minimiert die Mutation.

**Nicht enthalten:** Konfigurationsänderung, ESM-Änderung, IAM/SQS/DynamoDB,
Terraform, Pipeline-Start.

---

## 6. IAM-/Pipeline-Prüfung

### 6.1 IAM

Read-only:

```text
Mayaws → AdministratorAccess
lambda:UpdateFunctionCode / GetFunction / GetFunctionConfiguration → allowed
```

Die breite AdministratorAccess-Berechtigung ist für einen Teststack akzeptabel,
aber keine Least-Privilege-Operatorrolle. Für den Lauf ist nur der genannte
Lambda-Code-Update nötig.

### 6.2 Pipeline

Vorhandene Pipelines:

- `directAWSGit-Mays-Order-AWS`
- `mays-orders-development-ci-cd`

Ein manueller `aws lambda update-function-code`-Aufruf startet **keine**
Pipeline. Es wird kein Git-Push/Merge ausgelöst. Die bekannte
`directAWSGit`-Auto-Apply-Gefahr bleibt für spätere Pushes bestehen; sie wird
durch diesen Lauf nicht berührt.

**Terraform-Drift:** Das direkte Lambda-Update liegt außerhalb des
Terraform-/Installer-Pfads. Nach dem Testlauf ist ein read-only
Terraform-Plan/Drift-Check und eine separate Reconciliation-Entscheidung
erforderlich; es wird hier kein Terraform ausgeführt.

---

## 7. Rollback-Evidence

### 7.1 Rollback-Artefakt

```text
/tmp/opencode/g3fix-old-lambda.zip
SHA-256 bd6f279538c077d6fe1778d8a7ed67b0a6760314416030429de5e14a69dcd323
Base64  vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=
```

Quelle: `git show 75a32fc^:lambda/dist/lambda.zip` (altes deployed ZIP).
Falls die temporäre Datei fehlt, kann sie aus dem Git-Objekt wiederhergestellt
werden.

### 7.2 Rollback-Kommandos (vorbereitet, nicht ausgeführt)

```bash
# Rollback Handler
aws lambda update-function-code \
  --profile mayaws --region eu-central-1 \
  --function-name mays-orders-rc4-test-handler \
  --zip-file fileb:///tmp/opencode/g3fix-old-lambda.zip

# Rollback Worker
aws lambda update-function-code \
  --profile mayaws --region eu-central-1 \
  --function-name mays-orders-rc4-test-sqs-worker \
  --zip-file fileb:///tmp/opencode/g3fix-old-lambda.zip
```

Nach Rollback muss `CodeSha256` wieder
`vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=` sein.

### 7.3 Rollback-Grenzen

- Kein automatischer Rollback bei Testfehlern; nur manuell nach Freigabe.
- Keine Rückkehr zu ungebundenen/unsicheren Deployments.
- Keine Terraform-/State-Änderung als Rollback.
- Keine Alias-/Version-Rollback nötig, da keine Aliasse/Versionen existieren.

---

## 8. Post-Deployment-Verifikation

Nach einem freigegebenen Update:

| Prüfung | Erwartung |
|---|---|
| Handler CodeSha256 | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Worker CodeSha256 | derselbe Hash |
| State / LastUpdateStatus | `Active` / `Successful` |
| Handler/Worker Handler | `index.handler` / `sqs_handler.handler` |
| Runtime/Timeout/Memory | unverändert (`python3.14`, 10 s, 128 MB) |
| Role | unverändert |
| Environment | unverändert; kein neues Secret |
| ESM | `Enabled`, Batch Size 5, `ReportBatchItemFailures` |
| Queues/DLQ | 0/0 vor und nach Smoke-Test |
| GSI3 | ACTIVE/KEYS_ONLY, keine unerwarteten Einträge |
| CloudWatch | 7 Alarme, Lambda Errors nicht erhöht |
| API | Routen unverändert; 401 ohne Token weiterhin |
| Drift | separater read-only Terraform/Installer-Drift-Check erforderlich |

Die tatsächliche Live-E2E-Ausführung bleibt ein separater Freigabeschritt.

---

## 9. Abbruchbedingungen

- Keine ausdrückliche Deployment-Freigabe.
- Branch/HEAD/Working Tree abweichend.
- Account/Region/Function-ARN nicht wie oben.
- Aktueller AWS-CodeSha nicht `vW8nl…` (fremde Änderung).
- Lokales ZIP-Hash nicht `1584ee0d…`.
- Handler/Worker State nicht `Active` oder `LastUpdateStatus` nicht
  `Successful`.
- Pipeline läuft oder geplanter Push/Merge.
- ESM/Queue/DLQ/GSI3-Baseline fremd/nicht 0.
- Update würde Konfiguration, IAM, Secrets, ESM oder andere Ressourcen ändern.
- Rollback-Artefakt nicht hash-identisch.
- Unerwartete CloudWatch-Fehler nach Update.

---

## 10. Cleanup / operative Grenzen

- Kein Testdaten-Cleanup in diesem Auftrag, da keine Mutation ausgeführt wurde.
- Nach einem späteren Deployment: nur Teststack `mays-orders-rc4-test`,
  Testbenutzer/Orders/Messages exakt und eigentümergebunden, kein Purge.
- Keine Secrets auslesen/schreiben.
- Keine produktiven/RIS-Ressourcen.

---

## 11. Auditlog-Nachweis

Vorgesehener Eintrag:

```text
MO-RC3-RC4-G3-LIVE-DEPLOY-01A → docs/reports/MO-RC3-RC4-G3-LIVE-DEPLOY-01A.md
(read-only Deployment-Vorbereitung: lokales G3-FIX-ZIP 1584ee0d…/FYTuDcz…,
AWS CodeSha vW8nl… = altes ZIP bd6f2795…; beide Functions Active/$LATEST,
keine Aliasse/Versionen; IAM UpdateFunctionCode allowed; Pipelines vorhanden,
CLI-Update löst keine Pipeline aus; Rollback-Artefakt verifiziert; keine
AWS-/Terraform-Mutation, kein Push)
```

---

## 12. Commit / Status

Vorgesehen:

```text
Commit: docs(rc3,rc4): prepare controlled lambda code deployment
Dateien: docs/reports/MO-RC3-RC4-G3-LIVE-DEPLOY-01A.md
         docs/AI_AUDITLOG.md
```

Kein Push, kein Merge, keine AWS-Mutation.

```text
STATUS: READY FOR DEPLOYMENT APPROVAL
DEPLOYMENT: NOT EXECUTED
```
