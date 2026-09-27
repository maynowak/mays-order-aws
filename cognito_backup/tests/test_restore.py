from cognito_backup.restore import RestoreValidator

def test_cross_project_block():
    manifest = {
        "project_name": "mays-orders",
        "environment": "Development",
        "aws_account_id": "123",
        "aws_region": "eu-central-1",
        "backup_status": "SUCCESS"
    }
    try:
        RestoreValidator.validate_manifest(manifest, "mays-order-par", "Development", "123", "eu-central-1")
        assert False, "Should have blocked"
    except PermissionError as e:
        assert "project_name mismatch" in str(e)
        print("PASS cross project block")

if __name__ == "__main__":
    test_cross_project_block()
