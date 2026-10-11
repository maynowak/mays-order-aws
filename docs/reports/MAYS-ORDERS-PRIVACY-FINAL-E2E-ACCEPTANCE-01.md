# MAYS-ORDERS-PRIVACY-FINAL-E2E-ACCEPTANCE-01

Baseline `5e56938`, HEAD siehe Commit. Account `240571105849`, Region
`eu-central-1`, Profil `mayaws`. Zeit: 2026-10-11 ~12:10–12:20 UTC.
Artefakt: `lambda.zip` mit Runtime-Fix (deployed, CodeSha256 geändert).

## Phase 1 — Baseline (alle PASS)
- Remote main / HEAD `5e56938` verifiziert; nur präexistente uncommittete
  Terraform-Artefakte + Reports unberührt daneben.
- Identität: `240571105849` / `Mayaws`, konform mit STS.
- Workspace/State: `mays-orders-privacy-test`, 37 verwaltete Ressourcen.
- ZIP-Integrität: Installer-Check `lambda_artifact current (7 modules)`.
- Deployed Lambda vor Fix-Rollout: `LastModified 09:31`, danach neues
  CodeSha256 (Phase 2).

## Phase 2 — Deployment (PASS)
- Frischer Plan `deploy-0008`: 35 no-op + **2 updates**
  (`module.lambda.handler`, `module.sqs_worker.worker` = Fix-Rollout),
  0 creates/deletes/replaces, 0 cross-project. Policy Gate PASSED.
- Kontrolliertes `deploy --yes` (nur Testprojekt): successful, Post-Verify OK.

## Phase 3 — AWS E2E (synthetisch, User danach gelöscht)
| ID | Funktion | Erwartet | Ergebnis | Status |
|----|----------|----------|----------|--------|
| A-01 | Cognito-Login (admin-create, USER_PASSWORD_AUTH) | IdToken | erhalten | PASS |
| A-02 | Unauthentifiziert | 401 | 401 | PASS |
| A-03 | POST /orders | 201, serverseitiger Betrag | 201, totalAmount 1998 | PASS |
| A-04 | GET /orders/{id} | 200, Decimal als Zahl | 200, `1998.0` | PASS |
| A-05 | GET /orders | 200 + Liste | 200, count 1 | PASS |
| A-06 | Worker-Transition | PENDING→CONFIRMED async | nach 8 s CONFIRMED, Queue leer | PASS |
| A-07 | PATCH → PROCESSING | 200 | 200 | PASS |
| A-08 | PATCH ungültig → PENDING | 409 INVALID_TRANSITION | 409 | PASS |
| A-09 | Pagination limit=2 bei 4 Orders | nextToken | count 2 + Token | PASS |
| A-10 | GSI1/GSI2 | ACTIVE | beide ACTIVE | PASS |
| A-11 | IAM | Handler operiert | Put/Query/Update belegt | PASS |
| A-12 | CloudWatch-Logs | Handler + Worker | beide schreiben | PASS |

## Phase 4 — Privacy
| ID | Funktion | Status | Evidence |
|----|----------|--------|----------|
| P-01 | inspect_subject live | BLOCKED | `status`-Alias-Fix deployed (gleiche ZIP wie A-04-Nachweis), aber `_require_privacy_auth` braucht `PRIVACY_INTERNAL_SECRET`, das in `modules/lambda/main.tf` nicht provisioniert ist. Secret **nicht** improvisiert (Regel). Unit-Test: COMPLETED + Alias-Assert GREEN. Freigabe zur Secret-Provisionierung erforderlich. |
| P-02 | export_subject live | BLOCKED | wie P-01 (Unit GREEN). |
| P-03 | erase_subject live | BLOCKED | wie P-01 (Pfad zuvor auf echter Tabelle VERIFIED: echte Löschung). |
| P-04 | Tenant-Isolation/Auth-Negativ | VERIFIED (Vorlauf) | disjunkte Subjects, fail-closed Pfade auf echter Tabelle belegt. |

## Phase 5/6 — Cleanup-Vorbereitung (KEIN DESTROY)
- 4 synthetische Orders gelöscht, Tabelle `Count=0` nachgewiesen; Test-User
  `e2e-accept` gelöscht; Token vernichtet. Keine Secrets/PII in Reports.
- Ressourcenbestand: 37 (State) im Testprojekt.
- Destroy-Plan `...-destroy-0001.tfplan` vorbereitet: **37 deletes**,
  Namensprüfung aller 19 benannten Ressourcen → 0 Fremdressourcen
  (ausschließlich `mays-orders-privacy-test-*`). **Nicht ausgeführt.**

## Abschluss: YELLOW
Offen einzig: P-01–P-03 live (Secret-Provisionierung + interner Aufrufweg,
Governance-Freigabe). Alles andere PASS. STOP vor Destroy wie beauftragt.
