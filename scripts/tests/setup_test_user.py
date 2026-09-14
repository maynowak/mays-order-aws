#!/usr/bin/env python3
"""
Setup test user for E2E tests.

Usage:
    export AWS_PROFILE=mayaws
    export TEST_USER_PASSWORD="securePassword123!"
    python3 setup_test_user.py

The script:
1. Creates a Cognito user with email 
2. Sets the password
3. Adds user to 'staff' group
4. Is idempotent (handles existing users)

Security:
- Password is read from TEST_USER_PASSWORD env var
- Never prints the password
- Uses Cognito admin APIs (no CLI)
"""
import os
import sys
import uuid

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "eu-central-1")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "eu-central-1_XXXXXXXX")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
TEST_USER_EMAIL_PREFIX = os.environ.get("TEST_USER_EMAIL_PREFIX", "test-user")


def create_test_user(email: str, password: str) -> dict:
    """Create or update a Cognito test user."""
    cognito = boto3.client("cognito-idp", region_name=AWS_REGION)

    try:
        cognito.admin_create_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            MessageAction="SUPPRESS",
        )
        print(f"Created test user: {email}")
    except cognito.exceptions.UsernameExistsException:
        print(f"Test user already exists: {email}")
    except Exception as e:
        print(f"Error creating user: {e}")
        raise

    try:
        cognito.admin_set_user_password(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email,
            Password=password,
            Permanent=True,
        )
        print(f"Set permanent password for user")
    except Exception as e:
        print(f"Error setting password: {e}")
        raise

    try:
        cognito.admin_add_user_to_group(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email,
            GroupName="staff",
        )
        print(f"Added user to 'staff' group")
    except Exception as e:
        print(f"Warning: Could not add to staff group: {e}")

    return {"email": email, "status": "CONFIRMED"}


def main():
    password = os.environ.get("TEST_USER_PASSWORD")
    if not password:
        print("ERROR: TEST_USER_PASSWORD environment variable not set")
        sys.exit(1)

    email = f"{TEST_USER_EMAIL_PREFIX}_{uuid.uuid4().hex[:8]}@example.com"

    result = create_test_user(email, password)

    user_pool = boto3.client("cognito-idp", region_name=AWS_REGION)
    pools = user_pool.list_user_pools(MaxResults=20)

    test_pool_id = None
    for pool in pools.get("UserPools", []):
        if "mays-orders" in pool["Name"]:
            test_pool_id = pool["Id"]
            break

    if test_pool_id:
        print(f"Using Cognito user pool: {test_pool_id}")
        global COGNITO_USER_POOL_ID
        COGNITO_USER_POOL_ID = test_pool_id

    client = boto3.client("cognito-idp", region_name=AWS_REGION)
    clients = client.list_user_pool_clients(UserPoolId=COGNITO_USER_POOL_ID, MaxResults=20)

    client_id = None
    for c in clients.get("UserPoolClients", []):
        if "mays-orders" in c["ClientName"]:
            client_id = c["ClientId"]
            break

    if client_id:
        print(f"Using Cognito client: {client_id}")
        print(f"TEST_USER_EMAIL={email}")
        print(f"COGNITO_USER_POOL_ID={COGNITO_USER_POOL_ID}")
        print(f"COGNITO_CLIENT_ID={client_id}")
        print("AUTH_TOKEN can now be obtained via USER_PASSWORD_AUTH flow")
    else:
        print("Warning: Could not find Cognito client")

    print(f"\nTest user ready: {email}")


if __name__ == "__main__":
    main()