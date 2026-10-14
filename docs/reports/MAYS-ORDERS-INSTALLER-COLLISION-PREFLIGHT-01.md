# MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01

**Checkpoint:** MAYS-ORDERS-INSTALLER-COLLISION-PREFLIGHT-01
**Datum:** 2026-10-14
**Baseline:** 450ad94 (remote main), Tag v0.5.0-rc.1 → f6e737b
**AWS-Kontext (read-only):** Profil mayaws, Konto 240571105849, Region eu-central-1
**Status:** IMPLEMENTED / VERIFIED (Tests GREEN, Live-Nachweis erbracht)

## 1. Ausgangslage und Incident

Im AWS-Konto 240571105849 existieren **zwei unabhängige Deployments mit demselben
Projektnamen `mays-orders`**:

| Deployment | State | Cognito-Pool | Ressourcen |
|---|---|---|---|
| Dieses Repo (Mays-Orders-AWS) | S3-Backend `env:/mays-orders/terraform.tfstate`, Serial 18 | `eu-central-1_xhjl0PxEH` (2026-09-27) | Cognito-Backup-Stack (25 Blöcke: Pool/Client/Gruppe, Backup-Bucket, Backup-Lambda, Scheduler, SNS, IAM, 2 Alarme) |
| Parallel-Installation (RIS-verwaltet, Repo Mays-Recruiting-Intelligent-System) | Lokaler State `installer/projects/mays_orders/terraform/terraform.tfstate`, Serial 129 | `eu-central-1_ENMwxNFS9` (2026-10-08, Zuvor `8HrAMWpB2` aus GATE-3) | Voller MO-Stack (45 Blöcke: API, CloudTrail, Cognito, DynamoDB, Lambda, SQS, Worker, Monitoring) |

Beide Pools heißen identisch **`mays-orders-users`** und tragen denselben Tag
`Project=mays-orders` — die Tags allein können die Owner nicht unterscheiden.
Kein Tooling machte die Kollision sichtbar; die Klärung kostete erheblich Zeit
(User-Zitat: „hat das zeit gekostet -.-").

**Belege:** RIS GATE-3-Report (unser Backup-Stack dort ausdrücklich als
„vorgefunden, NICHT Gate-3, nicht angefasst" dokumentiert); RIS
MAYS-RIS-CLEANUP-AND-VERIFY-mitluftposter-01 („Protected Orders", Serial 129,
lokaler State); RIS-AWS-STATE-INVENTORY-01 (vermischte Ressourcenzuordnung);
Live-Audit dieses Checkpoints (2 Pools, 0 Users in beiden, Backup-Bucket enthält
nur Sep-27-JSON-Backups à 172–874 Bytes des leeren Pools).

## 2. Implementierung

**Neu:** `installer/core/collision_scan.py`
- Read-only AWS-Inventar via `aws` CLI (subprocess, JSON): Cognito-Pools,
  DynamoDB-Tabellen, Lambda-Funktionen, SQS-Queues, S3-Buckets.
- Injektionsbarer `runner` → Unit-Tests ohne echtes AWS.
- `find_name_duplicates()` — identische Namen innerhalb eines Service
  (Incident-Form: 2× `mays-orders-users`), Rückgabe mit IDs.
- `match_project_resources()` — Ressourcen mit Projektnamen-Match,
  case-insensitive, pro Service gruppiert.

**Neu:** `ValidationLayer._check_aws_project_collisions()` (context.py),
ausgeführt in `run_all()` → automatisch in `validate` UND Plan-Preflight:
- Kein AWS-Kontext → WARNING (Skip), Scan-Fehler → WARNING (best-effort, nie FAIL).
- Duplikate → WARNING mit IDs und Parallel-Deployment-Hinweis.
- Nur Matches → WARNING mit Ownership-Hinweis („this state vs. parallel owner").
- Keine Treffer → PASS.

**Fix:** `installer/cli/main.py` `_cmd_validate` — pre-existing Einrückungsfehler:
der Errors/Warnings-Block lag **in** der Check-Schleife und printete nach jedem
Check alle akkumulierten Warnungen erneut. Dedent → Ausgabe jetzt einmalig und
lesbar.

## 3. Tests

| Suite | Ergebnis |
|---|---|
| Neu: `installer/tests/test_collision_scan.py` (19 Tests: Scan-Parsing mit Fake-Runner, Duplikat-Erkennung inkl. Incident-Form, Match-Filter, Check-Klassifikation, Degradation, run_all-Integration) | 19/19 OK |
| Installer-Vollregression (test_installer, artifact_integrity, aws_profile_context, parallel_isolation, plan_discovery_isolation, runner_workspace, collision_scan) | **120/120 OK** |
| Lambda-Regression | **76/76 OK** |
| `compileall` installer + cli | OK |

## 4. Live-Nachweis (VERIFIED)

`./Mays-Order-AWS-installer --profile mayaws --project-name mays-orders --region eu-central-1 validate`:

```text
⚠ aws_project_collision: Name collision detected: cognito_user_pools 'mays-orders-users' x2
  — parallel deployment or orphan likely; verify ownership before plan/apply
    cognito_pools_matching_project: 2
    dynamodb_tables_matching_project: 2
    lambda_functions_matching_project: 3
    sqs_queues_matching_project: 1
    s3_buckets_matching_project: 4
    duplicates: [{... 'count': 2, 'ids': ['eu-central-1_ENMwxNFS9', 'eu-central-1_xhjl0PxEH']}]
```

Der Check hätte den Incident beim ersten `validate`/`plan` sichtbar gemacht.
Keine AWS-Mutationen; ausschließlich List-Aufrufe.

## 5. AI_AUDITLOG-Nacharbeit (erledigt)

- Fehlender Index-Eintrag `MAYS-ORDERS-RELEASE-CANDIDATE-HARDENING-01` ergänzt.
- `Latest HEAD` von veraltet `b5f698f` auf den aktuellen Stand korrigiert.
- Eintrag für diesen Checkpoint + aktualisierter Gesamtstatus.

## 6. Offene Punkte (nicht Teil dieses Checkpoints)

1. **Aufräumen des kollidierenden Rests** aus unserem S3-State-Workspace
   `mays-orders` (Backup-Stack, Serial 18, Pool `xhjl0PxEH`, 0 Users, Scheduler
   ENABLED mit täglichem cron) — Destroy-Plan-Vorbereitung folgt separat; die
   RIS-verwaltete Installation (Serial 129, Pool `ENMwxNFS9`) bleibt unangetastet.
2. Backup-Bucket hat kein `force_destroy` → vor Destroy leeren oder Config
   ergänzen (separater Schritt).
3. Optional Phase 2: Cross-Check der Inventar-Treffer gegen `terraform show -json`
   (MANAGED/UNMANAGED-Klassifikation) statt reiner Namensmatch-Warning.

## 7. Status

**IMPLEMENTED / VERIFIED** — Preflight-Kollisionsscan aktiv, Tests GREEN,
Live-Beweis gegen das reale Konto erbracht, Doku + Auditlog nachgearbeitet.
