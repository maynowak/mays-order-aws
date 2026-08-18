# LAMBDA Runtime Comparison — Node.js/TypeScript vs Python 3.14

> Tatsächlich vorhandener Stand im Repository:
> **Baseline T011-04** (Node.js/TypeScript, `nodejs22.x`) und
> **Migration** (`feature/lambda-python-314`, `python3.14`).
>
> Keine Performance-/Kostenbehauptungen ohne echte Messwerte. Werte, die nicht
> aus einer tatsächlichen Ausführung/AWS-Invocation stammen, sind explizit als
> **nicht gemessen** markiert.

## Vergleichstabelle

| Aspekt | Node.js/TypeScript (Baseline) | Python 3.14 (Migration) | Anmerkung |
|--------|-------------------------------|--------------------------|-----------|
| Lambda Runtime | `nodejs22.x` | `python3.14` | `terraform/main.tf` `aws_lambda_function.handler` |
| Programmiersprache | TypeScript (strikt getypt), kompiliert nach JavaScript | Python (dynamisch getypt; Typen via `typing`/`TypedDict`) | — |
| Handler-Eintrag | `index.handler` (CommonJS-Bundle `dist/index.js`) | `index.handler` (`from index import handler`; `index.py` am ZIP-Root) | gleicher String, unterschiedliche Auflösung |
| Build-Schritt | **ja, notwendig:** `tsc --noEmit` + esbuild-Bundle (ein JS-File) | **nein:** Python-Quellcode wird direkt gepackt | Python benötigt keinen Kompilier-/Bundling-Schritt |
| Bundling | esbuild, ein minifiziertes `dist/index.js` | entfällt (6 Module als `.py` im ZIP) | — |
| Packaging | `npm run package` (bestzip) → `dist/lambda.zip` | `python3 build_zip.py` (Stdlib `zipfile`) → `dist/lambda.zip` | reproduzierbar; gleicher ZIP-Pfad |
| Deployment | Terraform `filename` + `source_code_hash` | Terraform `filename` + `source_code_hash` | unverändert |
| Lambda Console / Code Visibility | **nur** gebündeltes JS sichtbar (Minified); Quelltext liegt in Git | **nur** Python-Quelltext sichtbar; Quelltext liegt in Git | AWS-Konsole ist NICHT die Entwicklungs-Umgebung; Git bleibt Source of Truth |
| Dependencies | `@aws-sdk/client-dynamodb`, `@aws-sdk/lib-dynamodb` (im Bundle) | boto3 (von der Python-Runtime bereitgestellt, **nicht** gebündelt) | keine weiteren Pakete nötig |
| Package Size | ~156 KB (Zip, nur `dist/index.js`); Quelle `index.js` 518,4 KB | 6.779 Bytes (~6,6 KB, 6 Module) | **gemessen**; Größe allein sagt nichts über Laufzeit aus |
| Memory Size | Terraform-Default (kein `memory_size` gesetzt) | Terraform-Default (kein `memory_size` gesetzt) | nicht gemessen (kein apply) |
| Cold Start | nicht gemessen | nicht gemessen | kein AWS-Runtime-Einsatz |
| Execution Duration | nicht gemessen | nicht gemessen | kein apply/keine Invocation |
| Wartbarkeit | strikte Typen, `noUnusedLocals`, Build-Check | einfacher Build, Stdlib-Test via `unittest`, Typen via TypedDict | subjektiv; beide dokumentiert |
| Lernbezug | TS→JS-Bundling, Node-SDK, Vitest | Python, boto3, unittest | unterschiedliche Schwerpunkte |
| AWS SDK | AWS SDK for JavaScript v3 | boto3 | gleiche DynamoDB-Operationen |
| Erwartete Kosten | 0 (nicht deployed) | 0 (nicht deployed) | keine Ressourcen erzeugt; Kosten hängen von Workload ab |

## Konsole / Source Code — Modellunterschied

```text
Bisher (Node.js/TypeScript):
TypeScript-Source (lambda/src/*.ts)
  → Build/Bundling (tsc --noEmit + esbuild) → dist/index.js
  → ZIP (bestzip) → dist/lambda.zip
  → Lambda (nodejs22.x)

Neu (Python 3.14):
Python-Source (lambda/src/*.py)
  → ZIP (python3 build_zip.py) → dist/lambda.zip
  → Python 3.14 Lambda Runtime
```

- **Git bleibt Source of Truth.** Die AWS-Konsole ist keine primäre
  Entwicklungsumgebung; direkte Konsole-Änderungen können beim nächsten
  Terraform-/ZIP-Deployment überschrieben werden.
- Die Möglichkeit, Python-Code in der Lambda-Konsole zu sehen/bearbeiten, ist
  ein reines Runtime-Feature — nicht Teil des Git-basierten
  Entwicklungsprozesses.

## Performance / Cost — Vorbereitung kontrollierter Vergleich

Noch **keine** AWS-Ressourcen erzeugt. Für einen späteren, kontrollierten
Vergleich (nach `apply` und Freigabe) sind für **beide** Stände folgende
Metriken mit vergleichbarer Arbeitslast (gleiche AP1..AP4-Sequenz, gleiche
Event-Größen, gleicher `timeout = 10`) zu messen:

- Memory Size (konfiguriert, aktuell Default)
- Duration (Median/p90/p99)
- Init Duration (Cold Start)
- Max Memory Used
- Package Size (bereits gemessen: Node ~156 KB vs Python ~6,6 KB)
- Invocation Count
- geschätzte Lambda-Kosten (aus echten CloudWatch-Daten, nicht geschätzt)

Bis dahin: alle Laufzeitwerte **nicht gemessen**. Es wird ausdrücklich nicht
behauptet, dass Python „grundsätzlich schneller", „grundsätzlich
speichereffizienter" oder „automatisch billiger" ist — diese Eigenschaften sind
workload- und konfigurationsabhängig.
