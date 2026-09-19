"""
Run Directory Management.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from installer.core.context import InstallationContext, ValidationResult


class RunDirectoryManager:
    """
    Manages run directories for installer executions.
    
    Each run gets a unique directory with all artifacts.
    """
    
    def __init__(self, base_dir: str = ".mays-installer/runs"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def create_run_dir(self, run_id: str) -> Path:
        """Create a new run directory."""
        run_dir = Path(".mays-installer") / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (run_dir / "logs").mkdir(exist_ok=True)
        (run_dir / "plans").mkdir(exist_ok=True)
        (run_dir / "artifacts").mkdir(exist_ok=True)
        
        return Path(".mays-installer/runs") / run_id
    
    def save_context(self, run_dir: Path, context) -> Path:
        """Save InstallationContext to run directory."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        context_file = run_dir / "context.json"
        context_file.write_text(context.to_json())
        return context_file
    
    def save_validation(self, run_dir: Path, validation_result) -> Path:
        """Save validation result."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        validation_file = run_dir / "validation.json"
        validation_file.write_text(validation_result.to_json())
        return validation_file
    
    def save_plan(self, run_dir: Path, plan_file: str, plan_result, mode: str = "deploy") -> Path:
        """Save plan file and analysis."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        plan_dir = Path("plans")
        plan_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy plan file
        import shutil
        dest_plan = run_dir / "plans" / f"{mode}.tfplan"
        shutil.copy2(plan_file, dest_plan)
        
        # Save plan analysis as JSON
        from installer.terraform.runner import PlanResult
        
        if hasattr(plan_result, 'to_json'):
            plan_json = plan_result.to_json()
        else:
            import json
            plan_json = json.dumps(plan_result, indent=2, default=str)
        
        plan_json_file = run_dir / "plans" / f"{mode}-plan.json"
        plan_json_file.write_text(plan_json)
        
        return dest_plan
    
    def save_validation_result(self, run_dir: Path, validation_result) -> Path:
        """Save validation result."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        validation_file = run_dir / "validation.json"
        validation_file.write_text(validation_result.to_json())
        return validation_file
    
    def save_plan_analysis(self, run_dir: Path, plan_file: str, plan_result, mode: str = "deploy") -> Path:
        """Save plan analysis as JSON."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        import json
        from installer.terraform.runner import PlanResult
        
        if hasattr(plan_result, 'to_json'):
            plan_json = plan_result.to_json()
        else:
            import json
            plan_json = json.dumps(plan_result, indent=2, default=str)
        
        plan_json_file = run_dir / "plans" / f"{mode}-plan.json"
        plan_json_file.write_text(plan_json)
        
        return plan_json_file
    
    def save_plan_file(self, run_dir: Path, plan_file: str, mode: str = "deploy") -> Path:
        """Copy plan file to run directory."""
        import shutil
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        dest = run_dir / "plans" / f"{mode}.tfplan"
        shutil.copy2(plan_file, dest)
        return dest
    
    def save_execution_log(self, run_dir: Path, log_content: str) -> Path:
        """Save execution log."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = run_dir / "execution.log"
        log_file.write_text(log_content)
        return log_file
    
    def save_report(self, run_dir: Path, report_content: str, name: str = "report") -> Path:
        """Save a report file."""
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = run_dir / f"{name}.md"
        report_file.write_text(report_content)
        return report_file
    
    def list_runs(self) -> List[Path]:
        """List all run directories."""
        if not self.base_dir.exists():
            return []
        
        runs = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and item.name != "__pycache__":
                runs.append(item)
        return sorted(runs, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def get_run_dir(self, run_id: str) -> Optional[Path]:
        """Get run directory by ID."""
        run_dir = self.base_dir / run_id
        if run_dir.exists():
            return run_dir
        return None
    
    def cleanup_old_runs(self, keep_last: int = 10) -> int:
        """Clean up old run directories, keeping only the most recent."""
        runs = self.list_runs()
        if len(runs) <= keep_last:
            return 0
        
        removed = 0
        for run in runs[10:]:
            import shutil
            shutil.rmtree(run)
            removed += 1
        return removed


class PlanArtifactManager:
    """
    Manages Terraform plan artifacts securely.
    
    Plan files can contain sensitive information.
    """
    
    @staticmethod
    def sanitize_plan_json(plan_json: dict) -> dict:
        """
        Sanitize plan JSON by removing sensitive values.
        
        Removes sensitive values from resource attributes.
        """
        import copy
        sanitized = copy.deepcopy(plan_json)
        
        # Remove sensitive values from resource changes
        if "resource_changes" in sanitized:
            for change in sanitized.get("resource_changes", []):
                change_data = change.get("change", {})
                after = change_data.get("after", {})
                if isinstance(after, dict):
                    # Remove sensitive keys
                    sensitive_keys = ["password", "secret", "key", "token", "credential"]
                    for key in list(after.keys()):
                        if any(sensitive in key.lower() for sensitive in sensitive_keys):
                            after[key] = "***REDACTED***"
                
                before = change_data.get("before", {})
                if isinstance(before, dict):
                    sensitive_keys = ["password", "secret", "key", "token", "credential"]
                    for key in list(before.keys()):
                        if any(sensitive in key.lower() for sensitive in sensitive_keys):
                            before[key] = "***REDACTED***"
        
        return sanitized
    
    @staticmethod
    def save_plan_safely(plan_file: str, output_path: Path, sanitize: bool = False) -> Path:
        """Save plan file, optionally sanitized.
        
        Terraform plan files are binary. To sanitize, we must first convert to JSON
        using `terraform show -json`, which requires provider plugins to be installed.
        """
        import shutil
        import json
        import subprocess
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if sanitize:
            # Convert binary plan to JSON using terraform show -json
            try:
                result = subprocess.run(
                    ["terraform", "show", "-json", plan_file],
                    capture_output=True, text=True, timeout=60,
                    cwd=os.path.dirname(plan_file) if os.path.dirname(plan_file) else None
                )
                if result.returncode != 0:
                    # If terraform show fails, fall back to copying binary
                    print(f"Warning: Could not sanitize plan (terraform show failed): {result.stderr}")
                    shutil.copy2(plan_file, output_path)
                else:
                    plan_data = json.loads(result.stdout)
                    sanitized = PlanArtifactManager.sanitize_plan_json(plan_data)
                    output_path.write_text(json.dumps(sanitized, indent=2))
            except Exception as e:
                print(f"Warning: Could not sanitize plan ({e}), copying binary")
                shutil.copy2(plan_file, output_path)
        else:
            shutil.copy2(plan_file, output_path)
        
        return output_path
    
    @staticmethod
    def validate_plan_file(plan_file: str) -> bool:
        """Validate that a plan file is readable and valid JSON."""
        try:
            import json
            with open(plan_file, "r") as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, OSError):
            return False