# E2E Test Suite — Setup, Gates und Cleanup

Diese Datei ist der Einstiegspunkt für die RC3/RC4-E2E-Tests. Sie erklärt
bewusst **lokal** und **live** getrennt.

## Dateien

| Datei | Zweck | benötigt AWS? |
|---|---|---|
| `tests/e2e_harness.py` | Fake-HTTP, Run-/Order-Fixtures, Ownership-Cleanup, Diagnostik | Nein |
| `tests/test_e2e_harness.py` | 16 lokale Tests für Harness, Auth, 401, Cleanup, Redaktion | Nein |
| `tests/test_e2e_async_order.py` | 4 echte Live-E2E-Tests; ohne Opt-in BLOCKED | Ja, nur mit Freigabe |
| `tests/privacy_e2e_harness.py` | B2-Gates, Lambda-Invoke-Adapter, Privacy-Kontext, exakte Fixtures | Nein |
| `tests/test_privacy_e2e_harness.py` | 15 lokale Privacy-Harness-Tests | Nein |
| `tests/test_privacy_e2e.py` | G3X-PRV-X01…X13 Live-Tests; standardmäßig BLOCKED | Ja, nur mit B2-Freigabe |

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

Die lokalen Tests verwenden `FakeTransport` bzw. Fake-Dynamo-Clients; sie
benötigen weder Credentials noch Netzwerk.

Privacy-Harness separat:

```bash
cd /tmp/opencode/rc4-upgrade-plan
python3 -m unittest tests.test_e2e_harness tests.test_privacy_e2e_harness -v
```

Erwartung: 31 Tests PASS, keine AWS-Verbindung.

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

## Privacy B2 — Live-Gates und Testbenutzer

Die Privacy-Livetests (`G3X-PRV-X01`…`X13`) verwenden **vorab bereitgestellte**
Testidentitäten A/B. Das Testmodul legt **keine** Cognito-Benutzer, IAM-Rollen,
Secrets oder Lambda-Konfiguration an.

Benötigte Umgebung (alle Werte erforderlich; fehlende Werte ergeben `BLOCKED`):

```bash
export MO_PRIVACY_LIVE=1
export MO_E2E_LIVE_CLEANUP=1
export PRIVACY_E2E_INVOKER_APPROVED=1
export AWS_PROFILE=mayaws
export AWS_REGION=eu-central-1
export PRIVACY_E2E_ACCOUNT_ID=240571105849
export PRIVACY_E2E_TABLE=mays-orders-rc4-test
export PRIVACY_E2E_HANDLER=mays-orders-rc4-test-handler
export PRIVACY_E2E_CODE_SHA256=FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=
export PRIVACY_E2E_PROJECT=mays-orders-rc4-test
export PRIVACY_E2E_CONSUMER_ID='cognito:cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OZ7TK51EK#415t3lt2k1umrmoaibn4f302sn'
export PRIVACY_E2E_QUEUE_URL='https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-rc4-test-orders-queue'
export PRIVACY_E2E_DLQ_URL='https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-rc4-test-orders-queue-dlq'
export API_BASE_URL='https://37fldhw7fi.execute-api.eu-central-1.amazonaws.com'
export PRIVACY_E2E_SUBJECT_A=<sub of test identity A>
export PRIVACY_E2E_SUBJECT_B=<sub of test identity B>
export PRIVACY_E2E_ACCESS_TOKEN_A=<pre-provisioned token A>
export PRIVACY_E2E_ACCESS_TOKEN_B=<pre-provisioned token B>
export PRIVACY_E2E_INTERNAL_TOKEN=<must equal the handler's PRIVACY_INTERNAL_SECRET>
```

`PRIVACY_E2E_INVOKER_APPROVED=1` bestätigt den separat freigegebenen,
least-privilege Lambda-Invoker. `MO_E2E_LIVE_CLEANUP=1` bestätigt den
run-scoped Cleanup. Ohne alle Gates importiert das Live-Modul kein boto3 und
führt keine AWS-Verbindung aus.

```bash
cd /tmp/opencode/rc4-upgrade-plan
python3 -m unittest tests.test_privacy_e2e -v
```

Erwartung ohne Freigabe:

```text
skipped: BLOCKED: missing privacy live prerequisite(s): ...
```

Der Cleanup verwendet:

- `LiveCleanupBackend` für normale A/B-Orders (subject-/owner-verifiziert).
- `ExactKeyCleanupBackend` für ANONYMIZE und Consumer-Fixtures mit exaktem
  `pk`/`sk` und run-scoped Marker; kein Scan, kein Purge, keine fremden Keys.

`G3X-PRV-X13` (fehlendes Lambda-Secret) ist in einem secret-fähigen B2-Lauf
nicht reproduzierbar, weil dafür eine zweite Lambda-Konfigurationsänderung
nötig wäre. Der lokale Test `test_privacy_requires_internal_secret` deckt den
fail-closed Branch ab; der Live-Test bleibt explizit `BLOCKED`.

Die Testidentitäten werden **nicht** automatisch gelöscht. Der Operator muss
sie nach dem Lauf über den freigegebenen Cognito-Cleanup entfernen.

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
