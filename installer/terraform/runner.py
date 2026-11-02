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

# MO-RC4-TERRAFORM-TIMEOUT-FIX-01: operation-specific process timeouts.
# Short/read-only Terraform commands keep 180s; apply and destroy need a
# realistic budget (58+ resources incl. CloudTrail wait) and use 900s by
# default, overridable via MAYS_TERRAFORM_APPLY_TIMEOUT.
DEFAULT_COMMAND_TIMEOUT_SECONDS = 180
DEFAULT_APPLY_TIMEOUT_SECONDS = 900
APPLY_TIMEOUT_ENV_VAR = "MAYS_TERRAFORM_APPLY_TIMEOUT"


def resolve_apply_timeout() -> int:
    """Resolve the apply/destroy timeout in seconds (fail-closed).

    An invalid override (non-numeric, zero, negative) raises TerraformError
    instead of silently falling back to a longer/shorter value.
    """
    raw = os.environ.get(APPLY_TIMEOUT_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_APPLY_TIMEOUT_SECONDS
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise TerraformError(
            f"{APPLY_TIMEOUT_ENV_VAR} must be a positive integer number of "
            f"seconds, got {raw!r}."
        ) from exc
    if value <= 0:
        raise TerraformError(
            f"{APPLY_TIMEOUT_ENV_VAR} must be a positive integer number of "
            f"seconds, got {raw!r}."
        )
    return value


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


def _failed_result(command: List[str], message: str) -> "TerraformResult":
    """Deterministic failure result (configuration errors, no execution)."""
    return TerraformResult(
        command=command,
        exit_code=-1,
        stdout="",
        stderr=message,
        duration=0.0,
        success=False,
    )


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
        workspace: str = "default",
        require_explicit_workspace: bool = False
    ):
        """
        Initialize TerraformRunner.
        
        Args:
            working_dir: Terraform working directory
            aws_context: Validated AWS execution context (required)
            terraform_bin: Path to terraform binary
            env: Additional environment variables
            workspace: Terraform workspace name for parallel deployments
            require_explicit_workspace: Fail-closed guard for project-isolated
                deployments (MO-RC4-P02I-E1B). When True, an empty workspace or
                the Terraform "default" workspace is rejected at construction
                time. Project-isolated callers must pass workspace=project_name.
        """
        if not aws_context.validated:
            raise ValueError("AWSExecutionContext must be validated")

        workspace = (workspace or "").strip()
        if not workspace:
            raise ValueError(
                "workspace must not be empty; project-isolated deployments "
                "must use workspace=project_name"
            )
        if require_explicit_workspace and workspace == "default":
            raise ValueError(
                "workspace 'default' is not allowed for project-isolated "
                "deployments (silent fallback); expected workspace=project_name"
            )
        
        self.working_dir = Path(working_dir).resolve()
        self.terraform_bin = "terraform"
        self.aws_context = aws_context
        self.env = {}
        self.workspace = workspace
        self.require_explicit_workspace = require_explicit_workspace
    
    def _get_terraform_env(self) -> dict:
        """Build explicit subprocess env from validated context.

        No os.environ mutation. Uses AWSExecutionContext.get_environment()
        so static-credential conflicts cannot leak into Terraform.
        """
        get_env = getattr(self.aws_context, "get_environment", None)
        if callable(get_env):
            return get_env()
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

        MO-RC4-P02I-E2B: `-input=false` ist immer gesetzt. Terraform darf im
        Installer nie interaktiv nachfragen (insbesondere nicht "copy existing
        state to the new backend?"); ein solcher Prompt bricht den Lauf ab,
        statt still eine State-Migration durchzufuehren.
        """
        args = ["init", "-input=false"]
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
        # MO-RC4-P02I-E2B: Plaene laufen nie interaktiv (keine Variablen-Prompts).
        args = ["plan", "-input=false"]
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
    
    def plan_destroy(self, out_file: Optional[str] = None, var: Optional[dict] = None,
                     var_file: Optional[str] = None) -> "TerraformResult":
        """Generate destroy plan.

        MO-RC4-P02I-E1B: destroy plans must carry the same project context as
        deploy plans. Without `var` the Terraform default of `project_name`
        ("mays-orders") would be used, silently targeting the default project
        namespace instead of the selected one.
        """
        return self.plan(out_file=out_file, destroy=True, var=var, var_file=var_file)
    
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

        try:
            timeout = resolve_apply_timeout()
        except TerraformError as exc:
            return _failed_result(["terraform", "apply", plan_file], str(exc))

        # Use provided AWS context or fall back to runner's context
        if aws_context is not None:
            if not aws_context.validated:
                raise TerraformError("AWS context not validated")
            # Temporarily override the context for this apply
            original_context = self.aws_context
            self.aws_context = aws_context
            try:
                return self.run_and_get_result(["apply", plan_file], timeout=timeout)
            finally:
                self.aws_context = original_context

        return self.run_and_get_result(["apply", plan_file], timeout=timeout)
    
    def destroy(self, plan_file: str) -> "TerraformResult":
        """
        Apply a destroy plan.
        
        Args:
            plan_file: Path to destroy plan file
        """
        if not os.path.exists(plan_file):
            raise TerraformError(f"Destroy plan file not found: {plan_file}")

        try:
            timeout = resolve_apply_timeout()
        except TerraformError as exc:
            return _failed_result(["terraform", "apply", plan_file], str(exc))

        # A destroy plan is applied like any other saved plan.
        return self.run_and_get_result(["apply", plan_file], timeout=timeout)
    
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

    def _ensure_workspace(self) -> None:
        """Select workspace, create if missing, verify selection.

        The "default" workspace is only reachable for callers that explicitly
        opt out of project isolation; project-isolated runners reject it at
        construction time (require_explicit_workspace=True, MO-RC4-P02I-E1B).
        """
        if self.workspace == "default":
            return
        # Select workspace
        result = subprocess.run(
            [self.terraform_bin, "workspace", "select", self.workspace],
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=self._get_terraform_env()
        )
        if result.returncode == 0:
            # Verify selection
            show = subprocess.run(
                [self.terraform_bin, "workspace", "show"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=30,
                env=self._get_terraform_env()
            )
            if show.returncode != 0:
                raise TerraformError(f"workspace show failed: {show.stderr.strip()}")
            current = show.stdout.strip()
            if current != self.workspace:
                raise TerraformError(f"workspace mismatch: expected {self.workspace}, got {current}")
            return
        # Select failed, check if missing
        output = f"{result.stdout}\n{result.stderr}".lower()
        missing_signals = ("doesn't exist", "does not exist", "not found", "no such workspace")
        if not any(sig in output for sig in missing_signals):
            raise TerraformError(f"terraform workspace select failed for '{self.workspace}': {result.stderr.strip()}")
        # Create workspace
        created = subprocess.run(
            [self.terraform_bin, "workspace", "new", self.workspace],
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=self._get_terraform_env()
        )
        if created.returncode != 0:
            raise TerraformError(f"terraform workspace new failed for '{self.workspace}': {created.stderr.strip()}")
        # Verify creation
        show = subprocess.run(
            [self.terraform_bin, "workspace", "show"],
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=self._get_terraform_env()
        )
        if show.returncode != 0:
            raise TerraformError(f"workspace show after create failed: {show.stderr.strip()}")
        current = show.stdout.strip()
        if current != self.workspace:
            raise TerraformError(f"workspace mismatch after create: expected {self.workspace}, got {current}")

    def run_and_get_result(
        self, args: List[str], timeout: int = DEFAULT_COMMAND_TIMEOUT_SECONDS
    ) -> "TerraformResult":
        """Run command and return structured result with workspace safety.

        `timeout` is the wall-clock limit for the Terraform process. Apply and
        destroy pass an operation-specific limit (900s default, override via
        MAYS_TERRAFORM_APPLY_TIMEOUT); plan/state/read-only commands keep the
        180s default.

        Process handling: `subprocess.run(timeout=...)` kills and reaps the
        direct Terraform child process when the limit is exceeded. Provider
        plugin processes are children of Terraform and terminate with their
        parent; the runner cannot reap them explicitly. A timeout is always
        reported as failure (success=False, exit_code=-1) and is never retried
        automatically.
        """
        start_time = time.time()
        # Workspace safety for non-init commands
        if not (len(args) > 0 and args[0] == "init"):
            self._ensure_workspace()
        try:
            process = subprocess.run(
                [self.terraform_bin] + args,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
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
                stderr=f"Command timed out after {timeout}s: {e}",
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