# MO-RC4-B2-LIVE-EXECUTION-02

**Kontrollierte B2-Privacy-Live-Ausführung und Rückbau**

**Datum:** 2026-11-13
**Branch:** `test/mo-rc4-testsuite-hardening-10a`
**HEAD vor Ausführung:** `7b6c3afe7caa24f9b54b8b0ee6e02ad3c996b927`
**AWS-Account:** `240571105849`
**Region:** `eu-central-1`
**Teststack:** `mays-orders-rc4-test`

```text
B2 LIVE VERIFIED — CLEANUP VERIFIED
```

Die B2-Privacy-Suite wurde gegen den freigegebenen RC4-Teststack ausgeführt.
14 Tests sind PASS, X13 ist gemäß dokumentierter Grenze SKIP. Cleanup,
IAM-Rückbau und Lambda-Env-Rückbau sind verifiziert. Es gab keine
Fremddatenoffenlegung und keine unzulässige Fremdänderung.

---

## 1. Baseline vor Ausführung

| Feld | Wert |
|---|---|
| Handler CodeSha256 | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Worker CodeSha256 | derselbe Hash |
| Handler-Env vor Lauf | `ORDERS_TABLE`, `SQS_QUEUE_URL`, `ORDERS_PROJECT_NAME` |
| `PRIVACY_INTERNAL_SECRET` | nicht vorhanden |
| DynamoDB / GSI3 | 0 / 0 |
| Main Queue / DLQ | 0/0 / 0/0 |
| Cognito-Pool | 0 User |
| Temp-IAM-Rolle | nicht vorhanden |
| `directAWSGit` Deploy | `Stopped` |

---

## 2. Temporäre Konfiguration

### IAM

Temporäre Rolle:

```text
mays-orders-rc4-test-b2-invoker
```

- Trust auf `arn:aws:iam::240571105849:user/Mayaws`.
- Inline-Policy exakt:
  - `lambda:InvokeFunction` und `lambda:GetFunctionConfiguration` auf den
    Handler;
  - `dynamodb:DescribeTable`, `GetItem`, `PutItem`, `DeleteItem` auf die
    Testtabelle;
  - `sqs:GetQueueAttributes` auf Main Queue/DLQ;
  - `sts:GetCallerIdentity`.
- AssumeRole wurde mit temporären STS-Credentials verifiziert.
- Keine langfristigen Access Keys, keine AdministratorAccess-Testidentität.
- Rolle und Inline-Policy wurden nach dem Lauf gelöscht.

### Lambda-Env

- `PRIVACY_INTERNAL_SECRET` temporär ergänzt; bestehende Env-Variablen blieben
  vollständig erhalten.
- Kein Code-, Runtime-, Handler-, Role- oder Worker-Update.
- Secret-Wert nur im Prozessspeicher; nicht in Git, Report, Auditlog,
  Shell-History oder argv.
- Nach dem Lauf wurde der ursprüngliche Env-Zustand wiederhergestellt und
  geprüft.

### Testidentitäten

- Zwei synthetische Benutzer A/B im bestehenden Testpool und App-Client.
- Unterschiedliche `sub`-Claims, derselbe Consumer.
- Benutzer wurden nach dem Lauf gelöscht; Pool ist wieder leer.
- Keine produktiven Identitäten, keine bestehenden Benutzer verändert.

---

## 3. Ausführung

Verwendet wurde ausschließlich die integrierte Suite:

```bash
PYTHONPATH=/tmp/opencode/rc4-upgrade-plan \
python3 /tmp/opencode/b2_phase_b.py
```

Der Operator-Runner hat die freigegebene Konfiguration eingerichtet und
`tests.test_privacy_e2e` ausgeführt. Der eigentliche Testlauf verwendete die
temporäre Invoke-Rolle, nicht `Mayaws` als direkten Invoker.

### Run-IDs

| Feld | Wert |
|---|---|
| Operator-Run | `b2livec61b2c8f28` |
| E2E-Test-Run | `031b217823d7` |
| Testklasse | `tests.test_privacy_e2e.PrivacyLiveE2E` |

### Ergebnis

```text
Ran 15 tests in 14.694s
OK (skipped=1)
```

| ID | Ergebnis |
|---|---|
| X01 Inspect eigene Daten | **PASS** |
| X01 Empty Subject | **PASS** |
| X01 Consumer-Scope | **PASS** |
| X02 falsches Projekt | **PASS** |
| X03 falscher interner Token | **PASS** |
| X04 `authorized=false` | **PASS** |
| X05 Export eigene Daten | **PASS** |
| X06 Export fremdes Subject | **PASS** |
| X07 Erase PREVIEW | **PASS** |
| X08 Erase ohne Policy | **PASS** |
| X09 Erase B / Idempotenz | **PASS** |
| X10 RETAIN | **PASS** |
| X11 ANONYMIZE | **PASS** |
| X12 Consumer-Scope-Erase | **PASS** |
| X13 fehlendes Secret | **SKIP — nicht als PASS gezählt** |

**X13** ist in einem secret-fähigen Lauf nicht reproduzierbar; der lokale
Lambda-Test `test_privacy_requires_internal_secret` deckt den fail-closed
Branch ab. Der Skip wird ausdrücklich nicht als PASS gewertet.

### Consumer-Isolation

- X01-CONSUMER: fremder Consumer/legacy ausgeschlossen.
- X06: Export B enthält ausschließlich B, keine A-Daten.
- X12: genau ein eigener Consumer-Record gelöscht; fremder Consumer und
  Legacy-Record unverändert.
- A1/A2 blieben bei X11/X12 unverändert.

### Erasure / ANONYMIZE

- X07/X08: keine Mutation.
- X09: B einmal gelöscht; Wiederholung löschte 0.
- X10: 2 retained, keine Mutation.
- X11: eine dedizierte One-Order-Anonymisierung; `subjectId` entfernt;
  exakter Cleanup.
- X12: Consumer-Scope-Delete ausschließlich für den eigenen Consumer.

---

## 4. Cleanup- und Rückbau-Nachweis

| Prüfung | Endzustand |
|---|---|
| DynamoDB `ItemCount` | **0** |
| GSI3 `PROCESSING#RUNNING` | **0** |
| Main Queue visible/in-flight | **0 / 0** |
| DLQ visible/in-flight | **0 / 0** |
| Cognito-Testbenutzer | **0** |
| Temp-IAM-Rolle | **gelöscht** |
| `PRIVACY_INTERNAL_SECRET` | **entfernt** |
| Handler-Env Keys | `ORDERS_TABLE`, `SQS_QUEUE_URL`, `ORDERS_PROJECT_NAME` |
| Handler CodeSha256 | `FYTuDczNCwQid4JxhFdaGHbBWcdaeg6VzNKbT+WjfkQ=` |
| Temp-Credentials-Datei | **gelöscht** |
| Queue Purge | **NEIN** |
| Fremde Daten gelöscht/verändert | **NEIN** |

Die Testsuite und der Operator-Runner haben ausschließlich run-eigene Orders
und exakte Keys entfernt. ANONYMIZE- und Consumer-Fixtures wurden über
`ExactKeyCleanupBackend` mit Run-Marker bereinigt.

---

## 5. Während der Vorbereitung gefundene und korrigierte Testdefekte

Vor dem erfolgreichen Lauf wurden ausschließlich **Test-/Operatorfehler**
gefunden; keine Produktänderung:

1. IAM-Rollen-Trust war wegen IAM-Eventual-Consistency erst nach einigen
   Sekunden assume-bar; der Runner wartet jetzt mit begrenztem Retry.
2. Operator-Skript brauchte den Repo-Root in `PYTHONPATH`; kein Testdefekt.
3. `E2ERun` als Klassenattribut `run` überschrieb `unittest.TestCase.run`;
   umbenannt zu `e2e_run`.
4. `_invoke` reichte `options` fälschlich in den Auth-Kontext statt in den
   Invoke-Payload; korrigiert.
5. `ExactKeyCleanupBackend` prüfte low-level DynamoDB-`AttributeValue` nicht
   typisiert; typisierte `items.L[].M.sku.S`-Prüfung ergänzt.
6. Die Testklasse nutzte für ANONYMIZE/X12 getrennte Subjects; der Cleanup
   verwendet dafür exakte Keys.
7. Zwischenläufe wurden jeweils bereinigt; der finale Endzustand ist 0/0/0/0.

Diese Korrekturen sind Test-Harness-Verbesserungen; die Produktlogik wurde
nicht verändert.

---

## 6. Verbleibende Risiken

- `PRIVACY_INTERNAL_SECRET` war temporär in der Lambda-Env; für die Dauer des
  Testfensters war es über `lambda:GetFunctionConfiguration` lesbar. Es wurde
  entfernt; ein dauerhafter Env-Secret-Betrieb bleibt kein Produktivmodell.
- P00 Secrets Manager/KMS/Retention ist weiterhin nicht implementiert.
- PITR (35 Tage) und fehlende Retention/TTL bleiben Privacy-Risiken.
- Der Consumer-Scope ist optional; ohne Scope bleibt das Verhalten
  deployment-weit.
- Der `erase`-Delete-Condition enthält `consumerId` nicht; bei unveränderlichem
  Consumer akzeptabel, aber ein TOCTOU-Restrisiko.
- Kein dauerhaftes Erasure-Ledger.
- X13 ist live nur in einer secret-absenten Konfiguration reproduzierbar.
- SEC-06, Idempotency-Key, Legacy-Migration, Handler-Registry, Terraform-Drift,
  RIS-Pin und CI/CD-Gates bleiben offen.

---

## 7. Release-Auswirkung

Die B2-Zeile der RC4-Release-Matrix ist jetzt:

```text
Privacy B2: B2 LIVE VERIFIED — CLEANUP VERIFIED
```

Das ist **keine** RC4-Gesamtfreigabe. Phase C und die übrigen offenen Punkte
werden getrennt behandelt. Es gab keine automatische G4-/RC4-Freigabe.

---

## 8. Auditlog / Commit

Der Auditlog-Eintrag wird nach dem Commit ergänzt.

| Feld | Wert |
|---|---|
| Test-Fix-Commit | `71e1ae70ec285d1611d8c309f9bdb1fe8ce44ed6` |
| Dokumentations-Commit | `e69b350fa11cd26acff273b7c3f56ea812d56482` |
| Working Tree nach Commit | CLEAN |

**STOP — keine automatische G4-/RC4-Freigabe, kein Terraform Apply, kein Push/Merge.**
