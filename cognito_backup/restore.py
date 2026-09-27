import json
from botocore.exceptions import ClientError

class RestoreValidator:
    @staticmethod
    def validate_manifest(manifest: dict, target_project: str, target_environment: str, target_account: str, target_region: str) -> None:
        errors = []
        if manifest.get("project_name") != target_project:
            errors.append("project_name mismatch")
        if manifest.get("environment") != target_environment:
            errors.append("environment mismatch")
        if manifest.get("aws_account_id") != target_account:
            errors.append("account mismatch")
        if manifest.get("aws_region") != target_region:
            errors.append("region mismatch")
        if manifest.get("backup_status") != "SUCCESS":
            errors.append(f"backup status is {manifest.get('backup_status')}, expected SUCCESS")
        if errors:
            raise PermissionError("Restore blocked: " + "; ".join(errors))

class RestoreEngine:
    def __init__(self, aws_region: str):
        self.client = None
        self.aws_region = aws_region

    def validate(self, manifest: dict, target_project: str, target_environment: str, target_account: str, target_region: str) -> bool:
        RestoreValidator.validate_manifest(manifest, target_project, target_environment, target_account, target_region)
        return True
