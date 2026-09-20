"""
H3-4: Subprocess Safety - Secure Subprocess Execution

Provides hardened subprocess execution with validation, timeouts,
and safe environment handling.
"""

from __future__ import annotations

import os
import subprocess
import signal
import time
import shlex
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

from installer.core.workspace import WorkspaceIntegrity, WorkspaceError
from installer.core.deployment_identity import AWSExecutionContext


class SubprocessError(Exception):
    """Exception raised for subprocess execution errors."""
    pass


class SubprocessTimeoutError(SubprocessError):
    """Exception raised when subprocess times out."""
    pass


class SubprocessValidationError(SubprocessError):
    """Exception raised when subprocess validation fails."""
    pass


class CommandExecutionError(SubprocessError):
    """Exception raised when command execution fails."""
    pass


class SubprocessSafetyLevel(Enum):
    """Security level for subprocess execution."""
    STRICT = "strict"      # Full validation, no shell
    STANDARD = "standard"  # Standard validation
    PERMISSIVE = "permissive"  # Minimal validation (not recommended)


@dataclass
class SafeSubprocessConfig:
    """Configuration for safe subprocess execution."""
    # Command validation
    allowed_commands: Optional[List[str]] = None  # None = allow all
    blocked_commands: List[str] = field(default_factory=lambda: ["rm -rf", "dd", "mkfs", "fdisk"])
    
    # Execution limits
    max_duration_seconds: int = 300
    max_output_size: int = 10 * 1024 * 1024  # 10MB
    max_memory_mb: Optional[int] = None  # Not enforced in Python
    
    # Environment
    allowed_env_vars: Optional[List[str]] = None  # None = allow all from safe list
    blocked_env_vars: List[str] = field(default_factory=lambda: [
        "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", 
        "AWS_SESSION_TOKEN", "PASSWORD", "SECRET", "TOKEN", "PRIVATE_KEY"
    ])
    
    # Working directory
    allowed_working_dirs: Optional[List[Path]] = None
    blocked_working_dirs: List[Path] = field(default_factory=list)
    
    # Shell
    allow_shell: bool = False
    shell_executable: Optional[str] = None
    
    # Environment
    inherit_env: bool = True
    env_allowlist: Optional[List[str]] = None
    env_blocklist: List[str] = field(default_factory=lambda: [
        "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", 
        "AWS_SESSION_TOKEN", "PASSWORD", "SECRET", "TOKEN", "PRIVATE_KEY"
    ])
    
    # Resource limits (Linux only, via resource module)
    max_cpu_time: Optional[int] = None  # seconds
    max_memory_bytes: Optional[int] = None  # bytes
    max_file_size: Optional[int] = None  # bytes
    
    # Validation
    validate_args: bool = True
    validate_env: bool = True
    validate_working_dir: bool = True
    
    def __post_init__(self):
        if self.allowed_working_dirs is not None:
            self.allowed_working_dirs = [Path(d).resolve() for d in self.allowed_working_dirs]
        self.blocked_working_dirs = [Path(d).resolve() for d in self.blocked_working_dirs]


class SubprocessResult:
    """Result of a safe subprocess execution."""
    
    def __init__(
        self,
        command: List[str],
        exit_code: int,
        stdout: str,
        stderr: str,
        duration: float,
        success: bool,
        timed_out: bool = False,
        signal: Optional[int] = None,
        command_string: str = ""
    ):
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration
        self.success = success
        self.timed_out = timed_out
        self.signal = signal
        self.command_string = command_string
        self.executed_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "command_string": self.command_string,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": self.duration,
            "success": self.success,
            "timed_out": self.timed_out,
            "signal": self.signal,
            "executed_at": datetime.now().isoformat()
        }
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, default=str)


class SafeSubprocessRunner:
    """
    Hardened subprocess runner with validation, timeouts, and safety checks.
    
    Replaces raw subprocess.run with validated, audited execution.
    """
    
    def __init__(
        self,
        workspace: Optional["WorkspaceIntegrity"] = None,
        config: Optional["SafeSubprocessConfig"] = None,
        default_timeout: int = 300
    ):
        self.workspace = workspace
        self.config = config or SafeSubprocessConfig()
        self.default_timeout = default_timeout
        self._execution_log: List[Dict[str, Any]] = []
    
    def _validate_command(self, command: List[str]) -> List[str]:
        """Validate command and arguments."""
        if not command:
            raise SubprocessValidationError("Empty command")
        
        # Check for shell metacharacters if shell not allowed
        if not self.config.allow_shell:
            for arg in command:
                if any(c in arg for c in [';', '&', '|', '`', '$', '(', ')', '<', '>']):
                    raise SubprocessValidationError(
                        f"Shell metacharacter in argument: {arg}"
                    )
        
        # Check for blocked commands
        command_string = " ".join(command)
        for blocked in self.config.blocked_commands:
            if blocked in command_string:
                raise SubprocessValidationError(f"Blocked command pattern: {blocked}")
        
        # Check allowed commands
        if self.config.allowed_commands:
            if command[0] not in self.config.allowed_commands:
                raise SubprocessValidationError(f"Command not in allowlist: {command[0]}")
        
        # Validate arguments
        if self.config.validate_args:
            for arg in command:
                if len(arg) > 4096:  # Reasonable limit
                    raise SubprocessValidationError(f"Argument too long: {arg[:100]}...")
        
        return command
    
    def _validate_environment(self, env: dict) -> dict:
        """Filter and validate environment variables."""
        safe_env = {}
        
        for key, value in env.items():
            # Skip blocked variables
            if any(blocked.lower() in key.lower() for key in self.config.env_blocklist):
                continue  # Skip sensitive variables
            
            # Check allowlist if configured
            if self.config.env_allowlist:
                if not any(key == allowed or key.startswith(allowed + "_") for allowed in self.config.env_allowlist):
                    continue
            
            # Check blocklist
            if any(key == blocked or key.startswith(blocked + "_") for blocked in self.config.env_blocklist):
                continue
            
            # Validate value length
            if len(value) > 65536:  # 64KB limit
                continue
            
            safe_env[key] = value
        
        return safe_env
    
    def _validate_working_dir(self, cwd: Optional[Path]) -> Path:
        """Validate working directory."""
        if cwd is None:
            cwd = Path.cwd()
        else:
            cwd = Path(cwd).resolve()
        
        if self.config.validate_working_dir:
            # Check allowed directories
            if self.config.allowed_working_dirs:
                allowed = False
                for allowed_dir in self.config.allowed_working_dirs:
                    try:
                        if cwd.is_relative_to(allowed_dir.resolve()):
                            allowed = True
                            break
                    except (ValueError, RuntimeError):
                        continue
                if not allowed:
                    raise SubprocessValidationError(f"Working directory not in allowed list: {cwd}")
            
            # Check blocked directories
            for blocked in self.config.blocked_working_dirs:
                try:
                    if cwd.is_relative_to(blocked.resolve()):
                        raise SubprocessValidationError(f"Working directory in blocked list: {cwd}")
                except (ValueError, RuntimeError):
                    pass
        
        return cwd
    
    def _build_environment(self, base_env: Optional[dict] = None, extra_env: Optional[dict] = None) -> dict:
        """Build safe environment for subprocess."""
        base = base_env or {}
        if self.config.inherit_env:
            base = {**os.environ, **base}
        else:
            base = {}
        
        # Add extra env vars
        if extra_env:
            base.update(extra_env)
        
        # Validate and filter
        env = self._validate_environment(base)
        
        # Ensure critical vars are set
        if "PATH" not in env:
            env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        
        return env
    
    def run(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        capture_output: bool = True,
        text: bool = True,
        input_data: Optional[str] = None,
        env: Optional[dict] = None,
        check: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Run command with safety checks.
        
        Args:
            command: Command and arguments as list
            cwd: Working directory
            timeout: Timeout in seconds
            capture_output: Capture stdout/stderr
            text: Return strings instead of bytes
            input_data: Input to pass to stdin
            env: Additional environment variables
            check: Raise on non-zero exit code
            
        Returns:
            subprocess.CompletedProcess
        """
        # Validate command
        validated_command = self._validate_command(command)
        
        # Validate working directory
        cwd = self._validate_working_dir(cwd)
        
        # Build environment
        env = self._build_environment()
        
        # Add any extra environment
        if env:
            env.update(self._validate_environment(env))
        
        # Use default timeout if not specified
        if timeout is None:
            timeout = self.default_timeout
        
        # Build command string for logging
        cmd_string = " ".join(shlex.quote(arg) for arg in command)
        
        # Log execution
        exec_record = {
            "command": command,
            "command_string": " ".join(shlex.quote(arg) for arg in command),
            "cwd": str(cwd),
            "timeout": timeout,
            "started_at": datetime.now().isoformat()
        }
        
        start_time = time.time()
        
        try:
            # Execute
            process = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_data,
                env=env,
                shell=False,  # Never use shell=True
            )
            
            duration = time.time() - start_time
            
            # Record execution
            exec_record.update({
                "exit_code": process.returncode,
                "duration": time.time() - start_time,
                "stdout_length": len(process.stdout) if process.stdout else 0,
                "stderr_length": len(process.stderr) if process.stderr else 0,
                "success": process.returncode == 0,
                "completed_at": datetime.now().isoformat()
            })
            
            # Check output size
            if process.stdout and len(process.stdout) > self.config.max_output_size:
                raise SubprocessError(f"Output exceeds maximum size ({self.config.max_output_size} bytes)")
            
            if process.stderr and len(process.stderr) > self.config.max_output_size:
                raise SubprocessError(f"Stderr exceeds maximum size")
            
            # Check exit code
            if check and process.returncode != 0:
                raise CommandExecutionError(
                    f"Command failed with exit code {process.returncode}",
                    exit_code=process.returncode,
                    stdout=process.stdout,
                    stderr=process.stderr
                )
            
            self._execution_log.append(exec_record)
            
            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr
            )
            
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            exec_record = {
                "command": command,
                "duration": time.time() - start_time,
                "timed_out": True,
                "error": f"Command timed out after {timeout}s"
            }
            self._execution_log.append(exec_record)
            raise SubprocessTimeoutError(f"Command timed out after {timeout}s") from e
        except Exception as e:
            duration = time.time() - start_time
            exec_record = {
                "command": command,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self._execution_log.append(exec_record)
            raise SubprocessError(f"Failed to execute command: {e}") from e
    
    def run_with_result(
        self,
        command: List[str],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        input_data: Optional[str] = None,
        env: Optional[dict] = None
    ) -> "SubprocessResult":
        """
        Run command and return structured result.
        
        Does not raise on non-zero exit code.
        """
        start_time = time.time()
        cmd_string = " ".join(shlex.quote(arg) for arg in command)
        
        try:
            process = self.run(
                command, cwd=cwd, timeout=timeout,
                capture_output=True, text=True,
                input_data=None, env=None, check=False
            )
            
            return SubprocessResult(
                command=command,
                exit_code=process.returncode,
                stdout=process.stdout or "",
                stderr=process.stderr or "",
                duration=time.time() - time.time(),  # Will be overwritten
                success=process.returncode == 0,
                command_string=cmd_string
            )
        except subprocess.TimeoutExpired as e:
            return SubprocessResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out: {e}",
                duration=time.time() - time.time(),  # Placeholder
                success=False,
                timed_out=True,
                command_string=cmd_string
            )
        except Exception as e:
            return SubprocessResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute: {e}",
                duration=0,
                success=False,
                command_string=cmd_string
            )
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get execution log."""
        return self._execution_log.copy()
    
    def clear_log(self) -> None:
        """Clear execution log."""
        self._execution_log.clear()


def create_safe_runner(
    workspace_root: Optional[Path] = None,
    terraform_dir: str = "terraform",
    default_timeout: int = 300,
    allowed_dirs: Optional[List[Path]] = None,
    allowed_commands: Optional[List[str]] = None,
    blocked_commands: Optional[List[str]] = None
) -> SafeSubprocessRunner:
    """
    Factory function to create a configured SafeSubprocessRunner.
    
    Args:
        workspace_root: Workspace root directory
        terraform_dir: Terraform directory
        default_timeout: Default command timeout
        allowed_dirs: Allowed working directories
        allowed_commands: Allowed commands (None = all)
        blocked_commands: Additional blocked commands
        
    Returns:
        Configured SafeSubprocessRunner
    """
    workspace = None
    if workspace_root:
        workspace = WorkspaceIntegrity(workspace_root, terraform_dir)
    
    config = SafeSubprocessConfig()
    if allowed_dirs:
        config.allowed_working_dirs = allowed_dirs
    if allowed_commands:
        config.allowed_commands = allowed_commands
    if blocked_commands:
        config.blocked_commands.extend(blocked_commands)
    
    return SafeSubprocessRunner(workspace, config, default_timeout)