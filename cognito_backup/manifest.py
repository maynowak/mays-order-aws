import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any

SCHEMA_VERSION = "1.0"

class Manifest:
    def __init__(
        self,
        project_name: str,
        environment: str,
        aws_account_id: str,
        aws_region: str,
        source_user_pool_id: str,
        source_user_pool_name: str,
    ):
        self.schema_version = SCHEMA_VERSION
        self.backup_id = self._generate_backup_id()
        self.project_name = project_name
        self.environment = environment
        self.aws_account_id = aws_account_id
        self.aws_region = aws_region
        self.source_user_pool_id = source_user_pool_id
        self.source_user_pool_name = source_user_pool_name
        self.backup_timestamp = datetime.now(timezone.utc).isoformat()
        self.export_timestamp = None
        self.user_count = 0
        self.group_count = 0
        self.files = {}
        self.checksums = {}
        self.backup_status = "PENDING"
        self.tool_version = "0.1.0"

    def _generate_backup_id(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}-{hashlib.sha256(ts.encode()).hexdigest()[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backup_id": self.backup_id,
            "project_name": self.project_name,
            "environment": self.environment,
            "aws_account_id": self.aws_account_id,
            "aws_region": self.aws_region,
            "source_user_pool_id": self.source_user_pool_id,
            "source_user_pool_name": self.source_user_pool_name,
            "backup_timestamp": self.backup_timestamp,
            "export_timestamp": self.export_timestamp,
            "user_count": self.user_count,
            "group_count": self.group_count,
            "files": self.files,
            "checksums": self.checksums,
            "backup_status": self.backup_status,
            "tool_version": self.tool_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        m = cls.__new__(cls)
        m.__dict__.update(data)
        return m
