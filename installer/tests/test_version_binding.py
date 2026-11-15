"""MO-INSTALLER-UPGRADE-VERSIONING-P0B-01: Quellcode- und Versionsbindung.

Rein lokal: git/subprocess und der Terraform-Runner werden gemockt.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from installer.core.deployment_identity import DeploymentId, PlanOperation
from installer.core.plan_manifest import MANIFEST_VERSION, PlanManifest
from installer.core.source_identity import SourceIdentity, resolve_source_identity
from installer.core.version_binding import (
    CODE_LEGACY_SOURCE,
    CODE_MISMATCH,
    CODE_MISSING,
    CODE_SOURCE_DIRTY,
    CODE_SOURCE_UNVERIFIED,
    CODE_STATE_UNREADABLE,
    LEGACY_UNKNOWN,
    UNREADABLE,
    UNVERIFIED,
    VERIFIED,
    check_source_for_plan,
    check_version_binding,
    detect_installed_version,
)

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
DEPLOYMENT_ID = DeploymentId("240571105849", "mays-orders-rc4", "development")


def _manifest(**overrides) -> PlanManifest:
    data = dict(
        deployment_id=DEPLOYMENT_ID,
        operation=PlanOperation.DEPLOY,
        region="eu-central-1",
        workspace="mays-orders-rc4",
        backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate",
                 "region": "eu-central-1", "workspace_key_prefix": "env:"},
        state_key="env:/mays-orders-rc4/terraform.tfstate",
        plan_file="plan.tfplan",
        plan_sha256="x",
        plan_size=1,
        git_commit=COMMIT_A,
        source_version="0.1.0",
        target_version="0.2.0",
        git_dirty=False,
        version_status=VERIFIED,
        version_source="terraform_output",
    )
    data.update(overrides)
    return PlanManifest(**data)


def _identity(commit=COMMIT_A, dirty=False, available=True) -> SourceIdentity:
    return SourceIdentity(available=available, commit=commit if available else None,
                          dirty=dirty if available else None,
                          detached=False, reason="" if available else "no git")


class TestSourceIdentity(unittest.TestCase):
    def _run(self, head=COMMIT_A, status="", symbolic_rc=0, head_rc=0):
        def fake(cmd, **kwargs):
            if "rev-parse" in cmd:
                return SimpleNamespace(returncode=head_rc, stdout=f"{head}\n", stderr="")
            if "status" in cmd:
                return SimpleNamespace(returncode=0, stdout=status, stderr="")
            if "symbolic-ref" in cmd:
                return SimpleNamespace(returncode=symbolic_rc, stdout="refs/heads/main", stderr="")
            raise AssertionError(cmd)

        return fake

    def test_real_repository_commit(self):
        identity = resolve_source_identity()
        self.assertTrue(identity.available, identity.reason)
        self.assertRegex(identity.commit or "", r"^[0-9a-f]{40}$")
        self.assertIsInstance(identity.dirty, bool)

    def test_detached_head_is_supported(self):
        with patch("installer.core.source_identity.subprocess.run",
                   side_effect=self._run(symbolic_rc=1)):
            identity = resolve_source_identity()
        self.assertTrue(identity.available)
        self.assertTrue(identity.detached)
        self.assertEqual(identity.commit, COMMIT_A)

    def test_dirty_tree_detected(self):
        with patch("installer.core.source_identity.subprocess.run",
                   side_effect=self._run(status=" M installer/cli/main.py\n")):
            identity = resolve_source_identity()
        self.assertTrue(identity.dirty)

    def test_missing_git_metadata(self):
        with patch("installer.core.source_identity.subprocess.run",
                   side_effect=FileNotFoundError("git")):
            identity = resolve_source_identity()
        self.assertFalse(identity.available)
        self.assertIsNone(identity.commit)

    def test_invalid_commit_is_rejected(self):
        with patch("installer.core.source_identity.subprocess.run",
                   side_effect=self._run(head="not-a-sha")):
            identity = resolve_source_identity()
        self.assertFalse(identity.available)


class TestInstalledVersion(unittest.TestCase):
    def _runner(self, state_ok=True, state_out="", output_ok=True, output_json="{}"):
        runner = SimpleNamespace()
        runner.state_list = lambda: SimpleNamespace(success=state_ok, stdout=state_out, stderr="")
        runner.output = lambda: SimpleNamespace(success=output_ok, stdout=output_json, stderr="")
        return runner

    def test_new_installation(self):
        installed = detect_installed_version(self._runner(state_out=""))
        self.assertEqual(installed.status, UNVERIFIED)
        self.assertIsNone(installed.version)

    def test_verified_version_from_output(self):
        out = json.dumps({"mo_version": {"value": "0.2.0"}})
        installed = detect_installed_version(
            self._runner(state_out="module.a\n", output_json=out)
        )
        self.assertEqual(installed.status, VERIFIED)
        self.assertEqual(installed.version, "0.2.0")
        self.assertEqual(installed.resources, 1)

    def test_state_without_version_is_legacy(self):
        installed = detect_installed_version(
            self._runner(state_out="module.a\n", output_json="{}")
        )
        self.assertEqual(installed.status, LEGACY_UNKNOWN)
        self.assertIsNone(installed.version)

    def test_unreadable_state(self):
        installed = detect_installed_version(self._runner(state_ok=False))
        self.assertEqual(installed.status, UNREADABLE)


class TestSourcePreflight(unittest.TestCase):
    def test_clean_source_passes(self):
        self.assertTrue(check_source_for_plan(_identity()).ok)

    def test_dirty_source_blocks(self):
        result = check_source_for_plan(_identity(dirty=True))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_SOURCE_DIRTY)

    def test_dirty_source_allowed_with_flag(self):
        self.assertTrue(check_source_for_plan(_identity(dirty=True), allow_dirty_source=True).ok)

    def test_missing_git_blocks(self):
        result = check_source_for_plan(_identity(available=False))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_SOURCE_UNVERIFIED)


class TestVersionBinding(unittest.TestCase):
    def _check(self, manifest, identity=None, installed=None, **kwargs):
        return check_version_binding(
            manifest,
            current_target_version="0.2.0",
            identity=identity or _identity(),
            installed=installed or SimpleNamespace(status=VERIFIED, version="0.1.0", resources=1),
            **kwargs,
        )

    def test_matching_binding_passes(self):
        self.assertTrue(self._check(_manifest()).ok)

    def test_legacy_manifest_v1_is_blocked(self):
        result = self._check(_manifest(manifest_version=1))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_MISSING)

    def test_target_version_mismatch(self):
        result = self._check(_manifest(target_version="0.3.0"))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_MISMATCH)

    def test_commit_changed_between_plan_and_apply(self):
        result = self._check(_manifest(), identity=_identity(commit=COMMIT_B))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_MISMATCH)

    def test_dirty_state_changed(self):
        result = self._check(_manifest(git_dirty=False), identity=_identity(dirty=True))
        self.assertFalse(result.ok)

    def test_dirty_plan_requires_flag(self):
        result = self._check(_manifest(git_dirty=True), identity=_identity(dirty=True))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_SOURCE_DIRTY)

    def test_dirty_plan_allowed_with_flag(self):
        result = self._check(
            _manifest(git_dirty=True),
            identity=_identity(dirty=True),
            allow_dirty_source=True,
        )
        self.assertTrue(result.ok)

    def test_legacy_source_requires_flag(self):
        result = self._check(
            _manifest(
                version_status=LEGACY_UNKNOWN,
                source_version=None,
                version_source="state_without_version",
            ),
            installed=SimpleNamespace(status=LEGACY_UNKNOWN, version=None, resources=3),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_LEGACY_SOURCE)

    def test_legacy_source_allowed_with_flag(self):
        result = self._check(
            _manifest(
                version_status=LEGACY_UNKNOWN,
                source_version=None,
                version_source="state_without_version",
            ),
            installed=SimpleNamespace(status=LEGACY_UNKNOWN, version=None, resources=3),
            allow_legacy_source=True,
        )
        self.assertTrue(result.ok)

    def test_installed_version_differs_from_plan(self):
        result = self._check(
            _manifest(),
            installed=SimpleNamespace(status=VERIFIED, version="0.1.1", resources=3),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_MISMATCH)

    def test_plan_for_new_install_but_state_exists(self):
        result = self._check(
            _manifest(
                version_status=UNVERIFIED,
                source_version=None,
                version_source="no_remote_state",
            ),
            installed=SimpleNamespace(status=LEGACY_UNKNOWN, version=None, resources=2),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_MISMATCH)

    def test_unreadable_state_blocks(self):
        result = self._check(
            _manifest(),
            installed=SimpleNamespace(status=UNREADABLE, version=None, resources=None),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_STATE_UNREADABLE)

    def test_verified_status_without_source_version_is_inconsistent(self):
        result = self._check(_manifest(source_version=None))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, CODE_MISMATCH)


class TestManifestSchemaV2(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.plan = Path(self._tmp.name) / "plan.tfplan"
        self.plan.write_bytes(b"plan")

    def _create(self, **kwargs):
        return PlanManifest.create(
            self.plan,
            deployment_id=DEPLOYMENT_ID,
            operation=PlanOperation.DEPLOY,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend={"type": "s3", "bucket": "b", "key": "terraform.tfstate"},
            **kwargs,
        )

    def test_v2_fields_are_written(self):
        manifest = self._create(
            git_commit=COMMIT_A,
            source_version=None,
            target_version="0.2.0",
            git_dirty=False,
            version_status=LEGACY_UNKNOWN,
            version_source="state_without_version",
        )
        data = manifest.to_dict()
        self.assertEqual(data["manifest_version"], MANIFEST_VERSION)
        self.assertEqual(data["target_version"], "0.2.0")
        self.assertEqual(data["git_commit"], COMMIT_A)
        self.assertFalse(data["git_dirty"])
        self.assertEqual(data["version_status"], LEGACY_UNKNOWN)
        self.assertEqual(data["version_source"], "state_without_version")

    def test_v1_json_is_readable_but_not_upgrade_capable(self):
        self._create(git_commit=COMMIT_A, target_version="0.2.0",
                     git_dirty=False, version_status=UNVERIFIED,
                     version_source="no_remote_state").write(self.plan)
        path = self.plan.with_name(self.plan.name + ".manifest.json")
        data = json.loads(path.read_text())
        data["manifest_version"] = 1
        for key in ("source_version", "target_version", "git_dirty",
                    "version_status", "version_source"):
            data.pop(key, None)
        path.write_text(json.dumps(data))

        manifest = PlanManifest.load(self.plan)
        self.assertEqual(manifest.manifest_version, 1)
        ok, _ = manifest.verify(
            self.plan,
            deployment_id=DEPLOYMENT_ID,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend=SimpleNamespace(comparison_dict=lambda: data["backend"],
                                    state_key=lambda ws: data["state_key"]),
            operation=PlanOperation.DEPLOY,
        )
        self.assertFalse(ok)
        ok, _ = manifest.verify(
            self.plan,
            deployment_id=DEPLOYMENT_ID,
            region="eu-central-1",
            workspace="mays-orders-rc4",
            backend=SimpleNamespace(comparison_dict=lambda: data["backend"],
                                    state_key=lambda ws: data["state_key"]),
            operation=PlanOperation.DEPLOY,
            allow_legacy_manifest=True,
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
