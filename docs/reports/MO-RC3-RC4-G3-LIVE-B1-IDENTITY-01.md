# MO-RC3-RC4-G3-LIVE-B1-IDENTITY-01

**Controlled Foreign-Identity Live E2E**

**Datum:** 2026-11-13
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Lauf:** `ecb75741d95baa2b5911625de058ec1b21d62dc3`
**Modus:** autorisierter Live-Test ausschließlich im RC4-Teststack;
keine Privacy-, DLQ-, Recovery- oder Kompatibilitätswiederholung;
keine Terraform-/IAM-/Cognito-Konfigurationsänderung; kein Push/Merge.

```text
IDENTITY LIVE VERIFIED
```

Alle sechs verpflichtenden Identitätstests sind PASS. Es gab keine
Fremddatenoffenlegung, keinen unzulässigen Write und keine Status-/Versions-
änderung durch Identity B. Der Cleanup ist vollständig nachgewiesen.

---

## 1. Run-ID und Baseline

| Feld | Wert |
|---|---|
| Run-ID | `g3b1ide89e712c67` |
| Git-Branch | `test/mo-rc4-testsuite-hardening-10a` |
| Git-HEAD vor Lauf | `ecb75741d95baa2b5911625de058ec1b21d62dc3` |
| Working Tree vor Lauf | CLEAN |
| AWS-Profil | `mayaws` |
| AWS-Account | `240571105849` |
| Region | `eu-central-1` |
| Teststack | `mays-orders-rc4-test` |
| API | `37fldhw7fi` |
| Handler | `mays-orders-rc4-test-handler` |
| Worker | `mays-orders-rc4-test-sqs-worker` |
| CodeSha256 Handler | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| CodeSha256 Worker | derselbe Hash |

---

## 2. Preflight

Read-only vor jeder Mutation:

| Prüfung | Ergebnis |
|---|---|
| STS Account | `240571105849` — PASS |
| Region | `eu-central-1` — PASS |
| Handler `State` / `LastUpdateStatus` | `Active` / `Successful` — PASS |
| Worker `State` / `LastUpdateStatus` | `Active` / `Successful` — PASS |
| CodeSha256 beide | Baseline-Hash — PASS |
| DynamoDB-Tabelle | ACTIVE, `ItemCount=0` — PASS |
| GSI3 `PROCESSING#RUNNING` | Count 0 — PASS |
| Main Queue | 0 visible / 0 in-flight — PASS |
| DLQ | 0 visible / 0 in-flight — PASS |
| Cognito-Testpool | `eu-central-1_OZ7TK51EK`, 0 User — PASS |
| Cognito-App-Client | `415t3lt2k1umrmoaibn4f302sn`, public, USER_PASSWORD_AUTH + Refresh — PASS |
| API-Authorizer | JWT, Audience = Client-ID, Pool-Issuer, `Authorization` — PASS |
| Pipeline-/Deployment-Lage | `directAWSGit…` Deploy `Stopped`; keine neue Lambda-Mutation; LastModified unverändert — PASS |

Der dokumentierte Cleanup-Pfad war ausführbar: exakter DDB-Key mit
Owner-`subjectId`-Guard, anschließend gezieltes `GetItem`, danach
`AdminDeleteUser`.

---

## 3. Cognito-Testkonfiguration und Identitätsnachweise

Es wurden genau zwei synthetische Benutzer im bestehenden Testpool angelegt.
Keine Pool-/Client-/Auth-Flow-Konfiguration wurde geändert.

| Identity | Testbenutzer | Verifizierte `sub` | Funktion |
|---|---|---|---|
| A | `g3b1ide89e712c67-a@example.com` | `f3e4c812-30d1-7077-7a6a-c7a96be85e4b` | Owner |
| B | `g3b1ide89e712c67-b@example.com` | `f304c8a2-80f1-70e6-dcf1-3301b61c1480` | Foreign User |

- Beide wurden über denselben App-Client mit `USER_PASSWORD_AUTH`
  authentifiziert.
- `sub(A) != sub(B)` — PASS.
- Beide haben denselben Consumer:
  `cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OZ7TK51EK#415t3lt2k1umrmoaibn4f302sn`.
- Damit wurde **Owner-Isolation innerhalb desselben Consumers** getestet,
  nicht Cross-Consumer-Isolation.
- Passwörter und Access Tokens wurden nur im Prozessspeicher gehalten und
  nicht in Report, Auditlog, Git oder Shell-Historie geschrieben.

---

## 4. Testfälle

### ID-01 — Owner Create

Identity A: `POST /orders` mit synthetischem Body, `orderType=generic`.

```text
HTTP 201
orderId = ord_6dac882b1e52a478db3f7583
```

- Order-ID serverseitig erzeugt, Format `ord_` + Hex — PASS.
- Persistierte Owner-Bindung: `subjectId = sub(A)` — PASS.
- Persistierter Consumer: `consumerId` = verifizierter Consumer — PASS.
- Keine Owner-Angabe aus dem Request-Body.

### ID-02 — Owner Read

Identity A: `GET /orders/ord_6dac882b1e52a478db3f7583`.

```text
HTTP 200
status = CONFIRMED
```

- `orderId` korrekt — PASS.
- Status nach Worker-Übergang `CONFIRMED` — PASS.
- DDB-Direktprüfung: `status=CONFIRMED`, `version=2` — PASS.
- `subjectId` und `consumerId` stimmen mit Identity A überein — PASS.

### ID-03 — Foreign Read

Identity B: `GET /orders/ord_6dac882b1e52a478db3f7583`.

```text
HTTP 404
error.code = ORDER_NOT_FOUND
```

- Kein `orderId`-Feld, kein `customer`, keine `items`, kein `totalAmount`,
  kein `status` im Response-Body — PASS.
- Response enthält ausschließlich den generischen Fehler; die Orderdaten
  werden nicht offengelegt — PASS.
- Ein `403` wurde nicht akzeptiert; der Vertrag verlangt `404` — PASS.

### ID-04 — Foreign PATCH

Identity B versuchte die im Vertrag gültige Transition
`CONFIRMED → PROCESSING` an der Order von A.

```text
HTTP 404
error.code = ORDER_NOT_FOUND
status_after = CONFIRMED
version_after = 2
```

- Keine Statusänderung — PASS.
- Keine Versionserhöhung (`2` vor und nach dem Versuch) — PASS.
- Keine Orderdaten im Response — PASS.
- Der Fremdversuch wurde vor jeder Transition geprüft und abgewiesen.

### ID-05 — Foreign List

Identity B: `GET /orders`.

```text
HTTP 200
count = 0
orders = []
```

- Order von A nicht enthalten — PASS.
- Keine Daten von Identity A — PASS.
- Keine fremde Order sichtbar — PASS.

### ID-06 — Owner Integrity

Identity A: erneutes `GET /orders/ord_6dac882b1e52a478db3f7583`.

```text
HTTP 200
api_status = CONFIRMED
db_status = CONFIRMED
db_version = 2
version_unchanged = true
```

- Order weiterhin vorhanden — PASS.
- Status unverändert — PASS.
- Version unverändert — PASS.
- Owner-Bindung unverändert — PASS.

---

## 5. Isolation Assertions

| Assertion | Ergebnis |
|---|---|
| A kann eigene Order erstellen | PASS |
| A kann eigene Order lesen | PASS |
| B erhält auf A-Order `404 ORDER_NOT_FOUND` | PASS |
| B erhält keine Orderfelder | PASS |
| B kann A-Order nicht per PATCH ändern | PASS |
| B-PATCH verändert Status nicht | PASS |
| B-PATCH erhöht Version nicht | PASS |
| B-Liste enthält A-Order nicht | PASS |
| A-Order nach Fremdversuchen unverändert | PASS |
| Keine Fremddatenoffenlegung | PASS |
| Keine unzulässigen Writes | PASS |

Es wurde kein `403` als Ersatz für den vertraglichen `404`-Pfad akzeptiert.
Es wurde keine Cross-Consumer-Konfiguration geändert.

---

## 6. DynamoDB-Nachweis

Gezielter, konsistenter `GetItem` auf exakt:

```text
pk = ord_ord_6dac882b1e52a478db3f7583
sk = #ORDER
```

| Zeitpunkt | Status | Version | Owner |
|---|---|---:|---|
| Nach Owner-Read / vor Fremdversuchen | CONFIRMED | 2 | `subjectId = sub(A)` |
| Nach Foreign Read/PATCH und Owner-Integrity | CONFIRMED | 2 | unverändert |

Keine breit angelegte Tabellenmutation, kein Scan-and-Delete.

---

## 7. Cleanup-Evidence

Nach Testabschluss:

1. Order über exakten Key gelöscht; `subjectId = sub(A)` als Bedingung.
2. Gezieltes `GetItem` bestätigt: Order nicht mehr vorhanden.
3. Beide synthetischen Cognito-Benutzer gelöscht.
4. Read-only Postflight:

| Prüfung | Ergebnis |
|---|---|
| DynamoDB `ItemCount` | **0** |
| GSI3 `PROCESSING#RUNNING` | **Count 0** |
| Main Queue visible/in-flight | **0 / 0** |
| DLQ visible/in-flight | **0 / 0** |
| Cognito-Pool User | **0** |
| Verbleibende Testorder | **keine** |
| Queue Purge | **NEIN** |
| Fremde Daten gelöscht | **NEIN** |

Die Postflight-Prüfung der Lambda-CodeSha256 bestätigte erneut für Handler und
Worker:

```text
FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=
```

---

## 8. Sicherheitsbefunde

```text
Fremdzugriff auf Orderdaten:        NONE
Foreign PATCH erfolgreich:          NO
Unzulässige Statusänderung:         NONE
Unzulässige Versionsänderung:       NONE
Fremde Daten verändert/gelöscht:    NONE
Fremder Benutzer beeinflusst:       NONE
Cleanup unvollständig:              NO
```

Es wurden keine neuen Sicherheitsdefekte festgestellt. Die bestehende
Owner- und Consumer-Bindung hat im Live-Test vertragskonform funktioniert.

---

## 9. Nicht ausgeführt / bewusst nicht wiederholt

- Keine DLQ-, Recovery- oder Kompatibilitätswiederholung.
- Keine Privacy-B2-Tests.
- Keine Cross-Consumer-Konfiguration und kein zweiter App-Client.
- Keine IAM-/Cognito-Konfigurationsänderung.
- Keine Lambda-Code-/Konfigurationsänderung.
- Kein Terraform, keine Pipeline, kein Push/Merge.

---

## 10. Ergebnisstatus

```text
IDENTITY LIVE VERIFIED
ID-01 Owner Create:        PASS (201)
ID-02 Owner Read:          PASS (200, CONFIRMED, version 2)
ID-03 Foreign Read:        PASS (404 ORDER_NOT_FOUND, no order fields)
ID-04 Foreign PATCH:       PASS (404, status/version unchanged)
ID-05 Foreign List:        PASS (200, count 0, no A data)
ID-06 Owner Integrity:     PASS (200, CONFIRMED, version 2)
Cleanup:                   VERIFIED
```

Keine G4-Freigabe. Keine Privacy-B2-Ausführung. Keine Cross-Consumer-
Konfigurationsänderung. Keine weiteren AWS-Mutationen.

---

## 11. Änderungen und Auditlog

| Datei | Änderung |
|---|---|
| `docs/reports/MO-RC3-RC4-G3-LIVE-B1-IDENTITY-01.md` | dieser Live-Bericht |
| `docs/AI_AUDITLOG.md` | Index-Eintrag ergänzt |

Originale B1-Live-Evidence in
`docs/reports/MO-RC3-RC4-G3-LIVE-B1-01.md` bleibt unverändert.

---

## 12. Commit-SHA und Working-Tree-Status

| Feld | Wert |
|---|---|
| Dokumentations-Commit | `deb005d027791372682d924a036ccd76022dc7b5` |
| Working Tree nach Commit | CLEAN |

Es wurden ausschließlich Dokumentationsdateien geändert. Kein Produktcode,
kein Test-Harness, kein Terraform, keine AWS-Konfiguration.
