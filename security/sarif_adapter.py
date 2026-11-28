#!/usr/bin/env python3
"""
SECURITY-01-FIX: SARIF Adapter for Dependency Detector

Converts native dependency detector JSON output to SARIF 2.1.0 format.

Only actionable findings are emitted.  ``CURRENT`` dependencies are omitted so
the previous note-level alert for an up-to-date provider resolves automatically
on the next upload.  Artifact URIs are repository-relative and every result has
a stable partial fingerprint for alert correlation.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SarifLocation:
    """SARIF location object per SARIF 2.1.0 spec."""
    uri: str
    start_line: Optional[int] = None
    start_column: Optional[int] = None
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def to_dict(self) -> dict:
        artifact_location = {"uri": self.uri}
        physical_location = {"artifactLocation": artifact_location}
        if self.start_line is not None:
            region = {"startLine": self.start_line}
            if self.start_column is not None:
                region["startColumn"] = self.start_column
            if self.end_line is not None:
                region["endLine"] = self.end_line
            if self.end_column is not None:
                region["endColumn"] = self.end_column
            physical_location["region"] = region
        return {"physicalLocation": physical_location}


@dataclass
class SarifMessage:
    """SARIF message object."""
    text: str
    markdown: Optional[str] = None

    def to_dict(self) -> dict:
        result = {"text": self.text}
        if self.markdown:
            result["markdown"] = self.markdown
        return result


@dataclass
class SarifRule:
    """SARIF rule object."""
    id: str
    name: str
    short_description: SarifMessage
    full_description: Optional[SarifMessage] = None
    help: Optional[SarifMessage] = None
    help_uri: Optional[str] = None
    default_configuration: Optional[dict] = None

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "shortDescription": self.short_description.to_dict(),
        }
        if self.full_description:
            result["fullDescription"] = self.full_description.to_dict()
        if self.help:
            result["help"] = self.help.to_dict()
        if self.help_uri:
            result["helpUri"] = self.help_uri
        if self.default_configuration:
            result["defaultConfiguration"] = self.default_configuration
        return result


@dataclass
class SarifResult:
    """SARIF result object."""
    rule_id: str
    level: str  # "none", "note", "warning", "error"
    message: SarifMessage
    locations: List[SarifLocation]
    rule_index: Optional[int] = None
    partial_fingerprints: Optional[dict] = None
    properties: Optional[dict] = None

    def to_dict(self) -> dict:
        result = {
            "ruleId": self.rule_id,
            "level": self.level,
            "message": self.message.to_dict(),
            "locations": [loc.to_dict() for loc in self.locations],
        }
        if self.rule_index is not None:
            result["ruleIndex"] = self.rule_index
        if self.partial_fingerprints:
            result["partialFingerprints"] = self.partial_fingerprints
        if self.properties:
            result["properties"] = self.properties
        return result


@dataclass
class SarifRun:
    """SARIF run object."""
    tool: dict
    results: List[SarifResult]
    column_kind: str = "utf16CodeUnits"
    original_uri_base_ids: Optional[dict] = None
    automation_details: Optional[dict] = None

    def to_dict(self) -> dict:
        result = {
            "tool": self.tool,
            "results": [r.to_dict() for r in self.results],
            "columnKind": self.column_kind,
        }
        if self.original_uri_base_ids:
            result["originalUriBaseIds"] = self.original_uri_base_ids
        if self.automation_details and "description" in self.automation_details:
            desc = self.automation_details["description"]
            if isinstance(desc, dict) and "text" in desc:
                result["automationDetails"] = self.automation_details
        return result


class SarifAdapter:
    """Converts native dependency detector results to SARIF 2.1.0."""

    TOOL_NAME = "Mays-Orders-AWS Security Dependency Detector"
    TOOL_VERSION = "2.0.0"
    AUTOMATION_ID = "dependency-check"
    FINGERPRINT_KEY = "dependencyIdentity/v1"

    # Actionable statuses and their SARIF levels.  CURRENT is intentionally
    # absent: up-to-date dependencies must not create findings.
    STATUS_LEVEL = {
        "CHANGED": "warning",
        "UPDATE_AVAILABLE": "note",
        "CONSTRAINT_UNSATISFIED": "error",
        "LOCK_MISSING": "warning",
        "LOCK_CONSTRAINT_DRIFT": "warning",
        "REGISTRY_INCOMPLETE": "warning",
        "LOOKUP_ERROR": "warning",
        "ERROR": "error",
        "UNKNOWN": "warning",
    }

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = (
            Path(repo_root).resolve() if repo_root is not None
            else Path(__file__).resolve().parents[1]
        )
        self.rules: Dict[str, SarifRule] = {}

    def _normalize_uri(self, uri: str) -> str:
        """Return a repository-relative POSIX URI when possible."""
        if not uri:
            return ""
        raw = str(uri).replace("\\", "/")
        if raw.startswith("file://"):
            raw = raw[7:]
        path = Path(raw)
        if not path.is_absolute():
            return path.as_posix()

        try:
            return path.resolve().relative_to(self.repo_root).as_posix()
        except (OSError, ValueError):
            # Defensive fallback for absolute paths outside the checkout:
            # preserve the repository-relative suffix when recognizable.
            parts = path.parts
            for marker in ("terraform", "installer", "security", "lambda", "module_builder", "scripts"):
                if marker in parts:
                    return "/".join(parts[parts.index(marker):])
            return path.name

    def _get_rule_id(self, dep_type: str, status: str) -> str:
        return f"SEC01-{dep_type.upper()}-{status.upper()}"

    def _rule_definition(self, dep_type: str, status: str) -> tuple[str, str, str]:
        if status == "CHANGED":
            return (
                "warning",
                f"{dep_type} version change detected",
                f"A new {dep_type} version is available but does not satisfy the declared constraint.",
            )
        if status == "UPDATE_AVAILABLE":
            return (
                "note",
                f"{dep_type} update available",
                f"A newer {dep_type} version satisfies the declared constraint.",
            )
        if status == "CONSTRAINT_UNSATISFIED":
            return (
                "error",
                f"{dep_type} locked version violates constraint",
                f"The version in .terraform.lock.hcl does not satisfy the declared {dep_type} constraint.",
            )
        if status == "LOCK_MISSING":
            return (
                "warning",
                f"{dep_type} missing from lock file",
                f"The {dep_type} is declared but has no entry in .terraform.lock.hcl.",
            )
        if status == "LOCK_CONSTRAINT_DRIFT":
            return (
                "warning",
                f"{dep_type} lock constraint drift",
                f"The constraints recorded in .terraform.lock.hcl differ from the declared constraint; updates are suppressed until reconciled.",
            )
        if status == "REGISTRY_INCOMPLETE":
            return (
                "warning",
                f"{dep_type} registry data incomplete",
                f"The registry response is missing usable or newer versions; no update is recommended.",
            )
        if status == "LOOKUP_ERROR":
            return (
                "warning",
                f"{dep_type} lookup failed",
                f"Failed to query the registry for {dep_type}.",
            )
        if status == "ERROR":
            return (
                "error",
                f"{dep_type} check error",
                f"The dependency check for {dep_type} failed.",
            )
        return (
            "warning",
            f"{dep_type} status unknown",
            f"The dependency status for {dep_type} could not be classified.",
        )

    def _get_rule(self, dep_type: str, status: str) -> SarifRule:
        rule_id = self._get_rule_id(dep_type, status)
        if rule_id in self.rules:
            return self.rules[rule_id]

        level, short_desc, full_desc = self._rule_definition(dep_type, status)
        rule = SarifRule(
            id=rule_id,
            name=f"{dep_type} {status}",
            short_description=SarifMessage(text=short_desc),
            full_description=SarifMessage(text=full_desc),
            default_configuration={"level": level},
        )
        self.rules[rule_id] = rule
        return rule

    def _fingerprint(self, dep_type: str, name: str, source: str, rule_id: str) -> str:
        identity = f"{dep_type}|{name}|{source}|{rule_id}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def _message(self, dep: dict, status: str, source: str) -> str:
        name = dep.get("name", "unknown")
        dep_type = dep.get("type", "unknown")
        declared = dep.get("current_version", "")
        locked = dep.get("locked_version")
        latest_available = dep.get("latest_available")
        latest_compatible = dep.get("latest_compatible")
        details = dep.get("details", "")

        parts = [f"{name} ({dep_type}): {status}."]
        if declared:
            parts.append(f"Declared constraint: {declared}.")
        parts.append(f"Locked version: {locked or 'missing'}.")
        parts.append(f"Latest available: {latest_available or 'unknown'}.")
        parts.append(f"Latest compatible: {latest_compatible or 'none'}.")
        if details:
            parts.append(details)
        return " ".join(parts)

    def convert(self, native_result: dict) -> dict:
        """Convert native dependency detector result to SARIF 2.1.0."""
        self.rules = {}
        native_deps = native_result.get("dependencies", [])
        results: List[SarifResult] = []

        for dep in native_deps:
            dep_type = str(dep.get("type", "unknown"))
            status = str(dep.get("status", "UNKNOWN")).upper()
            if status == "CURRENT":
                # Up-to-date dependencies are not findings.  This also lets a
                # previously uploaded CURRENT alert resolve automatically.
                continue
            if status not in self.STATUS_LEVEL:
                status = "UNKNOWN"

            name = str(dep.get("name", "unknown"))
            source = self._normalize_uri(str(dep.get("source", "")))
            rule = self._get_rule(dep_type, status)
            rule_index = list(self.rules.keys()).index(rule.id)
            level = self.STATUS_LEVEL[status]

            locations = [SarifLocation(uri=source)] if source else []
            properties = {
                "dependency_name": name,
                "dependency_type": dep_type,
                "status": status,
                "declared_constraint": dep.get("current_version", ""),
                "current_version": dep.get("current_version", ""),
                "locked_version": dep.get("locked_version"),
                "latest_available": dep.get("latest_available"),
                "latest_compatible": dep.get("latest_compatible"),
                "available_version": dep.get("available_version"),
                "source": source,
            }

            results.append(SarifResult(
                rule_id=rule.id,
                level=level,
                message=SarifMessage(text=self._message(dep, status, source)),
                locations=locations,
                rule_index=rule_index,
                partial_fingerprints={
                    self.FINGERPRINT_KEY: self._fingerprint(dep_type, name, source, rule.id),
                },
                properties=properties,
            ))

        tool = {
            "driver": {
                "name": self.TOOL_NAME,
                "version": self.TOOL_VERSION,
                "semanticVersion": self.TOOL_VERSION,
                "informationUri": "https://github.com/maynowak/mays-order-aws",
                "rules": [rule.to_dict() for rule in self.rules.values()],
            }
        }

        run = SarifRun(
            tool=tool,
            results=results,
            automation_details={
                "id": self.AUTOMATION_ID,
                "description": {"text": "Dependency Change Detection (dependency-check)"},
            },
        )

        return {
            "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [run.to_dict()],
        }


def main() -> int:
    """Convert native dependency result to SARIF."""
    if len(sys.argv) < 3:
        print("Usage: python3 sarif_adapter.py <input_json> <output_sarif>", file=sys.stderr)
        return 1

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    if not input_file.exists():
        print(f"Input file not found: {input_file}", file=sys.stderr)
        return 1

    try:
        with open(input_file) as f:
            native_result = json.load(f)

        adapter = SarifAdapter()
        sarif = adapter.convert(native_result)

        with open(output_file, "w") as f:
            json.dump(sarif, f, indent=2)

        print(f"SARIF written to {output_file}")
        return 0

    except Exception as e:
        print(f"Conversion error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
