# May's Orders — Lambda

> **Aktiver Stand:** Python 3.14 (`python3.14`, Handler `index.handler`).
> Die historische Node.js/TypeScript-Implementierung (T011-04, `nodejs22.x`)
> wurde im Cleanup (T011-04-PYTHON-CLEANUP) aus dem aktiven Lambda-Projekt
> entfernt und ist ausschließlich über die Git-Historie nachvollziehbar
> (Baseline-Commit `449cdd7`, Branch `feature/lambda-python-314`).

## Python (aktiv)

```text
cd lambda
python3 build_zip.py                      # → dist/lambda.zip (reproduzierbar)
PYTHONPATH=src python3 -m unittest discover -s tests -v   # Tests (unittest)
python3 -m compileall -q src tests        # Syntax-Check
```

- Handler: `index.handler` (`index.py` am ZIP-Root).
- boto3 wird von der Python-Lambda-Runtime bereitgestellt → kein
  `requirements.txt`, kein boto3-Bundling.
- Lokal ist boto3 nicht installiert; die Unit-Tests injizieren Fake-DynamoDB-
  Clients.
- ZIP-Entscheidung: `dist/lambda.zip` wird vom Python-Build erzeugt (6 Module,
  ~6,6 KB).

## Node.js/TypeScript (historische Baseline, T011-04)

Entfernt — nicht mehr im aktiven Repo, nicht mehr baubar/testbar. Nachvollziehbar
über Git-Historie (Baseline-Commit `449cdd7`, Vitest 45/45, `nodejs22.x`) und den
Migrationsbericht `docs/reports/LAMBDA-PYTHON-3.14-MIGRATION.md`.

## Module-Übersicht

| Datei | Zweck |
|-------|-------|
| `src/index.py` | Handler, Routing, API-GW-v2-Event, Fehler→HTTP |
| `src/order_service.py` | Order-Service AP1..AP4, DynamoDB (boto3) |
| `src/state_machine.py` | Transition-Matrix |
| `src/validation.py` | Validierung |
| `src/errors.py` | OrderError + Fehler-Factorys |
| `src/order_types.py` | Konstanten + Typen (TypedDict) |
| `tests/test_*.py` | Python-Unit-Tests (unittest) |