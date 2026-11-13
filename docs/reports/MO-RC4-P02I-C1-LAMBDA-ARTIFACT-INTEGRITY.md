# MO-RC4-P02I-C1-LAMBDA-ARTIFACT-INTEGRITY

**Lambda-Artefakt repariert · gemeinsame Integritätsprüfung für Installer und Builder**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**Basis:** `f5a3b03d018ad947a75cabdb231adf3923cb9381`
**Typ:** Implementierung + Regression (lokal) — **kein Deployment**, keine AWS-Operation, kein Push

---

## 1. Ausgangsfehler und Root Cause

| Befund | Detail |
|---|---|
| Symptom | `lambda/dist/lambda.zip` enthielt **7 von 11** Modulen (Stand 2026-10-11) |
| Fehlend | `identity.py`, `order_handlers.py`, `processing_result.py`, `recovery.py` |
| Zusätzlich veraltet | `index.py`, `order_service.py`, `sqs_handler.py` (seit P02/P02E/P02G geändert, im ZIP alt) |
| Folge | `index.py` → `ModuleNotFoundError: identity` (API-Cold-Start); `sqs_handler` → `order_handlers` (Worker) |
| **Root Cause** | `lambda/build_zip.py` pflegte eine **hartcodierte Modulliste** (7 Einträge); neue Module wurden nie ergänzt. Ein Rebuild reproduzierte den Fehler. |
| Erkennbarkeit | Installer-Gate (`verify_lambda_zip`) hätte FAIL gemeldet; Builder prüfte nur Existenz → hätte das defekte ZIP ausgeliefert |

---

## 2. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `lambda/build_zip.py` | **Modulliste ersetzt** durch sortierten Glob `src/*.py`; Pflicht-Handler (`index.py`, `sqs_handler.py`); **deterministische ZIP-Bytes** (fester Zeitstempel 1980-01-01, feste Rechte, DEFLATE); optionaler Zielpfad für Tests |
| `installer/core/artifact_integrity.py` | Kanonische Prüfung um **Pflicht-Handler** (`REQUIRED_MODULES`) erweitert (Handler fehlt → FAIL) |
| `module_builder/builder.py` | Neues Fail-Closed-Gate `_verify_lambda_artifact()` (nutzt **die kanonische Installer-Prüfung**, keine zweite Whitelist); aufgerufen in `build()` (Preset) und `build_module()` (orders-service) |
| `lambda/dist/lambda.zip` | **neu gebaut**: 11 Module, sha256 `bd6f2795…` |
| `lambda/tests/test_build_zip.py` | **neu**: Vollständigkeit, Determinismus, Zeitstempel, Imports aus dem ZIP |
| `installer/tests/test_artifact_integrity.py` | Fixtures mit Pflicht-Handlern; neue Fälle: leeres ZIP, fehlender Handler, korruptes ZIP |
| `module_builder/tests/test_module_builder.py` | **neu**: Gate akzeptiert echtes Artefakt, weist veraltetes/fehlendes ZIP fail-closed zurück |

Keine Änderung an Processing-State-Machine, Authorization, Privacy-Verträgen oder Terraform.

---

## 3. ZIP-Inhalt vorher/nachher

| | vorher | nachher |
|---|---|---|
| Dateien | 7 | **11** |
| `index.py` | alt (2026-10-11) | aktuell |
| `order_service.py` | alt | aktuell |
| `sqs_handler.py` | alt | aktuell |
| `identity.py` | **fehlt** | enthalten |
| `order_handlers.py` | **fehlt** | enthalten |
| `processing_result.py` | **fehlt** | enthalten |
| `recovery.py` | **fehlt** | enthalten |
| Zeitstempel | gemischt | **alle 1980-01-01** |
| sha256 | `b1018a3b…` | **`bd6f2795…`** |

---

## 4. Build-Reproduzierbarkeit

- Zwei aufeinanderfolgende Builds erzeugen **byte-identische** Archive
  (sha256 `bd6f279538c077d6fe1778d8a7ed67b0a6760314416030429de5e14a69dcd323`).
- Fester Zeitstempel + feste Rechte + sortierte Reihenfolge (getestet).
- Neue Module werden automatisch aufgenommen (Glob) — der Fehler kann sich nicht wiederholen.

---

## 5. Integritätsprüfung (eine Quelle der Wahrheit)

`installer/core/artifact_integrity.py::verify_lambda_zip(lambda_dir)`:

1. ZIP fehlt → FAIL (mit Rebuild-Hinweis)
2. ZIP korrupt (`BadZipFile`) → FAIL
3. ZIP leer → FAIL (fehlende Module)
4. Runtime-Modul fehlt → FAIL (`missing modules: [...]`)
5. **Handler fehlt** → FAIL (`Missing handler module(s)`) — neu
6. Veraltetes ZIP (7 Module) → FAIL (`missing modules`)
7. Vollständiges ZIP → PASS (`Lambda artifact current (11 modules)`)

Seiteneffektfrei (nur Lesen). **Keine zweite Whitelist:** Der Builder importiert genau diese
Funktion; die einzige „Liste" ist der Dateibestand `src/*.py`.

---

## 6. Builder-Gate

```text
lambda/dist/lambda.zip vorhanden?  (Phase A, bestehend)
        ↓
verify_lambda_zip()  → FAIL ⇒ module-builder: FEHLER: ... fail-closed (nichts geschrieben)
        ↓ PASS
Artefakt übernehmen (bestehend)
```

- Gilt für Preset-Builds **und** `orders-service`-Modulbuild.
- CLI/Verträge unverändert.
- Ist das `installer`-Paket nicht importierbar → ebenfalls fail-closed mit klarer Meldung
  (kein stilles Überspringen).

---

## 7. Installer-Gate

Unverändert fail-closed; Aufruf in `installer/core/context.py::_check_lambda_artifact`
(`validate`/Preflight). Durch die Erweiterung erkennt es zusätzlich fehlende Handler.
Verhalten im Repo nach Rebuild:

```text
installer gate: True - Lambda artifact current (11 modules)
```

---

## 8. Handler-Importprüfung (lokal, ohne AWS)

ZIP in temporäres Verzeichnis entpackt, dann in einem frischen Python-Prozess:

```text
import index, sqs_handler, recovery, order_service, identity,
       order_handlers, processing_result
→ OK (index.handler, sqs_handler.handler, run_recovery, run_processing_recovery callable)
```

- Kein Import-Zyklus (`recovery` importiert `sqs_handler` erst in der Funktion).
- Keine Seiteneffekte, keine AWS-Aufrufe, boto3 wird nur importiert.
- **OPEN:** AWS-Cold-Start (echte Runtime) bleibt dem E2E-Test vorbehalten.

---

## 9. Testzahlen

| Suite | Vorher | Nachher |
|---|---|---|
| Lambda | 321 | **326** (+5 `test_build_zip`) |
| Builder | 90 | **93** (+3 Gate) |
| Installer (`test_installer` + `test_artifact_integrity`) | 81 | **89** (+3 Integrity-Fälle, 8 gesamt) |
| **Gesamt** | 492 | **508** |

Zusätzlich:
- `terraform validate` → **PASS**
- `terraform fmt -check -recursive` → **PASS**
- Generiertes `complete`-Projekt: init 0 · validate **PASS** · ZIP mit **11 Modulen**
- `git diff --check` → clean · Secret-Audit → keine Treffer

---

## 10. Terraform-Kompatibilität (statisch)

- `filename = "${path.root}/../lambda/dist/lambda.zip"` (root + sqs-worker) — unverändert.
- `source_code_hash = filebase64sha256(var.filename)` — Hash ändert sich mit dem neuen ZIP
  (gewollt: Lambda-Update beim nächsten Apply).
- Handler-Pfade unverändert (`index.handler`, `sqs_handler.handler`), Runtime `python3.14`.
- Builder kopiert dasselbe ZIP; Installer-Pfad unverändert.
- **Keine Infrastrukturänderung** durch diesen Checkpoint.

---

## 11. Verbleibende Risiken

| Risiko | Status |
|---|---|
| AWS-Cold-Start nicht real getestet | **OPEN** (E2E) |
| Builder benötigt importierbares `installer`-Paket (fail-closed sonst) | **dokumentiert** |
| ZIP-Größe/-Hash ändert sich → Lambda-Update beim nächsten Apply | erwartet |
| CI prüft weder Tests noch Artefakt | **OPEN** (separater Vorschlag) |
| DLQ-Alarm ohne Benachrichtigungskanal | **OPEN** (P02I-C) |

---

## 12. Deployment-Readiness

**Artifact-Blocker aus P02I-C: behoben (VERIFIED lokal).**

- Installer-Gate: PASS (11 Module).
- Builder-Gate: defekte ZIPs werden fail-closed abgelehnt.
- Imports aus dem ZIP: OK.

**Status: CONDITIONALLY READY für kontrollierten AWS-E2E** (weiterhin offen: AWS-Cold-Start,
Plan-Review, `processing_recovery_enabled=false`, Alarm-Kanal). **NOT DEPLOYED.**

---

## 13. Commit

Commit-SHA: siehe Abschlussbericht (dieser Commit). Working Tree nach Commit CLEAN.

---

## 14. Statusübersicht

| Element | Status |
|---|---|
| `build_zip.py` vollständig/deterministisch | **IMPLEMENTED** |
| Artefakt neu gebaut (11 Module) | **VERIFIED** |
| Gemeinsame Prüfung (Handler-Pflicht) | **IMPLEMENTED** |
| Builder-Gate | **IMPLEMENTED / VERIFIED** |
| Installer-Gate | **VERIFIED** (unverändert fail-closed) |
| Handler-Imports (lokal) | **VERIFIED** |
| AWS-Cold-Start | **OPEN** |
| Deployment | **NOT DEPLOYED** |
