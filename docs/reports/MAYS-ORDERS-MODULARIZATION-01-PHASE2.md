# MAYS-ORDERS-MODULARIZATION-01-PHASE2

**Checkpoint:** MAYS-ORDERS-MODULARIZATION-01-PHASE2
**Datum:** 2026-10-18
**Baseline:** main `000cd41` (Research-Logs A/B/C)
**Scope:** IAM-/SQS-Kopplung modularisieren — SQS-Berechtigung optional, Builder-Deps lockern, Doku-Sync. Bestehende Implementierungen (Handler, Worker, RIS-Verträge) unangetastet.
**Status:** VERIFIED — 178/178 Installer+Builder, 76/76 Lambda, terraform fmt/validate PASS (Quelle + generierte Projekte), Git CLEAN

## 1. Research-Basis (Phase 1, siehe EXECUTION_LOGs A/B/C)

- **A (GREEN):** IAM-Policy = 4 Statements in EINER Policy; `sqs_queue_arn`/`queue_url` bereits optional (`default = ""`); Handler graceful ohne SQS (index.py Z.26-28, 145-147); Worker-Rolle self-contained.
- **B (GREEN):** RIS-Verträge = Statusmaschine, `ord_*`-Format, Schema, Queue-Nachrichtenform `{orderId, status, metadata}`, Naming `{project}-orders-queue`, offene Queue-Policy. **RIS hängt NICHT an der MO-Handler-Policy-Form.**
- **C (ORANGE):** Kein SQS-Gating im iam-Modul (Modularisierungs-Hebel); Queue-Policy `Principal = "*"` als Security-Finding (**bleibt OPEN, Härtung freigabepflichtig — RIS-Live-Pfad**); Boundary extern ohne IaC (OPEN); Doku-Drift (behoben in diesem Checkpoint).

## 2. WP1 — IAM-Modul: SQS-Berechtigung optional (Commit `5c70374`)

`terraform/modules/iam/main.tf`:
- Basis-Policy (`aws_iam_role_policy.handler`, Adresse unverändert) jetzt **nur DynamoDB (Table+GSI1+GSI2) + Logs** — SQS-Statement entfernt.
- Neu: `data.aws_iam_policy_document.sqs` + `aws_iam_role_policy.sqs`, **count-gated** über `var.sqs_queue_arn != "" ? 1 : 0` — **ohne Queue-ARN entsteht KEINE sqs-Berechtigung** (Least Privilege), mit Queue-ARN exakt `sqs:SendMessage` auf genau diese Queue.
- Header-Kommentar korrigiert (vorher falsch: „keine sqs-Aktionen").
- Verifikation: `terraform fmt -check` PASS, `terraform validate` PASS (Quell-Repo).

**Rückwärtskompatibilität:** Bei bestehendem Wiring (Queue-ARN gesetzt, Complete-Preset) entsteht dieselbe effektive Berechtigung — nur als separate Inline-Policy (`*-handler-sqs-policy`). Plan sichtbarer Unterschied: `handler`-Policy schrumpft um das SQS-Statement, `sqs`-Policy kommt hinzu (In-Place/Neu-Anlage; kein MO-Live-Bestand betroffen — privacy-test zerstört; RIS pinned alten MO-Stand).

## 3. WP2 — Module Builder (Commit `94097e2`)

- **Katalog** (`module_builder/catalog.py`): `iam: deps=[dynamodb]`, `lambda: deps=[dynamodb, iam]` (+ je `optional_deps: ["sqs"]` dokumentiert); **Worker-Abhängigkeiten unverändert hart** (`sqs_worker: [dynamodb, sqs]`).
- **Wiring-Stripping** (`_strip_unselected_module_inputs`): Bei Nicht-Auswahl von `sqs` entfernt der Builder die Zuweisungs-Zeilen `sqs_queue_arn = module.sqs.queue_arn` (iam-Block) und `queue_url = module.sqs.queue_url` (lambda-Block). Sicher: alle anderen module.-Referenzen in Modulblöcken zeigen auf Pflicht-Deps (per fail-closed garantiert in der Auswahl); betroffene Variablen haben Defaults (`""`).
- **README** generierter Projekte: dokumentiert synchronen Betrieb bei fehlendem SQS.
- **Tests:** 49/49 — u. a. neu: `iam ohne sqs` (kein Wiring, count-Gating im kopierten Modul, Basis-Policy intakt), `lambda ohne sqs` (sync-only, lambda.zip bleibt), `iam mit sqs` (Wiring erhalten), `sqs_worker ohne sqs` weiterhin fail-closed, README-Notiz.
- **Live-Verifikation:** Builds `dynamodb,iam` und `dynamodb,iam,lambda` ohne SQS → `terraform fmt -check`/`init -backend=false`/`validate` **PASS**; `dynamodb,sqs,iam` → Wiring-Zeile erhalten; **Complete-Preset** → validate **PASS** (rückwärtskompatibel). Policy-Gate unverändert mitgeliefert (Ressourcentyp `aws_iam_role_policy` allowlisted).
- Bestehende Fail-closed-Befunde live bestätigt: nicht-leerer Zielordner wurde bei Timeout-Abbruch korrekt abgelehnt (--force-Schutz).

## 4. WP3 — Doku-Sync (dieser Commit)

- `security/iam-design.md` §2.1: Berechtigungs-Tabelle an Code angeglichen — `dynamodb:DeleteItem` (Erasure) und `sqs:SendMessage` (**OPTIONAL, count-gated**) jetzt benannt und begründet; Verbotsliste bereinigt (Scan/BatchWriteItem/CreateTable/s3:*/iam:* bleiben verboten).
- `terraform/main.tf` IAM-Kommentar (Z.60) korrigiert.
- AI_AUDITLOG aktualisiert (dieser Commit).

## 5. Testergebnisse (alle real ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| Builder-Unit-Tests (inkl. 5 neuer PHASE2-Tests) | **49/49 PASS** |
| Installer-Regression (inkl. Collision/Guide/Artifact/Parallel/Discovery/Runner) | **129/129 PASS** (178 gesamt mit Builder) |
| Lambda-Regression (Orders-Worker `sqs_handler`, State Machine, API) | **76/76 PASS** |
| terraform fmt -check + validate (Quell-Repo) | PASS |
| Live-Build `dynamodb,iam` ohne SQS — validate | PASS |
| Live-Build `dynamodb,iam,lambda` sync-only — validate | PASS |
| Live-Build `dynamodb,sqs,iam` — Wiring erhalten | bestätigt |
| Complete-Preset — validate | PASS (rückwärtskompatibel) |
| Policy-Gate in generierten Projekten | mitgeliefert, unverändert |

## 6. STOP-Einhaltung

- **KEINE Queue-Policy-Härtung** — Security-Finding `Principal = "*"` bleibt **OPEN** und blockiert ungehärtete Produktivfreigabe (ausdrücklich, per Auftrag).
- **KEINE Boundary-Änderungen** — externes Boundary-Thema bleibt OPEN (Research C).
- **KEINE AWS-Mutationen, KEINE RIS-Änderungen, KEINE Privacy-Aktivierung, KEINE Release-Tags.**
- Handler-Code, Worker-Code, Orders-Worker, RIS-Verträge: **unangetastet** (Verträge per Research B als Abnahme-Basis dokumentiert).

## 7. Offene Punkte

1. Queue-Policy-Härtung (Principal + Condition + DLQ) — **Freigabe nötig** (RIS-Live-Pfad, AWS-Mutation).
2. Boundary-Policy ins IaC überführen oder Design-Doc + `data.aws_caller_identity` statt hartcodiertem ARN — **Freigabe nötig**.
3. B2 (automatische Abhängigkeitsauflösung) — wartet auf Freigabe.
4. RIS-Dead-Code (`modules/iam` Data-Docs mit `"*"`) — RIS-seitig, separater Task.

## 8. Git

| Commit | Paket |
|---|---|
| `5c70374` | WP1 — IAM-Modul SQS-optional (count-gated) |
| `94097e2` | WP2 — Builder: Deps, Wiring-Stripping, Tests, README |
| (dieser) | WP3 — Doku-Sync (iam-design.md, main.tf-Kommentar) + Report + Auditlog |

Alle auf main gepusht, Git CLEAN nach jedem Paket, keine Release-Tags.
