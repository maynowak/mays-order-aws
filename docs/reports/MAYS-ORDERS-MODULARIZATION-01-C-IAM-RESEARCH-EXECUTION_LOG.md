# MAYS-ORDERS-MODULARIZATION-01-C-IAM-RESEARCH — EXECUTION LOG

**Auftrag:** MAYS-ORDERS-MODULARIZATION-01-C (Subagent C, read-only)
**Nachtrag durch Orchestrator gemäß SUBAGENT-REPORT-PFLICHT (docs/AI_AUDITLOG.md)**

---

## Current Status

COMPLETE — Alle 7 Prüfpunkte abgearbeitet; IAM-Inventar beider Repos vollständig erhoben, alle Kopplungen (DynamoDB/SQS/Boundary) verifiziert. Read-only, keine Schreibzugriffe, keine AWS-Calls.

## Date/Time (UTC)

2026-10-18 09:34 UTC

## Git Branch + HEAD

- **MO** (`/home/dci-student/projects/Mays-Orders-AWS`): Branch `main`, HEAD `c0ac0f106e1fa38cb511f3b08f7dfcc671b27164` („feat: free module selection via --modules (B1) MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01")
- **RIS** (`/home/dci-student/projects/Mays-Recruiting-Intelligent-System`): Branch `main`, HEAD `a8462886e904a1cee92866410ded72b273d1e42d` („docs: add a scoped composite-lifecycle TODO with evidence states")

## Scope

Read-only-Erhebung des vollständigen IAM-Rollen-/Policy-Inventars und aller DynamoDB-/SQS-/Boundary-Kopplungen in beiden Repos als Grundlage für die geplante Modularisierung (SQS/Worker optional zum Order-Handler).

## Completed Sections

1. Rollen-Inventar beide Repos (MO: modules/iam, modules/sqs-worker, modules/cognito_backup_automation, ci/iam; RIS: modules/lambda, modules/orders_reader, modules/iam, modules/health_plane, modules/cloudtrail; modules/api hat KEINE IAM-Rolle)
2. Permissions Boundaries (grep beide Bäume; Handler-/RIS-Seite geprüft; Provisionierung der Boundary-Policy gesucht)
3. Pauschale DynamoDB-/SQS-Kopplungen (je Rolle/Policy kategorisiert: ARN-präzise vs. pauschal)
4. Least-Privilege-Doku (MO security/iam-design.md §1/§2.1; RIS-Doku-Grep) + Code-vs-Doku-Abweichungen
5. MO modules/iam/main.tf — 4 Statements exakt zitiert; sqs_queue_arn-Default; count/Gating geprüft
6. RIS orders_reader-Abhängigkeit von MO (nur ARNs, nicht Policy-Form)
7. Open Questions konsolidiert (Boundary-Provenance via git log -S + WEEK-04.md zurückverfolgt)

## Actual Findings

### 1. Rollen-Inventar

**MO (terraform/modules/ + ci/, alles per Terraform):**

1. **`aws_iam_role.handler` + `aws_iam_role_policy.handler`** — `terraform/modules/iam/main.tf:66-77`; Name `${project_name}-handler-role`; Principal `lambda.amazonaws.com` (Z.10-13); Zweck: Order-Handler-Lambda (DDB + SQS-Send + Logs). KEINE Boundary.
2. **`aws_iam_role.worker` + `aws_iam_role_policy.worker`** — `terraform/modules/sqs-worker/iam.tf:50-62`; Name `${project_name}-sqs-worker-role`; Principal `lambda.amazonaws.com` (Z.6-9); Zweck: SQS-Worker (DDB Get/Update, SQS Receive/Delete/GetQueueAttributes, Logs); **einzige Rolle im Repo mit `permissions_boundary` (Z.53)**.
3. **`aws_iam_role.backup_lambda`** + `aws_iam_policy.backup_policy` + Attachment — `terraform/modules/cognito_backup_automation/main.tf:16-65`; Name `${project_name}-cognito-backup-role`; Zweck: Cognito-User-Export nach S3. **cognito-idp-Aktionen auf `resources = ["*"]` (Z.40)** — pauschal (nur List*/AdminListGroupsForUser, aber unscoped).
4. **`aws_iam_role.scheduler_role`** + Policy + Attachment — gleiche Datei Z.117-138; Principal `scheduler.amazonaws.com`; Zweck: EventBridge-Scheduler → `lambda:InvokeFunction` NUR auf Backup-Lambda-ARN (Z.125-127) — ARN-präzise.
5. **CI/CD** (im Repo-Root `ci/`, NICHT unter terraform/): `aws_iam_role.pipeline` (`ci/iam/main.tf:94`, Principal `codepipeline.amazonaws.com`) + 1 Inline-Policy; `aws_iam_role.codebuild` (Z.189, Principal `codebuild.amazonaws.com`) + **7 Inline-Policies** (base/validate/plan/deploy/verify/destroy_plan/destroy). Deploy/Destroy-Stages: Action-Wildcards pro Service (`iam:*`, `dynamodb:*`, `sqs:*`, `s3:*` … Z.405-421/522-538), Resource namens-scoped `${project_name}-${environment}-*` (Z.422-427/539-544); plan/verify/destroy_plan Read-Aktionen auf `Resource = ["*"]` (Z.387/466/505).
6. SNS-Topic-Policy (keine Rolle): `cognito_backup_automation/main.tf:199-209`, Principal `cloudwatch.amazonaws.com`, nur SNS:Publish auf Topic-ARN.

**RIS (terraform/modules/):**

7. **`aws_iam_role.lambda_execution` (Agent)** + **10 Inline-Policies** — `modules/lambda/main.tf:7-24`; Name `${prefix}-agent`; ARN-präzise (DDB auf konkrete Tabellen-ARNs + `/index/*`; SQS nur auf `var.sqs_queue_arn` Z.162-164). KEINE Boundary.
8. **`aws_iam_role.reader` + `aws_iam_role_policy.reader_orders_table`** — `modules/orders_reader/main.tf:14-31/33-71`; eigene Order-Fassade auf fremde MO-Tabelle/Queue (gleicher Account), ARN-präzise.
9. **`aws_iam_role.lambda_role` + `aws_iam_role_policy.lambda_policy`** — `modules/iam/main.tf:46-63/65-111`; Health-Writer, per Root-Wiring an health_plane angebunden (`terraform/main.tf:80-88, 252`).
10. **`aws_iam_role.health_publisher`** + Policy + Attachment — `modules/health_plane/main.tf:83-131`; S3 objekt-präzise inkl. einzelner `public-status.json`-ARN.
11. CloudTrail-Bucket-Policy (keine Rolle): `modules/cloudtrail/main.tf:63-100`, Principal `cloudtrail.amazonaws.com`, ARN-präzise + SourceArn-Condition.
12. **RIS `modules/api` hat KEINE IAM-Rolle.**
13. **Dead Code in RIS `modules/iam/main.tf`:** drei `data "aws_iam_policy_document"` (Z.3-18 lambda_dynamodb, Z.20-30 lambda_sqs **mit `resources = ["*"]` Z.28**, Z.32-44 lambda_s3) werden von keiner Ressource referenziert — die Role-Policy nutzt inline `jsonencode` (Z.72-110). Kein Live-Grant, aber Verwirrungs-/Drift-Risiko.

### 2. Permissions Boundaries

- **Genau EIN `permissions_boundary` im gesamten MO-Repo:** `modules/sqs-worker/iam.tf:53` → `var.lambda_execution_boundary`, Default-ARN `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary` (`modules/sqs-worker/variables.tf:32-36`, hartcodierte Account-ID).
- **(a) Handler-Rolle: KEINE Boundary** (`modules/iam/main.tf:66-71`).
- **(b) KEINE andere Rolle in MO** (backup_lambda, scheduler, ci) **und KEINE einzige Rolle in RIS** hat eine Boundary (grep über RIS-*.tf: 0 Treffer; RIS-Doku: „Hardening (Boundaries) SPÄTER", `docs/reports/RIS-FOUNDATION-INSTALLER-INTEGRATION-04-EXECUTION_LOG.md:17`).
- **(c) Boundary-Policy wird NICHT im Repo provisioniert** — kein `aws_iam_policy`-Objekt; einzige Code-Referenz ist der Variablen-Default. **Provenance (verifiziert):** Incident-Doku `docs/reports/WEEK-04.md:43-45,53` (falsche Account-ID `20571105849` → korrigiert `240571105849`, Commit `6a34a02`, per `git log -S` identifiziert), ferner `docs/reports/00-AI_AUDITLOG-MIGRATED-EXECUTION_LOG.md:672-714` und `docs/release/RELEASE-v0.4.0.md:104-115`. Policy existiert manuell/extern im Account; kein IaC, kein Design-Dokument.

### 3. Pauschale DynamoDB-/SQS-Kopplungen

**ARN-präzise (gut):** MO Handler (DDB table+GSI-ARNs Z.28-30/39-42; SQS SendMessage auf Queue-ARN Z.51) · MO Worker (Tabellen-/Queue-ARN Z.21/32) · RIS Agent (alle DDB-Policies auf konkrete Tabellen-ARNs + `/index/*`; SQS nur auf Queue-ARN) · RIS orders_reader (DDB auf `orders_table_arn` + `index/*`; SQS SendMessage auf Queue-ARN) · RIS health_publisher (objekt-präzise).

**Pauschal (schlecht):**
- **MO Queue-Policy, exaktes Zitat** (`terraform/modules/sqs/main.tf:26-41`): Z.33 `Sid = "AllowAccessFromAccount"`, Z.34 `Effect = "Allow"`, **Z.35 `Principal = "*"`**, Z.36 `Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]`, Z.37 `Resource = aws_sqs_queue.orders.arn` — **keine Condition**: jede authentifizierte IAM-Identität in JEDEM AWS-Account darf senden/empfangen/löschen. Der Sid-Name suggeriert Account-Scoping, das der Policy fehlt. Zudem: **keine DLQ/Redrive im MO-SQS-Modul** (Retention 120 s, Visibility 30 s — Z.20-21).
- MO backup_lambda: `cognito-idp:*`-Listaktionen auf `resources = ["*"]` (Z.40).
- RIS: Logs-Wildcards `arn:aws:logs:*:*:*` (Agent Z.370, reader Z.67, iam-Modul Z.82).
- MO ci deploy/destroy: Service-Action-Wildcards + Read-`Resource:"*"`.
- RIS modules/iam: SQS-Data-Doc mit `"*"` — ungenutzt/Dead Code (Finding 1.13).

### 4. Least-Privilege-Regeln dokumentiert

**MO `security/iam-design.md`:** §1 Z.9-13 („Least Privilege ist verpflichtend … kein `*` auf Ressourcen, wo ein konkreter ARN möglich ist") · §2.1 Z.30-42 (Konzept-Policy NUR Put/Get/Update/Query auf table+gsi1) · **§2.1 Z.67-68: „Bewusst NICHT erlaubt: `dynamodb:Scan`, `dynamodb:DeleteItem`, `dynamodb:BatchWriteItem`, `dynamodb:CreateTable`, `s3:*`, `sqs:*`, `iam:*`."**

**Code-vs-Doku-Abweichungen (MO, aktuell):** `modules/iam/main.tf:25` erlaubt **`dynamodb:DeleteItem`**; `:49` erlaubt **`sqs:SendMessage`**; `:41` GSI2 (Konzept nur gsi1) — alles widerspricht §2.1. **Veraltete Kommentare:** `modules/iam/main.tf:3` und `terraform/main.tf:60` („keine s3/sqs/iam-Aktionen") — falsch, seit DeleteItem + SQS im Modul sind. `security/iam-design.md` §2.1 wurde nie um DeleteItem/GSI2/SQS erweitert.

**RIS:** kein dediziertes security/iam-Dokument; Regeln verstreut (README.md:38, docs/AI_CONTEXT.md:69, docs/reports/S2-16-IAM-DEPLOYMENT-GOVERNANCE.md:64, docs/architecture/SYSTEM-ARCHITECTURE.md:80 — letzteres führt MO-SQS-`*`-Policy + fehlende DLQ als bekanntes OPEN). Starke Inline-Begründungen im RIS-Code.

### 5. MO modules/iam/main.tf — die 4 Statements (exakt)

| Sid | Zeilen | Actions | Resources |
|---|---|---|---|
| `DynamoDBTable` | Z.19-31 | `dynamodb:PutItem`, `GetItem`, `UpdateItem`, `DeleteItem`, `Query` | `[var.dynamodb_table_arn]` |
| `DynamoDBGSI` | Z.33-43 | `dynamodb:Query` | `[var.dynamodb_gsi1_arn, var.dynamodb_gsi2_arn]` |
| `SQS` | Z.45-52 | `sqs:SendMessage` | `[var.sqs_queue_arn]` |
| `Logs` | Z.54-63 | `logs:CreateLogGroup`, `CreateLogStream`, `PutLogEvents` | `["*"]` (mit Verweis-Kommentar auf iam-design §2.1) |

- **`sqs_queue_arn` ist OPTIONAL: `default = ""`** (`modules/iam/variables.tf:27-31`); DDB-ARNs Pflicht (Z.12-25).
- **KEIN Statement hat `count`/Gating.** Bei leerem `sqs_queue_arn` entstünde `Resource: [""]` (ungültig). Praxis-Entschärfung: Root-Wiring setzt immer den Wert (`main.tf:69`) und der Builder erzwingt `sqs` als Pflicht-Dep von `iam` (`module_builder/catalog.py:29`).

### 6. RIS-Abhängigkeit von MO-IAM

Bestätigt: `reader_orders_table` = DDB `GetItem/Query/UpdateItem/PutItem` auf `var.orders_table_arn` + `/index/*` (Z.42-51); SQS `SendMessage` auf `var.orders_queue_arn` (Z.53-59, „Queue gehört fremdes Projekt; nur SendMessage"); Logs. **RIS hängt NUR an Table-/Queue-ARNs, NICHT an der Form der MO-Handler-Policy.** ARNs kommen als Root-Variablen fail-closed herein (`terraform/variables.tf:282-324`, Modul-Validierung `modules/orders_reader/variables.tf:45-83`); Composite-Installation injiziert MO-Outputs (`terraform/main.tf:145-159`). RIS SendMessage funktioniert identitätsseitig über die EIGENE Policy (Same-Account) — die MO-Queue-Policy `Principal = "*"` ist eine zusätzliche, viel weitere Öffnung, die RIS strukturell NICHT braucht (RIS-Doku führt sie als OPEN).

## Evidence / File References

**MO:** `terraform/modules/iam/main.tf` (Z.3, 19-63, 66-77) · `terraform/modules/iam/variables.tf` (Z.27-31) · `terraform/modules/sqs-worker/iam.tf` (Z.50-62) · `terraform/modules/sqs-worker/variables.tf` (Z.32-36) · `terraform/modules/sqs/main.tf` (Z.20-21, 26-41) · `terraform/modules/cognito_backup_automation/main.tf` (Z.16-65, 106-138, 199-209) · `terraform/main.tf` (Z.58-70, 180-202) · `ci/iam/main.tf` (Z.63-572) · `ci/pipeline/main.tf` (Z.66-73) · `security/iam-design.md` (Z.9-13, 30-42, 67-68) · `module_builder/catalog.py` (Z.29-31) · `docs/reports/WEEK-04.md` (Z.35-53) · `docs/reports/00-AI_AUDITLOG-MIGRATED-EXECUTION_LOG.md` (Z.672-714) · `docs/release/RELEASE-v0.4.0.md` (Z.104-115) · `docs/TERRAFORM_POLICY_GATE.md` (Z.24, 124)

**RIS:** `terraform/modules/lambda/main.tf` (Z.7-24, 26-374, 429-433) · `terraform/modules/orders_reader/main.tf` (Z.14-71, 73-97) · `terraform/modules/orders_reader/variables.tf` (Z.45-83) · `terraform/modules/iam/main.tf` (Z.3-44, 46-111) · `terraform/modules/health_plane/main.tf` (Z.35-42, 83-131) · `terraform/modules/cloudtrail/main.tf` (Z.63-100) · `terraform/modules/sqs/main.tf` (Z.3-73) · `terraform/main.tf` (Z.80-88, 145-159, 252) · `terraform/variables.tf` (Z.278-324) · `docs/architecture/SYSTEM-ARCHITECTURE.md` (Z.80) · `README.md` (Z.38) · `docs/reports/S2-16-IAM-DEPLOYMENT-GOVERNANCE.md` (Z.64) · `docs/reports/RIS-FOUNDATION-INSTALLER-INTEGRATION-04-EXECUTION_LOG.md` (Z.17)

## Classification

**ORANGE** — Inventar vollständig, Kopplungen verstanden; aber ein konkretes, unbehobenes Sicherheitsfinding (MO Queue-Policy `Principal = "*"` ohne Condition — accountübergreifendes Send/Receive/Delete auf der Orders-Queue) plus dokumentierte, unaufgelöste Punkte (externe Boundary ohne IaC/Design-Doc; Doku-Code-Drift in MO). Kein RED, weil das Finding dev-only, kurzlebig (Retention 120 s) und bei RIS als bekanntes OPEN dokumentiert ist; Lösungspfad existiert. **Bei Produktivnahme der Queue ohne Härtung → RED.**

## Checks Actually Executed

Nur Leseoperationen: `git log -1`, `git branch --show-current`, `git status --porcelain` (beide Repos), `git log -S "Mays-Orders-Lambda-Execution-Boundary"`, `git log --oneline -- terraform/modules/sqs-worker/iam.tf`, `date -u`; ripgrep über `*.tf`/`*.md` beider Repos; Datei-Lektüre. **Keine** Terraform-Commands, **keine** AWS-API-Calls, **keine** Schreibzugriffe.

## Git Status

Unverändert bestätigt — an beiden Repos durchgehend read-only gearbeitet. (MO: die Modifikation `docs/AI_AUDITLOG.md` existierte bereits bei Session-Beginn — Orchestrator-Arbeit, nicht von diesem Subagent.)

## Files Changed

**keine — read-only.**

## Open Questions

1. **(a) Externe Boundary-Policy:** Wo liegt die Definition (manuelle Konsole)? Ins Terraform überführen (z. B. bootstrap/)? Warum nur der Worker eine Boundary, der Handler nicht? Warum hartcodierter Account-ARN statt `data.aws_caller_identity`?
2. **(b) MO Queue-Policy `Principal = "*"`** (`modules/sqs/main.tf:35`): Einengung auf Account-ID bzw. konkrete Producer-Rollen-ARNs + `aws:SourceAccount`-Condition; gleichzeitig fehlt eine DLQ im MO-SQS-Modul. **Freigabepflichtig — RIS-Live-Pfad!**
3. **(c) Veraltete Kommentar-/Doku-Zeilen in MO** (iam/main.tf:3, main.tf:60, security/iam-design.md §2.1): Doku nachziehen ODER Code zurückstufen — fachliche Klärung (ist DeleteItem im Handler beabsichtigt? Ja: Erasure-Funktion — aber Doku muss es benennen).
4. **Modularisierungsrelevant:** iam-Modul braucht ein Statement-Gating für „SQS optional"; Builder-Deps `iam: [dynamodb, sqs]` lockern.
5. RIS `modules/iam/main.tf:20-30`: ungenutzte SQS-Data-Policy mit `"*"` — entfernen? (RIS-seitig, separater Task.)
6. MO `ci/iam`: Action-Wildcards deploy/destroy — bewusstes Staging oder Härtungs-Kandidat?
7. Boundary-Standard für beide Repos definieren (warum trägt keine RIS-Rolle eine?).

## Risks

- **Queue-Policy `Principal="*"`:** Fremde Accounts können Messages einschleusen (Poisoning der Worker-Status-Updates), abrufen (zwar nur Order-Status-Payloads) oder löschen. Dev-Materialisierung gering (Retention 120 s), strukturell unsauber, bei Prod-Erhöhung kritisch.
- **Doku-Code-Drift MO:** Wer iam-design.md §2.1 als Fachquelle liest, bekommt ein falsches Sicherheitsmodell; Audit-Referenzen laufen auf die Doku.
- **Externe Boundary ohne IaC:** Worker-Rolle an ein Objekt außerhalb der Versionskontrolle gebunden — Boundary-Drift bricht künftige Worker-Deploys still; hartcodierter Account-Default bricht Multicontext.
- **Fehlendes SQS-Gating im iam-Modul:** Jede künftige Auswahl ohne SQS erzeugt Abbruch (Builder-Deps) oder ungültige Policy (leerer ARN) — Risiko exakt am geplanten Modularisierungs-Hebel.
- **RIS Dead-Code-Policy mit `"*"`:** Kopier-Risiko.

## Recommended Next Actions

1. MO Queue-Policy härtten (Account/Role-ARNs + SourceAccount-Condition; DLQ ergänzen) — **Mensch-Freigabe nötig, AWS-Mutation**.
2. Boundary-Policy in Terraform provisionieren oder Design-Doc anlegen; Default auf `data.aws_caller_identity` umstellen; Handler-Boundary entscheiden.
3. Doku-Sync MO (iam-design §2.1, Modul-Kommentare) an den Code-Stand — oder fachlich zurückstufen.
4. Modularisierung: SQS-Statement im iam-Modul count-gaten (`var.sqs_queue_arn != ""`); Builder-Deps lockern (`iam: [dynamodb]`, sqs optional); Worker bleibt self-contained.
5. RIS-Dead-Code separat entfernen (nicht Teil der Modularisierung).
6. Report gemäß SUBAGENT-REPORT-PFLICHT nachgetragen (dieses Dokument) + AI_AUDITLOG-Index.

## Current Resume Point

Research-Auftrag C abgeschlossen (alle 7 Prüfpunkte, **ORANGE**). Nächster Schritt beim Orchestrator: Phase 2 der Modularisierung (SQS-optional-Implementierung) — Queue-Policy-Härtung und Boundary-IaC sind SEPARAT freizugebende Punkte (RIS-Live-Pfad / AWS-Mutation) und KEIN Teil der Builder-Modularisierung.
