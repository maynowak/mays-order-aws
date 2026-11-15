"""MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01: Upgrade-Readiness-Bericht.

Erzeugt `upgrade-readiness.json` + `.md` im Run-Verzeichnis. Der Bericht ist
eine Bewertung, **keine Ausfuehrungsfreigabe**: Der Apply-Pfad prueft P0A/P0B/
P0C unabhaengig erneut und liest die Readiness-Datei nicht als Freigabe.

Gesamtstatus:
- BLOCKED          : mindestens ein blockierender Grund
- REVIEW_REQUIRED  : fachliche Freigabe erforderlich
- NO_CHANGES       : verifizierter No-op ohne Drift
- READY            : alle Pruefungen bestanden (keine Ausfuehrungsfreigabe)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from installer.core.backup_gate import BACKUP_VERIFIED

READINESS_JSON = "upgrade-readiness.json"
READINESS_MD = "upgrade-readiness.md"
SCHEMA_VERSION = 1

READY = "READY"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED"
NO_CHANGES = "NO_CHANGES"


@dataclass
class ReadinessInput:
    project: str
    environment: str
    region: str
    account_id: Optional[str]
    backend: Dict[str, Any]
    workspace: str
    baseline: Dict[str, Any]
    source_version: Optional[str]
    target_version: str
    git_commit: Optional[str]
    plan_sha256: Optional[str]
    compatibility_status: Optional[str]
    compatibility_reason: Optional[str]
    drift_status: str
    noop_status: str
    planned_changes: List[Dict[str, Any]]
    classification: Dict[str, Any]
    blocking_reasons: List[str]
    backup_required: bool = False
    backup_status: Optional[str] = None
    backup_reason: Optional[str] = None
    backup_evidence: Optional[Dict[str, Any]] = None


def decide_status(payload: ReadinessInput) -> str:
    if payload.blocking_reasons:
        return BLOCKED
    if payload.backup_required and payload.backup_status != BACKUP_VERIFIED:
        return BLOCKED
    classification = payload.classification or {}
    if classification.get("overall") == "CRITICAL":
        return BLOCKED
    if payload.compatibility_status == "REVIEW_REQUIRED":
        return REVIEW_REQUIRED
    if classification.get("overall") == "REVIEW":
        return REVIEW_REQUIRED
    if payload.noop_status == "NO_OP_VERIFIED" and not payload.planned_changes:
        return NO_CHANGES
    return READY


def build_readiness_report(payload: ReadinessInput) -> Dict[str, Any]:
    status = decide_status(payload)
    classification = payload.classification or {}
    migration_required = [
        change for change in (classification.get("changes") or [])
        if change.get("category") == "CRITICAL"
    ]
    next_steps = {
        BLOCKED: [
            "Blockierende Gruende beheben (siehe blockingReasons).",
            "Keine Migration/Apply ohne separaten, freigegebenen Ablauf.",
            "Falls noetig: Plan nach Korrektur neu erstellen.",
        ],
        REVIEW_REQUIRED: [
            "Fachliche Freigabe der REVIEW-Aenderungen einholen.",
            "Apply mit --accept-upgrade-review (nach Freigabe) ausfuehren.",
        ],
        NO_CHANGES: ["Keine Aenderungen; kein Apply erforderlich."],
        READY: ["Plan-Review; Apply bleibt eine separate Freigabe."],
    }[status]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": payload.project,
        "environment": payload.environment,
        "aws": {"account": payload.account_id, "region": payload.region},
        "backend": payload.backend,
        "workspace": payload.workspace,
        "state": payload.baseline,
        "sourceVersion": payload.source_version,
        "targetVersion": payload.target_version,
        "gitCommit": payload.git_commit,
        "planSha256": payload.plan_sha256,
        "compatibility": {
            "status": payload.compatibility_status,
            "reason": payload.compatibility_reason,
        },
        "driftStatus": payload.drift_status,
        "noopStatus": payload.noop_status,
        "plannedChanges": payload.planned_changes,
        "classification": classification,
        "migrationRequired": migration_required,
        "backupRequired": payload.backup_required,
        "backupEvidence": payload.backup_evidence or {
            "status": payload.backup_status,
            "required": payload.backup_required,
            "message": payload.backup_reason,
        },
        "blockingReasons": payload.blocking_reasons,
        "nextSteps": next_steps,
        "evidenceLimits": [
            "Readiness ist keine Ausfuehrungsfreigabe; Apply prueft P0A/P0B/P0C und "
            "die Backup-Evidenz erneut.",
            "SemVer-Differenz ist kein technischer Kompatibilitaetsnachweis.",
            "Die Minor-Matrix gilt nur fuer exakt belegte Deployment-Versionspaare.",
            "Drift deckt nur Ressourcen ab, die Terraform beim Refresh liest (TOCTOU).",
            "Backup-Evidenz ist lokal geprueft; sie ersetzt keinen realen AWS-Backup-Test.",
            "Keine Datenmigration, kein Rollback.",
        ],
        "approved": False,
    }


def render_readiness_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Upgrade-Readiness")
    lines.append("")
    lines.append(f"**Status:** `{report.get('status')}`")
    lines.append("")
    lines.append("> Bewertung, keine Ausfuehrungsfreigabe. Der Apply-Pfad prueft "
                 "P0A/P0B/P0C unabhaengig erneut.")
    lines.append("")
    lines.append("## 1. Projekt und Umgebung")
    lines.append("")
    lines.append(f"- Projekt: `{report.get('project')}`")
    lines.append(f"- Environment: `{report.get('environment')}`")
    lines.append("")
    lines.append("## 2. AWS-Account und Region")
    lines.append("")
    aws = report.get("aws") or {}
    lines.append(f"- Account: `{aws.get('account')}`")
    lines.append(f"- Region: `{aws.get('region')}`")
    lines.append("")
    lines.append("## 3. Backend und Workspace")
    lines.append("")
    backend = report.get("backend") or {}
    lines.append(f"- Bucket: `{backend.get('bucket')}`")
    lines.append(f"- Key: `{backend.get('key')}`")
    lines.append(f"- Prefix: `{backend.get('workspace_key_prefix')}`")
    lines.append(f"- Workspace: `{report.get('workspace')}`")
    lines.append("")
    lines.append("## 4. State-Lineage und Serial")
    lines.append("")
    state = report.get("state") or {}
    lines.append(f"- Serial: `{state.get('serial')}`")
    lines.append(f"- Lineage: `{state.get('lineage')}`")
    lines.append(f"- Ressourcen: `{state.get('resources')}`")
    lines.append(f"- Baseline-Status: `{state.get('status')}`")
    lines.append("")
    lines.append("## 5. Installierte Ausgangsversion")
    lines.append("")
    lines.append(f"- `{report.get('sourceVersion')}`")
    lines.append("")
    lines.append("## 6. Zielversion")
    lines.append("")
    lines.append(f"- `{report.get('targetVersion')}`")
    lines.append("")
    lines.append("## 7. Git-Commit")
    lines.append("")
    lines.append(f"- `{report.get('gitCommit')}`")
    lines.append("")
    lines.append("## 8. Versionskompatibilitaet")
    lines.append("")
    compat = report.get("compatibility") or {}
    lines.append(f"- Status: `{compat.get('status')}`")
    lines.append(f"- Begruendung: {compat.get('reason')}")
    lines.append("")
    lines.append("## 9. Drift-Status")
    lines.append("")
    lines.append(f"- `{report.get('driftStatus')}`")
    lines.append("")
    lines.append("## 10. No-op-Status")
    lines.append("")
    lines.append(f"- `{report.get('noopStatus')}`")
    lines.append("")
    lines.append("## 11. Geplante Aenderungen")
    lines.append("")
    planned = report.get("plannedChanges") or []
    if planned:
        lines.append("| Adresse | Typ | Aktionen |")
        lines.append("|---|---|---|")
        for change in planned:
            lines.append("| `{a}` | `{t}` | `{x}` |".format(
                a=change.get("address"), t=change.get("type"),
                x=", ".join(change.get("actions") or [])))
    else:
        lines.append("- keine")
    lines.append("")
    lines.append("## 12. SAFE-/REVIEW-/CRITICAL-Klassifikation")
    lines.append("")
    classification = report.get("classification") or {}
    lines.append(f"- Gesamt: `{classification.get('overall')}`")
    for change in classification.get("changes") or []:
        lines.append(
            f"- `{change.get('category')}` `{change.get('address')}`: "
            f"{change.get('reason')}"
        )
    lines.append("")
    lines.append("## 13. Migrationspflichtige Aenderungen")
    lines.append("")
    migration = report.get("migrationRequired") or []
    if migration:
        for change in migration:
            lines.append(f"- `{change.get('address')}`: {change.get('reason')}")
    else:
        lines.append("- keine")
    lines.append("")
    lines.append("## 14. Blockierende Gruende")
    lines.append("")
    blocking = report.get("blockingReasons") or []
    if blocking:
        for reason in blocking:
            lines.append(f"- {reason}")
    else:
        lines.append("- keine")
    lines.append("")
    lines.append("## 15. Ergebnis und naechste Schritte")
    lines.append("")
    for step in report.get("nextSteps") or []:
        lines.append(f"- {step}")
    lines.append("")
    backup = report.get("backupEvidence") or {}
    lines.append("## 16. Backup-Evidenz (P3A)")
    lines.append("")
    lines.append(f"- Erforderlich: `{report.get('backupRequired')}`")
    lines.append(f"- Status: `{backup.get('status')}`")
    lines.append(f"- Meldung: {backup.get('message') or '-'}")
    if backup.get("backupArn"):
        lines.append(f"- Backup-ARN: `{backup.get('backupArn')}`")
    if backup.get("sha256"):
        lines.append(f"- Evidenz-SHA256: `{backup.get('sha256')}`")
    lines.append("")
    lines.append("## Nachweisgrenzen")
    lines.append("")
    for limit in report.get("evidenceLimits") or []:
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


def write_readiness_report(run_dir: str | Path, report: Dict[str, Any]) -> Tuple[Path, Path]:
    target = Path(run_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / READINESS_JSON
    md_path = target / READINESS_MD
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_readiness_markdown(report), encoding="utf-8")
    return json_path, md_path
