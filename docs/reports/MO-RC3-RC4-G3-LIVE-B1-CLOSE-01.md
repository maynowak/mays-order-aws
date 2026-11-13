# MO-RC3-RC4-G3-LIVE-B1-CLOSE-01

**Evidence Reconciliation & Identity-Test Preparation**

**Datum:** 2026-11-12
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD:** `6ac779b78e4259aad9b7e519a5ea5259cdc1fe96`
**Modus:** read-only Analyse, Dokumentation und Testvorbereitung;
keine AWS-Mutation, keine Cognito-Benutzererstellung, keine Lambda-Invocation,
kein API-Livetest, kein Terraform, kein Push/Merge.

```text
GSI3 Counter Contract:      CLOSED — MANIFEST ERROR
Foreign Identity Test:      READY FOR IDENTITY LIVE APPROVAL
Overall:                    READY FOR IDENTITY LIVE APPROVAL
```

Der historische B1-Lauf bleibt als `PARTIAL` dokumentiert. Der dort offene
GSI3-Counter-Nachweis ist jetzt eindeutig geklärt: `candidates=4` ist
vertragskonform; die Manifest-Erwartung `candidates=8` war falsch. Der
Foreign-Identity-Test ist ohne Infrastrukturänderung ausführbar vorbereitet,
aber noch **nicht** ausgeführt.

---

## 1. Git- und AWS-Baseline

### Git

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `6ac779b78e4259aad9b7e519a5ea5259cdc1fe96` |
| Working Tree vor Analyse | CLEAN |
| Working Tree nach Analyse | nur Dokumentation geändert, danach committed/CLEAN |

### AWS (read-only)

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| STS Account | `240571105849` |
| STS ARN | `arn:aws:iam::240571105849:user/Mayaws` |
| Region | `eu-central-1` |
| Teststack | `mays-orders-rc4-test` |
| API | `37fldhw7fi`, `https://37fldhw7fi.execute-api.eu-central-1.amazonaws.com` |
| Lambda Handler | `Active` / `Successful` / `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Lambda Worker | `Active` / `Successful` / derselbe CodeSha |
| DynamoDB | ACTIVE, `ItemCount=0`; GSI3 ACTIVE/KEYS_ONLY |
| Main Queue | `0 / 0` visible/in-flight |
| DLQ | `0 / 0` visible/in-flight |
| Cognito-Pool | `eu-central-1_OZ7TK51EK`, `mays-orders-rc4-test-users`, 0 User |
| Cognito-Client | `415t3lt2k1umrmoaibn4f302sn`, public, `ALLOW_USER_PASSWORD_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` |
| MFA | `OFF` |
| API-Authorizer | JWT, Audience = Client-ID, Issuer = Pool, Identity Source `Authorization` |
| Routen | `POST /orders`, `GET /orders`, `GET /orders/{orderId}`, `PATCH /orders/{orderId}/status`, alle JWT |

Keine AWS-Schreiboperation in diesem Task. Die Abfragen waren ausschließlich
`sts:GetCallerIdentity`, `lambda:GetFunctionConfiguration`,
`cognito-idp:Describe*`/`ListUsers`, `apigatewayv2:Get*`, `dynamodb:DescribeTable`
und `sqs:GetQueueAttributes`.

---

## 2. GSI3-Zählerdefinitionen

Quelle: `lambda/src/recovery.py`, Funktion `run_processing_recovery`.

| Feld | Definition | Code |
|---|---|---|
| `scanned` | Anzahl der aus GSI3 gelesenen Index-Treffer; wird pro Eintrag erhöht, bevor der Primärschlüssel aufgelöst wird. | `lambda/src/recovery.py:321-340` |
| `checked` | Anzahl der erfolgreichen `GetItem`-Rechecks auf dem Primär-Item. | `lambda/src/recovery.py:343-360` |
| `candidates` | Anzahl der **nach allen Filtern ausgewählten, gültigen Kandidaten**. Wird am Ende auf `len(selected)` gesetzt. | `lambda/src/recovery.py:397` |
| `sent` | Anzahl erfolgreicher SQS-Sendungen; wird nur nach erfolgreichem `send_message` erhöht. | `lambda/src/recovery.py:404-413` |
| `budgetExhausted` | Anzahl der Items, deren `processingAttempts >= MAX_PROCESSING_ATTEMPTS` ist. Kein globaler Scan-Abbruch. | `lambda/src/recovery.py:369-378` |
| `skipped` | Zähler je Skip-Grund (`cancelled`, `budget_exhausted`, `anonymized`, `not_running`, `lease_not_expired`, `order_missing`, `read_error`, `send_failed`, …). | `lambda/src/recovery.py:308-316`, `343-389` |
| `scan_limit_reached` | Separater Skip, wenn das harte Scan-Budget `max(limit*10, 100)` erreicht wird, bevor `limit` gültige Kandidaten gefunden wurden. | `lambda/src/recovery.py:398-400` |

### Inkrementierungsstellen

1. `report["scanned"] += 1` für jeden GSI3-Eintrag (`recovery.py:340`).
2. `report["checked"] += 1` erst nach erfolgreichem `GetItem` (`recovery.py:360`).
3. Skip-Filter laufen danach:
   - `processingState != "running"` → `not_running`
   - Lease nicht abgelaufen → `lease_not_expired`
   - `processingAttempts >= MAX` → `budgetExhausted += 1` + `budget_exhausted`
   - fehlende `subjectId` → `anonymized`
   - `status == CANCELLED` → `cancelled`
4. Nur wenn kein Filter greift, wird `(order_id, target_status)` an `selected`
   angehängt (`recovery.py:381-389`).
5. `candidates = len(selected)` (`recovery.py:397`).
6. `sent` wird pro erfolgreichem SQS-Send erhöht (`recovery.py:404-410`).

**Fachliche Bedeutung:** `candidates` ist keine Anzahl aller Index-Treffer und
keine Anzahl aller geprüften Items. Es ist die Anzahl der tatsächlich
ausgewählten, zustellbaren Recovery-Kandidaten.

---

## 3. Erklärung der Live-Evidence

B1-Run `g3b133a3dd52a0`, zehn Fixtures A/B/C/D/E/F/G/I/L/M.

### GSI3-Index

| Fixture | Index-Treffer? | Grund |
|---|---|---|
| A | ja | `CONFIRMED`, running, abgelaufener Claim |
| B | ja | `CONFIRMED`, running, abgelaufener Claim |
| C | nein | Lease noch aktiv (`claimed_ago=60s`, Cutoff 360s) |
| D | ja | `CONFIRMED`, running, aber Budget erschöpft |
| E | ja | `CANCELLED` |
| F | ja | keine `subjectId` (anonymisiert) |
| G | ja | `processingState=succeeded` |
| I | nein | keine GSI3-Attribute |
| L | ja | `SHIPPED`, running, abgelaufener Claim |
| M | ja | `PENDING`, running, abgelaufener Claim |

Ergebnis: **8 Index-Treffer** (A/B/D/E/F/G/L/M), daher `scanned=8`;
alle acht haben ein Primär-Item, daher `checked=8`.

### Filterung

| Fixture | Ergebnis | Zähler |
|---|---|---|
| A/B/L/M | ausgewählt | `candidates` +4 |
| D | Budget erschöpft | `budgetExhausted=1`, `skipped.budget_exhausted=1` |
| E | storniert | `skipped.cancelled=1` |
| F | anonymisiert | `skipped.anonymized=1` |
| G | nicht running | `skipped.not_running=1` |

Damit: `candidates=4`, `sent=4`. Die vier Sends waren A/B/L/M; der Worker
bestätigte A/B/L als idempotent und führte M einmalig `PENDING→CONFIRMED`
(Version 3). Der zweite Scan blieb status-/versionsstabil.

### `budgetExhausted=1`

D hatte `processingAttempts=2`; `MAX_PROCESSING_ATTEMPTS` ist 2. Der Zähler
markiert genau diesen Kandidaten. Der Report bleibt `COMPLETED`; es handelt
sich **nicht** um einen globalen Scan-Abbruch. Ein globales Scan-Limit würde
separat als `scan_limit_reached` erscheinen.

Lokale Regression bestätigt die Semantik:

```text
lambda/tests/test_processing_recovery.py
27 Tests, PASS
- test_budget_exhausted_is_skipped_and_counted
- test_skipped_entries_do_not_starve_valid_candidate
- test_limit_bounds_run
```

Der Starvation-Test erwartet ausdrücklich `candidates=1`, obwohl fünf
Index-Treffer geprüft wurden. Das ist dieselbe Semantik wie im Live-Lauf.

---

## 4. Manifestabweichung und Entscheidung

### Befund

Das G3-EXT-Manifest erwartete in `G3X-GSI3-RUN1-04`:

```text
8 candidates, 4 sent
```

Der deployed G3-FIX-Code liefert:

```text
scanned=8, checked=8, candidates=4, sent=4
```

### Entscheidung: **Fall A — Manifestfehler nachgewiesen**

Begründung:

- `candidates` ist im Produktcode eindeutig `len(selected)`.
- `selected` enthält nur gültige Kandidaten nach allen Skips.
- `scanned=8` zählt die Index-Treffer; davon sind vier Skips.
- Die Live-Werte stimmen mit Code, lokalen Tests und den dokumentierten
  Skip-Zählern überein.
- Es gibt keinen Hinweis auf einen Produktdefekt: Sends, Skips, Status und
  Duplikatverhalten sind korrekt.

Die Manifest-Erwartung verwechselte Index-Treffer (`scanned`) mit
ausgewählten Kandidaten (`candidates`). Die Manifest-Zeilen wurden korrigiert:

- `G3X-GSI3-PRE-01`: CodeSha auf den tatsächlich deployed G3-FIX-Hash
  `FYTu…` aktualisiert (vorher veraltet `vW8n…`).
- `G3X-GSI3-IDX-03`: genau 8 Index-Treffer, davon 4 auswählbare Kandidaten.
- `G3X-GSI3-RUN1-04`: `scanned=8`, `checked=8`, `candidates=4`, `sent=4`.
- Zählersemantik als verbindlicher Hinweis ergänzt.

Die ursprüngliche B1-Live-Evidence bleibt unverändert. Es wurde kein
Produktcode geändert.

---

## 5. Foreign-Identity-Testplan (nicht ausgeführt)

### Ziel

Nachweisen, dass eine Order ausschließlich über die autorisierte
Owner-Identität (`JWT.sub`) und den passenden Consumer erreichbar ist.
Identität B darf weder lesen noch schreiben und erhält keine Orderdaten.

### Voraussetzungen

- AWS-Profil `mayaws`, Account `240571105849`, Region `eu-central-1`.
- Teststack `mays-orders-rc4-test`; Lambda-CodeSha beider Funktionen
  `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=`.
- Leerer Ausgangszustand: Tabelle 0, GSI3 0, Main Queue/DLQ 0/0,
  Cognito-Pool 0 User.
- Bestehender Pool `eu-central-1_OZ7TK51EK` und Client
  `415t3lt2k1umrmoaibn4f302sn`; `ALLOW_USER_PASSWORD_AUTH` ist aktiv.
- JWT-Authorizer mit Audience = Client-ID und Pool-Issuer aktiv.
- Keine Cognito-Pool-/Client-Konfigurationsänderung, kein zweiter Client,
  keine IAM-Rollenänderung, keine Terraform-Änderung.

### Testidentitäten

Zwei synthetische Benutzer im bestehenden Testpool, beide mit demselben
App-Client:

```text
A: g3b1id<run>-a@example.com
B: g3b1id<run>-b@example.com
```

- Passwörter werden zufällig erzeugt, nur im Prozessspeicher gehalten und
  niemals in Report, Auditlog oder Shell-Historie geschrieben.
- `AdminCreateUser` mit `MessageAction=SUPPRESS`, danach
  `AdminSetUserPassword(Permanent=True)`; optional Gruppe `staff`.
- Login über `InitiateAuth(USER_PASSWORD_AUTH)`; Access Token nur im Speicher.
- `sub` aus dem Access Token dekodieren und asserten: `sub(A) != sub(B)`.
- Beide haben denselben `consumerId` (gleicher Issuer + Client); getestet wird
  damit **Owner-Isolation**, nicht Cross-Consumer-Isolation.

### Ablauf

| Schritt | Aktion | Erwartung |
|---|---|---|
| 1 | Preflight read-only | Baseline 0/0/0, CodeSha korrekt |
| 2 | A und B anlegen, Passwörter setzen | beide `Enabled`/bestätigt |
| 3 | A und B authentifizieren | beide Access Token, `sub` verschieden |
| 4 | A `POST /orders` mit synthetischem Body | **201**, Status `PENDING`, `orderId` |
| 5 | A `GET /orders/{id}` | **200**, korrekte `orderId`/Marker |
| 6 | B `GET /orders/{id}` | **404 `ORDER_NOT_FOUND`**, keine Orderfelder |
| 7 | B `PATCH /orders/{id}/status` auf `CANCELLED` | **404**, keine Änderung |
| 8 | A `GET /orders/{id}` erneut | **200**, Status/Version unverändert |
| 9 | B `GET /orders` | **200**, A-Order nicht enthalten (bei B ohne eigene Order: `count=0`) |
| 10 | A `GET /orders` | **200**, A-Order enthalten |
| 11 | Cleanup | Order(s) exakt löschen, User A/B löschen, Baseline 0 |

### Isolation Assertions

- B-Response auf A-Order enthält **kein** `orderId`, `customer`, `items`,
  `totalAmount`, `status` oder `subjectId`.
- B-Response ist die generische 404-Form (keine Existenzoffenlegung).
- B-PATCH verändert weder Status noch Version; A liest danach unverändert.
- B-Liste enthält keine A-Order.
- A-Liste enthält die eigene Order.
- Keine fremde Order, kein fremder User und keine fremde Queue-Nachricht wird
  verändert.

### Cleanup

1. A-Order über exakten Key `pk=ord_<orderId>`, `sk=#ORDER` löschen;
   `subjectId` muss exakt `sub(A)` sein (Owner-Guard).
2. Falls B eine eigene Order erstellt: analog mit `sub(B)`.
3. Benutzer A und B über `AdminDeleteUser` löschen.
4. Exakte Nachweise: Tabelle 0, GSI3 0, Main Queue/DLQ 0/0, Pool-User 0.
5. Kein `PurgeQueue`, kein Massenlöschen, keine fremden Daten.

Der bestehende `tests/e2e_harness.py` kann ohne Änderung genutzt werden:
`ApiClient` pro Token, `LiveCleanupBackend` pro `subject_id`. Es ist **keine**
Test-Harness-Codeänderung erforderlich.

### Abbruchbedingungen

- Account/Region/Stack/Codesha weicht ab.
- Baseline nicht 0 oder fremde User/Orders/Queues sichtbar.
- `AdminCreateUser`/`AdminSetUserPassword`/`InitiateAuth` schlägt fehl.
- A-POST nicht 201 oder A-GET nicht 200.
- B-GET nicht 404 oder B-Response enthält Orderdaten.
- B-PATCH nicht 404 oder A-Status/Version ändert sich.
- B-Liste enthält A-Order.
- Cleanup-Ownership stimmt nicht oder ein Testitem ist nicht eindeutig
  zuordenbar.
- Unerwartete AWS-/IAM-/Cognito-Konfigurationsanforderung.

Bei Abbruch: keine automatische Wiederholung; Testdaten nach den
Cleanup-Regeln bestmöglich exakt entfernen und `BLOCKED`/`FAILED` berichten.

### IAM-/Cognito-Voraussetzungen

Erforderlich sind ausschließlich Cognito-Admin-Datenoperationen:

```text
cognito-idp:AdminCreateUser
cognito-idp:AdminSetUserPassword
cognito-idp:AdminDeleteUser
optional: cognito-idp:AdminAddUserToGroup (staff)
```

`InitiateAuth` ist eine öffentliche Client-Operation und keine IAM-Berechtigung
der Testidentität. Die API nutzt weiterhin den bestehenden JWT-Authorizer.

**Keine** Änderung an Pool, Client, Auth-Flows, Audience, Issuer, Rollen oder
Terraform erforderlich. Ein Cross-Consumer-Test (zweiter Client/Pool) wäre
dagegen **BLOCKED — CONFIGURATION REQUIRED** und ist nicht Teil dieses Plans.

### Erforderlicher Freigabeumfang für die spätere Ausführung

- Zwei synthetische Cognito-Benutzer anlegen/authentifizieren/löschen.
- Eine synthetische Order als A erstellen; optional eine als B.
- Gezielte `GET`/`PATCH`-Versuche von B gegen die A-Order.
- Exakter Owner-verifizierter Cleanup der Testorders und User.
- Read-only Preflight/Postflight.

Nicht enthalten: Privacy, DLQ, Recovery, Lambda-Invoke, Terraform, Pipeline,
Produktion, Push/Merge.

---

## 6. IAM-/Cognito-Voraussetzungsbewertung

| Frage | Bewertung |
|---|---|
| Test ohne Infrastrukturänderungen möglich? | **JA** — bestehender Pool/Client/Auth-Flow/Autorizer |
| Zusätzliche Cognito-Konfiguration nötig? | **NEIN** |
| Zusätzliche IAM-Rolle nötig? | **NEIN** für den bestehenden Operator; Admin-User-CRUD muss vorhanden sein |
| Zweiter App-Client nötig? | **NEIN** für Owner-Isolation; **JA** nur für Cross-Consumer (nicht beauftragt) |
| Produktive Identitäten? | **NEIN** — ausschließlich synthetische Testbenutzer |
| Secrets/Tokens im Report? | **NEIN** — nur im Prozessspeicher |

Status: **READY FOR IDENTITY LIVE APPROVAL**.

---

## 7. Offene Risiken

- Der Identitätstest ist vorbereitet, aber **nicht ausgeführt**; es gibt keinen
  neuen Live-Nachweis.
- Der Test prüft Owner-Isolation innerhalb desselben Consumers. Cross-Consumer-
  Isolation bleibt ohne zweiten Client/Pool `BLOCKED — CONFIGURATION REQUIRED`.
- `AdminCreateUser`/`AdminDeleteUser` sind Datenoperationen am Testpool; sie
  benötigen die spätere ausdrückliche Freigabe.
- `ItemCount` ist eventual-consistent; Cleanup wird zusätzlich über exakte
  Keys und gezielte Reads verifiziert.
- Der historische B1-Bericht bleibt `PARTIAL`; der GSI3-Teil ist mit dieser
  Reconciliation geschlossen, der Identity-Teil bleibt offen.
- Privacy-B2, Processing-Aktivierung, API-Idempotenz, P00 und SEC-06 bleiben
  unverändert offen.
- Keine G4-Freigabe.

---

## 8. Ergebnisstatus (getrennt)

```text
GSI3 Counter Contract:      CLOSED — MANIFEST ERROR
GSI3 Product Defect:        NONE FOUND
budgetExhausted=1:          EXPECTED — per-candidate exhausted attempts
B1 Candidate Evidence:      RECONCILED — candidates=4 is contract-conformant
Foreign Identity Test:      READY FOR IDENTITY LIVE APPROVAL (NOT EXECUTED)
Cross-Consumer Isolation:   BLOCKED — CONFIGURATION REQUIRED
Overall:                    READY FOR IDENTITY LIVE APPROVAL
```

---

## 9. Änderungen

| Datei | Änderung |
|---|---|
| `docs/reports/MO-RC3-RC4-G3-EXT-LIVE-TEST-MANIFEST.md` | GSI3-Erwartung korrigiert; Zählersemantik dokumentiert |
| `docs/reports/MO-RC3-RC4-G3-LIVE-B1-CLOSE-01.md` | dieser Bericht |
| `docs/AI_AUDITLOG.md` | Index-Eintrag ergänzt |

Keine Produkt-, Test-Harness-, Terraform-, IAM-, Cognito- oder AWS-Änderung.

---

## 10. Auditlog-Nachweis

Vorgesehener Auditlog-Eintrag:

```text
MO-RC3-RC4-G3-LIVE-B1-CLOSE-01 → docs/reports/MO-RC3-RC4-G3-LIVE-B1-CLOSE-01.md
(read-only Reconciliation: GSI3 candidates=len(selected), scanned=8/checked=8/
candidates=4/sent=4; budgetExhausted=1 per-candidate; Manifest-Erwartung 8
war falsch und wurde auf 4 korrigiert; Foreign-Identity-Testplan mit zwei
synthetischen Usern, 201/200/404/404/200, Owner- und Listen-Isolation,
exaktem Cleanup; keine AWS-Mutation, keine User-Erstellung, keine Invocation,
kein Terraform, kein Push)
```

---

## 11. Resume-Point

Nächster zulässiger Schritt nach separater Freigabe:

```text
IDENTITY LIVE TEST (A/B) — create two synthetic Cognito users, create one
synthetic order as A, verify A 200 / B 404 / B PATCH 404 / A unchanged,
cleanup orders and both users, verify 0/0/0.
```

**STOP — keine automatische AWS-Live-Ausführung. Keine G4-Freigabe.
Keine Privacy-B2-Ausführung. Keine DLQ-/Recovery-Wiederholung.**

---

## 12. Commit-SHA und Working-Tree-Status

| Feld | Wert |
|---|---|
| Dokumentations-Commit | `ff967a5bd1c678ad0b039e769056f5981bc562a5` |
| Working Tree nach Commit | CLEAN |

Es wurden nur die drei Dokumentationsdateien geändert: Manifest,
Close-Bericht, Auditlog. Kein Produktcode, kein Test-Harness, kein Terraform.
