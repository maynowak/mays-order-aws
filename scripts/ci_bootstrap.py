#!/usr/bin/env python3
"""
CI Repository Bootstrap / Validation Script

Validates that a fresh checkout of the Mays-Orders-AWS repository
contains everything required for the AWS CodePipeline/CodeBuild setup.

This script MUST NOT require AWS credentials to run.
It only validates repository structure and local importability.
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_ok(msg: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def print_fail(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def print_warn(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def print_info(msg: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def print_section(title: str) -> None:
    print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
    print("-" * len(title))


class RepoValidator:
    """Validates Mays-Orders-AWS repository structure for CI/CD."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def _add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def _add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def _add_info(self, msg: str) -> None:
        self.info.append(msg)

    def validate_repo_root(self) -> bool:
        """Validate repository root detection."""
        print_section("Repository Root Detection")

        # Check for expected marker files/dirs
        markers = [
            ("installer/", "installer package"),
            ("terraform/", "Terraform configurations"),
            ("ci/buildspecs/validate.yml", "CI buildspecs"),
            ("ci/pipeline/main.tf", "Pipeline Terraform"),
            ("ci/iam/main.tf", "IAM Terraform"),
            ("scripts/ci_bootstrap.py", "CI bootstrap script"),
        ]

        all_ok = True
        for path, desc in markers:
            full = self.repo_root / path
            if full.exists():
                print_ok(f"{path} ({desc})")
            else:
                print_fail(f"{path} ({desc}) - MISSING")
                self._add_error(f"Missing required path: {path}")
                all_ok = False

        # Detect .git to confirm repo root
        git_dir = self.repo_root / ".git"
        if git_dir.exists():
            print_ok(".git directory found")
            self._add_info(f"Repository root: {self.repo_root}")
        else:
            print_warn(".git directory not found - may not be a git repo")

        return all_ok

    def validate_installer(self) -> bool:
        """Validate installer package exists and is importable."""
        print_section("Installer Validation")

        all_ok = True

        # Check installer package structure
        installer_dir = self.repo_root / "installer"
        required_files = [
            "__init__.py",
            "cli/main.py",
            "core/context.py",
            "core/deployment_identity.py",
            "core/aws_context.py",
            "core/fail_closed.py",
        ]

        for f in required_files:
            path = installer_dir / f
            if path.exists():
                print_ok(f"installer/{f}")
            else:
                print_fail(f"installer/{f} - MISSING")
                self._add_error(f"Missing installer file: {f}")
                all_ok = False

        # Test CLI import
        try:
            sys.path.insert(0, str(self.repo_root))
            from installer.cli.main import InstallerCLI
            print_ok("installer.cli.main importable")
        except ImportError as e:
            print_fail(f"installer.cli.main import failed: {e}")
            self._add_error(f"Installer CLI not importable: {e}")
            all_ok = False

        # Test core modules import
        try:
            from installer.core.context import InstallationContext, ValidationLayer
            from installer.core.aws_context import AWSProfileValidator, AWSExecutionContext
            from installer.core.deployment_identity import DeploymentContext, DeploymentId
            from installer.core.fail_closed import FailClosedError
            print_ok("installer.core modules importable")
        except ImportError as e:
            print_fail(f"installer.core import failed: {e}")
            self._add_error(f"Installer core not importable: {e}")
            all_ok = False

        # Test CLI instantiation
        try:
            cli = InstallerCLI()
            print_ok("InstallerCLI instantiable")
        except Exception as e:
            print_fail(f"InstallerCLI instantiation failed: {e}")
            self._add_error(f"InstallerCLI instantiation failed: {e}")
            all_ok = False

        return all_ok

    def validate_buildspecs(self) -> bool:
        """Validate all six CI buildspecs exist and reference installer."""
        print_section("Buildspec Validation")

        buildspecs = [
            ("validate.yml", "python3 -m installer.cli.main validate"),
            ("plan.yml", "python3 -m installer.cli.main plan"),
            ("deploy.yml", "python3 -m installer.cli.main deploy"),
            ("verify.yml", "python3 -m installer.cli.main verify"),
            ("destroy-plan.yml", "python3 -m installer.cli.main plan-destroy"),
            ("destroy.yml", "python3 -m installer.cli.main destroy"),
        ]

        all_ok = True
        buildspecs_dir = self.repo_root / "ci" / "buildspecs"

        for filename, expected_cmd in buildspecs:
            path = buildspecs_dir / filename
            if not path.exists():
                print_fail(f"{filename} - MISSING")
                self._add_error(f"Missing buildspec: {filename}")
                all_ok = False
                continue

            print_ok(f"{filename} exists")

            # Validate YAML syntax
            try:
                import yaml
                content = path.read_text()
                spec = yaml.safe_load(content)
                if not spec:
                    print_warn(f"{filename} - empty or invalid YAML")
                    continue
                print_ok(f"{filename} - valid YAML")
            except Exception as e:
                print_fail(f"{filename} - YAML parse error: {e}")
                self._add_error(f"Buildspec {filename} YAML error: {e}")
                all_ok = False
                continue

            # Check that buildspec invokes installer CLI
            if expected_cmd in content:
                print_ok(f"{filename} - invokes installer CLI ({expected_cmd})")
            else:
                print_warn(f"{filename} - expected command '{expected_cmd}' not found")

            # Check for direct Terraform bypass
            bypass_patterns = [
                "terraform apply",
                "terraform plan",
                "terraform destroy",
                "terraform init",
            ]
            for pattern in bypass_patterns:
                if pattern in content and "installer.cli.main" not in content:
                    if pattern not in ["terraform fmt", "terraform validate"]:
                        print_warn(f"{filename} - contains direct '{pattern}' (verify it's via installer)")

            # Verify buildspec path is relative to CODEBUILD_SRC_DIR
            if "source:" in content:
                print_info(f"{filename} - uses source config (CodeBuild will use CODEBUILD_SRC_DIR)")

        return all_ok

    def validate_terraform(self) -> bool:
        """Validate Terraform directory and configuration."""
        print_section("Terraform Validation")

        all_ok = True
        terraform_dir = self.repo_root / "terraform"

        if not terraform_dir.exists():
            print_fail("terraform/ directory - MISSING")
            self._add_error("Missing terraform/ directory")
            return False

        print_ok("terraform/ directory exists")

        required_files = ["main.tf", "variables.tf", "outputs.tf"]
        for f in required_files:
            path = terraform_dir / f
            if path.exists():
                print_ok(f"terraform/{f}")
            else:
                print_warn(f"terraform/{f} - MISSING (may be optional)")

        # Check for provider version
        main_tf = terraform_dir / "main.tf"
        if main_tf.exists():
            content = main_tf.read_text()
            if "required_version" in content:
                print_ok("terraform/main.tf - has required_version")
            if "required_providers" in content and "aws" in content:
                print_ok("terraform/main.tf - has AWS provider")

        # terraform fmt -check
        try:
            result = subprocess.run(
                ["terraform", "fmt", "-check", "-diff"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print_ok("terraform fmt -check passed")
            else:
                print_warn(f"terraform fmt -check has differences:\n{result.stdout}")
        except FileNotFoundError:
            print_warn("terraform CLI not available - skipping fmt/validate")
        except subprocess.TimeoutExpired:
            print_warn("terraform fmt timeout")

        # terraform validate (requires init first, skip for bootstrap)
        print_info("terraform validate skipped (requires init)")

        return all_ok

    def validate_pipeline_terraform(self) -> bool:
        """Validate CI pipeline Terraform references correct buildspec paths."""
        print_section("Pipeline Terraform Validation")

        all_ok = True
        pipeline_dir = self.repo_root / "ci" / "pipeline"

        if not pipeline_dir.exists():
            print_fail("ci/pipeline/ - MISSING")
            self._add_error("Missing ci/pipeline/ directory")
            return False

        main_tf = pipeline_dir / "main.tf"
        if not main_tf.exists():
            print_fail("ci/pipeline/main.tf - MISSING")
            self._add_error("Missing ci/pipeline/main.tf")
            return False

        content = main_tf.read_text()

        # Check buildspec paths are repository-relative
        expected_buildspecs = [
            'buildspec = "ci/buildspecs/validate.yml"',
            'buildspec = "ci/buildspecs/plan.yml"',
            'buildspec = "ci/buildspecs/deploy.yml"',
            'buildspec = "ci/buildspecs/verify.yml"',
            'buildspec = "ci/buildspecs/destroy-plan.yml"',
            'buildspec = "ci/buildspecs/destroy.yml"',
        ]

        for expected in expected_buildspecs:
            if expected in content:
                print_ok(f"Pipeline references {expected.split('=')[1].strip().strip('\"')}")
            else:
                print_fail(f"Pipeline missing reference: {expected}")
                self._add_error(f"Pipeline missing buildspec reference: {expected}")
                all_ok = False

        # Check for hardcoded absolute paths (bad)
        bad_patterns = [
            "/home/dci-student",
            "/root/",
            "/tmp/",
            "/opt/",
        ]
        for pattern in bad_patterns:
            if pattern in content:
                print_warn(f"Pipeline contains potential hardcoded path: {pattern}")

        return all_ok

    def validate_scripts(self) -> bool:
        """Validate CI scripts."""
        print_section("CI Scripts Validation")

        all_ok = True
        scripts_dir = self.repo_root / "scripts"

        if not scripts_dir.exists():
            print_fail("scripts/ directory - MISSING")
            self._add_error("Missing scripts/ directory")
            return False

        print_ok("scripts/ directory exists")

        # Check for ci_bootstrap.py
        bootstrap = scripts_dir / "ci_bootstrap.py"
        if bootstrap.exists():
            print_ok("scripts/ci_bootstrap.py exists")
            # Check syntax only (no full run to avoid timeout)
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'py_compile', str(bootstrap)],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode != 0:
                    print_warn(f"ci_bootstrap.py - syntax check failed: {result.stderr}")
                else:
                    print_ok("ci_bootstrap.py - syntax OK")
            except Exception as e:
                print_warn(f"ci_bootstrap.py - syntax check failed: {e}")
        else:
            print_fail("scripts/ci_bootstrap.py - MISSING")
            self._add_error("Missing ci_bootstrap.py")
            all_ok = False

        return all_ok

    def validate_no_direct_terraform_bypass(self) -> bool:
        """Ensure no CI configuration bypasses the installer."""
        print_section("Direct Terraform Bypass Detection")

        all_ok = True

        # Check buildspecs
        buildspecs_dir = self.repo_root / "ci" / "buildspecs"
        for spec_file in buildspecs_dir.glob("*.yml"):
            content = spec_file.read_text()

            # Check for direct terraform commands that bypass installer
            # Allow terraform fmt/validate as they're read-only checks
            lines = content.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Skip comments
                if stripped.startswith('#'):
                    continue
                # Check for direct terraform apply/plan/destroy/init (not fmt/validate)
                if any(cmd in stripped for cmd in [
                    "terraform apply",
                    "terraform plan",
                    "terraform destroy",
                    "terraform init",
                ]):
                    # Check if it's in a command that runs installer
                    context = " ".join(lines[max(0,i-5):i+5])
                    if "installer.cli.main" not in context:
                        print_warn(f"{spec_file.name}:{i+1} - possible direct terraform: {stripped[:80]}")
                        self._add_warning(f"Possible terraform bypass in {spec_file.name}:{i+1}")

        # Check pipeline Terraform
        pipeline_tf = self.repo_root / "ci" / "pipeline" / "main.tf"
        if pipeline_tf.exists():
            content = pipeline_tf.read_text()
            # CodePipeline Commands action would be a bypass
            if 'provider = "Commands"' in content:
                print_fail("Pipeline uses CodePipeline Commands action (bypasses CodeBuild/installer)")
                self._add_error("Pipeline uses Commands action - direct Terraform bypass")
                all_ok = False
            else:
                print_ok("Pipeline uses CodeBuild projects (not Commands action)")

        return all_ok

    def validate_yaml_syntax(self) -> bool:
        """Validate all YAML files in ci/ have valid syntax."""
        print_section("YAML Syntax Validation")

        all_ok = True
        import yaml

        for yaml_file in self.repo_root.glob("ci/**/*.yml"):
            if yaml_file.is_file():
                try:
                    yaml.safe_load(yaml_file.read_text())
                    print_ok(f"{yaml_file.relative_to(self.repo_root)} - valid")
                except yaml.YAMLError as e:
                    print_fail(f"{yaml_file.relative_to(self.repo_root)} - YAML error: {e}")
                    self._add_error(f"YAML syntax error in {yaml_file}: {e}")
                    all_ok = False
                except Exception as e:
                    print_fail(f"{yaml_file.relative_to(self.repo_root)} - read error: {e}")
                    self._add_error(f"YAML read error in {yaml_file}: {e}")
                    all_ok = False

        return all_ok

    def validate_git_diff(self) -> bool:
        """Run git diff --check for whitespace errors."""
        print_section("Git Diff Check")

        try:
            result = subprocess.run(
                ["git", "diff", "--check"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print_ok("git diff --check passed")
                return True
            else:
                print_warn(f"git diff --check found issues:\n{result.stdout}")
                self._add_warning("Git diff has whitespace issues")
                return True  # Warning only, not error
        except Exception as e:
            print_warn(f"git diff --check failed: {e}")
            return True

    def validate_python_syntax(self) -> bool:
        """Validate Python syntax for key modules."""
        print_section("Python Syntax Validation")

        all_ok = True
        python_files = [
            "installer/cli/main.py",
            "installer/core/context.py",
            "installer/core/aws_context.py",
            "installer/core/deployment_identity.py",
            "installer/core/fail_closed.py",
            "scripts/ci_bootstrap.py",
        ]

        for f in python_files:
            path = self.repo_root / f
            if path.exists():
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "py_compile", str(path)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        print_ok(f"{f} - syntax OK")
                    else:
                        print_fail(f"{f} - syntax error: {result.stderr}")
                        self._add_error(f"Python syntax error in {f}: {result.stderr}")
                        all_ok = False
                except Exception as e:
                    print_fail(f"{f} - check failed: {e}")
                    self._add_error(f"Python syntax check failed for {f}: {e}")
                    all_ok = False
            else:
                print_warn(f"{f} - not found")

        return all_ok

    def run_all(self) -> bool:
        """Run all validations."""
        print(f"{Colors.BOLD}{Colors.BLUE}")
        print("=" * 60)
        print("Mays-Orders-AWS CI Repository Bootstrap Validation")
        print("=" * 60)
        print(f"{Colors.RESET}")

        results = []

        results.append(("Repository Root", self.validate_repo_root()))
        results.append(("Installer", self.validate_installer()))
        results.append(("Buildspecs", self.validate_buildspecs()))
        results.append(("Terraform", self.validate_terraform()))
        results.append(("Pipeline Terraform", self.validate_pipeline_terraform()))
        results.append(("CI Scripts", self.validate_scripts()))
        results.append(("No Terraform Bypass", self.validate_no_direct_terraform_bypass()))
        results.append(("YAML Syntax", self.validate_yaml_syntax()))
        results.append(("Git Diff", self.validate_git_diff()))
        results.append(("Python Syntax", self.validate_python_syntax()))

        # Summary
        print_section("SUMMARY")

        passed = sum(1 for _, r in results if r)
        total = len(results)

        for name, result in results:
            status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
            print(f"  {status} - {name}")

        if self.errors:
            print(f"\n{Colors.RED}Errors:{Colors.RESET}")
            for e in self.errors:
                print(f"  {Colors.RED}•{Colors.RESET} {e}")

        if self.warnings:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.RESET}")
            for w in self.warnings:
                print(f"  {Colors.YELLOW}•{Colors.RESET} {w}")

        if self.info:
            print(f"\n{Colors.BLUE}Info:{Colors.RESET}")
            for i in self.info:
                print(f"  {Colors.BLUE}•{Colors.RESET} {i}")

        print(f"\n{Colors.BOLD}Result: {passed}/{total} checks passed{Colors.RESET}")

        if self.errors:
            print(f"{Colors.RED}VALIDATION FAILED{Colors.RESET}")
            return False
        else:
            print(f"{Colors.GREEN}VALIDATION PASSED{Colors.RESET}")
            return True


def main() -> int:
    # Find repository root (where this script is located)
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent

    print_info(f"Repository root: {repo_root}")

    validator = RepoValidator(repo_root)
    success = validator.run_all()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
