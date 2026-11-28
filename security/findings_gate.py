"""MO-GH-SEC-03: Security Findings Gate – Policy Engine

Deterministic, separately testable evaluator of SARIF findings.
Classifies findings according to the Security Gate Policy.

CodeQL security-severity is extracted from SARIF rule metadata
(`rule.properties.security-severity`) as a numeric CVSS-like value.
SARIF `level` is NOT equated with security-severity.

Unknown or invalid security-severity → BLOCKED (fail-closed).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class FindingSeverity(Enum):
    CRITICAL = auto()
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    UNKNOWN = auto()


class Classification(Enum):
    FAIL = auto()       # HIGH or CRITICAL → gate exits 1
    REPORT = auto()     # MEDIUM/LOW only → gate passes, warnings
    BLOCKED = auto()    # Missing/invalid evidence → gate exits 1
    NOT_EVALUATED = auto()  # Scanner not selected → gate passes, noted
    PASS = auto()       # No findings at all


@dataclass
class Finding:
    rule_id: str
    severity: FindingSeverity
    message: str
    security_severity: Optional[float] = None
    sarif_level: Optional[str] = None
    path: Optional[str] = None
    start_line: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    classification: Classification
    findings: List[Finding]
    summary: str
    selected: bool
    report_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "classification": self.classification.name,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "selected": self.selected,
            "report_path": self.report_path,
        }


# Mapping from numeric security-severity to FindingSeverity
# CodeQL security-severity is a CVSS-like score (0.0 – 10.0)
_SEVERITY_THRESHOLDS: List[tuple[float, FindingSeverity]] = [
    (9.0, FindingSeverity.CRITICAL),
    (7.0, FindingSeverity.HIGH),
    (4.0, FindingSeverity.MEDIUM),
    (0.0, FindingSeverity.LOW),
]


def _severity_from_numeric(score: Optional[float]) -> FindingSeverity:
    """Map a numeric CodeQL security-severity to FindingSeverity.

    Returns UNKNOWN if the score is None or negative (unknown/invalid).
    A score of exactly 0.0 means "none" — treated as LOW but flagged via
    security_severity=0.0 so callers can distinguish.
    """
    if score is None or score < 0:
        return FindingSeverity.UNKNOWN
    for threshold, severity in _SEVERITY_THRESHOLDS:
        if score >= threshold:
            return severity
    return FindingSeverity.LOW


def _extract_security_severity(result: dict) -> Optional[float]:
    """Extract numeric CodeQL security-severity from SARIF rule metadata.

    CodeQL SARIF stores security-severity in:
      result.rule.properties.security-severity  (string, e.g. "9.0")

    SARIF `level` (result.level) is NOT used as a substitute.
    """
    rule = result.get("rule", {})
    if not isinstance(rule, dict):
        return None

    properties = rule.get("properties", {})
    if not isinstance(properties, dict):
        return None

    sev_str = properties.get("security-severity", "")
    if not sev_str:
        return None

    try:
        return float(sev_str)
    except (ValueError, TypeError):
        return None


def _extract_sarif_level(result: dict) -> Optional[str]:
    """Extract SARIF `level` field for informational purposes only.

    This is NOT used for severity classification — only recorded
    alongside the finding for auditability.
    """
    level = result.get("level", "")
    return level if level else None


def _extract_rule_id(result: dict) -> str:
    rule_id = result.get("ruleId", "")
    return rule_id if rule_id else "unknown"


def _extract_description(result: dict) -> str:
    return result.get("text", result.get("description", "")) or ""


def _extract_results(sarif_data: dict) -> List[dict]:
    runs = sarif_data.get("runs", [])
    if not runs:
        return []
    # Collect results from all runs — CodeQL may emit multiple runs
    all_results: List[dict] = []
    for run in runs:
        all_results.extend(run.get("results", []))
    return all_results


def _classify_severity(
    security_severity: Optional[float], description: str
) -> FindingSeverity:
    """Classify severity using numeric security-severity only.

    Description-based fallback is intentionally NOT used for classification
    — if security-severity is missing, the result is UNKNOWN which leads
    to BLOCKED (fail-closed).
    """
    return _severity_from_numeric(security_severity)


def evaluate_scan(sarif_path: str, selected: bool = True) -> ScanResult:
    """Evaluate a single SARIF file and return a ScanResult.

    Fail-closed: any error (missing file, invalid JSON, unknown severity)
    results in BLOCKED → non-zero exit code. No fallback to PASS.
    """
    # ---- 1. Load SARIF ---------------------------------------------------
    try:
        with open(sarif_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary="SARIF file missing – gate BLOCKED (MO-GH-SEC-03)",
            selected=selected,
        )
    except json.JSONDecodeError as exc:
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary=f"Invalid SARIF JSON – gate BLOCKED: {exc} (MO-GH-SEC-03)",
            selected=selected,
        )
    except Exception as exc:  # noqa: BLE001 — any read error blocks
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary=f"SARIF read error – gate BLOCKED: {exc} (MO-GH-SEC-03)",
            selected=selected,
        )

    # ---- 2. Extract results from all runs --------------------------------
    try:
        results = _extract_results(data)
    except Exception as exc:  # noqa: BLE001
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary=f"SARIF structure error – gate BLOCKED: {exc} (MO-GH-SEC-03)",
            selected=selected,
        )

    # ---- 3. Classify each finding ---------------------------------------
    findings: List[Finding] = []
    blocked_reasons: List[str] = []

    for res in results:
        rule_id = _extract_rule_id(res)
        security_severity = _extract_security_severity(res)
        sarif_level = _extract_sarif_level(res)
        desc = _extract_description(res)

        # Fail-closed: unknown or invalid security-severity blocks
        if security_severity is None:
            blocked_reasons.append(
                f"{rule_id}: missing security-severity in rule metadata"
            )
            severity = FindingSeverity.UNKNOWN
        else:
            severity = _classify_severity(security_severity, desc)

        findings.append(
            Finding(
                rule_id=rule_id,
                severity=severity,
                message=desc[:200] or "Unnamed finding",
                security_severity=security_severity,
                sarif_level=sarif_level,
                path=res.get("path"),
                start_line=res.get("startLine"),
            )
        )

    # If any finding has unknown severity, the whole scan is BLOCKED
    if blocked_reasons:
        summary_lines = [
            "Security gate: unknown/invalid security-severity – gate BLOCKED (MO-GH-SEC-03)",
        ] + [f"  – {r}" for r in blocked_reasons]
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=findings,
            summary="\n".join(summary_lines),
            selected=selected,
        )

    # ---- 4. Apply policy ------------------------------------------------
    if not selected:
        return ScanResult(
            classification=Classification.NOT_EVALUATED,
            findings=findings,
            summary=(
                "Scanner not selected for this run – NOT EVALUATED (MO-GH-SEC-03)"
                if findings
                else "Scanner not selected – no findings to evaluate"
            ),
            selected=False,
        )

    has_critical_or_high = any(
        f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        for f in findings
    )

    if has_critical_or_high:
        fail_findings = [
            f for f in findings
            if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        ]
        summary_lines = [
            "Security gate: CRITICAL/HIGH findings detected – gate FAILS (MO-GH-SEC-03)",
        ]
        for f in fail_findings:
            sev_str = (
                f"{f.security_severity}"
                if f.security_severity is not None
                else "n/a"
            )
            summary_lines.append(
                f"  – {f.rule_id}: {f.severity.name} (security-severity={sev_str}) – {f.message}"
            )
        summary = "\n".join(summary_lines)
        return ScanResult(
            classification=Classification.FAIL,
            findings=findings,
            summary=summary,
            selected=True,
        )

    has_medium_or_low = any(
        f.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW)
        for f in findings
    )

    if has_medium_or_low:
        report_lines = [
            "Security gate: no CRITICAL/HIGH findings; MEDIUM/LOW findings reported (MO-GH-SEC-03)",
        ]
        for f in findings:
            if f.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW):
                sev_str = (
                    f"{f.security_severity}"
                    if f.security_severity is not None
                    else "n/a"
                )
                report_lines.append(
                    f"  – {f.rule_id}: {f.severity.name} (security-severity={sev_str}) – {f.message}"
                )
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


def write_report(result: ScanResult, report_path: str) -> None:
    """Write a machine-readable JSON report of the scan result."""
    import os

    report = {
        "classification": result.classification.name,
        "summary": result.summary,
        "selected": result.selected,
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.name,
                "message": f.message,
                "security_severity": f.security_severity,
                "sarif_level": f.sarif_level,
                "path": f.path,
                "start_line": f.start_line,
            }
            for f in result.findings
        ],
    }
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)


def main_cli() -> int:
    """CLI entry point: expects one positional argument – path to SARIF file."""
    import sys
    import os

    if len(sys.argv) < 2:
        print(
            "Usage: python3 security/findings_gate.py <path-to-sarif> [report-path]",
            file=sys.stderr,
        )
        return 2

    sarif_path = sys.argv[1]
    report_path = sys.argv[2] if len(sys.argv) > 2 else None

    result = evaluate_scan(sarif_path, selected=True)
    print(result.summary)

    if report_path:
        write_report(result, report_path)
        print(f"Report written to: {report_path}")

    exit_codes = {
        Classification.FAIL: 1,
        Classification.REPORT: 0,
        Classification.BLOCKED: 1,
        Classification.NOT_EVALUATED: 0,
        Classification.PASS: 0,
    }
    return exit_codes.get(result.classification, 1)  # default: BLOCKED (fail-closed)


if __name__ == "__main__":
    raise SystemExit(main_cli())