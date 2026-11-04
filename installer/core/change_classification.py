"""MO-INSTALLER-UPGRADE-ORCHESTRATION-P1-01: Change-Klassifikation.

Bewertet die im Plan enthaltenen Aenderungen als SAFE / REVIEW / CRITICAL.
Die Klassifikation ergaenzt P0A (Ressourcen-Safety), P0B (Versionen) und
P0C (State/Drift); sie ersetzt keine dieser Pruefungen.

Regeln:
- DELETE/REPLACE geschuetzter Typen ist bereits P0A-CRITICAL und wird hier
  nur uebernommen (keine Duplizierung der Typenliste).
- Neue Ressourcen sind SAFE, ausser sie schaffen eine oeffentliche/externe
  Schnittstelle oder eine sicherheitsrelevante Policy (REVIEW).
- Updates bestehender Ressourcen sind REVIEW.
- DELETE/REPLACE nicht geschuetzter Ressourcen ist REVIEW.
- Unbekannte Aktionen, unverifizierte Drift, fehlende Drift-Bewertung und
  blockierende Kompatibilitaet sind CRITICAL.
- Die Gesamtbewertung ist das Maximum der Einzelbewertungen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

SAFE = "SAFE"
REVIEW = "REVIEW"
CRITICAL = "CRITICAL"

_RANK = {SAFE: 0, REVIEW: 1, CRITICAL: 2}
_KNOWN_ACTIONS = {"no-op", "read", "create", "update", "delete"}

# Neue Ressourcen dieser Typen schaffen eine oeffentliche/externe Schnittstelle
# oder veraendern die Sicherheitskonfiguration -> fachliche Pruefung.
_REVIEW_CREATE_TYPES = {
    "aws_apigatewayv2_api",
    "aws_apigatewayv2_route",
    "aws_apigatewayv2_authorizer",
    "aws_apigatewayv2_integration",
    "aws_cloudtrail",
    "aws_iam_role",
    "aws_iam_policy",
    "aws_iam_role_policy",
    "aws_iam_role_policy_attachment",
    "aws_s3_bucket_policy",
    "aws_sns_topic",
    "aws_cognito_user_pool",
    "aws_cognito_user_pool_client",
}


@dataclass(frozen=True)
class ChangeAssessment:
    address: str
    resource_type: str
    actions: List[str]
    category: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "type": self.resource_type,
            "actions": list(self.actions),
            "category": self.category,
            "reason": self.reason,
        }


@dataclass
class ClassificationResult:
    overall: str
    changes: List[ChangeAssessment] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "changes": [c.to_dict() for c in self.changes],
            "reasons": list(self.reasons),
        }

    def by_category(self, category: str) -> List[ChangeAssessment]:
        return [c for c in self.changes if c.category == category]


def _worst(categories: Sequence[str]) -> str:
    worst = SAFE
    for category in categories:
        if _RANK.get(category, _RANK[CRITICAL]) > _RANK[worst]:
            worst = category
    return worst


def classify_planned_change(
    address: str,
    resource_type: str,
    actions: Sequence[str],
) -> ChangeAssessment:
    actions = [str(a) for a in actions]
    action_set = set(actions)

    if not actions or any(a not in _KNOWN_ACTIONS for a in actions):
        return ChangeAssessment(
            address, resource_type, actions, CRITICAL,
            "Unbekannte oder fehlende Terraform-Aktion.",
        )

    destructive = "delete" in action_set
    replacing = destructive and "create" in action_set

    if destructive:
        kind = "ersetzt" if replacing else "geloescht"
        return ChangeAssessment(
            address, resource_type, actions, REVIEW,
            f"Bestehende Ressource wird {kind} (nicht geschuetzter Typ) — "
            "fachliche/betriebliche Pruefung erforderlich.",
        )

    if "update" in action_set:
        return ChangeAssessment(
            address, resource_type, actions, REVIEW,
            "Bestehende Ressource wird geaendert — Pruefung der Auswirkungen "
            "erforderlich.",
        )

    if action_set == {"create"}:
        if resource_type in _REVIEW_CREATE_TYPES:
            return ChangeAssessment(
                address, resource_type, actions, REVIEW,
                "Neue Ressource mit oeffentlicher/externer Schnittstelle oder "
                "sicherheitsrelevanter Konfiguration.",
            )
        return ChangeAssessment(
            address, resource_type, actions, SAFE,
            "Neue, zulaessige Ressource ohne bestehende Abhaengigkeiten.",
        )

    return ChangeAssessment(
        address, resource_type, actions, REVIEW,
        "Nicht eindeutig klassifizierbare Aenderung — Pruefung erforderlich.",
    )


def classify_changes(
    *,
    safety_findings: Sequence[Dict[str, Any]] = (),
    drift_status: str = "",
    drift_findings: Sequence[Any] = (),
    planned_changes: Sequence[Any] = (),
    noop_status: str = "",
    compatibility_status: Optional[str] = None,
    protected_types: Sequence[str] = (),
) -> ClassificationResult:
    """Aggregiert alle Bewertungen zu SAFE/REVIEW/CRITICAL (Maximum)."""
    changes: List[ChangeAssessment] = []
    reasons: List[str] = []

    for finding in safety_findings:
        address = str(finding.get("address") or "<unknown>")
        resource_type = str(finding.get("type") or "")
        actions = [str(a) for a in (finding.get("actions") or [])]
        changes.append(
            ChangeAssessment(
                address, resource_type, actions, CRITICAL,
                str(finding.get("reason") or "Kritische Aenderung (P0A)."),
            )
        )

    for change in planned_changes:
        changes.append(
            classify_planned_change(
                str(getattr(change, "address", "<unknown>")),
                str(getattr(change, "resource_type", "")),
                getattr(change, "actions", []),
            )
        )

    protected = set(protected_types)
    for finding in drift_findings:
        resource_type = str(getattr(finding, "resource_type", ""))
        benign = bool(getattr(finding, "benign", False))
        if benign:
            category = SAFE
            reason = "Nachgewiesene Provider-/State-Normalisierung: " + str(
                getattr(finding, "benign_reason", "") or "keine sicherheitsrelevante Drift."
            )
        else:
            category = CRITICAL if resource_type in protected else REVIEW
            reason = "Infrastruktur-Drift erkannt (ausserhalb des Terraform-States)."
        changes.append(
            ChangeAssessment(
                str(getattr(finding, "address", "<unknown>")),
                resource_type,
                [str(a) for a in getattr(finding, "actions", [])],
                category,
                reason,
            )
        )

    if drift_status == "DRIFT_UNKNOWN":
        changes.append(
            ChangeAssessment(
                "<drift>", "", [], CRITICAL,
                "Drift konnte nicht belastbar bewertet werden.",
            )
        )
    if noop_status == "NO_OP_UNVERIFIED":
        changes.append(
            ChangeAssessment(
                "<plan>", "", [], CRITICAL,
                "Plan/No-op nicht belastbar verifiziert.",
            )
        )
    if compatibility_status in ("MIGRATION_REQUIRED", "INCOMPATIBLE", "UNKNOWN"):
        changes.append(
            ChangeAssessment(
                "<version>", "", [], CRITICAL,
                f"Versionskompatibilitaet: {compatibility_status}.",
            )
        )
    elif compatibility_status == "REVIEW_REQUIRED":
        changes.append(
            ChangeAssessment(
                "<version>", "", [], REVIEW,
                "Versionskompatibilitaet erfordert manuelle Pruefung.",
            )
        )

    overall = _worst([change.category for change in changes])
    for change in changes:
        if change.category != SAFE:
            reasons.append(f"{change.address}: {change.reason}")
    return ClassificationResult(overall=overall, changes=changes, reasons=reasons)
