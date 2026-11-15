# MO-RC4-P00-C-AUTHORIZATION-01

**Status:** A — Q-04/Q-09 APPROVED / IMPLEMENTATION AUTHORIZATION PENDING
**Datum:** 2026-11-13
**Branch:** `release/rc4-integration`
**Ausgangs-HEAD:** `21c1dbcca8d31c3887e333fd8bf27b651234bd12`
**Scope:** Dokumentation und Vertragsprüfung; keine P00-C-/P00-D-Implementierung.

```text
MO-RC4-P00-C — Q-04/Q-09 APPROVED / IMPLEMENTATION AUTHORIZATION PENDING
```

Der Release Owner hat Q-04 und Q-09 unter Vertragsabgleich freigegeben. P00-C
ist damit für eine separate Implementierungsautorisierung vorbereitet; die
Implementierung selbst ist **nicht** gestartet.

---

## 1. Q-04 — CMK-Ownership

| Feld | Entscheidung |
|---|---|
| AWS-verwalteter Standardschlüssel | **APPROVED** — Default für Secrets Manager |
| Bestehende kundeneigene CMK | **APPROVED** — nur explizite ARN-Referenz |
| Neue CMK | **APPROVED nur bei ausdrücklichem Opt-in** |
| Implizite CMK-Erzeugung | **VERBOTEN** |
| Bestehende Verschlüsselungsressourcen | **Keine Änderung** durch bloße SecretProvider-Aktivierung |
| DDB/SQS-CMK | **Nicht durch Q-04 entschieden** — separates P00-E-Thema |

Die Entscheidung ist mit ADR-008 D-5 und dem P00-Implementierungsvertrag §6/§8
konsistent.

---

## 2. Q-09 — Policy-Gate

| Feld | Entscheidung |
|---|---|
| Modell | Explizite Allowlist, Default Deny |
| IAM | Least Privilege |
| Secret-Zugriff | `secretsmanager:GetSecretValue` nur für freigegebene, exakte Secrets |
| KMS | `kms:Decrypt` nur bei tatsächlicher kundeneigener CMK |
| Wildcards | Ohne separate Owner-Entscheidung **verboten** |
| Bestehende Regeln | Bleiben erhalten; keine pauschale Lockerung |

Die Entscheidung ist mit Contract §6/§8/§9 und ADR-008 C-02/C-03 konsistent.

---

## 3. Vertragsprüfung

| Quelle | Prüfung | Ergebnis |
|---|---|---|
| `architecture/architecture-decisions.md` ADR-008 | D-5/C-02/C-03: Referenzen, optionaler Key-ARN, exakte IAM-Nutzung | **KONSISTENT** |
| `docs/contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md` | §6 AWS_MANAGED, §8 KMS, §9 Policy-Gate | **KONSISTENT**; Q-04/Q-09-Status nachgezogen |
| `docs/release/MO-RC4-P00-DECISION-REGISTER.md` | Q-04/Q-09 als entschieden dokumentiert | **KONSISTENT** |
| `docs/release/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md` | P00-C-M01 und L-Findings als Akzeptanzkriterien | **KONSISTENT** |
| `docs/release/RC4-INTEGRATION-MANIFEST.md` | P00-B integriert; P00-C-Authorization pending | **KONSISTENT** |

**Kein Contract-Conflict.** Eine Abgrenzung bleibt ausdrücklich bestehen:
Q-04 betrifft AWS_MANAGED/Secrets Manager; eine DynamoDB-/SQS-CMK-Aktivierung
bleibt P00-E und ist nicht pauschal freigegeben.

---

## 4. P00-C-Akzeptanzkriterien

### M-01 — Effective Cache Lifetime

**Status: OPEN — mandatory.**

- tatsächlichen Provider-/Cache-Lebenszyklus untersuchen;
- modulweiten Cache oder explizite Per-Invocation-Semantik implementieren;
- Cross-Invocation- und Cross-Identity-Isolation testen;
- Rotation und Cache-Invalidierung dokumentieren;
- ENV-Default unverändert lassen.

### Weitere verbindliche Kriterien

| ID | Kriterium | Status |
|---|---|---|
| L-01 | Non-ASCII-Material/Token darf keinen unbehandelten 500 auslösen; fail-closed validieren | **OPEN** |
| L-02 | Sanitized Provider-Observability ohne ARN/Referenz/Secret-Wert | **OPEN** |
| L-03 | `PRIVACY_KMS_KEY_ARN` muss bei CMK tatsächlich wirken oder bis dahin abgelehnt werden | **OPEN** |
| L-04 | Negative Tests für Lazy-Init, Request-Kontext und echte Redaction | **OPEN** |
| L-06 | Atomare Provider-Umschaltung dokumentieren und testen | **OPEN** |

L-05 bleibt **FIXED** (Basiskorrektur `8ddc050`). Keines der offenen Findings
wird ohne Nachweis als behoben markiert.

---

## 5. Abgrenzung

Nicht Teil dieses Auftrags:

- P00-C-Produktimplementierung;
- Secrets-Manager-Ressource, Terraform, IAM oder KMS;
- P00-D APP-MANAGED/HMAC;
- AWS-Mutation, Terraform Apply, Deployment;
- RIS-/Jobsearch-Änderung;
- Push, Main-Merge, Release-Tag.

---

## 6. Status

```text
MO-RC4-P00-C — Q-04/Q-09 APPROVED / IMPLEMENTATION AUTHORIZATION PENDING
Q-04: APPROVED (AWS default / existing ARN / opt-in CMK only)
Q-09: APPROVED (explicit allowlist / default deny / least privilege)
P00-C: READY FOR IMPLEMENTATION AUTHORIZATION — NOT STARTED
P00-C-M01: OPEN
L-01/L-02/L-03/L-04/L-06: OPEN
L-05: FIXED
IMPLEMENTATION / TERRAFORM / AWS: NONE
```

**STOP vor der P00-C-Produktimplementierung.**
