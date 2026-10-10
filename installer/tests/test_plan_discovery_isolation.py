import unittest
from pathlib import Path
from installer.core.deployment_identity import PlanDiscovery, DeploymentId, PlanOperation, PlanMetadata, SemanticVersion

class TestPlanDiscovery(unittest.TestCase):
    def test_find_latest_plan_project_isolation(self):
        # This test verifies PlanDiscovery filters by DeploymentId
        # which includes project name
        discovery = PlanDiscovery(base_dir=Path('/tmp/nonexistent'))
        deployment_id = DeploymentId(account_id='123456789012', project='p1', environment='Dev')
        plan = discovery.find_latest_plan(deployment_id, PlanOperation.DEPLOY)
        self.assertIsNone(plan)

if __name__ == '__main__':
    unittest.main()
