# MO-RC-BASELINE-RECONCILIATION-01

**Git- und Entwicklungsstand konsolidieren**

**Datum:** 2026-10-28

## Git-Stand

| Punkt | Wert |
|---|---|
| Repository | maynowak/mays-order-aws |
| Branch | feature/mo-module-contract-ris-dev2-2026 |
| HEAD | a46b189a0b8271a3847b1e00d09bfcf2039b9d2e |
| Working Tree | clean |

## Referenz-Commits vorhanden

- `59ac07869dd2dcc363bf6f4e708521d15c49e352` — docs(audit): IAM portability audit MAYS-ORDERS-MODULE-IAM-PORTABILITY-AUDIT-01 — vorhanden
- `ccf22a317dbe278ff19c33c0a47555c65f722382` — fix(iam): ... MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-01 — vorhanden
- `a46b189a0b8271a3847b1e00d09bfcf2039b9d2e` — fix(iam): ... terraform and builder changes — vorhanden

## Entwicklungsübersicht

| Entwicklung | Implementiert | Getestet | Dokumentiert | Commit |
|---|---|---|---|---|
| Module Builder | ja | ja — 90 Tests OK | ja | a46b189 |
| IAM FIX-01 | ja | ja | ja — MAYS-ORDERS-MODULE-IAM-PORTABILITY-FIX-01.md | ccf22a3 / a46b189 |
| IAM FIX-02 | nein | nein | nein | — |
| Lambda-Packaging | teilweise | nicht verifiziert | nein | — |
| SQS F-03 | offen | nein | nein | — |

## Befunde

- FIX-01 abgeschlossen: sqs-worker Modul default `null`, Root-Variable noch kontospezifisch.
- `terraform/variables.tf` enthält weiterhin `default = "arn:aws:iam::240571105849:policy/..."`.
- Lambda ZIP existiert unter `lambda/dist/lambda.zip`, Inhalt geprüft.
- SQS Resource Policy mit `Principal = "*"` vorhanden in `terraform/modules/sqs/main.tf`.
- Keine uncommitteten Änderungen.
- Keine Lambda-Packaging-Änderungen seit a46b189.
- F-03 nicht bearbeitet.

## Nächste Schritte

- IAM FIX-02 abschließen
- Lambda-Artefaktvertrag prüfen
- SQS Resource Policy F-03 beheben
- Regressionstests ausführen
