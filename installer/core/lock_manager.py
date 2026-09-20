"""
H3-2: Concurrent Run Protection - Lock Mechanism

Provides file-based locking to prevent concurrent mutating operations
against the same deployment identity.
"""

from __future__ import annotations

import os
import time
import json
import fcntl
import signal
import atexit
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from installer.core.deployment_identity import DeploymentId


class LockError(Exception):
    """Exception raised for lock-related errors."""
    pass


class LockState(Enum):
    """Lock states."""
    ACQUIRED = "acquired"
    RELEASED = "released"
    STALE = "stale"
    CONFLICT = "conflict"


@dataclass
class LockMetadata:
    """Metadata stored in lock file."""
    deployment_id: str
    operation: str  # "deploy" or "destroy" or "state_push"
    run_id: str
    pid: int
    started_at: str
    hostname: str
    command: str
    status: str = "active"
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "LockMetadata":
        data = json.loads(json_str)
        return cls(**data)


class RunLock:
    """
    File-based lock for preventing concurrent mutating operations.
    
    Uses file locking (fcntl) with metadata tracking to prevent
    concurrent mutating operations against the same deployment identity.
    """
    
    def __init__(self, deployment_id: str, operation: str, 
                 run_id: str, lock_dir: Optional[Path] = None,
                 stale_threshold_seconds: int = 3600):
        """
        Initialize run lock.
        
        Args:
            deployment_id: Deployment identity (account:project:environment)
            operation: Operation type ("deploy", "destroy", "state_push")
            run_id: Unique run identifier
            lock_dir: Directory for lock files (default: .mays-installer/locks)
            stale_threshold_seconds: Seconds after which lock is considered stale
        """
        self.deployment_id = deployment_id
        self.operation = operation
        self.run_id = run_id
        self.lock_dir = lock_dir or Path(".mays-installer/locks")
        self.stale_threshold = stale_threshold_seconds
        
        # Create lock directory
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        
        # Lock file path (includes deployment ID and operation)
        safe_deployment_id = deployment_id.replace(":", "_").replace("/", "_")
        self.lock_file = self.lock_dir / f"{safe_deployment_id}_{operation}.lock"
        self.metadata_file = self.lock_dir / f"{safe_deployment_id}_{operation}.meta.json"
        
        self._lock_fd: Optional[int] = None
        self._acquired = False
        self._metadata: Optional[LockMetadata] = None
        
        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)
    
    def acquire(self, blocking: bool = True, timeout: float = 30.0) -> bool:
        """
        Acquire the lock.
        
        Args:
            blocking: If True, wait for lock; if False, return immediately
            timeout: Maximum time to wait for lock (seconds)
            
        Returns:
            True if lock acquired, False if not acquired (non-blocking)
            
        Raises:
            LockError: If lock cannot be acquired or stale lock detected
        """
        if self._acquired:
            return True
        
        # Check for stale lock first
        self._check_stale_lock()
        
        # Open lock file
        self._lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY, 0o644)
        
        try:
            if blocking:
                # Try to acquire with timeout
                start_time = time.time()
                while True:
                    try:
                        fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except (IOError, OSError):
                        if time.time() - time.time() > timeout:
                            raise LockError(f"Timeout waiting for lock: {self.lock_file}")
                        time.sleep(0.1)
            else:
                # Non-blocking
                try:
                    fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (IOError, OSError):
                    os.close(self._lock_fd)
                    self._lock_fd = None
                    return False
            
            # Write lock metadata
            self._write_metadata()
            self._acquired = True
            
            # Register signal handlers for cleanup
            self._register_signal_handlers()
            
            return True
            
        except Exception as e:
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            raise LockError(f"Failed to acquire lock: {e}")
    
    def release(self) -> bool:
        """
        Release the lock.
        
        Returns:
            True if lock was released, False if not held
        """
        if not self._acquired or self._lock_fd is None:
            return False
        
        try:
            # Update metadata to released
            if self._metadata:
                self._metadata.status = "released"
                self._write_metadata()
            
            # Release file lock
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None
            self._acquired = False
            
            # Remove lock files
            self._cleanup_lock_files()
            
            return True
        except Exception as e:
            # Even on error, try to clean up
            self._cleanup_on_exit()
            raise LockError(f"Failed to release lock: {e}")
    
    def _write_metadata(self) -> None:
        """Write lock metadata to file."""
        if self._metadata is None:
            self._metadata = LockMetadata(
                deployment_id=self.deployment_id,
                operation=self.operation,
                run_id=self.run_id,
                pid=os.getpid(),
                started_at=datetime.now().isoformat(),
                hostname=os.uname().nodename,
                command=" ".join(sys.argv) if hasattr(sys, 'argv') else "unknown"
            )
        
        # Write atomically using temporary file
        temp_file = self.metadata_file.with_suffix(".tmp")
        temp_file.write_text(self._metadata.to_json())
        temp_file.replace(self.metadata_file)
    
    def _read_metadata(self) -> Optional["LockMetadata"]:
        """Read lock metadata from file."""
        if not self.metadata_file.exists():
            return None
        try:
            content = self.metadata_file.read_text()
            return LockMetadata.from_json(content)
        except (json.JSONDecodeError, OSError):
            return None
    
    def _check_stale_lock(self) -> None:
        """Check if existing lock is stale and handle it."""
        if not self.lock_file.exists():
            return
        
        # Check metadata
        existing_meta = self._read_metadata()
        if existing_meta is None:
            # No metadata, might be orphaned lock
            if self._is_process_alive(None):
                return
            # Remove orphaned lock
            self._cleanup_lock_files()
            return
        
        # Check if process is still alive
        pid = existing_meta.pid
        if self._is_process_alive(pid):
            # Lock is active, check if stale
            started = datetime.fromisoformat(existing_meta.started_at.replace('Z', '+00:00'))
            age = (datetime.now() - started).total_seconds()
            if age > self.stale_threshold:
                # Stale lock - remove it
                self._cleanup_lock_files()
                return
            raise LockError(
                f"Active lock exists for {self.deployment_id}/{self.operation} "
                f"(run: {existing_meta.run_id}, pid: {pid}, age: {age:.0f}s). "
                f"Use --force to override if you're sure it's safe."
            )
        else:
            # Process dead, lock is stale
            self._cleanup_lock_files()
    
    def _is_process_alive(self, pid: Optional[int]) -> bool:
        """Check if a process is still alive."""
        if pid is None or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def _cleanup_lock_files(self) -> None:
        """Remove lock and metadata files."""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except OSError:
            pass
        try:
            if self.metadata_file.exists():
                self.metadata_file.unlink()
        except OSError:
            pass
    
    def _cleanup_on_exit(self) -> None:
        """Cleanup on process exit."""
        if self._acquired and self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            except OSError:
                pass
            self._cleanup_lock_files()
    
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful cleanup."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, self._signal_handler)
            except (OSError, ValueError):
                pass  # Some signals not available on all platforms
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Signal handler for graceful cleanup."""
        self.release()
        sys.exit(128 + signum)
    
    def __enter__(self) -> "RunLock":
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
    
    @property
    def is_acquired(self) -> bool:
        return self._acquired
    
    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """Get current lock metadata as dictionary."""
        if self._metadata:
            return asdict(self._metadata)
        existing = self._read_metadata()
        return asdict(existing) if existing else None


class LockManager:
    """
    High-level lock manager for coordinating multiple locks.
    
    Provides a simpler interface for acquiring locks with proper
    error handling and diagnostics.
    """
    
    def __init__(self, lock_dir: Optional[Path] = None, stale_threshold: int = 3600):
        self.lock_dir = lock_dir or Path(".mays-installer/locks")
        self.stale_threshold = stale_threshold
        self._active_locks: Dict[str, RunLock] = {}
    
    def acquire(self, deployment_id: str, operation: str, run_id: str,
                blocking: bool = True, timeout: float = 30.0) -> "RunLock":
        """
        Acquire a lock for a deployment operation.
        
        Args:
            deployment_id: Deployment identity string
            operation: Operation type (deploy, destroy, state_push)
            run_id: Unique run identifier
            blocking: If True, wait for lock; if False, return immediately
            timeout: Maximum time to wait for lock (seconds)
            
        Returns:
            Acquired RunLock instance
            
        Raises:
            LockError: If lock cannot be acquired
        """
        lock = RunLock(deployment_id, operation, run_id, stale_threshold_seconds=self.stale_threshold)
        self._active_locks[f"{deployment_id}:{operation}"] = lock
        lock.acquire(blocking=blocking, timeout=30.0)
        return lock
    
    def release(self, deployment_id: str, operation: str) -> bool:
        """Release a specific lock."""
        key = f"{deployment_id}:{operation}"
        if key in self._active_locks:
            lock = self._active_locks.pop(key)
            return lock.release()
        return False
    
    def release_all(self) -> None:
        """Release all active locks."""
        for lock in self._active_locks.values():
            try:
                lock.release()
            except Exception:
                pass  # Best effort cleanup
        self._active_locks.clear()
    
    def get_active_locks(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all active locks."""
        result = {}
        for key, lock in self._active_locks.items():
            result[key] = lock.get_metadata() or {}
        return result
    
    def check_stale_locks(self) -> list:
        """Check for and return list of stale locks."""
        stale = []
        if not self.lock_dir.exists():
            return stale
        
        for lock_file in self.lock_dir.glob("*.lock"):
            # Extract deployment_id and operation from filename
            name = lock_file.stem  # removes .lock
            # Parse deployment_id_operation format
            parts = name.split("_")
            if len(parts) >= 2:
                deployment_id = "_".join(parts[:-1])
                operation = parts[-1]
                
                # Try to read metadata
                meta_file = self.lock_dir / f"{name}.meta.json"
                if meta_file.exists():
                    try:
                        with open(meta_file) as f:
                            meta = json.load(f)
                        started = datetime.fromisoformat(meta.get("started_at", "").replace('Z', '+00:00'))
                        age = (datetime.now() - started).total_seconds()
                        if age > 3600:  # 1 hour default
                            stale_info = {
                                "deployment_id": meta.get("deployment_id"),
                                "operation": meta.get("operation"),
                                "run_id": meta.get("run_id"),
                                "pid": meta.get("pid"),
                                "age_seconds": age,
                                "started_at": meta.get("started_at")
                            }
                            stale.append(stale_info)
                    except Exception:
                        pass
        return stale
    
    def cleanup_stale_locks(self) -> int:
        """Remove stale locks and return count cleaned."""
        stale = self.check_stale_locks()
        count = 0
        for stale_info in stale:
            deployment_id = stale_info["deployment_id"]
            operation = stale_info["operation"]
            safe_id = deployment_id.replace(":", "_").replace("/", "_")
            lock_file = self.lock_dir / f"{safe_id}_{operation}.lock"
            meta_file = self.lock_dir / f"{safe_id}_{operation}.meta.json"
            
            try:
                if Path(lock_file).exists():
                    Path(lock_file).unlink()
                if Path(meta_file).exists():
                    Path(meta_file).unlink()
                count += 1
            except OSError:
                pass
        return count
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_all()


def create_lock_manager(lock_dir: Optional[Path] = None, 
                        stale_threshold: int = 3600) -> LockManager:
    """Factory function to create a LockManager."""
    return LockManager(lock_dir, stale_threshold)


import atexit
import sys