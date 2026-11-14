# MO-RC4-P00-C-CORRECTION-04

**Status:** A — F-03 VERIFIED / F-01 OWNER DECISION PENDING
**Datum:** 2026-11-14
**Branch:** `feature/mo-rc4-p00-c-correction-04`
**Basis:** Review-HEAD `41b86121e5d6d6e185e0edeb9b7a77aac195c412`
**Feature-HEAD:** `08fde2386746590cfb37f593d29139bc6c982a59`
**Integration-HEAD:** `4d4db3ba94380b209eee06a913bc37e2fad9be99`

```text
MO-RC4-P00-C — F-03 VERIFIED / F-01 OWNER DECISION PENDING
```

Der Handler-Regressionstest für AWS_MANAGED ist implementiert und verifiziert.
F-01 bleibt bis zur ausdrücklichen Owner-Entscheidung **OPEN**. F-02/F-04/F-05
sind als Deployment-Gates präzisiert, nicht als erledigt markiert.

---

## 1. F-01 — Vertragsentscheidung (Vorschlag, nicht freigegeben)

Erstellt:

`docs/release/MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md`

Vorgeschlagen wird eine **Q-09 Amendment** für dieselben explizit freigegebenen
Secret-ARNs:

- `secretsmanager:GetSecretValue` (bestehend)
- `secretsmanager:DescribeSecret` (neu, nur CMK-Metadatenprüfung)
- `kms:Decrypt` nur bei tatsächlicher kundeneigener CMK
- keine Resource-/Action-Wildcards
- keine implizite CMK-Erzeugung
- keine DDB-/SQS-CMK-Erweiterung
- Default Deny bleibt bestehen

Enthaltene Änderungsvorlagen:

- ADR-008 D-5/C-03
- Decision Register Q-09
- Implementation Contract §6/§8
- Policy-Gate-Allowlist und Inline-IAM-Prüfung

**Status: PROPOSED / OWNER DECISION PENDING.** Keine ADR-, Contract-, Q-09-
oder Policy-Gate-Änderung wurde als genehmigt übernommen.

---

## 2. F-03 — Handler-Regression (verifiziert)

Neu:

`lambda/tests/test_index_aws_managed.py`

Der Test verwendet den echten `index.handler`-Pfad und mockt boto3 vollständig
über ein injiziertes Fake-Modul. Geprüft werden:

1. zwei aufeinanderfolgende Invocations;
2. ein gemeinsamer Modul-Provider/Cache (nur ein `GetSecretValue`);
3. Provider-Neuaufbau bei geänderter Secret-Referenz;
4. Cache-Invalidierung mit erneutem Fetch;
5. negative Provider-Konfiguration ohne Fetch;
6. falscher Token ohne Secret-Leak.

**Mutationsevidenz:** In einer temporären Kopie wurde `index.handler` so
verändert, dass pro Invocation ein neuer Provider erzeugt wird. Der neue Test
schlägt dann fehl; der Produktstand bleibt unverändert.

Der Test enthält keinen echten AWS-Endpoint und keine echten Credentials.

---

## 3. F-02 / F-04 / F-05 — Deployment-Gates

Aktualisiert:

`docs/security/AWS-MANAGED-PROVIDER-ROLLOUT.md`

### F-02 — Rotation

- Modul-Cache überlebt Invocations, ohne TTL.
- `invalidate()`/`reset_default_secret_provider()` sind kontrollierte Hooks,
  keine automatische Rotation.
- Manuelle Rotation wird in warmen Umgebungen erst nach erzwungenem
  Environment-Recycle wirksam.
- Parallele alte/neue Ausführungsumgebungen können kurzzeitig den alten Token
  akzeptieren.
- Keine automatische Rotation implementiert; Q-11/P00-F bleibt separat.

### F-04 — Secret-Payload

- `SecretString` enthält ausschließlich den internen Token.
- ASCII, 1…1024 Zeichen, keine JSON-Hülle, kein Zusatzpayload.
- Leer/nicht-ASCII/zu lang → fail-closed.
- Keine Secret-Werte in Logs/Fehlern.

### F-05 — Rollback

Zwei widerspruchsfreie Pfade:

- **A:** Forward-Fix in AWS_MANAGED (bevorzugt), kein Klartext-ENV.
- **B:** Kontrollierter ENV-Rollback nur mit separater Owner-Freigabe,
  out-of-band provisioniertem Secret und Environment-Recycle; niemals
  automatischer Fallback.

---

## 4. Gate D — AWS-SDK-Test-Sicherheitsgrenze

- Der neue Handler-Test injiziert ein Fake-`boto3`-Modul; `boto3.client`
  liefert ausschließlich einen Fake-Secrets-Manager-Client.
- Keine echten AWS-Endpunkte, keine echten Credentials, keine Live-Aufrufe.
- Der unbeabsichtigte read-only `GetSecretValue`-Versuch aus Review-03 ist
  dokumentiert: Zugriff wurde mit `AccessDeniedException` abgewiesen, kein
  Secret abgerufen, keine Mutation, keine Produkt-Evidenz.
- Die Testgrenze ist lokal; ein vollständiger Netzwerk-Guard für alle künftigen
  Tests bleibt eine CI-Härtungsempfehlung, ist aber nicht Teil dieses
  Korrekturpakets.

---

## 5. LOW-Findings

| ID | Status | Begründung |
|---|---|---|
| F-06 | **OPEN** | boto3-Timeouts benötigen Owner-/Infra-Werte; keine eigenmächtigen Timeout-Änderungen |
| F-07 | **OPEN** | Nicht-String-Token-Coercion ist vorbestehend; kein realistischer Bypass nachgewiesen |
| F-08 | **OPEN** | AWS-Error-Code im Event ist eine Observability-Erweiterung, keine Merge-Korrektur |
| F-09 | **OPEN — P00-E** | Policy-Gate-Allowlist/Inline-IAM-Prüfung bleibt P00-E |
| F-10 | **OPEN — INFO** | Cache-Lock ist bei Lambda-Single-Thread benign; keine Architekturänderung ohne Notwendigkeit |
| F-11 | **OPEN — INFO** | `id()`-Cache-Key ist im Produktionspfad `None`; Test-only-Risiko |
| F-12 | **DOCUMENTED** | P00-C-Scope als Runtime-Integration; IaC/IAM/KMS bleiben P00-E |

Keines dieser Findings wurde ohne Nachweis als behoben markiert.

---

## 6. Tests

| Suite | Ergebnis |
|---|---:|
| Lambda | **405 PASS** |
| Installer | **669 PASS** |
| Module Builder | **128 PASS** |
| E2E lokal | **32 PASS** |
| **Gesamt lokal** | **1.234 PASS** |
| Seed separat | **28 PASS** |

Neue Tests: **5** (`test_index_aws_managed.py`).

ZIP:

```text
lambda/dist/lambda.zip
42.081 Bytes
SHA-256 05bc3f65b4b2c385ab4bfc1d74eb0364b2b9041663c3b3beaa438aaa7810a554
12 Module, secret_provider.py enthalten
keine Runtime-Änderung durch F-03
```

---

## 7. Git

```text
Correction branch: feature/mo-rc4-p00-c-correction-04
Base:              review/mo-rc4-p00-c-security-03 @ 41b8612
Feature HEAD:      08fde23 (unverändert)
Integration HEAD:  4d4db3b (unverändert)
Product code changed: NO (test-only + docs)
Merge/Push/Deploy: NONE
```

### Commit-Gates

| Gate | Commit |
|---|---|
| F-03 Handler-Test | `e800906e69c3cafe8ff09e6ea0031b9f2987801b` |
| F-01/F-02/F-04/F-05 Docs | `2d4a8de9b5e1542c01c43d67092c80f9a33f5f92` |
| Abschluss-Evidenz | `2d4a8de9b5e1542c01c43d67092c80f9a33f5f92` |

---

## 8. Status

```text
MO-RC4-P00-C — F-03 VERIFIED / F-01 OWNER DECISION PENDING
F-01: OWNER DECISION PENDING (Q-09 amendment proposal)
F-03: VERIFIED (handler-level test + mutation proof)
F-02/F-04/F-05: DOCUMENTED DEPLOYMENT GATES
F-06/F-07/F-08/F-09/F-10/F-11: OPEN / P00-E or INFO
F-12: DOCUMENTED
```

**STOP vor erneuter Merge-Freigabe; unabhängiges Re-Review erforderlich.**
