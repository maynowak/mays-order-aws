"""MO-RC4-P02I-E2B: Cleanup-/Destroy-Vertrag (lokale Pruefungen).

Ein RC4-Teststack muss vollstaendig rueckbaubar sein, ohne fremde
Infrastruktur zu beruehren. Dieses Modul kapselt die *lokalen*, testbaren
Regeln des Vertrags:

- State-Cleanup darf ausschliesslich den State des eigenen Projekts adressieren
  (exakter Key ``env:/<project_name>/terraform.tfstate``).
- Gemeinsame Backend-Ressourcen (State-Bucket, Lock-Tabelle) und fremde
  Projekt-States sind geschuetzt.
- Ressourcen werden nie anhand eines Namenspraefixes geloescht; die einzige
  Quelle ist der Terraform-State des Projekts.

Es werden keine AWS-Operationen ausgefuehrt.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

# Ressourcen, die NIE durch einen RC4-Cleanup entfernt werden duerfen.
PROTECTED_RESOURCES: tuple[str, ...] = (
    "S3 mays-orders-tfstate-central-240571105849 (shared Terraform state bucket)",
    "DynamoDB mays-orders-terraform-locks (shared state lock table)",
    "RIS Terraform state (mays-ris-tf-state-dev / mays-ris-tf-lock)",
    "RIS-managed MO stack (ris-dev-mays-orders-*)",
    "CI roles mays-orders-development-ci-*",
    "CodePipeline mays-orders-development-ci-cd / directAWSGit-Mays-Order-AWS",
)

# State-Keys, die nie Ziel eines Cleanups sind (fremd oder geteilt).
PROTECTED_STATE_KEYS: tuple[str, ...] = (
    "terraform.tfstate",
    "env:/mays-orders/terraform.tfstate",
    "env:/mays-order-par/terraform.tfstate",
    "env:/mays-orders-privacy-test/terraform.tfstate",
)


def expected_state_key(project_name: str) -> str:
    """Der einzige zulaessige RC4-State-Key."""
    return f"env:/{project_name}/terraform.tfstate"


def validate_cleanup_target(
    state_key: str,
    project_name: str,
    *,
    protected_keys: Optional[Iterable[str]] = None,
) -> List[str]:
    """Prueft, ob ein State-Key als Cleanup-Ziel zulaessig ist."""
    errors: List[str] = []
    protected = set(protected_keys or PROTECTED_STATE_KEYS)

    if not project_name:
        errors.append("project_name fehlt: Cleanup-Ziel ist nicht bestimmbar.")
        return errors

    if state_key in protected:
        errors.append(
            f"State-Key '{state_key}' ist geschuetzt (geteilte oder fremde Infrastruktur)."
        )
        return errors

    expected = expected_state_key(project_name)
    if state_key != expected:
        errors.append(
            f"State-Key '{state_key}' ist nicht der State des Projekts "
            f"'{project_name}' (erwartet: '{expected}')."
        )

    return errors


def residual_resources(state_list_output: str) -> List[str]:
    """Liefert die im State verbliebenen Ressourcenadressen (ohne Leerzeilen)."""
    return [line.strip() for line in (state_list_output or "").splitlines() if line.strip()]
