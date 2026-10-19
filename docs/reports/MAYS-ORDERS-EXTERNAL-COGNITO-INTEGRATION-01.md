# MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01

**Checkpoint:** MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01
**Datum:** 2026-10-19 (Implementierung 2026-10-18/19)
**Baseline:** main `a78c785` (MODULE-CONTRACT) → `54de18d` (Implementierung) → Doku-Commit
**Scope (CRITICAL CORRECTION eingehalten):** AUSSCHLIESSLICH das generierte Orders-Service-Modul (`--preset orders-service`). Stamm-`terraform/{main,variables,outputs}.tf`, Installer, Complete-Preset, B1/B2, AWS-Deployments, CI/CD: **unangetastet** (git-diff belegt: nur `module_builder/builder.py` + Tests).
**Status:** VERIFIED — 87/87 Builder, 129/129 Installer, 76/76 Lambda; Modul-`--validate` PASS; Wrapper MANAGED + EXTERNAL + Fail-closed live bewiesen

## 1. Architekturübersicht / Entscheidung

Orders-Service bleibt vollständig (API+Handler, Worker, SQS, eigene Tabelle, IAM — nicht abwählbar). **Cognito ist die einzige variable Komponente**:

- **MANAGED (Standard):** `external_cognito = null` → Modul erstellt eigenen Pool + App Client + Gruppe `staff` (bisheriges Verhalten; Ressourcenadressen erhalten; `module.cognito` → `module.cognito[0]` bei Bestandsupgrades via Terraform-implizitem Move, TF ≥ 1.3).
- **EXTERNAL:** `external_cognito`-Objekt gesetzt → vorhandener Pool/Client des integrierenden Projekts; **keine Cognito-Ressourcen** erzeugt (count=0), **keine fremden Ressourcen** verändert/importiert/gelöscht. JWT-Authorizer bleibt aktiv.
- **Fail-closed:** unvollständige/ungültige Referenzen werden zur validate-/plan-Zeit abgelehnt (HCL-`validation` mit Regex + non-empty).

**Keine neue Auth-Architektur, keine neuen AWS-Dienste, keine Änderung des api-Untermoduls** — ausschließlich die bestehenden api-Inputs `cognito_user_pool_endpoint` + `cognito_user_pool_client_id` werden (im generierten Modul) aus `locals` gespeist.

## 2. Tatsächliche Input-Schnittstelle (aus Bestandscode abgeleitet)

```hcl
variable "external_cognito" {
  type = object({
    user_pool_endpoint = string # Pool-Endpoint OHNE Scheme — api-Modul bildet Issuer als "https://${…}" (terraform/modules/api/main.tf Z.35)
    user_pool_client_id = string # App-Client-ID → JWT audience (Z.34)
  })
  default = null
  validation { … regex "^cognito-idp\.[a-z0-9-]+\.amazonaws\.com/[a-zA-Z0-9_-]+$" + client_id != "" … } # fail-closed
}
```
Endpoint-Format abgeleitet aus `aws_cognito_user_pool.users.endpoint` (cognito-Modul-Output) — identische Semantik für externe Pools.

## 3. Tatsächliche Output-Schnittstelle (19 Namen erhalten)

| Output | MANAGED | EXTERNAL |
|---|---|---|
| `cognito_user_pool_endpoint` | eigener Pool-Endpoint | **externe Referenz** (semantisch: die tatsächlich verwendete) |
| `cognito_user_pool_client_id` | eigener Client | **externe Referenz** |
| `cognito_user_pool_id` / `_arn` / `_group_name` | eigene Werte | **null** — dokumentierte Inkompatibilität (vom Modul nicht verwaltet); Lösungsvorschlag: optionale Zusatzfelder im Objekt (freizugeben), NICHT stillschweigend umgedeutet |
| übrige 14 Outputs | unverändert | unverändert |

Modus-sichere Wertformen: `one(module.cognito[*].…)` (splat ist bei count=0 leer → null, kein Index-Fehler) bzw. `local.cognito_endpoint/_client_id`.

## 4. MANAGED-Verifikation (live)

- `--preset orders-service --validate` → fmt/init/validate **PASS**
- MANAGED-Wrapper (nur `project_name`) → init+validate **PASS** (Regression, unverändertes Verhalten)
- Unit: `external_cognito` default null; `module "cognito"` count-gated (`? 1 : 0`); Cognito-Modul gebündelt

## 5. EXTERNAL-Verifikation (live)

- EXTERNAL-Wrapper (`external_cognito` mit gültigen Referenzen) → init+validate **PASS**
- **Fail-closed-Negativtest:** leerer `user_pool_client_id` → `terraform validate` **Error: Invalid value for variable** (zeigt Objekt-Attribute + unsere Meldung) — frühe, verständliche Ablehnung belegt
- Unit: api-Block speist sich ausschließlich aus `local.cognito_*` (keine Direktreferenz auf `module.cognito`); count=0 bei gesetztem Objekt; JWT-Inputs bleiben gesetzt (nie leer)

## 6. Upgrade-Kompatibilität (7A/B/C geprüft)

- **A) Neuinstallation MANAGED:** identisch zum CONTRACT-Stand (default null).
- **B) Neuinstallation EXTERNAL:** keine Cognito-Ressourcen, Authorizer aus Referenzen (live validiert).
- **C) Bestehendes MANAGED-Deployment + neue Modulversion:** MANAGED bleibt Standard; einzige Adressänderung `module.cognito` → `module.cognito[0]` wird von Terraform (≥1.3) als impliziter Move behandelt — keine Ressourcen-Neuanlage, keine Namens-/Tag-/Tabellen-/Queue-/Rollenänderung (nur Cognito-Adresse indexiert; alle Ressourcen-Identitäten innerhalb des cognito-Moduls unverändert).
- **MANAGED→EXTERNAL-Migration eines Bestandsdeployments: NICHT Bestandteil** (würde den verwalteten Pool entfernen). Kontrollierte Voraussetzungen dokumentiert (README): Freigabe, Nutzer-/Gruppen-Migration, bewusstes State-Handling; **keine Automatik**.

## 7. Terraform-Validierungen (alle real ausgeführt)

| Prüfung | Ergebnis |
|---|---|
| Generiertes Modul `--validate` (fmt -check / init -backend=false / validate) | **PASS** |
| Wrapper MANAGED (Regression) | **PASS** |
| Wrapper EXTERNAL | **PASS** |
| Wrapper EXTERNAL unvollständig (Negativ) | **FAIL wie erwartet** („Invalid value for variable") |
| HCL-Escaping-Fix verifiziert (`\\.` im File, Regex-Wert `\.`) | ✓ (Zeile 56 variables.tf) |
| Stamm-Repo | **nicht verändert** (Scope-Korrektur; git-diff nur module_builder) |

## 8. Regressionstests

**87/87 Builder** (76 + 11 neue EXTERNAL-Tests: Standard/Default, count-Gate, locals-Ableitung, keine Direkt-refs im api-Block, JWT aktiv, fail-closed-Validierung, Pflichtbestandteile, Tags, Output-Namen + -Wertformen, README-Modi, Manifest) · **129/129 Installer** · **76/76 Lambda** · B1/B2/Complete-Suiten unverändert grün (REGRESSION-GATE bestanden — keine neuen Parameter/kein Verhaltenswandel auf bestehenden Wegen).

## 9. Geänderte Dateien

- `module_builder/builder.py` (EXTERNAL_COGNITO_VARIABLE, Output-Ersetzungen, locals/cognito-count/api-Wiring-Transforms, README-Template, Manifest)
- `module_builder/tests/test_module_builder.py` (Klasse `TestExternalCognitoIntegration`, 11 Tests; Variablen-Erwartung 4→5)

## 10. Commits & Git

| Commit | Paket |
|---|---|
| `54de18d` | Implementierung + Tests (2 Dateien, +239/−2) |
| (folgt) | Report + AI_AUDITLOG (dieser) |

Git CLEAN nach Implementierung; keine AWS-Mutationen; keine Release-Tags.

## 11. Offene Punkte

1. Optionale Zusatzfelder in `external_cognito` (pool_id/arn/group), damit die 3 null-Outputs im EXTERNAL-Modul belegt werden können — Lösungsvorschlag, Freigabe abwarten.
2. MANAGED→EXTERNAL-Migration als separater, freizugebender Ablauf (Doku im generierten README).
3. Live-API-Test mit echtem externen Pool (Token-Validierung end-to-end) — erfordert AWS-Freigabe; aktuell: statische + validate-Beweise.
