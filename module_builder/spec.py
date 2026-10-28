"""Preset specifications — single source of truth for what a build copies.

The 'complete' preset mirrors the full existing Mays-Orders-Stack:

    terraform root wiring (main/variables/outputs) + 11 child modules
    + Lambda artifacts (order handler zip, cognito backup zip)
    + Lambda source + build script (artifact reproducibility)
    + seed tooling (scripts/seed_orders.py + seed files, opt-in via variable)

Path contracts kept intact by mirroring the repo layout inside the target:

    ${path.root}/../lambda/dist/lambda.zip            (module lambda, sqs-worker)
    ${path.root}/../lambda/dist/cognito_backup.zip    (cognito_backup(_automation))
    ${path.module}/../database/seed/... + /../scripts/seed_orders.py (seed)

Deliberately NOT copied (safety / no repo dependency):
    terraform/backend.tf  → the generated project uses LOCAL state until the
                            consumer configures their own remote backend.
    monitoring.tf         → comment-only documentation file (0 resources).
    .terraform*, *.tfstate*, *.tfplan*, tfplan*, lock files → never.
"""

from __future__ import annotations

from typing import Dict, List

# All child modules of the complete stack (directory names under terraform/modules).
COMPLETE_MODULES: List[str] = [
    "api",
    "cloudtrail",
    "cognito",
    "cognito_backup",
    "cognito_backup_automation",
    "dynamodb",
    "iam",
    "lambda",
    "monitoring",
    "sqs",
    "sqs-worker",
]

# Root terraform files copied into the target (backend.tf intentionally excluded).
COMPLETE_ROOT_TF_FILES: List[str] = ["main.tf", "variables.tf", "outputs.tf"]

# Reference documentation copied alongside (comment-only docs, no resources).
COMPLETE_DOC_FILES: List[str] = ["terraform/README.md"]

# Lambda artifacts REQUIRED for the complete stack (fail-closed if missing).
COMPLETE_ARTIFACTS: List[str] = [
    "lambda/dist/lambda.zip",
    "lambda/dist/cognito_backup.zip",
]

# Lambda source + build script → artifacts stay reproducible in the target.
COMPLETE_LAMBDA_SOURCE: List[str] = ["lambda/src", "lambda/build_zip.py"]

# Cognito-Backup-Lambda: Quelle + Build-Skript (F1, HARDENING-01) — der Build
# ist deterministisch (feste Zip-Timestamps) und läuft identisch im Quell-Repo
# und in generierten Projekten. Package-Tests bleiben bewusst außen vor
# (Artefakt-Konvention wie lambda.zip).
COMPLETE_COGNITO_BACKUP_SOURCE: List[str] = [
    "cognito_backup",
    "lambda/cognito_backup_handler.py",
    "lambda/build_cognito_backup_zip.py",
]

# Policy-Gate (F2, HARDENING-01): selbstenthaltenes, stdlib-only, offline
# lauffähiges Paar (validate-plan.py liest resource-policy.json relativ zur
# eigenen Datei). Der Builder substituiert "project" in resource-policy.json
# auf den gewählten Projektnamen → das generierte Gate erzwingt den
# Namespace DES KONSUMENTEN. Keine Repo-Kopplung, keine stillschweigende
# Umgehung: FAIL blockiert (Exit 1), dokumentiert im generierten README.
COMPLETE_POLICY_FILES: List[str] = [
    "terraform/policy/validate-plan.py",
    "terraform/policy/resource-policy.json",
]

# Orders-Service-Vertrag (MAYS-ORDERS-MODULE-CONTRACT-01): unveränderliche
# Zusammensetzung des wiederverwendbaren Mays-Orders-AWS-Terraform-Moduls.
# Diese 7 Module sind Pflichtbestandteile (API/Handler, Worker, SQS, eigene
# Orders-Tabelle, Orders-IAM) — api benötigt die vom Modul verwaltete
# Cognito-Ressource (JWT-Authorizer). Monitoring/CloudTrail/Cognito-Backups
# und Seed sind NICHT Teil des Orders-Service-Vertrags (Root-Projekt-Extras).
ORDERS_SERVICE_MODULES: List[str] = [
    "api",
    "cognito",
    "dynamodb",
    "iam",
    "lambda",
    "sqs",
    "sqs_worker",
]

# Modul-Eingaben des Orders-Service-Vertrags (auditiert, WP4): die 7 Module
# verbrauchen genau diese Root-Variablen (aws_region entfällt — Region liefert
# der Provider des aufrufenden Projekts; Seed-/Backup-/Alarm-Variablen entfallen,
# da die zugehörigen Bestandteile nicht Vertragsbestandteil sind).
ORDERS_SERVICE_VARIABLES: List[str] = [
    "project_name",
    "tags",
    "monitoring_enabled",
    "log_retention_days",
    "lambda_execution_boundary",
]

# Seed tooling (opt-in via var.seed_example_data, default false).
COMPLETE_SEED_FILES: List[str] = [
    "scripts/seed_orders.py",
    "database/seed/orders_seed_demo_50.json",
    "database/seed/orders_seed_1000.jsonl",
]

PRESETS: Dict[str, Dict] = {
    "complete": {
        "description": "Vollständiger bestehender Mays-Orders-Stack "
                       "(API, Cognito, DynamoDB, Lambda, SQS+Worker, Monitoring, "
                       "CloudTrail, optionale Cognito-Backups, opt-in Seed).",
        "modules": COMPLETE_MODULES,
        "root_tf_files": COMPLETE_ROOT_TF_FILES,
        "doc_files": COMPLETE_DOC_FILES,
        "artifacts": COMPLETE_ARTIFACTS,
        "lambda_source": COMPLETE_LAMBDA_SOURCE,
        "cognito_backup_source": COMPLETE_COGNITO_BACKUP_SOURCE,
        "policy_files": COMPLETE_POLICY_FILES,
        "seed_files": COMPLETE_SEED_FILES,
    },
    "orders-service": {
        "description": "Wiederverwendbares Mays-Orders-AWS-Terraform-MODUL "
                       "(Orders-Service-Vertrag): API+Handler, Worker, SQS, eigene "
                       "Orders-Tabelle, Orders-IAM, Cognito (JWT) — als lokales "
                       "Modul referenzierbar; feste Zusammensetzung ohne Auswahl.",
        "modules": ORDERS_SERVICE_MODULES,
        "variables": ORDERS_SERVICE_VARIABLES,
    },
}


def get_preset(name: str) -> Dict:
    """Return the preset spec or raise a fail-closed error."""
    if name not in PRESETS:
        available = ", ".join(sorted(PRESETS))
        raise ValueError(
            f"Unbekanntes Preset: '{name}'. Verfügbare Presets: {available}"
        )
    return PRESETS[name]
