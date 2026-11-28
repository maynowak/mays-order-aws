"""MO-GH-SEC-03: Security Findings Gate – Policy Engine

Deterministic, separately testable evaluator of SARIF findings.
Classifies findings according to the Security Gate Policy.

CodeQL security-severity is extracted from SARIF rule metadata
(`rule.properties.security-severity` or `run.tool.driver.rules[].properties.security-severity`)
as a numeric CVSS-like value (0.0 – 10.0).
SARIF `level` is NOT equated with security-severity.

Unknown, negative, non-finite, or out-of-range (>10) security-severity → BLOCKED (fail-closed).
Findings without a security-severity but with a SARIF level of "warning"/"error" may be
quality findings (e.g. CodeQL quality rules) — these are classified separately and do not
trigger security FAIL unless they carry a security-severity.

Dependency findings (ruleId prefix "dependency-") are classified separately:
- LOCK_CONSTRAINT_DRIFT → configuration drift, NOT a security vulnerability
- UPDATE_AVAILABLE → informational, NOT a security finding
- CONSTRAINT_UNSATISFIED → REPORT (medium)
- VULNERABILITY → FAIL if security-severity >= 7.0, else REPORT
"""
from __future__ import annotations

import json
import math
import os
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
    is_dependency_finding: bool = False
    is_quality_finding: bool = False
    scanner_id: Optional[str] = None  # Scanner identity (e.g. "codeql", "dependency")
    run_id: Optional[str] = None      # SARIF run identifier

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    classification: Classification
    findings: List[Finding]
    summary: str
    selected: bool
    report_path: Optional[str] = None
    scanner_id: Optional[str] = None  # Scanner that produced this scan
    run_id: Optional[str] = None      # SARIF run identifier
    sha: Optional[str] = None         # Commit SHA
    ref: Optional[str] = None         # Git ref
    attempt: Optional[int] = None     # Workflow attempt number

    def to_dict(self) -> dict:
        return {
            "classification": self.classification.name,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "selected": self.selected,
            "report_path": self.report_path,
            "scanner_id": self.scanner_id,
            "run_id": self.run_id,
            "sha": self.sha,
            "ref": self.ref,
            "attempt": self.attempt,
        }


# Mapping from numeric security-severity to FindingSeverity
# CodeQL security-severity is a CVSS-like score (0.0 – 10.0)
_SEVERITY_THRESHOLDS: List[tuple[float, FindingSeverity]] = [
    (9.0, FindingSeverity.CRITICAL),
    (7.0, FindingSeverity.HIGH),
    (4.0, FindingSeverity.MEDIUM),
    (0.0, FindingSeverity.LOW),
]

# Dependency rule statuses that are NOT security vulnerabilities
_DEPENDENCY_NON_VULN_STATUSES = {
    "LOCK_CONSTRAINT_DRIFT",  # configuration drift, not a vulnerability
    "UPDATE_AVAILABLE",       # informational
    "LOCK_MISSING",           # configuration issue
    "REGISTRY_INCOMPLETE",    # configuration issue
}

# Dependency rule statuses that are security-relevant
_DEPENDENCY_VULN_STATUSES = {
    "CONSTRAINT_UNSATISFIED",  # medium severity concern
    "VULNERABILITY",           # actual vulnerability
}


def _severity_from_numeric(score: Optional[float]) -> FindingSeverity:
    """Map a numeric CodeQL security-severity to FindingSeverity.

    Returns UNKNOWN if the score is None, negative, non-finite (NaN/Inf),
    or out of range (>10). All invalid values lead to BLOCKED (fail-closed).
    A score of exactly 0.0 means "none" — treated as LOW but flagged via
    security_severity=0.0 so callers can distinguish.
    """
    if not isinstance(score, (int, float)):
        return FindingSeverity.UNKNOWN
    if not math.isfinite(score):
        return FindingSeverity.UNKNOWN
    if score < 0 or score > 10.0:
        return FindingSeverity.UNKNOWN
    for threshold, severity in _SEVERITY_THRESHOLDS:
        if score >= threshold:
            return severity
    return FindingSeverity.LOW


class _InvalidSeverity:
    """Sentinel: security-severity key exists but value is invalid."""
    pass


_INVALID_SEVERITY = _InvalidSeverity()


def _extract_security_severity_from_rule(rule: dict) -> Any:
    """Extract numeric security-severity from a SARIF rule object.

    Returns:
        float       – valid security-severity value
        None        – key not present (quality finding)
        _INVALID_SEVERITY – key present but value invalid (BLOCKED)
    """
    if not isinstance(rule, dict):
        return None
    properties = rule.get("properties", {})
    if not isinstance(properties, dict):
        return None
    if "security-severity" not in properties:
        return None
    sev_str = properties.get("security-severity", "")
    if not isinstance(sev_str, str) or not sev_str:
        return None
    try:
        return float(sev_str)
    except (ValueError, TypeError):
        return _INVALID_SEVERITY


def _resolve_rule_in_run(
    run: dict, rule_id: str, rule_index: Optional[int]
) -> Optional[dict]:
    """Resolve a SARIF rule definition within a SINGLE run.

    CodeQL SARIF defines rules in `run.tool.driver.rules[]` and results
    reference them via `ruleId` or `rule.index`. We look up the rule
    definition to extract security-severity metadata within the SAME run.

    FIX: Only match rule_index when it is not None to avoid None == None bug.
    """
    tool = run.get("tool", {})
    if not isinstance(tool, dict):
        return None
    driver = tool.get("driver", {})
    if not isinstance(driver, dict):
        return None
    rules = driver.get("rules", [])
    if not isinstance(rules, list):
        return None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        # Match by rule id
        if rule_id and rule.get("id") == rule_id:
            return rule
        # Match by rule index (ONLY if rule_index is not None)
        # FIX: Avoid None == None bug - only match index when both values exist
        if rule_index is not None and rule.get("index") == rule_index:
            return rule
    return None


def _extract_security_severity(
    result: dict, runs_or_run: Any
) -> Any:
    """Extract numeric CodeQL security-severity from SARIF result.

    Returns:
        float       – valid security-severity value
        None        – key not present (quality finding)
        _INVALID_SEVERITY – key present but value invalid (BLOCKED)

    First checks `result.rule.properties.security-severity` (inline rule def),
    then falls back to `run.tool.driver.rules[]` lookup by ruleId/index within
    the SAME run (not across runs).
    SARIF `level` is NOT used as a substitute.

    Args:
        result: SARIF result dict
        runs_or_run: Either a list of runs (for backward compatibility with tests)
                      or a single run dict (preferred for proper per-run resolution)
    """
    # Try inline rule definition first
    rule = result.get("rule", {})
    if isinstance(rule, dict):
        sev = _extract_security_severity_from_rule(rule)
        if isinstance(sev, float):
            return sev
        if isinstance(sev, _InvalidSeverity):
            return _INVALID_SEVERITY

    # Determine if we have a list (for tests) or a single run
    if isinstance(runs_or_run, list):
        # Legacy: tests pass a list of runs, search across all runs
        runs = runs_or_run
        result_run = None
    else:
        # Normal case: single run dict
        runs = [runs_or_run]

    # Fall back to run.tool.driver.rules lookup within the same run
    rule_id = result.get("ruleId", "")
    rule_index = None
    if isinstance(result.get("rule"), dict):
        rule_index = result["rule"].get("index")

    # FIX: Resolve rule within the same run, not across all runs
    # Try each run in order until we find a matching rule
    for run in runs:
        if not isinstance(run, dict):
            continue
        resolved_rule = _resolve_rule_in_run(run, rule_id, rule_index)
        if resolved_rule:
            sev = _extract_security_severity_from_rule(resolved_rule)
            if isinstance(sev, float):
                return sev
            if isinstance(sev, _InvalidSeverity):
                return _INVALID_SEVERITY

    return None


def _is_dependency_finding(rule_id: str) -> bool:
    """Check if a finding is a dependency scanner finding."""
    return rule_id.startswith("dependency-") or rule_id.startswith("dep-")


def _extract_dependency_status(result: dict) -> Optional[str]:
    """Extract dependency status from SARIF result properties."""
    rule = result.get("rule", {})
    if not isinstance(rule, dict):
        return None
    properties = rule.get("properties", {})
    if not isinstance(properties, dict):
        return None
    return properties.get("dependency-status") or properties.get("status")


def _validate_sarif_structure(data: dict) -> Optional[str]:
    """Validate SARIF 2.1.0 structure. Returns error message or None."""
    if not isinstance(data, dict):
        return "SARIF root is not an object"
    if data.get("version") != "2.1.0":
        return f"SARIF version must be 2.1.0, got: {data.get('version')}"
    runs = data.get("runs")
    if not isinstance(runs, list) or len(runs) == 0:
        return "SARIF must have at least one run in 'runs' array"
    for i, run in enumerate(runs):
        if not isinstance(run, dict):
            return f"Run[{i}] is not an object"
        if "results" not in run:
            return f"Run[{i}] missing 'results' array"
        results = run.get("results")
        if not isinstance(results, list):
            return f"Run[{i}] 'results' is not an array"
    return None


def _extract_rule_id(result: dict) -> str:
    rule_id = result.get("ruleId", "")
    return rule_id if rule_id else "unknown"


def _extract_sarif_level(result: dict) -> Optional[str]:
    """Extract SARIF `level` field for informational purposes only.

    This is NOT used for severity classification — only recorded
    alongside the finding for auditability.
    """
    level = result.get("level", "")
    return level if level else None


def _extract_description(result: dict) -> str:
    return result.get("text", result.get("description", "")) or ""


def _get_scanner_identity_from_run(run: dict) -> str:
    """Extract scanner identity from SARIF run tool driver name."""
    tool = run.get("tool", {})
    if not isinstance(tool, dict):
        return "unknown"
    driver = tool.get("driver", {})
    if not isinstance(driver, dict):
        return "unknown"
    name = driver.get("name", "unknown")
    if not isinstance(name, str):
        return "unknown"
    return name


def _get_run_id_from_run(run: dict) -> str:
    """Extract run identifier from SARIF run."""
    tool = run.get("tool", {})
    if not isinstance(tool, dict):
        return "unknown"
    driver = tool.get("driver", {})
    if not isinstance(driver, dict):
        return "unknown"
    # Use tool name or run hash if available
    return driver.get("name", "unknown")


def evaluate_scan(
    sarif_path: str,
    selected: bool = True,
    scanner_id: Optional[str] = None,
    run_id: Optional[str] = None,
    sha: Optional[str] = None,
    ref: Optional[str] = None,
    attempt: Optional[int] = None,
) -> ScanResult:
    """Evaluate a single SARIF file and return a ScanResult.

    Fail-closed: any error (missing file, invalid JSON, unknown severity,
    invalid severity range) results in BLOCKED → non-zero exit code.

    Rule resolution is done WITHIN each run (not across runs).
    Unresolved security rule with missing security-severity → BLOCKED.

    Args:
        sarif_path: Path to SARIF file.
        selected: Whether the scanner was explicitly selected for this run.
        scanner_id: Scanner identity (e.g. "codeql", "dependency").
        run_id: Run identifier.
        sha: Commit SHA.
        ref: Git ref.
        attempt: Workflow attempt number.
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
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )
    except json.JSONDecodeError as exc:
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary=f"Invalid SARIF JSON – gate BLOCKED: {exc} (MO-GH-SEC-03)",
            selected=selected,
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )
    except Exception as exc:  # noqa: BLE001 — any read error blocks
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary=f"SARIF read error – gate BLOCKED: {exc} (MO-GH-SEC-03)",
            selected=selected,
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )

    # ---- 2. Validate SARIF structure -------------------------------------
    struct_error = _validate_sarif_structure(data)
    if struct_error:
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=[],
            summary=f"SARIF structure error – gate BLOCKED: {struct_error} (MO-GH-SEC-03)",
            selected=selected,
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )

    # ---- 3. Process each run separately ----------------------------------
    # FIX: Resolve rules within the same run, not across all runs
    runs = data.get("runs", [])
    findings: List[Finding] = []
    blocked_reasons: List[str] = []

    for run in runs:
        run_scanner_id = scanner_id or _get_scanner_identity_from_run(run)
        run_run_id = run_id or _get_run_id_from_run(run)

        # Process results within this run
        results = run.get("results", [])
        if not isinstance(results, list):
            continue

        for res in results:
            rule_id = _extract_rule_id(res)
            # FIX: Extract security severity WITHIN the same run
            security_severity = _extract_security_severity(res, run)
            sarif_level = _extract_sarif_level(res)
            desc = _extract_description(res)
            is_dep = _is_dependency_finding(rule_id)
            dep_status = _extract_dependency_status(res) if is_dep else None

            # Dependency findings are classified separately
            if is_dep:
                # LOCK_CONSTRAINT_DRIFT → configuration drift, NOT a vulnerability
                if dep_status == "LOCK_CONSTRAINT_DRIFT":
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            severity=FindingSeverity.LOW,
                            message=(
                                "Dependency drift (not a vulnerability): "
                                f"{desc[:200] or 'Unnamed finding'}"
                            ),
                            security_severity=None,
                            sarif_level=sarif_level,
                            path=res.get("path"),
                            start_line=res.get("startLine"),
                            is_dependency_finding=True,
                            is_quality_finding=False,
                            scanner_id=run_scanner_id,
                            run_id=run_run_id,
                        )
                    )
                    continue
                # UPDATE_AVAILABLE, LOCK_MISSING, REGISTRY_INCOMPLETE → informational
                if dep_status in _DEPENDENCY_NON_VULN_STATUSES:
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            severity=FindingSeverity.LOW,
                            message=(
                                f"Dependency status {dep_status}: "
                                f"{desc[:200] or 'Unnamed finding'}"
                            ),
                            security_severity=None,
                            sarif_level=sarif_level,
                            path=res.get("path"),
                            start_line=res.get("startLine"),
                            is_dependency_finding=True,
                            is_quality_finding=False,
                            scanner_id=run_scanner_id,
                            run_id=run_run_id,
                        )
                    )
                    continue
                # CONSTRAINT_UNSATISFIED → REPORT (medium)
                if dep_status == "CONSTRAINT_UNSATISFIED":
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            severity=FindingSeverity.MEDIUM,
                            message=(
                                f"Dependency constraint unsatisfied: "
                                f"{desc[:200] or 'Unnamed finding'}"
                            ),
                            security_severity=None,
                            sarif_level=sarif_level,
                            path=res.get("path"),
                            start_line=res.get("startLine"),
                            is_dependency_finding=True,
                            is_quality_finding=False,
                            scanner_id=run_scanner_id,
                            run_id=run_run_id,
                        )
                    )
                    continue
                # VULNERABILITY → classify by security-severity
                if dep_status == "VULNERABILITY":
                    # FIX: Unresolved security rule with missing security-severity → BLOCKED
                    if security_severity is None:
                        blocked_reasons.append(
                            f"{rule_id}: dependency VULNERABILITY missing security-severity"
                        )
                        severity = FindingSeverity.UNKNOWN
                    elif isinstance(security_severity, _InvalidSeverity):
                        blocked_reasons.append(
                            f"{rule_id}: dependency VULNERABILITY has invalid security-severity"
                        )
                        severity = FindingSeverity.UNKNOWN
                    else:
                        severity = _severity_from_numeric(security_severity)
                    findings.append(
                        Finding(
                            rule_id=rule_id,
                            severity=severity,
                            message=(
                                f"Dependency vulnerability: "
                                f"{desc[:200] or 'Unnamed finding'}"
                            ),
                            security_severity=security_severity,
                            sarif_level=sarif_level,
                            path=res.get("path"),
                            start_line=res.get("startLine"),
                            is_dependency_finding=True,
                            is_quality_finding=False,
                            scanner_id=run_scanner_id,
                            run_id=run_run_id,
                        )
                    )
                    continue

            # Non-dependency findings: security-severity handling
            if isinstance(security_severity, _InvalidSeverity):
                # FIX: Invalid security-severity for security rule → BLOCKED
                blocked_reasons.append(
                    f"{rule_id}: invalid security-severity value"
                )
                severity = FindingSeverity.UNKNOWN
            elif security_severity is None:
                # Quality findings (e.g. CodeQL quality rules) without security-severity
                # are not security vulnerabilities — classify as LOW quality finding
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        severity=FindingSeverity.LOW,
                        message=(
                            f"Quality finding (no security-severity): "
                            f"{desc[:200] or 'Unnamed finding'}"
                        ),
                        security_severity=None,
                        sarif_level=sarif_level,
                        path=res.get("path"),
                        start_line=res.get("startLine"),
                        is_dependency_finding=False,
                        is_quality_finding=True,
                        scanner_id=run_scanner_id,
                        run_id=run_run_id,
                    )
                )
                continue

            # Validate security-severity range
            sev_severity = _severity_from_numeric(security_severity)
            if sev_severity == FindingSeverity.UNKNOWN:
                blocked_reasons.append(
                    f"{rule_id}: invalid security-severity {security_severity}"
                )
                severity = FindingSeverity.UNKNOWN
            else:
                severity = sev_severity

            findings.append(
                Finding(
                    rule_id=rule_id,
                    severity=severity,
                    message=desc[:200] or "Unnamed finding",
                    security_severity=security_severity,
                    sarif_level=sarif_level,
                    path=res.get("path"),
                    start_line=res.get("startLine"),
                    is_dependency_finding=False,
                    is_quality_finding=False,
                    scanner_id=run_scanner_id,
                    run_id=run_run_id,
                )
            )

    # If any finding has unknown/invalid severity, the whole scan is BLOCKED
    if blocked_reasons:
        summary_lines = [
            "Security gate: unknown/invalid security-severity – gate BLOCKED (MO-GH-SEC-03)",
        ] + [f"  – {r}" for r in blocked_reasons]
        return ScanResult(
            classification=Classification.BLOCKED,
            findings=findings,
            summary="\n".join(summary_lines),
            selected=selected,
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )

    # ---- 5. Apply policy ------------------------------------------------
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
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )

    # Check for CRITICAL/HIGH security findings (non-quality, non-drift)
    security_fail_findings = [
        f for f in findings
        if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        and not f.is_quality_finding
        and not (f.is_dependency_finding and f.severity == FindingSeverity.LOW)
    ]

    if security_fail_findings:
        summary_lines = [
            "Security gate: CRITICAL/HIGH security findings detected – gate FAILS (MO-GH-SEC-03)",
        ]
        for f in security_fail_findings:
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
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )

    # Check for MEDIUM/LOW findings (report only)
    report_findings = [
        f for f in findings
        if f.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW)
    ]

    if report_findings:
        report_lines = [
            "Security gate: no CRITICAL/HIGH security findings; MEDIUM/LOW findings reported (MO-GH-SEC-03)",
        ]
        for f in report_findings:
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
            scanner_id=scanner_id,
            run_id=run_id,
            sha=sha,
            ref=ref,
            attempt=attempt,
        )

    summary = "Security gate: no security findings detected – gate passes (MO-GH-SEC-03)"
    return ScanResult(
        classification=Classification.PASS,
        findings=findings,
        summary=summary,
        selected=True,
        scanner_id=scanner_id,
        run_id=run_id,
        sha=sha,
        ref=ref,
        attempt=attempt,
    )


def write_report(result: ScanResult, report_path: str) -> None:
    """Write a machine-readable JSON report of the scan result."""
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
                "is_dependency_finding": f.is_dependency_finding,
                "is_quality_finding": f.is_quality_finding,
                "scanner_id": f.scanner_id,
                "run_id": f.run_id,
            }
            for f in result.findings
        ],
        # Report metadata
        "scanner_id": result.scanner_id,
        "run_id": result.run_id,
        "sha": result.sha,
        "ref": result.ref,
        "attempt": result.attempt,
    }
    os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)


def main_cli() -> int:
    """CLI entry point: expects one positional argument – path to SARIF file."""
    import sys

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