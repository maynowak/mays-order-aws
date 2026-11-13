# MO-RC4-P00-OWNER-DECISION-02

**Owner-Entscheidung zur Foundation-Architektur**

**Datum:** 2026-11-13
**Branch:** `release/rc4-integration`
**Basis:** `f2c41a077a724a09a67b08b8b442b98b094f86c5`
**RC3-Baseline:** `086a8bea4c608724d400de834c21df5456b7ccac`
**Modus:** Dokumentation und Read-only-Abgleich; keine Produkt-/Terraform-/AWS-
Änderung, kein Push, kein Merge, kein Tag, kein Deployment.

---

## 1. Entscheidung

| ID | Gegenstand | Owner-Entscheidung | Status |
|---|---|---|---|
| Q-02 | Secret-Backend | AWS Secrets Manager | **APPROVED** |
| Q-08 | Secret-Zustellung | ARN/Name-Referenz in der Konfiguration + Laufzeit-Fetch; kein Klartext-Secret in Env | **APPROVED** |
| Q-10 | ADR-008 | Erst nach konkretem ADR-008/Contract-Abgleich | **PENDING** |

Q-02 und Q-08 sind damit entschieden. Die Entscheidungen legen Backend und
Referenz-/Fetch-Richtung fest. Sie autorisieren **keine** Produktimplementierung.

---

## 2. Q-02 — Secrets Manager

**Entschieden:** `AWS_MANAGED` verwendet AWS Secrets Manager.

Verbindliche Grenzen:

- Das Secret wird zur Laufzeit geladen.
- Die Lambda-Konfiguration enthält keine Secret-Werte.
- IAM erhält `secretsmanager:GetSecretValue` nur auf dem exakten Secret-ARN.
- Ein optionaler CMK-Pfad bleibt eine separate Entscheidung (Q-04/Q-09).
- Kein stiller Fallback auf `env`.
- Keine Secret-Werte in Git, Logs, Reports, Terraform-Outputs oder State.

Die Entscheidung schließt Q-02, aber nicht P00-C. P00-C bleibt durch Q-04, Q-09
und Q-10 sowie die Paketfreigabe blockiert.

---

## 3. Q-08 — ARN/Name-Referenz + Laufzeit-Fetch

**Entschieden:** Option (a) — Referenz in der Konfiguration, Secret-Fetch zur
Laufzeit; kein Klartext-Secret in Env.

Verbindliche Grenzen:

- `PRIVACY_SECRET_PROVIDER` und eine ARN-/Namensreferenz bilden die
  Konfigurationsfläche.
- Konfliktbehaftete Provider-Konfiguration wird fail-closed abgelehnt.
- Request-/Body-/Header-Daten dürfen keine Secret-Referenz auswählen.
- Der `env`-Default bleibt unverändert.
- Die exakte Validierungsfläche folgt dem P00-Implementierungsvertrag; jede
  Abweichung benötigt einen dokumentierten Contract-Change.

Die Entscheidung schließt Q-08, aber nicht P00-B. P00-B bleibt durch Q-10 und
die Paketfreigabe blockiert.

---

## 4. Q-10 — ADR-008

Der konkrete Abgleich liegt in:

`docs/release/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md`

Ergebnis:

- **Kein harter Architekturkonflikt.**
- **7 Klarstellungen** C-01…C-07.
- **2 Governance-Punkte:** Legacy-Frage-Nummern in ADR-008, ADR-006-Status.
- ADR-008 bleibt **PROPOSED**.
- Q-10 ist **nicht freigegeben**.

Vor einer Q-10-Freigabe sollte der Owner die Klarstellungen C-01…C-07
bestätigen und anschließend ADR-008 auf `ACCEPTED` setzen. Der Commander ändert
den ADR-Status nicht eigenmächtig.

---

## 5. Auswirkung auf die Arbeitspakete

| Paket | Auswirkung |
|---|---|
| P00-B SecretProvider Foundation | Q-08 entschieden; **blockiert durch Q-10** und Paketfreigabe |
| P00-C AWS_MANAGED | Q-02/Q-08 entschieden; **blockiert durch Q-04/Q-09/Q-10** |
| P00-D APP_MANAGED | unverändert; Q-10/Q-11 offen |
| P00-E KMS/Terraform/IAM | unverändert; Q-04/Q-09/Q-10 offen |
| P00-F Rotation | unverändert; Q-11 offen |
| P00-G Retention/TTL | unverändert; Q-05/Q-06/Q-07/Q-14 offen |
| P00-H Installer/Builder | unverändert; Q-03/Q-08/Q-09 offen (Q-08 entschieden) |
| P00-I Security/Regression | unverändert; alle Pakete und Q-12/Q-13 offen |

Es wurde kein Feature-Branch und keine Implementierung gestartet.

---

## 6. Dokumentationswirkung

Aktualisiert:

- `docs/release/MO-RC4-P00-DECISION-REGISTER.md`
- `docs/release/MO-RC4-P00-ADR-008-CONTRACT-COMPARISON.md` (neu)
- `docs/contracts/MO-RC4-P00-IMPLEMENTATION-CONTRACT.md`
- `docs/reports/MO-RC4-P00-A-SECURITY-ARCHITECTURE-DECISION.md`
- `docs/reports/MO-RC4-P00-OPEN-QUESTIONS.md`
- `docs/reports/MO-RC4-P00-ORCHESTRATION-01.md`
- `docs/release/MO-RC4-P00-IMPLEMENTATION-BACKLOG.md`
- `docs/release/MO-RC4-P00-EXECUTION-PLAN.md`
- `docs/release/MO-RC4-P00-DEPENDENCY-GRAPH.md`
- `docs/release/RC4-INTEGRATION-MANIFEST.md`
- `docs/PROJECT_STATUS.md`
- `docs/AI_AUDITLOG.md`

---

## 7. Status

```text
MO-RC4-P00-OWNER-DECISION-02
Q-02: APPROVED (Secrets Manager)
Q-08: APPROVED (ARN/name reference + runtime fetch)
Q-10: PENDING (ADR-008 comparison complete; clarifications C-01…C-07)
IMPLEMENTATION: NOT STARTED
PUSH / MERGE / TAG / DEPLOY: NOT PERFORMED
```

**STOP — keine P00-Implementierung ohne Q-10-Klärung und separate
Paketfreigabe.**
