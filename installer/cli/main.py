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


def build_plan_variables(context, parsed) -> dict:
    """Terraform `-var` values shared by deploy and destroy plans.

    MO-RC4-P02I-E1B: both plan kinds must carry the same project context.
    `project_name` is always injected (unless explicitly overridden via
    `--var`), so a missing parameter can never fall back to the Terraform
    default ("mays-orders") and address a foreign project namespace.
    """
    var = {}
    for raw in getattr(parsed, "var", None) or []:
        if "=" in raw:
            key, value = raw.split("=", 1)
            var[key] = value

    if "project_name" not in var:
        var["project_name"] = context.project_name

    # MO-P0B: Zielversion im State dokumentieren (Output mo_version).
    var.setdefault("deployment_version", context.deployment_version)

    # MO-RC4-P02I-E2B: Recovery-Schedules bleiben fuer den ersten RC4-Plan
    # aus. Die Defaults werden explizit gesetzt (statt sich auf Terraform-
    # Defaults zu verlassen); ein bewusstes --var ...=true gewinnt.
    for flag in ("recovery_enabled", "processing_recovery_enabled"):
        var.setdefault(flag, "false")

    notification_email = getattr(parsed, "notification_email", None)
    if notification_email and "notification_email" not in var:
        var["notification_email"] = notification_email

    return var


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
                  Mays-Order-AWS-installer --guide
            """)
        )

        # Global options
        parser.add_argument(
            "--profile",
            default=os.environ.get("AWS_PROFILE"),
            help="AWS CLI profile (default: from AWS_PROFILE env var)"
        )
        parser.add_argument(
            "--region",
            default=os.environ.get("AWS_REGION", "eu-central-1"),
            help="AWS region (default: eu-central-1)"
        )
        parser.add_argument(
            "--project-name",
            default=None,
            help="Project name (default: $PROJECT_NAME or mays-orders). "
                 "Required explicitly for --remote plans."
        )
        parser.add_argument(
            "--aws-region",
            default=os.environ.get("AWS_REGION", "eu-central-1"),
            help="AWS region (default: eu-central-1)"
        )
        parser.add_argument(
            "--environment",
            default=None,
            help="Environment (default: $ENVIRONMENT or Development). "
                 "Required explicitly for --remote plans."
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
            default=False,
            help="Run in dry-run mode (default: False)"
        )
        parser.add_argument(
            "--allow-dirty-source",
            action="store_true",
            default=False,
            help="Allow remote plans/applies from a dirty tracked working tree "
                 "(documented in the manifest; default: block)."
        )
        parser.add_argument(
            "--allow-legacy-source",
            action="store_true",
            default=False,
            help="Allow applying an upgrade plan whose installed source version is "
                 "LEGACY_UNKNOWN (default: block; no version is assumed)."
        )
        parser.add_argument(
            "--accept-upgrade-review",
            action="store_true",
            default=False,
            help="Explicitly accept REVIEW_REQUIRED upgrade changes after manual "
                 "review (compatibility/classification). Default: block."
        )
        parser.add_argument(
            "--notification-email",
            default=None,
            help="Optional email for Cognito backup SNS notifications"
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
        # Documentation pointer: prints guide location + TOC, then exits
        parser.add_argument(
            "--guide",
            action="store_true",
            default=False,
            help="Show the Installer Guide (docs/INSTALLER_GUIDE.md) path and table of contents, then exit"
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
            default=None,
            help="Plan artifact path (file with identity filename or directory). "
                 "Required for --remote plans."
        )
        plan_parser.add_argument(
            "--remote",
            action="store_true",
            default=False,
            help="Controlled remote plan: uses the configured S3 backend and the "
                 "project workspace, stores a verifiable artifact, never applies."
        )
        plan_parser.add_argument(
            "--upgrade",
            action="store_true",
            default=False,
            help="Explicit upgrade mode: requires an existing remote installation, "
                 "evaluates version compatibility and writes an upgrade readiness "
                 "report. Never applies."
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
        # Policy-Gate-Hinweis: Es gibt absichtlich KEIN Flag zum Überspringen
        # des Gates (das historische --no-policy-check war nie konsumiert und
        # wurde entfernt — MAYS-ORDERS-MODULE-BUILDER-CLI-CLEANUP-01). Der
        # Deploy-Gate in _cmd_deploy läuft bedingungslos; FAIL blockiert vor
        # dem menschlichen Approval.

        # destroy-plan command (alias for plan --destroy)
        destroy_parser = subparsers.add_parser(
            "plan-destroy",
            help="Generate destroy plan"
        )
        destroy_parser.add_argument(
            "--out",
            default=None,
            help="Destroy plan artifact path (file with identity filename or directory). "
                 "Required for --remote plans."
        )
        destroy_parser.add_argument(
            "--remote",
            action="store_true",
            default=False,
            help="Controlled remote destroy plan: uses the configured S3 backend and "
                 "the project workspace, stores a verifiable artifact, never applies."
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
        # NOTE: defaults are SUPPRESS so identity-level flags do not clobber
        # the global --profile/--region when the user passes them globally.
        identity_parser.add_argument(
            "--profile",
            default=argparse.SUPPRESS,
            help="AWS CLI profile"
        )
        identity_parser.add_argument(
            "--region",
            default=argparse.SUPPRESS,
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
        # MO-RC4-P02I-E2B: merken, ob --out ausdruecklich gesetzt wurde
        # (Default ist None; ein Remote-Plan verlangt einen expliziten Pfad).
        parsed._out_explicit = getattr(parsed, "out", None) is not None

        if getattr(parsed, "guide", False):
            from installer.cli.guide import render_guide_info
            print(render_guide_info())
            return 0

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
        import os
        from installer.core.context import InstallationContext
        context = InstallationContext.from_env()
        context.aws_profile = parsed.profile
        context.aws_region = parsed.aws_region

        # MO-RC4-P02I-E2B: Explizitheit von project_name/environment merken.
        # Ein Remote-Plan verlangt beide ausdruecklich; Defaults (Env oder
        # eingebaut) sind fuer den kontrollierten Plan nicht ausreichend.
        parsed._project_name_explicit = parsed.project_name is not None
        parsed._environment_explicit = parsed.environment is not None
        context.project_name = (
            parsed.project_name
            or os.environ.get("PROJECT_NAME")
            or context.project_name
        )
        context.environment = (
            parsed.environment
            or os.environ.get("ENVIRONMENT")
            or context.environment
        )
        context.terraform_dir = parsed.terraform_dir
        context.run_dir = parsed.run_dir
        context.dry_run = parsed.dry_run

        # H2: Deployment identity and versioning
        context.deployment_version = getattr(parsed, 'deployment_version', '0.1.0')
        context.development_phase = getattr(parsed, 'development_phase', 'H2')
        context.development_step = getattr(parsed, 'development_step', 0)
        context.development_status = getattr(parsed, 'development_status', 'development')

        # Ensure workspace is derived from final project_name, not from env init.
        # No global os.environ mutation: workspace travels on the context and
        # is passed explicitly to TerraformRunner.
        context.terraform_workspace = context.project_name

        return context

    @staticmethod
    def _make_runner(context, terraform_dir=None) -> "TerraformRunner":
        """Create TerraformRunner with explicit workspace (no env globals).

        MO-RC4-P02I-E1B: project-isolated deployments are fail-closed — the
        runner refuses the Terraform "default" workspace instead of silently
        operating on a shared state.
        """
        return TerraformRunner(
            terraform_dir if terraform_dir is not None else context.terraform_dir,
            context.aws_execution_context,
            workspace=context.terraform_workspace,
            require_explicit_workspace=True,
        )

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

        # MO-RC4-P02I-E2B: Controlled Remote Plan (expliziter Modus).
        remote = bool(getattr(parsed, "remote", False))
        upgrade = bool(getattr(parsed, "upgrade", False))
        if upgrade and not remote:
            print(
                "UPGRADE_REQUIRES_REMOTE: Ein Upgrade benoetigt einen Remote-Plan "
                "(State-Bezug). Bitte `plan --remote --upgrade` verwenden."
            )
            return 1
        backend_contract = None
        if remote:
            from installer.core.plan_contract import (
                BackendContractError,
                load_backend_contract,
                validate_remote_plan,
            )
            from installer.core.state_guard import (
                StateMigrationBlocked,
                assert_no_state_migration,
            )

            try:
                backend_contract = load_backend_contract(context.terraform_dir)
            except BackendContractError as exc:
                print(f"Remote plan blocked: {exc}")
                return 1

            contract_errors = validate_remote_plan(
                backend_contract,
                project_name=context.project_name,
                environment=context.environment,
                region=context.aws_region,
                workspace=context.terraform_workspace,
                project_name_explicit=bool(getattr(parsed, "_project_name_explicit", False)),
                environment_explicit=bool(getattr(parsed, "_environment_explicit", False)),
                output_explicit=bool(getattr(parsed, "_out_explicit", False)),
                operation="destroy" if parsed.destroy else "deploy",
            )
            if contract_errors:
                print("Remote plan blocked (preconditions not met):")
                for error in contract_errors:
                    print(f"  - {error}")
                return 1

            try:
                assert_no_state_migration(context.terraform_dir)
            except StateMigrationBlocked as exc:
                print(f"Remote plan blocked: {exc}")
                return 1

            print("Remote plan identity:")
            print(f"  Account:   {context.aws_execution_context.account_id}")
            print(f"  Region:    {context.aws_region}")
            print(f"  Project:   {context.project_name}")
            print(f"  Workspace: {context.terraform_workspace}")
            print(f"  Backend:   s3://{backend_contract.bucket}/"
                  f"{backend_contract.state_key(context.terraform_workspace)}")

        runner = self._make_runner(context)

        # Remote plan: the S3 backend is mandatory (no local-state fallback).
        init_result = runner.init(backend=True if remote else not context.dry_run)
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

        # MO-P0B: Quellcode-Identitaet fuer verbindliche Remote-Plaene.
        source_identity = None
        if remote:
            from installer.core.source_identity import resolve_source_identity
            from installer.core.version_binding import check_source_for_plan

            source_identity = resolve_source_identity()
            source_check = check_source_for_plan(
                source_identity,
                allow_dirty_source=bool(getattr(parsed, "allow_dirty_source", False)),
            )
            if not source_check.ok:
                print(source_check.message())
                return 1
            dirty_note = " (dirty)" if source_identity.dirty else ""
            print(f"Source: {source_identity.commit[:12]}{dirty_note}")

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

        # MO-RC4-P02I-E2B: expliziter Plan-Ausgabepfad (--out) mit erhaltener
        # Deployment-Identitaet im Dateinamen. Ohne --out bleibt es beim
        # kanonischen Namen im Terraform-Verzeichnis.
        from installer.core.plan_contract import PlanOutputError, resolve_plan_output

        try:
            plan_output = resolve_plan_output(
                context.terraform_dir,
                getattr(parsed, "out", None),
                out_filename,
                plan_metadata,
            )
        except PlanOutputError as exc:
            print(f"Plan output rejected: {exc}")
            return 1
        plan_output.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nGenerating plan: {plan_output}")

        original_cwd = os.getcwd()
        try:
            os.chdir(context.terraform_dir)
            # MO-RC4-P02I-E1B: deploy- und destroy-Plan teilen denselben
            # Projektkontext. Ohne explizites -var project_name wuerde Terraform
            # auf den Default ("mays-orders") zurueckfallen und damit einen
            # fremden Projekt-Namespace adressieren.
            var = build_plan_variables(context, parsed)
            var_file = getattr(parsed, "var_file", None) or None

            if parsed.destroy:
                plan_result = runner.plan_destroy(
                    out_file=str(plan_output),
                    var=var,
                    var_file=var_file,
                )
                mode = "destroy"
            else:
                plan_result = runner.plan(
                    out_file=str(plan_output),
                    var=var if var else None,
                    var_file=var_file,
                )
                mode = "deploy"
        finally:
            os.chdir(original_cwd)

        if not plan_result.success:
            print(f"Terraform plan failed: {plan_result.stderr}")
            return 1

        print("Plan generated successfully")

        # Save plan artifacts with H2 metadata
        plan_file_name = plan_output.name
        run_manager = RunDirectoryManager()
        saved_plan = run_manager.save_plan_file(
            run_dir, str(plan_output), "destroy" if parsed.destroy else "deploy"
        )

        # P0A-02: Upgrade-Safety-Gate bereits bei der Planerstellung.
        # Remote-Plaene werden weiter unten zusammen mit P0B/P0C bewertet;
        # Destroy-Plaene werden hier nicht bewertet (siehe _verify_destroy_plan).
        if not parsed.destroy and not remote:
            if not self._enforce_upgrade_safety(context, Path(saved_plan), run_dir):
                return 1

        # MO-P0B: installierte Ausgangsversion ermitteln (nur Remote-Plan).
        installed = None
        baseline = None
        drift_assessment = None
        compatibility = None
        readiness = None
        if remote:
            from installer.core.version_binding import UNREADABLE, detect_installed_version

            installed = detect_installed_version(runner)
            if installed.status == UNREADABLE:
                print(
                    "UPGRADE_STATE_UNREADABLE: Der installierte State ist nicht lesbar; "
                    "eine Neuinstallation darf nicht angenommen werden (fail-closed)."
                )
                return 1
            detail = f" {installed.version}" if installed.version else ""
            print(f"Installed version: {installed.status}{detail}")

            if upgrade:
                from installer.core.upgrade_mode import check_upgrade_source

                ok, code, message = check_upgrade_source(installed, remote=remote)
                if not ok:
                    print(message)
                    return 1
                print("Upgrade mode: existing installation detected")

                # P1B: Versionskompatibilitaet (fail-closed).
                from installer.core.compatibility import assess_compatibility

                compatibility = assess_compatibility(
                    installed.version if installed.status == "VERIFIED" else None,
                    context.deployment_version,
                    source_status=installed.status,
                )
                print(
                    f"Compatibility: {compatibility.status} "
                    f"({compatibility.reason})"
                )

            # MO-P0C: State-Baseline + Drift-/No-op-Bewertung.
            from installer.core.drift import (
                DRIFT_UNKNOWN,
                assess_plan,
                build_drift_report,
                write_drift_report,
            )
            from installer.core.plan_manifest import sha256_file
            from installer.core.state_baseline import capture_state_baseline
            from installer.core.upgrade_safety import (
                PROTECTED_RESOURCE_TYPES,
                analyze_plan,
            )

            baseline = capture_state_baseline(runner)
            if baseline.status == "UNREADABLE":
                print(
                    "UPGRADE_STATE_UNREADABLE: State-Baseline nicht ermittelbar "
                    "(fail-closed)."
                )
                return 1

            plan_json = self._load_plan_json(context, Path(saved_plan))
            if plan_json is None:
                return 1

            drift_assessment = assess_plan(
                plan_json, has_prior_state=(baseline.resources or 0) > 0
            )
            safety_assessment = analyze_plan(plan_json)

            # P1C: Change-Klassifikation (SAFE/REVIEW/CRITICAL).
            from installer.core.change_classification import classify_changes

            classification = classify_changes(
                safety_findings=[finding.to_dict() for finding in safety_assessment.findings],
                drift_status=drift_assessment.drift_status,
                drift_findings=drift_assessment.drift_findings,
                planned_changes=drift_assessment.planned_changes,
                noop_status=drift_assessment.noop_status,
                compatibility_status=(compatibility.status if compatibility else None),
                protected_types=PROTECTED_RESOURCE_TYPES,
            )

            blocking_reasons = []
            if drift_assessment.drift_status == DRIFT_UNKNOWN:
                blocking_reasons.append(
                    "UPGRADE_DRIFT_UNVERIFIED: Drift konnte nicht belastbar bewertet "
                    "werden (kein Refresh-Nachweis)."
                )
            protected_drift = [
                finding
                for finding in drift_assessment.drift_findings
                if finding.resource_type in PROTECTED_RESOURCE_TYPES
            ]
            if protected_drift:
                blocking_reasons.append(
                    "UPGRADE_BLOCKED_MIGRATION_REQUIRED: Drift an geschuetzten "
                    "Ressourcen: "
                    + ", ".join(f.address for f in protected_drift)
                )
            for finding in safety_assessment.findings:
                blocking_reasons.append(
                    f"UPGRADE_BLOCKED_MIGRATION_REQUIRED: {finding.address} "
                    f"({finding.resource_type}) — {finding.reason}"
                )
            if compatibility is not None and compatibility.blocked:
                blocking_reasons.append(
                    f"UPGRADE_BLOCKED_COMPATIBILITY: {compatibility.reason}"
                )

            report = build_drift_report(
                drift_assessment,
                project=context.project_name,
                environment=context.environment,
                workspace=context.terraform_workspace,
                baseline=baseline.to_dict(),
                source_version=(installed.version if installed else None),
                target_version=context.deployment_version,
                git_commit=(source_identity.commit if source_identity else None),
                critical_changes=[f.to_dict() for f in safety_assessment.findings],
                blocking_reasons=blocking_reasons,
            )
            drift_json, drift_md = write_drift_report(run_dir, report)
            print(
                f"Drift: {drift_assessment.drift_status} | "
                f"No-op: {drift_assessment.noop_status}"
            )

            # P1D: Upgrade-Readiness-Bericht.
            from installer.core.upgrade_readiness import (
                ReadinessInput,
                build_readiness_report,
                write_readiness_report,
            )

            readiness = build_readiness_report(
                ReadinessInput(
                    project=context.project_name,
                    environment=context.environment,
                    region=context.aws_region,
                    account_id=getattr(
                        context.aws_execution_context, "account_id", None
                    ),
                    backend=backend_contract.comparison_dict(),
                    workspace=context.terraform_workspace,
                    baseline=baseline.to_dict(),
                    source_version=(installed.version if installed else None),
                    target_version=context.deployment_version,
                    git_commit=(source_identity.commit if source_identity else None),
                    plan_sha256=sha256_file(Path(saved_plan)),
                    compatibility_status=(compatibility.status if compatibility else None),
                    compatibility_reason=(compatibility.reason if compatibility else None),
                    drift_status=drift_assessment.drift_status,
                    noop_status=drift_assessment.noop_status,
                    planned_changes=[c.to_dict() for c in drift_assessment.planned_changes],
                    classification=classification.to_dict(),
                    blocking_reasons=blocking_reasons,
                )
            )
            readiness_json, readiness_md = write_readiness_report(run_dir, readiness)
            print(f"Readiness: {readiness['status']}")
            print(f"Readiness-Bericht: {readiness_json}")

            if blocking_reasons:
                for reason in blocking_reasons:
                    print(reason)
                print(f"Drift-Zusammenfassung: {drift_md}")
                print(f"Readiness-Zusammenfassung: {readiness_md}")
                return 1
            print(f"Drift-Bericht: {drift_json}")

        # Save plan metadata alongside plan file
        plan_metadata_path = run_dir / "plans" / f"{plan_file_name}.meta.json"
        plan_metadata_path.write_text(plan_metadata.to_json())

        # Also save deployment context for reference
        deployment_context = context.get_deployment_context()
        deployment_context_path = run_dir / "plans" / f"{plan_file_name}.context.json"
        deployment_context_path.write_text(deployment_context.to_json())

        from installer.run.manager import PlanArtifactManager
        PlanArtifactManager.save_plan_safely(
            str(plan_output),
            Path(f".mays-installer/runs/{datetime.now().strftime('%Y%m%d-%H%M%S')}/plans/{plan_file_name}"),
            sanitize=False  # Skip sanitization to avoid provider initialization
        )

        # MO-RC4-P02I-E2B: Manifest fuer die Identitaetsbindung (nur Remote-Plan).
        if remote:
            from installer.core.plan_manifest import PlanManifest

            manifest = PlanManifest.create(
                saved_plan,
                deployment_id=deployment_context.deployment_id,
                operation=operation,
                region=context.aws_region,
                workspace=context.terraform_workspace,
                backend=backend_contract,
                variables=var,
                git_commit=(source_identity.commit if source_identity else None),
                source_version=(installed.version if installed and installed.status == "VERIFIED" else None),
                target_version=context.deployment_version,
                git_dirty=(source_identity.dirty if source_identity else None),
                version_status=(installed.status if installed else None),
                version_source=(installed.source if installed else None),
                state_baseline=(baseline.to_dict() if baseline else None),
                drift_status=(drift_assessment.drift_status if drift_assessment else None),
                noop_status=(drift_assessment.noop_status if drift_assessment else None),
                compatibility_status=(compatibility.status if compatibility else None),
                readiness_status=(readiness.get("status") if readiness else None),
            )
            manifest_path = manifest.write(saved_plan)
            print(f"  Plan manifest: {manifest_path}")
            print(f"  Plan sha256: {manifest.plan_sha256}")

        # Print summary using plan_result directly
        run_plan_path = saved_plan
        cmd = "destroy" if parsed.destroy else "deploy"
        print(f"\nPlan Summary:")
        print(f"  Plan file: {plan_file_name}")
        print(f"  Plan artifact: {saved_plan}")
        print(f"  Plan metadata: {plan_metadata_path.name}")
        print(f"  {cmd.capitalize()} with: ./Mays-Order-AWS-installer {cmd} --plan {run_plan_path}")
        print(f"  Status: Generated successfully")

        return 0

    def _cmd_plan_destroy(self, context, parsed, run_dir) -> int:
        """Generate destroy plan."""
        # Reuse plan command with destroy flag
        parsed.destroy = True
        # `--out` bleibt unveraendert: kein stiller Default-Pfad. Ein
        # Remote-Plan verlangt --out ausdruecklich (siehe _cmd_plan).
        return self._cmd_plan(context, parsed, run_dir)

    def _verify_plan_manifest(
        self,
        context,
        plan_file: Path,
        operation: PlanOperation,
        require_manifest: bool = True,
        allow_legacy_manifest: bool = False,
    ) -> bool:
        """Prueft das Plan-Manifest gegen den aktuellen Kontext.

        Deploy verlangt ein Manifest (Schema 2 mit Versionsbindung); Destroy
        akzeptiert Legacy-Plaene (v1) ohne Versionsbindung, da ein Destroy kein
        Upgrade ist.
        """
        from installer.core.plan_contract import BackendContractError, load_backend_contract
        from installer.core.plan_manifest import PlanManifest

        try:
            manifest = PlanManifest.load(plan_file)
        except ValueError as exc:
            print(f"Plan manifest invalid: {exc}")
            return False

        if manifest is None:
            if require_manifest:
                print(
                    "UPGRADE_VERSION_BINDING_MISSING: Der Plan hat kein Manifest "
                    "(keine Versions-/Identitaetsbindung). Bitte mit `plan --remote` "
                    "neu planen."
                )
                return False
            print(
                "WARNING: Plan has no manifest (legacy artifact); "
                "destroy continues with filename/context/cleanup checks only."
            )
            return True

        try:
            backend = load_backend_contract(context.terraform_dir)
        except BackendContractError as exc:
            print(f"Plan manifest cannot be verified: {exc}")
            return False

        deployment_context = context.get_deployment_context()
        ok, message = manifest.verify(
            plan_file,
            deployment_id=deployment_context.deployment_id,
            region=context.aws_region,
            workspace=context.terraform_workspace,
            backend=backend,
            operation=operation,
            allow_legacy_manifest=allow_legacy_manifest,
        )
        if not ok:
            print(f"Plan manifest mismatch: {message}")
            return False

        print(
            f"Plan manifest verified (project={manifest.deployment_id.project}, "
            f"workspace={manifest.workspace}, region={manifest.region}, "
            f"sha256={manifest.plan_sha256[:12]}...)"
        )
        return True

    def _load_plan_json(self, context, plan_path: Path):
        """Liest das Plan-JSON (fail-closed). Gibt None bei Fehlern zurueck."""
        runner = self._make_runner(context)
        result = runner.show_plan(str(Path(plan_path).resolve()))
        if not result.success:
            print(
                "UPGRADE_PLAN_UNREADABLE: Plan-JSON konnte nicht gelesen werden "
                f"(fail-closed): {(result.stderr or '').strip()[:400]}"
            )
            return None
        try:
            return json.loads(result.stdout)
        except (TypeError, ValueError) as exc:
            print(f"UPGRADE_PLAN_UNREADABLE: Plan-JSON ungueltig (fail-closed): {exc}")
            return None

    def _verify_upgrade_readiness(self, context, plan_file: Path, parsed) -> bool:
        """Prueft die Upgrade-Kompatibilitaet erneut (Readiness ist keine Freigabe)."""
        from installer.core.compatibility import assess_compatibility
        from installer.core.plan_manifest import PlanManifest

        try:
            manifest = PlanManifest.load(plan_file)
        except ValueError as exc:
            print(f"UPGRADE_READINESS_INVALID: {exc}")
            return False

        if manifest is None:
            print("UPGRADE_READINESS_MISSING: kein Plan-Manifest vorhanden.")
            return False

        if not manifest.compatibility_status:
            print("Upgrade readiness: n/a (kein Upgrade-Plan)")
            return True

        assessment = assess_compatibility(
            manifest.source_version,
            context.deployment_version,
            source_status=(manifest.version_status or "UNVERIFIED"),
        )
        if assessment.blocked:
            print(f"Upgrade readiness: BLOCKED ({assessment.status})")
            print(assessment.reason)
            return False
        if assessment.review_required and not getattr(
            parsed, "accept_upgrade_review", False
        ):
            print(
                "UPGRADE_REVIEW_APPROVAL_REQUIRED: Upgrade erfordert eine "
                "ausdrueckliche Freigabe (--accept-upgrade-review) nach manueller "
                "Pruefung."
            )
            print(assessment.reason)
            return False

        print(f"Upgrade readiness: {assessment.status}")
        return True

    def _verify_state_baseline(self, context, plan_file: Path) -> bool:
        """Vergleicht die im Manifest gebundene State-Baseline mit dem State."""
        from installer.core.drift import DRIFT_UNKNOWN
        from installer.core.plan_manifest import PlanManifest
        from installer.core.state_baseline import (
            capture_state_baseline,
            compare_state_baseline,
        )

        try:
            manifest = PlanManifest.load(plan_file)
        except ValueError as exc:
            print(f"UPGRADE_STATE_BASELINE_MISMATCH: {exc}")
            return False

        if manifest is None:
            print(
                "UPGRADE_STATE_BASELINE_MISSING: kein Plan-Manifest vorhanden "
                "(plan --remote erforderlich)."
            )
            return False

        if manifest.drift_status == DRIFT_UNKNOWN:
            print(
                "UPGRADE_DRIFT_UNVERIFIED: Der Plan traegt keinen belastbaren "
                "Drift-Nachweis; Apply ist blockiert."
            )
            return False

        current = capture_state_baseline(self._make_runner(context))
        ok, code, message = compare_state_baseline(manifest.state_baseline, current)
        if not ok:
            print(f"State baseline: BLOCKED ({code})")
            print(message)
            return False

        serial = (manifest.state_baseline or {}).get("serial")
        print(f"State baseline: OK (serial={serial})")
        return True

    def _verify_version_binding(self, context, plan_file: Path, parsed) -> bool:
        """Prueft die Versionsbindung eines gespeicherten Plans vor dem Apply.

        Ein gueltiger Plan-Hash legitimiert keine widerspruechlichen
        Versionsinformationen. Fehlende/unlesbare Informationen blockieren.
        """
        from installer.core.plan_manifest import PlanManifest
        from installer.core.source_identity import resolve_source_identity
        from installer.core.version_binding import (
            check_version_binding,
            detect_installed_version,
        )

        try:
            manifest = PlanManifest.load(plan_file)
        except ValueError as exc:
            print(f"UPGRADE_VERSION_BINDING_MISMATCH: {exc}")
            return False

        if manifest is None:
            print(
                "UPGRADE_VERSION_BINDING_MISSING: kein Plan-Manifest vorhanden "
                "(plan --remote erforderlich)."
            )
            return False

        runner = self._make_runner(context)
        installed = detect_installed_version(runner)
        identity = resolve_source_identity()
        check = check_version_binding(
            manifest,
            current_target_version=context.deployment_version,
            identity=identity,
            installed=installed,
            allow_dirty_source=bool(getattr(parsed, "allow_dirty_source", False)),
            allow_legacy_source=bool(getattr(parsed, "allow_legacy_source", False)),
        )
        if not check.ok:
            print(f"Upgrade version binding: BLOCKED ({check.code})")
            print(check.message())
            return False

        source = manifest.source_version or manifest.version_status
        print(
            f"Version binding: OK (target={manifest.target_version}, "
            f"source={source}, commit={(manifest.git_commit or '')[:12]})"
        )
        return True

    def _enforce_upgrade_safety(self, context, plan_path: Path, run_dir: Path) -> bool:
        """P0A: block delete/replace of protected resources (fail-closed).

        Runs for deploy plans at creation time and again immediately before a
        saved plan is applied. A valid manifest/SHA-256 alone does not make a
        plan safe. Explicit destroy plans are handled separately
        (_verify_destroy_plan) and are not subject to this gate.
        """
        from installer.core.upgrade_safety import (
            STATUS_SAFE,
            analyze_plan,
            build_migration_plan,
            format_block_message,
            sha256_file,
            write_migration_plan,
        )

        runner = self._make_runner(context)
        result = runner.show_plan(str(Path(plan_path).resolve()))
        if not result.success:
            print("UPGRADE_BLOCKED_PLAN_UNREADABLE")
            print(
                "Plan-JSON konnte nicht gelesen werden (fail-closed): "
                f"{(result.stderr or '').strip()[:400]}"
            )
            return False

        try:
            plan_json = json.loads(result.stdout)
        except (TypeError, ValueError) as exc:
            print("UPGRADE_BLOCKED_PLAN_UNREADABLE")
            print(f"Plan-JSON ist nicht interpretierbar (fail-closed): {exc}")
            return False

        assessment = analyze_plan(plan_json, sha256_file(plan_path))
        if assessment.status == STATUS_SAFE:
            print("Upgrade safety: PASS (keine geschuetzte Ressource wird geloescht/ersetzt)")
            return True

        migration_plan = build_migration_plan(
            assessment,
            project=context.project_name,
            environment=context.environment,
            workspace=context.terraform_workspace,
        )
        json_path, md_path = write_migration_plan(run_dir, migration_plan, assessment)
        print(format_block_message(assessment))
        print(f"Migrationsplan (JSON): {json_path}")
        print(f"Migrationsbericht (MD): {md_path}")
        return False

    def _verify_destroy_plan(self, context, plan_path: Path) -> tuple:
        """P0A: a destroy command may only apply a genuine destroy plan.

        Prevents using `destroy --plan <deploy-plan>` as a bypass of the
        upgrade safety gate.
        """
        from installer.core.upgrade_safety import is_destroy_plan

        runner = self._make_runner(context)
        result = runner.show_plan(str(Path(plan_path).resolve()))
        if not result.success:
            return False, (
                "Plan-JSON konnte nicht gelesen werden (fail-closed): "
                f"{(result.stderr or '').strip()[:400]}"
            )
        try:
            plan_json = json.loads(result.stdout)
        except (TypeError, ValueError) as exc:
            return False, f"Plan-JSON ist nicht interpretierbar (fail-closed): {exc}"

        ok, reason = is_destroy_plan(plan_json)
        if not ok:
            return False, reason
        return True, ""

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

        # MO-RC4-P02I-E2B: Manifest-basierte Identitaetsbindung pruefen
        # (Account/Projekt/Environment/Region/Workspace/Backend/Checksumme),
        # bevor der Plan kopiert oder angewendet wird.
        if not self._verify_plan_manifest(
            context, plan_file, PlanOperation.DEPLOY, require_manifest=True
        ):
            return 1

        # MO-P0B: verbindliche Versionsbindung (Zielversion, Commit, Dirty,
        # installierte Ausgangsversion) — vor jedem Apply.
        if not self._verify_version_binding(context, plan_file, parsed):
            return 1

        # MO-P0C: State-Baseline (Serial/Lineage/Fingerprint) vor dem Apply.
        if not self._verify_state_baseline(context, plan_file):
            return 1

        # P1D: Upgrade-Readiness (Kompatibilitaet) erneut pruefen — die
        # Readiness-Datei ist keine Freigabe.
        if not self._verify_upgrade_readiness(context, plan_file, parsed):
            return 1

        # P0A-02: Auch ein gespeicherter Plan mit gueltigem Manifest/SHA-256
        # muss das Upgrade-Safety-Gate erneut bestehen.
        if not self._enforce_upgrade_safety(context, plan_file, run_dir):
            return 1

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
        runner = self._make_runner(context)

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
        runner_dummy = self._make_runner(context)
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
            plan_json_result = self._make_runner(context).show_plan(terraform_plan_file)

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
        runner = self._make_runner(context, "terraform")
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
        verify_identity = self._make_runner(context, "terraform").version()
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
        # `--out` bleibt unveraendert: kein stiller Default-Pfad. Ein
        # Remote-Plan verlangt --out ausdruecklich (siehe _cmd_plan).
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

        # MO-RC4-P02I-E2B: Manifest-basierte Identitaetsbindung pruefen
        # (Account/Projekt/Environment/Region/Workspace/Backend/Checksumme),
        # bevor der Destroy-Plan kopiert oder angewendet wird.
        if not self._verify_plan_manifest(
            context,
            plan_file,
            PlanOperation.DESTROY,
            require_manifest=False,
            allow_legacy_manifest=True,
        ):
            return 1

        # P0A-03: Destroy darf nicht als Bypass fuer das Upgrade-Gate dienen;
        # es werden ausschliesslich echte Destroy-Plaene angewendet.
        destroy_ok, destroy_reason = self._verify_destroy_plan(context, plan_file)
        if not destroy_ok:
            print("DESTROY_PLAN_REQUIRED")
            print(destroy_reason)
            print("Es wurde kein Destroy ausgefuehrt.")
            return 1

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
        runner = self._make_runner(context)

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

        # MO-RC4-P02I-E2B: Cleanup-Ziel muss exakt der State des Projekts sein.
        from installer.core.cleanup_contract import validate_cleanup_target
        from installer.core.plan_contract import BackendContractError, load_backend_contract

        try:
            backend = load_backend_contract(context.terraform_dir)
        except BackendContractError as exc:
            print(f"Destroy blocked: {exc}")
            return 1
        state_key = backend.state_key(context.terraform_workspace)
        cleanup_errors = validate_cleanup_target(state_key, context.project_name)
        if cleanup_errors:
            print("Destroy blocked (cleanup contract):")
            for error in cleanup_errors:
                print(f"  - {error}")
            return 1
        print(f"State target: s3://{backend.bucket}/{state_key}")

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
        runner_dummy = self._make_runner(context)
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
        plan_json_result = self._make_runner(context).show_plan(terraform_plan_file)
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
        runner = self._make_runner(context, "terraform")
        destroy_result = runner.destroy(str(Path.cwd() / parsed.plan))

        if not destroy_result.success:
            print(f"Destruction failed: {destroy_result.stderr}")
            return 1

        print("Destruction successful!")

        # Post-destroy verification (Cleanup-Vertrag)
        print("\nRunning post-destroy verification...")
        from installer.core.cleanup_contract import residual_resources

        verify_result = runner.state_list()
        if verify_result.success:
            remaining = residual_resources(verify_result.stdout)
            if remaining:
                print(f"⚠ {len(remaining)} resource(s) still present in state:")
                for address in remaining:
                    print(f"    {address}")
                print(
                    "Cleanup contract NOT satisfied: no state cleanup before a "
                    "successful, verified empty state. Aborting."
                )
                return 1
            print("✓ Terraform state accessible and empty (0 resources)")
        else:
            print("⚠ Could not verify Terraform state")
            return 1

        print("\nDestruction completed successfully!")
        return 0

    def _cmd_state(self, context: "InstallationContext", parsed, run_dir: Path) -> int:
        """Manage Terraform state."""
        # Validate AWS context first
        if not context.validate_aws_context():
            print("AWS context validation failed. Cannot proceed with state operations.")
            return 1

        runner = self._make_runner(context)

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

        runner = self._make_runner(context)
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

        runner = self._make_runner(context, "terraform")
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
