# MO-RC4-P01-CONTRACT-INVENTORY

**Benutzer-, Bestell-, Status- und Delete-Verträge (Ist-Zustand, RC3-Basis)**

**Datum:** 2026-11-01
**Branch:** `feature/mo-rc4-kms-privacy-retention`
**HEAD:** `c40b695` (P00) — bestätigt, Working Tree clean, `origin` synchron
**Typ:** reine Analyse (keine Code-/AWS-Änderung)

Legende: **IMPLEMENTED** = Code vorhanden · **VERIFIED** = durch Tests/Lauf belegt ·
**PARTIAL** = teilweise · **PLANNED** = nur geplant · **UNKNOWN** = nicht vorhanden/ungeklärt.

---

## 1. Quellen (tatsächlich gelesen)

| Pfad | Relevanz |
|---|---|
| `lambda/src/index.py` | HTTP-Routen, interner Privacy-Invoke, SQS-Kick |
| `lambda/src/order_service.py` | CRUD, Privacy inspect/export/erase, Auth-Boundary |
| `lambda/src/validation.py` | erlaubte Request-Felder |
| `lambda/src/order_types.py` | Statusliste, Item-Felder, GSI-Konstanten |
| `lambda/src/state_machine.py` | Übergangsmatrix |
| `lambda/src/sqs_handler.py` | Worker-Verarbeitung |
| `terraform/modules/dynamodb/main.tf` | Schlüssel, GSIs, PITR, TTL |
| `terraform/modules/lambda/main.tf` | Handler-Env |
| `terraform/modules/sqs-worker/{main,iam}.tf` | Worker-Env, -Rechte |
| `terraform/modules/sqs/main.tf` | Queue (keine DLQ) |
| `terraform/modules/api/main.tf` | 4 Routen, JWT-Authorizer |
| `terraform/modules/cognito/main.tf` | Pool/Client/Gruppe (keine Nutzer-Ressourcen) |
| `terraform/modules/cognito_backup_automation/main.tf` | `cognito-idp:ListUsers`-Recht |
| `cognito_backup/exporter.py` | `list_users` (Backup-Pfad) |
| `docs/reports/MAYS-ORDERS-MODULARIZATION-01-B-RIS-CONTRACTS-RESEARCH-EXECUTION_LOG.md` | RIS-Schreibpfad |
| `order-lifecycle/state-machine.md`, `transition-rules.md` | fachliche Soll-Semantik |

## 2. Analyse A — Benutzer- und Bestellverträge

### 2.1 Contract-Matrix

| Objekt | Feld | Quelle (Code) | API (Request/Response) | Speicherung (DynamoDB) | Worker | Bedeutung |
|---|---|---|---|---|---|---|
| Order | `orderId` | `order_service.py:39` (`ord_`+hex) | Response, Pfad `{orderId}` | `orderId`, `pk="ord_<id>"` | `message.orderId` | fachliche ID |
| Order | `status` | `order_types.py:5-12` | PATCH-Body, Response | `status` | `message.status` (fest `CONFIRMED` aus `index.py:31-35`) | Lebenszyklus |
| Order | `customer.name` | `validation.py:50` | POST-Body (Pflicht) | `customer.name` | — | PII |
| Order | `customer.email` | `validation.py:51-56` | POST-Body (Pflicht, Regex) | `customer.email` | — | PII |
| Order | `items[].sku/quantity/unitPrice` | `validation.py:58-72` | POST-Body | `items[]` | — | Positionen |
| Order | `items[].lineTotal` | `order_service.py:130-133` | Response | `items[].lineTotal` | — | berechnet |
| Order | `currency` | `validation.py:74-79` | POST-Body (ISO-4217) | `currency` | — | Währung |
| Order | `totalAmount` | `order_service.py:134` | Response | `totalAmount` | — | Summe |
| Order | `createdAt` / `updatedAt` | `order_service.py:43` | Response | beide | `updatedAt` aktualisiert | Zeitstempel |
| intern | `pk` / `sk` | `order_types.py:16-18` | nie | Schlüssel (sk=`#ORDER`) | liest | Storage-Key |
| intern | `gsi1pk`/`gsi1sk` | `order_service.py:148-149` | nie | Listing-Index | — | `GET /orders` |
| intern | **`subjectId`** | `order_service.py:152-157` | **nie gesetzt** (API ruft `create_order(body)` ohne subject_id, `index.py:143`) | nur wenn Parameter gesetzt | — | Nutzerbezug |
| intern | `gsi2pk`/`gsi2sk` | `order_service.py:156-157` | nie | nur mit `subjectId` | — | Privacy-Lookup |
| intern | `version` | `order_service.py:145` (Start 1) | nicht exponiert | ja | **nicht erhöht** | Optimistic Locking |
| intern | `isTestData` | Seed-Datei | gestrippt (`INTERNAL_FIELDS`) | nur Seed | — | Demo-Marker |
| **User** | `sub`/`userId`/`ownerId` | — | **JWT-Claims werden nicht gelesen** (`index.py` nutzt nur Body/Pfad) | **nicht vorhanden** | — | fehlt |
| **Tenant** | `tenantId` | — | — | **nicht vorhanden** | — | fehlt (RIS führt Tenant selbst) |
| **Retention** | `retentionUntil`/`ttl`/`expiresAt` | — | — | **nicht vorhanden** | — | fehlt |

### 2.2 Befunde

1. **`subjectId` ist strukturell vorbereitet, praktisch ungenutzt.** `create_order(subject_id=...)`
   (`order_service.py:125`, `152-157`) setzt `subjectId` + GSI2 nur, wenn der Parameter
   übergeben wird — der einzige Aufrufer (`index.py:143`) übergibt ihn **nie**. Damit:
   **PARTIAL** (Feld/Index existieren, Befüllung fehlt).
2. **Privacy-Lookup läuft ins Leere für API-Orders.** `inspect/export/erase` queryen
   ausschließlich GSI2 (`order_service.py:237, 294, 375`). Ohne `subjectId` gibt es keine
   GSI2-Items → `affectedRecords: 0`. **Folge:** Ein Benutzer-Löschauftrag findet heute
   keine über die MO-API erstellten Bestellungen. **VERIFIED** (Code-Pfad).
3. **Seed enthält kein `subjectId`** (`grep -c subjectId database/seed/orders_seed_demo_50.json` = 0).
4. **Kein `userId`/`ownerId`/`tenantId`** irgendwo in Code oder Schema.
5. **Keine Retention-Felder** (kein `retentionUntil`, kein `ttl`; DynamoDB-Modul hat keinen
   `ttl`-Block — `grep -c ttl` = 0).
6. **API-Vertrag ist absichtlich eng:** `validation.py:44` erlaubt nur `customer`, `items`,
   `currency`; unbekannte Felder → 400 (`reject_unknown_keys`). Ein Client kann also
   **heute** weder `subjectId` noch eine Frist übergeben.
7. **ANTWORT AUF DIE KERNFRAGE** — „Welche Identifikatoren sind in API-Requests vorhanden?“:
   Nur `orderId` (Pfad) und der Body (Kunde/Positionen/Währung). **Kein** Benutzer- oder
   Mandanten-Identifikator, **kein** Retention-Wert.

### 2.3 Unterschiede API ↔ Worker ↔ DB

| Aspekt | API (Handler) | Worker | DynamoDB |
|---|---|---|---|
| Status-Übergang | `can_transition` + `ConditionExpression` auf `status` + `version`-Inkrement (`order_service.py:201-225`) | `can_transition` **ohne** Condition/Wersion (`sqs_handler.py:76-93`) | keine Constraint |
| Felder | validierte Body-Felder | liest `orderId`, `status`, `payload` | alle Felder |
| PII | schreibt `customer.*` | liest/schreibt sie nicht | gespeichert |
| subjectId | nie gesetzt | nicht verwendet | optional vorhanden |
| Fehler | 400/404/409/500 | Log + `return False` (Nachricht gilt als verarbeitet → **kein Retry**) | — |
| Idempotenz | `version`-Condition | keine | — |

### 2.4 Externe Schreibpfade (RIS)

Laut `MAYS-ORDERS-MODULARIZATION-01-B-…EXECUTION_LOG.md` (Z. 21–25):
- RIS schreibt **direkt** in die MO-Tabelle (`orders_reader`: `put_item`, `update_item`,
  GSI1-Query) und sendet den SQS-Kick.
- Dabei wird das MO-Verhalten 1:1 repliziert — inklusive **`pk`-Doppelpräfix `ord_ord_…`**
  und **ohne `subjectId`**; „kein Tenant-Feld“ ist dort ausdrücklich als Befund notiert.
- RIS-IAM hat `PutItem`/`UpdateItem` auf Tabelle + `/index/*`.

**Konsequenz für RC4:** Es existieren Bestellungen, die **nicht** über MO-Code entstanden
und **nicht** über `subjectId` auffindbar sind. Cleanup/Orphan-Logik darf sie **nicht**
als „verwaist“ klassifizieren (siehe `MO-RC4-P01-ORPHAN-CLEANUP-DESIGN.md` §2).

## 3. Analyse B — Benutzerlöschung

### 3.1 Szenarien und Ist-Verhalten

| # | Szenario | Unterstützt? | Ist-Verhalten | Beleg |
|---|---|---|---|---|
| 1 | Löschung über MO-API | **NEIN** | Keine `DELETE`-Route (0 Treffer in `terraform/modules/api/main.tf`); keine Löschoperation im Handler | `api/main.tf`, `index.py` |
| 2 | Nutzer aus MANAGED Cognito entfernt | **NEIN (keine Automatik)** | Kein Trigger, kein Stream, kein Event. Bestellungen bleiben unverändert | `cognito/main.tf` (nur Pool/Client/Gruppe) |
| 3 | Nutzer aus EXTERNAL Cognito entfernt | **NEIN** | MO hat im ROOT-Repo keinen EXTERNAL-Modus; im generierten Modul nur Authorizer-Referenz, keine Nutzerverwaltung | `module_builder/builder.py` (EXTERNAL) |
| 4 | Consumer meldet Nutzerlöschung | **PARTIAL** | Nur interner Lambda-Invoke `privacy/erase` (`index.py:105-125`) mit Projekt-/Berechtigungs-/Secret-Prüfung — **nicht** über HTTP erreichbar | `index.py:101-125`, `order_service.py:101-124` |
| 5 | Nutzer weg, Bestellungen bleiben | **JA (implizit)** | Bestellungen bleiben dauerhaft; keine Erkennung, keine Frist, keine Bereinigung | Code + fehlendes TTL |

### 3.2 Was passiert heute mit Bestellungen bei Benutzerlöschung?

**Nichts.** Es gibt keine Verknüpfung (kein `subjectId` in der Praxis), keinen Trigger und
keine Frist. Ein `privacy/erase` löscht/anonymisiert nur, was über GSI2 gefunden wird —
also bei API-Orders **nichts**.

### 3.3 Vorhandene Bausteine (wiederverwendbar)

| Baustein | Status | Einschränkung |
|---|---|---|
| `erase_subject` mit `PREVIEW`/`EXECUTE`, `ERASE`/`ANONYMIZE`/`RETAIN` | IMPLEMENTED / VERIFIED (historisch) | findet nur GSI2-Items; verlangt explizite Policy |
| Auth-Boundary `_require_privacy_auth` | IMPLEMENTED / VERIFIED | Secret nur per Env (siehe Secret-Design) |
| `cognito-idp:ListUsers` (Backup-Rolle) | IMPLEMENTED | nur MANAGED-Pool, nur Backup-Lambda, `Resource: "*"` |
| `cognito_backup/restore.py` | IMPLEMENTED | Restore, kein Delete |
| `version`-basierte Bedingung im Erase | IMPLEMENTED | schützt vor Races |

### 3.4 Fehlende Funktionen (explizit)

- Kein `DELETE /orders/{id}` und keine Nutzer-Lösch-API.
- Kein Cognito-Trigger (Pre Sign-up/Post Confirmation/User Deleted) und keine EventBridge-Regel.
- Kein „subject → orders“-Backfill für Bestandsdaten.
- Keine Lösch-/Retention-Frist, kein Cleanup-Job, kein Audit-Trail für Löschungen.
- Keine Erkennung „Bestellung ohne existierenden Nutzer“ (kein Abgleich mit Cognito).

## 4. Analyse D — Status und Retention (State-Machine-Matrix)

### 4.1 Implementierte Status

`order_types.py:5-12`: `PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED`.
**`COMPLETED` und `FAILED` existieren als Bestell-Status NICHT** (`COMPLETED` erscheint nur
als *Operation*-Status im Erase-Ergebnis, `order_service.py:496-498`; `FAILED` nur als
Zähler `failedRecords`).

### 4.2 Übergangsmatrix (Code = `state_machine.py:5-12`)

| Von \ Nach | PENDING | CONFIRMED | PROCESSING | SHIPPED | DELIVERED | CANCELLED |
|---|---|---|---|---|---|---|
| PENDING | – (Selbstübergang verboten) | ✅ | ✗ | ✗ | ✗ | ✅ |
| CONFIRMED | ✗ | – | ✅ | ✗ | ✗ | ✅ |
| PROCESSING | ✗ | ✗ | – | ✅ | ✗ | ✗ |
| SHIPPED | ✗ | ✗ | ✗ | – | ✅ | ✗ |
| DELIVERED | ✗ | ✗ | ✗ | ✗ | – | ✗ |
| CANCELLED | ✗ | ✗ | ✗ | ✗ | ✗ | – |

Fachlich deckungsgleich mit `order-lifecycle/transition-rules.md` — **VERIFIED**.

### 4.3 Antworten auf die Analysefragen

| Status | Befund |
|---|---|
| `PENDING` | Keine Aufbewahrungsregel; verharrt unbegrenzt, wenn der SQS-Kick fehlschlägt (`index.py:145-147` loggt nur) |
| `CONFIRMED` | Keine Abschluss-/Archivierungsregel |
| `COMPLETED` | **nicht implementiert** (auch nicht in `ORDER_STATUSES`) |
| `CANCELLED` | Endzustand, **keine** Folgen: keine Frist, keine Anonymisierung, keine Benachrichtigung |
| `FAILED` | **nicht implementiert**; Worker-Fehler werden geloggt und die Nachricht als verarbeitet betrachtet (`return False`) → **kein Retry**, **keine DLQ** (`grep redrive|dead_letter` = 0) |

### 4.4 Risiken im Status-/Worker-Pfad

1. **Cancel-Race im Worker:** `sqs_handler.py:67-93` liest den Status, prüft `can_transition`
   und schreibt **ohne** `ConditionExpression`/Version. Wird die Bestellung zwischen Lesen
   und Schreiben storniert, kann `CANCELLED → CONFIRMED` geschrieben werden (ungültiger
   Zustand). **PARTIAL** (API-Pfad ist geschützt, Worker-Pfad nicht).
2. **`version` wird vom Worker nicht erhöht** → Optimistic Locking im API-Pfad verliert
   seine Aussagekraft, sobald der Worker schreibt.
3. **Kein DLQ/Retry** → verlorene Verarbeitung bleibt unbemerkt (nur Log).
4. **Fehlgeschlagener SQS-Kick** bei `POST /orders` → Bestellung bleibt `PENDING` ohne
   Fehlersignal an den Client (Response ist trotzdem 201).

### 4.5 Retention heute

- **Kein globales, benutzerbezogenes oder bestellbezogenes Feld.** Retention existiert
  ausschließlich als **Argument** des Erase-Aufrufs (`RETAIN`/`ERASE`/`ANONYMIZE`), ohne
  Frist und ohne Speicherung.
- Ein vom Consumer übergebener Retention-Wert kann **heute nicht** übernommen werden
  (API-Validator lehnt unbekannte Felder ab).

## 5. RIS-Kompatibilität (MO-Dokumentation)

| Vertrag | Ist-Zustand | Status |
|---|---|---|
| Orders-Service-Modul: 6 Inputs (`project_name`, `tags`, `monitoring_enabled`, `log_retention_days`, `lambda_execution_boundary`, `external_cognito`) | stabil seit RC3 | VERIFIED |
| Outputs (20: API/DDB/SQS/Lambda/IAM/Cognito) | stabil | VERIFIED |
| SQS-Worker-Vertrag (`{orderId,status,metadata.reason}`, `ord_*`, Status-Matrix, 400/404/409/500) | von RIS repliziert | VERIFIED |
| EXTERNAL-Cognito (nur generiertes Modul, JWT bleibt aktiv) | vorhanden | VERIFIED |
| Nutzer-/Mandantenidentifikation | MO: keine; RIS: `tenant_id` nur im RIS-Port, nicht in MO-Daten | **UNKNOWN/Befund** |
| Privacy-Schnittstellen | nur interner Invoke, keine HTTP-Route | VERIFIED |
| Consumer-Pin | RIS `1dbb0cb` = RC3-Code | VERIFIED (MO-Evidence) |

**Einschränkung:** RIS-Code wurde in P01 **nicht** erneut gelesen (kein Zugriff nötig/erlaubt);
Basis sind ausschließlich MO-Dokumentation und MO-Reports (P06). RIS-Repo unverändert.

## 6. Fehlende Funktionen (Gesamtliste)

1. Nutzerbezug (`subjectId`) aus JWT beim Anlegen.
2. `userId`/`ownerId`-Semantik (falls JWT-`sub` nicht ausreicht).
3. Lösch-/Retention-Felder und -Fristen.
4. Cleanup-/Orphan-Routine inkl. Dry-Run.
5. Cognito-Trigger bzw. Event-Anbindung (neue AWS-Ressource → ADR).
6. DLQ/Retry für den Worker.
7. Worker-Race-Schutz (Condition/Version).
8. Secret-Provisionierung (Secrets Manager).
9. Audit-Trail für Löschungen (wer/was/wann/Ergebnis).

## 7. Risiken (Gesamtbild)

| Risiko | Schwere | Anmerkung |
|---|---|---|
| DSGVO-Löschauftrag findet keine Orders (kein subjectId) | **hoch** | Rechtsrisiko, nicht nur Technik |
| Orphan-Cleanup löscht RIS-Orders fälschlich | **hoch** | RIS schreibt ohne `subjectId`, mit anderem `pk`-Muster |
| Worker überschreibt Cancel (Race) | mittel | Datenintegrität |
| Verlorene Worker-Nachrichten (kein DLQ) | mittel | Betriebsblindheit |
| Retention ohne Frist = unbegrenzte Speicherung | **hoch** | DSGVO |
| Secret im Env (Status quo) | mittel | siehe Secret-Design |
| Bestandsdaten ohne Frist | mittel | Migration nötig (separat) |

## 8. Teststrategie (für die Folge-Implementierung)

- **Contract-Tests:** `POST /orders` → Item enthält `subjectId`/`retentionUntil` (nach
  Freigabe), Validator lehnt weiterhin fremde Felder ab, Response unverändert.
- **Privacy-Tests:** Inspect/Export/Erase finden API-Orders nach Subject-Zuordnung;
  Erase mit `RETAIN` verändert nichts; PREVIEW mutiert nie.
- **Worker-Tests:** Race-Simulation (Statuswechsel zwischen Read/Write) muss mit
  Condition in beiden Pfaden scheitern (409/kein Write).
- **Retention-Tests:** Fristberechnung, TTL-Wert, Bestand ohne Feld bleibt unangetastet.
- **Cleanup-Tests:** Dry-Run idempotent, Fremd-/RIS-Daten unberührt, Abbruch mitten im
  Lauf wiederholbar.
- **RIS-Kompatibilität:** Input-/Output-Namen unverändert; Default-Plan ohne neue Ressourcen.

## 9. Akzeptanzkriterien (P01)

- [x] Alle genannten Felder mit Datei/Zeile belegt.
- [x] Fehlende Felder ausdrücklich als fehlend markiert (nicht „vermutet“).
- [x] Statusmatrix gegen Code und Fach-Doku abgeglichen.
- [x] Nutzerlöschung in allen 5 Szenarien bewertet.
- [x] Externe Schreibpfade (RIS) benannt und als Cleanup-Risiko markiert.
- [x] Keine Code-/AWS-Änderung, keine neuen Pflichtfelder vorgeschlagen.
