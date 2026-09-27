import boto3
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any

class S3BackupStorage:
    def __init__(self, bucket_name: str, region: str):
        self.s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket_name

    def _key_prefix(self, project_name: str, environment: str, timestamp: str) -> str:
        return f"{project_name}/{environment}/{timestamp}/"

    def upload_manifest(self, project_name: str, environment: str, timestamp: str, manifest: Dict[str, Any]) -> str:
        prefix = self._key_prefix(project_name, environment, timestamp)
        key = f"{prefix}manifest.json"
        body = json.dumps(manifest, indent=2).encode("utf-8")
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body)
        return key

    def upload_file(self, project_name: str, environment: str, timestamp: str, filename: str, data: bytes) -> str:
        prefix = self._key_prefix(project_name, environment, timestamp)
        key = f"{prefix}{filename}"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def compute_checksum(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
