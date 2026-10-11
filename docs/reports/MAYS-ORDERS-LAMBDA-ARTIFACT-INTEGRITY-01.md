# MAYS-ORDERS-LAMBDA-ARTIFACT-INTEGRITY-01

## Befund
- `source_code_hash = filebase64sha256(...)` bereits an allen drei
  `aws_lambda_function`-Ressourcen vorhanden (handler, sqs-worker,
  cognito-backup) — **nicht dupliziert**, kein Terraform-Change nötig.
- Eigentliche Lücke (E2E-Vorfall): nichts erzwang, dass `dist/lambda.zip`
  aus dem freigegebenen `src/` gebaut war — stale ZIP (18.09., ohne Fix
  `50efac4`) wurde deployed. Hash erkennt nur Drift vs. State, keine
  Staleness vs. Source.

## Fix (bestehender Installer, keine neue Pipeline/Architektur)
- Neu `installer/core/artifact_integrity.py`: `verify_lambda_zip()` vergleicht
  sha256 jeder Datei in `dist/lambda.zip` mit `src/*.py` (fehlend/extra/
  abweichend → FAIL mit Rebuild-Anweisung). Reine Lese-Prüfung.
- `ValidationLayer` (`installer/core/context.py`): neuer Check
  `lambda_artifact` (PASS/FAIL/SKIP), läuft vor jedem Plan/Deploy —
  stale ZIP blockiert künftig den Plan fail-closed statt still zu deployen.

## Tests (100/100 GREEN)
- Neu `test_artifact_integrity` (5): fresh→PASS, geändertes/neues Modul und
  fehlendes ZIP → FAIL mit konkreter Meldung, Repo-Artefakt aktuell.
- Bestand (95): Installer-, Workspace-, Parallel-, Discovery-, AWS-Kontext-Suites.

## Live-Nachweis (read-only)
- `validate --profile mayaws --project-name mays-orders-privacy-test`:
  `✓ lambda_artifact: Lambda artifact current (7 modules)`,
  Gesamt `11 passed, 0 failed`.

## Status: GREEN
Kein apply/destroy, keine AWS-/State-Änderungen. Hinweis (out of scope):
`cognito_backup.zip` hat kein Build-Skript im Repo — bei Bedarf separat.
