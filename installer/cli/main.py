"""
CLI for Mays Installer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

from installer.core.context import InstallationContext, ValidationLayer
from installer.core.deployment_identity import (
    DeploymentContext, DeploymentId, SemanticVersion,
    DevelopmentPhase, PlanOperation, PlanMetadata,
    PlanDiscovery, PlanSequenceManager
)
from installer.terraform.runner import TerraformRunner, PlanResult
from installer.terraform.plan_analysis import evaluate_plan_safety
from installer.run.manager import RunDirectoryManager, PlanArtifactManager


class InstallerCLI:
    """Main CLI entry point for Mays Installer."""

    def __init__(self):
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="Mays-Order-AWS-installer",
            description="Mays Recruiting Intelligence Installer - Deployment Lifecycle",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent("""
                Examples:
                  Mays-Order-AWS-installer validate
                  mays-installer plan
                  mays-installer plan --destroy
                  mays-installer validate --profile mayaws --region eu-central-1
            """)
        )

        # Global options
        parser.add_argument(
            "--profile",
            default=os.environ.get("AWS_PROFILE"),
            help="AWS CLI profile (default: mayaws)"
        )
        parser.add_argument(
            "--region",
            default=os.environ.get("AWS_REGION", "eu-central-1"),
            help="AWS region (default: eu-central-1)"
        )
        parser.add_argument(
            "--project-name",
            default=os.environ.get("PROJECT_NAME", "mays-orders"),
            help="Project name (default: mays-orders)"
        )
        parser.add_argument(
            "--aws-region",
            default=os.environ.get("AWS_REGION", "eu-central-1"),
            help="AWS region (default: eu-central-1)"
        )
        parser.add_argument(
            "--environment",
            default=os.environ.get("ENVIRONMENT", "Development"),
            help="Environment (default: Development)"
        )
        parser.add_argument(
            "--terraform-dir",
            default="terraform",
            help="Terraform working directory (default: terraform)"
        )
        parser.add_argument(
            "--run-dir",
            default=".mays-installer/runs",
            help="Base directory for run artifacts (default: .mays-installer/runs)"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="Run in dry-run mode (default: True)"
        )

        # H2: Deployment identity and versioning
        parser.add_argument(
            "--deployment-version",
            default=os.environ.get("DEPLOYMENT_VERSION", "0.1.0"),
            help="Deployment semantic version (default: 0.1.0)"
        )
        parser.add_argument(
            "--development-phase",
            default=os.environ.get("DEVELOPMENT_PHASE", "H2"),
            help="Development phase (e.g., H2, D8) (default: H2)"
        )
        parser.add_argument(
            "--development-step",
            type=int,
            default=int(os.environ.get("DEVELOPMENT_STEP", "0")),
            help="Development step number (default: 0)"
        )
        parser.add_argument(
            "--development-status",
            default=os.environ.get("DEVELOPMENT_STATUS", "development"),
            choices=["development", "testing", "staging", "production", "archived"],
            help="Development status (default: development)"
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # validate command
        validate_parser = subparsers.add_parser(
            "validate",
            help="Run validation checks"
        )
        validate_parser.add_argument(
            "--output",
            choices=["json", "text"],
            default="text",
            help="Output format (default: text)"
        )

        # plan command
        plan_parser = subparsers.add_parser(
            "plan",
            help="Generate Terraform deployment plan"
        )
        plan_parser.add_argument(
            "--out",
            default="deploy.tfplan",
            help="Output plan file (default: deploy.tfplan)"
        )
        plan_parser.add_argument(
            "--var-file",
            help="Path to .tfvars file"
        )
        plan_parser.add_argument(
            "--var",
            action="append",
            help="Set variable (can be used multiple times)"
        )
        plan_parser.add_argument(
            "--destroy",
            action="store_true",
            help="Generate destroy plan instead of deploy plan"
        )
        plan_parser.add_argument(
            "--no-policy-check",
            action="store_true",
            help="Skip policy gate check"
        )

        # destroy-plan command (alias for plan --destroy)
        destroy_parser = subparsers.add_parser(
            "plan-destroy",
            help="Generate destroy plan"
        )
        destroy_parser.add_argument(
            "--out",
            default="destroy.tfplan",
            help="Output destroy plan file (default: destroy.tfplan)"
        )
        destroy_parser.add_argument(
            "--var-file",
            help="Path to .tfvars file"
        )
        destroy_parser.add_argument(
            "--var",
            action="append",
            help="Set variable (can be used multiple times)"
        )

        # deploy command
        deploy_parser = subparsers.add_parser(
            "deploy",
            help="Apply a saved deployment plan"
        )
        deploy_parser.add_argument(
            "--plan",
            default=None,
            help="Plan file to apply (default: auto-detect latest from .mays-installer/runs)"
        )
        deploy_parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            help="Skip approval prompt (use with caution)"
        )

        # destroy command
        destroy_parser = subparsers.add_parser(
            "destroy",
            help="Apply a saved destroy plan"
        )
        destroy_parser.add_argument(
            "--plan",
            default=None,
            help="Destroy plan file to apply (default: auto-detect latest from .mays-installer/runs)"
        )
        destroy_parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            help="Skip approval prompt (use with caution)"
        )

        # state command
        state_parser = subparsers.add_parser(
            "state",
            help="Manage Terraform state"
        )
        state_subparsers = state_parser.add_subparsers(dest="state_command", help="State commands")

        # state list
        state_list_parser = state_subparsers.add_parser(
            "list",
            help="List resources in state"
        )
        state_list_parser.add_argument(
            "--state-file",
            help="Path to state file"
        )

        # state show
        state_show_parser = state_subparsers.add_parser(
            "show",
            help="Show a resource in state"
        )
        state_show_parser.add_argument(
            "address",
            help="Resource address"
        )
        state_show_parser.add_argument(
            "--state-file",
            help="Path to state file"
        )

        # state pull
        state_pull_parser = state_subparsers.add_parser(
            "pull",
            help="Pull current state"
        )

        # state push
        state_push_parser = state_subparsers.add_parser(
            "push",
            help="Push state to remote"
        )
        state_push_parser.add_argument(
            "state_file",
            help="Path to state file"
        )

        # output command
        output_parser = subparsers.add_parser(
            "output",
            help="Show output values"
        )
        output_parser.add_argument(
            "name",
            nargs="?",
            help="Output name"
        )
        output_parser.add_argument(
            "--state-file",
            help="Path to state file"
        )

        # identity command
        identity_parser = subparsers.add_parser(
            "identity",
            help="Show AWS identity information"
        )
        identity_parser.add_argument(
            "--profile",
            default=os.environ.get("AWS_PROFILE"),
            help="AWS CLI profile"
        )
        identity_parser.add_argument(
            "--region",
            default=os.environ.get("AWS_REGION", "eu-central-1"),
            help="AWS region"
        )

        # gui command
        gui_parser = subparsers.add_parser(
            "gui",
            help="Launch the Shell GUI (read-only terminal interface)"
        )
        gui_parser.add_argument(
            "--no-clear",
            action="store_true",
            help="Don't clear screen on each menu refresh"
        )

        return parser

    def run(self, args: Optional[list] = None) -> int:
        """Run the CLI."""
        parsed = self.parser.parse_args(args)

        if not parsed.command:
            self.parser.print_help()
            return 1

        # Create context
        context = self._create_context(parsed)

        # Create run directory manager
        run_manager = RunDirectoryManager()
        run_dir = run_manager.create_run_dir(context.run_id)
        context.run_dir = str(run_dir)

        # Save context
        run_manager.save_context(run_dir, context)

        # Route to command
        if parsed.command == "validate":
            return self._cmd_validate(context, parsed, run_dir)
        elif parsed.command == "plan":
            return self._cmd_plan(context, parsed, run_dir)
        elif parsed.command == "plan-destroy":
            return self._cmd_plan_destroy(context, parsed, run_dir)
        elif parsed.command == "deploy":
            return self._cmd_deploy(context, parsed, run_dir)
        elif parsed.command == "destroy":
            return self._cmd_destroy(context, parsed, run_dir)
        elif parsed.command == "state":
            return self._cmd_state(context, parsed, run_dir)
        elif parsed.command == "output":
            return self._cmd_output(context, parsed, run_dir)
        elif parsed.command == "identity":
            return self._cmd_identity(context, parsed, run_dir)
        elif parsed.command == "gui":
            return self._cmd_gui(context, parsed, run_dir)

        return 1

    def _create_context(self, parsed) -> "InstallationContext":
        """Create InstallationContext from parsed arguments."""
        from installer.core.context import InstallationContext
        context = InstallationContext.from_env()
        context.aws_profile = parsed.profile
        context.aws_region = parsed.aws_region
        context.project_name = parsed.project_name
        context.environment = parsed.environment
        context.terraform_dir = parsed.terraform_dir
        context.run_dir = parsed.run_dir
        context.dry_run = parsed.dry_run

        # H2: Deployment identity and versioning
        context.deployment_version = getattr(parsed, 'deployment_version', '0.1.0')
        context.development_phase = getattr(parsed, 'development_phase', 'H2')
        context.development_step = getattr(parsed, 'development_step', 0)
        context.development_status = getattr(parsed, 'development_status', 'development')
        return context

    def _cmd_validate(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Run validation checks."""
        print(f"Running validation checks for {context.project_name}...")
        print(f"Profile: {context.aws_profile}, Region: {context.aws_region}")
        print(f"Environment: {context.environment}")
        print(f"Run directory: {run_dir}")

        # Run validation
        validation = ValidationLayer(context)
        result = validation.run_all()

        # Save validation result
        run_manager = RunDirectoryManager()
        run_manager.save_validation_result(run_dir, result)

        # Output results
        if parsed.output == "json":
            print(result.to_json())
        else:
            print(f"\n{result.summary()}")
            print(f"\nDetails:")
            for check in result.checks:
                status_icon = {
                    "PASS": "✓",
                    "FAIL": "✗",
                    "WARNING": "⚠",
                    "SKIP": "○"
                }.get(check.status, "?")
                print(f"  {status_icon} {check.name}: {check.message}")
                if check.details:
                    for k, v in check.details.items():
                        print(f"    {k}: {v}")

                if result.errors:
                    print(f"\nErrors:")
                    for err in result.errors:
                        print(f"  ✗ {err}")

                if result.warnings:
                    print(f"\nWarnings:")
                    for warn in result.warnings:
                        print(f"  ⚠ {warn}")

        return 0 if not result.has_errors() else 1

    def _cmd_plan(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Generate deployment plan with H2 plan identity."""
        print(f"Generating deployment plan...")
        print(f"Profile: {context.aws_profile}, Region: {context.aws_region}")
        print(f"Environment: {context.environment}")
        print(f"Project: {context.project_name}")
        print(f"Deployment Version: {context.deployment_version}")
        print(f"Development Phase: {context.development_phase}{context.development_step if context.development_step > 0 else ''}")
        print(f"Development Status: {context.development_status}")
        print(f"Run directory: {run_dir}")

        # Run validation first
        print("\nRunning pre-flight validation...")
        validation = ValidationLayer(context)
        validation_result = ValidationLayer(context).run_all()

        if validation_result.has_errors():
            print("Validation failed. Cannot proceed with plan.")
            return 1

        # Save validation
        run_manager = RunDirectoryManager()
        run_manager.save_validation_result(run_dir, validation_result)

        # Run terraform init
        print("\nRunning terraform init...")

        # Validate AWS context first
        if not context.validate_aws_context():
            print("AWS context validation failed. Cannot proceed with plan.")
            return 1

        runner = TerraformRunner(context.terraform_dir, context.aws_execution_context)

        # Check if backend should be configured
        init_result = runner.init(backend=not context.dry_run)
        if not init_result.success:
            print(f"Terraform init failed: {init_result.stderr}")
            return 1
        print("Terraform init successful")

        # Run terraform validate
        print("\nRunning terraform validate...")
        validate_result = runner.validate()
        if not validate_result.success:
            print(f"Terraform validate failed: {validate_result.stderr}")
            return 1
        print("Terraform validate passed")

        # H2: Get deployment context for plan identity
        deployment_context = context.get_deployment_context()
        operation = PlanOperation.DESTROY if parsed.destroy else PlanOperation.DEPLOY

        # Get next sequence number
        sequence_manager = PlanSequenceManager()
        sequence_number = sequence_manager.get_next_sequence(deployment_context.deployment_id, operation)

        # Create plan metadata
        plan_metadata = PlanMetadata(
            deployment_id=deployment_context.deployment_id,
            version=deployment_context.version,
            development_phase=deployment_context.development_state.phase,
            operation=operation,
            sequence_number=sequence_number,
            git_commit=deployment_context.installer_commit
        )

        # Generate H2 plan filename
        out_filename = plan_metadata.to_filename()
        print(f"\nGenerating plan: {out_filename}")

        original_cwd = os.getcwd()
        try:
            os.chdir(context.terraform_dir)
            if parsed.destroy:
                plan_result = runner.plan_destroy(out_file=out_filename)
                mode = "destroy"
            else:
                # Parse variables
                var = {}
                if parsed.var:
                    for v in parsed.var:
                        if "=" in v:
                            k, v_val = v.split("=", 1)
                            var[k] = v_val

                plan_result = runner.plan(
                    out_file=out_filename,
                    var=var if var else None,
                    var_file=parsed.var_file if hasattr(parsed, 'var_file') and parsed.var_file else None
                )
                mode = "deploy"
        finally:
            os.chdir(original_cwd)

        if not plan_result.success:
            print(f"Terraform plan failed: {plan_result.stderr}")
            return 1

        print("Plan generated successfully")

        # Save plan artifacts with H2 metadata
        plan_file_in_terraform = Path(context.terraform_dir) / out_filename
        run_manager = RunDirectoryManager()
        run_manager.save_plan_file(run_dir, str(Path(context.terraform_dir) / out_filename), "destroy" if parsed.destroy else "deploy")

        # Save plan metadata alongside plan file
        plan_metadata_path = run_dir / "plans" / f"{out_filename}.meta.json"
        plan_metadata_path.write_text(plan_metadata.to_json())

        # Also save deployment context for reference
        deployment_context = context.get_deployment_context()
        deployment_context_path = run_dir / "plans" / f"{out_filename}.context.json"
        deployment_context_path.write_text(deployment_context.to_json())

        from installer.run.manager import PlanArtifactManager
        PlanArtifactManager.save_plan_safely(
            str(Path(context.terraform_dir) / out_filename),
            Path(f".mays-installer/runs/{datetime.now().strftime('%Y%m%d-%H%M%S')}/plans/{out_filename}"),
            sanitize=False  # Skip sanitization to avoid provider initialization
        )

        # Print summary using plan_result directly
        run_plan_path = run_dir / "plans" / out_filename
        cmd = "destroy" if parsed.destroy else "deploy"
        print(f"\nPlan Summary:")
        print(f"  Plan file: {out_filename}")
        print(f"  Plan metadata: {plan_metadata_path.name}")
        print(f"  {cmd.capitalize()} with: ./Mays-Order-AWS-installer {cmd} --plan {run_plan_path}")
        print(f"  Status: Generated successfully")

        return 0

    def _cmd_plan_destroy(self, context, parsed, run_dir) -> int:
        """Generate destroy plan."""
        # Reuse plan command with destroy flag
        parsed.destroy = True
        if not hasattr(parsed, 'out') or parsed.out == "deploy.tfplan":
            parsed.out = "destroy.tfplan"
        return self._cmd_plan(context, parsed, run_dir)

    def _cmd_deploy(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Apply a saved deployment plan with H2 deployment identity validation."""
        print(f"Deploying plan: {parsed.plan if parsed.plan else 'auto-detect'}")
        print(f"Profile: {context.aws_profile}, Region: {context.aws_region}")
        print(f"Environment: {context.environment}")
        print(f"Project: {context.project_name}")
        print(f"Deployment Version: {context.deployment_version}")
        print(f"Development Phase: {context.development_phase}{context.development_step if context.development_step > 0 else ''}")
        print(f"Development Status: {context.development_status}")
        print(f"Run directory: {run_dir}")
        print(f"Dry-run mode: {context.dry_run}")
        print(f"Allow AWS operations: {context.allow_aws_operations}")

        # Validate AWS context
        if not context.validate_aws_context():
            print("AWS context validation failed. Cannot proceed with deployment.")
            return 1

        # Enforce allow_aws_operations for mutations
        if not context.allow_aws_operations:
            print("ERROR: AWS operations not allowed. Set ALLOW_AWS_OPERATIONS=true to enable mutations.")
            return 1

        # Get deployment context for identity validation
        deployment_context = context.get_deployment_context()

        # Auto-detect latest deploy plan if not provided - using H2 PlanDiscovery
        if parsed.plan is None:
            plan_discovery = PlanDiscovery()
            latest_plan = plan_discovery.find_latest_plan(
                deployment_id=deployment_context.deployment_id,
                operation=PlanOperation.DEPLOY,
                version=deployment_context.version,
                development_phase=deployment_context.development_state.phase
            )
            if latest_plan:
                parsed.plan = str(latest_plan.file_path)
                print(f"Auto-detected latest deploy plan: {parsed.plan}")
                print(f"  Plan metadata: {latest_plan.metadata.to_json()}")
            else:
                print("No matching deploy plan found in .mays-installer/runs/*/plans/")
                print(f"  Filter: deployment_id={deployment_context.deployment_id}, version={deployment_context.version}, phase={deployment_context.development_state.phase}")
                print("Run './Mays-Order-AWS-installer plan' first to generate a plan.")
                return 1

        # Check if plan file exists
        plan_file = Path(parsed.plan)
        if not plan_file.is_absolute():
            plan_file = Path(".") / parsed.plan

        # Validate plan matches deployment identity BEFORE copying
        plan_discovery = PlanDiscovery()
        is_valid, error_msg = plan_discovery.validate_plan_context(plan_file, deployment_context.deployment_id)
        if not is_valid:
            print(f"Plan validation failed: {error_msg}")
            print("ERROR: --yes cannot bypass deployment identity mismatch.")
            return 1

        # If plan is in run directory, copy to terraform/ for relative path resolution
        if ".mays-installer/runs/" in str(plan_file) and plan_file.exists():
            import shutil
            terraform_plan = Path(context.terraform_dir) / plan_file.name
            shutil.copy2(plan_file, terraform_plan)
            plan_file = terraform_plan
            print(f"Plan copied to {terraform_plan} for terraform execution")

        if not plan_file.exists():
            print(f"Plan file not found: {plan_file}")
            return 1

        # Plan integrity check (includes AWS context matching)
        run_manager = RunDirectoryManager()
        runner = TerraformRunner(context.terraform_dir, context.aws_execution_context)

        # Use resolved plan_file path for verification
        plan_path = str(plan_file)
        if context.terraform_dir in plan_path:
            terraform_plan_file = Path(plan_path).name
        else:
            terraform_plan_file = plan_path

        # Verify plan integrity
        is_valid, error_msg = runner.verify_plan_integrity(terraform_plan_file, context.run_id)
        if not is_valid:
            print(f"Plan integrity check failed: {error_msg}")
            return 1

        # Verify plan matches current AWS execution context
        is_valid, error_msg = runner.verify_plan_context_match(terraform_plan_file, context.aws_execution_context)
        if not is_valid:
            print(f"Plan context mismatch: {error_msg}")
            return 1

        # H2: Verify plan metadata matches deployment context
        plan_discovery = PlanDiscovery()
        meta = PlanMetadata.parse_filename(plan_file.name)
        if meta:
            if not meta.matches_deployment(deployment_context.deployment_id):
                print(f"ERROR: Plan deployment ID mismatch!")
                print(f"  Expected: {deployment_context.deployment_id}")
                print(f"  Plan:     {meta.deployment_id}")
                print("ERROR: --yes cannot bypass deployment identity mismatch.")
                return 1

            if meta.operation != PlanOperation.DEPLOY:
                print(f"ERROR: Plan operation mismatch! Expected deploy, got {meta.operation.value}")
                print("ERROR: --yes cannot bypass operation mismatch.")
                return 1

            if meta.version != deployment_context.version:
                print(f"WARNING: Plan version mismatch!")
                print(f"  Context: {deployment_context.version}")
                print(f"  Plan:    {meta.version}")
                # Don't block, just warn

            if meta.development_phase != deployment_context.development_state.phase:
                print(f"WARNING: Plan development phase mismatch!")
                print(f"  Context: {deployment_context.development_state.phase}")
                print(f"  Plan:    {meta.development_phase}")
                # Don't block, just warn
        else:
            print(f"WARNING: Could not parse plan metadata from filename: {plan_file.name}")
            print("Proceeding with basic validation only.")

        # Display plan summary before approval

        # Verify plan matches current AWS execution context
        is_valid, error_msg = runner.verify_plan_context_match(terraform_plan_file, context.aws_execution_context)
        if not is_valid:
            print(f"Plan context mismatch: {error_msg}")
            return 1

        # Display plan summary before approval
        print(f"\n=== DEPLOYMENT APPROVAL ===")
        print(f"Profile: {context.aws_profile}")
        print(f"Account: {context.aws_execution_context.account_id}")
        print(f"Region: {context.aws_region}")
        print(f"Environment: {context.environment}")
        print(f"Plan file: {parsed.plan}")
        print(f"Run ID: {context.run_id}")
        print()

        # Show plan summary
        runner_dummy = TerraformRunner(context.terraform_dir, context.aws_execution_context)
        plan_json_result = runner_dummy.show_plan(terraform_plan_file)
        if plan_json_result.success:
            import json
            plan_json = json.loads(plan_json_result.stdout)
            plan_summary = PlanResult.from_plan_json(plan_json, parsed.plan, "deploy")
            print(f"Plan: {plan_summary.add} to add, {plan_summary.change} to change, {plan_summary.destroy} to destroy, {plan_summary.replace} to replace")
        else:
            print("Plan summary: (could not parse plan details)")

        print()
        if plan_json_result.success:
            import json
            plan_json = json.loads(plan_json_result.stdout)
            plan_summary = PlanResult.from_plan_json(plan_json, parsed.plan, "deploy")
            safety = evaluate_plan_safety(plan_summary, mode="deploy")
            print(f"Safety Analysis: {safety['status']}")
            for check in safety.get("checks", []):
                status_icon = {"PASS": "✓", "WARNING": "⚠", "BLOCKED": "✗"}.get(check["status"], "?")
                print(f"  {status_icon} {check['name']}: {check['message']}")

            if safety["status"] == "BLOCKED":
                print("\n⚠ Plan blocked by safety policy")
                return 1

        # Policy gate check (skip in dry-run mode since providers aren't initialized)
        if not context.dry_run:
            print("\nRunning policy gate check...")
            import subprocess
            import tempfile
            import json

            # Get plan JSON using terraform show -json
            plan_json_result = TerraformRunner(context.terraform_dir, context.aws_execution_context).show_plan(terraform_plan_file)

            if not plan_json_result.success:
                print(f"Warning: Could not get plan JSON for policy gate: {plan_json_result.stderr}")
                print("Skipping policy gate check (plan may be stale or providers not initialized)")
            else:
                # Save plan JSON to temp file for policy gate
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
                    json.dump(json.loads(plan_json_result.stdout), tf)
                    plan_json_path = tf.name

                try:
                    policy_result = subprocess.run([
                        "python3", "terraform/policy/validate-plan.py", plan_json_path
                    ], capture_output=True, text=True, cwd=".", timeout=60)

                    if policy_result.returncode != 0:
                        print(f"Policy gate FAILED:")
                        print(policy_result.stdout)
                        print(policy_result.stderr)
                        print("\n⚠ Deployment blocked by policy gate")
                        return 1
                    else:
                        print("Policy gate PASSED")
                finally:
                    import os
                    try:
                        os.unlink(plan_json_path)
                    except:
                        pass
        else:
            print("\nSkipping policy gate check (dry-run mode)")

        # Approval gate
        if not parsed.yes:
            print()
            response = input("Proceed with deployment? [y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                print("Deployment cancelled.")
                return 0

        # Apply the plan
        print("\nApplying plan...")
        runner = TerraformRunner("terraform", context.aws_execution_context)
        apply_result = runner.apply(str(Path.cwd() / parsed.plan))

        if not apply_result.success:
            print(f"Deployment failed: {apply_result.stderr}")
            return 1

        print("Deployment successful!")

        # Post-apply verification
        print("\nRunning post-apply verification...")
        verify_result = runner.state_list()
        if verify_result.success:
            print("✓ Terraform state accessible")
        else:
            print("⚠ Could not verify Terraform state")

        # Verify AWS identity
        verify_identity = TerraformRunner("terraform", context.aws_execution_context).version()
        if verify_identity.success:
            print("✓ AWS identity verified")
        else:
            print("⚠ Could not verify AWS identity")

        print("\nDeployment completed successfully!")
        return 0

    def _cmd_plan_destroy(self, context, parsed, run_dir) -> int:
        """Generate destroy plan."""
        # Reuse plan command with destroy flag
        parsed.destroy = True
        if not hasattr(parsed, 'out') or parsed.out == "deploy.tfplan":
            parsed.out = "destroy.tfplan"
        return self._cmd_plan(context, parsed, run_dir)

    def _cmd_destroy(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Apply a saved destroy plan with H2 deployment identity validation."""
        print(f"Destroying with plan: {parsed.plan if parsed.plan else 'auto-detect'}")
        print(f"Profile: {context.aws_profile}, Region: {context.aws_region}")
        print(f"Environment: {context.environment}")
        print(f"Project: {context.project_name}")
        print(f"Deployment Version: {context.deployment_version}")
        print(f"Development Phase: {context.development_phase}{context.development_step if context.development_step > 0 else ''}")
        print(f"Development Status: {context.development_status}")
        print(f"Run directory: {run_dir}")
        print(f"Dry-run mode: {context.dry_run}")
        print(f"Allow AWS operations: {context.allow_aws_operations}")

        # Validate AWS context
        if not context.validate_aws_context():
            print("AWS context validation failed. Cannot proceed with destruction.")
            return 1

        # Enforce allow_aws_operations for mutations
        if not context.allow_aws_operations:
            print("ERROR: AWS operations not allowed. Set ALLOW_AWS_OPERATIONS=true to enable mutations.")
            return 1

        # Get deployment context for identity validation
        deployment_context = context.get_deployment_context()

        # Auto-detect latest destroy plan if not provided - using H2 PlanDiscovery
        if parsed.plan is None:
            plan_discovery = PlanDiscovery()
            latest_plan = plan_discovery.find_latest_plan(
                deployment_id=deployment_context.deployment_id,
                operation=PlanOperation.DESTROY,
                version=deployment_context.version,
                development_phase=deployment_context.development_state.phase
            )
            if latest_plan:
                parsed.plan = str(latest_plan.file_path)
                print(f"Auto-detected latest destroy plan: {parsed.plan}")
                print(f"  Plan metadata: {latest_plan.metadata.to_json()}")
            else:
                print("No matching destroy plan found in .mays-installer/runs/*/plans/")
                print(f"  Filter: deployment_id={deployment_context.deployment_id}, version={deployment_context.version}, phase={deployment_context.development_state.phase}")
                print("Run './Mays-Order-AWS-installer plan-destroy' first to generate a destroy plan.")
                return 1

        # Check if plan file exists
        plan_file = Path(parsed.plan)
        if not plan_file.is_absolute():
            plan_file = Path(".") / parsed.plan

        # Validate plan matches deployment identity BEFORE copying
        plan_discovery = PlanDiscovery()
        is_valid, error_msg = plan_discovery.validate_plan_context(plan_file, deployment_context.deployment_id)
        if not is_valid:
            print(f"Plan validation failed: {error_msg}")
            print("ERROR: --yes cannot bypass deployment identity mismatch.")
            return 1

        # If plan is in run directory, copy to terraform/ for relative path resolution
        if ".mays-installer/runs/" in str(plan_file) and plan_file.exists():
            import shutil
            terraform_plan = Path(context.terraform_dir) / plan_file.name
            shutil.copy2(plan_file, terraform_plan)
            plan_file = terraform_plan
            print(f"Plan copied to {terraform_plan} for terraform execution")

        if not plan_file.exists():
            print(f"Destroy plan file not found: {plan_file}")
            return 1

        # Plan integrity check (includes AWS context matching)
        run_manager = RunDirectoryManager()
        runner = TerraformRunner(context.terraform_dir, context.aws_execution_context)

        # Use resolved plan_file path for verification
        plan_path = str(plan_file)
        if context.terraform_dir in plan_path:
            terraform_plan_file = Path(plan_path).name
        else:
            terraform_plan_file = plan_path

        # Verify plan integrity
        is_valid, error_msg = runner.verify_plan_integrity(terraform_plan_file, context.run_id)
        if not is_valid:
            print(f"Destroy plan integrity check failed: {error_msg}")
            return 1

        # Verify plan matches current AWS execution context
        is_valid, error_msg = runner.verify_plan_context_match(terraform_plan_file, context.aws_execution_context)
        if not is_valid:
            print(f"Plan context mismatch: {error_msg}")
            return 1

        # H2: Verify plan metadata matches deployment context
        plan_discovery = PlanDiscovery()
        meta = PlanMetadata.parse_filename(plan_file.name)
        if meta:
            if not meta.matches_deployment(deployment_context.deployment_id):
                print(f"ERROR: Plan deployment ID mismatch!")
                print(f"  Expected: {deployment_context.deployment_id}")
                print(f"  Plan:     {meta.deployment_id}")
                print("ERROR: --yes cannot bypass deployment identity mismatch.")
                return 1

            if meta.operation != PlanOperation.DESTROY:
                print(f"ERROR: Plan operation mismatch! Expected destroy, got {meta.operation.value}")
                print("ERROR: --yes cannot bypass operation mismatch.")
                return 1

            if meta.version != deployment_context.version:
                print(f"WARNING: Plan version mismatch!")
                print(f"  Context: {deployment_context.version}")
                print(f"  Plan:    {meta.version}")
                # Don't block, just warn

            if meta.development_phase != deployment_context.development_state.phase:
                print(f"WARNING: Plan development phase mismatch!")
                print(f"  Context: {deployment_context.development_state.phase}")
                print(f"  Plan:    {meta.development_phase}")
                # Don't block, just warn
        else:
            print(f"WARNING: Could not parse plan metadata from filename: {plan_file.name}")
            print("Proceeding with basic validation only.")

        # Display destroy plan summary before approval
        print(f"\n=== DESTROY APPROVAL ===")
        print(f"Profile: {context.aws_profile}")
        print(f"Account: {context.aws_execution_context.account_id}")
        print(f"Region: {context.aws_region}")
        print(f"Environment: {context.environment}")
        print(f"Plan file: {plan_path}")
        print(f"Run ID: {context.run_id}")
        print()

        # Show destroy plan summary
        runner_dummy = TerraformRunner(context.terraform_dir, context.aws_execution_context)
        plan_json_result = runner_dummy.show_plan(terraform_plan_file)
        if plan_json_result.success:
            import json
            plan_json = json.loads(plan_json_result.stdout)
            plan_summary = PlanResult.from_plan_json(plan_json, parsed.plan, "destroy")
            print(f"Destroy Plan: {plan_summary.add} to add, {plan_summary.change} to change, {plan_summary.destroy} to destroy, {plan_summary.replace} to replace")
        else:
            print("Destroy plan summary: (could not parse plan details)")

        print()

        # Safety evaluation
        plan_json_result = TerraformRunner(context.terraform_dir, context.aws_execution_context).show_plan(terraform_plan_file)
        if plan_json_result.success:
            import json
            plan_json = json.loads(plan_json_result.stdout)
            plan_summary = PlanResult.from_plan_json(plan_json, parsed.plan, "destroy")
            safety = evaluate_plan_safety(plan_summary, mode="destroy")
            print(f"Safety Analysis: {safety['status']}")
            for check in safety.get("checks", []):
                status_icon = {"PASS": "✓", "WARNING": "⚠", "BLOCKED": "✗"}.get(check["status"], "?")
                print(f"  {status_icon} {check['name']}: {check['message']}")

            if safety["status"] == "BLOCKED":
                print("\n⚠ Destroy plan blocked by safety policy")
                return 1

        # Approval gate
        if not parsed.yes:
            print()
            response = input("Proceed with DESTRUCTION? [y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                print("Destruction cancelled.")
                return 0

        # Apply the destroy plan
        print("\nApplying destroy plan...")
        runner = TerraformRunner("terraform", context.aws_execution_context)
        destroy_result = runner.destroy(str(Path.cwd() / parsed.plan))

        if not destroy_result.success:
            print(f"Destruction failed: {destroy_result.stderr}")
            return 1

        print("Destruction successful!")

        # Post-destroy verification
        print("\nRunning post-destroy verification...")
        verify_result = runner.state_list()
        if verify_result.success:
            print("✓ Terraform state accessible")
        else:
            print("⚠ Could not verify Terraform state")

        print("\nDestruction completed successfully!")
        return 0

    def _cmd_state(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Manage Terraform state."""
        # Validate AWS context first
        if not context.validate_aws_context():
            print("AWS context validation failed. Cannot proceed with state operations.")
            return 1

        runner = TerraformRunner(context.terraform_dir, context.aws_execution_context)

        if parsed.state_command == "list":
            result = runner.state_list(parsed.state_file)
            if result.success:
                print(result.stdout)
            else:
                print(f"Error: {result.stderr}")
                return 1

        elif parsed.state_command == "show":
            if not parsed.address:
                print("Error: address is required for state show")
                return 1
            result = runner.state_show(parsed.address, parsed.state_file)
            if result.success:
                print(result.stdout)
            else:
                print(f"Error: {result.stderr}")
                return 1

        elif parsed.state_command == "pull":
            result = runner.state_pull()
            if result.success:
                print(result.stdout)
            else:
                print(f"Error: {result.stderr}")
                return 1

        elif parsed.state_command == "push":
            # state push is a mutating operation - requires allow_aws_operations
            if not context.allow_aws_operations:
                print("ERROR: AWS operations not allowed. Set ALLOW_AWS_OPERATIONS=true to enable state push.")
                return 1
            if not parsed.state_file:
                print("Error: state-file is required for state push")
                return 1
            result = runner.state_push(parsed.state_file)
            if result.success:
                print("State pushed successfully")
            else:
                print(f"Error: {result.stderr}")
                return 1

        else:
            print(f"Unknown state command: {parsed.state_command}")
            return 1

        return 0

    def _cmd_output(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Show output values."""
        # Validate AWS context first
        if not context.validate_aws_context():
            print("AWS context validation failed. Cannot proceed with output operations.")
            return 1

        runner = TerraformRunner(context.terraform_dir, context.aws_execution_context)
        result = runner.output(parsed.name, parsed.state_file)
        if result.success:
            print(result.stdout)
        else:
            print(f"Error: {result.stderr}")
            return 1
        return 0
    def _cmd_identity(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Show AWS identity information."""
        # Validate AWS context first
        if not context.validate_aws_context():
            print("AWS context validation failed. Cannot proceed.")
            return 1

        runner = TerraformRunner("terraform", context.aws_execution_context)
        result = runner.version()
        if result.success:
            import json
            version_info = json.loads(result.stdout)
            print("Terraform Version: {}".format(version_info.get("terraform_version", "unknown")))

        # Show AWS identity using validated context
        aws_ctx = context.aws_execution_context
        if aws_ctx:
            print("Account: {}".format(aws_ctx.account_id))
            print("User/Role ARN: {}".format(aws_ctx.identity_arn))
            # Get UserId via STS if needed
            import subprocess
            try:
                if context.aws_profile and context.aws_profile.strip():
                    cmd = ["aws", "sts", "get-caller-identity", "--profile", context.aws_profile]
                else:
                    cmd = ["aws", "sts", "get-caller-identity"]
                if context.aws_region:
                    cmd.extend(["--region", context.aws_region])
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    import json
                    identity = json.loads(result.stdout)
                    print("User ID: {}".format(identity.get("UserId")))
            except Exception:
                pass  # UserId is optional

        profile_display = context.aws_profile if context.aws_profile else "(default credential chain)"
        print("\nProfile: {}".format(profile_display))
        print("Region: {}".format(context.aws_region))
        print("Project: {}".format(context.project_name))
        print("Environment: {}".format(context.environment))
        return 0

        return 0

    def _cmd_gui(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Launch the Shell GUI (read-only terminal interface)."""
        from installer.cli.gui import ShellGUI

        # Create and run the GUI
        gui = ShellGUI(context)
        return gui.run()


def main():
    """Main entry point."""
    cli = InstallerCLI()
    return cli.run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
