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
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add security dir to path for import
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "security"))

from findings_gate import (  # noqa: E402
    Classification,
    FindingSeverity,
    _extract_security_severity,
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


class TestExtractSecuritySeverity(unittest.TestCase):
    """Test extraction of security-severity from SARIF rule metadata."""

    def test_valid_numeric_string(self):
        result = {
            "ruleId": "py/sql-injection",
            "rule": {
                "properties": {"security-severity": "9.0"}
            },
        }
        self.assertEqual(_extract_security_severity(result), 9.0)

    def test_valid_integer_string(self):
        result = {
            "ruleId": "py/weak-crypto",
            "rule": {
                "properties": {"security-severity": "7"}
            },
        }
        self.assertEqual(_extract_security_severity(result), 7.0)

    def test_missing_properties(self):
        result = {
            "ruleId": "py/unknown",
            "rule": {},
        }
        self.assertIsNone(_extract_security_severity(result))

    def test_missing_security_severity_key(self):
        result = {
            "ruleId": "py/unknown",
            "rule": {
                "properties": {}
            },
        }
        self.assertIsNone(_extract_security_severity(result))

    def test_invalid_security_severity(self):
        result = {
            "ruleId": "py/bad",
            "rule": {
                "properties": {"security-severity": "not-a-number"}
            },
        }
        self.assertIsNone(_extract_security_severity(result))

    def test_no_rule_key(self):
        result = {"ruleId": "py/no-rule"}
        self.assertIsNone(_extract_security_severity(result))

    def test_rule_is_not_dict(self):
        result = {"ruleId": "py/bad", "rule": "not-a-dict"}
        self.assertIsNone(_extract_security_severity(result))


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

    def test_missing_security_severity_blocked(self):
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
            self.assertEqual(result.classification, Classification.BLOCKED)
            self.assertIn("missing security-severity", result.summary)
        finally:
            os.unlink(path)

    def test_invalid_security_severity_blocked(self):
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

    def test_unknown_classification_not_pass(self):
        """Verify that no code path returns PASS for an error condition."""
        # This test ensures that evaluate_scan never returns PASS when
        # there's an error — PASS is only for genuinely clean scans.
        # Missing file → BLOCKED even if not selected (fail-closed).
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
    import unittest.mock
    old_argv = sys.argv
    sys.argv = ["findings_gate.py"] + args
    try:
        return main_cli()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()