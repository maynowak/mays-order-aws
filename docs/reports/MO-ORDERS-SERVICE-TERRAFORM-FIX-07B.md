# MO-ORDERS-SERVICE-TERRAFORM-FIX-07B — Generiertes `orders-service`-Modul validierbar

**Datum:** 2026-11-26
**Branch:** `fix/mo-orders-service-terraform-07b` (Basis `main` `8830da2`)
**Status:** `IMPLEMENTED / VERIFIED LOCAL` — kein Merge, kein Deployment, keine
AWS-/Terraform-Plan-/Apply-Aktion, keine RIS-Änderung.

## Problem

`python3 -m module_builder build --target <tmp> --project-name ris-dev-mays-orders
--preset orders-service --validate` brach auf `main` `8830da2` bei
`terraform validate` ab (`Reference to undeclared input variable`).

Reproduktion (vor dem Fix) zeigte mehr als die zwei gemeldeten Stellen:

| Datei/Zeile | Referenz | Ursache |
|---|---|---|
| `outputs.tf:129` (`mo_version`) | `var.deployment_version` | Variable nicht im statischen Vertrag |
| `main.tf:108` (`module "sqs"`) | `var.sqs_max_receive_count` | dito |
| `main.tf:105–107` (`module "sqs"`) | `var.sqs_visibility_timeout_seconds`, `var.sqs_message_retention_seconds`, `var.sqs_dlq_message_retention_seconds` | dito |
| `main.tf:40/63` (`iam`/`lambda`) | `module.privacy_secret` | P00-E-Wiring auf ein Modul, das bewusst **nicht** Vertragsbestandteil ist |
| `main.tf:42/65` | `var.privacy_secret_enabled`, `var.privacy_kms_key_arn` | nur für diese Privacy-Wiring existent |

Ursache: `build_module()` filterte Variablen über die statische Liste
`ORDERS_SERVICE_VARIABLES` und Modulblöcke über `ORDERS_SERVICE_MODULES`, ohne
das tatsächliche Root-Wiring zu prüfen. Spätere Root-Änderungen (P00-E Privacy,
MO-P0B `deployment_version`, MO-RC4-P02C SQS-Parameter) liefen dadurch aus dem
Vertrag. Der `complete`-Preset war nicht betroffen (er kopiert `variables.tf`
vollständig).

## Fix (nur Builder-/Template-Quelle, keine generierten Dateien)

- `module_builder/spec.py`: `ORDERS_SERVICE_VARIABLES` um die fünf tatsächlich
  referenzierten Variablen ergänzt (`deployment_version` +
  vier SQS-Parameter, Defaults unverändert). Neu:
  `ORDERS_SERVICE_EXCLUDED_MODULE_REFS = ["privacy_secret"]` und
  `ORDERS_SERVICE_EXCLUDED_VARIABLES` mit Begründung (ADR-008: unveränderter
  7-Modul-Vertrag, Privacy-Produktivbetrieb BLOCKED).
- `module_builder/builder.py`:
  - Neuer Helper `_strip_out_of_contract_wiring()` entfernt ausschließlich die
    allowlistete Privacy-Wiring (inkl. zugehöriger Kommentarzeilen). Jede
    **andere** Referenz auf ein Nicht-Vertragsmodul bricht fail-closed ab.
  - Vertrags-Audit **vor** jedem Schreiben: die Menge der `var.`-Referenzen in
    generierter `main.tf` + `outputs.tf` muss exakt
    `ORDERS_SERVICE_VARIABLES` (ohne die generierte `external_cognito`)
    entsprechen. Fehlende oder ungenutzte Einträge → Abbruch ohne Schreiben.
  - Manifest-Notiz `out_of_contract_wiring_removed` für Provenance.
  - Modul-README: neue Input-Tabelle (11 Eingaben, Defaults dokumentiert) und
    Privacy-Abgrenzung.
- Keine Änderung an Presets, Security-Defaults, Modul-Wiring der 7 Module,
  Root-Terraform, Lambda, Installer, RIS oder Pin-Dateien.

## Verifikation

| Prüfung | Ergebnis |
|---|---|
| `build --preset orders-service --project-name ris-dev-mays-orders --validate` | **PASS** (`fmt -check`, `init -backend=false`, `validate`) |
| `build --preset complete --validate` (Regression) | **PASS** |
| Modul-Builder-Tests (`module_builder.tests.test_module_builder` + `test_builder_upgrade`) | **134 PASS** (Baseline 129, +5 Regression) |
| Installer-Tests | **81 PASS** |
| Lambda-Tests | **456 PASS** |
| `compileall module_builder` | PASS |

Generiertes Modul (Stichprobe): 7 Module unverändert, 21 Outputs, 11 Inputs,
keine `privacy_*`-Referenz, `sqs_enabled = true` Gate unverändert.

## Grenzen

- Nur lokale Offline-Validierung (`init -backend=false`); kein Plan/Apply.
- Der `terraform`-Regressionstest wird ohne CLI übersprungen; die
  referenzkonsistenten Python-Prüfungen bleiben immer aktiv. Ist die
  Provider-Registry offline, wird der Terraform-Test explizit mit Grund
  übersprungen.
- Die Auswirkung auf den RIS-Pin bzw. die RIS-Modul-Generierung ist nicht Teil
  dieses Tasks (kein RIS-Checkout gelesen/geändert).
