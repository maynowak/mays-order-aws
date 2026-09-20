"""
H3-5: Interruption/Recovery Safety - Signal Handling

Provides signal handling for graceful shutdown and state recovery.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import atexit
import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from contextlib import contextmanager

from installer.core.deployment_identity import DeploymentId, DeploymentContext, PlanOperation


class ExecutionState(Enum):
    """Execution state of the installer."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


@dataclass
class ExecutionStateTracker:
    """Tracks execution state for recovery."""
    state: ExecutionState = ExecutionState.NOT_STARTED
    operation: str = ""
    deployment_id: str = ""
    run_id: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    plan_file: Optional[str] = None
    step: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "operation": self.operation,
            "deployment_id": self.deployment_id,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "plan_file": self.plan_file,
            "step": self.step,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)


class InterruptibleOperation:
    """
    Context manager for interruptible operations with state tracking.
    
    Handles SIGINT/SIGTERM gracefully, preserves state for recovery.
    """
    
    def __init__(
        self,
        operation: str,
        deployment_id: str,
        run_id: str,
        state_file: Optional[Path] = None,
        plan_file: Optional[str] = None
    ):
        self.operation = operation
        self.deployment_id = deployment_id
        self.run_id = run_id
        self.plan_file = plan_file
        self.state_file = state_file or Path(f".mays-installer/runs/{run_id}/state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.state = ExecutionStateTracker(
            state=ExecutionState.NOT_STARTED,
            operation=operation,
            deployment_id=deployment_id,
            run_id=run_id,
            plan_file=plan_file
        )
        
        self._original_handlers = {}
        self._interrupted = False
        self._interrupt_received = False
        
        # Register cleanup
        atexit.register(self._cleanup)
    
    def __enter__(self) -> "InterruptibleOperation":
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.fail(str(exc_val))
        else:
            self.succeed()
        return False
    
    def start(self) -> None:
        """Mark operation as started."""
        self.state.state = ExecutionState.RUNNING
        self.state.started_at = datetime.now().isoformat()
        self._save_state()
        self._register_signal_handlers()
    
    def succeed(self) -> None:
        """Mark operation as succeeded."""
        self.state.state = ExecutionState.SUCCEEDED
        self.state.completed_at = datetime.now().isoformat()
        self._save_state()
        self._cleanup()
    
    def fail(self, error: str) -> None:
        """Mark operation as failed."""
        self.state.state = ExecutionState.FAILED
        self.state.completed_at = datetime.now().isoformat()
        self.state.error = error
        self._save_state()
        self._cleanup()
    
    def interrupt(self) -> None:
        """Mark operation as interrupted."""
        self._interrupt_received = True
        self.state.state = ExecutionState.INTERRUPTED
        self.state.completed_at = datetime.now().isoformat()
        self.state.error = "Interrupted by signal"
        self._save_state()
    
    def step(self, step_name: str) -> None:
        """Update current step."""
        self.state.step = step_name
        self._save_state()
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata."""
        self.state.metadata[key] = value
        self._save_state()
    
    def _save_state(self) -> None:
        """Save state to file atomically."""
        temp_file = self.state_file.with_suffix(".tmp")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text(self.state.to_json())
        temp_file.replace(self.state_file)
    
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                original = signal.signal(sig, self._signal_handler)
                self._original_handlers[sig] = original
            except (OSError, ValueError):
                pass  # Some signals not available on all platforms
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Signal handler for graceful shutdown."""
        self._interrupt_received = True
        self.interrupt()
        # Re-raise signal with default handler to terminate
        if signum in self._original_handlers:
            signal.signal(signum, self._original_handlers[signum])
            os.kill(os.getpid(), signum)
    
    def _cleanup(self) -> None:
        """Cleanup signal handlers."""
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except (OSError, ValueError):
                pass
        self._original_handlers.clear()
    
    @property
    def was_interrupted(self) -> bool:
        return self._interrupt_received
    
    @property
    def is_running(self) -> bool:
        return self.state.state == ExecutionState.RUNNING
    
    @contextmanager
    def step_context(self, step_name: str):
        """Context manager for a step."""
        self.step(step_name)
        try:
            yield
        except Exception as e:
            self.fail(str(e))
            raise
        finally:
            pass


@contextmanager
def interruptible_operation(
    operation: str,
    deployment_id: str,
    run_id: str,
    state_file: Optional[Path] = None,
    plan_file: Optional[str] = None
) -> "InterruptibleOperation":
    """
    Context manager for interruptible operations.
    
    Usage:
        with interruptible_operation("deploy", "123:project:dev", "run-123") as op:
            op.step("validation")
            # ... do work
            op.step("plan")
            # ... more work
            op.succeed()
    """
    op = InterruptibleOperation(
        operation=operation,
        deployment_id=deployment_id,
        run_id=run_id,
        state_file=state_file,
        plan_file=plan_file
    )
    try:
        op.start()
        yield op
        if op.state.state == ExecutionState.RUNNING:
            op.succeed()
    except Exception as e:
        op.fail(str(e))
        raise


class RecoveryManager:
    """
    Manages recovery from interrupted operations.
    """
    
    def __init__(self, runs_dir: Path = Path(".mays-installer/runs")):
        self.runs_dir = Path(runs_dir)
    
    def find_interrupted_runs(self) -> List[Dict[str, Any]]:
        """Find interrupted runs that can be recovered."""
        interrupted = []
        
        if not self.runs_dir.exists():
            return []
        
        for run_dir in self.runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            
            state_file = run_dir / "state.json"
            if not state_file.exists():
                continue
            
            try:
                with open(state_file) as f:
                    state = json.load(f)
                
                if state.get("state") in ("running", "interrupted"):
                    interrupted.append({
                        "run_id": run_dir.name,
                        "state": state,
                        "state_file": str(state_file)
                    })
            except (json.JSONDecodeError, OSError):
                pass
        
        return interrupted
    
    def get_recovery_info(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get recovery info for a specific run."""
        state_file = self.runs_dir / run_id / "state.json"
        if not state_file.exists():
            return None
        
        try:
            with open(state_file) as f:
                state = json.load(f)
            return state
        except (json.JSONDecodeError, OSError):
            return None
    
    def mark_resolved(self, run_id: str, resolution: str) -> None:
        """Mark an interrupted run as resolved."""
        state_file = self.runs_dir / run_id / "state.json"
        if not state_file.exists():
            return
        
        try:
            with open(state_file) as f:
                state = json.load(f)
            
            state["resolution"] = resolution
            state["resolved_at"] = datetime.now().isoformat()
            
            temp_file = state_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(state, indent=2, default=str))
            temp_file.replace(state_file)
        except (OSError, json.JSONDecodeError):
            pass


class SignalHandler:
    """
    Centralized signal handling for the installer.
    """
    
    _instance: Optional["SignalHandler"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._handlers: Dict[int, Callable] = {}
        self._original_handlers: Dict[int, Callable] = {}
        self._shutdown_requested = False
    
    def register(self, signum: int, handler: Callable) -> None:
        """Register a signal handler."""
        if signum in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT):
            original = signal.signal(signum, handler)
            self._original_handlers[signum] = original
            self._handlers[signum] = handler
    
    def install_default_handlers(self, shutdown_callback: Callable) -> None:
        """Install default graceful shutdown handlers."""
        def handler(signum, frame):
            print(f"\nReceived signal {signal.Signals(signum).name}, shutting down gracefully...")
            try:
                shutdown_callback()
            except Exception:
                pass
            sys.exit(128 + signum)
        
        self.register(signal.SIGTERM, handler)
        self.register(signal.SIGINT, handler)
        if hasattr(signal, "SIGQUIT"):
            self.register(signal.SIGQUIT, handler)
    
    def restore_original_handlers(self) -> None:
        """Restore original signal handlers."""
        for signum, handler in self._original_handlers.items():
            try:
                signal.signal(signum, handler)
            except (OSError, ValueError):
                pass
        self._original_handlers.clear()
    
    @classmethod
    def get_instance(cls) -> "SignalHandler":
        if cls._instance is None:
            cls._instance = SignalHandler()
        return cls._instance


@contextmanager
def signal_handling_context(shutdown_callback: Callable):
    """
    Context manager for temporary signal handling.
    
    Usage:
        with signal_handling_context(my_shutdown_function):
            # code that can be interrupted
            pass
    """
    handler = SignalHandler()
    handler.install_default_handlers(shutdown_callback)
    try:
        yield
    finally:
        handler.restore_original_handlers()


class GracefulShutdown:
    """
    Manages graceful shutdown sequence.
    """
    
    def __init__(self):
        self._callbacks: List[Callable] = []
        self._shutdown_started = False
        self._lock = threading.Lock()
    
    def register(self, callback: Callable, priority: int = 0) -> None:
        """Register a shutdown callback with priority (higher runs first)."""
        with self._lock:
            self._callbacks.append((priority, callback))
            self._callbacks.sort(key=lambda x: -x[0])
    
    def execute(self) -> None:
        """Execute all shutdown callbacks."""
        if self._shutdown_started:
            return
        
        self._shutdown_started = True
        
        for priority, callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                # Log but continue with other callbacks
                print(f"Shutdown callback failed: {e}", file=sys.stderr)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.execute()
        return False


# Global graceful shutdown instance
_graceful_shutdown = GracefulShutdown()


def get_graceful_shutdown() -> GracefulShutdown:
    """Get the global graceful shutdown manager."""
    return _graceful_shutdown


def register_shutdown_callback(callback: Callable, priority: int = 0) -> None:
    """Register a shutdown callback."""
    _graceful_shutdown.register(callback, priority)


@contextmanager
def graceful_shutdown_context():
    """Context manager for graceful shutdown."""
    shutdown = GracefulShutdown()
    try:
        yield shutdown
    finally:
        shutdown.execute()


import threading
import sys