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
from functools import total_ordering
from itertools import zip_longest
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


@total_ordering
class Version:
    """SemVer-like version with numeric core and SemVer pre-release ordering.

    Terraform provider versions are normally ``MAJOR.MINOR.PATCH``.  Missing
    core components compare as zero (``1.2`` == ``1.2.0``).  Build metadata is
    ignored; pre-release identifiers use SemVer precedence.
    """

    __slots__ = ("core", "prerelease", "original")

    def __init__(self, core: tuple[int, ...], prerelease: tuple[tuple[int, Any], ...] = (), original: str = ""):
        if not core:
            raise ValueError("version core must not be empty")
        self.core = tuple(core)
        self.prerelease = tuple(prerelease)
        self.original = original

    @classmethod
    def parse(cls, value: str) -> "Version":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"invalid version: {value!r}")
        raw = value.strip()
        normalized = raw[1:] if raw[:1] in ("v", "V") else raw
        normalized = normalized.split("+", 1)[0]
        if "-" in normalized:
            core_part, prerelease_part = normalized.split("-", 1)
        else:
            core_part, prerelease_part = normalized, ""

        core_parts = core_part.split(".")
        if not core_parts or any(not part.isdigit() for part in core_parts):
            raise ValueError(f"invalid version core: {value!r}")

        prerelease: list[tuple[int, Any]] = []
        if prerelease_part:
            for identifier in prerelease_part.split("."):
                if not identifier:
                    raise ValueError(f"invalid pre-release: {value!r}")
                if identifier.isdigit():
                    prerelease.append((0, int(identifier)))
                else:
                    prerelease.append((1, identifier))

        return cls(tuple(int(part) for part in core_parts), tuple(prerelease), raw)

    def _compare(self, other: "Version") -> int:
        if not isinstance(other, Version):
            return NotImplemented

        max_len = max(len(self.core), len(other.core))
        self_core = self.core + (0,) * (max_len - len(self.core))
        other_core = other.core + (0,) * (max_len - len(other.core))
        if self_core != other_core:
            return -1 if self_core < other_core else 1

        if not self.prerelease and not other.prerelease:
            return 0
        if not self.prerelease:
            return 1
        if not other.prerelease:
            return -1

        for left, right in zip_longest(self.prerelease, other.prerelease):
            if left is None:
                return -1
            if right is None:
                return 1
            if left == right:
                continue
            # Numeric identifiers have lower precedence than alphanumeric ones.
            if left[0] != right[0]:
                return -1 if left[0] < right[0] else 1
            return -1 if left[1] < right[1] else 1
        return 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._compare(other) == 0

    def __lt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._compare(other) < 0

    def __hash__(self) -> int:
        return hash((self.core, self.prerelease))

    def __repr__(self) -> str:
        return f"Version({self.original or '.'.join(map(str, self.core))!r})"


def _parse_single_constraint(constraint: str) -> tuple[str, str]:
    """Parse one constraint such as ``>= 6.0`` or ``~> 0.11``."""
    value = constraint.strip()
    if not value:
        raise ValueError("empty version constraint")
    operators = ("!=", ">=", "<=", "~>", ">", "<", "=")
    for op in operators:
        if value.startswith(op):
            version = value[len(op):].strip()
            if not version:
                raise ValueError(f"missing version in constraint: {constraint!r}")
            return op, version
    # No operator found, assume exact match.
    return "=", value


def parse_version_constraint(version: str) -> tuple[str, str]:
    """Parse a single constraint; raises ``ValueError`` for combined input."""
    constraints = parse_version_constraints(version)
    if len(constraints) != 1:
        raise ValueError(f"expected one constraint, got {len(constraints)}: {version!r}")
    return constraints[0]


def parse_version_constraints(constraint: str) -> list[tuple[str, str]]:
    """Parse comma-separated Terraform constraints (all must match)."""
    if not isinstance(constraint, str) or not constraint.strip():
        raise ValueError("empty version constraint")
    parts = [part.strip() for part in constraint.split(",") if part.strip()]
    if not parts:
        raise ValueError("empty version constraint")
    return [_parse_single_constraint(part) for part in parts]


def _pessimistic_upper_bound(constraint_version: Version) -> Version:
    """Return the exclusive upper bound for Terraform's ``~>`` operator.

    HashiCorp semantics (the second-to-last specified component may increment):

    * ``~> 1``      -> ``>= 1.0.0, < 2.0.0``
    * ``~> 1.2``    -> ``>= 1.2.0, < 2.0.0``
    * ``~> 1.2.3``  -> ``>= 1.2.3, < 1.3.0``
    * ``~> 0.11``   -> ``>= 0.11.0, < 1.0.0``
    * ``~> 0.11.0`` -> ``>= 0.11.0, < 0.12.0``
    """
    core = list(constraint_version.core)
    if len(core) == 1:
        upper = (core[0] + 1, 0, 0)
    else:
        upper = tuple(core[:-2] + [core[-2] + 1, 0])
    return Version(upper)


def _version_satisfies_single(version: Version, op: str, constraint_version: Version) -> bool:
    if op == "=":
        return version == constraint_version
    if op == "!=":
        return version != constraint_version
    if op == ">":
        return version > constraint_version
    if op == "<":
        return version < constraint_version
    if op == ">=":
        return version >= constraint_version
    if op == "<=":
        return version <= constraint_version
    if op == "~>":
        return version >= constraint_version and version < _pessimistic_upper_bound(constraint_version)
    raise ValueError(f"unsupported version operator: {op!r}")


def version_satisfies_constraint(version: str, constraint: str) -> bool:
    """Check a version against one or more comma-separated Terraform constraints."""
    try:
        parsed_version = Version.parse(version)
        constraints = parse_version_constraints(constraint)
        return all(
            _version_satisfies_single(parsed_version, op, Version.parse(cv))
            for op, cv in constraints
        )
    except (TypeError, ValueError):
        return False


def sort_versions(versions: list[str], reverse: bool = True) -> list[str]:
    """Sort versions numerically; invalid entries are dropped."""
    parsed: list[tuple[Version, str]] = []
    for version in versions:
        try:
            parsed.append((Version.parse(version), version))
        except (TypeError, ValueError):
            continue
    parsed.sort(key=lambda item: item[0], reverse=reverse)
    return [version for _, version in parsed]


def is_prerelease(version: str) -> bool:
    """Return True for SemVer pre-release versions (e.g. ``1.0.0-rc.1``)."""
    try:
        return bool(Version.parse(version).prerelease)
    except (TypeError, ValueError):
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
    """Compare two versions numerically, including pre-release precedence."""
    try:
        left = Version.parse(v1)
        right = Version.parse(v2)
    except (TypeError, ValueError):
        return 0
    if left < right:
        return -1
    if left > right:
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


def detect_all_changes(repo_root: Optional[Path] = None) -> DetectionResult:
    """Run all dependency checks and return consolidated result.

    ``repo_root`` removes the former dependency on the caller's working
    directory.  It defaults to this repository (parent of ``security/``).
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    run = run_id()
    timestamp = datetime.now(timezone.utc).isoformat() + "Z"
    all_deps = []

    # Check Terraform providers
    tf_file = root / "terraform/main.tf"
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