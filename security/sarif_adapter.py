#!/usr/bin/env python3
"""
SECURITY-01-FIX: SARIF Adapter for Dependency Detector

Converts native dependency detector JSON output to SARIF 2.1.0 format.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any


@dataclass
class SarifLocation:
    """SARIF location object per SARIF 2.1.0 spec."""
    uri: str
    start_line: Optional[int] = None
    start_column: Optional[int] = None
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to SARIF 2.1.0 location format with physicalLocation.artifactLocation.uri"""
        artifact_location = {"uri": self.uri}
        physical_location = {"artifactLocation": artifact_location}
        result = {"physicalLocation": physical_location}
        return result


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
    locations: List["SarifLocation"]
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
    column_kind: str = "utf16"
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
        if self.automation_details:
            result["automationDetails"] = self.automation_details
        return result


class SarifAdapter:
    """Converts native dependency detector results to SARIF 2.1.0."""

    # SARIF level mapping
    SEVERITY_MAP = {
        "ERROR": "error",
        "WARNING": "warning",
        "NOTE": "note",
        "NONE": "none",
    }

    def __init__(self):
        self.rule_index = 0
        self.rules: Dict[str, SarifRule] = {}

    def _get_rule_id(self, dep_type: str, status: str) -> str:
        """Generate a rule ID for the dependency type and status."""
        return f"SEC01-{dep_type.upper()}-{status.upper()}"

    def _get_rule(self, dep_type: str, status: str) -> SarifRule:
        """Get or create a SARIF rule for the dependency type and status."""
        rule_id = self._get_rule_id(dep_type, status)
        if rule_id in self.rules:
            return self.rules[rule_id]

        # Create rule based on type and status
        if status == "CHANGED":
            level = "warning"
            short_desc = f"{dep_type} version change detected"
            full_desc = f"A new version of {dep_type} is available that does not satisfy the declared constraint."
        elif status == "CONSTRAINT_UNSATISFIED":
            level = "error"
            short_desc = f"{dep_type} constraint unsatisfied"
            full_desc = f"The latest version of {dep_type} does not satisfy the declared constraint in Terraform configuration."
        elif status == "LOOKUP_ERROR":
            level = "warning"
            short_desc = f"{dep_type} lookup failed"
            full_desc = f"Failed to check for updates for {dep_type}."
        elif status == "UPDATE_AVAILABLE":
            level = "note"
            short_desc = f"{dep_type} update available"
            full_desc = f"A new version of {dep_type} is available within the declared constraint."
        else:  # CURRENT
            level = "note"
            short_desc = f"{dep_type} is current"
            full_desc = f"{dep_type} is up to date within the declared constraint."

        rule = SarifRule(
            id=f"SEC01-{dep_type.upper()}-{status.upper()}",
            name=f"{dep_type} {status}",
            short_description=SarifMessage(text=short_desc),
            full_description=SarifMessage(text=full_desc),
            default_configuration={"level": level},
        )
        self.rules[rule_id] = rule
        return rule

    def convert(self, native_result: dict) -> dict:
        """Convert native dependency detector result to SARIF 2.1.0."""
        native_deps = native_result.get("dependencies", [])

        results = []
        rules = {}

        for dep in native_deps:
            dep_type = dep.get("type", "unknown")
            status = dep.get("status", "UNKNOWN")
            name = dep.get("name", "unknown")
            source = dep.get("source", "")
            current_version = dep.get("current_version", "")
            available_version = dep.get("available_version")
            details = dep.get("details", "")

            rule_id = self._get_rule_id(dep_type, status)
            rule = self._get_rule(dep_type, status)
            rules[rule_id] = rule

            # Determine SARIF level
            if status == "CONSTRAINT_UNSATISFIED":
                level = "error"
            elif status in ("CHANGED", "LOOKUP_ERROR"):
                level = "warning"
            else:
                level = "note"

            # Create location
            locations = []
            if source:
                # Extract line number if possible (simplified)
                locations.append(SarifLocation(
                    uri=source,
                    start_line=None,
                    start_column=None,
                ))

            # Create message
            message_text = f"{name} ({dep_type}): {status}"
            if available_version:
                message_text += f" - available: {available_version}"
            message_text += f". Current: {dep.get('current_version', 'unknown')}. {details}"

            result = SarifResult(
                rule_id=rule.id,
                level=level,
                message=SarifMessage(text=message_text),
                locations=locations,
                properties={
                    "dependency_name": name,
                    "dependency_type": dep_type,
                    "current_version": dep.get("current_version", ""),
                    "available_version": available_version,
                    "deployment_id": dep.get("deployment_id", ""),
                },
            )
            results.append(result)

        # Build tool driver
        tool = {
            "driver": {
                "name": "Mays-Orders-AWS Security Dependency Detector",
                "version": "1.0.0",
                "informationUri": "https://github.com/maynowak/mays-order-aws",
                "rules": [r.to_dict() for r in rules.values()],
            }
        }

        # Build run
        run = SarifRun(
            tool=tool,
            results=results,
            automation_details={
                "id": "security-01-dependency-check",
                "description": "SECURITY-01 Dependency Change Detection"
            }
        )

        # Build SARIF document
        sarif = {
            "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [run.to_dict()],
        }

        return sarif


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