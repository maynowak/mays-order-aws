"""
H3-1: Workspace Integrity - Path Validation and Confinement

Provides path validation and confinement to ensure installer operations
stay within the configured workspace boundaries.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class WorkspaceError(Exception):
    """Exception raised for workspace integrity violations."""
    pass


class WorkspaceIntegrity:
    """
    Validates and enforces workspace boundaries for installer operations.
    
    Ensures all filesystem operations remain within the configured workspace
    and prevents path traversal attacks.
    """
    
    def __init__(self, workspace_root: Path, terraform_dir: str = "terraform"):
        """
        Initialize workspace integrity checker.
        
        Args:
            workspace_root: Root directory for installer workspace (e.g., .mays-installer)
            terraform_dir: Terraform working directory name (relative to project root)
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.project_root = Path.cwd().resolve()
        self.terraform_dir = (self.project_root / terraform_dir).resolve()
        
        # Ensure workspace root exists
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
        # Define allowed paths within workspace
        self._allowed_paths = {
            "workspace_root": self.workspace_root,
            "runs": self.workspace_root / "runs",
            "terraform": self.terraform_dir,
        }
    
    def validate_path(self, path: Path, operation: str = "access") -> Path:
        """
        Validate that a path is within allowed workspace boundaries.
        
        Args:
            path: Path to validate
            operation: Description of operation (for error messages)
            
        Returns:
            Resolved absolute path if valid
            
        Raises:
            WorkspaceError: If path is outside workspace boundaries
        """
        if not isinstance(path, Path):
            path = Path(path)
        
        # Resolve to absolute path
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as e:
            raise WorkspaceError(f"Cannot resolve path for {operation}: {e}")
        
        # Check if path is within workspace root or terraform directory
        allowed = False
        for name, allowed_path in self._allowed_paths.items():
            try:
                if resolved.is_relative_to(allowed_path.resolve()):
                    return resolved
            except (ValueError, RuntimeError):
                continue
        
        # If we get here, path is outside allowed boundaries
        raise WorkspaceError(
            f"Path traversal detected for {operation}: {resolved} "
            f"is outside workspace boundaries. "
            f"Allowed: workspace root ({self.workspace_root}), "
            f"terraform dir ({self.terraform_dir})"
        )
    
    def validate_relative_path(self, relative_path: str, base: Optional[Path] = None) -> Path:
        """
        Validate a relative path stays within workspace boundaries.
        
        Args:
            relative_path: Relative path string
            base: Base directory (defaults to project root)
            
        Returns:
            Resolved absolute path if valid
            
        Raises:
            WorkspaceError: If path traverses outside workspace
        """
        base_path = (base or self.project_root).resolve()
        target = (base / relative_path).resolve()
        return self.validate_path(target, "relative path access")
    
    def ensure_within_workspace(self, path: Path, description: str = "file") -> Path:
        """
        Ensure a path is within workspace, raising detailed error if not.
        
        Args:
            path: Path to check
            description: Description of what the path represents
            
        Returns:
            Validated absolute path
        """
        return self.validate_path(path, f"{description} access")
    
    def get_safe_path(self, relative_path: str, base: Optional[Path] = None) -> Path:
        """
        Get a safe absolute path for a relative path within workspace.
        
        Args:
            relative_path: Relative path from workspace root or project root
            base: Base directory (defaults to project root)
            
        Returns:
            Safe absolute path within workspace
        """
        return self.validate_relative_path(relative_path)
    
    def get_allowed_paths(self) -> dict[str, Path]:
        """Return dictionary of allowed path names and their resolved paths."""
        return {name: path.resolve() for name, path in self._allowed_paths.items()}
    
    def is_within_workspace(self, path: Path) -> bool:
        """Check if a path is within workspace boundaries without raising."""
        try:
            self.validate_path(path)
            return True
        except WorkspaceError:
            return False


def validate_workspace_path(path: Path, workspace_root: Path, description: str = "path") -> Path:
    """
    Convenience function to validate a path against workspace root.
    
    Args:
        path: Path to validate
        workspace_root: Workspace root directory
        description: Description for error messages
        
    Returns:
        Validated absolute path
        
    Raises:
        WorkspaceError: If path is outside workspace
    """
    integrity = WorkspaceIntegrity(Path(path).parent if path.is_file() else Path(path))
    return integrity.validate_path(Path(path), description)


def create_workspace_integrity(workspace_root: Optional[Path] = None, 
                                terraform_dir: str = "terraform") -> "WorkspaceIntegrity":
    """
    Factory function to create WorkspaceIntegrity with sensible defaults.
    
    Args:
        workspace_root: Workspace root (defaults to .mays-installer in cwd)
        terraform_dir: Terraform directory name
        
    Returns:
        Configured WorkspaceIntegrity instance
    """
    if workspace_root is None:
        workspace_root = Path.cwd() / ".mays-installer"
    return WorkspaceIntegrity(Path(workspace_root), terraform_dir)


from typing import Optional