# MO-RC4-P00-C — SECURITY REVIEW 03

**Status:** B — SECURITY REVIEW FAILED / CORRECTIONS REQUIRED
**Datum:** 2026-11-14
**Review-Branch:** `review/mo-rc4-p00-c-security-03`
**Feature-HEAD:** `08fde2386746590cfb37f593d29139bc6c982a59`
**Target:** `release/rc4-integration` @ `4d4db3ba94380b209eee06a913bc37e2fad9be99`
**Modus:** Read-only Multi-Agent-Review; keine Produktcode-, Terraform-, AWS- oder RIS-/Jobsearch-Änderung.

```text
MO-RC4-P00-C — SECURITY REVIEW FAILED / CORRECTIONS REQUIRED
```

Kein CRITICAL-/HIGH-Finding, aber mehrere MEDIUM-Findings mit
Korrektur-/Nachweispflicht. Insbesondere die CMK-IAM-Anforderung
(`DescribeSecret`) ist nicht durch ADR-008/Contract/Q-09 gedeckt, und der
Modul-Cache ist nicht durch einen echten `index.handler`-Test abgesichert.

---

## 1. Ausgangsbasis und Evidence-Klassen

| Feld | Wert |
|---|---|
| Feature-HEAD | `08fde23` |
| Target-HEAD | `4d4db3b` |
| Ancestry | `git merge-base --is-ancestor 4d4db3b 08fde23` = PASS |
| Merge-Tree | konfliktfrei |
| Diff | 11 Dateien: Lambda-Code/Tests/ZIP + Dokumentation |
| Tests | Lambda 400, Installer 669, Builder 128, E2E lokal 32 = **1.229 PASS**; Seed 28 |
| ZIP | `05bc3f65b4b2c385ab4bfc1d74eb0364b2b9041663c3b3beaa438aaa7810a554`, 42.081 B, 12 Module |
| AWS-live | **keine erfolgreiche AWS-Verifikation**; siehe Prozessabweichung §8 |

Evidence-Stufen:

- **IMPLEMENTED:** Code/Dokument vorhanden.
- **LOCAL-TESTED:** Suite/Fake-Probe lokal ausgeführt.
- **INDEPENDENTLY-VERIFIED:** unabhängige Review-Probe mit Fake-Clients.
- **AWS-LIVE-VERIFIED:** nicht erreicht.

---

## 2. Findings

### F-01 — MEDIUM — `secretsmanager:DescribeSecret` ist nicht im akzeptierten IAM-Vertrag

**Datei/Stelle:** `lambda/src/secret_provider.py` (`SecretsManagerProvider._verify_kms_key`), ADR-008 D-5/C-03, P00-Contract §6, Q-09.

**Nachweis:** Der CMK-Pfad ruft `DescribeSecret` auf, um `KmsKeyId` zu prüfen. ADR-008 und Contract §6 nennen nur `secretsmanager:GetSecretValue` und bedingt `kms:Decrypt`; Q-09 autorisiert ebenfalls keine `DescribeSecret`-Aktion. Nur die P00-C-Rollout-Doku und der P00-C-Backlog erwähnen sie.

**Auswirkung:** Wird IAM exakt nach ADR/Contract provisioniert, scheitert jeder CMK-Pfad fail-closed mit 400, bevor `GetSecretValue` aufgerufen wird. Kein Datenleck, aber ein Vertrags- und Betriebsfehler.

**Korrektur:** `DescribeSecret` ausdrücklich in ADR-008 D-5/C-03, Contract §6, Q-09 und Policy-Gate aufnehmen — oder die Runtime-Verifikation entfernen. Keine stillschweigende IAM-Erweiterung.

**Merge-Blocker:** **JA** (Contract-/IAM-Konflikt muss vor Merge- oder Deployment-Freigabe entschieden sein).

---

### F-02 — MEDIUM — Cache überlebt Rotation; kein produktiver Invalidierungspfad

**Datei/Stelle:** `lambda/src/secret_provider.py` (`get_default_secret_provider`, `SecretCache.invalidate`, `reset_default_secret_provider`); `lambda/src/index.py:252`.

**Nachweis:** Der Modul-Provider überlebt Invocations; `invalidate()`/`reset_default_secret_provider()` werden im Produktionscode nicht aufgerufen. Nach einer manuellen Secret-Rotation bleibt das alte Secret in warmen Ausführungsumgebungen gültig, bis die Umgebung ersetzt wird. Die Rollout-Doku beschreibt diesen Zwang nicht ausdrücklich.

**Auswirkung:** Ein kompromittiertes/rotiertes Token kann in warmen Lambdas weiter akzeptiert werden. Der Contract erlaubt Invalidierung durch neues Environment/Deployment, aber der Betriebsablauf und die Risikoakzeptanz sind nicht vollständig dokumentiert.

**Korrektur:** Rollout-/Rollback-Doku um „Rotation/Compromise erfordert forcierten Environment-Recycle“ ergänzen; TTL oder Invalidierung als P00-F/Q-11-Aufgabe dokumentieren. Keine stille Cache-Ewigkeit.

**Merge-Blocker:** **NEIN** für Code-Merge; **JA** für Deployment-Freigabe ohne dokumentierte Risikoakzeptanz.

---

### F-03 — MEDIUM — Kein Test des realen `index.handler`-Pfads mit Secrets Manager

**Datei/Stelle:** `lambda/tests/test_index.py`, `lambda/tests/test_secret_provider.py`.

**Nachweis:** `test_index.py` patcht `index.create_order_service` in allen relevanten Handler-Tests. Der echte Pfad `handler → create_order_service → OrderService → get_default_secret_provider → SecretsManagerProvider` wird mit `PRIVACY_SECRET_PROVIDER=secretsmanager` nicht getestet. Ein Mutationstest, der den Provider wieder pro Invocation erzeugt (M-01-Regression), blieb mit 400/400 Tests grün. Eine unabhängige Fake-boto3-Probe zeigt, dass der Pfad aktuell funktioniert, aber das ist kein committeter Nachweis.

**Auswirkung:** M-01 könnte durch eine spätere Änderung an `index.py:252` unbemerkt regressieren; die Suite bliebe grün.

**Korrektur:** Handler-Test mit Fake-boto3: zwei Invocations, ein Fetch; Wechsel der Secret-Referenz führt zu neuem Fetch; Fehler wird nicht gecacht; kein Request-Feld steuert den Provider.

**Merge-Blocker:** **JA** für die M-01-Akzeptanz; der Code funktioniert nach unabhängiger Probe, aber der geforderte Nachweis fehlt.

---

### F-04 — MEDIUM — Secret-Payload-/Längenvertrag ist nicht explizit

**Datei/Stelle:** `lambda/src/secret_provider.py` (`_load`, `_constant_time_token_match`); `docs/security/AWS-MANAGED-PROVIDER-ROLLOUT.md`.

**Nachweis:** `GetSecretValue.SecretString` wird als gesamter Token-String verwendet. Ein JSON-Payload (`{"token": ...}`) würde als ungültiger Token scheitern; Non-ASCII oder >1024 Zeichen werden fail-closed abgewiesen. Die Doku sagt nur „approved payload format“, ohne exakte Form/Länge.

**Auswirkung:** Fehlkonfigurierte Secrets führen zu schwer diagnostizierbaren 400-Fehlern, nicht zu einer klaren Payload-Validierung.

**Korrektur:** „SecretString = exakt der interne Token, ASCII, 1…1024 Zeichen, keine JSON-Hülle“ im Rollout-/Contract-Dokument festschreiben und testen.

**Merge-Blocker:** **NEIN** für Code; **JA** für Aktivierung.

---

### F-05 — MEDIUM — Rollback-Sequenz ist widersprüchlich

**Datei/Stelle:** `docs/security/AWS-MANAGED-PROVIDER-ROLLOUT.md`.

**Nachweis:** Der Rollback sagt „previous configuration restore“, während §3 das Wiedereinführen von `PRIVACY_INTERNAL_SECRET` nur mit separater Freigabe erlaubt. Es gibt keinen eindeutigen sicheren Rollback-Pfad (z. B. ENV weiter provisioniert lassen oder Code-first-Rollback).

**Auswirkung:** Ein fehlgeschlagener Umschaltversuch kann in einer nicht ausführbaren oder unsicheren Rollback-Situation enden.

**Korrektur:** Zwei konkrete Rollback-Varianten mit Voraussetzungen, Verantwortlichkeit und Freigabe dokumentieren; keine Klartext-Rückkehr ohne Owner-Freigabe.

**Merge-Blocker:** **NEIN** für Code; **JA** für Aktivierung.

---

### F-06 — LOW — Keine begrenzten boto3-Timeouts

**Datei/Stelle:** `lambda/src/secret_provider.py` (`Boto3SecretsManagerFetcher._get_client`), Lambda-Timeout 10 s.

**Nachweis:** boto3-Client wird ohne `Config(connect_timeout/read_timeout/retries)` erzeugt. Ein hängender Secrets-Manager-Aufruf endet im Lambda-Timeout statt als `SecretUnavailable`/400.

**Auswirkung:** Verfügbarkeit/Fehlerklasse, kein Secret-Leak.

**Korrektur:** Explizite Timeouts/Retry-Grenzen in P00-C/P00-E setzen.

**Merge-Blocker:** NEIN.

---

### F-07 — LOW — Nicht-String-Token wird per `str()` verglichen

**Datei/Stelle:** `lambda/src/order_service.py` (`_constant_time_token_match`).

**Nachweis:** `internal_token: 1` kann gegen Secret `"1"` matchen. Das ist eine vorbestehende `str(token)`-Semantik, kein neuer Bypass für realistische High-Entropy-Secrets.

**Korrektur:** `isinstance(..., str)` erzwingen; Typfehler fail-closed.

**Merge-Blocker:** NEIN.

---

### F-08 — LOW — AWS-Fehlercode fehlt im Observability-Event

**Datei/Stelle:** `lambda/src/secret_provider.py` (`log_secret_provider_failure`).

**Nachweis:** Event enthält `event`, `provider`, `errorClass`, aber nicht den whitelisted AWS-`Error.Code`. AccessDenied, Throttling und Timeout sind im Log nicht unterscheidbar.

**Auswirkung:** Betriebliche Diagnose erschwert; keine Secret-Offenlegung.

**Korrektur:** Whitelisted, sanitized `errorCode` ergänzen; keine `Message`/ARN.

**Merge-Blocker:** NEIN.

---

### F-09 — LOW — Policy-Gate-Allowlist deckt Secrets/KMS nicht ab

**Datei/Stelle:** `terraform/policy/resource-policy.json`, `terraform/policy/validate-plan.py`, Rollout-Doku.

**Nachweis:** Keine `aws_secretsmanager_*`/`aws_kms_*`-Typen in der Allowlist; der Wildcard-Check prüft nur `aws_iam_policy`, nicht die Inline-`aws_iam_role_policy` des Handlers. Rollout-Schritt 1/2 nennt den Policy Gate nicht.

**Auswirkung:** P00-E-Terraform kann den Gate derzeit nicht passieren; Q-09 „keine Wildcards“ ist für die relevante Inline-Policy nicht mechanisch geprüft.

**Korrektur:** Policy-Gate-Erweiterung/Inline-Policy-Prüfung als P00-E-Gate; Rollout-Doku ergänzen.

**Merge-Blocker:** NEIN (P00-C enthält keine Terraform-Änderung).

---

### F-10 — LOW — `SecretCache.get_or_load` ist nicht thread-sicher

**Datei/Stelle:** `lambda/src/secret_provider.py:242-254`.

**Nachweis:** Check-then-set ohne Lock; im Lambda-Standardmodell (ein Invocation-Thread pro Environment) benign. Nur unter hypothetischer Thread-Nutzung doppelter Fetch möglich.

**Auswirkung:** Kein Leak; nur zusätzliche Latenz/Calls.

**Korrektur:** Lock oder dokumentierte Single-Thread-Annahme.

**Merge-Blocker:** NEIN.

---

### F-11 — LOW — `id(fetcher)`/`id(descriptor)` im Modul-Cache-Key

**Datei/Stelle:** `lambda/src/secret_provider.py` (`get_default_secret_provider`).

**Nachweis:** Produktionspfad nutzt `None`; Tests injizieren Objekte. Theoretische ID-Wiederverwendung könnte einen veralteten Provider treffen. Die starke Referenz hält das Objekt am Leben, aber der Key ist fragil.

**Korrektur:** Explizite Identitäts-Token statt `id()` oder dokumentierte Test-only-Nutzung.

**Merge-Blocker:** NEIN.

---

### F-12 — LOW — Status-/Scope-Überzeichnung

**Datei/Stelle:** `docs/release/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md`, P00-C-Report.

**Nachweis:** „IMPLEMENTATION COMPLETE“ kann so gelesen werden, als seien Secret-Ressource, IAM, KMS und Policy Gate Teil von P00-C; diese fehlen jedoch und gehören zu P00-E/Infrastruktur. Der Report nennt sie als offene Abhängigkeiten, die Backlog-Zeile ist aber missverständlich.

**Korrektur:** P00-C als „Runtime Integration Complete; IaC/IAM/KMS = P00-E“ bezeichnen.

**Merge-Blocker:** NEIN (Dokumentationskorrektur).

---

## 3. Finding-Nachweisstatus

| Finding | Implementiert | Lokal getestet | Unabhängig verifiziert | AWS-live |
|---|---|---|---|---|
| M-01 Cache Lifetime | JA | JA (Provider-Ebene) | JA (Fake-boto3-Handler-Probe) | NEIN |
| L-01 Non-ASCII | JA | JA | JA | NEIN |
| L-02 Observability | JA | JA | JA (redigiert) | NEIN |
| L-03 KMS-Bindung | JA | JA | JA (Fake) | NEIN |
| L-04 Test-Hardening | JA | JA | teilweise; Handler-Test fehlt (F-03) | NEIN |
| L-06 Rollout | JA | lokal | Dokumentation unvollständig (F-02/F-05) | NEIN |
| L-05 | FIXED | JA | JA | NEIN |

**Kein Finding ist AWS-live-verifiziert.** M-01/L-01…L-04/L-06 dürfen daher nicht als „VERIFIED FIXED“ im Sinne einer Live-Verifikation bezeichnet werden.

---

## 4. Tests / Packaging

| Prüfung | Ergebnis |
|---|---:|
| Lambda | **400 PASS** |
| Installer | **669 PASS** |
| Module Builder | **128 PASS** |
| E2E lokal | **32 PASS** |
| Gesamt | **1.229 PASS** |
| Seed separat | **28 PASS** |
| ZIP SHA-256 | `05bc3f65b4b2c385ab4bfc1d74eb0364b2b9041663c3b3beaa438aaa7810a554` |
| ZIP-Größe | 42.081 Bytes |
| ZIP-Inhalt | 12 Module, `secret_provider.py` enthalten |
| Source/ZIP | 12/12 byte-identisch, keine Mismatches |
| Rebuild | byte-identisch in `/tmp` |
| Merge-Tree | konfliktfrei |

---

## 5. Integration Readiness

- Feature stammt direkt von `4d4db3b` ab.
- Keine Terraform-/AWS-/RIS-/Jobsearch-Änderung.
- Kein Merge, Push, Deployment oder Release-Tag.
- **Merge-Blocker:** F-01 (IAM-/Contract-Drift), F-03 (M-01-Handler-Testnachweis); zusätzlich Deployment-HOLD für F-02/F-04/F-05.
- F-09 (Policy Gate/IAM) blockiert P00-E, nicht den P00-C-Code-Merge.

**Empfehlung:** Kein Merge, bis F-01/F-03 korrigiert und erneut reviewt sind. F-02/F-04/F-05 als Deployment-Gates dokumentieren.

---

## 6. Prozessabweichung / Sicherheitsgrenze

Ein unabhängiger Security-Reviewer hat bei einer lokalen Probe versehentlich
einen **einzigen read-only `GetSecretValue`-Versuch** mit boto3 gegen
`secretsmanager.eu-central-1.amazonaws.com` für einen dummy ARN ausgelöst.
Der Aufruf wurde mit `AccessDeniedException` abgewiesen; es wurde kein Secret
abgerufen, keine Ressource verändert und kein AWS-State geschrieben. Der
Versuch ist **keine Produkt-Evidenz** und wird hier ausdrücklich als
Prozessabweichung dokumentiert. Weitere AWS-Aufrufe wurden nicht ausgeführt.

---

## 7. Git / Review-Artefakt

```text
Review branch: review/mo-rc4-p00-c-security-03
Reviewed feature HEAD: 08fde2386746590cfb37f593d29139bc6c982a59
Target HEAD: 4d4db3ba94380b209eee06a913bc37e2fad9be99
Feature diff: 11 paths
Product code changed by review: NONE
Merge/Push/Terraform/AWS mutation: NONE
```

**STOP vor Merge und Deployment.**
