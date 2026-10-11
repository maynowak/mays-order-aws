# MAYS-ORDERS-PRIVACY-RUNTIME-FIX-01

## Befund-Nachschärfung
E2E-Verify meldete zwei Lambda-Fehler. Analyse zeigt drei Ursachen, zwei im
aktuellen Code, eine im Build-Artefakt:
1. `GET/LIST → Decimal is not JSON serializable`: Das deployed
   `lambda/dist/lambda.zip` (gebaut 18.09.) enthält den Fix `50efac4`
   (01.10., `_json_default` in `index.py`) **nicht** — stale Artefakt. Der
   aktuelle Code serialisiert in `ok()`/`fail()` bereits korrekt; Lücke war
   nur `encode_next_token` (`order_service.py:66`, `json.dumps` ohne `default`).
2. `inspect/export → BLOCKED`: `ProjectionExpression` mit unmaskiertem
   reserviertem Wort `status` → `ValidationException` (live reproduziert,
   Alias-Query belegt GSI2/Datenmodell als korrekt).

## Fix (keine Architektur, kein Datenmodell, keine GSI-Änderung)
- `src/errors.py`: zentrale `json_default`-Funktion (Decimal → float, sonst
  TypeError — kein `default=str`). Existierender Helper aus `index.py`
  dorthin verschoben statt dupliziert.
- `src/index.py`: importiert `json_default` (Alias `_json_default` erhalten).
- `src/order_service.py`: `encode_next_token` nutzt `default=json_default`;
  inspect/export-Projektionen auf `... #status ...` +
  `ExpressionAttributeNames = {"#status": "status"}` umgestellt, alle übrigen
  Attribute unverändert. API-Verträge unverändert.
- `lambda/dist/lambda.zip` per `build_zip.py` neu gebaut (Fix im Artefakt
  verifiziert: `json_default` + `#status` enthalten). **Nicht deployed**
  (no-apply-Regel) — nächster Installer-Deploy übernimmt es.

## Tests (73/73 GREEN)
- Bestehend: Decimal-`ok()`-Tests, Privacy-Autorisierungs-/Erase-Tests,
  POST/PATCH/Erase/Auth-Negativpfade — unverändert bestanden.
- Neu (`TestRuntimeFixRegression`, `TestHandlerDecimalRegression`):
  GET/LIST mit Decimal über Handler (exakter Live-Fehler) → 200;
  LEK mit Decimal kodier-/dekodierbar; inspect/export übergeben
  `#status`-Alias und liefern COMPLETED statt BLOCKED.

## Status: GREEN (Code-Verifikation)
Kein Terraform, keine AWS-Mutationen, kein Lambda-Update in AWS.
STOP wie beauftragt — Deploy + Re-Verify separater freigegebener Schritt.
