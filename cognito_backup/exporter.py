import boto3
from typing import List, Dict, Any
from botocore.exceptions import ClientError

class CognitoExporter:
    def __init__(self, region: str):
        self.client = boto3.client("cognito-idp", region_name=region)

    def export_users(self, user_pool_id: str, max_results: int = 60) -> List[Dict[str, Any]]:
        users = []
        pagination_token = None
        while True:
            try:
                kwargs = {"UserPoolId": user_pool_id, "MaxResults": max_results}
                if pagination_token:
                    kwargs["PaginationToken"] = pagination_token
                response = self.client.list_users(**kwargs)
                users.extend(response.get("Users", []))
                pagination_token = response.get("PaginationToken")
                if not pagination_token:
                    break
            except ClientError as e:
                raise RuntimeError(f"Failed to list users: {e}")
        return users

    def export_groups(self, user_pool_id: str) -> List[Dict[str, Any]]:
        groups = []
        next_token = None
        while True:
            try:
                kwargs = {"UserPoolId": user_pool_id}
                if next_token:
                    kwargs["NextToken"] = next_token
                response = self.client.list_groups(**kwargs)
                groups.extend(response.get("Groups", []))
                next_token = response.get("NextToken")
                if not next_token:
                    break
            except ClientError as e:
                raise RuntimeError(f"Failed to list groups: {e}")
        return groups
