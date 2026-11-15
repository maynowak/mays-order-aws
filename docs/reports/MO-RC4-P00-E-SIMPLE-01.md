# MO-RC4-P00-E-SIMPLE-01 — P00-E lokal implementiert

**Status:** `RESULT B — LOKAL IMPLEMENTIERT / INTEGRATION APPROVAL REQUIRED`

- **Basis:** `release/rc4-integration` @ `2dbbd3f37ee64ac7b25849a3c55c78b864e524b8`
- **Feature-Branch:** `feature/mo-rc4-p00-e-simple`
- **Implementierungs-Commit:** `a6667ec`
- **Datum:** 2026-11-14
- **AWS/Terraform-Mutation:** keine
- **Terraform plan/apply:** nicht ausgeführt
- **Push/Merge/Deployment:** nicht ausgeführt

## 1. Ausgangsprüfung

- `AGENTS.md` und `docs/AI_AUDITLOG.md` gelesen.
- Integration-Worktree war auf dem erwarteten HEAD `2dbbd3f` und clean.
- Eine frühere P00-E-Arbeit existiert nur als Analyse-/Dokumentationsbranch
  `analysis/mo-rc4-p00-e-baseline-01` (`46c6e61`); dort wurden keine
  Terraform-/Produktdateien geändert oder überschrieben.
- Die Implementierung erfolgte auf einem separaten Feature-Branch direkt von
  `2dbbd3f`. Der Analysebranch wurde nicht verändert.

## 2. Die drei Fragen

### 2.1 Welchen KMS-Schlüssel verwendet das relevante Secret?

Auf dem Basis-HEAD existiert kein Privacy-Secret und damit auch kein
Secret-KMS-Schlüssel. Die minimale Implementierung legt nur dann einen
Secret-Container an, wenn `privacy_secret_enabled = true` gesetzt wird.

- **Default (`false`):** kein Secret, keine Änderung an Laufzeit-ENV oder IAM.
- **Aktiviert ohne `privacy_kms_key_arn`:** AWS-managed Secrets-Manager-Key
  (`aws/secretsmanager`); es wird **kein** KMS-Schlüssel erzeugt.
- **Aktiviert mit `privacy_kms_key_arn`:** ausschließlich der angegebene,
  bereits existierende Customer-Managed Key (exakte ARN); es wird **kein**
  neuer KMS-Schlüssel erzeugt.

Der Secret-**Wert** wird nicht von Terraform verwaltet. Es gibt bewusst keine
`aws_secretsmanager_secret_version`; die Provisionierung erfolgt out-of-band
durch den Owner.

### 2.2 Hat die Lambda-Ausführungsrolle die erforderlichen Rechte?

Vor der Änderung: **nein**. Die Handler-Rolle hatte keine
Secrets-Manager-/KMS-Berechtigungen.

Nach der Änderung, count-gated und nur bei aktiviertem Secret:

| Fall | IAM-Recht | Ressource |
|---|---|---|
| Secret aktiviert | `secretsmanager:GetSecretValue` | exakte Secret-ARN |
| Secret + externer CMK | `secretsmanager:DescribeSecret` | exakte Secret-ARN |
| Secret + externer CMK | `kms:Decrypt` | exakte CMK-ARN |

Es gibt keine Wildcards, keine pauschalen `secretsmanager:*`-/`kms:*`-Rechte
und keine Berechtigungen, wenn `privacy_secret_enabled = false`. Bei
AWS-managed Key werden bewusst keine KMS-Rechte vergeben.

### 2.3 Erfüllt die Terraform-Konfiguration den Q-09-Vertrag?

Vor der Änderung: **nein** für diesen Scope. Der Policy Gate akzeptierte
`aws_secretsmanager_secret` nicht und prüfte Inline-`aws_iam_role_policy`-
Dokumente nicht auf sensible Secrets-/KMS-Wildcards.

Nach der Änderung ist der **minimale P00-E-Q-09-Scope** erfüllt:

- `aws_secretsmanager_secret` ist in der Ressourcen-Allowlist.
- Secret-Namen müssen im Projekt-Namespace liegen.
- Ein gesetztes `kms_key_id` muss eine exakte KMS-Key-ARN sein.
- Inline-IAM-Rollenpolitiken werden auf Wildcard-Actions geprüft.
- Secrets-Manager-/KMS-Actions mit Wildcard-Ressourcen werden abgelehnt.
- Bestehende Logs-Wildcards bleiben außerhalb dieser engen Q-09-Prüfung, um
  keine bestehende, nicht-sensitive Policy zu brechen.

Bewusst **nicht** implementiert: `aws_kms_key`-Allowlist, KMS-Key-Erzeugung,
DDB-/SQS-CMK-Wiring. Dafür gibt es in diesem Minimal-Scope keine neue
Ressource und keine Owner-Freigabe.

## 3. Änderungen

### Neue Dateien

- `terraform/modules/privacy_secret/main.tf` — optionaler
  `aws_secretsmanager_secret`-Container, kein Secret-Wert.
- `terraform/modules/privacy_secret/variables.tf` — Projekt, Tags, optionale
  exakte CMK-ARN; Default nutzt den AWS-managed Key.
- `terraform/modules/privacy_secret/outputs.tf` — ARN/Name.

### Geänderte Terraform-Dateien

- `terraform/main.tf` — opt-in Modul, count-gated IAM-/Lambda-Verdrahtung.
- `terraform/variables.tf` — `privacy_secret_enabled` (Default `false`) und
  `privacy_kms_key_arn` (Default leer, exakte ARN-Validierung).
- `terraform/outputs.tf` — `privacy_secret_arn` (ARN, kein Wert).
- `terraform/modules/iam/main.tf` / `variables.tf` — exakte
  Secrets-Manager-/KMS-Policies, nur bei Aktivierung.
- `terraform/modules/lambda/main.tf` / `variables.tf` — nicht-sensitive
  `PRIVACY_SECRET_PROVIDER`, `PRIVACY_SECRET_ID` und optional
  `PRIVACY_KMS_KEY_ARN`; keine Änderung bei Default `false`.
- `terraform/policy/resource-policy.json` — Secret-Typ in Allowlist.
- `terraform/policy/validate-plan.py` — Secret-Namespace-/KMS-ARN-Prüfung,
  Inline-IAM-Wildcard-Prüfung, sensible Secrets-/KMS-Ressourcenprüfung.

### Builder und Tests

- `module_builder/catalog.py` / `spec.py` — `privacy_secret` im Katalog und
  im `complete`-Preset, damit das Root-Modul vollständig generiert werden kann.
- `installer/tests/test_policy_gate.py` — fünf neue Tests für Secret-Allowlist,
  Namespace, exakte KMS-ARN, Inline-Policy mit exakter ARN und Wildcard-Ablehnung.

Keine Änderungen an DynamoDB, SQS, API Gateway, Cognito, CloudFront oder
am APP_MANAGED-Pfad.

## 4. Testresultate

| Prüfung | Ergebnis |
|---|---|
| `terraform fmt -check -recursive` | PASS |
| `terraform init -backend=false` | PASS (lokal, kein AWS) |
| `terraform validate` | PASS |
| Lambda Unit Tests | 429/429 PASS |
| Module Builder Tests | 128/128 PASS |
| Policy-Gate-Tests | 23/23 PASS (inkl. 5 neue P00-E-Tests) |
| `git diff --check` | PASS |
| Terraform plan/apply | **nicht ausgeführt** |
| AWS-Live-Aufrufe | **keine** |

Die vollständige Installer-Suite wurde in diesem Minimal-Scope nicht erneut
ausgeführt; betroffen ist nur die Policy-Gate-Testklasse, die vollständig
lief. `terraform validate` ist eine statische Konfigurationsprüfung und kein
Nachweis eines erfolgreichen Apply-Verhaltens.

## 5. Working Tree und Commit

- Implementierungs-Commit: `a6667ec` (`feat(terraform): add opt-in privacy secret wiring`)
- Feature-Branch: `feature/mo-rc4-p00-e-simple`
- Kein Push, kein Merge, kein Deployment.

## 6. Verbleibende Gates

1. **Integrationsfreigabe** für `feature/mo-rc4-p00-e-simple` (dieser Branch
   ist noch nicht in `release/rc4-integration`).
2. **Terraform-Plan-Freigabe** separat; Plan ist nicht ausgeführt.
3. **Terraform-Apply-/AWS-Live-Freigabe** separat; keine AWS-Mutation.
4. Out-of-band-Provisionierung des Secret-Werts durch den Owner.
5. Bei externem CMK: Owner-Freigabe für Key und Key-Policy (`kms:Decrypt`).
6. DDB-/SQS-CMK bleibt eine separate Owner-Entscheidung.
7. P00-F Rotation/Revocation, Environment-Recycle und Transition-Window bleiben
   offen.

**Ergebnis B:** P00-E ist lokal implementiert und validiert; eine separate
Integrationsfreigabe ist erforderlich.
