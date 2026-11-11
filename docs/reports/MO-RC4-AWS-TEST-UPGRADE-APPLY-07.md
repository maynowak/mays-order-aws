# MO-RC4-AWS-TEST-UPGRADE-APPLY-07

**Kontrollierter RC4-Test-Apply auf `mays-orders-rc4-test`**

**Datum:** 2026-11-11
**Plan-Code:** `00125ee` (isolierter Apply-Worktree)
**Report-Branch:** `test/mo-rc4-aws-test-upgrade-replan-06` @ `51114f0`
**Ergebnis:** Apply erfolgreich, Infrastruktur verifiziert; **Live-Funktionstests PENDING**

```text
RC4 TEST UPGRADE APPLIED — FUNCTIONAL VERIFICATION PENDING
```

---

## 1. Operator-Freigabe

`MO-RC4-AWS-TEST-UPGRADE-APPLY-07` wurde ausdrücklich für genau einen Apply
des Plans `7eec0a6e…` auf `mays-orders-rc4-test` freigegeben. P1
`REVIEW_REQUIRED` wurde mit den dokumentierten Nachkontrollen akzeptiert.
Kein Produktions-, RIS- oder anderer Workspace-Eingriff.

---

## 2. Git-/Code-Baseline

| Feld | Wert |
|---|---|
| Report-Branch | `test/mo-rc4-aws-test-upgrade-replan-06` |
| Report-HEAD | `51114f0` |
| Plan-/Apply-Code | `00125ee3ed14ee564549f6f92c338619fb1406dc` |
| Apply-Worktree | `/tmp/opencode/rc4-apply-00125ee` (detached `00125ee`) |
| Parser-Fix | enthalten |
| Backup-ARN-Gate | enthalten |
| Fingerprint-Vertrag | enthalten |
| `--accept-upgrade-review` | verwendet |

Der Apply-Worktree blieb unverändert; der Plan wurde nicht neu erzeugt.

---

## 3. AWS-Identität

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| Account | `240571105849` — VERIFIED |
| Region | `eu-central-1` |
| ARN | `arn:aws:iam::240571105849:user/Mayaws` |

Kein Fallback auf ein anderes Profil.

---

## 4. Plan und Manifest

| Feld | Wert |
|---|---|
| Plan-SHA-256 | `7eec0a6e1869c31dfe23a1b2ee8762b4363b1f6135705f3e34dc5b9440de409b` |
| Manifest-SHA-256 | `029ff9351d33dd9ca054ba91d943787e7ec115c9d3721430e20d609d1c57bdd5` |
| Planaktionen | 2 CREATE, 7 UPDATE, 0 DELETE, 0 REPLACE, 1 READ |
| Deployment-ID | `240571105849:mays-orders-rc4-test:rc4-test` |
| Source/Target | `0.1.0` / `0.2.0` |

Plan und Manifest wurden vor und nach dem Apply nicht verändert.

---

## 5. State-Baseline

### Vor Apply

| Feld | Wert |
|---|---|
| Serial | `4` |
| Lineage | `45f61e6a-a0a4-d9ce-1427-8c9a3fad6cad` |
| Managed Resources | 37 |
| Fingerprint | `670bc917fe4671df2ecb7b317068160c8fc452e02e87aa7a63b3b63e864f2a4a` |

### Nach Apply

| Feld | Wert |
|---|---|
| Serial | **`8`** |
| Lineage | unverändert |
| Managed Resources | **39** (37 + DLQ + Alarm) |
| Fingerprint | `e5d830d508a9d41cd053ca386030c1b94a30eb2aaa73053f97c4e528a34a7453` |
| `mo_version` | **`0.2.0`** |

---

## 6. Backup-Prüfung

| Feld | Wert |
|---|---|
| Backup-ARN | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test/backup/01793737895744-2f886092` |
| Status | **AVAILABLE** |
| PITR | **ENABLED** |
| Evidence-SHA-256 | `4e2129ffb3828a7a6555a7107bacc6874a4a6936d6432f13557474a8770fad94` |
| Gate | **VERIFIED** |

Kein neues Backup erstellt.

---

## 7. Gates

| Gate | Ergebnis |
|---|---|
| P0A | **PASS** — 0 DELETE / 0 REPLACE |
| P0C | **PASS** — benigne Normalisierung; keine kritische Drift |
| P1 | **REVIEW_REQUIRED**, ausdrücklich akzeptiert |
| P3A | **VERIFIED** |
| PlanMetadata | **PASS** — `240571105849:mays-orders-rc4-test:rc4-test` |
| Minor-Matrix | **COMPATIBLE** |

---

## 8. Apply

```bash
ALLOW_AWS_OPERATIONS=true \
Mays-Order-AWS-installer \
  --profile mayaws --region eu-central-1 \
  --project-name mays-orders-rc4-test --environment rc4-test \
  --deployment-version 0.2.0 --accept-upgrade-review \
  deploy --plan <approved plan> --yes
```

Ergebnis:

```text
Plan: 2 to add, 7 to change, 0 to destroy, 0 to replace
Policy gate PASSED
Applying plan...
Deployment successful!
Deployment completed successfully!
```

Apply-Log: `/tmp/opencode/rc4-apply-07.log`  
Log-SHA-256: `e377499ec0de21f4d6166627b77ef930992685dcf007b398182c3f52789f166b`

Keine Wiederholung, keine Reparatur, kein Rollback.

---

## 9. Infrastruktur nach Apply

### DynamoDB

| Prüfung | Ergebnis |
|---|---|
| Tabelle | `mays-orders-rc4-test` |
| Status | ACTIVE |
| Key | `pk` (HASH), `sk` (RANGE) — unverändert |
| GSI1/GSI2 | ACTIVE |
| GSI3 | **ACTIVE**, `KEYS_ONLY` |
| PITR | ENABLED |
| Items | 0 (keine Daten geschrieben) |

### Lambda

| Funktion | Status | CodeSha |
|---|---|---|
| `mays-orders-rc4-test-handler` | Active | `vW8nlTjAd9b+F3jYp+1nsKZ2AxRBYDBCneXhSmnc0yM=` |
| `mays-orders-rc4-test-sqs-worker` | Active | dito |

### SQS / DLQ

| Prüfung | Ergebnis |
|---|---|
| Queue | `mays-orders-rc4-test-orders-queue` |
| DLQ | `mays-orders-rc4-test-orders-queue-dlq` |
| Retention | 345600 s |
| Visibility | 60 s |
| Redrive | ausschließlich auf die Test-DLQ, `maxReceiveCount=1` |

### IAM

Handler-Policy enthält GSI1/GSI2/GSI3-Query und die bisherigen Rechte.
SQS-Policy enthält **ausschließlich** `sqs:SendMessage` auf
`arn:aws:sqs:eu-central-1:240571105849:mays-orders-rc4-test-orders-queue`.
Keine Wildcards, keine unerwarteten Aktionen.

### Event-Source-Mapping / CloudWatch

- ESM: `mays-orders-rc4-test-orders-queue`, BatchSize 5,
  `ReportBatchItemFailures` aktiv.
- CloudWatch: 7 Alarme, darunter `mays-orders-rc4-test-dlq-messages` (OK).
- Log-Groups Handler/Worker vorhanden.

### Protected Resources

- Cognito-Pool `mays-orders-rc4-test-users` unverändert; keine Domain.
- CloudTrail `mays-orders-rc4-test-trail` unverändert; `ris-dev-trail` unverändert.
- Keine RIS-Ressource im Apply/State.

---

## 10. Funktionstests

Lokale Regression nach Apply:

| Lauf | Ergebnis |
|---|---|
| Installer | **621 PASS** |
| Builder | **128 PASS** |
| Lambda | **326 PASS** |
| Terraform fmt/validate | PASS |

Live-Smoke-/Integrationstests wurden **nicht** ausgeführt: Sie würden
Authentifizierung, synthetische Order-Schreibvorgänge und/oder
Queue-Nachrichten erfordern, die nicht durch einen separat dokumentierten
Testvertrag in diesem Auftrag freigegeben waren. Es wurden keine zusätzlichen
AWS-Mutationen ausgelöst.

Damit ist die **Funktionsverifikation PENDING**, nicht VERIFIED.

---

## 11. Offene Punkte / Risiken

| ID | Punkt | Status |
|---|---|---|
| F-01 | Live-RC4-Funktionstest (Handler/Worker/GSI3/DLQ) | **PENDING** |
| R-01 | Manifest/Evidence unsigniert | bestehende Grenze |
| R-02 | CloudTrail-Zweitinstanz läuft weiter | Kosten/Log-Duplikate |
| R-03 | Testtabelle leer | keine Datenmigrationsaussage |
| R-04 | `REVIEW_REQUIRED` bleibt dokumentiert | Apply erfolgte mit Freigabe |

---

## 12. Nächster Schritt

Separater Funktionstest-Auftrag für den isolierten Teststack mit explizit
freigegebenen synthetischen Testdaten. Kein Produktionssystem, keine RIS.

Bericht: `docs/reports/MO-RC4-AWS-TEST-UPGRADE-APPLY-07.md`

**Apply abgeschlossen; keine weiteren Terraform-Operationen, kein Push/Merge. STOP.**
