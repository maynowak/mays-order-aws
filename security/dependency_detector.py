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
from typing import Any, Callable, Optional
import urllib.request
import urllib.error


@dataclass
class Dependency:
    """Represents a single dependency.

    ``current_version`` is the declared Terraform constraint (legacy name).
    ``locked_version`` is the version from ``.terraform.lock.hcl``.
    ``latest_available`` is the newest registry version; ``latest_compatible``
    is the newest version that satisfies the declared constraint.
    ``available_version`` remains as a compatibility alias for the recommended
    update target (latest compatible).
    """
    name: str
    type: str  # "terraform_provider", "github_action", "python_package", "npm_package", "git_submodule"
    source: str  # repo-relative file path where dependency is declared
    current_version: str
    current_reference: Optional[str] = None  # for git refs, commits, etc.
    available_version: Optional[str] = None
    available_reference: Optional[str] = None
    status: str = "UNKNOWN"  # CURRENT, UPDATE_AVAILABLE, CONSTRAINT_UNSATISFIED, LOCK_MISSING, REGISTRY_INCOMPLETE, LOOKUP_ERROR, ERROR, UNKNOWN
    details: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    locked_version: Optional[str] = None
    latest_available: Optional[str] = None
    latest_compatible: Optional[str] = None
    locked_constraints: Optional[str] = None


@dataclass
class LockedProvider:
    """A provider entry parsed from ``.terraform.lock.hcl``."""
    version: Optional[str] = None
    constraints: Optional[str] = None


@dataclass
class RegistryVersions:
    """Sorted registry versions, split into stable and pre-release."""
    stable: list[str]
    prerelease: list[str]
    details: str = ""


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


def _normalize_provider_source(source: str) -> str:
    """Normalize ``registry.terraform.io/hashicorp/aws`` to ``hashicorp/aws``."""
    value = source.strip()
    for prefix in ("registry.terraform.io/", "registry.opentofu.org/"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value


def parse_terraform_lock(lock_file: Path) -> dict[str, LockedProvider]:
    """Parse provider versions and constraints from ``.terraform.lock.hcl``."""
    if not lock_file or not lock_file.exists():
        return {}

    try:
        text = lock_file.read_text()
    except OSError:
        return {}

    entries: dict[str, LockedProvider] = {}
    provider_re = re.compile(r'provider\s+"([^"]+)"\s*\{')
    for match in provider_re.finditer(text):
        source = _normalize_provider_source(match.group(1))
        start = match.end() - 1
        depth = 0
        body = ""
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    body = text[start + 1:index]
                    break
        version_match = re.search(r'\bversion\s*=\s*"([^"]+)"', body)
        constraints_match = re.search(r'\bconstraints\s*=\s*"([^"]+)"', body)
        entries[source] = LockedProvider(
            version=version_match.group(1) if version_match else None,
            constraints=constraints_match.group(1) if constraints_match else None,
        )
    return entries


def fetch_terraform_provider_versions(provider_source: str) -> tuple[Optional[RegistryVersions], str]:
    """Fetch and numerically sort all registry versions for a provider."""
    normalized = _normalize_provider_source(provider_source)
    parts = normalized.split("/")
    if len(parts) != 2:
        return None, f"Invalid provider source format: {provider_source}"

    namespace, name = parts
    url = f"https://registry.terraform.io/v1/providers/{namespace}/{name}/versions"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mays-Orders-AWS-SECURITY-01/2.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        raw_versions = data.get("versions", [])
        if not isinstance(raw_versions, list) or not raw_versions:
            return None, "No versions found in registry"

        versions: list[str] = []
        for entry in raw_versions:
            if isinstance(entry, dict):
                version = entry.get("version", "")
                if isinstance(version, str) and version.strip():
                    versions.append(version.strip())

        if not versions:
            return None, "No valid versions found in registry"

        stable = sort_versions([v for v in versions if not is_prerelease(v)])
        prerelease = sort_versions([v for v in versions if is_prerelease(v)])
        if not stable and not prerelease:
            return None, "No parseable versions found in registry"

        details = f"Registry: {len(stable)} stable, {len(prerelease)} pre-release"
        return RegistryVersions(stable=stable, prerelease=prerelease, details=details), details

    except urllib.error.HTTPError as e:
        return None, f"HTTP error {e.code} querying registry"
    except urllib.error.URLError as e:
        return None, f"Network error: {e}"
    except (ValueError, TypeError) as e:
        return None, f"Invalid registry response: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def fetch_latest_terraform_provider_version(provider_source: str, current_version: str) -> tuple[Optional[str], str]:
    """Compatibility wrapper returning the newest stable (or pre-release) version."""
    registry, details = fetch_terraform_provider_versions(provider_source)
    if registry is None:
        return None, details
    if registry.stable:
        latest = registry.stable[0]
    elif registry.prerelease:
        latest = registry.prerelease[0]
    else:
        return None, details
    return latest, f"{details}; latest: {latest}"


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


def _normalize_constraint_text(constraint: str) -> str:
    """Normalize whitespace so ``>= 6.0`` and ``>=6.0`` compare equal."""
    return re.sub(r"\s+", "", constraint.strip())


def _latest_compatible_version(registry: RegistryVersions, declared_constraint: str) -> Optional[str]:
    """Return the newest stable version satisfying the declared constraint."""
    candidates = list(registry.stable)
    # Only consider pre-releases when the constraint explicitly asks for one.
    if "-" in declared_constraint:
        candidates.extend(registry.prerelease)
    compatible = [version for version in candidates if version_satisfies_constraint(version, declared_constraint)]
    sorted_compatible = sort_versions(compatible)
    return sorted_compatible[0] if sorted_compatible else None


def check_terraform_providers(
    tf_file: Path,
    lock_file: Optional[Path] = None,
    version_fetcher: Optional[Callable[[str], tuple[Optional[RegistryVersions], str]]] = None,
    source_display: Optional[str] = None,
) -> list[Dependency]:
    """Resolve declared constraints, locked versions and registry versions.

    Resolution rules:
    - Lock entry missing -> ``LOCK_MISSING`` (warning, no false update claim).
    - Locked version violates the declared constraint -> ``CONSTRAINT_UNSATISFIED``.
    - Registry error -> ``LOOKUP_ERROR`` (or preserves a lock violation).
    - Registry latest older than the lock -> ``REGISTRY_INCOMPLETE`` (no update).
    - Lock constraints differ from the declared constraint -> ``LOCK_CONSTRAINT_DRIFT``
      (warning; update recommendation suppressed until reconciled).
    - Newer compatible version available -> ``UPDATE_AVAILABLE``.
    - Otherwise -> ``CURRENT``.
    """
    deps = parse_terraform_providers(tf_file)
    locked = parse_terraform_lock(lock_file) if lock_file else {}
    fetcher = version_fetcher or fetch_terraform_provider_versions

    for dep in deps:
        if dep.type != "terraform_provider":
            continue
        if source_display:
            dep.source = source_display

        details = [dep.details] if dep.details else []
        provider_source = dep.current_reference or ""
        locked_entry = locked.get(_normalize_provider_source(provider_source))
        dep.locked_version = locked_entry.version if locked_entry else None
        dep.locked_constraints = locked_entry.constraints if locked_entry else None

        details.append(f"declared constraint: {dep.current_version}")
        details.append(f"locked version: {dep.locked_version or 'missing'}")
        if dep.locked_constraints:
            details.append(f"lock constraints: {dep.locked_constraints}")
        constraint_drift = bool(
            dep.locked_constraints
            and _normalize_constraint_text(dep.locked_constraints) != _normalize_constraint_text(dep.current_version)
        )
        if constraint_drift:
            details.append("lock constraints differ from declared constraint")

        try:
            parse_version_constraints(dep.current_version)
        except ValueError as exc:
            dep.status = "ERROR"
            details.append(f"invalid declared constraint: {exc}")
            dep.details = "; ".join(details)
            continue

        if dep.locked_version:
            try:
                Version.parse(dep.locked_version)
            except ValueError:
                dep.status = "ERROR"
                details.append(f"invalid locked version: {dep.locked_version!r}")
                dep.details = "; ".join(details)
                continue

        registry, fetch_details = fetcher(provider_source)
        details.append(fetch_details)
        if registry is None:
            if dep.locked_version and not version_satisfies_constraint(dep.locked_version, dep.current_version):
                dep.status = "CONSTRAINT_UNSATISFIED"
                details.append("locked version does not satisfy declared constraint")
            else:
                dep.status = "LOOKUP_ERROR"
            dep.details = "; ".join(details)
            continue

        dep.latest_available = (
            registry.stable[0] if registry.stable
            else (registry.prerelease[0] if registry.prerelease else None)
        )
        dep.latest_compatible = _latest_compatible_version(registry, dep.current_version)
        dep.available_version = dep.latest_compatible or dep.latest_available
        details.append(f"latest available: {dep.latest_available or 'none'}")
        details.append(f"latest compatible: {dep.latest_compatible or 'none'}")

        if not dep.locked_version:
            dep.status = "LOCK_MISSING"
            details.append("no .terraform.lock.hcl entry for this provider")
            dep.details = "; ".join(details)
            continue

        if not version_satisfies_constraint(dep.locked_version, dep.current_version):
            dep.status = "CONSTRAINT_UNSATISFIED"
            details.append("locked version does not satisfy declared constraint")
            dep.details = "; ".join(details)
            continue

        if dep.latest_available is None:
            dep.status = "REGISTRY_INCOMPLETE"
            details.append("registry returned no usable versions")
            dep.details = "; ".join(details)
            continue

        if compare_versions(dep.latest_available, dep.locked_version) < 0:
            dep.status = "REGISTRY_INCOMPLETE"
            details.append("registry latest is older than locked version; no update recommendation")
            dep.details = "; ".join(details)
            continue

        if constraint_drift:
            dep.status = "LOCK_CONSTRAINT_DRIFT"
            details.append("update recommendation suppressed until lock constraints are reconciled")
            dep.details = "; ".join(details)
            continue

        if dep.latest_compatible and compare_versions(dep.latest_compatible, dep.locked_version) > 0:
            dep.status = "UPDATE_AVAILABLE"
            details.append(f"update available: {dep.locked_version} -> {dep.latest_compatible}")
        else:
            dep.status = "CURRENT"
            if dep.latest_available and compare_versions(dep.latest_available, dep.locked_version) > 0:
                details.append("newer registry version is outside the declared constraint")
            else:
                details.append("locked version is current within declared constraint")
        dep.details = "; ".join(details)

    return deps


def detect_all_changes(
    repo_root: Optional[Path] = None,
    version_fetcher: Optional[Callable[[str], tuple[Optional[RegistryVersions], str]]] = None,
) -> DetectionResult:
    """Run all dependency checks and return consolidated result.

    ``repo_root`` removes the former dependency on the caller's working
    directory.  ``version_fetcher`` enables deterministic offline tests.
    """
    root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]
    run = run_id()
    timestamp = datetime.now(timezone.utc).isoformat() + "Z"
    all_deps = []

    tf_file = root / "terraform/main.tf"
    lock_file = root / "terraform/.terraform.lock.hcl"
    if tf_file.exists():
        try:
            source_display = tf_file.relative_to(root).as_posix()
        except ValueError:
            source_display = str(tf_file)
        all_deps.extend(check_terraform_providers(
            tf_file,
            lock_file=lock_file,
            version_fetcher=version_fetcher,
            source_display=source_display,
        ))

    # TODO: Add GitHub Actions workflow detection
    # TODO: Add Python package detection (if requirements.txt/pyproject.toml added)
    # TODO: Add npm package detection (if package.json added)
    # TODO: Add git submodule detection

    errors = [d for d in all_deps if d.status in ("ERROR", "LOOKUP_ERROR")]
    constraint_unsatisfied = [d for d in all_deps if d.status == "CONSTRAINT_UNSATISFIED"]
    updates = [d for d in all_deps if d.status == "UPDATE_AVAILABLE"]
    warnings = [d for d in all_deps if d.status in ("LOCK_MISSING", "REGISTRY_INCOMPLETE", "LOCK_CONSTRAINT_DRIFT")]

    if errors:
        status = "DEPENDENCY_CHECK_ERROR"
        summary = f"{len(errors)} dependency check(s) failed"
    elif constraint_unsatisfied:
        status = "DEPENDENCY_CHANGE_DETECTED"
        summary = f"{len(constraint_unsatisfied)} locked version(s) violate the declared constraint"
    elif updates:
        status = "DEPENDENCY_CHANGE_DETECTED"
        summary = f"{len(updates)} compatible dependency update(s) available"
    elif warnings:
        status = "DEPENDENCY_CHANGE_DETECTED"
        summary = f"{len(warnings)} dependency warning(s) require review"
    else:
        status = "DEPENDENCIES_CURRENT"
        summary = "All dependencies are current"

    return DetectionResult(
        status=status,
        dependencies=all_deps,
        run_id=run,
        timestamp=timestamp,
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