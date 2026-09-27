import os
import json
from cognito_backup.backup import BackupEngine

def handler(event, context):
    project_name = os.environ.get('PROJECT_NAME')
    environment = os.environ.get('ENVIRONMENT')
    aws_account_id = os.environ.get('AWS_ACCOUNT_ID')
    aws_region = os.environ.get('AWS_REGION')
    user_pool_id = os.environ.get('USER_POOL_ID')
    user_pool_name = os.environ.get('USER_POOL_NAME')
    bucket_name = os.environ.get('BUCKET_NAME')

    if not all([project_name, environment, aws_account_id, aws_region, user_pool_id, user_pool_name, bucket_name]):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing environment variables'})
        }

    engine = BackupEngine(
        project_name=project_name,
        environment=environment,
        aws_account_id=aws_account_id,
        aws_region=aws_region,
        user_pool_id=user_pool_id,
        user_pool_name=user_pool_name,
        bucket_name=bucket_name
    )
    result = engine.run()
    status = 200 if result.get('backup_status') == 'SUCCESS' else 500
    return {
        'statusCode': status,
        'body': json.dumps(result)
    }
