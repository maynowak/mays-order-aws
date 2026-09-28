"""
Installer Core Command Service
Provides stable programmatic interface for deployment commands.
"""

from __future__ import annotations

from installer.core.context import InstallationContext
from installer.terraform.runner import TerraformRunner
from installer.core.command_result import CommandResult, CommandStatus


class CommandService:
    def __init__(self, context: InstallationContext):
        self.context = context
        self.runner = TerraformRunner(
            context.terraform_dir,
            context.aws_execution_context
        )

    def init(self, backend: bool = True) -> CommandResult:
        result = self.runner.init(backend=backend)
        status = CommandStatus.SUCCESS if result.success else CommandStatus.FAILED
        return CommandResult(
            command="init",
            status=status,
            exit_code=0 if result.success else 1,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            metadata={"backend": backend}
        )

    def validate(self) -> CommandResult:
        result = self.runner.validate()
        status = CommandStatus.SUCCESS if result.success else CommandStatus.FAILED
        return CommandResult(
            command="validate",
            status=status,
            exit_code=0 if result.success else 1,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    def plan(self, out_file: str = "deploy.tfplan", var: dict | None = None) -> CommandResult:
        result = self.runner.plan(out_file=out_file, var=var)
        status = CommandStatus.SUCCESS if result.success else CommandStatus.FAILED
        return CommandResult(
            command="plan",
            status=status,
            exit_code=0 if result.success else 1,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            metadata={"out_file": out_file}
        )

    def apply(self, plan_file: str) -> CommandResult:
        result = self.runner.apply(plan_file)
        status = CommandStatus.SUCCESS if result.success else CommandStatus.FAILED
        return CommandResult(
            command="apply",
            status=status,
            exit_code=0 if result.success else 1,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            metadata={"plan_file": plan_file}
        )

    def destroy(self, plan_file: str) -> CommandResult:
        result = self.runner.destroy(plan_file)
        status = CommandStatus.SUCCESS if result.success else CommandStatus.FAILED
        return CommandResult(
            command="destroy",
            status=status,
            exit_code=0 if result.success else 1,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            metadata={"plan_file": plan_file}
        )
