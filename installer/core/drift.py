"""MO-INSTALLER-UPGRADE-DRIFT-SAFETY-P0C-01: Drift- und No-op-Bewertung.

Wertet das Terraform-Plan-JSON aus:

- ``resource_drift`` (Refresh-Ergebnis) getrennt von ``resource_changes``
  (geplante Upgrade-Aenderungen)
- ``output_changes``
- Plan-Vollstaendigkeit (``complete``/``applyable``/``errored``)

Regeln:
- Eine leere Drift-Liste ohne belastbaren Refresh-Nachweis ist **kein**
  ``NO_DRIFT`` (fail-closed: ``DRIFT_UNKNOWN``).
- Ein Plan ohne Resource Changes ist nur dann ``NO_OP_VERIFIED``, wenn auch
  die Drift-Bewertung belastbar und ohne Drift ist.
- Es werden keine State-Inhalte in den Bericht uebernommen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

NO_DRIFT = "NO_DRIFT"
DRIFT_DETECTED = "DRIFT_DETECTED"
DRIFT_UNKNOWN = "DRIFT_UNKNOWN"

NO_OP_VERIFIED = "NO_OP_VERIFIED"
CHANGES_PLANNED = "CHANGES_PLANNED"
NO_OP_UNVERIFIED = "NO_OP_UNVERIFIED"

KNOWN_ACTIONS = {"no-op", "read", "create", "update", "delete"}
DRIFT_REPORT_SCHEMA_VERSION = 1

DRIFT_REPORT_JSON = "upgrade-drift-report.json"
DRIFT_REPORT_MD = "upgrade-drift-report.md"


@dataclass(frozen=True)
class PlanChange:
    address: str
    resource_type: str
    actions: List[str]
    replace_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "type": self.resource_type,
            "actions": list(self.actions),
            "replacePaths": list(self.replace_paths),
        }


@dataclass
class DriftAssessment:
    drift_status: str
    drift_findings: List[PlanChange]
    noop_status: str
    planned_changes: List[PlanChange]
    output_changes: Dict[str, List[str]]
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "driftStatus": self.drift_status,
            "driftFindings": [f.to_dict() for f in self.drift_findings],
            "noopStatus": self.noop_status,
            "plannedChanges": [c.to_dict() for c in self.planned_changes],
            "outputChanges": self.output_changes,
            "reason": self.reason,
        }


def _flatten_paths(raw: Any) -> List[str]:
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


def _entries(plan: Any, key: str) -> Optional[List[dict]]:
    if not isinstance(plan, dict):
        return None
    raw = plan.get(key)
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    return [entry for entry in raw if isinstance(entry, dict)]


def _change_entries(plan: Any) -> Optional[List[dict]]:
    if not isinstance(plan, dict):
        return None
    raw = plan.get("resource_changes")
    if not isinstance(raw, list):
        return None
    return [entry for entry in raw if isinstance(entry, dict)]


def analyze_plan_drift(
    plan: Any, *, has_prior_state: bool
) -> Tuple[str, List[PlanChange], str]:
    """Bewertet ``resource_drift`` (fail-closed)."""
    if not has_prior_state:
        return (
            NO_DRIFT,
            [],
            "Kein vorheriger State (verifizierter leerer/neuer State) — Drift nicht anwendbar.",
        )

    entries = _entries(plan, "resource_drift")
    if entries is None:
        return (
            DRIFT_UNKNOWN,
            [],
            "Plan enthaelt keinen belastbaren 'resource_drift'-Nachweis "
            "(kein Refresh) — Drift nicht bewertbar (fail-closed).",
        )

    findings: List[PlanChange] = []
    for entry in entries:
        actions_raw = (entry.get("change") or {}).get("actions")
        if not isinstance(actions_raw, list) or not actions_raw:
            return (
                DRIFT_UNKNOWN,
                [],
                f"Drift-Eintrag '{entry.get('address')}' ohne gueltige Aktionen.",
            )
        actions = [str(a) for a in actions_raw]
        if any(a not in KNOWN_ACTIONS for a in actions):
            return (
                DRIFT_UNKNOWN,
                [],
                f"Unbekannte Terraform-Aktion(en) {actions} im Drift-Eintrag "
                f"'{entry.get('address')}'.",
            )
        if all(a in {"no-op", "read"} for a in actions):
            continue
        findings.append(
            PlanChange(
                address=str(entry.get("address") or "<unknown>"),
                resource_type=str(entry.get("type") or ""),
                actions=actions,
                replace_paths=_flatten_paths((entry.get("change") or {}).get("replace_paths")),
            )
        )

    if findings:
        return DRIFT_DETECTED, findings, f"{len(findings)} Drift-Aenderung(en) erkannt."
    return NO_DRIFT, [], "Refresh durchgefuehrt, keine Drift-Aenderungen."


def classify_noop(
    plan: Any,
    *,
    drift_status: str,
    drift_findings: List[PlanChange],
) -> Tuple[str, List[PlanChange], Dict[str, List[str]], str]:
    """Klassifiziert den Plan als No-op/CHANGES_PLANNED (fail-closed)."""
    changes_entries = _change_entries(plan)
    if changes_entries is None:
        return (
            NO_OP_UNVERIFIED,
            [],
            {},
            "Plan enthaelt keine gueltige 'resource_changes'-Liste (fail-closed).",
        )

    planned: List[PlanChange] = []
    for entry in changes_entries:
        actions_raw = (entry.get("change") or {}).get("actions")
        if not isinstance(actions_raw, list) or not actions_raw:
            return (
                NO_OP_UNVERIFIED,
                [],
                {},
                f"Ressourceneintrag '{entry.get('address')}' ohne gueltige Aktionen.",
            )
        actions = [str(a) for a in actions_raw]
        if any(a not in KNOWN_ACTIONS for a in actions):
            return (
                NO_OP_UNVERIFIED,
                [],
                {},
                f"Unbekannte Terraform-Aktion(en) {actions} bei "
                f"'{entry.get('address')}'.",
            )
        if all(a in {"no-op", "read"} for a in actions):
            continue
        planned.append(
            PlanChange(
                address=str(entry.get("address") or "<unknown>"),
                resource_type=str(entry.get("type") or ""),
                actions=actions,
                replace_paths=_flatten_paths((entry.get("change") or {}).get("replace_paths")),
            )
        )

    output_changes: Dict[str, List[str]] = {}
    raw_outputs = plan.get("output_changes") if isinstance(plan, dict) else None
    if isinstance(raw_outputs, dict):
        for name, entry in raw_outputs.items():
            actions = (entry or {}).get("actions") if isinstance(entry, dict) else None
            if isinstance(actions, list) and any(a not in {"no-op", "read"} for a in actions):
                output_changes[str(name)] = [str(a) for a in actions]

    if isinstance(plan, dict) and (plan.get("complete") is False or plan.get("errored") is True):
        return (
            NO_OP_UNVERIFIED,
            planned,
            output_changes,
            "Plan ist unvollstaendig oder fehlerhaft (complete/errored).",
        )

    if planned or output_changes:
        reason = (
            f"{len(planned)} geplante Ressourcenaenderung(en)"
            + (f", {len(output_changes)} Output-Aenderung(en)" if output_changes else "")
        )
        return CHANGES_PLANNED, planned, output_changes, reason

    if drift_status == DRIFT_UNKNOWN:
        return (
            NO_OP_UNVERIFIED,
            planned,
            output_changes,
            "Keine Resource Changes, aber Drift ist nicht belastbar bewertet.",
        )
    if drift_status == DRIFT_DETECTED:
        return (
            NO_OP_UNVERIFIED,
            planned,
            output_changes,
            "Keine geplanten Aenderungen, aber Drift wurde erkannt "
            f"({len(drift_findings)} Eintrag/Eintraege).",
        )

    return NO_OP_VERIFIED, planned, output_changes, "Keine relevanten Aenderungen, Drift geprueft."


def assess_plan(plan: Any, *, has_prior_state: bool) -> DriftAssessment:
    drift_status, drift_findings, drift_reason = analyze_plan_drift(
        plan, has_prior_state=has_prior_state
    )
    noop_status, planned, output_changes, noop_reason = classify_noop(
        plan, drift_status=drift_status, drift_findings=drift_findings
    )
    reasons = [r for r in (drift_reason, noop_reason) if r]
    return DriftAssessment(
        drift_status=drift_status,
        drift_findings=drift_findings,
        noop_status=noop_status,
        planned_changes=planned,
        output_changes=output_changes,
        reason=" ".join(reasons),
    )


def build_drift_report(
    assessment: DriftAssessment,
    *,
    project: str,
    environment: str,
    workspace: str,
    baseline: Dict[str, Any],
    source_version: Optional[str],
    target_version: Optional[str],
    git_commit: Optional[str],
    critical_changes: List[Dict[str, Any]],
    blocking_reasons: List[str],
) -> Dict[str, Any]:
    return {
        "schemaVersion": DRIFT_REPORT_SCHEMA_VERSION,
        "project": project,
        "environment": environment,
        "workspace": workspace,
        "state": {
            "serial": baseline.get("serial"),
            "lineage": baseline.get("lineage"),
            "resources": baseline.get("resources"),
            "status": baseline.get("status"),
            "fingerprint": baseline.get("fingerprint"),
            "captured_at": baseline.get("captured_at"),
        },
        "sourceVersion": source_version,
        "targetVersion": target_version,
        "gitCommit": git_commit,
        "driftStatus": assessment.drift_status,
        "noopStatus": assessment.noop_status,
        "plannedChanges": [c.to_dict() for c in assessment.planned_changes],
        "driftFindings": [f.to_dict() for f in assessment.drift_findings],
        "criticalChanges": critical_changes,
        "blockingReasons": blocking_reasons,
        "evidenceLimits": [
            "resource_drift deckt nur Ressourcen ab, die Terraform beim Refresh liest.",
            "Ein No-op-Plan ist kein Beweis fuer driftsfreie Infrastruktur ausserhalb des States.",
            "Die Baseline prueft Serial/Lineage/Fingerprint, nicht den Inhalt einzelner Ressourcen.",
            "Eine Pruefung vor Apply verhindert keine Aenderungen danach (TOCTOU).",
        ],
        "approved": False,
    }


def render_drift_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Upgrade-Drift-Bericht")
    lines.append("")
    lines.append(f"**Projekt:** `{report.get('project')}` · "
                 f"**Environment:** `{report.get('environment')}` · "
                 f"**Workspace:** `{report.get('workspace')}`")
    lines.append("")
    lines.append(f"**Drift-Status:** `{report.get('driftStatus')}` · "
                 f"**No-op-Status:** `{report.get('noopStatus')}`")
    lines.append("")
    state = report.get("state") or {}
    lines.append("## State-Identitaet")
    lines.append("")
    lines.append(f"- Serial: `{state.get('serial')}`")
    lines.append(f"- Lineage: `{state.get('lineage')}`")
    lines.append(f"- Ressourcen: `{state.get('resources')}`")
    lines.append(f"- Baseline-Status: `{state.get('status')}`")
    lines.append(f"- Fingerprint: `{state.get('fingerprint')}`")
    lines.append(f"- Erfasst: `{state.get('captured_at')}`")
    lines.append("")
    lines.append("## Versionen")
    lines.append("")
    lines.append(f"- Ausgangsversion: `{report.get('sourceVersion')}`")
    lines.append(f"- Zielversion: `{report.get('targetVersion')}`")
    lines.append(f"- Git-Commit: `{report.get('gitCommit')}`")
    lines.append("")
    lines.append("## Geplante Upgrade-Aenderungen")
    lines.append("")
    planned = report.get("plannedChanges") or []
    if planned:
        lines.append("| Adresse | Typ | Aktionen | Replace-Pfade |")
        lines.append("|---|---|---|---|")
        for change in planned:
            lines.append("| `{a}` | `{t}` | `{x}` | `{r}` |".format(
                a=change.get("address"), t=change.get("type"),
                x=", ".join(change.get("actions") or []),
                r=", ".join(change.get("replacePaths") or []) or "—"))
    else:
        lines.append("- keine")
    lines.append("")
    lines.append("## Erkannte Drift")
    lines.append("")
    drift = report.get("driftFindings") or []
    if drift:
        lines.append("| Adresse | Typ | Aktionen |")
        lines.append("|---|---|---|")
        for finding in drift:
            lines.append("| `{a}` | `{t}` | `{x}` |".format(
                a=finding.get("address"), t=finding.get("type"),
                x=", ".join(finding.get("actions") or [])))
    else:
        lines.append("- keine (siehe Nachweisgrenzen)")
    lines.append("")
    lines.append("## Kritische Aenderungen (P0A)")
    lines.append("")
    critical = report.get("criticalChanges") or []
    if critical:
        for change in critical:
            lines.append(f"- `{change.get('address')}`: {change.get('reason', '')}")
    else:
        lines.append("- keine")
    lines.append("")
    lines.append("## Blockierende Gruende")
    lines.append("")
    blocking = report.get("blockingReasons") or []
    if blocking:
        for reason in blocking:
            lines.append(f"- {reason}")
    else:
        lines.append("- keine")
    lines.append("")
    lines.append("## Nachweisgrenzen")
    lines.append("")
    for limit in report.get("evidenceLimits") or []:
        lines.append(f"- {limit}")
    lines.append("")
    lines.append("> Der Bericht ist eine Bewertung, keine Ausfuehrungsfreigabe.")
    lines.append("")
    return "\n".join(lines)


def write_drift_report(run_dir: str | Path, report: Dict[str, Any]) -> Tuple[Path, Path]:
    target = Path(run_dir)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / DRIFT_REPORT_JSON
    md_path = target / DRIFT_REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    md_path.write_text(render_drift_markdown(report), encoding="utf-8")
    return json_path, md_path
