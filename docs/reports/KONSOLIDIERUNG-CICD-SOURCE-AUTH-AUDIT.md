# CI/CD Source Auth Audit – Konsolidierung

**Datum:** 2026-09-26  
**Status:** Audit abgeschlossen, Dokumentation  
**Scope:** Prüfung aktueller Source-Authentifizierung in CodePipeline

## Historischer Kontext

Bericht `docs/reports/GITHUB-AUTH-CI-INTEGRATION-01.md` vom 2026-09-22 beschreibt ein historisches PAT-Problem:
- CodePipeline Source Action mit GitHub v1 + OAuthToken aus Secrets Manager
- Token invalid/revoked → Source Stage Fail
- Klassifikation C) PAT_REQUIRED_FOR_SOURCE

Dieser Bericht ist historisch.

## Aktueller Stand

Prüfung von `ci/pipeline/main.tf`:

**Source Action Konfiguration:**
```hcl
stage {
  name = "Source"
  action {
    name             = "Source"
    category         = "Source"
    owner            = "AWS"
    provider         = "CodeStarSourceConnection"
    version          = "1"
    output_artifacts = ["source_output"]
    configuration = {
      ConnectionArn    = "arn:aws:codeconnections:eu-central-1:240571105849:connection/b0fa25d8-874f-4639-8e91-3ed87b2bb59b"
      FullRepositoryId = "maynowak/mays-order-aws"
      BranchName       = var.github_branch
      OutputArtifactFormat = "CODE_ZIP"
    }
  }
}
```

**Befund:**
1. Aktuelle Source-Authentifizierung verwendet **AWS CodeStar Connections**, nicht GitHub PAT
2. Provider = `CodeStarSourceConnection`, kein `OAuthToken`
3. Connection ARN ist konfiguriert, keine Referenz auf Secrets Manager GitHub Token
4. Kein `github-token-xxxxx` Secret wird im Terraform Code referenziert

**Suchergebnisse:**
- `grep OAuthToken ci/**/*.tf` → keine Treffer
- `grep github-token ci/**/*.tf` → keine Treffer

## Schlussfolgerung

- GitHub PAT ist **kein aktiver Bestandteil** der produktiven Source-Konfiguration
- Historischer PAT-Bericht ist **SUPERSEDED** durch CodeConnections
- Installer funktioniert
- Aktuelle offene CI/CD Baustelle betrifft Deploy-Berechtigungen / Policy-Kette, nicht Source Auth

## Empfehlung

- `docs/reports/GITHUB-AUTH-CI-INTEGRATION-01.md` als HISTORISCH / SUPERSEDED kennzeichnen
- Aktuellen CodeConnections-Stand dokumentieren
- Keine Änderung am funktionierenden Code durchführen

## Tests / Checks

- Terraform Code Review durchgeführt
- Keine Code-Änderungen
- Git Status clean

## Git

Kein Commit erforderlich für diese Dokumentation im Rahmen der Konsolidierung, Dokumentation erstellt.
