# MO-ORDER-DESCRIPTION-05 — SKU-CONVENTION GUIDANCE

**Status:** `IMPLEMENTED / VERIFIED (DOKUMENTATION)` · **Datum:** 2026-11-24
**Basis:** `main` `64c32a6` · **Scope:** Dokumentationserweiterung, keine Code-/
AWS-/Terraform-/RIS-Änderung.

## 1. Anlass

`items[].sku` ist ein freier String ohne Katalogprüfung. Für interne Consumer soll
dokumentiert werden, dass sie eigene SKU-Konventionen definieren und das Feld
zusätzlich als **informative Order-Art-Markierung** nutzen können — ausdrücklich
**nicht** als Routing-Ersatz für `orderType`.

## 2. Änderungen

| Datei | Änderung |
|---|---|
| `api/endpoints.md` | Neuer Abschnitt **§2.1.1 „Eigene SKU-Konventionen (Empfehlung, nicht normativ)"** inkl. Regeln und Beispiel |
| `api/api-documentation.md` | Konsistenz-Hinweis: SKU frei/nicht kataloggeprüft; eigene Konventionen sind Consumer-Verträge |
| `database/dynamodb-design.md` | Hinweis am Item-Modell: SKU-Semantik, kein Routing-Ersatz, Verweis auf §2.1.1 |

## 3. Inhalt der Empfehlung

- `orderType` bleibt das Routing-/Verarbeitungsfeld; `sku` ist Positionskennung.
- Eigene Konventionen: stabil, dokumentiert, versioniert, kurzer druckbarer Text,
  keine Secrets/PII, unbekannte SKUs fail-safe behandeln.
- Die API erzwingt nur „nicht leer"; sie trimmt nicht und prüft keine Länge/Katalog.
- Preis bleibt Pflicht (`quantity >= 1`, `unitPrice >= 1`), auch für Marker-SKUs.
- `items` ist über die öffentliche API nach dem Anlegen unveränderlich; direkte
  Tabellenschreiber (z. B. RIS) müssen den Tabellenvertrag einhalten.

## 4. Beispiel (informativ, kein Vertrag)

Interner Consumer A verwendet beim Anlegen (oder als autorisierter direkter
Tabellenschreiber) den SKU-Wert `Benutze Bestellung auf Korb X` als
Order-Art-Hinweis und verarbeitet die Order; seinen eigenen Zustand „wartet"
meldet er in seinem Verarbeitungsstatus, nicht durch Umschreiben von `items`
über die öffentliche API.

```json
"items": [
  { "sku": "Benutze Bestellung auf Korb X", "quantity": 1, "unitPrice": 199 }
]
```

Für maschinelle Verarbeitung wird ein kurzer, stabiler Token (z. B. `BASKET-X`)
empfohlen; der Satz ist nur ein Beispiel für eine freie Konvention.

## 5. Verifikation

- Keine Code-, Test-, Terraform-, CI- oder RIS-Änderung; bestehende 456 Lambda-
  Tests bleiben unberührt.
- `git diff --check`: PASS.
- Keine AWS-Mutation, kein Deployment.

## 6. Grenzen

- Die Empfehlung ist **nicht normativ**; sie ändert den API-Vertrag nicht.
- Eine katalogisierte SKU-Prüfung, Längenbegrenzung oder ein SKU-Update via API
  sind weiterhin nicht implementiert und nicht Teil dieses Auftrags.
