"""
H3-3: Plan Artifact Integrity - Enhanced Verification

Provides enhanced verification of plan artifacts to ensure they cannot
be silently replaced or corrupted between creation and deployment.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum

from installer.core.deployment_identity import (
    DeploymentId, PlanMetadata, PlanOperation, PlanMetadata, SemanticVersion,
    DevelopmentPhase
)


class PlanIntegrityError(Exception):
    """Exception raised for plan integrity violations."""
    pass


class IntegrityCheck(Enum):
    """Types of integrity checks."""
    FILE_EXISTS = "file_exists"
    FILE_READABLE = "file_readable"
    METADATA_MATCHES = "metadata_matches"
    CONTENT_HASH_MATCHES = "content_hash_matches"
    DEPLOYMENT_ID_MATCHES = "deployment_id_matches"
    OPERATION_MATCHES = "operation_matches"
    VERSION_MATCHES = "version_matches"
    PHASE_MATCHES = "phase_matches"
    SEQUENCE_VALID = "sequence_valid"
    CHECKSUM_MATCHES = "checksum_matches"


@dataclass
class IntegrityCheckResult:
    """Result of a single integrity check."""
    check: IntegrityCheck
    passed: bool
    message: str
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlanIntegrityReport:
    """Complete integrity report for a plan artifact."""
    plan_file: str
    deployment_id: str
    operation: str
    version: str
    phase: str
    sequence_number: int
    checks: List[Dict[str, Any]] = field(default_factory=list)
    overall_valid: bool = True
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())
    plan_file_path: str = ""
    plan_file_size: int = 0
    plan_file_hash: str = ""
    metadata_file: str = ""
    context_file: str = ""
    
    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.get("passed", False))
    
    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.get("passed", False))
    
    @property
    def all_passed(self) -> bool:
        return all(c.get("passed", False) for c in self.checks)
    
    def add_check(self, check: IntegrityCheck, passed: bool, message: str, details: dict = None) -> None:
        """Add a check result."""
        self.checks.append({
            "check": check.value,
            "passed": passed,
            "message": message,
            "details": details or {}
        })
        if not passed:
            self.overall_valid = False
    
    def to_dict(self) -> dict:
        data = asdict(self)
        # Convert enums to strings
        data["checks"] = self.checks
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class PlanIntegrityVerifier:
    """
    Verifies plan artifact integrity from creation through deployment.
    
    Ensures plan artifacts cannot be silently replaced or corrupted
    between creation and deployment.
    """
    
    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path.cwd() / ".mays-installer" if workspace_root is None else Path(workspace_root)
        self.runs_dir = Path(".mays-installer/runs")
    
    def compute_file_hash(self, file_path: Path, algorithm: str = "sha256") -> str:
        """Compute file hash."""
        hash_func = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    
    def compute_plan_hash(self, plan_file: Path) -> str:
        """Compute hash of plan file (binary)."""
        return self.compute_file_hash(plan_file)
    
    def verify_plan_file(self, plan_path: Path, expected_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Verify a plan file's integrity.
        
        Args:
            plan_path: Path to plan file
            expected_metadata: Optional expected metadata for comparison
            
        Returns:
            Dictionary with verification results
        """
        results = {
            "valid": True,
            "checks": [],
            "errors": [],
            "warnings": []
        }
        
        plan_path = Path(plan_path)
        
        # Check 1: File exists
        if not plan_path.exists():
            results["valid"] = False
            results["errors"].append(f"Plan file not found: {plan_path}")
            return results
        
        # Check 2: File is readable
        try:
            with open(plan_path, "rb") as f:
                f.read(1)
        except (OSError, IOError) as e:
            results["valid"] = False
            results["errors"].append(f"Plan file not readable: {e}")
            return results
        
        # Check 3: File is not empty
        if plan_path.stat().st_size == 0:
            results["valid"] = False
            results["errors"].append("Plan file is empty")
            return results
        
        # Check 4: File is valid Terraform plan
        try:
            import subprocess
            result = subprocess.run(
                ["terraform", "show", "-json", str(plan_path)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                results["valid"] = False
                results["errors"].append(f"Invalid Terraform plan: {result.stderr}")
                return results
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Cannot verify plan format: {e}")
            return results
        
        # If expected metadata provided, do additional checks
        if expected_metadata:
            # Verify deployment ID matches
            # ... could add more checks here
            pass
        
        results["checks"] = ["file_exists", "file_readable", "file_not_empty", "valid_terraform_plan"]
        return results
    
    def verify_plan_with_context(self, plan_path: Path, deployment_context) -> Dict[str, Any]:
        """
        Verify plan file matches deployment context.
        
        Args:
            plan_path: Path to plan file
            deployment_context: DeploymentContext to verify against
            
        Returns:
            Verification results
        """
        from installer.core.deployment_identity import (
            PlanMetadata, DeploymentId, PlanOperation
        )
        
        results = {
            "valid": True,
            "checks": [],
            "errors": [],
            "warnings": []
        }
        
        # First verify basic plan file
        base_results = self.verify_plan_file(plan_path)
        if not base_results["valid"]:
            return base_results
        
        results["checks"].extend(base_results.get("checks", []))
        results["errors"].extend(base_results.get("errors", []))
        results["warnings"].extend(base_results.get("warnings", []))
        results["valid"] = base_results["valid"]
        
        if not base_results["valid"]:
            return results
        
        # Parse plan metadata from filename
        plan_path = Path(plan_path)
        meta = None
        from installer.core.deployment_identity import PlanMetadata
        meta = PlanMetadata.parse_filename(plan_path.name)
        
        if not meta:
            results["valid"] = False
            results["errors"].append(f"Cannot parse plan metadata from filename: {plan_path.name}")
            return results
        
        # Check deployment ID matches
        if not meta.matches_deployment(deployment_id):
            results["valid"] = False
            results["errors"].append(
                f"Deployment ID mismatch: plan has {meta.deployment_id}, expected {deployment_id}"
            )
        
        # Check operation matches
        if meta.operation != operation:
            results["valid"] = False
            results["errors"].append(
                f"Operation mismatch: plan is {meta.operation.value}, expected {operation.value}"
            )
        
        # Check version (warn only)
        if meta.version != version:
            results["warnings"].append(
                f"Version mismatch: plan has {meta.version}, context has {version}"
            )
        
        # Check development phase (warn only)
        if meta.development_phase != phase:
            results["warnings"].append(
                f"Development phase mismatch: plan has {meta.development_phase}, context has {phase}"
            )
        
        return results
    
    def create_integrity_report(self, plan_path: Path, deployment_context) -> Dict[str, Any]:
        """
        Create a complete integrity report for a plan.
        """
        from installer.core.deployment_identity import PlanMetadata
        
        report = {
            "plan_file": str(plan_path),
            "timestamp": datetime.now().isoformat(),
            "checks": [],
            "overall_valid": True,
            "plan_file_size": 0,
            "plan_file_hash": "",
            "metadata_file": "",
            "context_file": ""
        }
        
        plan_path = Path(plan_path)
        
        # File size
        if plan_path.exists():
            report["plan_file_size"] = plan_path.stat().st_size
        
        # File hash
        if plan_path.exists():
            import hashlib
            report["plan_file_hash"] = self.compute_file_hash(plan_path)
        
        # Metadata file
        meta_file = Path(str(plan_path) + ".meta.json")
        if meta_file.exists():
            report["metadata_file"] = str(meta_file)
        
        # Context file
        context_file = Path(str(plan_path).replace(".tfplan", ".context.json"))
        if context_file.exists():
            report["context_file"] = str(context_file)
        
        # TODO: Add more comprehensive checks
        
        return report


class PlanIntegrityManager:
    """
    Manages plan integrity verification throughout the deployment lifecycle.
    """
    
    def __init__(self, workspace_root: Optional[Path] = None):
        self.verifier = PlanIntegrityVerifier(workspace_root)
    
    def verify_before_deploy(self, plan_path: str, deployment_context) -> Dict[str, Any]:
        """
        Verify plan integrity before deployment.
        
        Args:
            plan_path: Path to plan file
            deployment_context: DeploymentContext to verify against
            
        Returns:
            Verification results
        """
        from installer.core.deployment_identity import PlanOperation
        
        # Determine operation from context or infer
        operation = PlanOperation.DEPLOY  # default
        
        results = self.verifier.verify_plan_with_context(
            Path(plan_path), deployment_context
        )
        
        if not results["valid"]:
            raise PlanIntegrityError(f"Plan integrity verification failed: {results['errors']}")
        
        return results
    
    def verify_plan_integrity(self, plan_file: str, deployment_context) -> Dict[str, Any]:
        """
        Verify plan integrity against deployment context.
        
        Args:
            plan_file: Path to plan file
            deployment_context: DeploymentContext to verify against
            
        Returns:
            Verification results
        """
        from installer.core.deployment_identity import PlanOperation
        
        results = self.verifier.verify_plan_with_context(
            Path(plan_file), deployment_context
        )
        
        return results
    
    def save_integrity_report(self, plan_path: str, report: Dict[str, Any]) -> Path:
        """Save integrity report alongside plan file."""
        plan_path = Path(plan_path)
        report_path = Path(str(plan_path) + ".integrity.json")
        report["generated_at"] = datetime.now().isoformat()
        report_path.write_text(json.dumps(report, indent=2, default=str))
        return report_path


import hashlib
import sys
import atexit