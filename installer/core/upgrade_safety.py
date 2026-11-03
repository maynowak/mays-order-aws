"""MO-INSTALLER-UPGRADE-SAFETY-P0A-01: Upgrade-Schutz fuer bestehende Systeme.

Zentrale, rein lokale Auswertung eines Terraform-Plan-JSON:

- Klassifiziert Ressourcen, deren DELETE/REPLACE Datenverlust bedeutet
  (DynamoDB-Tabellen, S3-Buckets, Cognito User Pools, SQS Queues).
- Bewertet die tatsaechlichen Terraform-Aktionen (`delete`, `create+delete`,
  `delete+create`) — nie anhand von Namenspraefixen.
- Fail-closed: fehlende/unbekannte Planinformationen gelten als nicht sicher.
- Erzeugt bei migrationspflichtigen Aenderungen einen strukturierten
  Migrationsplan (JSON + Markdown) im Installer-Run-Verzeichnis.

Es wird KEINE Migration ausgefuehrt und kein AWS-Aufruf gemacht.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 1

STATUS_SAFE = "SAFE"
STATUS_MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
STATUS_UNKNOWN = "UNKNOWN"

# Terraform plan actions (format_version 1.x/1.2).
KNOWN_ACTIONS = {"no-op", "read", "create", "update", "delete"}

# Geschuetzte Ressourcentypen: DELETE oder REPLACE bedeutet Datenverlust.
PROTECTED_RESOURCE_TYPES: Dict[str, str] = {
    "aws_dynamodb_table": "Order-Daten (Items) der Tabelle",
    "aws_s3_bucket": "S3-Objekte und Objektversionen des Buckets",
    "aws_cognito_user_pool": "Cognito-Benutzer, Gruppen und Clients",
    "aws_sqs_queue": "SQS-Nachrichten der Queue",
}

# Weitere zustandsbehaftete Typen werden bewusst NICHT pauschal blockiert
# (z. B. Lambda/API/IAM sind ersetzbar ohne Datenverlust); sie erscheinen im
# normalen Plan-Review. Diese Liste ist die einzige Quelle der Wahrheit.

MIGRATION_PLAN_JSON = "upgrade-migration-plan.json"
MIGRATION_PLAN_MD = "upgrade-migration-plan.md"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class UpgradeFinding:
    address: str
    resource_type: str
    actions: List[str]
    replace_paths: List[str] = field(default_factory=list)
    risk: str = "CRITICAL"
    reason: str = ""
    requires_migration: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "type": self.resource_type,
            "actions": list(self.actions),
            "replacePaths": list(self.replace_paths),
            "risk": self.risk,
            "reason": self.reason,
            "requiresMigration": self.requires_migration,
        }


@dataclass
class UpgradeAssessment:
    status: str
    findings: List[UpgradeFinding] = field(default_factory=list)
    reason: str = ""
    plan_sha256: Optional[str] = None

    @property
    def blocked(self) -> bool:
        return self.status != STATUS_SAFE

    def summary(self) -> str:
        if self.status == STATUS_SAFE:
            return "Upgrade safety: PASS (keine DELETE/REPLACE geschuetzter Ressourcen)"
        return (
            f"Upgrade safety: {self.status} "
            f"({len(self.findings)} kritische Aenderung(en))"
        )


def _flatten_replace_paths(raw: Any) -> List[str]:
    paths: List[str] = []
    if not isinstance(raw, list):
        return paths
    for entry in raw:
        if isinstance(entry, list):
            parts = [str(p) for p in entry]
            paths.append(".".join(parts) if parts else "")
        elif isinstance(entry, (str, int)):
            paths.append(str(entry))
    return [p for p in paths if p]


def analyze_plan(plan: Any, plan_sha256: Optional[str] = None) -> UpgradeAssessment:
    """Bewertet ein Terraform-Plan-JSON (fail-closed).

    Liefert SAFE nur, wenn alle Aenderungen interpretierbar sind und keine
    geschuetzte Ressource geloescht/ersetzt wird.
    """
    if not isinstance(plan, dict):
        return UpgradeAssessment(
            status=STATUS_UNKNOWN,
            reason="Plan-JSON ist kein Objekt; Upgrade-Sicherheit nicht bewertbar.",
            plan_sha256=plan_sha256,
        )

    changes = plan.get("resource_changes")
    if not isinstance(changes, list):
        return UpgradeAssessment(
            status=STATUS_UNKNOWN,
            reason="Plan-JSON enthaelt keine gueltige 'resource_changes'-Liste (fail-closed).",
            plan_sha256=plan_sha256,
        )

    findings: List[UpgradeFinding] = []

    for change in changes:
        if not isinstance(change, dict):
            return UpgradeAssessment(
                status=STATUS_UNKNOWN,
                reason="Ungueltiger Eintrag in 'resource_changes' (fail-closed).",
                plan_sha256=plan_sha256,
            )

        address = str(change.get("address") or "<unknown>")
        resource_type = str(change.get("type") or "")
        actions_raw = (change.get("change") or {}).get("actions")

        if not isinstance(actions_raw, list) or not actions_raw:
            return UpgradeAssessment(
                status=STATUS_UNKNOWN,
                reason=(
                    f"Aktionen fuer '{address}' fehlen oder sind ungueltig "
                    "(fail-closed)."
                ),
                plan_sha256=plan_sha256,
            )

        actions = [str(a) for a in actions_raw]
        unknown = [a for a in actions if a not in KNOWN_ACTIONS]
        if unknown:
            return UpgradeAssessment(
                status=STATUS_UNKNOWN,
                reason=(
                    f"Unbekannte Terraform-Aktion(en) {unknown} bei '{address}' "
                    "(fail-closed)."
                ),
                plan_sha256=plan_sha256,
            )

        if resource_type not in PROTECTED_RESOURCE_TYPES:
            continue

        if "delete" not in actions:
            continue

        replace = "create" in actions
        reason_base = PROTECTED_RESOURCE_TYPES[resource_type]
        reason = (
            f"{'Ersetzen' if replace else 'Loeschen'} von {resource_type} "
            f"wuerde {reason_base} zerstoeren."
        )
        findings.append(
            UpgradeFinding(
                address=address,
                resource_type=resource_type,
                actions=actions,
                replace_paths=_flatten_replace_paths(
                    (change.get("change") or {}).get("replace_paths")
                ),
                reason=reason,
            )
        )

    if findings:
        return UpgradeAssessment(
            status=STATUS_MIGRATION_REQUIRED,
            findings=findings,
            plan_sha256=plan_sha256,
        )

    return UpgradeAssessment(status=STATUS_SAFE, plan_sha256=plan_sha256)


def is_destroy_plan(plan: Any) -> Tuple[bool, str]:
    """Prueft, ob ein Plan ausschliesslich loescht (expliziter Destroy-Plan)."""
    if not isinstance(plan, dict):
        return False, "Plan-JSON ist kein Objekt."
    changes = plan.get("resource_changes")
    if not isinstance(changes, list) or not changes:
        return False, "Plan enthaelt keine 'resource_changes' (kein Destroy-Plan)."

    for change in changes:
        if not isinstance(change, dict):
            return False, "Ungueltiger Eintrag in 'resource_changes'."
        actions = (change.get("change") or {}).get("actions")
        if not isinstance(actions, list) or not actions:
            return False, f"Aktionen fuer '{change.get('address')}' fehlen."
        if any(a in {"create", "update"} for a in actions):
            return False, (
                f"Plan enthaelt nicht-destruktive Aktion(en) {actions} bei "
                f"'{change.get('address')}' — kein Destroy-Plan."
            )
        unknown = [a for a in actions if a not in KNOWN_ACTIONS]
        if unknown:
            return False, f"Unbekannte Aktion(en) {unknown} im Destroy-Plan."
    return True, ""


def build_migration_plan(
    assessment: UpgradeAssessment,
    *,
    project: str,
    environment: str,
    workspace: str,
    source_version: Optional[str] = None,
    target_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Strukturierter Migrationsplan (JSON-Schema P0A-04)."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": (
            STATUS_MIGRATION_REQUIRED
            if assessment.findings
            else assessment.status
        ),
        "project": project,
        "environment": environment,
        "workspace": workspace,
        "sourceVersion": source_version,
        "targetVersion": target_version,
        "planSha256": assessment.plan_sha256,
        "resources": [finding.to_dict() for finding in assessment.findings],
        "approved": False,
    }


def render_migration_plan_markdown(
    plan: Dict[str, Any],
    *,
    created_at: Optional[str] = None,
) -> str:
    """Lesbarer Migrationsplan (Migrationsplanung, keine Ausfuehrungsfreigabe)."""
    timestamp = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: List[str] = []
    lines.append("# Upgrade-Migrationsplan")
    lines.append("")
    lines.append(f"**Erstellt:** {timestamp}")
    lines.append(f"**Status:** `{plan.get('status')}`")
    lines.append("")
    lines.append("> Dies ist eine **Migrationsplanung**, keine Ausfuehrungsfreigabe.")
    lines.append("> Es wurde keine Migration und kein AWS-Aufruf ausgefuehrt.")
    lines.append("")

    lines.append("## 1. Ausgangsumgebung")
    lines.append("")
    lines.append(f"- Projekt: `{plan.get('project')}`")
    lines.append(f"- Environment: `{plan.get('environment')}`")
    lines.append(f"- Workspace: `{plan.get('workspace')}`")
    lines.append(f"- Quellversion: `{plan.get('sourceVersion')}` (nicht gebunden)")
    lines.append("")

    lines.append("## 2. Zielumgebung")
    lines.append("")
    lines.append(f"- Projekt: `{plan.get('project')}` (unveraendert)")
    lines.append(f"- Zielversion: `{plan.get('targetVersion')}` (nicht gebunden)")
    lines.append("")

    lines.append("## 3. Planidentitaet")
    lines.append("")
    lines.append(f"- Plan-SHA-256: `{plan.get('planSha256')}`")
    lines.append("")

    lines.append("## 4. Erkannte kritische Aenderungen")
    lines.append("")
    lines.append(f"- Anzahl: **{len(plan.get('resources') or [])}**")
    lines.append("")

    lines.append("## 5. Datenverlustrisiken")
    lines.append("")
    for resource in plan.get("resources") or []:
        lines.append(f"- `{resource.get('address')}`: {resource.get('reason')}")
    lines.append("")

    lines.append("## 6. Betroffene Ressourcen")
    lines.append("")
    lines.append("| Adresse | Typ | Aktionen | Replace-Pfade |")
    lines.append("|---|---|---|---|")
    for resource in plan.get("resources") or []:
        lines.append(
            "| `{addr}` | `{typ}` | `{actions}` | `{paths}` |".format(
                addr=resource.get("address"),
                typ=resource.get("type"),
                actions=", ".join(resource.get("actions") or []),
                paths=", ".join(resource.get("replacePaths") or []) or "—",
            )
        )
    lines.append("")

    lines.append("## 7. Mögliche Migrationsstrategien")
    lines.append("")
    lines.append("- **A — In-place-Upgrade:** nur fuer Aenderungen ohne Replacement; hier nicht ausreichend.")
    lines.append("- **B — Side-by-Side:** neue Ressource, Datenexport/-kopie, Integritaetspruefung,")
    lines.append("  Umstellung, alte Ressource erhalten, Rueckfall pruefen, Loeschung nur mit Freigabe.")
    lines.append("- **C — Backup/Restore:** Backup-Verfuegbarkeit, Wiederherstellbarkeit, Konsistenz,")
    lines.append("  Dauer und Auswirkungen auf laufende Anwendungen pruefen.")
    lines.append("- **D — Manuelle Migration:** `MANUAL_MIGRATION_REQUIRED`, wenn keine sichere")
    lines.append("  automatische Strategie verfuegbar ist.")
    lines.append("")

    lines.append("## 8. Erforderliche Vorbedingungen")
    lines.append("")
    lines.append("- Explizite menschliche Freigabe der Migrationsstrategie.")
    lines.append("- Backup/Export der betroffenen Daten (PITR/Snapshot/Export).")
    lines.append("- Getestete Wiederherstellung in einer isolierten Umgebung.")
    lines.append("- Wartungsfenster / koordinierte Anwendungsumstellung.")
    lines.append("- Kein automatischer Retry; kein Destroy ohne separate Freigabe.")
    lines.append("")

    lines.append("## 9. Prüf- und Abnahmekriterien")
    lines.append("")
    lines.append("- Datenintegritaet nach Migration (Stichproben, Counts, Schluessel).")
    lines.append("- Anwendungs-E2E auf der neuen Ressource erfolgreich.")
    lines.append("- Keine fremden/RIS-Ressourcen beruehrt.")
    lines.append("- Alter Bestand erst nach dokumentierter Freigabe entfernt.")
    lines.append("- Neuer Plan nach Migration ist ein No-op.")
    lines.append("")

    lines.append("## 10. Offene Entscheidungen")
    lines.append("")
    lines.append("- Strategie (B/C/D) und Verantwortlichkeit.")
    lines.append("- Zeitfenster und Rueckfallplan.")
    lines.append("- Umgang mit laufenden Nachrichten/Benutzern waehrend der Migration.")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_migration_plan(
    run_dir: str | Path,
    plan: Dict[str, Any],
    assessment: UpgradeAssessment,
) -> Tuple[Path, Path]:
    """Schreibt `upgrade-migration-plan.json` und `.md` ins Run-Verzeichnis."""
    target = Path(run_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / MIGRATION_PLAN_JSON
    md_path = target / MIGRATION_PLAN_MD
    json_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_migration_plan_markdown(plan), encoding="utf-8")
    return json_path, md_path


def format_block_message(assessment: UpgradeAssessment) -> str:
    """Eindeutige Fehlermeldung fuer das Gate."""
    lines = ["UPGRADE_BLOCKED_MIGRATION_REQUIRED"]
    lines.append(
        "Geschuetzte Ressourcen wuerden geloescht oder ersetzt — Apply ist blockiert."
    )
    for finding in assessment.findings:
        lines.append(
            f"  - {finding.address} ({finding.resource_type}): "
            f"actions={finding.actions}"
            + (f" replace_paths={finding.replace_paths}" if finding.replace_paths else "")
        )
        lines.append(f"    Datenverlust: {finding.reason}")
    lines.append(
        "Erforderlich: Migrationspruefung (upgrade-migration-plan.json/.md), "
        "explizite Freigabe; keine automatische Migration."
    )
    return "\n".join(lines)
