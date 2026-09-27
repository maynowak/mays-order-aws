import sys
sys.path.append("..")
from cognito_backup.manifest import Manifest

def test_manifest_creation():
    m = Manifest("mays-orders", "Development", "123456789012", "eu-central-1", "pool-id", "pool-name")
    d = m.to_dict()
    assert d["project_name"] == "mays-orders"
    assert d["environment"] == "Development"
    assert d["schema_version"] == "1.0"
    print("PASS manifest creation")

if __name__ == "__main__":
    test_manifest_creation()
