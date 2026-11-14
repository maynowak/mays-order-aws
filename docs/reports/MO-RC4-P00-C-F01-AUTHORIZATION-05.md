# MO-RC4-P00-C-F01-AUTHORIZATION-05

**Status:** A — F-01 CONTRACT AMENDED / F-03 VERIFIED / RE-REVIEW READY
**Datum:** 2026-11-14
**Branch:** `feature/mo-rc4-p00-c-f01-authorization-05`
**Basis:** Correction-HEAD `d3ce23749d31642ef303b5e71b7df6b0721e62e8`
**Feature-HEAD:** `08fde2386746590cfb37f593d29139bc6c982a59`
**Integration-HEAD:** `4d4db3ba94380b209eee06a913bc37e2fad9be99`

```text
MO-RC4-P00-C — F-01 CONTRACT AMENDED / F-03 VERIFIED / RE-REVIEW READY
```

Q-09 ist als **Limited Amendment** für `secretsmanager:DescribeSecret`
freigegeben. Die Verträge sind konsistent aktualisiert. F-01 ist noch **nicht**
`VERIFIED FIXED`; dafür ist das unabhängige Re-Review erforderlich.

---

## 1. Owner-Entscheidung

**APPROVED — LIMITED AMENDMENT** für:

```text
secretsmanager:DescribeSecret
```

Nur für dieselben explizit freigegebenen Secret-ARNs; ausschließlich zur
KMS-Metadatenverifikation; keine Wildcards; `GetSecretValue` bleibt exakt
beschränkt; `kms:Decrypt` nur bei tatsächlicher kundeneigener CMK; keine
implizite CMK; keine DDB-/SQS-CMK-Erweiterung; Default Deny bleibt.

Keine AWS-Mutation und keine Infrastrukturfreigabe durch diese Entscheidung.

---

## 2. Vertragsänderungen

| Quelle | Änderung |
|---|---|
| `architecture/architecture-decisions.md` | ADR-008 D-5 ergänzt `DescribeSecret` auf demselben exakten Secret-ARN, nur bei CMK-Metadatenprüfung; C-03 nachgezogen |
| `docs/release/MO-RC4-P00-DECISION-REGISTER.md` | Q-09 `DECIDED — LIMITED AMENDMENT`; Owner-Entscheidung dokumentiert |
| `docs/contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md` | §6 Metadata-IAM-Zeile, §8 Amendment-Regel, Cache-Scope präzisiert |
| `docs/TERRAFORM_POLICY_GATE.md` | P00-E-Spezifikation für Secrets/KMS, exakte ARNs, Inline-IAM-Wildcard-Prüfung; **nicht implementiert** |
| `docs/release/MO-RC4-P00-C-F01-Q09-AMENDMENT-PROPOSAL.md` | Status auf `APPROVED — LIMITED AMENDMENT / CONTRACT AMENDED` gesetzt |
| `docs/release/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md` | F-01 `CONTRACT AMENDED / RE-REVIEW PENDING` |
| `docs/release/MO-RC4-P00-EXECUTION-PLAN.md` | P00-C-Status auf Contract-Amendment/Re-Review aktualisiert |

**Runtime-Abgleich:** `DescribeSecret` wird nur aufgerufen, wenn
`PRIVACY_KMS_KEY_ARN` gesetzt ist; der Standardpfad nutzt ausschließlich
`GetSecretValue`. Keine DDB-/SQS-CMK-Änderung, keine Wildcards, keine
implizite CMK.

---

## 3. F-01-Status

```text
F-01: CONTRACT AMENDED / RE-REVIEW PENDING
```

Nicht `VERIFIED FIXED`. Die Owner-Freigabe und die Vertragskonsistenz sind
dokumentiert; die unabhängige Re-Review-Evidenz fehlt noch.

---

## 4. F-03-Evidence

Validiert aus CORRECTION-04, ohne erneute Implementierung:

- `lambda/tests/test_index_aws_managed.py`
- echter `index.handler`-Pfad
- zwei aufeinanderfolgende Invocations
- ein gemeinsamer Modul-Provider/Cache
- genau ein `GetSecretValue`
- Identity-Isolation bei Referenzwechsel
- Cache-Invalidierung
- negative Provider-Konfiguration ohne Fetch
- Mutation mit per-Invocation-Provider lässt den Test fehlschlagen

Zielgerichtete Tests: `test_index_aws_managed` + `test_secret_provider` = **60 PASS**.

---

## 5. Deployment-Gates

Unverändert offen:

- **F-02:** Rotation/Cache-Recycle und Risiko paralleler alter/neuer Umgebungen.
- **F-04:** exakter SecretString-Payload-/ASCII-/Längenvertrag.
- **F-05:** Rollback-Semantik und Owner-Freigaben.
- **F-06/F-08/F-09/F-10/F-11:** Low/INFO; P00-E- oder Observability-Follow-ups.
- F-09 Policy-Gate-Code/Allowlist ist **nicht** implementiert; nur die
  Spezifikation wurde ergänzt.

Keine Secrets-Manager-/IAM-/KMS-Ressource, keine Umschaltung, keine Rotation
und kein Rollback wurden ausgeführt.

---

## 6. Tests

| Prüfung | Ergebnis |
|---|---:|
| Zieltests F-03/Provider | **60 PASS** |
| Lambda gesamt (vorherige Evidence) | **405 PASS** |
| Installer | **669 PASS** |
| Module Builder | **128 PASS** |
| E2E lokal | **32 PASS** |
| Gesamt lokal | **1.234 PASS** |
| Seed | **28 PASS** |
| `git diff --check` | **PASS** |

Es wurden keine Produktcode- oder Testkonfigurationsänderungen vorgenommen;
daher keine erneute vollständige Regression erforderlich. Keine Live-AWS-Aufrufe.

---

## 7. Git-Integrationsplan

Aktuelle Abstammung:

```text
feature/mo-rc4-p00-c-aws-managed @ 08fde23
  └─ review/mo-rc4-p00-c-security-03 @ 41b8612
      └─ feature/mo-rc4-p00-c-correction-04 @ d3ce237
          └─ feature/mo-rc4-p00-c-f01-authorization-05 @ HEAD
```

Vorgesehener späterer Integrationsplan (nicht ausgeführt):

1. Unabhängiges Re-Review des F01-Branches.
2. Merge `feature/mo-rc4-p00-c-aws-managed` nach `release/rc4-integration`
   (`--no-ff`).
3. Merge des Correction-/F01-Branches nach dem Feature-Merge; da Feature ein
   Ancestor ist, entstehen keine doppelten Produktcommits.
4. Review-/Korrektur-Dokumentation wird bewusst mitgeführt; kein separater
   Merge des Review-Branches.
5. Keine Integration vor Re-Review und Owner-Merge-Freigabe.

Keine Änderung am Integrationsbranch. Kein Merge, Push oder Deployment.

---

## 8. Commits

| Commit | Inhalt |
|---|---|
| `e800906e69c3cafe8ff09e6ea0031b9f2987801b` | F-03 Handler-Regressionstest |
| `2d4a8de9b5e1542c01c43d67092c80f9a33f5f92` | F-01-Vorschlag und Deployment-Gates |
| `d3ce23749d31642ef303b5e71b7df6b0721e62e8` | Correction-04 Commit-Evidenz / Basis |
| `5cb0b0bf1a089c28ee55f635cc8e944e12f07f15` | Q-09 Contract Amendment, Decision Register, ADR, Contract, Policy-Gate-Spezifikation, Backlog, Auditlog, Report |

## 9. Status

```text
MO-RC4-P00-C — F-01 CONTRACT AMENDED / F-03 VERIFIED / RE-REVIEW READY
F-01: CONTRACT AMENDED / RE-REVIEW PENDING
F-03: VERIFIED
F-02/F-04/F-05: DEPLOYMENT GATES OPEN
POLICY GATE: SPECIFIED ONLY — P00-E IMPLEMENTATION PENDING
AWS-LIVE: NOT VERIFIED
```

**STOP vor Merge und Deployment. Unabhängiges Re-Review erforderlich.**
