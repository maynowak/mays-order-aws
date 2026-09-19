"""
H2: Deployment Identity, Versioning & Plan Isolation.

Canonical deployment identity and versioned development state for the installer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List
from collections import defaultdict


class DevelopmentStatus(Enum):
    """Development status of a deployment."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class PlanOperation(Enum):
    """Type of plan operation."""
    DEPLOY = "deploy"
    DESTROY = "destroy"


class VersionComparison(Enum):
    """Result of version comparison."""
    SAME = "same"
    DEVELOPMENT_UPDATE = "development_update"
    PATCH_UPDATE = "patch_update"
    MINOR_UPGRADE = "minor_upgrade"
    MAJOR_UPGRADE = "major_upgrade"
    MIGRATION_REQUIRED = "migration_required"
    INCOMPATIBLE = "incompatible"


class OwnershipStatus(Enum):
    """Ownership status of existing resources."""
    OWNED = "owned"
    FOREIGN = "foreign"
    AMBIGUOUS = "ambiguous"
    UNMANAGED = "unmanaged"


@dataclass
class SemanticVersion:
    """Semantic version (major.minor.patch)."""
    major: int
    minor: int
    patch: int
    
    def __post_init__(self):
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version components must be non-negative")
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __lt__(self, other: "SemanticVersion") -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __le__(self, other: "SemanticVersion") -> bool:
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))
    
    @classmethod
    def parse(cls, version_str: str) -> "SemanticVersion":
        """Parse semantic version from string (e.g., '1.2.3')."""
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str.strip())
        if not match:
            raise ValueError(f"Invalid semantic version format: {version_str}")
        major, minor, patch = map(int, match.groups())
        return cls(major=major, minor=minor, patch=patch)
    
    def to_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)


@dataclass
class DevelopmentPhase:
    """Development phase identifier (e.g., H1, H2, D8)."""
    phase: str  # e.g., "H1", "H2", "D8"
    step: int = 0
    
    def __post_init__(self):
        if not self.phase:
            raise ValueError("Phase cannot be empty")
        if self.step < 0:
            raise ValueError("Step must be non-negative")
    
    def __str__(self) -> str:
        if self.step > 0:
            return f"{self.phase}{self.step}"
        return self.phase
    
    @classmethod
    def parse(cls, phase_str: str) -> "DevelopmentPhase":
        """Parse development phase from string (e.g., 'H2' or 'H217')."""
        match = re.match(r"^([A-Za-z]\d+)(\d*)$", phase_str.strip())
        if not match:
            raise ValueError(f"Invalid development phase format: {phase_str}")
        phase = match.group(1)
        step_str = match.group(2)
        step = int(step_str) if step_str else 0
        return cls(phase=phase, step=step)


@dataclass
class DevelopmentState:
    """Development state metadata."""
    version: SemanticVersion
    phase: DevelopmentPhase
    status: DevelopmentStatus = DevelopmentStatus.DEVELOPMENT
    
    def __post_init__(self):
        if self.version is None:
            raise ValueError("Version is required")
        if self.phase is None:
            raise ValueError("Development phase is required")
    
    def __str__(self) -> str:
        return f"v{self.version}-{self.phase}-{self.status.value}"
    
    def compare(self, other: "DevelopmentState") -> VersionComparison:
        """Compare this development state with another."""
        if self.version == other.version and self.phase == other.phase:
            return VersionComparison.SAME
        
        if self.version.major != other.version.major:
            return VersionComparison.INCOMPATIBLE
        
        if self.version.minor != other.version.minor:
            return VersionComparison.MINOR_UPGRADE if self > other else VersionComparison.MIGRATION_REQUIRED
        
        if self.version.patch != other.version.patch:
            return VersionComparison.PATCH_UPDATE if self > other else VersionComparison.MIGRATION_REQUIRED
        
        if self.phase.step != other.phase.step:
            return VersionComparison.DEVELOPMENT_UPDATE if self > other else VersionComparison.MIGRATION_REQUIRED
        
        return VersionComparison.INCOMPATIBLE
    
    def __gt__(self, other: "DevelopmentState") -> bool:
        if self.version != other.version:
            return self.version > other.version
        return self.phase.step > other.phase.step


@dataclass
class DeploymentId:
    """
    Canonical deployment identity.
    
    Format: <account>:<project>:<environment>
    Example: 240571105849:mays-orders:development
    
    This identifies a deployment uniquely within an AWS account.
    Version is NOT part of deployment identity - it's an upgrade of the same deployment.
    """
    account_id: str
    project: str
    environment: str
    
    def __post_init__(self):
        if not self.account_id or not self.account_id.isdigit():
            raise ValueError("Account ID must be a valid AWS account ID (12 digits)")
        if len(self.account_id) != 12:
            raise ValueError("Account ID must be exactly 12 digits")
        if not self.project:
            raise ValueError("Project name cannot be empty")
        if not self.environment:
            raise ValueError("Environment cannot be empty")
    
    def __str__(self) -> str:
        return f"{self.account_id}:{self.project}:{self.environment}"
    
    @classmethod
    def parse(cls, deployment_id_str: str) -> "DeploymentId":
        """Parse deployment ID from string."""
        parts = deployment_id_str.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid deployment ID format: {deployment_id_str}. Expected: account:project:environment")
        return cls(account_id=parts[0], project=parts[1], environment=parts[2])
    
    def matches_context(self, account_id: str, project: str, environment: str) -> bool:
        """Check if this deployment ID matches the given context."""
        return (self.account_id == account_id and 
                self.project == project and 
                self.environment.lower() == environment.lower())
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeploymentId):
            return NotImplemented
        return (self.account_id == other.account_id and 
                self.project == other.project and 
                self.environment.lower() == other.environment.lower())
    
    def __hash__(self) -> int:
        return hash((self.account_id, self.project, self.environment.lower()))
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class PlanMetadata:
    """
    Metadata embedded in plan filename and stored alongside plan.
    
    Contains all identity information needed for plan isolation.
    """
    deployment_id: DeploymentId
    version: SemanticVersion
    development_phase: DevelopmentPhase
    operation: PlanOperation
    sequence_number: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    git_commit: Optional[str] = None
    
    def __post_init__(self):
        if self.sequence_number <= 0:
            raise ValueError("Sequence number must be positive")
    
    def to_filename(self) -> str:
        """
        Generate plan filename from metadata.
        
        Format: <project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan
        Example: mays-orders-development-0.3.0-H217-240571105849-deploy-0042.tfplan
        """
        env_safe = self.deployment_id.environment.lower()
        project_safe = self.deployment_id.project.lower()
        version_str = str(self.version)
        phase_str = str(self.development_phase)
        account_str = self.deployment_id.account_id
        op_str = self.operation.value
        seq_str = f"{self.sequence_number:04d}"
        
        return f"{project_safe}-{env_safe}-{version_str}-{phase_str}-{account_str}-{op_str}-{seq_str}.tfplan"
    
    def to_destroy_filename(self) -> str:
        """Generate destroy plan filename."""
        meta = PlanMetadata(
            deployment_id=self.deployment_id,
            version=self.version,
            development_phase=self.development_phase,
            operation=PlanOperation.DESTROY,
            sequence_number=self.sequence_number,
            created_at=datetime.now().isoformat(),
            git_commit=self.git_commit
        )
        return meta.to_filename()
    
    @classmethod
    def parse_filename(cls, filename: str) -> Optional["PlanMetadata"]:
        """
        Parse plan metadata from filename.
        
        Expected format: <project>-<environment>-<version>-<phase>-<account>-<operation>-<sequence>.tfplan
        """
        if not filename.endswith(".tfplan"):
            return None
        
        name = filename[:-7]  # Remove .tfplan
        parts = name.split("-")
        
        if len(parts) < 7:
            return None
        
        try:
            # Last parts: operation, sequence
            operation_str = parts[-2]
            sequence_str = parts[-1]
            operation = PlanOperation(operation_str)
            sequence_number = int(sequence_str)
            
            # Account is before operation
            account_id = parts[-3]
            
            # Phase is before account
            phase_str = parts[-4]
            development_phase = DevelopmentPhase.parse(phase_str)
            
            # Version is before phase
            version_str = parts[-5]
            version = SemanticVersion.parse(version_str)
            
            # Environment is before version
            environment = parts[-6]
            
            # Project is everything before environment (could have hyphens)
            project = "-".join(parts[:-6])
            
            deployment_id = DeploymentId(
                account_id=account_id,
                project=project,
                environment=environment
            )
            
            return cls(
                deployment_id=deployment_id,
                version=version,
                development_phase=development_phase,
                operation=operation,
                sequence_number=sequence_number
            )
        except (ValueError, IndexError):
            return None
    
    def matches_deployment(self, deployment_id: DeploymentId) -> bool:
        return self.deployment_id == deployment_id
    
    def matches_operation(self, operation: PlanOperation) -> bool:
        return self.operation == operation
    
    def to_dict(self) -> dict:
        return {
            "deployment_id": self.deployment_id.to_dict(),
            "version": str(self.version),
            "development_phase": str(self.development_phase),
            "operation": self.operation.value,
            "sequence_number": self.sequence_number,
            "created_at": self.created_at,
            "git_commit": self.git_commit
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "PlanMetadata":
        data = json.loads(json_str)
        return cls(
            deployment_id=DeploymentId(**data["deployment_id"]),
            version=SemanticVersion.parse(data["version"]),
            development_phase=DevelopmentPhase.parse(data["development_phase"]),
            operation=PlanOperation(data["operation"]),
            sequence_number=data["sequence_number"],
            created_at=data["created_at"],
            git_commit=data.get("git_commit")
        )


@dataclass
class PlanIdentity:
    """
    Complete plan identity combining metadata and file reference.
    """
    metadata: PlanMetadata
    file_path: Path
    file_size: int = 0
    
    def __post_init__(self):
        if not self.file_path.exists():
            raise FileNotFoundError(f"Plan file not found: {self.file_path}")
    
    @property
    def filename(self) -> str:
        return self.file_path.name
    
    def matches_deployment(self, deployment_id: DeploymentId) -> bool:
        return self.metadata.matches_deployment(deployment_id)
    
    def matches_operation(self, operation: PlanOperation) -> bool:
        return self.metadata.matches_operation(operation)


@dataclass
class TagSet:
    """Canonical AWS resource tag set for installer-managed resources."""
    
    # Required identity tags (must be present on all managed resources)
    project: str
    environment: str
    deployment_id: str
    
    # Version/development metadata tags
    version: str
    development_phase: str
    development_step: int
    
    # Governance/ownership tags
    managed_by: str = "mays-installer"
    owner: Optional[str] = None
    maker: Optional[str] = None
    
    # System/component tags
    system: Optional[str] = None
    component: Optional[str] = None
    
    # Custom tags (user-defined)
    custom_tags: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.project:
            raise ValueError("Project tag is required")
        if not self.environment:
            raise ValueError("Environment tag is required")
        if not self.deployment_id:
            raise ValueError("DeploymentId tag is required")
        if not self.version:
            raise ValueError("Version tag is required")
        if not self.development_phase:
            raise ValueError("DevelopmentPhase tag is required")
    
    def to_dict(self) -> dict:
        """Convert to AWS tag dictionary."""
        tags = {
            "Project": self.project,
            "Environment": self.environment,
            "DeploymentId": self.deployment_id,
            "Version": self.version,
            "DevelopmentPhase": self.development_phase,
            "DevelopmentStep": str(self.development_step),
            "ManagedBy": self.managed_by,
        }
        
        if self.owner:
            tags["Owner"] = self.owner
        if self.maker:
            tags["Maker"] = self.maker
        if self.system:
            tags["System"] = self.system
        if self.component:
            tags["Component"] = self.component
        
        # Add custom tags (prefix with Custom: to avoid conflicts)
        for key, value in self.custom_tags.items():
            tags[f"Custom:{key}"] = value
        
        return tags
    
    def merge_with_existing(self, existing_tags: dict) -> dict:
        """
        Merge canonical tags with existing tags.
        
        Preserves existing tags that don't conflict with canonical tags.
        Canonical tags take precedence for identity/version metadata.
        """
        result = existing_tags.copy()
        
        # Update with canonical tags (these are authoritative)
        canonical = self.to_dict()
        for key, value in canonical.items():
            result[key] = value
        
        return result
    
    @classmethod
    def from_context(cls, context: "DeploymentContext") -> "TagSet":
        """Create tag set from deployment context."""
        return cls(
            project=context.deployment_id.project,
            environment=context.deployment_id.environment,
            deployment_id=str(context.deployment_id),
            version=str(context.version),
            development_phase=str(context.development_state.phase),
            development_step=context.development_state.phase.step,
            system=context.system_name if hasattr(context, 'system_name') else None,
            component=context.component_name if hasattr(context, 'component_name') else None,
        )


@dataclass
class ResourceOwnership:
    """Ownership analysis result for an existing AWS resource."""
    resource_arn: str
    resource_type: str
    ownership: OwnershipStatus
    deployment_id: Optional[DeploymentId] = None
    version: Optional[SemanticVersion] = None
    development_phase: Optional[DevelopmentPhase] = None
    tags: dict = field(default_factory=dict)
    details: str = ""
    
    def is_destroyable_by(self, deployment_id: DeploymentId) -> bool:
        """Check if resource can be destroyed by the given deployment."""
        return self.ownership == OwnershipStatus.OWNED and self.deployment_id == deployment_id
    
    def to_dict(self) -> dict:
        return {
            "resource_arn": self.resource_arn,
            "resource_type": self.resource_type,
            "ownership": self.ownership.value,
            "deployment_id": str(self.deployment_id) if self.deployment_id else None,
            "version": str(self.version) if self.version else None,
            "development_phase": str(self.development_phase) if self.development_phase else None,
            "tags": self.tags,
            "details": self.details
        }


@dataclass
class DeploymentContext:
    """
    Complete deployment context for the installer.
    
    Separates installer context from target deployment context.
    """
    # Target deployment context (required, no defaults)
    deployment_id: DeploymentId
    version: SemanticVersion
    development_state: DevelopmentState
    
    # Installer context (with defaults)
    installer_name: str = "Mays-Order-AWS-installer"
    installer_version: str = "0.1.0"
    installer_commit: Optional[str] = None
    
    # Optional system/component identification
    system_name: Optional[str] = None
    component_name: Optional[str] = None
    
    # AWS context
    aws_region: str = "eu-central-1"
    aws_profile: str = "mayaws"
    
    # Safety flags
    allow_aws_operations: bool = False
    dry_run: bool = True
    
    # Run configuration
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S"))
    run_dir: Optional[str] = None
    terraform_dir: str = "terraform"
    
    def __post_init__(self):
        if self.run_dir is None:
            self.run_dir = f".mays-installer/runs/{self.run_id}"
    
    def validate_against_aws(self, aws_account_id: str, aws_region: str, aws_profile: str) -> bool:
        """Validate deployment context matches AWS context."""
        return (self.deployment_id.account_id == aws_account_id and
                self.aws_region == aws_region and
                self.aws_profile == aws_profile)
    
    def get_deployment_id_string(self) -> str:
        return str(self.deployment_id)
    
    def get_plan_base_name(self, operation: PlanOperation) -> str:
        """Generate base plan name without sequence number."""
        env_safe = self.deployment_id.environment.lower()
        project_safe = self.deployment_id.project.lower()
        version_str = str(self.version)
        phase_str = str(self.development_state.phase)
        account_str = self.deployment_id.account_id
        op_str = operation.value
        
        return f"{project_safe}-{env_safe}-{version_str}-{phase_str}-{account_str}-{op_str}"
    
    def to_dict(self) -> dict:
        return {
            "installer_name": self.installer_name,
            "installer_version": self.installer_version,
            "installer_commit": self.installer_commit,
            "deployment_id": self.deployment_id.to_dict(),
            "version": str(self.version),
            "development_state": {
                "version": str(self.development_state.version),
                "phase": str(self.development_state.phase),
                "status": self.development_state.status.value
            },
            "system_name": self.system_name,
            "component_name": self.component_name,
            "aws_region": self.aws_region,
            "aws_profile": self.aws_profile,
            "allow_aws_operations": self.allow_aws_operations,
            "dry_run": self.dry_run,
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "terraform_dir": self.terraform_dir
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "DeploymentContext":
        data = json.loads(json_str)
        return cls(
            installer_name=data.get("installer_name", "Mays-Order-AWS-installer"),
            installer_version=data.get("installer_version", "0.1.0"),
            installer_commit=data.get("installer_commit"),
            deployment_id=DeploymentId(**data["deployment_id"]),
            version=SemanticVersion.parse(data["version"]),
            development_state=DevelopmentState(
                version=SemanticVersion.parse(data["development_state"]["version"]),
                phase=DevelopmentPhase.parse(data["development_state"]["phase"]),
                status=DevelopmentStatus(data["development_state"]["status"])
            ),
            system_name=data.get("system_name"),
            component_name=data.get("component_name"),
            aws_region=data.get("aws_region", "eu-central-1"),
            aws_profile=data.get("aws_profile", "mayaws"),
            allow_aws_operations=data.get("allow_aws_operations", False),
            dry_run=data.get("dry_run", True),
            run_id=data.get("run_id", datetime.now().strftime("%Y%m%d-%H%M%S")),
            run_dir=data.get("run_dir"),
            terraform_dir=data.get("terraform_dir", "terraform")
        )


class PlanSequenceManager:
    """Manages sequential plan numbering per deployment."""
    
    def __init__(self, base_dir: Path = Path(".mays-installer/runs")):
        self.base_dir = base_dir
        self._sequence_cache: dict[str, int] = {}
    
    def _get_deployment_key(self, deployment_id: DeploymentId) -> str:
        return str(deployment_id)
    
    def get_next_sequence(self, deployment_id: DeploymentId, operation: PlanOperation) -> int:
        """Get next sequence number for deployment + operation."""
        key = f"{self._get_deployment_key(deployment_id)}:{operation.value}"
        
        if key in self._sequence_cache:
            self._sequence_cache[key] += 1
            return self._sequence_cache[key]
        
        # Scan existing runs for highest sequence number
        max_seq = 0
        if self.base_dir.exists():
            for run_dir in self.base_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                plans_dir = run_dir / "plans"
                if not plans_dir.exists():
                    continue
                for plan_file in plans_dir.iterdir():
                    if not plan_file.suffix == ".tfplan":
                        continue
                    meta = PlanMetadata.parse_filename(plan_file.name)
                    if meta and meta.deployment_id == deployment_id and meta.operation == operation:
                        max_seq = max(max_seq, meta.sequence_number)
        
        self._sequence_cache[key] = max_seq + 1
        return max_seq + 1
    
    def reset_cache(self):
        self._sequence_cache.clear()


class PlanDiscovery:
    """Hardened plan discovery with deployment identity filtering."""
    
    def __init__(self, base_dir: Path = Path(".mays-installer/runs")):
        self.base_dir = base_dir
    
    def find_plans(self, 
                   deployment_id: DeploymentId,
                   operation: PlanOperation,
                   version: Optional[SemanticVersion] = None,
                   development_phase: Optional[DevelopmentPhase] = None) -> List[PlanIdentity]:
        """
        Find plans matching deployment identity and optional filters.
        
        Returns plans sorted by sequence number (newest first).
        """
        plans = []
        
        if not self.base_dir.exists():
            return plans
        
        for run_dir in self.base_dir.iterdir():
            if not run_dir.is_dir():
                continue
            plans_dir = run_dir / "plans"
            if not plans_dir.exists():
                continue
            
            for plan_file in plans_dir.iterdir():
                if not plan_file.suffix == ".tfplan":
                    continue
                
                meta = PlanMetadata.parse_filename(plan_file.name)
                if not meta:
                    continue
                
                # Match deployment identity
                if meta.deployment_id != deployment_id:
                    continue
                
                # Match operation
                if meta.operation != operation:
                    continue
                
                # Match version if specified
                if version and meta.version != version:
                    continue
                
                # Match development phase if specified
                if development_phase and meta.development_phase != development_phase:
                    continue
                
                plans.append(PlanIdentity(metadata=meta, file_path=plan_file))
        
        # Sort by sequence number descending (newest first)
        plans.sort(key=lambda p: p.metadata.sequence_number, reverse=True)
        return plans
    
    def find_latest_plan(self,
                         deployment_id: DeploymentId,
                         operation: PlanOperation,
                         version: Optional[SemanticVersion] = None,
                         development_phase: Optional[DevelopmentPhase] = None) -> Optional[PlanIdentity]:
        """Find the latest matching plan."""
        plans = self.find_plans(deployment_id, operation, version, development_phase)
        return plans[0] if plans else None
    
    def validate_plan_context(self, plan_path: Path, expected_deployment_id: DeploymentId) -> tuple[bool, str]:
        """Validate plan file matches expected deployment context."""
        meta = PlanMetadata.parse_filename(plan_path.name)
        if not meta:
            return False, f"Cannot parse plan metadata from filename: {plan_path.name}"
        
        if meta.deployment_id != expected_deployment_id:
            return False, (f"Plan deployment ID mismatch: expected {expected_deployment_id}, "
                          f"got {meta.deployment_id}")
        
        return True, ""


class OwnershipAnalyzer:
    """Analyzes ownership of existing AWS resources."""
    
    # Tag keys that identify deployment ownership
    DEPLOYMENT_TAGS = ["DeploymentId", "Project", "Environment", "Version", "DevelopmentPhase"]
    
    def __init__(self, current_deployment_id: DeploymentId):
        self.current_deployment_id = current_deployment_id
    
    def analyze_resource(self, resource_arn: str, resource_type: str, tags: dict) -> ResourceOwnership:
        """Analyze ownership of a single resource based on its tags."""
        deployment_id_str = tags.get("DeploymentId")
        project = tags.get("Project")
        environment = tags.get("Environment")
        version_str = tags.get("Version")
        phase_str = tags.get("DevelopmentPhase")
        
        # No deployment tags = unmanaged
        if not deployment_id_str:
            return ResourceOwnership(
                resource_arn=resource_arn,
                resource_type=resource_type,
                ownership=OwnershipStatus.UNMANAGED,
                tags=tags,
                details="Resource has no DeploymentId tag"
            )
        
        try:
            deployment_id = DeploymentId.parse(deployment_id_str)
        except ValueError:
            return ResourceOwnership(
                resource_arn=resource_arn,
                resource_type=resource_type,
                ownership=OwnershipStatus.AMBIGUOUS,
                tags=tags,
                details=f"Invalid DeploymentId tag format: {deployment_id_str}"
            )
        
        # Check if deployment ID matches current
        if deployment_id == self.current_deployment_id:
            return ResourceOwnership(
                resource_arn=resource_arn,
                resource_type=resource_type,
                ownership=OwnershipStatus.OWNED,
                deployment_id=deployment_id,
                version=SemanticVersion.parse(version_str) if version_str else None,
                development_phase=DevelopmentPhase.parse(phase_str) if phase_str else None,
                tags=tags,
                details="Resource belongs to current deployment"
            )
        
        # Different project = foreign
        if project and project != self.current_deployment_id.project:
            return ResourceOwnership(
                resource_arn=resource_arn,
                resource_type=resource_type,
                ownership=OwnershipStatus.FOREIGN,
                deployment_id=deployment_id,
                tags=tags,
                details=f"Resource belongs to different project: {project}"
            )
        
        # Same project, different environment
        if environment and environment != self.current_deployment_id.environment:
            return ResourceOwnership(
                resource_arn=resource_arn,
                resource_type=resource_type,
                ownership=OwnershipStatus.FOREIGN,
                deployment_id=deployment_id,
                tags=tags,
                details=f"Resource belongs to different environment: {environment}"
            )
        
        # Same project, same environment, different account
        if deployment_id.account_id != self.current_deployment_id.account_id:
            return ResourceOwnership(
                resource_arn=resource_arn,
                resource_type=resource_type,
                ownership=OwnershipStatus.FOREIGN,
                deployment_id=deployment_id,
                tags=tags,
                details=f"Resource belongs to different account: {deployment_id.account_id}"
            )
        
        # Same deployment ID but different version/phase = ambiguous
        return ResourceOwnership(
            resource_arn=resource_arn,
            resource_type=resource_type,
            ownership=OwnershipStatus.AMBIGUOUS,
            deployment_id=deployment_id,
            version=SemanticVersion.parse(version_str) if version_str else None,
            development_phase=DevelopmentPhase.parse(phase_str) if phase_str else None,
            tags=tags,
            details=f"Resource has same deployment ID but different version/phase"
        )


# Convenience function to create deployment context from installer context
def create_deployment_context(
    account_id: str,
    project: str,
    environment: str,
    version: str,
    development_phase: str,
    development_step: int = 0,
    development_status: str = "development",
    aws_region: str = "eu-central-1",
    aws_profile: str = "mayaws",
    system_name: Optional[str] = None,
    component_name: Optional[str] = None,
    allow_aws_operations: bool = False,
    dry_run: bool = True,
    terraform_dir: str = "terraform"
) -> DeploymentContext:
    """Factory function to create DeploymentContext from simple parameters."""
    return DeploymentContext(
        deployment_id=DeploymentId(
            account_id=account_id,
            project=project,
            environment=environment
        ),
        version=SemanticVersion.parse(version),
        development_state=DevelopmentState(
            version=SemanticVersion.parse(version),
            phase=DevelopmentPhase.parse(development_phase),
            status=DevelopmentStatus(development_status)
        ),
        system_name=system_name,
        component_name=component_name,
        aws_region=aws_region,
        aws_profile=aws_profile,
        allow_aws_operations=allow_aws_operations,
        dry_run=dry_run
    )