# May's Orders — Lambda

> Aktiver Stand (Branch `feature/lambda-python-314`): **Python 3.14**
> (`python3.14`, Handler `index.handler`). Die Node.js/TypeScript-
> Implementierung (T011-04, `nodejs22.x`) bleibt als **historische Baseline**
> im Repo und ist über `npm` weiterhin baubar/testbar.

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
  Clients (entspricht dem Node-Baseline-Testansatz).
- ZIP-Entscheidung: `dist/lambda.zip` wird vom Python-Build erzeugt (6 Module,
  ~6,6 KB).

## Node.js/TypeScript (Baseline, T011-04)

```text
cd lambda
npm install
npm test                                 # Vitest 45/45
npm run build                            # tsc --noEmit + esbuild → dist/index.js
npm run package                          # bestzip → dist/lambda.zip
```

> Hinweis: `npm run package` überschreibt `dist/lambda.zip` (gleicher Pfad).
> Für den aktiven Python-Stand immer `python3 build_zip.py` verwenden.
> `dist/` ist gitignored; beide Builds sind reproduzierbar.

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
| `src/*.ts` / `tests/*.test.ts` | Node-Baseline (T011-04), unverändert |
