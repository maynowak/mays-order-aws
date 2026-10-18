"""Module catalog — stable names, declared dependencies, resource needs.

Basis: verifizierte Abhängigkeitsanalyse der Root-Verdrahtung
(terraform/main.tf, MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01):
jede Abhängigkeit ist eine NACHFOLGENDE module.<x>-Referenz im Block.

Namen sind die STABILEN Terraform-Modulnamen aus main.tf (Nicht: Verzeichnis-
namen — sqs_worker lebt im Verzeichnis sqs-worker). Der Katalog ist die
einzige Autorität für die freie Modulauswahl (--modules).

B1-Regeln (MAYS-ORDERS-MODULE-BUILDER-B1-SELECTION-01):
- Unbekannte/doppelte Module → fail-closed.
- Fehlende Pflichtabhängigkeiten → fail-closed mit vollständiger Diagnose.
- KEINE automatische Ergänzung (stille Auflösung folgt erst in B2).
"""

from __future__ import annotations

import re
from typing import Dict, List

# Stabiler Modulname -> Verzeichnis (unter terraform/modules/) + direkte Pflicht-Deps
# + optionale Deps (PHASE2): optionale Deps werden NICHT erzwungen; fehlen sie,
# entfernt der Builder die entsprechenden Wiring-Zeilen (z. B. iam.sqs_queue_arn,
# lambda.queue_url) — die Module haben dafür geeignete Defaults (""), und das
# iam-Modul erzeugt ohne Queue-ARN KEINE sqs-Berechtigung (count-gated).
# Basis: Research A/C (MAYS-ORDERS-MODULARIZATION-01-A/-C-EXECUTION_LOG).
MODULE_CATALOG: Dict[str, Dict] = {
    "dynamodb": {"dir": "dynamodb", "deps": [], "optional_deps": []},
    "sqs": {"dir": "sqs", "deps": [], "optional_deps": []},
    "cognito": {"dir": "cognito", "deps": [], "optional_deps": []},
    "cloudtrail": {"dir": "cloudtrail", "deps": [], "optional_deps": []},
    "cognito_backup": {"dir": "cognito_backup", "deps": [], "optional_deps": []},
    "iam": {"dir": "iam", "deps": ["dynamodb"], "optional_deps": ["sqs"]},
    "lambda": {"dir": "lambda", "deps": ["dynamodb", "iam"], "optional_deps": ["sqs"]},
    "sqs_worker": {"dir": "sqs-worker", "deps": ["dynamodb", "sqs"], "optional_deps": []},
    "api": {"dir": "api", "deps": ["cognito", "lambda"], "optional_deps": []},
    "monitoring": {"dir": "monitoring", "deps": ["api", "dynamodb", "lambda"], "optional_deps": []},
    "cognito_backup_automation": {
        "dir": "cognito_backup_automation",
        "deps": ["cognito", "cognito_backup"],
        "optional_deps": [],
    },
}

# Root-Variablen: immer erforderlich (provider/locals/Namen) ODER Modul-zugeordnet.
# Basis: tatsächliche var.-Nutzung je Modulblock in main.tf (verifiziert).
ALWAYS_VARIABLES = {"project_name", "aws_region", "tags"}
VARIABLE_MODULES: Dict[str, List[str]] = {
    "seed_example_data": ["dynamodb"],
    "seed_file_path": ["dynamodb"],
    "monitoring_enabled": ["lambda", "sqs_worker", "monitoring"],
    "log_retention_days": ["lambda", "sqs_worker", "monitoring"],
    "dashboard_enabled": ["monitoring"],
    "alarm_period_seconds": ["monitoring"],
    "alarm_evaluation_periods": ["monitoring"],
    "api_5xx_threshold": ["monitoring"],
    "api_4xx_threshold": ["monitoring"],
    "lambda_error_threshold": ["monitoring"],
    "lambda_duration_threshold_ms": ["monitoring"],
    "lambda_throttle_threshold": ["monitoring"],
    "dynamodb_throttled_threshold": ["monitoring"],
    "notification_email": ["cognito_backup_automation"],
    "enable_cognito_backup": ["cognito_backup", "cognito_backup_automation"],
    "enable_cognito_backup_automation": ["cognito_backup_automation"],
}

# Ressourcen-Bedarf je Auswahl (Lambda-Artefakte/-Quellen nur bei Bedarf):
LAMBDA_ZIP_MODULES = {"lambda", "sqs_worker"}          # filename-Referenz in beiden Blöcken
BACKUP_ZIP_MODULES = {"cognito_backup_automation"}     # Handler-Zip liegt in diesem Modul
LAMBDA_SOURCE_MODULES = {"lambda", "sqs_worker"}
BACKUP_SOURCE_MODULES = {"cognito_backup_automation"}
SEED_MODULES = {"dynamodb"}  # terraform_data.seed_orders referenziert module.dynamodb


def validate_module_list(names: List[str]) -> None:
    """Liste prüfen: doppelte/unbekannte Module + Pflichtabhängigkeiten.

    Fail-closed; KEINE stille Ergänzung (B1-Regel, Auflösung folgt in B2).
    """
    if not names:
        raise SystemExit("module-builder: FEHLER: keine Module angegeben.")
    seen, duplicates = set(), []
    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise SystemExit(
            f"module-builder: FEHLER: doppelte Module in der Auswahl: "
            f"{', '.join(duplicates)}."
        )
    unknown = [n for n in names if n not in MODULE_CATALOG]
    if unknown:
        available = ", ".join(sorted(MODULE_CATALOG))
        raise SystemExit(
            f"module-builder: FEHLER: unbekannte Module: {', '.join(unknown)}.\n"
            f"Verfügbare Module: {available}"
        )
    validate_selection_closure(names)


def parse_module_selection(spec: str) -> List[str]:
    """Komma-Liste -> bereinigte Auswahl (inkl. vollständiger Validierung)."""
    if not spec or not spec.strip():
        raise SystemExit("module-builder: FEHLER: --modules ist leer.")
    names = [name.strip() for name in spec.split(",") if name.strip()]
    validate_module_list(names)
    return names


def validate_selection_closure(selected: List[str]) -> None:
    """Alle direkten Pflichtabhängigkeiten müssen explizit ausgewählt sein.

    KEINE stille Ergänzung (B2): fehlende Abhängigkeiten → vollständige
    Diagnose mit Korrektur-Hinweis, damit die Auswahl in einem Durchlauf
    korrigiert werden kann.
    """
    selection = set(selected)
    findings: List[str] = []
    for name in selected:
        missing = [d for d in MODULE_CATALOG[name]["deps"] if d not in selection]
        if missing:
            findings.append(
                f"  - '{name}' benötigt: {', '.join(MODULE_CATALOG[name]['deps'])} "
                f"(fehlt: {', '.join(missing)})"
            )
    if findings:
        raise SystemExit(
            "module-builder: FEHLER: fehlende Pflichtabhängigkeiten "
            "(keine automatische Auflösung — bewusste B1-Regel, Auflösung folgt in B2):\n"
            + "\n".join(findings)
            + "\nBitte die Auswahl um die fehlenden Module ergänzen."
        )


def required_variables(selected: List[str]) -> List[str]:
    """Variablen, die für die Auswahl erforderlich sind (immer + modul-zugeordnet)."""
    selection = set(selected)
    names = set(ALWAYS_VARIABLES)
    for var_name, modules in VARIABLE_MODULES.items():
        if selection.intersection(modules):
            names.add(var_name)
    return names


# Generische Referenz-Erkennung für Blockfilter (module.<name> in Blocktext).
MODULE_REF_RE = re.compile(r"module\.([a-zA-Z0-9_-]+)")
