# F012 — Optional Order Description (`orderDescription`)

> Feature-Dokumentation nach `docs/features/_progress-template.md`.
> Task-ID: **MO-ORDER-DESCRIPTION-01**. Branch: `feature/mo-order-description-01`.

## Progress-Block

```text
Feature:
F012 — Optional Order Description

Status:
✅ COMPLETE (lokal verifiziert, Branch gepusht; Merge Review offen)

Current Task:
MO-ORDER-DESCRIPTION-01 — abgeschlossen bis Merge Review

Completed Tasks:
- Patch-Prüfung und -Anwendung (`git apply --check` / `git apply`)   ✅
- Feldvertrag validiert (optional, String, 1–1.024 Zeichen nach Trim, keine
  Steuerzeichen außer TAB/LF/CR)                                      ✅
- Persistenz + Rückgabe über POST/GET, Abwesenheit bei Altbestand      ✅
- Privacy-Inspect/-Export/-Anonymisierung (mit und ohne Feld)          ✅
- Test-Harness: `test_build_zip` ortsunabhängig importierbar           ✅
- Fokussierte Tests erweitert (16 Tests)                               ✅
- Dokumentation, Execution Log, Auditlog                               ✅
- Checkpoint: Commit `923f2b7` (Harness) + `80a84ca` (Feature), Push    ✅

In Progress:
- Nichts (Arbeitsstand abgeschlossen)

Pending Tasks:
- Merge nach `main` nach menschlichem Merge Review (NICHT Teil dieses Auftrags)

Changes Made:
- lambda/src/order_types.py: `orderDescription: NotRequired[str]` im Order-Typ
- lambda/src/validation.py: `MAX_ORDER_DESCRIPTION_LENGTH = 1024`,
  `validate_order_description()`, Allowlist in `validate_create_order`
- lambda/src/order_service.py: Persistenz (nur wenn angegeben), Privacy-Inspect
  (`dataCategories`), Privacy-Export, ANONYMIZE entfernt das Attribut
- lambda/tests/test_order_description.py: 16 Vertrags-/Privacy-Tests
- lambda/tests/test_build_zip.py: `sys.path`-Bootstrap für Aufruf aus Repo-Root
- Doku: `api/endpoints.md`, `api/api-documentation.md`,
  `database/dynamodb-design.md`, `docs/diagnostics/dynamodb/schema-reference.md`,
  `docs/diagnostics/dynamodb/security-and-iam.md`

Tests:
- Lambda: 456/456 PASS (Baseline `1eaa14e`: 440/440 PASS ⇒ +16)
- Installer: 81/81 PASS · Module Builder: 129/129 PASS · Seed: 28/28 PASS
- `compileall`: PASS · `build_zip.py` zweimal byte-identisch
  (sha256 `117299c97c775038fa2ccdedf3ecc2515a3d2c2e6a537bf9ede3fff1a5b425af`)

Validation:
- `PYTHONPATH=lambda/src python3 -m unittest discover -s lambda/tests`: PASS
- `cd lambda && PYTHONPATH=src python3 -m unittest discover -s tests`: PASS
- Terraform/AWS: NOT APPLICABLE (keine Infrastrukturänderung)

Known Issues:
- `orderDescription` ist bewusst nicht Teil der kompakten Listenprojektion
  (`GET /orders`); Downstream-Konsumenten (RIS) müssen das Feld separat anfordern.
- `database/dynamodb-design.md` ist weiterhin ein Woche-1-Baseline-Dokument;
  Code-verifizierter Stand bleibt `docs/diagnostics/dynamodb/schema-reference.md`.

Blockers:
- Keine (Freigabe nur bis Merge Review, kein Merge/Deployment).

Current Checkpoint:
- Branch `feature/mo-order-description-01`, Feature-Commit `80a84ca`,
  Harness-Commit `923f2b7`; Remote-Branch gepusht; Evidence-Commit folgt.

Next Step:
- Menschliches Merge Review; danach optionaler Merge nach `main`.
```

## Vertrag (Kurzfassung)

| Aspekt | Verhalten |
|---|---|
| Feld | `orderDescription`, optionales Top-Level-Feld von `POST /orders` |
| Typ | String, nach `strip()` nicht leer, max. 1.024 Zeichen |
| Steuerzeichen | TAB (`\t`), LF (`\n`), CR (`\r`) erlaubt; übrige C0-/C1-/DEL-Zeichen, U+2028/U+2029 und Surrogates abgelehnt |
| Persistenz | DynamoDB-Attribut nur bei Angabe; kein Default, keine Migration |
| Rückgabe | `POST /orders` (201) und `GET /orders/{orderId}` (200), nicht in `GET /orders` |
| Unverändert | `items`, `orderType`, Routing, Preis-/Statusberechnung |
| Datenschutz | Inspect nennt Kategorie, Export enthält Wert, ANONYMIZE entfernt Attribut, ERASE löscht Item |
| Altbestand | Orders ohne Feld bleiben unverändert lesbar (kein Feld in der Antwort) |

## Offene Punkte

- `GET /orders`-Projektion: Bedarf eines Downstream-Konsumenten (RIS) ist nicht
  belegt; Erweiterung wäre eine additive Vertragsänderung und separat freizugeben.
- Live-Verifikation (deployte API) ist nicht Teil dieses Auftrags (kein Deployment).
