# F002 — Cognito Authentication

| Feld | Wert |
|------|------|
| **ID** | F002 |
| **Name** | Cognito Authentication |
| **Status** | 🟡 DESIGNED — NOT IMPLEMENTED |
| **Week** | 2 |
| **Abhängigkeiten** | F001 |
| **Fachquelle** | `security/authentication-decision.md` |

## Beschreibung

Benutzer-Authentifizierung via Cognito User Pool; JWT wird vom API-Gateway-JWT-Autorisator
validiert. Authentication (Benutzeridentität) strikt getrennt von IAM (Service-Berechtigungen).

## Tasks

| ID | Task | Status |
|----|------|--------|
| T002-01 | User Pool anlegen (Terraform) | ✅ COMPLETE |
| T002-02 | User Pool Client konfigurieren | ✅ COMPLETE |
| T002-03 | Gruppe `staff` anlegen | ✅ COMPLETE |
| T002-04 | Testbenutzer anlegen (Live, via AWS CLI) | ⏳ PLANNED |
| T002-05 | JWT-Flow verifizieren (Login → Token → geschützter Request) | ⏳ PLANNED |
| T002-06 | Negativ-Tests (401 ohne/ungültiges Token) | ⏳ PLANNED |

> T002-01…T002-03 sind im Rahmen von **F011/T011-05** (Branch `feature/cognito`) per
> Terraform implementiert: `aws_cognito_user_pool.users`,
> `aws_cognito_user_pool_client.app` (USER_PASSWORD_AUTH + Refresh, Public Client),
> `aws_cognito_user_group.staff`. Kein `apply` — Ressourcen erst nach Freigabe erzeugt.

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform fmt/init/validate | PASS (T011-05, Provider 6.60.0) |
| Terraform plan | NOT RUN (zu T011-07) |
| Live: Login + Token | NOT RUN (kein apply) |
| Live: 401-Fälle | NOT RUN (kein apply) |

## Git Checkpoint

- Branch: `feature/cognito` · Commit: offen · Push: offen (Checkpoint-Task)

## Next Step

T002-04 (Testbenutzer anlegen, Live via AWS CLI) — nach `apply` und Freigabe (F011/T011-08).