"""
Installation Context - Central configuration and state for the installer.
"""

from __future__ import annotations

import json
import os
import subprocess
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from installer.core.deployment_identity import (
    DeploymentContext,
    DeploymentId,
    SemanticVersion,
    DevelopmentPhase,
    DevelopmentState,
    DevelopmentStatus,
    PlanOperation,
    PlanMetadata,
    PlanIdentity,
    TagSet,
    ResourceOwnership,
    OwnershipStatus,
    DeploymentContext,
    create_deployment_context,
)

from installer.core.aws_context import AWSProfileValidator, AWSExecutionContext, AWSValidationError


@dataclass
class InstallationContext:
    """
    Central configuration context for the installer.

    Contains all configuration needed for the deployment lifecycle.
    No AWS secrets are stored in this context.
    """

    # AWS Configuration
    aws_profile: str = ""
    aws_region: str = "eu-central-1"
    aws_account_id: Optional[str] = None
    identity_arn: Optional[str] = None

    # Validated AWS execution context (set after validation)
    aws_execution_context: Optional["AWSExecutionContext"] = None

    # Environment Configuration
    environment: str = "Development"
    project_name: str = "mays-orders"

    # H2: Deployment Identity & Versioning
    deployment_version: str = "0.1.0"           # Semantic version (major.minor.patch)
    development_phase: str = "H2"               # Development phase (e.g., H2, D8)
    development_step: int = 0                   # Development step number
    development_status: str = "development"     # development, testing, staging, production, archived

    # Cognito Configuration
    cognito_mode: str = "user_pool"  # user_pool, identity_pool, external
    cognito_user_pool_id: Optional[str] = None
    cognito_client_id: Optional[str] = None

    # Terraform Configuration
    terraform_dir: str = "terraform"
    terraform_workspace: str = "default"

    # Run Configuration
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d-%H%M%S"))
    run_dir: Optional[str] = None

    # Safety flags
    allow_aws_operations: bool = False  # Must be explicitly enabled for apply/destroy
    dry_run: bool = True  # Default to dry-run mode

    def __post_init__(self):
        """Initialize derived fields."""
        if self.run_dir is None:
            self.run_dir = f".mays-installer/runs/{self.run_id}"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> InstallationContext:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    @classmethod
    def from_env(cls) -> InstallationContext:
        """Create context from environment variables."""
        return cls(
            aws_profile=os.environ.get("AWS_PROFILE", ""),
            aws_region=os.environ.get("AWS_REGION", "eu-central-1"),
            aws_account_id=os.environ.get("AWS_ACCOUNT_ID"),
            identity_arn=os.environ.get("AWS_IDENTITY_ARN"),
            environment=os.environ.get("ENVIRONMENT", "Development"),
            project_name=os.environ.get("PROJECT_NAME", "mays-orders"),
            deployment_version=os.environ.get("DEPLOYMENT_VERSION", "0.1.0"),
            development_phase=os.environ.get("DEVELOPMENT_PHASE", "H2"),
            development_step=int(os.environ.get("DEVELOPMENT_STEP", "0")),
            development_status=os.environ.get("DEVELOPMENT_STATUS", "development"),
            cognito_mode=os.environ.get("COGNITO_MODE", "user_pool"),
            cognito_user_pool_id=os.environ.get("COGNITO_USER_POOL_ID"),
            cognito_client_id=os.environ.get("COGNITO_CLIENT_ID"),
            terraform_dir=os.environ.get("TERRAFORM_DIR", "terraform"),
            terraform_workspace=os.environ.get("TERRAFORM_WORKSPACE", "default"),
            run_id=os.environ.get("RUN_ID", datetime.now().strftime("%Y%m%d-%H%M%S")),
            run_dir=os.environ.get("RUN_DIR"),
            allow_aws_operations=os.environ.get("ALLOW_AWS_OPERATIONS", "false").lower() == "true",
            dry_run=os.environ.get("DRY_RUN", "true").lower() == "true",
        )

    def ensure_run_dir(self) -> Path:
        """Create and return the run directory."""
        run_path = Path(self.run_dir)
        run_path.mkdir(parents=True, exist_ok=True)
        return run_path

    def save(self) -> Path:
        """Save context to run directory."""
        run_path = self.ensure_run_dir()
        context_file = run_path / "context.json"
        context_file.write_text(self.to_json())
        return context_file

    @classmethod
    def load(cls, run_dir: str) -> InstallationContext:
        """Load context from run directory."""
        context_file = Path(run_dir) / "context.json"
        if context_file.exists():
            return cls.from_json(context_file.read_text())
        raise FileNotFoundError(f"Context file not found: {context_file}")

    def get_deployment_id(self) -> "DeploymentId":
        """Get canonical deployment ID from context."""
        from installer.core.deployment_identity import DeploymentId
        if not self.aws_execution_context:
            raise ValueError("AWS execution context not validated")
        return DeploymentId(
            account_id=self.aws_execution_context.account_id,
            project=self.project_name,
            environment=self.environment
        )

    def get_deployment_context(self) -> "DeploymentContext":
        """Create H2 DeploymentContext from this installation context."""
        from installer.core.deployment_identity import (
            DeploymentContext, DeploymentId, SemanticVersion,
            DevelopmentPhase, DevelopmentState, DevelopmentStatus
        )
        if not self.aws_execution_context:
            raise ValueError("AWS execution context not validated")

        deployment_id = DeploymentId(
            account_id=self.aws_execution_context.account_id,
            project=self.project_name,
            environment=self.environment
        )

        version = SemanticVersion.parse(self.deployment_version)
        dev_phase = DevelopmentPhase.parse(self.development_phase)

        dev_state = DevelopmentState(
            version=version,
            phase=dev_phase,
            status=DevelopmentStatus(self.development_status)
        )

        return DeploymentContext(
            deployment_id=deployment_id,
            version=version,
            development_state=dev_state,
            aws_region=self.aws_region,
            aws_profile=self.aws_profile,
            allow_aws_operations=self.allow_aws_operations,
            dry_run=self.dry_run,
            run_id=self.run_id,
            run_dir=self.run_dir,
            terraform_dir=self.terraform_dir
        )

    def validate_aws_context(self) -> Optional["AWSExecutionContext"]:
        """
        Validate AWS profile and create AWSExecutionContext.

        Returns:
            AWSExecutionContext if validation succeeds, None otherwise
        """
        # Run validation using ValidationLayer
        validation = ValidationLayer(self)
        result = validation.run_all()

        if result.has_errors():
            return None

        # If we got here, the AWS context was created during validation
        return self.aws_execution_context


@dataclass
class ValidationCheck:
    """Individual validation check result."""
    name: str
    status: str  # PASS, FAIL, WARNING, SKIP
    message: str
    details: Optional[dict] = None


@dataclass
class ValidationResult:
    """Result of validation checks."""
    status: str  # READY, BLOCKED, WARNING
    checks: list[ValidationCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_check(self, check: ValidationCheck) -> None:
        """Add a validation check."""
        self.checks.append(check)
        if check.status == "FAIL":
            self.errors.append(f"{check.name}: {check.message}")
            self.status = "BLOCKED"
        elif check.status == "WARNING":
            self.warnings.append(f"{check.name}: {check.message}")
            if self.status != "BLOCKED":
                self.status = "WARNING"
        elif check.status == "PASS":
            if self.status == "":
                self.status = "READY"

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def summary(self) -> str:
        """Generate a summary string."""
        passed = sum(1 for c in self.checks if c.status == "PASS")
        failed = sum(1 for c in self.checks if c.status == "FAIL")
        warned = sum(1 for c in self.checks if c.status == "WARNING")
        skipped = sum(1 for c in self.checks if c.status == "SKIP")

        return (
            f"Validation {self.status}: {passed} passed, "
            f"{failed} failed, {warned} warned, {skipped} skipped"
        )

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "checks": [asdict(c) for c in self.checks],
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class ValidationLayer:
    """
    Validation layer for pre-flight checks.

    Performs structured validation checks before any Terraform operations.
    """

    def __init__(self, context: InstallationContext):
        self.context = context
        self.result = ValidationResult(status="")

    def run_all(self) -> ValidationResult:
        """Run all validation checks."""
        self.result = ValidationResult(status="")

        # Core checks
        self._check_aws_profile_validated()
        self._check_region()
        self._check_terraform_cli()
        self._check_terraform_version()
        self._check_terraform_working_dir()
        self._check_terraform_config()
        self._check_installer_config()

        return self.result

    def _add_check(self, name: str, status: str, message: str, details: Optional[dict] = None):
        check = ValidationCheck(name=name, status=status, message=message, details=details)
        self.result.add_check(check)

    def _check_aws_profile_validated(self) -> None:
        """Check if AWS credentials are validated and create AWSExecutionContext."""
        try:
            # Use the new credential resolver that supports both profile and profile-less modes
            profile = self.context.aws_profile if self.context.aws_profile else None
            validator = AWSProfileValidator(profile, self.context.aws_region)
            aws_ctx = validator.validate()

            # Verify expected account if configured
            if self.context.aws_account_id and aws_ctx.account_id != self.context.aws_account_id:
                self._add_check(
                    "aws_account_id_validated",
                    "FAIL",
                    f"Account ID mismatch: expected {self.context.aws_account_id}, got {aws_ctx.account_id}"
                )
                return

            # Store validated AWS execution context
            self.context.aws_execution_context = aws_ctx

            profile_desc = f"profile '{self.context.aws_profile}'" if self.context.aws_profile else "IAM role / default credential chain"
            self._add_check(
                "aws_profile_validated",
                "PASS",
                f"AWS {profile_desc} validated for account {aws_ctx.account_id}"
            )
            self._add_check(
                "aws_identity_validated",
                "PASS",
                f"AWS identity validated: {aws_ctx.identity_arn}"
            )
            self._add_check(
                "aws_account_id_validated",
                "PASS",
                f"Account ID validated: {aws_ctx.account_id}"
            )

        except AWSValidationError as e:
            self._add_check(
                "aws_profile_validated",
                "FAIL",
                f"AWS validation failed: {e}"
            )
        except FileNotFoundError:
            self._add_check(
                "aws_cli",
                "FAIL",
                "AWS CLI not found in PATH"
            )
        except subprocess.TimeoutExpired:
            self._add_check(
                "aws_cli_timeout",
                "FAIL",
                "AWS CLI timeout"
            )
        except Exception as e:
            self._add_check(
                "aws_validation_error",
                "FAIL",
                f"Error validating AWS context: {e}"
            )

    def _check_region(self) -> None:
        """Check if region is valid."""
        valid_regions = [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-west-3",
            "eu-central-1", "eu-central-2",
            "eu-north-1", "eu-south-1", "eu-south-2",
            "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
            "ap-southeast-1", "ap-southeast-2", "ap-southeast-3",
            "ap-south-1", "ap-south-2",
            "ca-central-1", "ca-west-1",
            "sa-east-1",
            "me-south-1", "me-central-1",
            "af-south-1",
            "il-central-1"
        ]

        if self.context.aws_region in valid_regions:
            self._add_check(
                "region",
                "PASS",
                f"Region '{self.context.aws_region}' is valid"
            )
        else:
            self._add_check(
                "region",
                "WARNING",
                f"Region '{self.context.aws_region}' may not be valid"
            )

    def _check_terraform_cli(self) -> None:
        """Check if Terraform CLI is available."""
        try:
            result = subprocess.run(
                ["terraform", "version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                self._add_check(
                    "terraform_cli",
                    "PASS",
                    f"Terraform available: {version_line}"
                )
            else:
                self._add_check(
                    "terraform_cli",
                    "FAIL",
                    f"Terraform version check failed: {result.stderr}"
                )
        except FileNotFoundError:
            self._add_check(
                "terraform_cli",
                "FAIL",
                "Terraform CLI not found in PATH"
            )
        except Exception as e:
            self._add_check(
                "terraform_cli",
                "FAIL",
                f"Error checking Terraform: {e}"
            )

    def _check_terraform_version(self) -> None:
        """Check Terraform version meets minimum."""
        import re
        try:
            result = subprocess.run(
                ["terraform", "version", "-json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                import json
                version_info = json.loads(result.stdout)
                version_str = version_info.get("terraform_version", "")

                # Parse version
                match = re.match(r"(\d+)\.(\d+)\.(\d+)", version_str)
                if match:
                    major, minor, patch = map(int, match.groups())
                    if major > 1 or (major == 1 and minor >= 5):
                        self._add_check(
                            "terraform_version",
                            "PASS",
                            f"Terraform version {version_str} meets minimum (>=1.5.0)"
                        )
                    else:
                        self._add_check(
                            "terraform_version",
                            "WARNING",
                            f"Terraform version {version_str} may be below minimum 1.5.0"
                        )
                else:
                    self._add_check(
                        "terraform_version",
                        "WARNING",
                        f"Could not parse Terraform version: {version_str}"
                    )
            else:
                self._add_check(
                    "terraform_version",
                    "WARNING",
                    "Could not get Terraform version info"
                )
        except Exception as e:
            self._add_check(
                "terraform_version",
                "WARNING",
                f"Could not check Terraform version: {e}"
            )

    def _check_terraform_working_dir(self) -> None:
        """Check Terraform working directory exists."""
        terraform_dir = Path(self.context.terraform_dir)
        if terraform_dir.exists() and terraform_dir.is_dir():
            self._add_check(
                "terraform_working_dir",
                "PASS",
                f"Terraform directory exists: {terraform_dir}"
            )
        else:
            self._add_check(
                "terraform_working_dir",
                "FAIL",
                f"Terraform directory not found: {terraform_dir}"
            )

    def _check_terraform_config(self) -> None:
        """Check Terraform configuration files exist."""
        terraform_dir = Path(self.context.terraform_dir)
        required_files = ["main.tf", "variables.tf", "outputs.tf"]

        missing = []
        for req in required_files:
            if not (terraform_dir / req).exists():
                missing.append(req)

        if not missing:
            self._add_check(
                "terraform_config",
                "PASS",
                "All required Terraform config files present"
            )
        else:
            self._add_check(
                "terraform_config",
                "FAIL",
                f"Missing Terraform config files: {', '.join(missing)}"
            )

    def _check_installer_config(self) -> None:
        """Check installer configuration."""
        if self.context.project_name:
            self._add_check(
                "project_name",
                "PASS",
                f"Project name: {self.context.project_name}"
            )
        else:
            self._add_check(
                "project_name",
                "FAIL",
                "Project name not configured"
            )

        if self.context.environment:
            self._add_check(
                "environment",
                "PASS",
                f"Environment: {self.context.environment}"
            )
        else:
            self._add_check(
                "environment",
                "WARNING",
                "Environment not set, defaulting to Development"
            )
