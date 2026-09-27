import json
from datetime import datetime, timezone
from .manifest import Manifest
from .exporter import CognitoExporter
from .storage import S3BackupStorage

class BackupEngine:
    def __init__(self, project_name: str, environment: str, aws_account_id: str, aws_region: str,
                 user_pool_id: str, user_pool_name: str, bucket_name: str):
        self.project_name = project_name
        self.environment = environment
        self.aws_account_id = aws_account_id
        self.aws_region = aws_region
        self.user_pool_id = user_pool_id
        self.user_pool_name = user_pool_name
        self.bucket_name = bucket_name

        self.exporter = CognitoExporter(aws_region)
        self.storage = S3BackupStorage(bucket_name, aws_region)
        self.manifest = Manifest(project_name, environment, aws_account_id, aws_region, user_pool_id, user_pool_name)

    def _preflight_check(self) -> None:
        if not self.project_name or not self.user_pool_id:
            raise ValueError("project_name and user_pool_id are required")
        # Additional checks can be added

    def run(self) -> Dict:
        self._preflight_check()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        try:
            users = self.exporter.export_users(self.user_pool_id)
            groups = self.exporter.export_groups(self.user_pool_id)
            
            user_data = json.dumps(users, default=str).encode("utf-8")
            group_data = json.dumps(groups, default=str).encode("utf-8")
            
            user_checksum = self.storage.compute_checksum(user_data)
            group_checksum = self.storage.compute_checksum(group_data)
            
            self.manifest.user_count = len(users)
            self.manifest.group_count = len(groups)
            self.manifest.export_timestamp = datetime.now(timezone.utc).isoformat()
            self.manifest.backup_status = "SUCCESS"
            
            user_key = self.storage.upload_file(self.project_name, self.environment, timestamp, "users.json", user_data)
            group_key = self.storage.upload_file(self.project_name, self.environment, timestamp, "groups.json", group_data)
            
            self.manifest.files = {
                "users": user_key,
                "groups": group_key
            }
            self.manifest.checksums = {
                "users.json": user_checksum,
                "groups.json": group_checksum
            }
            
            manifest_key = self.storage.upload_manifest(self.project_name, self.environment, timestamp, self.manifest.to_dict())
            self.manifest.files["manifest"] = manifest_key
            
            return self.manifest.to_dict()
        except Exception as e:
            self.manifest.backup_status = "FAILED"
            raise RuntimeError(f"Backup failed: {e}")
