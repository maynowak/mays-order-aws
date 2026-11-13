# MO-RC4-AWS-TEST-UPGRADE-REPLAN-06

**Neuer RC4-Testupgrade-Plan mit korrigiertem PlanMetadata-Parser**

**Datum:** 2026-11-11
**Branch:** `test/mo-rc4-aws-test-upgrade-replan-06` (ab `00125ee`)
**Modus:** Read-only AWS + Terraform-Plan; **kein Apply, kein Destroy, kein Backup,
kein State-Write, kein Push/Merge.**

---

## 1. Git-Ausgangslage

| Feld | Wert |
|---|---|
| Ausgangsbranch | `fix/mo-rc4-plan-metadata-parser-fix-05` |
| Ausgangs-HEAD | `00125ee` |
| Arbeitsbranch | `test/mo-rc4-aws-test-upgrade-replan-06` |
| Working Tree vor Plan | CLEAN |
| Plan-Code-Commit | `00125ee3ed14ee564549f6f92c338619fb1406dc` |
| Git-Tree | `6dfd06e94e15986e07bfc6b908970e549afd120b` |
| Terraform-Tree | `9ebbf0722cdc1b05c1f772929dbc7fe6c4641834` |

---

## 2. RC4-Code-Baseline

Enthalten:

- Parser-Fix `00125ee` (hyphenierte Deployment-IDs)
- Backup-ARN-Gate `d4ecef7`
- Kanonischer Fingerprint `canonical-sha256-v1` (`bd40a3d`)
- P3A-Evidence-Revalidierung (`b9ac02a`)
- RC4-Manifest-/Readiness-Vertrag
- Source-Commit-Bindung im Manifest

---

## 3. Parser-Fix-Nachweis

Der neue Plan-Dateiname

```text
mays-orders-rc4-test-rc4-test-0.2.0-H2-240571105849-deploy-0002.tfplan
```

wird mit dem erwarteten Kontext korrekt aufgelöst:

```text
240571105849:mays-orders-rc4-test:rc4-test
```

`PlanDiscovery.validate_plan_context` → `(True, "")`.

---

## 4. Source-Commit-Bindung

Der Plan ist an Code-Commit `00125ee…` gebunden. Spätere reine Berichts-/Audit-
Commits ändern diese Bindung nicht. Für einen späteren Apply ist ein isolierter
Worktree exakt auf `00125ee` zu verwenden; keine Codeänderung dort.

---

## 5. AWS-Identität

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| Account | `240571105849` — VERIFIED |
| Region | `eu-central-1` |
| ARN | `arn:aws:iam::240571105849:user/Mayaws` |
| Zeitstempel | `2026-11-11T14:13:28Z` |

---

## 6. Terraform-State

| Feld | Wert |
|---|---|
| Workspace | `mays-orders-rc4-test` |
| State-Key | `env:/mays-orders-rc4-test/terraform.tfstate` |
| Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| Serial | `4` |
| Managed Resources | 37 |
| `mo_version` | `0.1.0` |
| Fingerprint | `670bc917fe4671df2ecb7b317068160c8fc452e02e87aa7a63b3b63e864f2a4a` |
| Fingerprint-Version | `canonical-sha256-v1` |

### DynamoDB-Baseline

`mays-orders-rc4-test`, ACTIVE, GSI1/GSI2 vorhanden, **kein GSI3**, 0 Items,
PITR ENABLED.

---

## 7. Backup-Bindung

| Feld | Wert |
|---|---|
| Backup-ARN | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092` |
| AWS-Status | **AVAILABLE** |
| PITR | **ENABLED** |
| Evidence | `docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01/order-backup-evidence.json` |
| Evidence-SHA-256 | `4e2129ffb3828a7a6555a7107bacc6874a4a6936d6432f13557474a8770fad94` |
| evidenceKind | `EXISTING_BACKUP_REVALIDATION` |
| Gate | **VERIFIED** |

Keine neue Backup-Erstellung; Evidence unverändert.

---

## 8. Lokale Regression

| Lauf | Ergebnis |
|---|---|
| Installer gesamt | **621 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| Parser-/Discovery-/Sequenz-Tests | PASS |
| PlanIntegrity / Backup-ARN-Gate / Fingerprint | PASS |
| `compileall installer` | PASS |
| `terraform fmt -check` | PASS |
| `terraform validate` | PASS |

Keine AWS-Mutation.

---

## 9. Neuer Terraform-Plan

Ausgeführt mit dem vorhandenen RC4-Installer:

```bash
plan --remote --upgrade \
  --out .mays-installer/runs/20261111-replan-06/plans \
  --backup-evidence docs/reports/MO-RC4-P3A-EVIDENCE-REBIND-01/order-backup-evidence.json \
  --backup-arn arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092 \
  --var enable_cognito_backup=false \
  --var enable_cognito_backup_automation=false \
  --var seed_example_data=false \
  --var monitoring_enabled=true
```

Ergebnis: Plan erfolgreich, Readiness `REVIEW_REQUIRED`.

---

## 10. Vollständige Planänderungen

| Aktion | Anzahl |
|---|---:|
| CREATE | **2** |
| UPDATE | **7** |
| DELETE | **0** |
| REPLACE | **0** |
| READ | **1** |
| UNKNOWN | **0** |

- CREATE: `module.sqs.aws_sqs_queue.dlq`,
  `module.monitoring.aws_cloudwatch_metric_alarm.dlq_messages[0]`
- UPDATE: DynamoDB-Tabelle, IAM Handler-Policy, IAM SQS-Policy,
  Lambda Handler, SQS Queue, SQS Event-Source-Mapping, Lambda Worker
- DynamoDB: `pk`/`sk` unverändert; GSI1/GSI2 bleiben; GSI3 additiv
- Keine DELETE-/REPLACE-Aktion

---

## 11. P0A / P0C / P1 / P3A

| Gate | Ergebnis |
|---|---|
| P0A Protected Resources | **PASS** — DELETE=0, REPLACE=0 |
| P0C Drift | **PASS (REVIEW)** — 20 Drift-Einträge; S3/Cognito benigne, keine kritische Drift |
| P1 Upgrade-Readiness | **REVIEW_REQUIRED** — keine Blockade, Classification REVIEW |
| P3A Backup-Gate | **VERIFIED** — ARN, Evidence, Fingerprint/Version |
| Minor-Matrix | **COMPATIBLE** `0.1.0 → 0.2.0` |

`REVIEW_REQUIRED` bleibt bestehen und wird nicht zu PASS umklassifiziert.

---

## 12. Deployment-ID-Validierung

```text
240571105849:mays-orders-rc4-test:rc4-test
```

Der neue Dateiname wird durch den korrigierten Parser ohne Umgehung korrekt
zugeordnet; `PlanDiscovery.validate_plan_context` liefert `True`.

---

## 13. Plan- und Manifest-SHA-256

| Feld | Wert |
|---|---|
| Planpfad | `/tmp/opencode/rc4-upgrade-plan/.mays-installer/runs/20261111-151439/plans/mays-orders-rc4-test-rc4-test-0.2.0-H2-240571105849-deploy-0002.tfplan` |
| Plan-SHA-256 | `7eec0a6e1869c31dfe23a1b2ee8762b4363b1f6135705f3e34dc5b9440de409b` |
| Manifest | `.../mays-orders-rc4-test-rc4-test-0.2.0-H2-240571105849-deploy-0002.tfplan.manifest.json` |
| Manifest-SHA-256 | `029ff9351d33dd9ca054ba91d943787e7ec115c9d3721430e20d609d1c57bdd5` |
| Deployment-ID | `240571105849:mays-orders-rc4-test:rc4-test` |
| Plan-Code | `00125ee` |
| Source/Target | `0.1.0` / `0.2.0` |
| Backup-Evidence-SHA | `4e2129ff…` |
| State-Fingerprint | `670bc917…` |

Plan und Manifest liegen außerhalb von Git (`.mays-installer/`) und wurden nach
der Hashbildung nicht verändert.

---

## 14. Offene Review-Punkte

1. `REVIEW_REQUIRED` der sieben geplanten Updates bleibt bestehen.
2. IAM-SQS-Policy und SQS-Redrive-Policy sind im Plan teilweise `after_unknown`;
   post-apply verifizieren (nur `sqs:SendMessage` auf Test-Queue; Redrive nur
   Test-DLQ).
3. Manifest/Evidence sind nicht signiert (bestehende Vertrauensgrenze).

---

## 15. Risiken

| ID | Risiko | Bewertung |
|---|---|---|
| R-01 | Review der geplanten Updates erforderlich | Apply nur mit Review-Freigabe |
| R-02 | Unknown IAM/SQS-Werte bis Apply | post-apply Pflichtprüfungen |
| R-03 | Kein Apply/keine Funktionstests in diesem Auftrag | bewusst |
| R-04 | CloudTrail-Zweitinstanz läuft weiter | Kosten/Log-Duplikate |
| R-05 | Testtabelle leer | keine Datenmigrationsaussage |

---

## 16. Voraussetzungen für den späteren Test-Apply

1. Isolierten Worktree exakt auf Code-Commit `00125ee` auschecken.
2. Plan-SHA `7eec0a6e…` und Manifest-SHA `029ff935…` prüfen.
3. Pre-Op erneut durchführen (State/Backup/Readiness).
4. Apply nur mit `--accept-upgrade-review` und separater GO-Freigabe.
5. Keine Neuplanung, kein Destroy, keine Codeänderung im Apply-Worktree.
6. Nach Apply: GSI3, Lambda, SQS/DLQ, IAM, CloudWatch, `mo_version=0.2.0`.

**Status:**

```text
RC4 AWS TEST REPLAN VERIFIED — APPLY APPROVAL REQUIRED
```

Kein Apply, kein Backup, keine AWS-Mutation, kein Push/Merge. **STOP.**
