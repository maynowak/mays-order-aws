"""
H3-8: Logging/Audit Hardening - Sanitize Logs

Provides secure logging with automatic secret sanitization.
"""

from __future__ import annotations

import logging
import re
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from logging import LogRecord, Handler, Formatter, Filter
from logging.handlers import RotatingFileHandler
from enum import Enum
from contextlib import contextmanager
from pathlib import Path


class LogLevel(Enum):
    """Log levels."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class SecretFilter(Filter):
    """
    Logging filter that removes secrets from log records.
    
    Removes or masks sensitive data from log records before they are
    written to log files or stdout.
    """
    
    # Patterns that indicate sensitive data
    SECRET_PATTERNS = [
        r'(?i)(aws_secret_access_key|aws_access_key_id|aws_session_token)',
        r'(?i)(password|passwd|pwd)',
        r'(?i)(secret|secret_key|api_key|api_token)',
        r'(?i)(token|access_token|refresh_token|bearer_token)',
        r'(?i)(private_key|ssh_key|ssh_private_key)',
        r'(?i)(client_secret|client_id)',
        r'(?i)(database_url|connection_string)',
        r'(?i)(authorization|authorization_header)',
    ]
    
    # Keywords that indicate sensitive values
    SECRET_KEYWORDS = [
        "password", "passwd", "pwd", "secret", "key", "token",
        "credential", "auth", "authorization", "private", "private_key"
    ]
    
    def __init__(self):
        super().__init__()
        self._compiled_patterns = [re.compile(p) for p in self.SECRET_PATTERNS]
        self._secret_re = re.compile(r'(?i)(' + '|'.join(self.SECRET_KEYWORDS) + r')\s*[:=]\s*[^\s,}]+')
    
    def filter(self, record: LogRecord) -> bool:
        """Filter and sanitize log record."""
        # Sanitize message
        if record.msg:
            record.msg = self._sanitize_string(str(record.msg))
        
        # Sanitize args
        if record.args:
            record.args = tuple(
                self._sanitize_string(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        # Sanitize exception info
        if record.exc_info:
            # Don't modify exception info, but could sanitize traceback
            pass
        
        return True
    
    def _sanitize_string(self, text: str) -> str:
        """Sanitize a string by replacing secrets with [REDACTED]."""
        if not isinstance(text, str):
            return text
        
        result = text
        
        # Replace secret patterns
        for pattern in self._compiled_patterns:
            result = pattern.sub(r'\1=[REDACTED]', result)
        
        # Replace keyword=value patterns
        def replace_secret(match):
            key = match.group(1)
            return f"{key}=[REDACTED]"
        
        result = self._secret_re.sub(replace_secret, result)
        
        return result


class SanitizingFormatter(Formatter):
    """
    Formatter that automatically sanitizes sensitive data.
    """
    
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self._filter = SecretFilter()
    
    def format(self, record: LogRecord) -> str:
        # Apply sanitization before formatting
        self._filter.filter(record)
        return super().format(record)


class StructuredLogFormatter(Formatter):
    """
    Structured JSON log formatter with built-in sanitization.
    
    Produces JSON logs suitable for log aggregation systems.
    """
    
    DEFAULT_FIELDS = {
        'timestamp', 'level', 'logger', 'message',
        'module', 'function', 'line', 'thread', 'process'
    }
    
    def __init__(self, extra_fields: Optional[List[str]] = None):
        super().__init__()
        self.extra_fields = extra_fields or []
        self._filter = SecretFilter()
    
    def format(self, record: LogRecord) -> str:
        # Apply sanitization
        self._filter.filter(record)
        
        # Build structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": self._filter._sanitize_string(str(record.getMessage())),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process,
        }
        
        # Add extra fields
        for field in self.extra_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if isinstance(value, str):
                    value = self._sanitize_string(value)
                log_entry[field] = value
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add stack info if present
        if record.stack_info:
            log_entry["stack_info"] = self.formatStack(record.stack_info)
        
        # Sanitize all string values
        return json.dumps(self._sanitize_dict(log_entry), default=str)
    
    def _sanitize_string(self, text: str) -> str:
        """Sanitize a string using the secret filter."""
        filter_obj = SecretFilter()
        return filter_obj._sanitize_string(text)
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary values."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._sanitize_string(value)
            elif isinstance(value, dict):
                result[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [self._sanitize_string(v) if isinstance(v, str) else v for v in value]
            else:
                result[key] = value
        return result


class AuditLogger:
    """
    Specialized logger for audit events.
    
    Writes structured audit events to separate log file
    with enhanced security and compliance features.
    """
    
    def __init__(
        self,
        name: str = "mays-installer.audit",
        log_file: Optional[Path] = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler (INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(StructuredLogFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler (DEBUG and above)
        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(StructuredLogFormatter())
            file_handler.addFilter(SecretFilter())
            self.logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def log_event(
        self,
        event_type: str,
        message: str,
        deployment_id: Optional[str] = None,
        operation: Optional[str] = None,
        run_id: Optional[str] = None,
        level: int = logging.INFO,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an audit event."""
        extra_data = {
            "event_type": event_type,
            "deployment_id": deployment_id,
            "operation": operation,
            "run_id": run_id,
        }
        
        if extra:
            # Sanitize extra data
            for key, value in extra.items():
                if isinstance(value, str):
                    extra[key] = self._sanitize_string(value)
        
        if extra:
            extra.update(extra)
        
        self.logger.log(level, message, extra=extra)
    
    def _sanitize_string(self, text: str) -> str:
        """Sanitize string using secret filter."""
        filter_obj = SecretFilter()
        return filter_obj._sanitize_string(text)
    
    def log_validation(self, checks: list, run_id: str, deployment_id: str) -> None:
        """Log validation results."""
        self.log_event(
            event_type="validation",
            message=f"Validation completed: {len([c for c in checks if c.get('status') == 'PASS'])} passed, {len([c for c in checks if c.get('status') == 'FAIL'])} failed",
            deployment_id=deployment_id,
            run_id=run_id,
            level=logging.INFO,
            extra={"checks": checks}
        )
    
    def log_plan_operation(self, operation: str, plan_file: str, run_id: str, 
                          deployment_id: str, success: bool, details: str = "") -> None:
        """Log plan operation."""
        self.log_event(
            event_type=f"plan_{operation}",
            message=f"Plan {operation} {'succeeded' if success else 'failed'}: {details}",
            deployment_id=deployment_id,
            operation=operation,
            run_id=run_id,
            level=logging.INFO if success else logging.ERROR,
            extra={"plan_file": plan_file, "details": details}
        )
    
    def log_deployment(self, operation: str, run_id: str, deployment_id: str,
                       success: bool, details: str = "") -> None:
        """Log deployment operation."""
        self.log_event(
            event_type=f"deployment_{operation}",
            message=f"Deployment {operation} {'succeeded' if success else 'failed'}: {details}",
            deployment_id=deployment_id,
            operation=operation,
            run_id=run_id,
            level=logging.INFO if success else logging.ERROR,
            extra={"details": details}
        )
    
    def log_policy_gate(self, run_id: str, deployment_id: str, 
                       passed: bool, violations: List[str] = None) -> None:
        """Log policy gate result."""
        self.log_event(
            event_type="policy_gate",
            message=f"Policy gate {'passed' if passed else 'failed'}: {len(violations) if violations else 0} violations",
            deployment_id=deployment_id,
            operation="policy_gate",
            run_id=run_id,
            level=logging.INFO if passed else logging.ERROR,
            extra={"violations": violations or []}
        )
    
    def log_approval(self, operation: str, approved: bool, run_id: str,
                     deployment_id: str, auto_approved: bool = False) -> None:
        """Log approval decision."""
        self.log_event(
            event_type="approval",
            message=f"{operation} approval {'granted' if approved else 'denied'}" + 
                    (" (auto-approved)" if auto_approved else ""),
            deployment_id=deployment_id,
            operation=operation,
            run_id=run_id,
            level=logging.INFO if approved else logging.WARNING,
            extra={"auto_approved": auto_approved}
        )
    
    def log_state_change(self, run_id: str, deployment_id: str,
                         operation: str, old_state: str, new_state: str) -> None:
        """Log state transition."""
        self.log_event(
            event_type="state_change",
            message=f"State changed from {old_state} to {new_state}",
            deployment_id=deployment_id,
            operation=operation,
            run_id=run_id,
            level=logging.INFO,
            extra={"old_state": old_state, "new_state": new_state}
        )


def create_audit_logger(
    log_file: Optional[Path] = None,
    name: str = "mays-installer.audit"
) -> AuditLogger:
    """
    Create an audit logger with default configuration.
    
    Args:
        log_file: Path to audit log file
        name: Logger name
        
    Returns:
        Configured AuditLogger instance
    """
    if log_file is None:
        log_file = Path(".mays-installer/audit.log")
    
    return AuditLogger(name=name, log_file=log_file)


def get_installer_logger(name: str = "mays-installer") -> logging.Logger:
    """
    Get a logger with secret filtering enabled.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(StructuredLogFormatter())
        console.addFilter(SecretFilter())
        logger.addHandler(console)
        
        logger.propagate = False
    
    return logger


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    structured: bool = True
) -> logging.Logger:
    """
    Configure logging for the installer.
    
    Args:
        level: Log level
        log_file: Optional log file path
        structured: Use structured JSON formatting
        
    Returns:
        Configured root logger
    """
    # Clear existing handlers
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    if structured:
        console.setFormatter(StructuredLogFormatter())
    else:
        console.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        ))
    console.addFilter(SecretFilter())
    
    root.addHandler(console)
    
    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        if structured:
            file_handler.setFormatter(StructuredLogFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s %(name)s: %(message)s'
            ))
        file_handler.addFilter(SecretFilter())
        root.addHandler(file_handler)
    
    return root


def sanitize_log_message(message: str) -> str:
    """
    Sanitize a log message by removing secrets.
    
    Args:
        message: Log message to sanitize
        
    Returns:
        Sanitized message
    """
    filter_obj = SecretFilter()
    return filter_obj._sanitize_string(str(message))


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize a dictionary by removing/redacting sensitive keys.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized dictionary
    """
    filter_obj = SecretFilter()
    
    def _sanitize(obj):
        if isinstance(obj, str):
            return filter_obj._sanitize_string(obj)
        elif isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj
    
    return _sanitize(data)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    structured: bool = True
) -> logging.Logger:
    """
    Configure logging for the installer.
    
    Args:
        level: Log level
        log_file: Optional log file path
        structured: Use structured JSON formatting
        
    Returns:
        Configured root logger
    """
    # Clear existing handlers
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    if structured:
        console.setFormatter(StructuredLogFormatter())
    else:
        console.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        ))
    console.addFilter(SecretFilter())
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(console)
    
    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredLogFormatter() if True else logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        ))
        file_handler.addFilter(SecretFilter())
        logging.getLogger().addHandler(file_handler)
    
    return logging.getLogger()


@contextmanager
def log_context(**context):
    """
    Context manager to add contextual information to logs.
    
    Usage:
        with log_context(deployment_id="123:proj:dev", run_id="run-123"):
            logger.info("Doing something")
    """
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        for key, value in context.items():
            setattr(record, key, value)
        return record
    
    logging.setLogRecordFactory(record_factory)
    try:
        yield
    finally:
        logging.setLogRecordFactory(old_factory)