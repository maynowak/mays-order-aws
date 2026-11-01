# MO-RC4-P02B-PRIVACY-ISOLATION

**Consumer-Isolation der Privacy-Funktionen: Befund, Umsetzung, Grenzen**

**Datum:** 2026-11-01
**Typ:** Analyse + additive, nur einschränkende Implementierung
**Kernbefund:** GSI2 isoliert **keine** Consumer — die Isolation ist heute
**deploymentweit** (eine Tabelle = ein Projekt = ein Cognito-Pool). Ein optionaler
Scope-Filter wurde ergänzt; echte Mehr-Consumer-Isolation bleibt **BLOCKED**.

---

## 1. Ausgangsstruktur (unverändert)

```text
item:
  pk      = "ord_<id>"
  sk      = "#ORDER"
  gsi2pk  = "SUBJECT#<subjectId>"      ← Privacy-Partition
  gsi2sk  = "ord_<id>#<createdAt>"
```

`privacy/inspect`, `/export`, `/erase` fragen ausschließlich
`gsi2pk = SUBJECT#<subjectId>` ab (`order_service.py`).

## 2. Kollisionsanalyse

| Szenario | Kollision? | Erklärung |
|---|---|---|
| Zwei Benutzer **eines** Pools, gleiche ID | unmöglich | `sub` ist pro Pool eindeutig |
| Zwei **verschiedene** Consumer, gleiche Owner-ID | **JA, strukturell möglich** | `SUBJECT#<id>` enthält keinen Consumer |
| Gleiche ID, unterschiedlicher Owner-Typ (user/agent) | **JA** | Typ ist nicht Teil des Partitionsschlüssels |
| RIS-`tenant_id`/`sub` im MO-`subjectId` | **JA** | fremder Namensraum im gleichen Schlüssel |

**Bewertung:** In der heutigen Architektur ist je Deployment genau ein Consumer aktiv
(eigener Cognito-Pool, eigene Tabelle, eigener Projektname). Damit ist die
**Deployment-Trennung** wirksam — innerhalb einer Tabelle aber **keine** Consumer-Isolation
auf Datenebene. Sobald ein zweiter Consumer dieselbe Tabelle nutzt (z. B. RIS-Direktschreiben
mit fremden IDs), wäre die Trennung nicht mehr gegeben.

## 3. Umgesetzt: optionaler Consumer-Scope (nur einschränkend)

### 3.1 Verhalten

| Aufruf-Kontext | Ergebnis |
|---|---|
| ohne `consumerId` (heute, alle bestehenden Aufrufer) | **exakt wie bisher** — alle Items des Subjects |
| mit `consumerId = X` | nur Items mit `consumerId == X`; Items mit anderem Consumer **und** Legacy-Items (ohne `consumerId`) werden **nicht** zurückgegeben/gelöscht |

Erase zählt übersprungene Datensätze in `limitations`
(`"N record(s) outside consumer scope were not touched"`).

### 3.2 Warum Legacy-Items ausgeschlossen werden

Ein Item ohne `consumerId` lässt keine Aussage über seinen Consumer zu. Es einem
bestimmten Consumer zuzuschlagen wäre eine **erfundene** Zuordnung. Deshalb: bei
gesetztem Scope nur exakt passende Items.

### 3.3 Was sich **nicht** ändert

- Keine Änderung an GSI2, keine Reindexierung, keine neue Tabelle.
- Keine Erweiterung von Zugriffsrechten (der Filter kann nur weniger zeigen).
- Bestehende Aufrufer (ohne Scope) sehen unverändert alle Daten ihres Deployments.

## 4. Grenzen (bewusst)

| Grenze | Konsequenz |
|---|---|
| Scope wirkt **nach** der GSI2-Query | bei sehr vielen Fremd-Items entstehen unnötige Reads (Kosten), keine Sicherheitslücke |
| Kein GSI2-Partitionswechsel | echte Mehr-Consumer-Trennung auf Indexebene nicht erreicht |
| Scope ist **opt-in** | wer ihn nicht setzt, erhält das alte Verhalten — kein stiller Bruch, aber auch kein Zwang |
| Legacy-Items ohne Consumer | bei gesetztem Scope unsichtbar (fail-closed) |
| RIS-Items (kein `subjectId`) | von Privacy ohnehin nicht gefunden |

## 5. Migrations-/Abfrageentwurf (NICHT implementiert)

Falls echte Mehr-Consumer-Isolation nötig wird:

### Variante A — Composite-Partition (empfohlen, falls nötig)

```text
gsi2pk = "SUBJECT#<consumerId>#<ownerId>"
```

- Neue Items: composite; Legacy bleibt `SUBJECT#<ownerId>`.
- Abfrage müsste **zwei** Partitionen lesen (composite + legacy) — nur für den
  Standard-Consumer, der die Legacy-Daten besitzt.
- **Migration:** kein Reindex nötig (Legacy bleibt lesbar), aber Privacy-Aufrufer
  brauchen den Consumer im Kontext (Vertrag).
- **Risiko:** Doppelabfrage, längere Schlüssel (DynamoDB-Limit 2048 Byte — unkritisch).

### Variante B — separater GSI3 (`privacypk`)

- Neuer Index, nur für neue Items befüllt; Legacy über GSI2.
- **Kosten:** zusätzlicher Index, doppelte Schreiblast.
- Saubere Trennung ohne Semantikänderung an GSI2.

### Variante C — Consumer je Deployment (Status quo, empfohlen für RC4)

- Ein Consumer pro Tabelle bleibt Regel; Scope-Filter dient als Schutznetz.
- Kein Migrationsbedarf.

**Entscheidung:** Für RC4 bleibt **C**; A/B sind dokumentiert und **nicht** aktiviert
(keine GSI-Änderung ohne Freigabe, keine Reindexierung, keine Migration).

## 6. Privacy-Funktionen im Detail

| Funktion | Mit Scope | Ohne Scope |
|---|---|---|
| `inspect` | gefilterte Referenzen; Pagination vollständig | unverändert (alle Seiten) |
| `export` | nur passende Items im Export | unverändert |
| `erase` (PREVIEW) | Zählung nur in-scope | unverändert |
| `erase` (EXECUTE) | löscht/anonymisiert nur in-scope; Fremd-Items unberührt (Test) | unverändert |
| Auth-Boundary | unverändert (Projekt/Flag/Secret) | unverändert |

## 7. Tests

| Test | Aussage |
|---|---|
| `test_inspect_without_scope_returns_all` | Rückwärtskompatibilität |
| `test_inspect_with_scope_returns_only_matching_consumer` | Isolation |
| `test_export_with_scope_hides_other_consumer_and_legacy` | keine Vermischung, kein `consumerId` im Export |
| `test_erase_with_scope_does_not_touch_foreign_consumer` | fremde Items bleiben unangetastet + Hinweis in `limitations` |
| `test_erase_without_scope_keeps_previous_behavior` | keine Verhaltensänderung ohne Scope |
| `test_scope_excludes_other_consumers_and_legacy` | reine Funktion, fail-closed |
| `test_status_update_does_not_touch_identity_fields` | parallele Statusupdates verändern die Bindung nicht |
| bestehende `TestPrivacyConsistency` (P02) | unverändert grün |

## 8. Offene Punkte

| ID | Frage | Status |
|---|---|---|
| V-4 | Wird `consumerId` dauerhaft Privacy-Filter (Scope verpflichtend)? | **offen** — heute opt-in |
| V-7 | Composite-Partition (A) oder GSI3 (B) bei Mehr-Consumer-Bedarf? | **offen**, nicht implementiert |
| V-8 | Sollen Legacy-Items bei gesetztem Scope sichtbar bleiben (nur Standard-Consumer)? | **offen**, aktuell nein |
| — | Migration/Reindexierung | **nicht durchgeführt**, nicht nötig für RC4 |

## 9. Akzeptanzkriterien

- [x] GSI2 unverändert, keine Reindexierung, keine neue Tabelle.
- [x] Keine Ausweitung bestehender Privacy-Rechte.
- [x] Keine stille Vermischung von Legacy- und neuen Identitätsräumen.
- [x] Consumer-Isolation wirkt, wo sie ohne Vertrags-/Datenmigration sicher ist.
- [x] Echte Mehr-Consumer-Isolation ausdrücklich **BLOCKED** mit Migrationsentwurf.
