"""MO-RC4-P02I-E2B: Schutz gegen unbeabsichtigte State-Migration.

Ein kontrollierter Remote-Plan darf niemals stillschweigend einen lokalen
Terraform-State in das Remote-Backend uebernehmen. Terraform bietet beim
Wechsel von `-backend=false` auf ein konfiguriertes Backend eine Migration an
(interaktiv) bzw. bricht mit `-input=false` ab.

Dieses Modul prueft vor dem Remote-Plan ausschliesslich lokal:
- existiert `<terraform_dir>/terraform.tfstate`?
- enthaelt er Ressourcen?

Regel: lokaler State mit Ressourcen (oder unlesbarer State) => Abbruch.
Ein leerer Legacy-State (0 Ressourcen) blockiert nicht, wird aber gemeldet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class StateMigrationBlocked(RuntimeError):
    """Ein lokaler State wuerde in das Remote-Backend migriert."""


def inspect_local_state(terraform_dir: str | Path) -> Dict[str, Any]:
    """Liest nur Metadaten (serial, Ressourcenanzahl) des lokalen States."""
    path = Path(terraform_dir) / "terraform.tfstate"
    result: Dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "readable": False,
        "serial": None,
        "resources": 0,
    }
    if not path.exists():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        result["resources"] = None  # unlesbar -> fail-closed
        return result
    result["readable"] = True
    result["serial"] = data.get("serial")
    result["resources"] = len(data.get("resources") or [])
    return result


def assert_no_state_migration(terraform_dir: str | Path) -> Dict[str, Any]:
    """Fail-closed Guard fuer den Remote-Plan.

    Raises:
        StateMigrationBlocked: lokaler State vorhanden mit Ressourcen oder unlesbar.
    Returns:
        Metadaten des (leeren oder nicht vorhandenen) lokalen States.
    """
    meta = inspect_local_state(terraform_dir)
    if not meta["exists"]:
        return meta

    if not meta["readable"]:
        raise StateMigrationBlocked(
            f"Lokaler Terraform-State '{meta['path']}' ist vorhanden, aber nicht lesbar. "
            "Ein Remote-Plan wuerde eine State-Migration ausloesen. Abbruch — "
            "Datei mit gesonderter Freigabe pruefen/entfernen."
        )

    if (meta["resources"] or 0) > 0:
        raise StateMigrationBlocked(
            f"Lokaler Terraform-State '{meta['path']}' enthaelt {meta['resources']} "
            "Ressource(n). Ein Remote-Plan wuerde ihn in das S3-Backend migrieren. "
            "Abbruch — Migration ist nicht Teil eines Plans und benoetigt eine "
            "gesonderte Freigabe."
        )

    return meta
