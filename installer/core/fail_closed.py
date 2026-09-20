"""
H3-9: Fail-Closed Rule - Default Deny Behavior

Enforces fail-closed security principle: any uncertainty or error
results in a safe failure rather than proceeding with potentially
unsafe operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Callable, TypeVar, Generic
from functools import wraps
from contextlib import contextmanager

from installer.core.deployment_identity import DeploymentId, DeploymentContext


class FailClosedError(Exception):
    """Exception raised when fail-closed policy triggers."""
    pass


class ValidationFailedError(FailClosedError):
    """Raised when validation fails and fail-closed policy applies."""
    pass


class SecurityViolationError(FailClosedError):
    """Raised when a security boundary is violated."""
    pass


class UncertainStateError(FailClosedError):
    """Raised when system state cannot be determined with certainty."""
    pass


class FailClosedPolicy(Enum):
    """Fail-closed policy modes."""
    STRICT = "strict"        # Fail on any uncertainty
    STANDARD = "standard"    # Fail on security-relevant uncertainty
    LENIENT = "lenient"      # Only fail on explicit security violations


@dataclass
class FailClosedConfig:
    """Configuration for fail-closed behavior."""
    policy: FailClosedPolicy = FailClosedPolicy.STANDARD
    
    # What constitutes a security-relevant failure
    fail_on_validation_error: bool = True
    fail_on_unknown_state: bool = True
    fail_on_plan_mismatch: bool = True
    fail_on_deployment_mismatch: bool = True
    fail_on_lock_failure: bool = True
    fail_on_unknown_aws_state: bool = True
    
    # What to do on uncertainty
    treat_unknown_as_failure: bool = True
    treat_timeout_as_failure: bool = True
    treat_interruption_as_failure: bool = True
    
    def __post_init__(self):
        if self.policy == FailClosedPolicy.STRICT:
            self.fail_on_validation_error = True
            self.fail_on_unknown_state = True
            self.fail_on_plan_mismatch = True
            self.fail_on_deployment_mismatch = True
            self.fail_on_lock_failure = True
            self.fail_on_unknown_aws_state = True
            self.treat_unknown_as_failure = True
            self.treat_timeout_as_failure = True
            self.treat_interruption_as_failure = True
        elif self.policy == FailClosedPolicy.LENIENT:
            self.fail_on_validation_error = False
            self.fail_on_unknown_state = False
            self.fail_on_plan_mismatch = False
            self.fail_on_deployment_mismatch = False
            self.fail_on_lock_failure = False
            self.fail_on_unknown_aws_state = False
            self.treat_unknown_as_failure = False
            self.treat_timeout_as_failure = False
            self.treat_interruption_as_failure = False


class FailClosedError(Exception):
    """Base exception for fail-closed violations."""
    pass


class ValidationFailedError(FailClosedError):
    """Raised when validation fails and fail-closed policy applies."""
    pass


class SecurityViolationError(FailClosedError):
    """Raised when a security boundary is violated."""
    pass


class UncertainStateError(FailClosedError):
    """Raised when system state cannot be determined with certainty."""
    pass


class DeploymentMismatchError(FailClosedError):
    """Raised when deployment identity doesn't match."""
    pass


class PlanIntegrityError(FailClosedError):
    """Raised when plan integrity check fails."""
    pass


class LockFailureError(FailClosedError):
    """Raised when lock acquisition fails."""
    pass


class UnknownAWSStateError(FailClosedError):
    """Raised when AWS state cannot be determined."""
    pass


T = TypeVar('T')


class FailClosedGuard:
    """
    Enforces fail-closed behavior for critical operations.
    
    Provides decorators and context managers that enforce
    fail-closed semantics.
    """
    
    def __init__(self, config: Optional["FailClosedConfig"] = None):
        self.config = config or FailClosedConfig()
    
    def _should_fail(self, condition: bool, error_type: type, message: str) -> None:
        """Raise appropriate exception if condition indicates failure."""
        if condition:
            raise self._make_error(error_type, message)
    
    def _make_error(self, error_type: type, message: str) -> FailClosedError:
        """Create appropriate error instance."""
        return error_type(message)
    
    def require_valid(self, condition: bool, message: str = "Validation failed") -> None:
        """Require condition to be True, else raise ValidationFailedError."""
        if self.config.fail_on_validation_error:
            self._should_fail(not condition, ValidationFailedError, message)
    
    def require_known_state(self, state: Optional[Any], message: str = "Unknown state") -> Any:
        """Require state to be known (not None/unknown)."""
        if self.config.fail_on_unknown_state:
            self._should_fail(state is None, UncertainStateError, message)
        return state
    
    def require_plan_match(self, plan_meta, expected_context, message: str = "Plan mismatch") -> None:
        """Require plan metadata to match expected context."""
        if self.config.fail_on_plan_mismatch:
            self._should_fail(True, PlanIntegrityError, message)
    
    def require_deployment_match(self, actual: DeploymentId, expected: DeploymentId, 
                                  message: str = "Deployment ID mismatch") -> None:
        """Require deployment IDs to match."""
        if self.config.fail_on_deployment_mismatch:
            self._should_fail(actual != expected, DeploymentMismatchError, message)
    
    def require_lock(self, lock_acquired: bool, message: str = "Lock acquisition failed") -> None:
        """Require lock to be acquired."""
        if self.config.fail_on_lock_failure:
            self._should_fail(not lock_acquired, LockFailureError, message)
    
    def require_aws_state(self, aws_state: Optional[Any], message: str = "Unknown AWS state") -> None:
        """Require AWS state to be known."""
        if self.config.fail_on_unknown_aws_state:
            self._should_fail(aws_state is None, UnknownAWSStateError, message)


class FailClosedDecorator:
    """Decorator for enforcing fail-closed behavior on functions."""
    
    def __init__(self, config: Optional["FailClosedConfig"] = None):
        self.guard = FailClosedGuard(config)
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FailClosedError:
                # Re-raise fail-closed errors
                raise
            except Exception as e:
                # Convert unexpected errors to fail-closed
                raise FailClosedError(f"Unexpected error in {func.__name__}: {e}") from e
        return wraps(func)(self.guard.validate(func)) if hasattr(self, 'validate') else func
    
    def validate(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                # Validate result if needed
                return result
            except FailClosedError:
                raise
            except Exception as e:
                raise FailClosedError(f"Unexpected error: {e}") from e
        return wraps(func)(wrapper)


@contextmanager
def fail_closed_context(config: Optional["FailClosedConfig"] = None):
    """
    Context manager that enforces fail-closed behavior.
    
    Usage:
        with fail_closed_context():
            result = risky_operation()
    """
    config = config or FailClosedConfig()
    guard = FailClosedGuard(config)
    
    try:
        yield guard
    except FailClosedError:
        raise
    except Exception as e:
        raise FailClosedError(f"Unexpected error: {e}") from e


def fail_closed(config: Optional["FailClosedConfig"] = None) -> Callable:
    """
    Decorator that enforces fail-closed behavior on a function.
    
    Usage:
        @fail_closed()
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FailClosedError:
                raise
            except Exception as e:
                raise FailClosedError(f"Unexpected error in {func.__name__}: {e}") from e
        return wraps(func)(wrapper)
    return decorator


@contextmanager
def fail_closed_scope(config: Optional[FailClosedConfig] = None):
    """
    Context manager for fail-closed scope.
    
    Usage:
        with fail_closed_scope():
            result = critical_operation()
    """
    config = config or FailClosedConfig()
    guard = FailClosedGuard(config)
    
    try:
        yield guard
    except FailClosedError:
        raise
    except Exception as e:
        raise FailClosedError(f"Unexpected error: {e}") from e


def fail_closed(
    config: Optional["FailClosedConfig"] = None,
    message: str = "Operation failed due to fail-closed policy"
) -> Callable:
    """
    Decorator that enforces fail-closed behavior.
    
    Usage:
        @fail_closed()
        def critical_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FailClosedError:
                raise
            except Exception as e:
                raise FailClosedError(message) from e
        return wraps(func)(wrapper)
    return decorator


class FailClosedValidator:
    """
    Validator that enforces fail-closed semantics.
    
    Used to validate critical preconditions before operations.
    """
    
    def __init__(self, config: Optional["FailClosedConfig"] = None):
        self.config = config or FailClosedConfig()
    
    def validate_deployment_context(self, context: "DeploymentContext") -> None:
        """Validate deployment context is complete and valid."""
        # Require deployment ID
        if not self._has_valid_deployment_id(context):
            raise DeploymentMismatchError("Invalid or missing deployment ID")
        
        # Require version
        if not context.version:
            raise ValidationFailedError("Missing deployment version")
        
        # Require development state
        if not context.development_state:
            raise ValidationFailedError("Missing development state")
        
        # Validate AWS context if operations allowed
        if context.allow_aws_operations:
            if not context.aws_region:
                raise ValidationFailedError("AWS region required for mutations")
            if not context.aws_profile:
                raise ValidationFailedError("AWS profile required for mutations")
    
    def validate_plan_integrity(self, plan_meta, expected_context) -> None:
        """Validate plan metadata matches expected context."""
        # Check deployment ID
        if plan_meta.deployment_id != expected_deployment_id:
            raise DeploymentMismatchError(
                f"Plan deployment ID mismatch: expected {expected_deployment_id}, got {plan_meta.deployment_id}"
            )
        
        # Check operation
        if plan_meta.operation != expected_operation:
            raise ValidationFailedError(
                f"Plan operation mismatch: expected {expected_operation}, got {plan_meta.operation}"
            )
        
        # Check version (warn only by default)
        if plan_meta.version != expected_version:
            if self.config.fail_on_plan_mismatch:
                raise ValidationFailedError(
                    f"Plan version mismatch: expected {expected_version}, got {plan_meta.version}"
                )
    
    def validate_aws_context(self, aws_context) -> None:
        """Validate AWS execution context."""
        if not aws_context or not aws_context.validated:
            raise UnknownAWSStateError("AWS context not validated")
        
        if not aws_context.account_id:
            raise ValidationFailedError("Missing AWS account ID")
        
        if not aws_context.region:
            raise ValidationFailedError("Missing AWS region")
        
        if not aws_context.identity_arn:
            raise ValidationFailedError("Missing AWS identity ARN")


def create_fail_closed_config(
    policy: str = "standard",
    **overrides
) -> "FailClosedConfig":
    """Create fail-closed configuration with optional overrides."""
    policy_enum = FailClosedPolicy(policy.lower())
    config = FailClosedConfig(policy=policy_enum)
    
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config


def strict_fail_closed() -> FailClosedConfig:
    """Create strict fail-closed configuration."""
    return FailClosedConfig(policy=FailClosedPolicy.STRICT)


def standard_fail_closed() -> FailClosedConfig:
    """Create standard fail-closed configuration."""
    return FailClosedConfig(policy=FailClosedPolicy.STANDARD)


def lenient_fail_closed() -> FailClosedConfig:
    """Create lenient fail-closed configuration."""
    return FailClosedConfig(policy=FailClosedPolicy.LENIENT)