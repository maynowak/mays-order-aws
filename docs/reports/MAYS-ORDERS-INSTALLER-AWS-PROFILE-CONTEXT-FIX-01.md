# MAYS-ORDERS-INSTALLER-AWS-PROFILE-CONTEXT-FIX-01

## Ausgangslage
`./Mays-Order-AWS-installer --profile mayaws ... identity` meldete Account `992382612204`
(Default-Kette, maymilly), während `aws sts get-caller-identity --profile mayaws`
Account `240571105849` (Mayaws) liefert. Profil, Account-ID und Terraform-Kontext
waren im Installer nicht konsistent.

## Befunde (verifiziert)
1. **Argparse-Shadowing (Root Cause):** Der `identity`-Subparser definierte eigene
   `--profile`/`--region`-Optionen mit Env-Defaults. Ohne identity-spezifische Flags
   überschrieb der Subparser-Default (`None`) den global übergebenen Wert `--profile
   mayaws`. Ergebnis: `context.aws_profile` leer → Validierung über Default-Kette →
   falsche Identität `992382612204`.
2. **Globale `os.environ`-Mutationen:** `InstallationContext.__post_init__` und
   `InstallerCLI._create_context` setzten global `TERRAFORM_WORKSPACE`;
   `TerraformRunner.__init__` las den Workspace aus `os.environ` statt aus dem
   Kontext. Parallele Projekte teilten sich damit implizit einen Prozess-globalen
   Zustand.
3. **Statische Credentials konnten Profil still überstimmen:**
   `TerraformRunner._get_terraform_env` vererbte `os.environ` vollständig und legte
   nur `AWS_PROFILE` darüber. `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/
   `AWS_SESSION_TOKEN` aus der Umgebung hätten für Terraform/boto3 Vorrang vor dem
   validierten Profil gehabt.
4. **Doppelte tote Methoden** in `installer/terraform/runner.py` (zwei
   `_get_terraform_env`, ein toter `_ensure_workspace`-Stub vor der echten
   Implementierung).
5. **Runner ohne Workspace:** Kein `TerraformRunner(...)`-Aufruf in `cli/main.py`
   übergab `workspace`; alles hing am globalen Env-Var.

## Fixes (minimal, keine neue Architektur)
- `installer/cli/main.py`
  - `identity`-Subparser: `--profile`/`--region` auf `default=argparse.SUPPRESS`,
    damit globale Werte nicht überschrieben werden.
  - `_create_context`: keine `os.environ`-Mutation mehr; Workspace =
    `project_name` (explizit auf Kontext).
  - Neues `_make_runner(context, dir)`: übergibt
    `workspace=context.terraform_workspace` explizit; alle 11 Aufrufstellen
    umgestellt.
- `installer/core/context.py`: `__post_init__` mutiert `os.environ` nicht mehr.
- `installer/core/aws_context.py`
  - `find_static_credentials()` + Fail-closed: Profil + statische Credentials
    gesetzt → `AWSValidationError` mit STOP-Anweisung (statt stiller
    Fehlidentität).
  - `to_env()` liefert zusätzlich `AWS_DEFAULT_REGION`.
  - `get_environment()` baut explizites Subprozess-Env, strippt bei
    Profil-Modus statische Credentials + `AWS_DEFAULT_PROFILE`, mutiert
    `os.environ` nie.
- `installer/terraform/runner.py`
  - Tote Duplikate entfernt; einziges `_get_terraform_env()` nutzt
    `get_environment()`; `__init__` liest Workspace nur noch aus Parameter.
- `installer/core/command_service.py`: Runner mit explizitem Workspace.
- `installer/tests/test_aws_profile_context.py`: 9 Mock-Tests
  (Profilwechsel, Konflikt-STOP, Env-Filter mit/ohne Profil, Account-Mismatch
  fail-closed, Runner-Env ohne globale Mutation, Context ohne globale Mutation).

## Evidence
- `aws sts get-caller-identity --profile mayaws` → Account `240571105849`,
  ARN `...:user/Mayaws` (vor und nach Fix identisch).
- Nach Fix: `identity` mit `--profile mayaws` → Account `240571105849`,
  ARN `...:user/Mayaws`, `Profile: mayaws` (vorher `992382612204`).
- Konflikt-Test live: mit gesetztem `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` +
  `--profile mayaws` → `AWS context validation failed. Cannot proceed.`
  (fail-closed, keine Secrets im Output); ohne die Vars → `240571105849`.
- Tests: `test_aws_profile_context.TestAWSProfileContextUnit` (9) +
  `test_runner_workspace` + `test_parallel_isolation` +
  `test_plan_discovery_isolation` → 14/14 OK; volle
  `test_installer`-Suite (86 Tests) OK.
- `terraform validate` (eu-central-1, Profil mayaws): `Success!`.
- `git diff --check`: sauber. Secret-Audit: keine Secrets im Diff
  (einziger Treffer: Variablennamen-String in Blocklist).

## Status: GREEN
- Installer-Identität == Terraform-Provider-Identität == `mayaws`/`240571105849`.
- Backend-/Plan-/Deployment-Ziel-Abgleich: Plan-Metadaten enthalten Account-ID
  aus validiertem Kontext (`DeploymentId`), Deploy validiert Plan gegen
  `deployment_id` + `verify_plan_context_match`; Account-ID stammt je Lauf frisch
  aus STS, nie aus alten Run-Verzeichnissen/Dateinamen.
- Kein `apply`/`destroy`, keine AWS-Ressourcen geändert, kein State-Import,
  keine Policy-Gate-Änderung.

## Offene Punkte
- `identity`-Ausgabe bleibt best-effort bei `User ID` (optional, kein Fail).
- Pre-existing uncommitted Änderungen in `terraform/` (backend.tf,
  cognito_backup_automation, tfplan, lock-Dateien) wurden nicht angefasst.
