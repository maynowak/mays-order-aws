# MAYS-ORDERS-MODULARIZATION-01-A-WORKER-IAM-RESEARCH — EXECUTION LOG

- **Current Status:** COMPLETED (read-only Research abgeschlossen)
- **Date/Time:** 2026-10-18 (UTC-Kontext; Research im Rahmen der Worker-/IAM-Modularisierung)
- **Git Branch + HEAD:** Mays-Orders-AWS, main `c0ac0f1` (Orchestrator-verifiziert)
- **Scope:** Worker-, IAM- und Lambda-Bausteine des Mays-Orders-Stacks technisch vermessen — exakte SQS-Kopplungen für die Modularisierung nachweisen. Keine Implementierung.
- **Mode:** READ-ONLY — keine Schreibzugriffe, keine AWS-Calls.

## Completed Sections

1. IAM-Modul-Policy-Struktur vollständig erfasst (main.tf, variables.tf, outputs.tf)
2. Lambda-Modul-Variablen inkl. `queue_url`-Default geprüft
3. SQS- und sqs-worker-Module inkl. Worker-IAM geprüft
4. Handler-Verhalten ohne SQS (index.py) verifiziert
5. Root-Wiring-Zeilen mit module.sqs-Referenzen lokalisiert
6. Permissions-Boundaries-Inventar
7. Least-Privilege-Regeln (security/iam-design.md) vs. Code abgeglichen
8. Testabdeckung Handler-Policy/Enqueue geprüft

## Actual Findings

1. **IAM-Modul:** `data "aws_iam_policy_document" "handler` mit GENAU 4 Statements → EINE `aws_iam_role_policy.handler` (modules/iam/main.tf Z.73–77):
   - `DynamoDBTable` (Z.19–31): PutItem, GetItem, UpdateItem, DeleteItem, Query → `var.dynamodb_table_arn`
   - `DynamoDBGSI` (Z.33–43): Query → gsi1+gsi2-ARN
   - `SQS` (Z.45–52): `sqs:SendMessage` → `var.sqs_queue_arn` — **unbedingt, kein count/Gating**
   - `Logs` (Z.54–63): CreateLogGroup/Stream/PutLogEvents → `["*"]`
2. **Variablen sind bereits optional:** `sqs_queue_arn` default `""` (modules/iam/variables.tf Z.27–31); `queue_url` default `""` (modules/lambda/variables.tf Z.57–61). Pflicht: nur die DynamoDB-ARNs. Die faktische Kopplung entsteht über Root-Wiring + Builder-Katalog.
3. **Handler ist vollständig graceful ohne SQS:** index.py Z.16 `SQS_QUEUE_URL = os.environ.get(...)`; Z.26–28 `_send_to_sqs`-Skip mit Log; Z.145–147 `if order_id and SQS_QUEUE_URL:` — Enqueue optional, Fehler bricht Request nie. **Aber: kein Test deckt Enqueue/Skip ab** (lambda/tests: 0 sqs-Treffer).
4. **Worker-Rolle self-contained:** modules/sqs-worker/iam.tf — eigene Rolle+Policy (DDB Get/Update Z.15–21; SQS Receive/Delete/GetQueueAttributes Z.24–33; Logs Z.35–44), `permissions_boundary = var.lambda_execution_boundary` (Z.53, Default-ARN eines EXTERNEN, nicht im Repo provisionierten Policy-Objekts), **keine Referenz auf module.iam**.
5. **Root-Wiring (terraform/main.tf):** Z.69 `sqs_queue_arn = module.sqs.queue_arn` (iam-Block), Z.84 `queue_url = module.sqs.queue_url` (lambda-Block), Z.186 queue_name, Z.195–196 sqs_worker-Inputs — hart verdrahtet; Builder übernimmt Blöcke verbatim.
6. **Builder-Katalog erzwingt sqs als Pflicht-Dep** von iam und lambda (module_builder/catalog.py Z.29–30; fail-closed-Tests test_module_builder.py Z.459–473).
7. **Permissions Boundaries:** nur sqs-worker (externer ARN); Handler-Rolle hat KEINE Boundary.
8. **Code-vs-Doku-Abweichungen:** iam/main.tf Z.3-Header + main.tf Z.60 behaupten „keine sqs-Aktionen" (falsch: Z.49 sqs:SendMessage); security/iam-design.md §2.1 (Z.67–68) verbietet DeleteItem/sqs:* — Code enthält beides (Erasure-/SQS-Erweiterung ohne Doku-Update). **Queue-Policy modules/sqs/main.tf Z.26–41: Principal `*`** (Z.35) — account-weit offen (bekanntes Security-Finding).
9. **Kein Test prüft die Handler-Policy** (installer-Test `test_iam_roles_separated` betrifft ci/iam CodeBuild/CodePipeline-Rollen).

## Evidence / File References

- `terraform/modules/iam/main.tf` Z.3, 19–31, 33–43, 45–52, 54–63, 66–77; `variables.tf` Z.12–31; `outputs.tf` Z.2–15
- `terraform/modules/lambda/variables.tf` Z.27–61; `terraform/modules/sqs/main.tf` Z.1–56 (Queue-Policy Z.26–41, Principal Z.35)
- `terraform/modules/sqs-worker/`: main.tf Z.3, 12, 27–32; iam.tf Z.1–66; variables.tf Z.12–36
- `lambda/src/index.py` Z.16, 26–28, 48–50, 145–147; `lambda/src/sqs_handler.py` Z.26–27, 33–96
- `terraform/main.tf` Z.60, 62–70 (Z.69), 78–89 (Z.84), 182–187, 191–202
- `module_builder/catalog.py` Z.29–31; `module_builder/tests/test_module_builder.py` Z.459–473
- `security/iam-design.md` §1 Z.9–13, §2.1 Z.32–40, 67–72, §3 Z.91–93

## Classification

**GREEN** — Inventar vollständig; die SQS-Kopplung ist dreifach hart (Wiring Z.69/84, ungegates Policy-Statement, Katalog-Dep), aber die Modul-Variablen sind bereits optional und der Handler-Code bereits graceful → Modularisierung mit minimalem Eingriff möglich.

## Checks Actually Executed

Nur Leseoperationen: file reads, grep, Brace-Matching-Scan von main.tf-Modulblöcken, Test-Verzeichnis-Scans. Kein terraform apply/plan, keine AWS-Calls.

## Git Status

Working tree des Repos zum Research-Zeitpunkt unverändert (Agent schreibt nichts; Bestätigung: keine Datei angefasst).

## Files Changed

**Keine — read-only.** (Bestätigt.)

## Open Questions

1. Queue-Policy Principal `*` — Einengung auf die beiden Rollen wäre Least-Privilege-konform, ist aber Verhaltensänderung am Bestand → separat freizugeben.
2. Externe Boundary-Policy `Mays-Orders-Lambda-Execution-Boundary` — im Repo nur als Default-ARN referenziert, nicht provisioniert; Provenance zu klären.
3. Header-/Doku-Abweichungen (iam/main.tf Z.3, main.tf Z.60, security/iam-design.md §2.1) — Nachdokumentation offen.
4. Fehlende Enqueue/Skip-Tests im Lambda-Suite — als Vertrags-Test für „lambda ohne sqs" sinnvoll.

## Risks

- Policy-Restrukturierung (SQS-Statement separieren) ändert den Policy-Inhalt bestehender `aws_iam_role_policy.handler` → bei künftigen MO-Pläns als In-Place-Update sichtbar (kein Live-Bestand von MO betroffen: privacy-test zerstört; RIS pinned alten MO-Stand).

## Recommended Next Actions

1. SQS-Statement des IAM-Moduls count-gated auslagern (zweite aws_iam_role_policy) — Module-Variablen behalten default "".
2. Lambda-Modul UNVERÄNDERT lassen (queue_url default "" genügt — Handler skippt).
3. Root main.tf UNBERÜHRT lassen; stattdessen Builder-seitiges Stripping der module.sqs-Zeilen bei Nichtauswahl + Katalog-Dep-Update (iam: [dynamodb], lambda: [dynamodb, iam]).
4. Enqueue/Skip-Regressionstests ergänzen; Doku-Abweichungen nachziehen.

## Current Resume Point

Research A abgeschlossen und in diesem Log nachgetragen; Implementierungs-Entscheidung (count-gated SQS-Policy + Builder-Stripping) dokumentiert — Umsetzung siehe MAYS-ORDERS-MODULARIZATION-01 (Phase 2).
