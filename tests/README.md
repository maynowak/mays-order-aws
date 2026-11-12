# E2E Test Suite — Setup, Gates und Cleanup

Diese Datei ist der Einstiegspunkt für die RC3/RC4-E2E-Tests. Sie erklärt
bewusst **lokal** und **live** getrennt.

## Dateien

| Datei | Zweck | benötigt AWS? |
|---|---|---|
| `tests/e2e_harness.py` | Fake-HTTP, Run-/Order-Fixtures, Ownership-Cleanup, Diagnostik | Nein |
| `tests/test_e2e_harness.py` | 16 lokale Tests für Harness, Auth, 401, Cleanup, Redaktion | Nein |
| `tests/test_e2e_async_order.py` | 4 echte Live-E2E-Tests; ohne Opt-in BLOCKED | Ja, nur mit Freigabe |

## Lokale Tests

```bash
cd /tmp/opencode/rc4-upgrade-plan
python3 -m unittest discover -s tests -p 'test_e2e_harness.py'
```

Erwartung:

```text
Ran 16 tests
OK
```

Die lokalen Tests verwenden `FakeTransport`; sie benötigen weder Credentials
noch Netzwerk.

## Live-E2E — Voraussetzungen

Ein Live-Lauf ist **nur** mit einer autorisierten, vorab bereitgestellten
Testidentität und einer ausdrücklichen Cleanup-Freigabe zulässig.

Benötigte Umgebung:

```bash
export AWS_PROFILE=mayaws
export AWS_REGION=eu-central-1
export ORDERS_TABLE=mays-orders-rc4-test
export API_BASE_URL=https://37fldhw7fi.execute-api.eu-central-1.amazonaws.com
export ACCESS_TOKEN=<pre-provisioned Cognito access token>
export E2E_SUBJECT=<JWT sub to which the token belongs>
export MO_E2E_LIVE=1
export MO_E2E_LIVE_CLEANUP=1
```

`E2E_SUBJECT` ist die Eigentümerprüfung für den Cleanup. Der Live-Test löscht
**nur** Order-Items, deren gespeicherte `subjectId` exakt diesem Wert
entspricht. Fremde Orders werden mit `CleanupOwnershipError` abgelehnt.

`MO_E2E_LIVE_CLEANUP` darf nur in einem ausdrücklich freigegebenen Testlauf
gesetzt werden. Ohne diese Variable werden die Live-Tests als `BLOCKED`
übersprungen.

## Testbenutzer-Verfahren (historisch, AWS-Mutation)

Das im Projekt vorhandene Verfahren:

```bash
export AWS_PROFILE=mayaws
export COGNITO_USER_POOL_ID=eu-central-1_OZ7TK51EK
export COGNITO_CLIENT_ID=415t3lt2k1umrmoaibn4f302sn
export TEST_USER_PASSWORD=<approved test password>
python3 scripts/tests/setup_test_user.py
```

Hinweise:

- Das Skript legt einen Cognito-Benutzer an, setzt ein Passwort und fügt ihn
  zur Gruppe `staff` hinzu.
- Es benötigt `COGNITO_USER_POOL_ID` explizit; ohne diese Variable würde es
  den Platzhalter `eu-central-1_XXXXXXXX` verwenden.
- Es erzeugt **keinen** Access Token. Der `ACCESS_TOKEN` muss separat über
  `USER_PASSWORD_AUTH` beschafft werden.
- Der historische Cleanup löschte Order, DLQ-Nachricht und Testbenutzer;
  Cleanup ist ein separater, freigabepflichtiger AWS-Schritt.

**Dieses Skript wird nicht automatisch durch die Testsuite ausgeführt.** Es
ist ein kontrollierter Operator-Schritt, keine Produktfunktion.

## Live-Lauf

```bash
cd /tmp/opencode/rc4-upgrade-plan
python3 -m unittest tests.test_e2e_async_order -v
```

Erwartung bei erfüllten Voraussetzungen:

- unauthentifizierter `GET /orders` → 401,
- authentifizierter `POST /orders` → 201/PENDING,
- Worker-Übergang → CONFIRMED,
- GET-Datenintegrität,
- Cleanup jedes erzeugten Order-Items über `E2E_SUBJECT`.

Ohne `MO_E2E_LIVE`, `ACCESS_TOKEN`, `E2E_SUBJECT` oder
`MO_E2E_LIVE_CLEANUP` bleiben die Live-Tests **BLOCKED** und es wird keine
Order erzeugt.

## Cleanup-Regeln

- Keine Queue-Purge-Operation.
- Keine fremden Orders löschen.
- Keine direkte Massenlöschung; nur exakte, eigentümergeprüfte Order-Keys.
- Cleanup-Fehler werden nicht unterdrückt.
- Testbenutzer werden nach dem Lauf separat über `AdminDeleteUser` entfernt.
- Keine Secrets/Tokens/Passwörter in Reports oder Logs.

## Warum das wichtig ist

Ein `PASS` der 1.153 lokalen Tests ist **kein** AWS-Live-Nachweis. Die
lokale Suite nutzt Fakes; die Live-Suite ist separat und bleibt ohne
Testidentität, Cleanup-Freigabe und ausdrückliche AWS-Genehmigung `BLOCKED`.
