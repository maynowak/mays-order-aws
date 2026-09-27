"""
Remote State Lifecycle Detection.

Detects current state of Terraform remote state infrastructure and project migration status.

Principles:
- Detection only, no automatic migration
- Native Terraform remains independent
- Project_name → Workspace semantics preserved
- No hard-coded AWS profiles
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class RemoteStateStatus:
    """Current remote state lifecycle status."""
    remote_infrastructure_exists: bool = False
    remote_backend_configured: bool = False
    local_state_exists: bool = False
    project_migrated: bool = False
    migration_required: bool = False
    mode: str = "LOCAL"  # LOCAL, REMOTE_READY, REMOTE_MIGRATED, MIGRATION_REQUIRED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "remote_infrastructure_exists": self.remote_infrastructure_exists,
            "remote_backend_configured": self.remote_backend_configured,
            "local_state_exists": self.local_state_exists,
            "project_migrated": self.project_migrated,
            "migration_required": self.migration_required,
            "mode": self.mode,
        }


class RemoteStateLifecycleDetector:
    """
    Detects remote state lifecycle status for a project.
    
    No side effects, detection only.
    """
    
    def __init__(self, terraform_dir: str = "terraform", project_name: str = "mays-orders"):
        self.terraform_dir = Path(terraform_dir).resolve()
        self.project_name = project_name
        self.workspace = project_name  # project_name → workspace
    
    def detect(self) -> RemoteStateStatus:
        """Detect current remote state lifecycle status."""
        status = RemoteStateStatus()
        
        # Check remote infrastructure
        status.remote_infrastructure_exists = self._remote_infrastructure_exists()
        
        # Check remote backend configured
        status.remote_backend_configured = self._remote_backend_configured()
        
        # Check local state exists
        status.local_state_exists = self._local_state_exists()
        
        # Determine migration status
        status.project_migrated = status.remote_backend_configured and self._project_has_remote_state()
        
        # Determine mode
        if not status.remote_infrastructure_exists:
            status.mode = "LOCAL"
        elif status.remote_backend_configured:
            if status.project_migrated:
                status.mode = "REMOTE_MIGRATED"
            else:
                status.mode = "REMOTE_READY"
        else:
            # Infrastructure exists but backend not configured for project
            if status.local_state_exists:
                status.migration_required = True
                status.mode = "MIGRATION_REQUIRED"
            else:
                status.mode = "REMOTE_READY"
        
        return status
    
    def _remote_infrastructure_exists(self) -> bool:
        """Check if remote state infrastructure exists."""
        bootstrap_state = self.terraform_dir.parent / "terraform" / "bootstrap" / "terraform.tfstate"
        # Also check common locations
        bootstrap_dirs = [
            self.terraform_dir.parent / "terraform" / "bootstrap",
            Path.cwd() / "terraform" / "bootstrap",
        ]
        
        for base in bootstrap_dirs:
            state_file = base / "terraform.tfstate"
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        state = json.load(f)
                    resources = state.get("resources", [])
                    # Check for S3 bucket and DynamoDB table resources
                    has_s3 = any(r.get("type") == "aws_s3_bucket" for r in resources)
                    has_ddb = any(r.get("type") == "aws_dynamodb_table" for r in resources)
                    if has_s3 and has_ddb:
                        return True
                except Exception:
                    continue
        return False
    
    def _remote_backend_configured(self) -> bool:
        """Check if remote backend is configured for Terraform."""
        # Check for backend.tf
        backend_files = [
            self.terraform_dir / "backend.tf",
            Path.cwd() / "terraform" / "backend.tf",
        ]
        
        for backend_file in backend_files:
            if backend_file.exists():
                try:
                    content = backend_file.read_text()
                    if 'backend "s3"' in content:
                        return True
                except Exception:
                    continue
        
        # Check for backend configuration in main.tf or variables
        # Simple heuristic: look for backend block
        for tf_file in self.terraform_dir.glob("*.tf"):
            try:
                content = tf_file.read_text()
                if 'backend "s3"' in content:
                    return True
            except Exception:
                continue
        
        return False
    
    def _local_state_exists(self) -> bool:
        """Check if local state exists for project."""
        # Default state
        default_state = self.terraform_dir / "terraform.tfstate"
        if default_state.exists():
            # Check if state is empty or has resources
            try:
                with open(default_state, "r") as f:
                    state = json.load(f)
                if state.get("resources"):
                    return True
            except Exception:
                pass
        
        # Workspace specific state
        workspace_state = self.terraform_dir / "terraform.tfstate.d" / self.workspace / "terraform.tfstate"
        if workspace_state.exists():
            try:
                with open(workspace_state, "r") as f:
                    state = json.load(f)
                if state.get("resources"):
                    return True
            except Exception:
                pass
        
        # If file exists at all, consider it exists
        return default_state.exists() or workspace_state.exists()
    
    def _project_has_remote_state(self) -> bool:
        """
        Check if project has remote state.
        
        This is a heuristic: if backend is configured and local state is empty,
        assume migrated. More robust check would require Terraform CLI.
        """
        # Simple heuristic for now
        # In real implementation, would check terraform workspace list and backend
        return False


def get_remote_state_status(terraform_dir: str = "terraform", project_name: str = "mays-orders") -> RemoteStateStatus:
    """Convenience function to get remote state status."""
    detector = RemoteStateLifecycleDetector(terraform_dir, project_name)
    return detector.detect()
