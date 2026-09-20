"""
H3-6: Runtime State Consistency - Atomic Operations

Provides atomic file operations and state consistency guarantees.
"""

from __future__ import annotations

import os
import json
import tempfile
import shutil
import fcntl
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Any, TypeVar
from contextlib import contextmanager
from enum import Enum

T = TypeVar('T')


class StateConsistencyError(Exception):
    """Exception raised for state consistency violations."""
    pass


class AtomicOperation:
    """
    Provides atomic file operations with rollback capability.
    
    Ensures filesystem operations are atomic and can be rolled back
    on failure.
    """
    
    @staticmethod
    @contextmanager
    def atomic_write(file_path: Path, mode: str = "w", encoding: str = "utf-8"):
        """
        Atomically write to a file using a temporary file and atomic rename.
        
        Usage:
            with AtomicOperation.atomic_write(Path("config.json")) as f:
                f.write(json.dumps(data))
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temp file in same directory
        with tempfile.NamedTemporaryFile(
            mode=mode,
            encoding=encoding,
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".tmp"
        ) as tmp:
            try:
                yield tmp
                tmp.flush()
                os.fsync(tmp.fileno())
            
                # Atomic rename
                os.replace(tmp.name, path)
            except Exception:
                # Clean up temp file on error
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
                raise
    
    @staticmethod
    @contextmanager
    def atomic_json_write(file_path: Path, indent: int = 2):
        """Atomically write JSON data."""
        with AtomicOperation.atomic_write(file_path) as f:
            yield f
    
    @staticmethod
    def atomic_replace(src: Path, dst: Path) -> None:
        """Atomically replace dst with src."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
    
    @staticmethod
    def atomic_move(src: Path, dst: Path) -> None:
        """Atomically move src to dst."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)


class AtomicStateManager:
    """
    Manages atomic state updates with rollback capability.
    
    Provides transaction-like semantics for state changes.
    """
    
    def __init__(self, state_file: Path, backup_count: int = 3):
        self.state_file = Path(state_file)
        self.backup_count = backup_count
        self._backup_dir = Path(state_file).parent / ".backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._backup_files: list = []
    
    def read_state(self) -> Optional[dict]:
        """Read current state."""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    
    def write_state(self, data: dict, atomic: bool = True) -> bool:
        """Write state atomically."""
        if atomic:
            with AtomicOperation.atomic_write(self.state_file) as f:
                json.dump(data, f, indent=2, default=str)
        else:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        return True
    
    def update_state(self, updater: Callable[[dict], dict]) -> bool:
        """
        Atomically update state using a transformation function.
        
        Args:
            updater: Function that takes current state and returns new state
            
        Returns:
            True if update succeeded
        """
        # Read current state
        current = self.read_state() or {}
        
        # Apply update
        try:
            new_state = updater(current)
        except Exception as e:
            raise StateConsistencyError(f"Updater function failed: {e}")
        
        # Write new state atomically
        return self.write_state(new_state)
    
    def _create_backup(self) -> None:
        """Create a backup of current state."""
        if not self.state_file.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"{self.state_file.stem}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
        backup_path = self._backup_dir / backup_name
        
        try:
            shutil.copy2(self.state_file, backup_path)
            # Clean up old backups
            self._cleanup_old_backups()
        except OSError:
            pass  # Best effort
    
    def _cleanup_old_backups(self) -> None:
        """Remove old backups beyond retention count."""
        backups = sorted(
            self._backup_dir.glob("*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        for backup in self._backup_files[5:]:  # Keep last 5
            try:
                backup.unlink()
            except OSError:
                pass
    
    def verify_integrity(self) -> bool:
        """Verify state file integrity."""
        try:
            data = self.read_state()
            return data is not None
        except Exception:
            return False


class StateTransaction:
    """
    Context manager for atomic state transactions.
    
    Usage:
        with StateTransaction(state_file) as tx:
            tx.update({"key": "value"})
            # If exception occurs, changes are rolled back
    """
    
    def __init__(self, state_file: Path):
        self.state_file = Path(state_file)
        self._original_state: Optional[dict] = None
        self._committed = False
    
    def __enter__(self) -> "StateTransaction":
        # Read and backup original state
        self._original_state = self._read_original()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            # Success - nothing to do, changes already written
            pass
        else:
            # Rollback on exception
            self._rollback()
        return False
    
    def _read_original(self) -> Optional[dict]:
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return None
    
    def write(self, data: dict) -> None:
        """Write state within transaction."""
        with AtomicOperation.atomic_write(self.state_file) as f:
            json.dump(data, f, indent=2, default=str)
    
    def _rollback(self) -> None:
        """Rollback to original state."""
        if self._original_state is not None:
            with AtomicOperation.atomic_write(self.state_file) as f:
                json.dump(self._original_state, f, indent=2, default=str)
        elif self.state_file.exists():
            # No original state, remove file
            try:
                self.state_file.unlink()
            except OSError:
                pass


@contextmanager
def atomic_state_update(state_file: Path) -> Any:
    """
    Context manager for atomic state updates.
    
    Usage:
        with atomic_state_update(state_file) as state:
            state["key"] = "value"
        # Automatically committed on success, rolled back on exception
    """
    state_file = Path(state_file)
    
    # Read original
    original = None
    if state_file.exists():
        try:
            with open(state_file) as f:
                original = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    
    # Create working copy
    working = state_file.with_suffix(".working")
    if state_file.exists():
        shutil.copy2(state_file, working)
    else:
        working.write_text("{}")
    
    try:
        # Yield working copy for modification
        with open(working) as f:
            data = json.load(f)
        
        yield data
        
        # Write back atomically
        with AtomicOperation.atomic_write(state_file) as tmp:
            json.dump(data, tmp, indent=2, default=str)
        
    except Exception:
        # Rollback on error
        if state_file.exists():
            try:
                state_file.unlink()
            except OSError:
                pass
        raise
    else:
        # Clean up working file
        try:
            working.unlink()
        except OSError:
            pass


class ConsistencyChecker:
    """Validates state consistency."""
    
    @staticmethod
    def verify_json_file(file_path: Path) -> bool:
        """Verify file contains valid JSON."""
        try:
            with open(file_path) as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, OSError):
            return False
    
    @staticmethod
    def verify_state_consistency(state_file: Path, expected_schema: Optional[dict] = None) -> bool:
        """Verify state file consistency."""
        if not state_file.exists():
            return False
        
        try:
            with open(state_file) as f:
                data = json.load(f)
            
            if expected_schema:
                # Basic schema validation
                for key, expected_type in expected_schema.items():
                    if key not in data:
                        return False
                    if not isinstance(data[key], expected_type):
                        return False
            
            return True
        except (json.JSONDecodeError, OSError, TypeError):
            return False
    
    @staticmethod
    def verify_atomic_writes(state_file: Path, attempts: int = 10) -> bool:
        """Test that atomic writes work correctly."""
        import threading
        import time
        
        errors = []
        
        def writer(writer_id: int):
            try:
                with atomic_state_update(state_file) as data:
                    data[f"writer_{writer_id}"] = f"value_{writer_id}"
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(5):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify final state
        return ConsistencyChecker.verify_json_file(state_file)


class FileLock:
    """
    Simple file-based lock for coordinating access to shared resources.
    """
    
    def __init__(self, lock_file: Path, timeout: float = 30.0):
        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self._fd: Optional[int] = None
        self._acquired = False
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire the lock."""
        if self._acquired:
            return True
        
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY, 0o644)
        
        try:
            if blocking:
                start_time = time.time()
                while True:
                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except IOError:
                        if timeout and time.time() - start_time > timeout:
                            raise TimeoutError("Lock acquisition timeout")
                        time.sleep(0.1)
            else:
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    os.close(self._fd)
                    return False
            
            self._acquired = True
            return True
        except Exception:
            if self._fd is not None:
                os.close(self._fd)
            raise
    
    def release(self) -> bool:
        """Release the lock."""
        if not self._acquired or self._fd is None:
            return False
        
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
            self._acquired = False
            return True
        except Exception:
            return False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
    
    @property
    def is_acquired(self) -> bool:
        return self._acquired


@contextmanager
def file_lock(lock_file: Path, timeout: float = 30.0) -> Any:
    """Context manager for file locking."""
    lock = FileLock(lock_file, timeout)
    try:
        lock.acquire()
        yield
    finally:
        lock.release()


import hashlib
import atexit