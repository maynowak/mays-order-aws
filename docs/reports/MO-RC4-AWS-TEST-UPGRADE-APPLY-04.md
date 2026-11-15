# MO-RC4-AWS-TEST-UPGRADE-APPLY-04

**Präoperative Visite für den RC4-Test-Apply (CONDITIONAL GO)**

**Datum:** 2026-11-11
**Branch:** `test/mo-rc4-aws-test-upgrade-apply-04` (ab `e357ac0`)
**Modus:** ausschließlich Pre-Op/read-only. **Kein Apply, kein Destroy, kein Backup,
kein State-Write, kein Push/Merge.**

```text
RC4 PRE-OP VERIFIED — APPLY AUTHORIZATION REQUIRED
APPLY_NOT_AUTHORIZED
```

---

## 1. Git-Ausgangslage

| Feld | Wert |
|---|---|
| Ausgangsbranch | `test/mo-rc4-aws-test-upgrade-plan-03` |
| Ausgangs-HEAD | `e357ac0` |
| Arbeitsbranch | `test/mo-rc4-aws-test-upgrade-apply-04` |
| Plan-Code-Pin | `ffbebe9` |
| Working Tree vor Pre-Op | CLEAN |

`ffbebe9` ist der notwendige Fix des Readiness-Aufrufs (kein Sicherheitsgate
wurde abgeschwächt); der Plan wurde mit diesem Code erstellt.

---

## 2. AWS-Identität

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| Account | `240571105849` — VERIFIED |
| Region | `eu-central-1` |
| ARN | `arn:aws:iam::240571105849:user/Mayaws` |
| Zeitstempel | `2026-11-11T11:04:55Z` |

Kein Fallback auf ein anderes Profil.

---

## 3. Terraform-State

| Feld | Wert |
|---|---|
| Workspace | `mays-orders-rc4-test` |
| State-Key | `env:/mays-orders-rc4-test/terraform.tfstate` |
| Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| Serial | `4` |
| Managed Resources | 37 |
| `mo_version` | `0.1.0` |
| Kanonischer Fingerprint | `670bc917fe4671df2ecb7b317068160c8fc452e02e87aa7a63b3b63e864f2a4a` |
| Fingerprint-Version | `canonical-sha256-v1` |

---

## 4. Planidentität

| Feld | Wert |
|---|---|
| Planpfad | `/tmp/opencode/rc4-upgrade-plan/.mays-installer/runs/20261111-113743/plans/mays-orders-rc4-test-rc4-test-0.2.0-H2-240571105849-deploy-0001.tfplan` |
| Plan-SHA-256 | `8fe8facf39966afba26ff85f16e13631fa8295bf0cb7473f2b8d08e03883b49c` |
| Manifest-SHA-256 | `64371e6d6a8307a84a4f91e4101567f95c2bc9c3587d645212608b37ce56ab32` |
| Manifest-Version | 2 |
| Source/Target | `0.1.0` / `0.2.0` |
| Workspace | `mays-orders-rc4-test` |

Plan und Manifest sind vorhanden, unverändert und hash-identisch mit der
Freigabegrundlage.

### Planaktionen

| Aktion | Anzahl |
|---|---:|
| CREATE | **2** |
| UPDATE | **7** |
| DELETE | **0** |
| REPLACE | **0** |
| READ | **1** |
| UNKNOWN Action | **0** |

Terraform: `Plan: 2 to add, 7 to change, 0 to destroy.`

---

## 5. Backup-Gate

| Feld | Wert |
|---|---|
| Backup-ARN | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092` |
| AWS-Status | **AVAILABLE** |
| PITR | **ENABLED** |
| Evidence | `docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01/order-backup-evidence.json` |
| Evidence-SHA-256 | `4e2129ffb3828a7a6555a7107bacc6874a4a6936d6432f13557474a8770fad94` |
| evidenceKind | `EXISTING_BACKUP_REVALIDATION` |
| Gate | **VERIFIED** |

Die Backup-ARN wurde unabhängig über `--backup-arn` gebunden und exakt geprüft.

---

## 6. REVIEW_REQUIRED — Einzelbewertung der sieben Updates

Die Klassifikation `REVIEW_REQUIRED` bleibt bestehen; sie wird nicht zu PASS
umklassifiziert.

| # | Terraform-Adresse | Vorher → Nachher | Wirkung | Risiko | Review |
|---|---|---|---|---|---|
| 1 | `module.dynamodb.aws_dynamodb_table.orders` | GSI1/GSI2 → GSI1/GSI2/GSI3; `pk`/`sk` unverändert | additive Processing-Recovery-Index | GSI-Backfill/Aktivierung; keine Datenlöschung | **ACCEPT** |
| 2 | `module.iam.aws_iam_role_policy.handler` | GSI1/GSI2-Query → GSI1/GSI2/GSI3-Query | Handler darf GSI3 lesen | minimale Rechteerweiterung um GSI3 | **ACCEPT** |
| 3 | `module.iam.aws_iam_role_policy.sqs[0]` | SQS:SendMessage unverändert beabsichtigt; `policy` im Plan `after_unknown` | Queue-Send-Recht bleibt | Policy-Inhalt erst bei Apply berechnet; post-apply verifizieren | **ACCEPT WITH POST-CHECK** |
| 4 | `module.lambda.aws_lambda_function.handler` | Code-Hash `sQGKO9A0…` → `vW8nlTjA…` | RC4-Handler-Code | Lambda-Code-Update, kein Env-/IAM-Replace | **ACCEPT** |
| 5 | `module.sqs.aws_sqs_queue.orders` | Retention 120 s → 345600 s; Visibility 30 s → 60 s; Redrive → DLQ | RC4-DLQ/Retry-Konfiguration | Redrive-Policy im Plan unknown; post-apply prüfen | **ACCEPT WITH POST-CHECK** |
| 6 | `module.sqs_worker.aws_lambda_event_source_mapping.sqs_worker` | FunctionResponseTypes `[]` → `ReportBatchItemFailures` | partielle Batch-Fehlerbehandlung | Semantik der Worker-Fehlerbehandlung ändert sich | **ACCEPT** |
| 7 | `module.sqs_worker.aws_lambda_function.worker` | Code-Hash `sQGKO9A0…` → `vW8nlTjA…` | RC4-Worker-Code | Lambda-Code-Update, kein Env-/IAM-Replace | **ACCEPT** |

### Creates

- `module.sqs.aws_sqs_queue.dlq`
- `module.monitoring.aws_cloudwatch_metric_alarm.dlq_messages[0]`

### Review-Entscheidung

**ACCEPTED FOR TEST APPLY**, mit zwei post-apply Pflichtprüfungen:

1. IAM-SQS-Policy enthält weiterhin ausschließlich `sqs:SendMessage` auf die
   Test-Queue (kein Wildcard, keine zusätzlichen Aktionen).
2. SQS-Redrive-Policy verweist ausschließlich auf die neue Test-DLQ; keine
   bestehende Queue/RIS-Queue wird referenziert.

Die ursprüngliche Klassifikation bleibt `REVIEW_REQUIRED`; der Apply benötigt
`--accept-upgrade-review`.

---

## 7. P0A / P0C / P1 / P3A

| Gate | Ergebnis |
|---|---|
| P0A Protected Resources | **PASS** — DELETE=0, REPLACE=0; keine destruktive geschützte Änderung |
| P0C Drift | **PASS (REVIEW)** — 20 Drift-Einträge; S3/Cognito-Normalisierung benigne, keine kritische Drift |
| P1 Upgrade-Readiness | **REVIEW_REQUIRED** — keine blockierenden Gründe; Classification REVIEW |
| P3A Backup-Gate | **VERIFIED** — ARN, Evidence, Fingerprint/Version |
| Minor-Matrix | **COMPATIBLE** `0.1.0 → 0.2.0` |

---

## 8. Freigabestatus

```text
RC4 PRE-OP VERIFIED — APPLY AUTHORIZATION REQUIRED
APPLY_NOT_AUTHORIZED
```

Es wurde **kein Apply** ausgeführt. Die Ausführung benötigt eine neue,
ausdrückliche Operator-Freigabe mit genau diesem Plan-Hash:

```text
8fe8facf39966afba26ff85f16e13631fa8295bf0cb7473f2b8d08e03883b49c
```

Die Freigabe muss `--accept-upgrade-review` einschließen; ohne sie bleibt der
Apply-Gate-Pfad bei `REVIEW_REQUIRED` blockiert.

---

## 9. Tatsächlich ausgeführte Aktionen

- AWS STS/Describe/Get/List (read-only)
- `terraform state pull` (read-only)
- `terraform show -json` des vorhandenen Plans (read-only)
- Backup-Gate-Auswertung lokal
- keine AWS-Mutation, kein Backup, kein Terraform-Plan/Apply

---

## 10. Postoperative Diagnose (nur Plan für später)

Nach separater Apply-Freigabe sind ausschließlich lesende Prüfungen
vorgesehen:

- Tabelle ACTIVE, `pk`/`sk`, GSI1/GSI2/GSI3 ACTIVE, PITR
- Lambda Handler/Worker ACTIVE, erwartete Code-Hashes
- SQS Queue + DLQ, Redrive-Policy, Event-Source-Mapping
- CloudWatch-DLQ-Alarm
- IAM Handler-Policy (GSI3, Logs) und SQS-Policy (keine Wildcards)
- Cognito/CloudTrail unverändert
- `mo_version=0.2.0`
- Keine RIS-Ressource geändert

Keine echten Order-/PII-Daten; keine produktiven Endpunkte.

---

## 11. Offene Risiken

| ID | Risiko | Bewertung |
|---|---|---|
| R-01 | SQS-Policy `after_unknown` | post-apply prüfen |
| R-02 | SQS-Redrive-Policy `after_unknown` | post-apply prüfen |
| R-03 | `REVIEW_REQUIRED` erfordert explizite Review-Freigabe | Apply nur mit `--accept-upgrade-review` |
| R-04 | Manifest/Evidence nicht signiert | bestehende Vertrauensgrenze |
| R-05 | CloudTrail-Zweitinstanz läuft weiter | Kosten/Log-Duplikate |
| R-06 | Testtabelle leer | keine Datenmigrationsaussage |

---

## 12. Nächster Schritt

Separate Apply-Freigabe für den konkreten Plan-Hash; danach ausschließlich der
gebundene Plan, mit `--accept-upgrade-review`. Keine Neuplanung, kein Destroy,
kein zusätzliches Backup.

Bericht: `docs/reports/MO-RC4-AWS-TEST-UPGRADE-APPLY-04.md`

**Kein Apply, keine AWS-Mutation, kein Push/Merge. STOP.**
