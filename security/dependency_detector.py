#!/usr/bin/env python3
"""
SECURITY-01: Dependency Change Detector

Detects changes in external dependencies for the Mays-Orders-AWS repository.

Currently monitors:
- Terraform providers (from terraform/main.tf)
- Future: GitHub Actions, Python packages, npm packages, git submodules

Output: Machine-readable JSON with DEPENDENCIES_CURRENT or DEPENDENCY_CHANGE_DETECTED
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import urllib.request
import urllib.error


@dataclass
class Dependency:
    """Represents a single dependency."""
    name: str
    type: str  # "terraform_provider", "github_action", "python_package", "npm_package", "git_submodule"
    source: str  # file path where dependency is declared
    current_version: str
    current_reference: Optional[str] = None  # for git refs, commits, etc.
    available_version: Optional[str] = None
    available_reference: Optional[str] = None
    status: str = "UNKNOWN"  # CURRENT, CHANGED, ERROR, UNKNOWN
    details: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")


@dataclass
class DetectionResult:
    """Overall result of dependency detection."""
    status: str  # DEPENDENCIES_CURRENT, DEPENDENCY_CHANGE_DETECTED, DEPENDENCY_CHECK_ERROR
    dependencies: list[Dependency]
    run_id: str
    timestamp: str
    summary: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "status": self.status,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "dependencies": [asdict(d) for d in self.dependencies]
        }, indent=2)


def parse_version_constraint(version: str) -> tuple[str, str]:
    """
    Parse version constraint like ">= 6.0", "~> 0.11", "= 1.0.0".
    Returns (operator, version).
    """
    version = version.strip()
    operators = [">=", "<=", "~>", ">", "<", "=", "!="]
    for op in operators:
        if version.startswith(op):
            return op, version[len(op):].strip()
    # No operator found, assume exact match
    return "=", version


def version_satisfies_constraint(version: str, constraint: str) -> bool:
    """
    Check if a version satisfies a constraint.
    Simplified implementation for common Terraform constraints.
    """
    op, constraint_version = parse_version_constraint(constraint)

    def parse_ver(v: str) -> tuple:
        # Parse semantic version, handle pre-release suffixes
        parts = v.split("-")[0].split(".")
        return tuple(int(p) for p in parts)

    try:
        v = parse_ver(version)
        cv = parse_ver(constraint_version)
    except ValueError:
        return False

    if op == "=":
        return v == cv
    elif op == "!=":
        return v != cv
    elif op == ">":
        return v > cv
    elif op == "<":
        return v < cv
    elif op == ">=":
        return v >= cv
    elif op == "<=":
        return v <= cv
    elif op == "~>":
        # Pessimistic constraint: ~> 1.2 means >= 1.2 and < 1.3
        # ~> 1.2.3 means >= 1.2.3 and < 1.2.4
        parts = constraint_version.split(".")
        if len(parts) >= 2:
            major = int(parts[0])
            minor = int(parts[1])
            if len(parts) == 2:
                return v >= (major, minor) and v < (major, minor + 1)
            elif len(parts) >= 3:
                patch = int(parts[2])
                return v >= (major, minor, patch) and v < (major, minor, patch + 1)
        return False

    return False


def run_id() -> str:
    """Generate a unique run identifier."""
    return f"sec01-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


def parse_terraform_providers(tf_file: Path) -> list[Dependency]:
    """Parse Terraform required_providers from main.tf."""
    deps = []

    if not tf_file.exists():
        return deps

    content = tf_file.read_text()

    # Find required_providers block with proper brace matching
    start = content.find('required_providers')
    if start == -1:
        return deps

    brace_count = 0
    end = -1
    for i, ch in enumerate(content[start:], start):
        if ch == '{':
            brace_count += 1
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    if end == -1:
        return deps

    providers_block = content[start:end]

    # Parse each provider: name = { source = "...", version = "..." }
    provider_re = re.compile(
        r'(\w+)\s*=\s*\{[^}]*source\s*=\s*"([^"]+)"[^}]*version\s*=\s*"([^"]+)"',
        re.DOTALL
    )

    for match in provider_re.finditer(providers_block):
        name = match.group(1)
        source = match.group(2)
        version = match.group(3)

        deps.append(Dependency(
            name=name,
            type="terraform_provider",
            source=str(tf_file),
            current_version=version,
            current_reference=source,
            details=f"Terraform provider {name} from {source}"
        ))

    return deps


def fetch_latest_terraform_provider_version(provider_source: str, current_version: str) -> tuple[Optional[str], str]:
    """
    Fetch latest version from Terraform Registry.
    Returns (latest_version, details)
    """
    # Parse source: "hashicorp/aws" -> namespace="hashicorp", name="aws"
    parts = provider_source.split("/")
    if len(parts) != 2:
        return None, f"Invalid provider source format: {provider_source}"

    namespace, name = parts

    # Query Terraform Registry API
    url = f"https://registry.terraform.io/v1/providers/{namespace}/{name}/versions"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mays-Orders-AWS-SECURITY-01/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        versions = data.get("versions", [])
        if not versions:
            return None, "No versions found in registry"

        # Find latest stable version (not beta, alpha, rc)
        stable_versions = []
        for v in versions:
            version = v.get("version", "")
            if version and not any(x in version.lower() for x in ["alpha", "beta", "rc"]):
                stable_versions.append(version)

        if not stable_versions:
            # Fallback: use latest version even if pre-release
            latest = versions[0].get("version", "")
            return latest, f"Latest (pre-release): {latest}"

        latest = stable_versions[0]
        return latest, f"Latest stable: {latest}"

    except urllib.error.HTTPError as e:
        return None, f"HTTP error {e.code} querying registry"
    except urllib.error.URLError as e:
        return None, f"Network error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two semantic versions.
    Returns: -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    def parse_ver(v: str) -> tuple:
        parts = v.split("-")[0].split(".")
        return tuple(int(p) for p in parts)

    try:
        v1_parts = parse_ver(v1)
        v2_parts = parse_ver(v2)
    except ValueError:
        return 0

    if v1_parts < v2_parts:
        return -1
    elif v1_parts > v2_parts:
        return 1
    return 0


def check_terraform_providers(tf_file: Path) -> list[Dependency]:
    """Check all Terraform providers for updates."""
    deps = parse_terraform_providers(tf_file)

    for dep in deps:
        if dep.type == "terraform_provider":
            latest, details = fetch_latest_terraform_provider_version(
                dep.current_reference or "", dep.current_version
            )
            dep.available_version = latest
            dep.details += f"; {details}"

            if not latest:
                dep.status = "LOOKUP_ERROR"
                continue

            # Check if latest version satisfies the current constraint
            constraint_satisfied = version_satisfies_constraint(latest, dep.current_version)

            if not constraint_satisfied:
                # Latest version doesn't satisfy the constraint
                dep.status = "CONSTRAINT_UNSATISFIED"
            else:
                # Latest satisfies constraint - check if it's actually newer
                cmp_result = compare_versions(latest, dep.current_version)
                if cmp_result > 0:
                    # Latest is newer and satisfies constraint
                    dep.status = "UPDATE_AVAILABLE"
                else:
                    # Latest is same or older
                    dep.status = "CURRENT"

    return deps


def detect_all_changes() -> DetectionResult:
    """Run all dependency checks and return consolidated result."""
    run = run_id()
    timestamp = datetime.now(timezone.utc).isoformat() + "Z"
    all_deps = []

    # Check Terraform providers
    tf_file = Path("terraform/main.tf")
    if tf_file.exists():
        tf_deps = check_terraform_providers(tf_file)
        all_deps.extend(tf_deps)

    # TODO: Add GitHub Actions workflow detection
    # TODO: Add Python package detection (if requirements.txt/pyproject.toml added)
    # TODO: Add npm package detection (if package.json added)
    # TODO: Add git submodule detection

    # Determine overall status
    changed = [d for d in all_deps if d.status in ("CHANGED", "UPDATE_AVAILABLE")]
    constraint_unsatisfied = [d for d in all_deps if d.status == "CONSTRAINT_UNSATISFIED"]
    errors = [d for d in all_deps if d.status in ("ERROR", "LOOKUP_ERROR")]

    if errors:
        status = "DEPENDENCY_CHECK_ERROR"
        summary = f"{len(errors)} dependency check(s) failed"
    elif constraint_unsatisfied:
        status = "DEPENDENCY_CHANGE_DETECTED"
        summary = f"{len(constraint_unsatisfied)} dependency constraint(s) unsatisfied"
    elif changed:
        status = "DEPENDENCY_CHANGE_DETECTED"
        summary = f"{len(changed)} dependency update(s) available"
    else:
        status = "DEPENDENCIES_CURRENT"
        summary = "All dependencies are current"

    return DetectionResult(
        status=status,
        dependencies=all_deps,
        run_id=run_id(),
        timestamp=datetime.now(timezone.utc).isoformat() + "Z",
        summary=summary
    )


def main() -> int:
    """Main entry point."""
    try:
        result = detect_all_changes()
        print(result.to_json())

        # Exit code: 0 = current, 1 = changes detected, 2 = error
        if result.status == "DEPENDENCY_CHECK_ERROR":
            return 2
        elif result.status == "DEPENDENCY_CHANGE_DETECTED":
            return 1
        return 0

    except Exception as e:
        error_result = DetectionResult(
            status="DEPENDENCY_CHECK_ERROR",
            dependencies=[],
            run_id=run_id(),
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            summary=f"Detector error: {e}"
        )
        print(error_result.to_json())
        return 2


if __name__ == "__main__":
    sys.exit(main())