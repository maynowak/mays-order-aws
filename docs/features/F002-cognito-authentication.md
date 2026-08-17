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
| T002-01 | User Pool anlegen (Terraform) | ⏳ PLANNED |
| T002-02 | User Pool Client konfigurieren | ⏳ PLANNED |
| T002-03 | Gruppe `staff` anlegen | ⏳ PLANNED |
| T002-04 | Testbenutzer anlegen (Live, via AWS CLI) | ⏳ PLANNED |
| T002-05 | JWT-Flow verifizieren (Login → Token → geschützter Request) | ⏳ PLANNED |
| T002-06 | Negativ-Tests (401 ohne/ungültiges Token) | ⏳ PLANNED |

## Testnachweise

| Prüfung | Status |
|---------|--------|
| Terraform validate/plan | NOT RUN |
| Live: Login + Token | NOT RUN |
| Live: 401-Fälle | NOT RUN |

## Git Checkpoint

- Branch: `main` · Commit: offen · Push: offen (nach menschlicher Freigabe)

## Next Step

T002-01 (User Pool via Terraform) — nach Freigabe.