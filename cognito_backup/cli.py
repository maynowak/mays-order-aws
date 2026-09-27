import argparse
from .backup import BackupEngine

def main():
    parser = argparse.ArgumentParser(description="Cognito User Data Backup")
    subparsers = parser.add_subparsers(dest="command")
    
    backup_parser = subparsers.add_parser("backup", help="Run backup")
    backup_parser.add_argument("--project-name", required=True)
    backup_parser.add_argument("--environment", required=True)
    backup_parser.add_argument("--account-id", required=True)
    backup_parser.add_argument("--region", required=True)
    backup_parser.add_argument("--user-pool-id", required=True)
    backup_parser.add_argument("--user-pool-name", required=True)
    backup_parser.add_argument("--bucket", required=True)
    
    args = parser.parse_args()
    
    if args.command == "backup":
        engine = BackupEngine(
            project_name=args.project_name,
            environment=args.environment,
            aws_account_id=args.account_id,
            aws_region=args.region,
            user_pool_id=args.user_pool_id,
            user_pool_name=args.user_pool_name,
            bucket_name=args.bucket
        )
        result = engine.run()
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    import json
    main()
