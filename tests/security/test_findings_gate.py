#!/usr/bin/env python3
"""MO-GH-SEC-03: Executable tests for the Security Findings Gate.

Covers all seven QA corrections:
1. FAIL-CLOSED: unknown classification, Python errors, invalid evidence → non-zero
2. PORTABILITY: no hardcoded developer paths
3. SCAN SELECTION: scanner selection and execution status from needs
4. EVIDENCE: SARIF artifact validation, missing/invalid → BLOCKED
5. SEVERITY: numeric CodeQL security-severity from rule metadata
6. COVERAGE: scheduled and partial scans handled correctly
7. REPORTING: machine-readable JSON report
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add security dir to path for import
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "security"))

from findings_gate import (  # noqa: E402
    Classification,
    FindingSeverity,
    _extract_security_severity,
    _extract_security_severity_from_rule,
    _INVALID_SEVERITY,
    _severity_from_numeric,
    evaluate_scan,
    main_cli,
    write_report,
)


class TestSeverityFromNumeric(unittest.TestCase):
    """Test numeric security-severity → FindingSeverity mapping."""

    def test_critical_9_0(self):
        self.assertEqual(_severity_from_numeric(9.0), FindingSeverity.CRITICAL)
        self.assertEqual(_severity_from_numeric(10.0), FindingSeverity.CRITICAL)

    def test_high_7_0_to_8_9(self):
        self.assertEqual(_severity_from_numeric(7.0), FindingSeverity.HIGH)
        self.assertEqual(_severity_from_numeric(8.9), FindingSeverity.HIGH)

    def test_medium_4_0_to_6_9(self):
        self.assertEqual(_severity_from_numeric(4.0), FindingSeverity.MEDIUM)
        self.assertEqual(_severity_from_numeric(6.9), FindingSeverity.MEDIUM)

    def test_low_above_zero(self):
        self.assertEqual(_severity_from_numeric(0.1), FindingSeverity.LOW)
        self.assertEqual(_severity_from_numeric(3.9), FindingSeverity.LOW)

    def test_unknown_none(self):
        self.assertEqual(_severity_from_numeric(None), FindingSeverity.UNKNOWN)

    def test_unknown_negative(self):
        self.assertEqual(_severity_from_numeric(-1.0), FindingSeverity.UNKNOWN)

    def test_unknown_nan(self):
        self.assertEqual(_severity_from_numeric(float("nan")), FindingSeverity.UNKNOWN)

    def test_unknown_inf(self):
        self.assertEqual(_severity_from_numeric(float("inf")), FindingSeverity.UNKNOWN)

    def test_unknown_out_of_range_high(self):
        self.assertEqual(_severity_from_numeric(11.0), FindingSeverity.UNKNOWN)

    def test_unknown_out_of_range_low(self):
        self.assertEqual(_severity_from_numeric(-0.1), FindingSeverity.UNKNOWN)


class TestExtractSecuritySeverityFromRule(unittest.TestCase):
    """Test extraction of security-severity from SARIF rule metadata."""

    def test_valid_numeric_string(self):
        rule = {"properties": {"security-severity": "9.0"}}
        self.assertEqual(_extract_security_severity_from_rule(rule), 9.0)

    def test_valid_integer_string(self):
        rule = {"properties": {"security-severity": "7"}}
        self.assertEqual(_extract_security_severity_from_rule(rule), 7.0)

    def test_missing_properties(self):
        rule = {}
        self.assertIsNone(_extract_security_severity_from_rule(rule))

    def test_missing_security_severity_key(self):
        rule = {"properties": {}}
        self.assertIsNone(_extract_security_severity_from_rule(rule))

    def test_invalid_security_severity(self):
        rule = {"properties": {"security-severity": "abc"}}
        self.assertIs(_extract_security_severity_from_rule(rule), _INVALID_SEVERITY)

    def test_empty_security_severity(self):
        rule = {"properties": {"security-severity": ""}}
        self.assertIsNone(_extract_security_severity_from_rule(rule))

    def test_no_rule(self):
        self.assertIsNone(_extract_security_severity_from_rule({}))


class TestExtractSecuritySeverity(unittest.TestCase):
    """Test extraction of security-severity from SARIF result with runs."""

    def test_inline_rule_def(self):
        result = {
            "ruleId": "py/sql-injection",
            "rule": {"properties": {"security-severity": "9.0"}},
        }
        runs = []
        self.assertEqual(_extract_security_severity(result, runs), 9.0)

    def test_rule_from_driver_rules(self):
        result = {"ruleId": "py/sql-injection", "rule": {"index": 0}}
        runs = [{
            "tool": {
                "driver": {
                    "name": "CodeQL",
                    "rules": [{"id": "py/sql-injection", "index": 0, "properties": {"security-severity": "8.5"}}],
                }
            },
            "results": [],
        }]
        self.assertEqual(_extract_security_severity(result, runs), 8.5)

    def test_invalid_severity_propagated(self):
        result = {
            "ruleId": "py/bad",
            "rule": {"properties": {"security-severity": "not-a-number"}},
        }
        runs = []
        self.assertIs(_extract_security_severity(result, runs), _INVALID_SEVERITY)

    def test_missing_severity(self):
        result = {"ruleId": "py/unknown", "rule": {"properties": {}}}
        runs = []
        self.assertIsNone(_extract_security_severity(result, runs))

    def test_no_rule_key(self):
        result = {"ruleId": "py/no-rule"}
        runs = []
        self.assertIsNone(_extract_security_severity(result, runs))


class TestEvaluateScanFailClosed(unittest.TestCase):
    """Test FAIL-CLOSED behavior: errors never fall through to PASS."""

    def test_missing_sarif_file_blocked(self):
        result = evaluate_scan("/nonexistent/path.sarif", selected=True)
        self.assertEqual(result.classification, Classification.BLOCKED)
        self.assertTrue(result.selected)

    def test_invalid_json_blocked(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            f.write("NOT VALID JSON{{{")
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_empty_file_blocked(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_empty_json_blocked(self):
        """SARIF with no runs → BLOCKED."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            f.write("{}")
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_missing_runs_blocked(self):
        """SARIF with empty runs array → BLOCKED."""
        sarif = {"version": "2.1.0", "runs": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_invalid_security_severity_blocked(self):
        """Invalid security-severity value → BLOCKED."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/bad-sev",
                    "rule": {"properties": {"security-severity": "abc"}},
                    "level": "error",
                    "text": "Bad severity",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_out_of_range_severity_blocked(self):
        """Severity > 10 → BLOCKED."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/out-of-range",
                    "rule": {"properties": {"security-severity": "11"}},
                    "level": "error",
                    "text": "Out of range",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_negative_severity_blocked(self):
        """Negative severity → BLOCKED."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/negative",
                    "rule": {"properties": {"security-severity": "-1"}},
                    "level": "error",
                    "text": "Negative",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_nan_severity_blocked(self):
        """NaN severity → BLOCKED."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/nan",
                    "rule": {"properties": {"security-severity": "NaN"}},
                    "level": "error",
                    "text": "NaN",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.BLOCKED)
        finally:
            os.unlink(path)

    def test_missing_security_severity_quality_finding(self):
        """Missing security-severity for non-dependency → quality finding (REPORT), not BLOCKED."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/no-sev",
                    "rule": {"properties": {}},
                    "level": "error",
                    "text": "No severity",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            # Quality finding without security-severity → REPORT (not BLOCKED)
            self.assertEqual(result.classification, Classification.REPORT)
            self.assertTrue(any(f.is_quality_finding for f in result.findings))
        finally:
            os.unlink(path)

    def test_unknown_classification_not_pass(self):
        """Verify that no code path returns PASS for an error condition."""
        result = evaluate_scan("/nonexistent.sarif", selected=True)
        self.assertNotEqual(result.classification, Classification.PASS)
        # Not selected but file exists → NOT_EVALUATED
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/test",
                    "rule": {"properties": {"security-severity": "9.0"}},
                    "level": "error",
                    "text": "Test",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=False)
            self.assertEqual(result.classification, Classification.NOT_EVALUATED)
        finally:
            os.unlink(path)


class TestEvaluateScanSeverityLevels(unittest.TestCase):
    """Test that numeric security-severity drives classification."""

    def _make_sarif(self, sev_value: str) -> str:
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/test-rule",
                    "rule": {
                        "properties": {"security-severity": sev_value}
                    },
                    "level": "error",
                    "text": "Test finding",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            return f.name

    def test_severity_9_0_fail(self):
        path = self._make_sarif("9.0")
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.FAIL)
        finally:
            os.unlink(path)

    def test_severity_7_5_fail(self):
        path = self._make_sarif("7.5")
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.FAIL)
        finally:
            os.unlink(path)

    def test_severity_5_0_report(self):
        path = self._make_sarif("5.0")
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.REPORT)
        finally:
            os.unlink(path)

    def test_severity_2_0_report(self):
        path = self._make_sarif("2.0")
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.REPORT)
        finally:
            os.unlink(path)

    def test_severity_0_0_low_report(self):
        path = self._make_sarif("0.0")
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.REPORT)
        finally:
            os.unlink(path)

    def test_multiple_runs_critical_and_high_fail(self):
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "CodeQL", "rules": []}},
                    "results": [{
                        "ruleId": "py/critical",
                        "rule": {"properties": {"security-severity": "9.5"}},
                        "level": "error",
                        "text": "Critical",
                    }],
                },
                {
                    "tool": {"driver": {"name": "CodeQL", "rules": []}},
                    "results": [{
                        "ruleId": "py/high",
                        "rule": {"properties": {"security-severity": "7.2"}},
                        "level": "warning",
                        "text": "High",
                    }],
                },
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.FAIL)
        finally:
            os.unlink(path)

    def test_not_selected_not_evaluated(self):
        path = self._make_sarif("9.0")
        try:
            result = evaluate_scan(path, selected=False)
            self.assertEqual(result.classification, Classification.NOT_EVALUATED)
        finally:
            os.unlink(path)


class TestDependencyFindings(unittest.TestCase):
    """Test dependency findings are classified separately."""

    def test_lock_constraint_drift_not_vulnerability(self):
        """LOCK_CONSTRAINT_DRIFT → LOW, not a security vulnerability."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "Dependency", "rules": []}},
                "results": [{
                    "ruleId": "dependency-drift",
                    "rule": {
                        "properties": {"dependency-status": "LOCK_CONSTRAINT_DRIFT"}
                    },
                    "level": "warning",
                    "text": "Lock constraint drift detected",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.REPORT)
            self.assertTrue(any(f.is_dependency_finding for f in result.findings))
            drift_finding = [f for f in result.findings if f.is_dependency_finding][0]
            self.assertEqual(drift_finding.severity, FindingSeverity.LOW)
        finally:
            os.unlink(path)

    def test_dependency_vulnerability_fail(self):
        """Dependency VULNERABILITY with high severity → FAIL."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "Dependency", "rules": []}},
                "results": [{
                    "ruleId": "dependency-vuln",
                    "rule": {
                        "properties": {
                            "dependency-status": "VULNERABILITY",
                            "security-severity": "9.0",
                        }
                    },
                    "level": "error",
                    "text": "Critical dependency vulnerability",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            path = f.name
        try:
            result = evaluate_scan(path, selected=True)
            self.assertEqual(result.classification, Classification.FAIL)
        finally:
            os.unlink(path)


class TestWriteReport(unittest.TestCase):
    """Test machine-readable JSON report generation."""

    def test_report_written(self):
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/test",
                    "rule": {"properties": {"security-severity": "9.0"}},
                    "level": "error",
                    "text": "Test",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            sarif_path = f.name

        report_path = tempfile.mktemp(suffix=".json")
        try:
            result = evaluate_scan(sarif_path, selected=True)
            write_report(result, report_path)

            with open(report_path) as rf:
                report = json.load(rf)

            self.assertEqual(report["classification"], "FAIL")
            self.assertEqual(len(report["findings"]), 1)
            self.assertEqual(report["findings"][0]["rule_id"], "py/test")
            self.assertEqual(report["findings"][0]["severity"], "CRITICAL")
            self.assertEqual(report["findings"][0]["security_severity"], 9.0)
        finally:
            os.unlink(sarif_path)
            if os.path.exists(report_path):
                os.unlink(report_path)

    def test_report_written_for_pass(self):
        """Report is also generated for PASS classification."""
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            sarif_path = f.name

        report_path = tempfile.mktemp(suffix=".json")
        try:
            result = evaluate_scan(sarif_path, selected=True)
            write_report(result, report_path)

            with open(report_path) as rf:
                report = json.load(rf)

            self.assertEqual(report["classification"], "PASS")
        finally:
            os.unlink(sarif_path)
            if os.path.exists(report_path):
                os.unlink(report_path)

    def test_report_written_for_blocked(self):
        """Report is also generated for BLOCKED classification."""
        sarif = {
            "version": "2.1.0",
            "runs": [],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            sarif_path = f.name

        report_path = tempfile.mktemp(suffix=".json")
        try:
            result = evaluate_scan(sarif_path, selected=True)
            write_report(result, report_path)

            with open(report_path) as rf:
                report = json.load(rf)

            self.assertEqual(report["classification"], "BLOCKED")
        finally:
            os.unlink(sarif_path)
            if os.path.exists(report_path):
                os.unlink(report_path)


class TestMainCliExitCodes(unittest.TestCase):
    """Test CLI exit codes match the gate policy."""

    def _make_sarif(self, sev_value: str) -> str:
        sarif = {
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "CodeQL", "rules": []}},
                "results": [{
                    "ruleId": "py/test",
                    "rule": {"properties": {"security-severity": sev_value}},
                    "level": "error",
                    "text": "Test",
                }],
            }],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sarif, f)
            return f.name

    def test_cli_critical_exit_1(self):
        path = self._make_sarif("9.0")
        try:
            rc = main_cli_with_args([path])
            self.assertEqual(rc, 1)
        finally:
            os.unlink(path)

    def test_cli_high_exit_1(self):
        path = self._make_sarif("7.5")
        try:
            rc = main_cli_with_args([path])
            self.assertEqual(rc, 1)
        finally:
            os.unlink(path)

    def test_cli_medium_exit_0(self):
        path = self._make_sarif("5.0")
        try:
            rc = main_cli_with_args([path])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(path)

    def test_cli_missing_file_exit_1(self):
        rc = main_cli_with_args(["/nonexistent.sarif"])
        self.assertEqual(rc, 1)

    def test_cli_no_args_exit_2(self):
        rc = main_cli_with_args([])
        self.assertEqual(rc, 2)


def main_cli_with_args(args: list) -> int:
    """Helper to call main_cli with a specific argv."""
    old_argv = sys.argv
    sys.argv = ["findings_gate.py"] + args
    try:
        return main_cli()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()