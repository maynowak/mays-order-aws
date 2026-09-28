"""
Installer Core Command Service
Provides stable programmatic interface for deployment commands.
"""

from __future__ import annotations

from installer.core.context import InstallationContext
from installer.terraform.runner import TerraformRunner


class CommandService:
    def __init__(self, context: InstallationContext):
        self.context = context
        self.runner = TerraformRunner(
            context.terraform_dir,
            context.aws_execution_context
        )

    def init(self, backend: bool = True) -> dict:
        result = self.runner.init(backend=backend)
        return {"success": result.success, "stdout": result.stdout, "stderr": result.stderr}

    def validate(self) -> dict:
        result = self.runner.validate()
        return {"success": result.success, "stdout": result.stdout, "stderr": result.stderr}

    def plan(self, out_file: str = "deploy.tfplan", var: dict | None = None) -> dict:
        result = self.runner.plan(out_file=out_file, var=var)
        return {"success": result.success, "stdout": result.stdout, "stderr": result.stderr}

    def apply(self, plan_file: str) -> dict:
        result = self.runner.apply(plan_file)
        return {"success": result.success, "stdout": result.stdout, "stderr": result.stderr}

    def destroy(self, plan_file: str) -> dict:
        result = self.runner.destroy(plan_file)
        return {"success": result.success, "stdout": result.stdout, "stderr": result.stderr}
