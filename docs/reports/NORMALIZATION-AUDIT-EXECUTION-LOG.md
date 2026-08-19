# NORMALIZATION-AUDIT — Execution Log

> **Task:** Normalisierung der Seed-Daten explizit prüfen (10 Fragen).
> **Auftrag:** NICHTS ändern — nur feststellen und dokumentieren.
> **Datum:** 2026-08-19
> **Basis:** HEAD `e1d80e6` (merge feature/dynamodb-seed → main), Branch `main`.
> **Repo-Zustand vor Audit:** Arbeitsbaum sauber, bis auf untracked `docs.zip` (nicht angefasst).

---

## 2026-08-19 12:36 — Schritt 1

### Aktion
Repo-Status, HEAD/Branch und Reports-Verzeichnis geprüft (Recovery-Einstieg).

### Command
git status --short
git branch --show-current
git rev-parse HEAD
ls docs/reports

### Ergebnis
PASS

### Evidenz
- Branch `main`, HEAD `e1d80e6` (merge feature/dynamodb-seed → main).
- Untracked: nur `docs.zip` (nicht angefasst).
- `docs/reports/` enthält u. a. `DYNAMODB-SEED-1000.md`, `T011-06-RECOVERY.md`, `T011-07-TERRAFORM-PLAN-REVIEW.md`.

### Auswirkungen
Keine (read-only).

### Nächster Schritt
Seed-Datei, Importer, Design-Doku und Tests lesen.

---

## 2026-08-19 12:36 — Schritt 2

### Aktion
Seed-Datei, Importer, Tests, Item-Modell und Design-Doku gelesen.

### Command
Read: database/seed/orders_seed_1000.jsonl (erste Zeilen)
Read: scripts/seed_orders.py
Read: scripts/tests/test_seed_orders.py
Read: database/dynamodb-design.md
Read: docs/reports/DYNAMODB-SEED-1000.md
Read: lambda/src/order_service.py, lambda/src/order_types.py

### Ergebnis
PASS

### Evidenz
- Datei-Items (Top-Level): `pk, sk, orderId, status, customer, items, currency, totalAmount, createdAt, updatedAt, gsi1pk, gsi1sk` (12 Felder; **kein** `version`).
- Datei-Item-Entry: `sku, name, quantity, unitPrice` (**kein** `lineTotal`).
- `normalize_item()` (seed_orders.py:55-68): baut `items[]` neu auf `{sku, quantity, unitPrice, lineTotal}` (droppt `name`), setzt `version = 1`.
- `order_types.OrderItem` (order_types.py:30-34): Modell enthält **kein** `name`.
- AP1 `create_order` (order_service.py:103-120): berechnet `lineTotal` und setzt `version = 1` identisch.

### Auswirkungen
Keine (read-only).

### Nächster Schritt
Git-Historie der Seed-Datei prüfen (angepasst vs. unverändert).

---

## 2026-08-19 12:37 — Schritt 3

### Aktion
Git-Historie und Feld-Vorkommen in der Seed-Datei quantifiziert.

### Command
git log --oneline -- scripts/seed_orders.py database/seed/orders_seed_1000.jsonl
git show --stat 13bb73f
grep -c 'lineTotal' / '"version"' / '"name"' database/seed/orders_seed_1000.jsonl
python3 (JSON-Schlüssel der ersten Zeile)

### Ergebnis
PASS

### Evidenz
- Einziger Commit für die Datei: `13bb73f` „feat: add idempotent dynamodb seed data" — **1000 insertions, 0 changes**.
- Seed-Datei: `lineTotal` = 0 Vorkommen, `"version"` = 0 Vorkommen, `"name"` = 1000 Vorkommen.
- Erste Zeile: Top-Level-Keys 12 (s. Schritt 2), Item-Keys `['name','quantity','sku','unitPrice']`.

### Auswirkungen
Keine (read-only).

### Nächster Schritt
Offene Entscheidungen aus vorherigem Arbeitsauftrag (Reports/Status) prüfen.

---

## 2026-08-19 12:37 — Schritt 4

### Aktion
Offene Entscheidungen in Reports/Status/CHANGELOG recherchiert.

### Command
Grep: T011-08|offen|Absturz in docs/**
Read: docs/PROJECT_STATUS.md (Zeilen 1-154)
Read: docs/CHANGELOG.md (Seed-Abschnitt)
git log --oneline feature/dynamodb-seed --not main

### Ergebnis
PASS

### Evidenz
- `DYNAMODB-SEED-1000.md` Z. 159/173-174: `terraform apply` **NOT RUN** — Freigabe erforderlich (T011-08); Live-Seed ⏳ PLANNED.
- `PROJECT_STATUS.md` Z. 27-28: `AWS Resources: NONE`; Z. 49: Seed „NICHT importiert (opt-in, kein apply)".
- `feature/dynamodb-seed` enthält keine über main hinausgehenden Commits (vollständig gemerged).
- Dokumentierter Absturz betrifft T011-06 (`T011-06-RECOVERY.md`), nicht den Seed-Task.

### Auswirkungen
Keine (read-only).

### Nächster Schritt
Unit-Tests und Dry-Run tatsächlich ausführen (Evidenz Q8/Q9).

---

## 2026-08-19 12:38 — Schritt 5

### Aktion
Seed-Unit-Tests und Dry-Run ausgeführt (Fake-Client vs. real; boto3-Verfügbarkeit geprüft).

### Command
PYTHONPATH=scripts python3 -m unittest discover -s scripts/tests -v
python3 scripts/seed_orders.py --dry-run
python3 -c "import boto3"  (nicht installiert)
pip/venv: nicht verfügbar (kein pip, kein python3-venv)

### Ergebnis
PASS (Tests/Dry-Run) · BLOCKED (boto3-Live-Verifikation)

### Evidenz
- Unit-Tests: **14/14 PASS** in 0.345 s (u. a. `test_normalize_sets_line_total_and_version`, TEST 8-10 gegen `FakeDynamoClient`).
- `--dry-run`: 1000 validiert, 0 geschrieben.
- boto3 lokal **nicht** installiert; pip/venv fehlen → kein empirischer Live-Test möglich.
- `seed_orders.py` nutzt den **low-level client** (`batch_get_item`/`batch_write_item`) mit **ungemarshallten** Python-Dicts; der Client erwartet AttributeValue-Format (im Gegensatz zur **resource**-API in `order_service.py`). → Potenzieller offener Punkt, erst nach apply verifizierbar.

### Auswirkungen
Keine Repo-Änderung; `/tmp/opencode/boto3check` (fehlgeschlagener venv-Versuch, außerhalb des Repos).

### Nächster Schritt
Befunde beantworten und Log abschließen.

---

## 2026-08-19 12:39 — Schritt 6

### Aktion
Audit abgeschlossen, Befunde zu den 10 Fragen formuliert, Execution-Log geschrieben.

### Command
Write: docs/reports/NORMALIZATION-AUDIT-EXECUTION-LOG.md

### Ergebnis
PASS

### Evidenz
Siehe Befunde unten. Es wurde kein Code, keine Doku-Fachquelle und kein Datenfile verändert.

### Auswirkungen
Neu erstellt: `docs/reports/NORMALIZATION-AUDIT-EXECUTION-LOG.md` (dieses Dokument, Log gemäß Recovery-Protokoll).

### Nächster Schritt
Keiner (read-only Audit). Live-Verifikation bleibt an T011-08/Freigabe gebunden.

---

# Befunde (Antworten auf die 10 Fragen)

**Grundlage:** HEAD `e1d80e6`, Code unverändert, Tests ausgeführt (14/14 PASS), Dry-Run PASS, boto3 lokal nicht verifizierbar.

### 1. Welche Felder enthält die originale Seed-Datei?
Top-Level (12 Felder): `pk, sk, orderId, status, customer, items, currency, totalAmount, createdAt, updatedAt, gsi1pk, gsi1sk`. **Kein** `version`.
Pro Item-Eintrag (4 Felder): `sku, name, quantity, unitPrice`. **Kein** `lineTotal`.
(Evidenz: erste Zeile via Python-JSON, grep-Zählungen: `lineTotal`=0, `version`=0, `name`=1000.)

### 2. Welche Felder werden vom Importer normalisiert?
`normalize_item()` (scripts/seed_orders.py:55-68) erzeugt pro Item neu `{sku, quantity, unitPrice, lineTotal}` und setzt Top-Level `version = 1`.
- `lineTotal` wird **berechnet**: `quantity × unitPrice` (seed_orders.py:63).
- `version` wird **gesetzt**: `1` (seed_orders.py:67).
- `items[].name` wird **verworfen** (das Dict wird neu aufgebaut und enthält `name` nicht mehr).

### 3. Warum werden lineTotal und version erzeugt?
Sie sind Teil des dokumentierten Item-Modells (`database/dynamodb-design.md` §2: `items[] = {sku, quantity, unitPrice, lineTotal}`, `version` = Optimistic-Locking-Feld). Im Normalbetrieb erzeugt AP1 `create_order` diese Felder server-seitig identisch (order_service.py:104 `lineTotal`, :120 `version = 1`). Der Seed gleicht die Testdaten damit exakt dem Modell und dem Produktivpfad an. Begründung dokumentiert in `docs/reports/DYNAMODB-SEED-1000.md` §2 (Z. 57-60).

### 4. Warum wird items[].name nicht gespeichert?
`name` ist **kein** Attribut des Item-Modells: `OrderItem` TypedDict enthält nur `{sku, quantity, unitPrice, lineTotal}` (lambda/src/order_types.py:30-34); auch `dynamodb-design.md` §2 listet für `items[]` kein `name`. Datenmodell = Source of Truth (DYNAMODB-SEED-1000.md Z. 48-49, 54). `name` ist nur ein menschenlesbarer Buchtitel in der Quelldatei.

### 5. Ist diese Entscheidung in dynamodb-design.md bzw. dem Seed-Report begründet?
Ja, im **Seed-Report** `docs/reports/DYNAMODB-SEED-1000.md` §2 (Tabelle „Dokumentierte Abweichungen vom Item-Modell", Z. 51-60): fehlendes `lineTotal`, vorhandenes `name` (wird nicht gespeichert), fehlendes `version` (wird gesetzt), jeweils mit Begründung (Server-seitig wie AP1; Datei bleibt Ausgangsdokument). `dynamodb-design.md` §2 definiert das Modell (enthalten: `lineTotal`, `version`; kein `name`), begründet aber die Seed-Abweichung selbst nicht — das tut der Report.

### 6. Wurde die Seed-Datei selbst angepasst oder bewusst unverändert übernommen?
**Bewusst unverändert übernommen.** Einziger Commit `13bb73f`: 1000 insertions, 0 changes; Report Z. 22 „als Ausgangsdatei unverändert ins Repo übernommen"; Datei enthält weiterhin `name` und keine `lineTotal`/`version` (grep: 1000/0/0). Die Normalisierung passiert ausschließlich beim Import (`normalize_item`), nicht in der Datei.

### 7. Welche Form wird tatsächlich an DynamoDB geschrieben?
**Bisher nichts.** `terraform apply` = NOT RUN, `AWS Resources: NONE` (PROJECT_STATUS Z. 27-28, Report Z. 159). Was in Tests/`FakeDynamoClient` gespeichert wird, ist die **normalisierte Python-Dict-Form**: Top-Level 13 Felder (12 der Datei + `version: 1`), Item-Einträge 4 Felder `{sku, quantity, unitPrice, lineTotal}` (ohne `name`).
**Offener Punkt (Risiko):** `seed_orders.py` schreibt über den **low-level client** (`batch_write_item`, Z. 183) mit **ungemarshallten** Dicts; der Client erwartet AttributeValue-Format (`{"S": ...}`). `order_service.py` nutzt dagegen die **resource**-API (`Table.put_item`), die automatisch marshallt. Ein Live-Lauf des Seeder könnte daher an boto3-Parametervalidation scheitern. Lokal nicht verifizierbar (kein boto3/pip/venv) — Verifikation nach Freigabe (T011-08) erforderlich.

### 8. Gibt es Tests für diese Normalisierung?
Ja. `scripts/tests/test_seed_orders.py`:
- `test_normalize_sets_line_total_and_version` (Z. 122-131): prüft `lineTotal == quantity × unitPrice`, `name` nicht in normalisiertem Item, `version == 1`.
- Lauf gerade erneut ausgeführt: **14/14 PASS**.

### 9. Wurde die Normalisierung nur mit Fake-Client getestet oder bereits gegen DynamoDB?
**Nur mit Fake-Client.** `FakeDynamoClient` (test_seed_orders.py:20-46) bildet `batch_get_item`/`batch_write_item` in-memory ab; TEST 8-10 laufen dagegen. Es gibt **keinen** Live-Test gegen echtes DynamoDB: Report Z. 132-133 („Real-AWS-Import ist erst nach apply möglich"), Z. 159 (`apply` NOT RUN), Z. 173-174 (Live-Seed ⏳ PLANNED). Das entspricht der dokumentierten Status-Konvention „Build: PASS ≠ Live: PASS".

### 10. Welche Entscheidung war im vorherigen Arbeitsauftrag noch offen und wurde möglicherweise durch den Absturz nicht abgeschlossen?
Vorheriger Arbeitsauftrag = T011-10 DynamoDB Testdaten-Seed (Feature `dynamodb-seed`, gemerged `e1d80e6`). **Offene Entscheidung:** der **Live-Seed gegen echtes DynamoDB** — `terraform apply -var="seed_test_data=true"` — einschließlich tatsächlicher Durchführung des Imports. Status: **NOT RUN / ⏳ PLANNED**, explizit an **menschliche Freigabe (T011-08)** gebunden (Report Z. 159, 162-167, 173-174; PROJECT_STATUS Z. 20, 49; CHANGELOG Z. 39-44).
**Absturz-Hinweis:** Für den Seed-Task selbst gibt es **keinen** dokumentierten Absturz; er wurde vollständig committet/gemerged (Branch `feature/dynamodb-seed` ohne überschüssige Commits). Der dokumentierte Agent-/VS-Code-Absturz betrifft den früheren Task **T011-06** (Recovery-Beleg: `docs/reports/T011-06-RECOVERY.md`). Zusätzlich offen: die Verifikation des in Frage 7 benannten boto3-Client-Marshalling-Risikos beim ersten Live-Lauf.