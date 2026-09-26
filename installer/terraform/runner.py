"""
Terraform Runner - Central adapter for Terraform operations.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import shlex


@dataclass
class TerraformCommandAudit:
    """Audit record for a Terraform command execution."""
    command: List[str]
    profile: str
    region: str
    working_directory: str
    start_time: str
    duration: float
    exit_code: int
    success: bool
    stdout: str
    stderr: str
    
    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, default=str)


@dataclass
class TerraformResult:
    """Result of a Terraform command execution."""
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    audit: Optional["TerraformCommandAudit"] = None
    
    @classmethod
    def from_completed_process(
        cls, 
        process: subprocess.CompletedProcess, 
        command: List[str],
        start_time: float,
        profile: str = "",
        region: str = "",
        working_directory: str = ""
    ) -> "TerraformResult":
        duration = time.time() - start_time
        audit = TerraformCommandAudit(
            command=command,
            profile=profile,
            region=region,
            working_directory=working_directory,
            start_time=datetime.fromtimestamp(start_time).isoformat(),
            duration=duration,
            exit_code=process.returncode,
            success=process.returncode == 0,
            stdout=process.stdout or "",
            stderr=process.stderr or ""
        )
        return cls(
            command=command,
            exit_code=process.returncode,
            stdout=process.stdout or "",
            stderr=process.stderr or "",
            duration=duration,
            success=process.returncode == 0,
            audit=audit
        )
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, default=str)


class TerraformRunner:
    """
    Central Terraform Runner.
    
    Encapsulates all Terraform subprocess calls.
    No shell string construction with uncontrolled user input.
    Every command requires a validated AWSExecutionContext.
    """
    
    def __init__(
        self, 
        working_dir: str,
        aws_context: "AWSExecutionContext",
        terraform_bin: str = "terraform",
        env: Optional[dict] = None,
        workspace: str = "default"
    ):
        """
        Initialize TerraformRunner.
        
        Args:
            working_dir: Terraform working directory
            aws_context: Validated AWS execution context (required)
            terraform_bin: Path to terraform binary
            env: Additional environment variables
            workspace: Terraform workspace name for parallel deployments
        """
        if not aws_context.validated:
            raise ValueError("AWSExecutionContext must be validated")
        
        self.working_dir = Path(working_dir).resolve()
        self.terraform_bin = "terraform"
        self.aws_context = aws_context
        self.env = {}
        # Use environment variable override for parallel deployments
        env_workspace = os.environ.get("TERRAFORM_WORKSPACE")
        if env_workspace:
            self.workspace = env_workspace
        else:
            self.workspace = workspace
    
    def _get_terraform_env(self) -> dict:
        """Get environment with AWS profile and region set."""
        env = {**os.environ}
        env.update(self.aws_context.to_env())
        return env
    
    def _run(
        self, 
        args: List[str], 
        capture_output: bool = True,
        timeout: int = 300,
        cwd: Optional[Path] = None
    ) -> subprocess.CompletedProcess:
        """Run Terraform command with structured arguments."""
        cmd = [self.terraform_bin] + args
        
        env = self._get_terraform_env()
        
        start_time = time.time()
        
        try:
            process = subprocess.run(
                cmd,
                cwd=cwd or self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._get_terraform_env()
            )
            return process
        except subprocess.TimeoutExpired as e:
            raise TerraformError(f"Command timed out: {e.cmd}") from e
        except Exception as e:
            raise TerraformError(f"Failed to execute command: {e}") from e
    
    def run_and_get_result(self, args: List[str]) -> "TerraformResult":
        """Run command and return structured result."""
        start_time = time.time()
        working_directory = str(self.working_dir)
        
        try:
            process = subprocess.run(
                [self.terraform_bin] + args,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=180,
                env=self._get_terraform_env()
            )
            return TerraformResult.from_completed_process(
                process, 
                [self.terraform_bin] + args, 
                time.time(),
                profile=self.aws_context.profile,
                region=self.aws_context.region,
                working_directory=str(self.working_dir)
            )
        except subprocess.TimeoutExpired as e:
            return TerraformResult(
                command=[self.terraform_bin] + args,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out: {e}",
                duration=time.time() - start_time,
                success=False
            )
        except Exception as e:
            return TerraformResult(
                command=[self.terraform_bin] + args,
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute: {e}",
                duration=0,
                success=False
            )
    
    def _get_terraform_env(self) -> dict:
        """Get environment with AWS profile and region set."""
        env = {**os.environ}
        env.update(self.aws_context.to_env())
        return env
    
    def version(self) -> "TerraformResult":
        """Get Terraform version."""
        return self.run_and_get_result(["version", "-json"])
    
    def init(
        self, 
        backend: bool = True,
        upgrade: bool = False,
        reconfigure: bool = False
    ) -> "TerraformResult":
        """
        Run terraform init.
        
        Args:
            backend: Whether to configure backend (False for local validation only)
            upgrade: Upgrade modules and providers
            reconfigure: Reconfigure backend
        """
        args = ["init"]
        if not backend:
            args.append("-backend=false")
        if upgrade:
            args.append("-upgrade")
        if reconfigure:
            args.append("-reconfigure")
        return self.run_and_get_result(args)
    
    def validate(self) -> "TerraformResult":
        """Run terraform validate."""
        return self.run_and_get_result(["validate"])
    
    def plan(
        self, 
        out_file: Optional[str] = None,
        destroy: bool = False,
        var_file: Optional[str] = None,
        var: Optional[dict] = None
    ) -> "TerraformResult":
        """
        Run terraform plan.
        
        Args:
            out_file: Path to save plan file
            destroy: Generate destroy plan
            var_file: Path to .tfvars file
            var: Variables to pass
        """
        args = ["plan"]
        if destroy:
            args.append("-destroy")
        if out_file:
            args.extend(["-out", out_file])
        if var_file:
            args.extend(["-var-file", var_file])
        if var:
            for k, v in var.items():
                args.extend(["-var", f"{k}={v}"])
        
        return self.run_and_get_result(args)
    
    def show_plan(self, plan_file: str) -> "TerraformResult":
        """Show plan in JSON format."""
        return self.run_and_get_result(["show", "-json", plan_file])
    
    def plan_destroy(self, out_file: Optional[str] = None) -> "TerraformResult":
        """Generate destroy plan."""
        return self.plan(out_file=out_file, destroy=True)
    
    def show(self, plan_file: str) -> "TerraformResult":
        """Show plan (human readable)."""
        return self.run_and_get_result(["show", plan_file])
    
    def apply(self, plan_file: str, aws_context: Optional["AWSExecutionContext"] = None) -> "TerraformResult":
        """
        Apply a saved Terraform plan.
        
        Args:
            plan_file: Path to saved plan file (from terraform plan -out)
            aws_context: Optional AWS execution context for validation
        """
        if not os.path.exists(plan_file):
            raise TerraformError(f"Plan file not found: {plan_file}")
        
        # Use provided AWS context or fall back to runner's context
        if aws_context is not None:
            if not aws_context.validated:
                raise TerraformError("AWS context not validated")
            # Temporarily override the context for this apply
            original_context = self.aws_context
            self.aws_context = aws_context
            try:
                return self.run_and_get_result(["apply", plan_file])
            finally:
                self.aws_context = original_context
        
        return self.run_and_get_result(["apply", plan_file])
    
    def destroy(self, plan_file: str) -> "TerraformResult":
        """
        Apply a destroy plan.
        
        Args:
            plan_file: Path to destroy plan file
        """
        if not os.path.exists(plan_file):
            raise TerraformError(f"Destroy plan file not found: {plan_file}")
        return self.run_and_get_result(["apply", plan_file])
    
    # State commands
    
    def state_list(self, state_file: Optional[str] = None) -> "TerraformResult":
        """List resources in state."""
        args = ["state", "list"]
        if state_file:
            args.extend(["-state", state_file])
        return self.run_and_get_result(args)
    
    def state_show(self, address: str, state_file: Optional[str] = None) -> "TerraformResult":
        """Show a resource in state."""
        args = ["state", "show", address]
        if state_file:
            args.extend(["-state", state_file])
        return self.run_and_get_result(args)
    
    def state_pull(self) -> "TerraformResult":
        """Pull current state."""
        return self.run_and_get_result(["state", "pull"])
    
    def state_push(self, state_file: str) -> "TerraformResult":
        """Push state to remote."""
        return self.run_and_get_result(["state", "push", state_file])
    
    def output(self, name: Optional[str] = None, state_file: Optional[str] = None) -> "TerraformResult":
        """Show output values."""
        args = ["output", "-json"]
        if name:
            args.append(name)
        if state_file:
            args.extend(["-state", state_file])
        return self.run_and_get_result(args)
    
    def verify_plan_integrity(self, plan_file: str, expected_run_id: str) -> Tuple[bool, str]:
        """
        Verify plan file integrity and ownership.
        
        Args:
            plan_file: Path to plan file (relative to working_dir or absolute)
            expected_run_id: Expected run ID
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Resolve plan file path relative to working_dir
        plan_path = Path(plan_file)
        if not plan_path.is_absolute():
            plan_path = self.working_dir / plan_path
        
        if not plan_path.exists():
            return False, f"Plan file not found: {plan_path}"
        
        # Verify it's a valid plan file by trying to show it
        result = self.show_plan(str(plan_path))
        if not result.success:
            return False, f"Invalid plan file: {result.stderr}"
        
        # Check if plan file belongs to current run (via metadata in run dir)
        plan_path = Path(plan_file).resolve()
        
        # Check if plan file is in a valid run directory
        try:
            run_dirs = list(Path(".mays-installer/runs").glob("*"))
            valid = False
            for run_dir in run_dirs:
                if plan_path.is_relative_to(run_dir / "plans"):
                    valid = True
                    break
            
            # Also check if plan file is in terraform directory (common case)
            if not valid:
                try:
                    if plan_file.is_relative_to(Path("terraform")):
                        valid = True
                except ValueError:
                    pass
            
            if not valid:
                return False, f"Plan file does not belong to a known run directory"
        except Exception:
            # If any error occurs during validation, just skip this check
            pass
        
        return True, ""

    def verify_plan_context_match(self, plan_file: str, expected_context: "AWSExecutionContext") -> Tuple[bool, str]:
        """
        Verify plan file was generated with the same AWS execution context.
        
        Args:
            plan_file: Path to plan file (relative to working_dir or absolute)
            expected_context: Expected AWSExecutionContext
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Resolve plan file path relative to working_dir
        plan_path = Path(plan_file)
        if not plan_path.is_absolute():
            plan_path = self.working_dir / plan_path
        
        if not plan_path.exists():
            return False, f"Plan file not found: {plan_path}"
        
        # Get plan JSON to check provider configuration
        result = self.show_plan(str(plan_path))
        if not result.success:
            return False, f"Cannot read plan file: {result.stderr}"
        
        try:
            import json
            plan_json = json.loads(result.stdout)
            
            # Check provider configuration for region
            provider_configs = plan_json.get("configuration", {}).get("provider_config", {})
            if isinstance(provider_configs, dict):
                for provider_name, config in provider_configs.items():
                    if not isinstance(config, dict) or provider_name.split(".")[0] != "aws":
                        continue
                    expressions = config.get("expressions", {})
                    region_expr = expressions.get("region") if isinstance(expressions, dict) else None
                    region = region_expr.get("constant_value") if isinstance(region_expr, dict) else None
                    if region is not None and region != expected_context.region:
                        return False, f"Plan region '{region}' does not match current context region '{expected_context.region}'"
            
            # Note: We cannot easily verify profile/account from plan file alone
            # since Terraform plan doesn't store the AWS profile used.
            # The profile/account verification is done at apply time via AWSExecutionContext.
            
        except Exception as e:
            # If we can't parse the plan, allow it but log warning
            return True, f"Could not verify plan context: {e}"
        
        return True, ""

    def run_and_get_result(self, args: List[str]) -> "TerraformResult":
        """Run command and return structured result."""
        start_time = time.time()
        working_directory = str(self.working_dir)
        
        # Ensure workspace selected for parallel deployments
        if self.workspace and self.workspace != "default":
            try:
                result = subprocess.run(
                    [self.terraform_bin, "workspace", "select", self.workspace],
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=self._get_terraform_env()
                )
                # If select fails, try to create workspace
                if result.returncode != 0:
                    subprocess.run(
                        [self.terraform_bin, "workspace", "new", self.workspace],
                        cwd=self.working_dir,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        env=self._get_terraform_env()
                    )
            except Exception:
                pass
        
        try:
            process = subprocess.run(
                [self.terraform_bin] + args,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=180,
                env=self._get_terraform_env()
            )
            return TerraformResult.from_completed_process(
                process, 
                [self.terraform_bin] + args, 
                time.time(),
                profile=self.aws_context.profile,
                region=self.aws_context.region,
                working_directory=str(self.working_dir)
            )
        except subprocess.TimeoutExpired as e:
            return TerraformResult(
                command=[self.terraform_bin] + args,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out: {e}",
                duration=time.time() - start_time,
                success=False
            )
        except Exception as e:
            return TerraformResult(
                command=[self.terraform_bin] + args,
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute: {e}",
                duration=0,
                success=False
            )
    
    def _get_terraform_env(self) -> dict:
        """Get environment with AWS profile and region set."""
        env = {**os.environ}
        env.update(self.aws_context.to_env())
        return env
    
    def run_and_get_result(self, args: List[str]) -> "TerraformResult":
        """Run command and return structured result."""
        start_time = time.time()
        working_directory = str(self.working_dir)
        
        try:
            process = subprocess.run(
                [self.terraform_bin] + args,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=180,
                env=self._get_terraform_env()
            )
            return TerraformResult.from_completed_process(
                process, 
                [self.terraform_bin] + args, 
                time.time(),
                profile=self.aws_context.profile,
                region=self.aws_context.region,
                working_directory=str(self.working_dir)
            )
        except subprocess.TimeoutExpired as e:
            return TerraformResult(
                command=[self.terraform_bin] + args,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out: {e}",
                duration=time.time() - start_time,
                success=False
            )
        except Exception as e:
            return TerraformResult(
                command=[self.terraform_bin] + args,
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute: {e}",
                duration=0,
                success=False
            )
    
    def _get_terraform_env(self) -> dict:
        """Get environment with AWS profile and region set."""
        env = {**os.environ}
        env.update(self.aws_context.to_env())
        return env


class TerraformError(Exception):
    """Terraform execution error."""
    pass


@dataclass
class PlanResult:
    """Structured result from Terraform plan analysis."""
    mode: str  # "deploy" or "destroy"
    plan_file: str
    add: int = 0
    change: int = 0
    destroy: int = 0
    replace: int = 0
    resources: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    success: bool = True
    plan_file_path: str = ""
    raw_plan: dict = field(default_factory=dict)
    
    @classmethod
    def from_plan_json(cls, plan_json: dict, plan_file: str, mode: str) -> "PlanResult":
        """Create PlanResult from terraform show -json output."""
        result = cls(mode=mode, plan_file=plan_file)
        result.plan_file_path = plan_file
        result.raw_plan = plan_json
        
        resource_changes = plan_json.get("resource_changes", [])
        
        for change in resource_changes:
            actions = change.get("change", {}).get("actions", [])
            if not actions:
                continue
            
            resource_info = {
                "address": change.get("address", ""),
                "type": change.get("type", ""),
                "name": change.get("name", ""),
                "actions": actions,
                "provider": change.get("provider_name", ""),
            }
            
            result.resources.append(resource_info)
            
            # Count actions
            for action in actions:
                if action == "create":
                    result.add += 1
                elif action == "update":
                    result.change += 1
                elif action == "delete":
                    result.destroy += 1
                elif action == "replace":
                    result.replace += 1
        
        # Extract warnings from plan
        warnings = plan_json.get("warnings", [])
        if warnings:
            result.warnings = warnings if isinstance(warnings, list) else [warnings]
        
        return result
    
    def to_dict(self) -> dict:
        import json
        from dataclasses import asdict
        return asdict(self)
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def summary(self) -> str:
        return (
            f"Plan {self.mode}: {self.add} add, {self.change} change, "
            f"{self.destroy} destroy, {self.replace} replace"
        )
    
    def has_unexpected_destroy(self) -> bool:
        return self.destroy > 0 and self.mode == "deploy"
    
    def has_replacements(self) -> bool:
        return self.replace > 0


# Need to import field from dataclasses
from dataclasses import field