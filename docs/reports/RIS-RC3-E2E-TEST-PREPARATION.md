# RIS-RC3-E2E-TEST-PREPARATION

**Vorbereitung/Abgleich des RIS AWS E2E-Tests vor RC.3**

**Datum:** 2026-10-31 (Revision 2)
**MO Commit:** `8b61922a2d79180ad5b14e51e51e4568b8ad2098`
**RIS Branch:** `feature/mo-module-installer-ris-dev2-2026` @ `73965e3`
**Status:** ✅ **RESOLVED — kein neuer E2E-Test erforderlich**

> **Revision 2:** Revision 1 meldete BLOCKED, weil das RIS-Repo lokal nicht als
> Git-Repository vorlag. Das RIS-Repo wurde inzwischen read-only aus GitHub
> gelesen (`/tmp/opencode/ris-readonly`). Die dortige Evidence belegt einen
> vollständigen AWS-E2E-Lauf gegen den gepinnten Builder `1dbb0cb`, der zu
> RC.3 (`8b61922`) **code-identisch** ist (Delta: Whitespace + Docs).

## 1. RIS Git-Baseline (VERIFIED)

| Feld | Wert |
|------|------|
| Repository | `maynowak/Mays-Recruiting-Intelligence-System` |
| Branch | `feature/mo-module-installer-ris-dev2-2026` |
| Branch-HEAD (remote) | `73965e3964ec86fe265a0cce5670e58bf77ceacf` |
| Zugriff | read-only (ls-remote + shallow clone nach `/tmp`) |

## 2. Pins (VERIFIED)

| Pin | Commit |
|---|---|
| `installer/mays-orders-builder.pinned.json` (maßgeblich) | `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d` |
| `installer/mays-orders-clone.pinned.json` (Legacy) | `5cf50a0` (rc.2 prep) |

## 3. Vorhandene AWS-E2E-Evidence (VERIFIED AWS E2E)

`docs/reports/RIS-MO-RC-01-CONSUMER-ACCEPTANCE.md` (2026-10-30), Pipeline
BUILD → APPLY → LIVE TEST → DESTROY → CLEAN, Account `262370457690`,
Workspace `ris-dev2`:

| Test | Ergebnis |
|---|---|
| Init / Plan (169 add, 0 change, 0 destroy) | PASS |
| Apply | PASS (Exit 0) |
| Post-Deploy No-Op | PASS |
| Live-Tests T-01…T-07 | 7/7 PASS |
| SQS → Worker → DynamoDB (`PENDING → CONFIRMED`) | PASS |
| Destroy | PASS (Exit 0) |
| Cleanup (nur Backend bleibt) | PASS |

Evidence-Dateien: `docs/reports/evidence/RIS-MO-RC-01-2026/` (`03`, `05`, `08`, `09`),
`plan-ris-dev2.txt`, `tf-outputs.json`.

## 4. Security-Fix-Delta (VERIFIED)

| Fix | im getesteten Pin `1dbb0cb`? | Nachweis |
|---|---|---|
| F-03 SQS-Wildcard entfernt | JA | keine `aws_sqs_queue_policy` in `modules/sqs/main.tf`; F-03 im RIS-Report RESOLVED |
| GAP-06 plan-stabiles SQS-Gate | JA | `count = var.sqs_enabled ? 1 : 0` |
| IAM-Portabilität (FIX-01/02) | JA | `lambda_execution_boundary` default `null`; Installation in fremdem Account gelungen |

## 5. Delta getesteter Pin ↔ RC.3 (VERIFIED LOCAL)

`git diff -w 1dbb0cb..main -- terraform/ lambda/ module_builder/ installer/ scripts/`
ist **leer**; ohne `-w` ausschließlich `terraform/main.tf` (10+/10−, reine Ausrichtung).
→ Kein Retest für RC.3 erforderlich.

## 6. Kosten- und Ressourcenrisiko (nur falls doch ein Test nötig würde)

| Posten | Größenordnung |
|---|---|
| Infrastruktur | ~169 Ressourcen, On-Demand/Pay-per-Request |
| Laufzeit | 1 Apply + 1 No-Op + 1 Destroy, ca. 30–60 min inkl. CloudFront-Abbau |
| Backend | S3 `ris-dev2-tf-state-dev` + DDB `ris-dev2-tf-lock` bleiben bewusst erhalten |
| Bekannte Fallstricke | CLI-Timeout → verwaiste State-Locks; CloudTrail-Bucket `BucketNotEmpty`; doppelte CloudFront-Distributionen |

## 7. Entscheidung

**READY (already executed) — kein neuer AWS-E2E-Test vor RC.3.**

- Vorhandene Evidence deckt den RC.3-Code ab (Code-Identität).
- Ein zusätzlicher Lauf ist erst vor **Produktionsfreigabe** oder bei einer
  Code-Änderung gegenüber `1dbb0cb` sinnvoll.

**Nächste Schritte (menschlich):** Tag `v0.5.0-rc.3` auf `8b61922`; optional
RIS-Builder-Pin auf `8b61922` nachziehen (rein kosmetisch).
