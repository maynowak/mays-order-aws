# Features — May's Orders

> Feature-/Task-Dokumentation nach dem Muster des Mays-Job-Matcher-Projekts.
> Statuskonvention: ✅ COMPLETE · ⏳ PLANNED · 🔵 IN PROGRESS · 🟡 DESIGNED · 🚧 BLOCKED · ⚪ NOT VERIFIED.
> Nur Features, die tatsächlich geplant oder umgesetzt sind.

## Feature-Index

| ID | Feature | Week | Status |
|----|---------|------|--------|
| [F001](F001-project-foundation.md) | Project Foundation | 1 | ✅ COMPLETE |
| [F002](F002-cognito-authentication.md) | Cognito Authentication | 2 | 🟡 DESIGNED |
| [F003](F003-api-gateway.md) | API Gateway (HTTP API) | 2 | 🟡 DESIGNED |
| [F004](F004-order-creation.md) | Order Creation | 2 | 🟡 DESIGNED |
| [F005](F005-order-retrieval.md) | Order Retrieval | 2 | 🟡 DESIGNED |
| [F006](F006-order-listing.md) | Order Listing | 2 | 🟡 DESIGNED |
| [F007](F007-status-transition.md) | Status Transition | 3 | 🟡 DESIGNED |
| [F008](F008-concurrent-update-protection.md) | Concurrent Update Protection | 3 | 🟡 DESIGNED |
| [F009](F009-iam-security.md) | IAM / Security | 2–3 | 🟡 DESIGNED |
| [F010](F010-cloudwatch-monitoring.md) | CloudWatch Monitoring | 3–4 | ⏳ PLANNED |
| [F011](F011-terraform-infrastructure.md) | Terraform Infrastructure | 2 | 🟡 DESIGNED |

## Abhängigkeiten

```text
F001 (Foundation)
  ├── F011 (Terraform) ── Basis für F002/F003/F004–F006
  ├── F002 (Cognito)   ── Auth für alle API-Features
  └── F003 (API GW)    ── Routen für F004–F006
F004/F005/F006         ── auf Basis F002/F003
F007/F008              ── erweitern F004 (State Machine, Conditional Writes)
F009                   ── quer (IAM, Least Privilege)
F010                   ── Monitoring für alle
```

## Arbeitsweise

Jedes Feature ist in Tasks (TXXX-01…) zerlegt; jeder Task folgt:

```text
Analyse → Plan → Implementation → Test → Build/Validation → Live Verification
        → Documentation → Git Checkpoint
```

Ein Task ist erst abgeschlossen, wenn die Prüfungen tatsächlich durchgeführt und der
Checkpoint gepusht wurde. Testnachweise in `tests/test-results.md`.