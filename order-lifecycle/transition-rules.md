# State Transition Rules — May's Orders

## 1. Transition Matrix (vollständig)

`✓` = erlaubt · `✗` = ungültig · `–` = nicht sinnvoll (gleicher Zustand)

| Von \ Nach | PENDING | CONFIRMED | PROCESSING | SHIPPED | DELIVERED | CANCELLED |
|------------|:-------:|:---------:|:----------:|:-------:|:---------:|:---------:|
| PENDING    | –        | ✓         | ✗          | ✗       | ✗         | ✓         |
| CONFIRMED  | ✗        | –         | ✓          | ✗       | ✗         | ✓         |
| PROCESSING | ✗        | ✗         | –          | ✓       | ✗         | ✗         |
| SHIPPED    | ✗        | ✗         | ✗          | –       | ✓         | ✗         |
| DELIVERED  | ✗        | ✗         | ✗          | ✗       | –         | ✗         |
| CANCELLED  | ✗        | ✗         | ✗          | ✗       | ✗         | –         |

## 2. Explizit getestete Fälle (Test-Spezifikation)

| # | Ausgangszustand | Zielzustand | Erwartetes Ergebnis | HTTP |
|---|-----------------|-------------|---------------------|------|
| 1 | PENDING | CONFIRMED | Erfolg | 200 |
| 2 | PENDING | CANCELLED | Erfolg | 200 |
| 3 | CONFIRMED | PROCESSING | Erfolg | 200 |
| 4 | CONFIRMED | CANCELLED | Erfolg | 200 |
| 5 | PROCESSING | SHIPPED | Erfolg | 200 |
| 6 | SHIPPED | DELIVERED | Erfolg | 200 |
| 7 | PENDING | PROCESSING | Ungültig → Fehler | 409 |
| 8 | PENDING | SHIPPED | Ungültig → Fehler | 409 |
| 9 | PENDING | DELIVERED | Ungültig → Fehler | 409 |
| 10 | CONFIRMED | DELIVERED | Ungültig → Fehler | 409 |
| 11 | PROCESSING | CANCELLED | Ungültig → Fehler | 409 |
| 12 | SHIPPED | CANCELLED | Ungültig → Fehler | 409 |
| 13 | DELIVERED | (beliebig) | Ungültig → Fehler | 409 |
| 14 | CANCELLED | (beliebig) | Ungültig → Fehler | 409 |
| 15 | (nicht vorhandene ID) | – | Fehler | 404 |
| 16 | ungültiger Status-String | – | Fehler | 400 |
| 17 | fehlende Pflichtfelder (POST) | – | Fehler | 400 |
| 18 | unbekanntes Feld (POST) | – | Fehler | 400 |

## 3. Verhalten der Übergänge

### 3.1 Erfolgsfall (gültiger Übergang)

- Anwendung liest aktuellen Status, validiert die Transition in der State Machine,
  führt einen **Conditional Write** durch (`attribute_exists` + `status = currentStatus`).
- Antwort: HTTP 200 mit dem aktualisierten Order-Objekt.

### 3.2 Ungültiger Übergang

- Transition nicht in der Transition-Tabelle → **HTTP 409 Conflict** mit Fehlercode
  `INVALID_TRANSITION`, inkl. aktuellem und gewünschtem Status.

### 3.3 Nicht existierende Order

- Order-ID nicht vorhanden → **HTTP 404 Not Found** mit Fehlercode `ORDER_NOT_FOUND`.

### 3.4 Ungültiger Statuswert / fehlende Felder

- Validierungsfehler → **HTTP 400 Bad Request** mit Fehlercode `VALIDATION_ERROR`.

## 4. Konkurrierende Updates (Race Condition)

**Szenario:** User A setzt `PROCESSING`, User B setzt gleichzeitig `CANCELLED` — beide
basieren auf dem aktuellen Stand `CONFIRMED`.

| Schritt | User A | User B | Zustand |
|---------|--------|--------|---------|
| 1 | liest `CONFIRMED` | liest `CONFIRMED` | CONFIRMED |
| 2 | schreibt CONDITIONAL `status = CONFIRMED` → `PROCESSING` | – | PROCESSING |
| 3 | – | schreibt CONDITIONAL `status = CONFIRMED` → `CANCELLED` | **BEDINGUNG FEHLT** → Fehler 409 |

**Mechanismus:** DynamoDB **Conditional Write** auf `attribute_exists(PK) AND status = <erwarteterAltStatus>`.
DynamoDB führt den Write atomar aus; nur ein Update kann gewinnen. Der Verlierer erhält
`ConditionalCheckFailedException` → Anwendung antwortet `409 CONFLICTED_UPDATE`.
Damit ist ein inkonsistenter Endzustand (z. B. `CANCELLED` von `PROCESSING` aus) ausgeschlossen.

**Trade-off:** Alternative wäre Optimistic Locking via Version-Number. Der Status-basierte
Conditional Check ist einfacher und deckt das reale Szenario ab; eine Versionsspalte kann
später als Verschärfung ergänzt werden (offen, dokumentiert in Woche 3).

## 5. Idempotenz

- Wiederholter Übergang auf denselben Zielzustand wird in Woche 3 final definiert.
  Vorab-Definition: **Fehler 409** (kein No-Op), damit Semantik eindeutig und testbar ist —
  wird mit Unit-Test verifiziert und ggf. angepasst.