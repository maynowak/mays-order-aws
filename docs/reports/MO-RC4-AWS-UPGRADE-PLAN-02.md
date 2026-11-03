# MO-RC4-AWS-UPGRADE-PLAN-02

**Realer RC3 `0.1.0` → RC4 `0.2.0`-Upgrade-Plan**

**Datum:** 2026-11-03
**Branch:** `test/mo-rc4-aws-upgrade-plan-02` (ab `2e09e72`)
**Freigabe:** `GO` für Planerstellung/Prüfung; **kein Apply**.
**Status:** `RC4 UPGRADE PLAN BLOCKED`

```text
APPLY_NOT_AUTHORIZED
```

---

## 1. Benutzerfreigabe

Planerstellung und -prüfung wurden freigegeben. Ein Terraform Apply ist
ausdrücklich **nicht** freigegeben. Es wurde kein Apply ausgeführt.

---

## 2. Git-Ausgangsstand

| Feld | Wert |
|---|---|
| Ausgangsbranch | `test/mo-rc4-p3a-backup-execute-01` |
| Ausgangs-HEAD | `1a83282` |
| Arbeitsbranch | `test/mo-rc4-aws-upgrade-plan-02` |
| RC3-Basis | `086a8be` |
| RC3-Marker | `ff60a65` |
| RC4-Code-Pin | `2e09e72` |
| Working Tree | CLEAN |

**Korrektur zur Auftragsannahme:** `0756563` ist **kein** RC3-Baseline-Branch,
sondern ein RC4-Dokumentations-/Teststack-Branch. Die RC3-Baseline liegt auf
`test/mo-rc3-version-marker-01` @ `ff60a65` (Code-Basis `086a8be`). Der
tatsächliche RC4-Implementierungsstand für diesen Plan ist `2e09e72`
(`feature/mo-rc4-upgrade-release-gates`), von dem der Arbeitsbranch abzweigt.

---

## 3. Tatsächlicher RC4-Code-Pin

| Feld | Wert |
|---|---|
| Commit | `2e09e72d0e44a7f297dd379eac191acc3b63ac84` |
| Terraform | RC4-Root mit `deployment_version` + `mo_version` |
| Installer | RC4-Upgrade-Orchestrierung (P0A/P0B/P0C/P1/P3A/Release-Gates) |
| Version-Matrix | `0.1.0 → 0.2.0 = COMPATIBLE` |
| Backup-Gate | `installer/core/backup_gate.py` |
| Geschützte Typen | DynamoDB, S3, Cognito, SQS |

---

## 4. RC3-Baseline

| Feld | Wert |
|---|---|
| Workspace | `mays-orders-rc4-test` |
| State-Key | `env:/mays-orders-rc4-test/terraform.tfstate` |
| State-Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| State-Serial | `4` |
| Managed Resources | 37 |
| Deployment-Version | `0.1.0` |
| Tabelle | `mays-orders-rc4-test` |
| GSI1/GSI2 | vorhanden |
| GSI3 | nicht vorhanden |
| PITR | ENABLED |
| Items | 0 |

---

## 5. AWS-Identität

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| Account | `240571105849` — VERIFIED |
| Region | `eu-central-1` |
| ARN | `arn:aws:iam::240571105849:user/Mayaws` |

AWS CLI und Terraform liefen mit `mayaws`; kein `default`-Fallback.

---

## 6. Workspace und State vor Plan

| Feld | Wert |
|---|---|
| Workspace | `mays-orders-rc4-test` |
| State-Key | `env:/mays-orders-rc4-test/terraform.tfstate` |
| Serial | `4` |
| Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| Managed Resources | 37 |
| Data Sources | 9 |
| `mo_version` | `0.1.0` |
| State-Fingerprint vor Plan | `684907f580df3c441d837827cddcf2a506538ea3d4b43e40e029e5002b2ced73` |

---

## 7. Backup-Evidence

| Feld | Wert |
|---|---|
| Backup-ARN | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092` |
| Status | **AVAILABLE** |
| PITR | **ENABLED** |
| Evidence-Pfad | `.mays-installer/runs/20261103-213125/order-backup-evidence.json` |
| Evidence-SHA-256 | `9475284f1ac165fed18722506508b360fc7d446c667b89bae5390fdba08a6ce1` |
| Evidence-Status | `overallStatus=VERIFIED` |
| Tabellen-ARN | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test` |
| State im Evidence | Serial 4, Lineage `45f61e6a…`, Fingerprint `684907f5…` |

Die Evidence wurde unverändert an den Plan gebunden
(`.mays-installer/runs/20261103-214710/plans/order-backup-evidence.json`).

---

## 8. Versionsbindung

| Feld | Wert |
|---|---|
| Quelle | `0.1.0` (State-Output `mo_version`, VERIFIED) |
| Ziel | `0.2.0` (`--deployment-version`) |
| Kompatibilität | **COMPATIBLE** (Evidenzmatrix) |
| Legacy | nein |
| `--accept-upgrade-review` | nicht verwendet |

---

## 9. Upgrade-CLI und Parameter

```bash
Mays-Order-AWS-installer \
  --profile mayaws --region eu-central-1 \
  --project-name mays-orders-rc4-test \
  --environment rc4-test \
  --deployment-version 0.2.0 \
  plan --remote --upgrade \
  --out .mays-installer/runs/20261103-upgrade-02/plans \
  --backup-evidence .mays-installer/runs/20261103-213125/order-backup-evidence.json \
  --var enable_cognito_backup=false \
  --var enable_cognito_backup_automation=false \
  --var seed_example_data=false \
  --var monitoring_enabled=true
```

Der Installer verwendete RC4-Code-Commit `2e09e72`, Workspace
`mays-orders-rc4-test` und die vorhandene State-Bindung.

---

## 10. Tatsächlicher Terraform-Plan

| Aktion | Anzahl |
|---|---:|
| CREATE | **2** |
| UPDATE | **7** |
| DELETE | **0** |
| REPLACE | **0** |
| READ | **1** |
| UNKNOWN | **0** |

Terraform-Zusammenfassung:

```text
Plan: 2 to add, 7 to change, 0 to destroy.
```

### Geplante Änderungen

| Adresse | Typ | Aktion |
|---|---|---|
| `module.dynamodb.aws_dynamodb_table.orders` | `aws_dynamodb_table` | update |
| `module.iam.aws_iam_role_policy.handler` | `aws_iam_role_policy` | update |
| `module.iam.aws_iam_role_policy.sqs[0]` | `aws_iam_role_policy` | update |
| `module.lambda.aws_lambda_function.handler` | `aws_lambda_function` | update |
| `module.sqs.aws_sqs_queue.orders` | `aws_sqs_queue` | update |
| `module.sqs.aws_sqs_queue.dlq` | `aws_sqs_queue` | create |
| `module.sqs_worker.aws_lambda_function.worker` | `aws_lambda_function` | update |
| `module.sqs_worker.aws_lambda_event_source_mapping.sqs_worker` | `aws_lambda_event_source_mapping` | update |
| `module.monitoring.aws_cloudwatch_metric_alarm.dlq_messages[0]` | `aws_cloudwatch_metric_alarm` | create |

DynamoDB-Änderung: `hash_key=pk`, `range_key=sk`, Tabellenname unverändert;
GSI3 wird additiv ergänzt (`gsi1`, `gsi2`, `gsi3`); **kein Replace**.
Keine DELETE/REPLACE-Aktion in `resource_changes`.

---

## 11. Drift und blockierende Gates

Terraform Refresh meldete **20 Drift-Ressourcen** (nur `update`). Darunter
geschützte Typen:

- `module.cloudtrail.aws_s3_bucket.trail` — Drift `policy`
- `module.cognito.aws_cognito_user_pool.users` — Drift
  `auto_verified_attributes`, `username_attributes`

Weitere Drift-Punkte (nicht abschließend als harmlos bewertet):
API-Defaults, CloudTrail-Event-Selector, IAM `inline_policy`,
Lambda `layers`, CloudWatch-Alarm-Actions/Tags, SQS-ESM-Felder.

P0C blockiert Drift an geschützten Typen:

```text
UPGRADE_BLOCKED_MIGRATION_REQUIRED:
Drift an geschuetzten Ressourcen:
module.cloudtrail.aws_s3_bucket.trail,
module.cognito.aws_cognito_user_pool.users
```

Readiness: **BLOCKED**; Classification: **CRITICAL** (durch geschützten Drift).
P0A selbst meldete keine DELETE/REPLACE-Findings.

Es wurde **kein automatischer Refresh-only-Apply, keine State-Reparatur und
keine Drift-Bereinigung** durchgeführt.

---

## 12. State nach Plan

| Feld | Wert |
|---|---|
| Serial | `4` (unverändert) |
| Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| Managed Resources | 37 |
| State-Fingerprint nach Plan | `cbb81ab41b43f0ffa12e275623c947656f59436341c85c7885cb31358f881989` |

Der Fingerprint weicht vom Backup-Evidence-Fingerprint (`684907f5…`) ab; die
Serial blieb gleich. **Die bestehende Backup-Gate-Implementierung prüft
Lineage/Serial, aber nicht den State-Fingerprint.** P0C würde einen
Fingerprint-Wechsel bei einem späteren Manifest/Apply erkennen; ein Manifest
wurde wegen der Readiness-Blockade nicht erzeugt.

---

## 13. Geschützte Ressourcen

| Typ | Befund |
|---|---|
| DynamoDB | Update, kein Replace, GSI3 additiv, pk/sk unverändert |
| S3 (CloudTrail) | **Drift blockiert** |
| Cognito | **Drift blockiert** |
| SQS | Update + DLQ-CREATE, kein Replace |
| IAM | Policy-Updates |
| API Gateway | Drift (update), aber kein geplanter DELETE |
| Lambda | Update (Code), kein Replace |
| CloudWatch | Updates + DLQ-Alarm-CREATE |

Keine RIS-Ressource im Plan.

---

## 14. Backup-Gate-Ergebnis

Die bestehende Gate-Funktion meldet:

```text
status   = VERIFIED
blocking = False
sha256   = 9475284f1ac165fed18722506508b360fc7d446c667b89bae5390fdba08a6ce1
backupArn= arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092
```

Damit sind SHA-256, Tabellenidentität, Account/Region, `AVAILABLE`, PITR und
State-Lineage/Serial geprüft. **Nicht geprüft:** State-Fingerprint (siehe §12).
Der Plan wurde durch P0C-Drift blockiert, nicht durch das Backup-Gate.

---

## 15. Plan-Artefakt

| Feld | Wert |
|---|---|
| Planpfad | `/tmp/opencode/rc4-upgrade-plan/.mays-installer/runs/20261103-214710/plans/mays-orders-rc4-test-rc4-test-0.2.0-H2-240571105849-deploy-0001.tfplan` |
| Plan-SHA-256 | `c266ed53f8f2753d076fd52725a8ab3f10fb15832e3cc8e74e08b97ae02aa43a` |
| Terraform | `1.16.1` |
| RC4-Commit | `2e09e72` |
| Workspace | `mays-orders-rc4-test` |
| Source/Target | `0.1.0` / `0.2.0` |
| Backup-Evidence-SHA | `9475284f1ac165fed18722506508b360fc7d446c667b89bae5390fdba08a6ce1` |
| Manifest | **nicht erzeugt** (Readiness BLOCKED) |

Planfile/JSON bleiben außerhalb von Git; keine Secrets im Bericht.

---

## 16. Tests

| Lauf | Ergebnis |
|---|---|
| Upgrade-/Backup-/Drift-/Protected-Tests (6 Module) | **225 PASS** |
| `terraform fmt -check` | PASS |
| `terraform validate` | PASS |

Keine AWS-Mutation durch Tests.

---

## 17. Kostenrisiken

- Der RC3-Teststack läuft bereits; RC4-Plan erzeugt keine Ressourcen.
- Zusätzliche RC4-Ressourcen im Plan: SQS-DLQ + CloudWatch-DLQ-Alarm; minimale
  laufende Kosten.
- CloudTrail-Zweitinstanz und CloudWatch bleiben bestehende Kostenpositionen.
- Kein Apply und kein Destroy; keine Kostenschätzung als Freigabe.

---

## 18. Offene Punkte

1. **P0C-Drift** an `aws_s3_bucket.trail` und `aws_cognito_user_pool.users`
   muss kontrolliert geklärt werden; keine automatische Reparatur.
2. **State-Fingerprint** weicht von der Backup-Evidence ab; Backup-Gate prüft
   ihn derzeit nicht. Vor einem Apply muss die Evidenz entweder erneuert oder
   die Gate-Lücke entschieden werden.
3. Kein Manifest, keine Apply-Freigabe.
4. RC4-Zielversion/Release-Tag-Zuordnung bleibt offen.
5. Kein Restore/Cutover.

---

## 19. Apply-Entscheidungsvorlage

**Nicht freigabefähig.** Erforderlich wären:

1. Kontrollierte Drift-Klärung (ohne automatisches Refresh-only-Apply).
2. Neue bzw. konsistente Backup-Evidenz mit passendem State-Fingerprint.
3. Neuer Plan nach Bereinigung und erneute Prüfung.
4. Separate Apply-Freigabe für exakt diesen neuen Plan-Hash.

**Status:**

```text
RC4 UPGRADE PLAN BLOCKED
```

Kein Apply, kein Destroy, kein Backup, kein Restore, kein Push/Merge. **STOP.**
