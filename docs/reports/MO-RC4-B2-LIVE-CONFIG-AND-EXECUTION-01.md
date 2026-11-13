# MO-RC4-B2-LIVE-CONFIG-AND-EXECUTION-01

**B2 Privacy Live Configuration — Phase A**

**Datum:** 2026-11-13
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Phase A:** `690beb3ff8a6bedc75cd9be390bafcfc585c157b`
**Modus:** ausschließlich read-only AWS-Verifikation und Dokumentation;
**keine AWS-Mutation**, keine Testbenutzer, kein Secret gesetzt oder gelesen,
keine Lambda-Invocation, kein Livetest, keine IAM-/Terraform-Änderung, kein
Push/Merge.

```text
B2 LIVE CONFIGURATION — READY FOR APPROVAL
```

Phase A ist abgeschlossen. Die temporäre Konfiguration ist mit den vorhandenen
AWS-Berechtigungen und den dokumentierten Sicherheitsgrenzen technisch
einrichtbar. Es wurde **nichts** eingerichtet oder verändert. Phase B darf erst
nach ausdrücklicher, auf diesen Antrag bezogener Freigabe beginnen.

---

## 1. Ausgangslage

| Feld | Wert |
|---|---|
| Branch | `test/mo-rc4-testsuite-hardening-10a` |
| HEAD | `690beb3ff8a6bedc75cd9be390bafcfc585c157b` |
| Working Tree | CLEAN |
| B2-Suite | `B2 TESTSUITE INTEGRATED — READY FOR LIVE CONFIGURATION` |
| Lokale Tests | 1.173 PASS |
| B2-Live | noch nicht ausgeführt |
| AWS-Account | `240571105849` |
| Region | `eu-central-1` |
| Profil | `mayaws` |
| Caller | `arn:aws:iam::240571105849:user/Mayaws` |

Gelesen: `docs/AI_AUDITLOG.md`, B2-Integrationsbericht,
`tests/README.md`, B2-PREP-01 und G3-Live-Manifest.

---

## 2. Read-only AWS-Verifikation

| Prüfung | Ergebnis |
|---|---|
| STS Account | `240571105849` — PASS |
| Region | `eu-central-1` — PASS |
| Handler | `mays-orders-rc4-test-handler`, `Active` / `Successful` |
| Worker | `mays-orders-rc4-test-sqs-worker`, `Active` / `Successful` |
| CodeSha256 beide | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Handler Env Keys | `SQS_QUEUE_URL`, `ORDERS_TABLE`, `ORDERS_PROJECT_NAME` |
| `PRIVACY_INTERNAL_SECRET` | **nicht vorhanden** |
| DynamoDB | ACTIVE, `ItemCount=0` |
| GSI3 `PROCESSING#RUNNING` | Count 0 |
| Main Queue | 0 / 0 |
| DLQ | 0 / 0 |
| Cognito-Pool | `eu-central-1_OZ7TK51EK`, 0 User |
| API-Routen | nur die vier Order-Routen, keine Privacy-Route |
| Handler Resource-Policy | nur `apigateway.amazonaws.com` auf API `37fldhw7fi/*/*` |
| Function URL | keine |
| `directAWSGit` Deploy | `Stopped` |
| Development-Pipeline | historisch fehlgeschlagene Stage-Status; keine neue Auslösung |

Keine AWS-Schreiboperation. Es wurden keine Secret-Werte gelesen.

### Berechtigungsbefund

`Mayaws` besitzt `AdministratorAccess` und kann die temporäre Konfiguration
technisch einrichten. **`Mayaws` wird ausdrücklich nicht als Test-Invoker
verwendet.** Der Testlauf erhält eine separate, zeitlich begrenzte Rolle mit
engem Ressourcen-Scope.

---

## 3. Erforderliche temporäre Konfiguration

### 3.1 Lambda-Handler-Env

Betroffene Ressource:

```text
arn:aws:lambda:eu-central-1:240571105849:function:mays-orders-rc4-test-handler
```

Änderung:

```text
PRIVACY_INTERNAL_SECRET=<temporärer Zufallswert>
```

- Nur Konfigurations-Update; **kein Code-Update**.
- Keine Änderung an Runtime, Handler, Role, Timeout, Memory, Worker oder
  SQS/DynamoDB/Cognito.
- Der bisherige Env-Zustand wird exakt gesichert und nach dem Lauf
  wiederhergestellt.
- Der Wert wird niemals in Git, Report, Auditlog, Shell-History oder argv
  geschrieben.
- Sollte `PRIVACY_INTERNAL_SECRET` wider Erwarten bereits vorhanden sein, wird
  **kein bestehendes Secret überschrieben**; der Lauf stoppt und meldet
  `BLOCKED — EXISTING SECRET`.

### 3.2 Temporäre IAM-Rolle für den Testlauf

Vorgeschlagener Name:

```text
mays-orders-rc4-test-b2-invoker
```

Trust:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::240571105849:user/Mayaws"},
    "Action": "sts:AssumeRole"
  }]
}
```

Inline-Policy, exakt begrenzt:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokePrivacyHandler",
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:eu-central-1:240571105849:function:mays-orders-rc4-test-handler"
    },
    {
      "Sid": "PreflightHandlerConfig",
      "Effect": "Allow",
      "Action": "lambda:GetFunctionConfiguration",
      "Resource": "arn:aws:lambda:eu-central-1:240571105849:function:mays-orders-rc4-test-handler"
    },
    {
      "Sid": "TestTableFixtures",
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders-rc4-test"
    },
    {
      "Sid": "QueueReadOnly",
      "Effect": "Allow",
      "Action": "sqs:GetQueueAttributes",
      "Resource": [
        "arn:aws:sqs:eu-central-1:240571105849:mays-orders-rc4-test-orders-queue",
        "arn:aws:sqs:eu-central-1:240571105849:mays-orders-rc4-test-orders-queue-dlq"
      ]
    },
    {
      "Sid": "CallerIdentity",
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    }
  ]
}
```

Bewertung:

- Kein `AdministratorAccess`.
- Kein `iam:*`, kein `secretsmanager:*`, kein `kms:*`, kein S3, kein
  Cognito-Admin, kein Queue-Send/Receive/Delete, kein `PurgeQueue`.
- `lambda:GetFunctionConfiguration` ist für den bestehenden Live-Preflight
  nötig und kann die Env-Variablen lesen. Deshalb bleibt die Rolle nur für das
  Testfenster bestehen und wird danach gelöscht.
- Die Rolle ersetzt keine Produktrolle und wird nicht in Terraform gehalten.

### 3.3 Testidentitäten A/B

Zwei synthetische Benutzer im bestehenden Pool `eu-central-1_OZ7TK51EK` und
bestehenden Client `415t3lt2k1umrmoaibn4f302sn`:

```text
A (Owner):        b2-<run>-a@example.com
B (Foreign):      b2-<run>-b@example.com
```

- `AdminCreateUser` + `AdminSetUserPassword(Permanent=True)`.
- Optional `staff`-Gruppe; die API-Autorisierung benötigt sie nicht.
- Authentifizierung über `USER_PASSWORD_AUTH`; Access Tokens nur im
  Prozessspeicher.
- `sub(A) != sub(B)` und beide gehören zum selben Consumer.
- Nach dem Lauf `AdminDeleteUser` für beide; Pool muss wieder 0 User haben.
- Keine bestehenden Benutzer werden verändert.

### 3.4 Testdaten

- A: zwei API-Orders über den Testendpoint (für Inspect/Export/Preview/RETAIN).
- B: eine API-Order (für fremden Subject-Export und Erase).
- Zusätzliche run-präfixierte Direct-DDB-Fixtures:
  - fremder Consumer unter Subject A für Inspect-Scope;
  - ein One-Order-Subject für ANONYMIZE;
  - ein Scope-Subject mit eigenem Consumer-Record und fremdem Consumer-Record
    für X12.
- Alle Marker enthalten die Run-ID. Cleanup über exakte Keys.

---

## 4. Secret-Handhabung

1. Zufallswert mit `secrets.token_urlsafe(32)` erzeugen.
2. Wert ausschließlich in einer temporären `0600`-Datei oder im Prozessspeicher
   halten; keine Ausgabe in Terminal/History.
3. `PRIVACY_INTERNAL_SECRET` per
   `lambda:UpdateFunctionConfiguration` mit `--cli-input-json file://...`
   setzen. Kein Secret in argv.
4. Derselbe Wert wird dem Testprozess als
   `PRIVACY_E2E_INTERNAL_TOKEN` übergeben.
5. Nach dem Lauf:
   - Env-Key entfernen und vorherigen Env-Zustand wiederherstellen,
   - temporäre Secret-Datei sicher löschen (`shred`/unlink),
   - keine Secrets Manager-/SSM-/KMS-Ressource anlegen.
6. Keine Secret-Werte in Report, Auditlog, Git, Logs oder Diagnostik.

**Risiko:** Ein Env-Secret ist für `lambda:GetFunctionConfiguration` lesbar.
Deshalb ist die Konfiguration zeitlich begrenzt, die Testrolle hat keinen
`secretsmanager`-Zugriff, und die Rolle wird nach dem Lauf gelöscht. Dies ist
kein Produktivmodell; P00/Secrets Manager bleibt separat offen.

---

## 5. Testausführung nach Freigabe

Genau der vorhandene Runner:

```bash
cd /tmp/opencode/rc4-upgrade-plan
python3 -m unittest tests.test_privacy_e2e -v
```

Erwartung:

- 14 ausführbare Privacy-Tests (X01–X12 inkl. Subcases),
- `X13` wird gemäß dokumentierter Grenze als `BLOCKED/SKIP` behandelt
  (secret-absenter Stack nicht im selben Lauf reproduzierbar),
- keine Testbenutzer-Erstellung durch die Suite,
- keine AWS-Mutation bei fehlenden Gates.

Der Testlauf verwendet die temporäre Rolle über ein temporäres AWS-Profil
(assume-role); die Profildatei ist `0600` und wird nach dem Lauf gelöscht.
`Mayaws` wird nur zum Einrichten/Abbauen und nicht zum Invoke verwendet.

### Erwartete Kernassertions

- X01: Inspect A → 2 Referenzen, keine PII.
- X01-CONSUMER: fremder Consumer/legacy ausgeschlossen.
- X05/X06: Export A=2, B=1; keine internen Felder.
- X07/X08: Preview und Execute-ohne-Policy ohne Mutation.
- X09: B Erase=1; Wiederholung=0.
- X10: RETAIN=2 retained, keine Mutation.
- X11: ANONYMIZE=1; `subjectId` entfernt; exakter Cleanup.
- X12: genau 1 eigener Consumer-Record gelöscht; fremder Consumer/legacy
  unberührt.
- X13: `BLOCKED/SKIP` wie dokumentiert.

---

## 6. Cleanup und Rückbau

### Nach dem Testlauf

1. `tearDownClass` reinigt normale A/B-Orders über `LiveCleanupBackend`.
2. ANONYMIZE- und Consumer-Fixtures werden über
   `ExactKeyCleanupBackend` mit run-scoped Marker entfernt.
3. Exakte `GetItem`-Prüfung: keine Order-Reste.
4. Tabelle/GSI3/Queue/DLQ read-only prüfen: 0/0/0/0.
5. Zwei Testbenutzer löschen; Pool `list-users` = 0.
6. Temporäres AWS-Profil und Secret-Datei löschen.
7. `PRIVACY_INTERNAL_SECRET` aus der Handler-Env entfernen; ursprünglichen
   Env-Zustand wiederherstellen.
8. Temporäre IAM-Rolle und Inline-Policy löschen.
9. Lambda-CodeSha256 erneut prüfen: unverändert `FYTu…`.

### Kein Purge / keine Massenlöschung

- Kein `sqs:PurgeQueue`.
- Kein Tabellenscan.
- Keine fremden Keys.
- Keine Änderung an RIS/Produktion.

### Rückbau bei Abbruch

- Sofort keine weiteren Funktionstests.
- Bereits erzeugte run-eigene Daten exakt löschen, soweit sicher zuordenbar.
- Env-Secret und temporäre Rolle entfernen.
- Testbenutzer löschen.
- Bei unklarer Zuordnung: `CLEANUP INCOMPLETE` berichten, keine improvisierte
  Massenlöschung.

---

## 7. Abbruchbedingungen

Sofort STOP bei:

- Account-/Region-/Stack-/CodeSha-Mismatch,
- unerwarteten Bestandsdaten oder Queue-Nachrichten,
- nicht eindeutig zuordenbaren Testidentitäten,
- erfolgreichem Fremdzugriff auf Orderdaten,
- erfolgreichem Foreign-PATCH oder unerwarteter Status-/Versionsänderung,
- unerwarteter AWS-/Pipeline-/Deployment-Aktivität,
- fehlender Invoke-Berechtigung,
- Cleanup-/Ownership-Mismatch,
- Secret- oder Credential-Leak außerhalb des Testprozesses,
- nicht sicherem Rückbau.

Keine automatischen Wiederholungen. Keine Erweiterung der Testrechte ohne neue
Freigabe.

---

## 8. Freigabeantrag — exakt

**Beantragt wird ausschließlich die folgende Phase-B-Ausführung:**

| Punkt | Umfang |
|---|---|
| Lambda-Konfiguration | `PRIVACY_INTERNAL_SECRET` temporär auf Handler; kein Code-/Runtime-/Role-Update |
| IAM | temporäre Rolle `mays-orders-rc4-test-b2-invoker` mit der oben genannten Inline-Policy und Trust auf `Mayaws`; danach löschen |
| Cognito | zwei synthetische Benutzer A/B im bestehenden Testpool; danach löschen |
| API | A1/A2/B1 über Test-API; exakte Cleanup-Keys |
| DDB-Fixtures | fremder Consumer, ANONYMIZE-Subject, Scope-Subject; run-präfixiert; exakte Cleanup-Keys |
| Lambda-Invoke | nur `privacy/inspect`, `privacy/export`, `privacy/erase` auf Handler |
| Zusätzliche Tests | B2-Suite `tests.test_privacy_e2e`; X13 als BLOCKED/SKIP |
| Cleanup | exakte Keys, User-Löschung, Env-/Rollen-Rückbau, Queue/DLQ 0/0 |
| Nicht enthalten | Terraform, KMS/Secrets Manager, neue API-Route, Produktcode, RIS/Produktion, Push/Merge |

**Voraussetzung für die Freigabe:** Der Antrag muss ausdrücklich bestätigt
werden. Ohne diese Bestätigung bleibt Phase B blockiert.

---

## 9. Ergebnisstatus

```text
Phase A:                         COMPLETE
AWS read-only verification:      PASS
Configuration feasibility:       YES — with temporary role/env/users
B2 LIVE CONFIGURATION:           READY FOR APPROVAL
AWS mutations in Phase A:        NONE
B2 live tests in Phase A:        NONE
```

Die Konfiguration ist mit den vorhandenen Rechten technisch möglich, aber
**noch nicht eingerichtet**. Die Freigabe ist der nächste notwendige Schritt.

---

## 10. Auditlog / Commit

Der Auditlog-Eintrag wird nach dem Commit ergänzt. Es wurden nur
Dokumentationsdateien geändert.

| Feld | Wert |
|---|---|
| Dokumentations-Commit | wird nach dem Commit eingetragen |
| Working Tree nach Commit | CLEAN |

**STOP — keine AWS-Mutation, keine Secret-Erstellung, keine Lambda-Invocation,
kein Livetest, keine RC4-Release-Freigabe.**
