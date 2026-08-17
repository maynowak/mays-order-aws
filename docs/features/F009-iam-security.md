# F009 — IAM / Security

| Feld | Wert |
|------|------|
| **ID** | F009 |
| **Name** | IAM / Security |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2–3 |
| **Abhängigkeiten** | F002, F011 |
| **Fachquelle** | `security/iam-design.md`, `security/authentication-decision.md` |

## Beschreibung

IAM Least Privilege für Lambda (DynamoDB-Aktionen + Logs, kein `Scan`/`DeleteItem`),
Resource-Based Policy für API-GW → Lambda, Trennung Auth vs. IAM, keine Secrets,
kein PII im Log, Authorization via `cognito:groups`.

## Tasks

| ID | Task | Status |
|----|------|--------|
| T009-01 | IAM-Rolle + Policy (Least Privilege) in Terraform | ⏳ PLANNED |
| T009-02 | Lambda-Invoke-Permission (Resource-Based) | ⏳ PLANNED |
| T009-03 | Authorization-Logik (Group `staff`) | ⏳ PLANNED |
| T009-04 | Log-Sanitization (keine Tokens/PII) | ⏳ PLANNED |
| T009-05 | Secret-Audit in Checkpoints (dauerhaft) | ✅ COMPLETE (Prozess etabliert) |
| T009-06 | Negativ-Tests (401/403) | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform plan (Policy-Review) | NOT RUN |
| Live: unauthentifiziert → 401 | NOT RUN |
| Live: ohne Berechtigung → 403 | NOT RUN |
| Secret-Audit | PASS (bisherige Checkpoints) |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen

## Next Step

T009-01 (IAM-Rolle) — nach Freigabe.