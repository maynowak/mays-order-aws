"""
AWS Execution Context - Validated AWS profile and account binding.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import json as json_module

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class AWSValidationError(Exception):
    """Raised when AWS profile validation fails."""
    pass


@dataclass
class AWSExecutionContext:
    """
    Validated AWS execution context.
    
    Contains all validated AWS credentials and identity information.
    Every Terraform operation requires a validated AWSExecutionContext.
    """
    
    profile: Optional[str]  # None for IAM role / default credential chain
    region: str
    account_id: str
    identity_arn: str
    validated: bool = True
    validation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    profile_source: str = "explicit"  # explicit, env, config, iam_role
    
    def __post_init__(self):
        if self.profile is not None and not self.profile:
            raise ValueError("Profile cannot be empty string")
        if not self.region:
            raise ValueError("Region cannot be empty")
        if not self.account_id:
            raise ValueError("Account ID cannot be empty")
        if not self.identity_arn:
            raise ValueError("Identity ARN cannot be empty")
        if not self.validated:
            raise ValueError("Context must be validated")
    
    def to_env(self) -> dict:
        """Return environment variables for Terraform execution."""
        env = {"AWS_REGION": self.region}
        if self.profile:
            env["AWS_PROFILE"] = self.profile
        return env
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json_module.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "AWSExecutionContext":
        data = json.loads(json_str)
        return cls(**data)
    
    def get_environment(self, extra_env: Optional[dict] = None) -> dict:
        """Get complete environment for Terraform execution."""
        env = {**os.environ}
        env.update(self.to_env())
        if extra_env:
            env.update(extra_env)
        return env


class AWSProfileValidator:
    """
    Validates AWS profile and extracts identity information.
    
    Supports two modes:
    - Profile-based: Uses AWS CLI with --profile (local development)
    - Profile-less: Uses boto3 default credential chain (CI/CD, IAM roles)
    """
    
    def __init__(self, profile: Optional[str], region: Optional[str] = None):
        self.profile = profile
        self.region = region
    
    def validate(self) -> AWSExecutionContext:
        """
        Validate AWS credentials and return execution context.
        
        Performs:
        1. Credential availability check (profile or default chain)
        2. STS GetCallerIdentity
        3. Account ID verification
        4. Region validation
        
        Raises:
            AWSValidationError: If any validation step fails
        """
        if self.profile:
            # Profile-based validation (local development)
            return self._validate_with_profile()
        else:
            # Profile-less validation (CI/CD, IAM roles)
            return self._validate_without_profile()
    
    def _validate_with_profile(self) -> AWSExecutionContext:
        """Validate using AWS CLI with explicit profile."""
        # 1. Check profile exists
        self._check_profile_exists()
        
        # 2. Get caller identity
        identity = self._get_caller_identity_with_profile()
        account_id = identity.get("Account")
        identity_arn = identity.get("Arn")
        
        if not account_id:
            raise AWSValidationError("Could not determine account ID from STS")
        if not identity_arn:
            raise AWSValidationError("Could not determine identity ARN from STS")
        
        # 3. Determine region
        region = self._determine_region()
        
        return AWSExecutionContext(
            profile=self.profile,
            region=region,
            account_id=account_id,
            identity_arn=identity_arn,
            validated=True,
            validation_timestamp=datetime.now().isoformat(),
            profile_source="explicit"
        )
    
    def _validate_without_profile(self) -> AWSExecutionContext:
        """Validate using boto3 default credential chain (IAM role, env vars, etc.)."""
        if not BOTO3_AVAILABLE:
            raise AWSValidationError(
                "boto3 not available. Install boto3 for profile-less AWS validation "
                "(required for CI/CD environments)"
            )
        
        # 1. Get caller identity using boto3 (uses default credential chain)
        identity = self._get_caller_identity_boto3()
        account_id = identity.get("Account")
        identity_arn = identity.get("Arn")
        
        if not account_id:
            raise AWSValidationError("Could not determine account ID from STS")
        if not identity_arn:
            raise AWSValidationError("Could not determine identity ARN from STS")
        
        # 2. Determine region
        region = self._determine_region_boto3()
        
        return AWSExecutionContext(
            profile=None,
            region=region,
            account_id=account_id,
            identity_arn=identity_arn,
            validated=True,
            validation_timestamp=datetime.now().isoformat(),
            profile_source="iam_role"
        )
    
    def _check_profile_exists(self) -> None:
        """Check if AWS profile exists."""
        try:
            result = subprocess.run(
                ["aws", "configure", "list", "--profile", self.profile],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise AWSValidationError(
                    f"AWS profile '{self.profile}' not found: {result.stderr}"
                )
        except FileNotFoundError:
            raise AWSValidationError("AWS CLI not found in PATH")
        except subprocess.TimeoutExpired:
            raise AWSValidationError("AWS CLI timeout")
    
    def _get_caller_identity_with_profile(self) -> dict:
        """Get caller identity from STS using AWS CLI with profile."""
        try:
            cmd = ["aws", "sts", "get-caller-identity", "--profile", self.profile]
            if self.region:
                cmd.extend(["--region", self.region])
            
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                raise AWSValidationError(
                    f"Cannot get AWS identity: {result.stderr}"
                )
            
            import json
            return json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            raise AWSValidationError("STS call timeout")
        except FileNotFoundError:
            raise AWSValidationError("AWS CLI not found in PATH")
        except Exception as e:
            raise AWSValidationError(f"Error checking AWS identity: {e}")
    
    def _get_caller_identity_boto3(self) -> dict:
        """Get caller identity from STS using boto3 default credential chain."""
        try:
            session = boto3.Session(profile_name=self.profile) if self.profile else boto3.Session()
            sts = session.client("sts", region_name=self.region)
            return sts.get_caller_identity()
        except NoCredentialsError:
            raise AWSValidationError(
                "No AWS credentials found. Configure AWS_PROFILE, "
                "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, or run in an IAM role environment."
            )
        except ProfileNotFound as e:
            raise AWSValidationError(f"AWS profile not found: {e}")
        except ClientError as e:
            raise AWSValidationError(f"STS error: {e}")
        except Exception as e:
            raise AWSValidationError(f"Error checking AWS identity via boto3: {e}")
    
    def _determine_region(self) -> str:
        """Determine AWS region for profile-based mode."""
        if self.region:
            return self.region
        
        # Try to get from profile config
        try:
            result = subprocess.run(
                ["aws", "configure", "get", "region", "--profile", self.profile],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        
        # Default
        return "eu-central-1"
    
    def _determine_region_boto3(self) -> str:
        """Determine AWS region for profile-less mode."""
        if self.region:
            return self.region
        
        # Try boto3 session region
        try:
            session = boto3.Session(profile_name=self.profile) if self.profile else boto3.Session()
            if session.region_name:
                return session.region_name
        except Exception:
            pass
        
        # Try environment variable
        env_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if env_region:
            return env_region
        
        # Default
        return "eu-central-1"


def validate_aws_context(
    profile: Optional[str],
    region: str,
    expected_account_id: Optional[str] = None
) -> AWSExecutionContext:
    """
    Convenience function to validate AWS context.
    
    Args:
        profile: AWS profile name (None for default credential chain / IAM role)
        region: AWS region
        expected_account_id: Optional expected account ID for verification
        
    Returns:
        Validated AWSExecutionContext
        
    Raises:
        AWSValidationError: If validation fails
    """
    validator = AWSProfileValidator(profile, region)
    context = validator.validate()
    
    # Verify expected account if provided
    if expected_account_id and context.account_id != expected_account_id:
        raise AWSValidationError(
            f"Account ID mismatch: expected {expected_account_id}, "
            f"got {context.account_id}"
        )
    
    return context
