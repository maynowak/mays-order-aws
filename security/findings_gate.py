"""MO-GH-SEC-03: Security Findings Gate – Policy Engine

Deterministic, separately testable evaluator of SARIF findings.
Classifies findings according to the Security Gate Policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class FindingSeverity(Enum):
    CRITICAL = auto()
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()


class Classification(Enum):
    FAIL = auto()       # HIGH or CRITICAL found → gate must exit 1
    REPORT = auto()     # MEDIUM/LOW only → gate passes, warnings emitted
    BLOCKED = auto()    # Missing/invalid evidence → gate exits 1
    NOT_EVALUATED = auto()  # Scanner not selected → gate passes, noted
    PASS = auto()       # No findings at all


@dataclass
class Finding:
    rule_id: str
    severity: FindingSeverity
    message: str
    path: Optional[str] = None
    start_line: Optional[int] = None


@dataclass
class ScanResult:
    classification: Classification
    findings: List[Finding]
    summary: str
    selected: bool


_SARIF_TO_FINDING: dict[str, FindingSeverity] = {
    "critical": FindingSeverity.CRITICAL,
    "error": FindingSeverity.CRITICAL,
    "high": FindingSeverity.HIGH,
    "warning": FindingSeverity.MEDIUM,
    "note": FindingSeverity.LOW,
}


def _classify_severity(sarif_severity: Optional[str], description: str) -> FindingSeverity:
    if sarif_severity:
        s = sarif_severity.lower()
        if s in _SARIF_TO_FINDING:
            return _SARIF_TO_FINDING[s]
    lowered = description.lower()
    if any(k in lowered for k in ["critical", "security"]):
        return FindingSeverity.CRITICAL
    if "high" in lowered:
        return FindingSeverity.HIGH
    if "medium" in lowered:
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW


def _extract_results(sarif_data: dict) -> List[dict]:
    runs = sarif_data.get("runs", [])
    if not runs:
        return []
    return runs[0].get("results", [])


def _extract_rule_id(result: dict) -> str:
    rule = result.get("ruleId", "")
    return rule if rule else "unknown"


def _extract_description(result: dict) -> str:
    return result.get("text", result.get("description", "")) or ""


def _extract_sarif_severity(result: dict) -> Optional[str]:
    level = result.get("level", "")
    if level:
        return level
    rule = result.get("rule", {})
    if isinstance(rule, dict):
        return rule.get("severity", "")
    return ""


def evaluate_scan(sarif_path: str, selected: bool = True) -> ScanResult:
    """Evaluate a single SARIF file and return a ScanResult."""
    try:
        with open(sarif_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary="SARIF file missing – gate BLOCKED",
            selected=selected,
        )
    except json.JSONDecodeError:
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary="Invalid SARIF JSON – gate BLOCKED",
            selected=selected,
        )

    results = _extract_results(data)
    findings: List[Finding] = []
    for res in results:
        rule_id = _extract_rule_id(res)
        sarif_sev = _extract_sarif_severity(res)
        desc = _extract_description(res)
        sev = _classify_severity(sarif_sev, desc)
        findings.append(
            Finding(rule_id=rule_id, severity=sev, message=desc[:200] or "Unnamed finding",
                    path=res.get("path"), start_line=res.get("startLine"))
        )

    has_critical_or_high = any(
        f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH) for f in findings
    )

    if not selected:
        return ScanResult(
            classification=Classification.NOT_EVALUATED,
            findings=findings,
            summary=("Scanner not selected for this run – NOT EVALUATED (MO-GH-SEC-03)"
                     if findings else "Scanner not selected – no findings to evaluate"),
            selected=False,
        )

    if has_critical_or_high:
        fail_findings = [f for f in findings if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)]
        summary_lines = ["Security gate: CRITICAL/HIGH findings detected – gate FAILS (MO-GH-SEC-03)"]
        for f in fail_findings:
            summary_lines.append(f"  – {f.rule_id}: {f.severity.name} – {f.message}")
        summary = "\n".join(summary_lines)
        return ScanResult(
            classification=Classification.FAIL,
            findings=findings,
            summary=summary,
            selected=True,
        )

    has_medium_or_low = any(
        f.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW) for f in findings
    )

    if has_medium_or_low:
        report_lines = ["Security gate: no CRITICAL/HIGH findings; MEDIUM/LOW findings reported (MO-GH-SEC-03)"]
        for f in findings:
            if f.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW):
                report_lines.append(f"  – {f.rule_id}: {f.severity.name} – {f.message}")
        summary = "\n".join(report_lines)
        return ScanResult(
            classification=Classification.REPORT,
            findings=findings,
            summary=summary,
            selected=True,
        )

    summary = "Security gate: no findings detected – gate passes (MO-GH-SEC-03)"
    return ScanResult(
        classification=Classification.PASS,
        findings=findings,
        summary=summary,
        selected=True,
    )


def main_cli() -> int:
    """CLI entry point: expects one positional argument – path to SARIF file."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 security/findings_gate.py <path-to-sarif>", file=sys.stderr)
        return 2
    sarif_path = sys.argv[1]
    result = evaluate_scan(sarif_path, selected=True)
    print(result.summary)
    exit_codes = {
        Classification.FAIL: 1,
        Classification.REPORT: 0,
        Classification.BLOCKED: 1,
        Classification.NOT_EVALUATED: 0,
        Classification.PASS: 0,
    }
    return exit_codes.get(result.classification, 0)


if __name__ == "__main__":
    raise SystemExit(main_cli())