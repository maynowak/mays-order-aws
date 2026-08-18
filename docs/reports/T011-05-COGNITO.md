# T011-05 COGNITO REPORT

> Task-Report: F011/T011-05 — Amazon Cognito (User Pool, App Client, Gruppe `staff`)
> als Terraform-Konfiguration. Git bleibt Source of Truth.

## Summary

Im Rahmen von F011 (Terraform Infrastructure) wurden die drei dokumentierten
Cognito-Komponenten als Terraform-Ressourcen implementiert: **User Pool**,
**App Client** und **Gruppe `staff`**. Grundlage ist die dokumentierte
Auth-Entscheidung (`security/authentication-decision.md`, ADR-003) und das
Feature F002 (`docs/features/F002-cognito-authentication.md`, T002-01…03).

Scope-Grenzen strikt eingehalten: **kein** `aws_cognito_user_pool_domain`
(Login via `USER_PASSWORD_AUTH` benötigt kein Hosted-UI), **kein** API Gateway /
JWT-Authorizer / Lambda-Invoke-Permission (folgt in T011-06), **kein** `apply`,
**keine** AWS-Ressourcen erzeugt.

**Voraussetzung (Abschnitt 3–4 der Vorgabe):** Die abgeschlossene
Python-3.14-Migration musste zuerst auf `main` sein. Sie war es nicht
(`main` = `ce4b62e`, Branch `feature/lambda-python-314` = `d64f583`) →
zuerst per `git merge --no-ff feature/lambda-python-314` nach `main`
integriert (Merge-Commit `20bfb05`, Push SUCCESS). `feature/lambda-python-314`
bleibt erhalten. Danach `feature/cognito` von `main` erstellt.

## Baseline

| Komponente | Wert |
|------------|------|
| Branch (vor T011-05) | `main` HEAD `20bfb05` (Merge der Python-3.14-Migration) |
| Feature-Branch | `feature/cognito` (neu, von `main`) |
| Fachquelle | `security/authentication-decision.md` (ADR-003), F002 (T002-01…03), `security/iam-design.md` |
| AWS-Provider | `~> 6.0` / 6.60.0 (unverändert, kein Downgrade) |
| Terraform-Dateien | `terraform/main.tf`, `terraform/outputs.tf` |

## Implementierte Ressourcen

| Ressource | Terraform-Typ | Name | Konfiguration / Begründung |
|-----------|---------------|------|---------------------------|
| User Pool | `aws_cognito_user_pool.users` | `${var.project_name}-users` (mays-orders-users) | `admin_create_user_config.allow_admin_create_user_only = true` (Staff-Admin-Anlage via AWS CLI, T002-04; keine offene Selbst-Registrierung — keine Signup-Anforderung dokumentiert); Passwortrichtlinie Standardwerte (min. 8, Upper/Lower/Number/Symbol; `authentication-decision.md` §6); `mfa_configuration = "OFF"` (Standard, §6) |
| App Client | `aws_cognito_user_pool_client.app` | `${var.project_name}-client` (mays-orders-client) | `explicit_auth_flows = [ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH]` (JWT-Flow §3); `generate_secret = false` — Public Client, Voraussetzung für `USER_PASSWORD_AUTH`; kein App-Client-Secret im Repo |
| Gruppe | `aws_cognito_user_group.staff` | `staff` | Claim `cognito:groups` im Access Token → Basis der Authorization (A-09, §5; `security/iam-design.md`) |

> **Provider-Hinweis:** AWS-Provider 6.60.0 stellt die Ressource als
> `aws_cognito_user_group` bereit (nicht `aws_cognito_user_pool_group`).
> Beim ersten `terraform validate` wurde `Invalid resource type` gemeldet;
> die Ressource wurde auf den in 6.60.0 gültigen Typ umgestellt
> (`terraform providers schema -json` verifiziert).

### Bewusst NICHT in T011-05

- `aws_cognito_user_pool_domain` — `USER_PASSWORD_AUTH`-Login benötigt kein
  Hosted-UI/OAuth-Redirect (`terraform/README.md`: Domain nur "falls nötig").
- API Gateway / HTTP API / JWT-Authorizer / `aws_lambda_permission` — T011-06.
- Testbenutzer / Login-Live-Test — T002-04…06 (nach `apply`/Freigabe).
- Keine IAM-User, keine Access Keys (TR-15), keine Secrets.

## Changed Files

| Datei | Art | Zweck |
|-------|-----|-------|
| `terraform/main.tf` | geändert | Cognito: `aws_cognito_user_pool.users`, `aws_cognito_user_pool_client.app`, `aws_cognito_user_group.staff` |
| `terraform/outputs.tf` | geändert | `cognito_user_pool_id`, `cognito_user_pool_arn`, `cognito_user_pool_client_id`, `cognito_user_pool_group_name` |
| `terraform/README.md` | geändert | §2.4 Cognito (Ressourcentabelle, JWT-Flow, bewusste Nicht-Features), Ressourcentabelle §3 |
| `docs/features/F002-cognito-authentication.md` | geändert | T002-01…03 COMPLETE, Testnachweise, Next Step |
| `docs/features/F011-terraform-infrastructure.md` | geändert | T011-05 COMPLETE, Progress/Changes/Current Checkpoint |
| `docs/PROJECT_STATUS.md` | geändert | Status, Checkpoint-Tabelle, Phase-Level, Feature-Status |
| `docs/reports/WEEK-02.md` | geändert | Wochenreport (T011-05, Integration, Validation) |
| `docs/CHANGELOG.md` | geändert | Changelog-Eintrag T011-05 |
| `docs/reports/T011-05-COGNITO.md` | neu | dieser Report |

## Outputs (terraform/outputs.tf)

```text
cognito_user_pool_id          → aws_cognito_user_pool.users.id
cognito_user_pool_arn         → aws_cognito_user_pool.users.arn
cognito_user_pool_client_id   → aws_cognito_user_pool_client.app.id
cognito_user_pool_group_name  → aws_cognito_user_group.staff.name
```

## Validation

- `terraform fmt` — PASS
- `terraform init` (AWS-Provider ~> 6.0 / 6.60.0, Lock-File wiederverwendet) — PASS
- `terraform validate` — PASS (ohne Warnungen)
- `terraform plan` — NOT RUN (gehört laut Projektplan zu T011-07, nicht vorgezogen)
- `terraform apply` — NOT RUN (keine AWS-Ressourcen erzeugen; Freigabe erforderlich)
- `git diff --check` — PASS
- Secret-Audit — PASS (grep auf AKIA/Access-Key/Secret/Private-Key-Muster über das
  gesamte Repo inkl. terraform/: keine Treffer)
- Live/Login-Tests — NOT RUN (kein apply)

## Security

- Keine Secrets in Terraform (kein App-Client-Secret — Public Client).
- Benutzer-Auth ausschließlich über Cognito → JWT (ADR-003, TR-15).
- Keine offene Registrierung (Admin-Create-User) — keine unautorisierten Benutzer.
- Auth (Benutzeridentität) strikt getrennt von IAM (Service-Berechtigungen).
- Least Privilege: Cognito-Ressourcen vergeben keine Cross-Service-Rechte
  (keine `role_arn`/IAM-Bindung in T011-05).

## Known Limitations

- Kein `user_pool_domain`: Sollte später ein Hosted-UI oder OAuth-Flow (z. B.
  für einen echten Client mit Redirect) nötig sein, ist
  `aws_cognito_user_pool_domain` separat zu ergänzen (dokumentiert).
- MFA ist OFF (Standard). Aktivierung von MFA wäre eine Verfeinerung (§6) und
  ist nicht Teil der aktuellen Anforderung.
- Passwortrichtlinie und MFA folgen AWS-Standardwerten — bewusst keine
  abweichende Konfiguration ohne dokumentierte Anforderung.
- Ressourcen werden erst bei `apply` (T011-08, nach Freigabe) real erzeugt;
  bis dahin keine Live-Verifizierung (Login/Token/401).

## Git Checkpoint

- Branch: `feature/cognito` (Feature-Branches werden **nicht** gelöscht)
- Vorher: `main` = `20bfb05` (Merge Python-3.14-Migration)
- Commit: TBD · Push: offen (nach menschlicher Freigabe)
- Danach: `git merge --no-ff feature/cognito` nach `main` + Push

## Current Project State

- Cognito: **CONFIGURED** (Terraform T011-05) — NOT CREATED (kein apply)
- AWS Resources: NONE
- F011 IN PROGRESS · T011-01…05 COMPLETE · T011-06 NEXT
- F002: T002-01…03 COMPLETE (Terraform) · T002-04…06 PLANNED (nach apply)

## Next Step

T011-06 — HTTP API + Routen + Authorizer — separater Task / Prompt. STOP.
