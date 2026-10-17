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
        "seed_files": COMPLETE_SEED_FILES,
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
