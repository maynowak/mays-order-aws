"""MO-BUILDER-UPGRADE-P2-01: Builder-Upgrade (Manifest, Diff, Apply).

Rein lokal: temporaere Verzeichnisse, keine AWS-/Terraform-Aufrufe.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from module_builder.builder import build
from module_builder.upgrade import (
    ADD,
    BLOCKED,
    CODE_CONFLICT,
    CONFLICT,
    CONFLICTED_PROJECT,
    LEGACY_PROJECT,
    MANAGED_PROJECT,
    MANIFEST_NAME,
    NEW_PROJECT,
    NO_CHANGES,
    READY,
    REMOVE_CANDIDATE,
    REVIEW_REQUIRED,
    UNCHANGED,
    UNVERIFIED_PROJECT,
    UPDATE_SAFE,
    USER_MODIFIED,
    USER_OWNED,
    BuilderUpgradeError,
    apply_upgrade,
    build_report,
    decide_status,
    detect_project_status,
    diff_project,
    safe_target,
    sha256_file,
)
from module_builder.cli import main as builder_main


def _manifest(files: dict, **overrides) -> dict:
    data = {
        "manifest_version": 2,
        "builder_version": "0.1.0",
        "preset": "custom",
        "modules": ["dynamodb"],
        "project_name": "up-test",
        "generated_at": "2026-11-01T00:00:00+00:00",
        "source": {"repo": "maynowak/mays-order-aws", "commit": "a" * 40},
        "files": files,
    }
    data.update(overrides)
    return data


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _hashes(root: Path, rels) -> dict:
    return {rel: sha256_file(root / rel) for rel in rels}


class TestProjectIdentity(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_missing_directory_is_new(self):
        status, manifest, _ = detect_project_status(self.root / "nope")
        self.assertEqual(status, NEW_PROJECT)
        self.assertIsNone(manifest)

    def test_empty_directory_is_new(self):
        (self.root / "empty").mkdir()
        self.assertEqual(detect_project_status(self.root / "empty")[0], NEW_PROJECT)

    def test_directory_without_manifest_is_unverified(self):
        (self.root / "foreign").mkdir()
        (self.root / "foreign" / "main.tf").write_text("")
        self.assertEqual(
            detect_project_status(self.root / "foreign")[0], UNVERIFIED_PROJECT
        )

    def test_invalid_manifest_is_unverified(self):
        (self.root / "bad").mkdir()
        (self.root / "bad" / MANIFEST_NAME).write_text("{not json")
        self.assertEqual(detect_project_status(self.root / "bad")[0], UNVERIFIED_PROJECT)

    def test_legacy_manifest_without_fingerprints(self):
        (self.root / "legacy").mkdir()
        data = {"builder_version": "0.1.0", "project_name": "up-test",
                "files_written": ["terraform/main.tf"]}
        (self.root / "legacy" / MANIFEST_NAME).write_text(json.dumps(data))
        status, _, reasons = detect_project_status(self.root / "legacy")
        self.assertEqual(status, LEGACY_PROJECT)
        self.assertIn("Legacy", reasons[0])

    def test_project_name_mismatch_is_conflicted(self):
        (self.root / "p").mkdir()
        (self.root / "p" / "a.tf").write_text("x")
        (self.root / "p" / MANIFEST_NAME).write_text(
            json.dumps(_manifest({"a.tf": sha256_file(self.root / "p" / "a.tf")}))
        )
        status, _, _ = detect_project_status(self.root / "p", expected_project_name="other")
        self.assertEqual(status, CONFLICTED_PROJECT)

    def test_managed_project_detected(self):
        (self.root / "p").mkdir()
        _write(self.root / "p", "a.tf", "x")
        files = {"a.tf": sha256_file(self.root / "p" / "a.tf")}
        (self.root / "p" / MANIFEST_NAME).write_text(json.dumps(_manifest(files)))
        self.assertEqual(detect_project_status(self.root / "p")[0], MANAGED_PROJECT)

    def test_manifest_path_traversal_is_conflicted(self):
        (self.root / "p").mkdir()
        (self.root / "p" / MANIFEST_NAME).write_text(
            json.dumps(_manifest({"../evil.tf": "0" * 64}))
        )
        self.assertEqual(detect_project_status(self.root / "p")[0], CONFLICTED_PROJECT)


class TestDiff(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.tree = self.root / "tree"
        self.project.mkdir()
        self.tree.mkdir()

    def _diff(self, managed: dict, disk: dict, new: dict):
        for rel, content in disk.items():
            _write(self.project, rel, content)
        for rel, content in new.items():
            _write(self.tree, rel, content)
        return diff_project(self.project, self.tree, _manifest(managed))

    def test_unchanged(self):
        _write(self.project, "a.tf", "same")
        _write(self.tree, "a.tf", "same")
        diff = diff_project(self.project, self.tree, _manifest(_hashes(self.project, ["a.tf"])))
        self.assertEqual(diff.by_category(UNCHANGED)[0].path, "a.tf")
        self.assertEqual(decide_status(MANAGED_PROJECT, diff)[0], NO_CHANGES)

    def test_add(self):
        _write(self.tree, "new.tf", "new")
        diff = diff_project(self.project, self.tree, _manifest({}))
        self.assertEqual(diff.by_category(ADD)[0].path, "new.tf")
        self.assertEqual(decide_status(MANAGED_PROJECT, diff)[0], READY)

    def test_update_safe(self):
        _write(self.project, "a.tf", "old")
        _write(self.tree, "a.tf", "new")
        diff = diff_project(
            self.project, self.tree, _manifest(_hashes(self.project, ["a.tf"]))
        )
        entry = diff.entries[0]
        self.assertEqual(entry.category, UPDATE_SAFE)
        self.assertEqual(decide_status(MANAGED_PROJECT, diff)[0], READY)

    def test_user_modified_conflict(self):
        _write(self.project, "a.tf", "user")
        _write(self.tree, "a.tf", "new")
        managed = {"a.tf": "0" * 64}
        diff = diff_project(self.project, self.tree, _manifest(managed))
        self.assertEqual(diff.entries[0].category, CONFLICT)
        self.assertEqual(decide_status(MANAGED_PROJECT, diff), (BLOCKED, CODE_CONFLICT))

    def test_user_modified_but_already_target(self):
        _write(self.project, "a.tf", "same")
        _write(self.tree, "a.tf", "same")
        diff = diff_project(self.project, self.tree, _manifest({"a.tf": "0" * 64}))
        self.assertEqual(diff.entries[0].category, USER_MODIFIED)
        self.assertEqual(decide_status(MANAGED_PROJECT, diff)[0], REVIEW_REQUIRED)

    def test_unmanaged_file_at_target_path_conflict(self):
        _write(self.project, "a.tf", "user")
        _write(self.tree, "a.tf", "new")
        diff = diff_project(self.project, self.tree, _manifest({}))
        self.assertEqual(diff.entries[0].category, CONFLICT)

    def test_managed_file_deleted_by_user(self):
        _write(self.tree, "a.tf", "new")
        diff = diff_project(self.project, self.tree, _manifest({"a.tf": "0" * 64}))
        self.assertEqual(diff.entries[0].category, USER_MODIFIED)
        self.assertEqual(decide_status(MANAGED_PROJECT, diff)[0], REVIEW_REQUIRED)

    def test_remove_candidate_is_not_deleted(self):
        _write(self.project, "old.tf", "old")
        _write(self.tree, "new.tf", "new")
        diff = diff_project(self.project, self.tree, _manifest({"old.tf": "0" * 64}))
        self.assertEqual(diff.by_category(REMOVE_CANDIDATE)[0].path, "old.tf")
        self.assertEqual(decide_status(MANAGED_PROJECT, diff)[0], REVIEW_REQUIRED)

    def test_user_config_is_preserved(self):
        _write(self.project, "terraform.tfvars", 'project_name = "up-test"')
        _write(self.project, ".env.local", "SECRET=1")
        _write(self.tree, "a.tf", "x")
        diff = diff_project(self.project, self.tree, _manifest({}))
        self.assertIn("terraform.tfvars", diff.config_preserved)
        self.assertIn(".env.local", diff.config_preserved)
        self.assertFalse(any(entry.path == "terraform.tfvars" for entry in diff.entries))

    def test_user_owned_unknown_file_reported(self):
        _write(self.project, "notes.md", "mine")
        _write(self.tree, "a.tf", "x")
        diff = diff_project(self.project, self.tree, _manifest({}))
        self.assertEqual(diff.by_category(USER_OWNED)[0].path, "notes.md")

    def test_new_and_removed_parameters(self):
        _write(self.project, "terraform/variables.tf", 'variable "a" {}\nvariable "old" {}\n')
        _write(self.tree, "terraform/variables.tf", 'variable "a" {}\nvariable "new" {}\n')
        diff = diff_project(self.project, self.tree, _manifest({}))
        self.assertEqual(diff.new_parameters, ["new"])
        self.assertEqual(diff.removed_parameters, ["old"])


class TestApply(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.tree = self.root / "tree"
        self.project.mkdir()
        self.tree.mkdir()
        _write(self.project, "keep.tf", "keep")
        _write(self.tree, "keep.tf", "keep")
        _write(self.tree, "add.tf", "added")
        self.manifest = _manifest(_hashes(self.project, ["keep.tf"]))

    def _diff(self):
        return diff_project(self.project, self.tree, self.manifest)

    def test_apply_writes_only_safe_changes(self):
        diff = self._diff()
        result = apply_upgrade(
            self.project, self.tree, diff,
            new_manifest={**self.manifest, "builder_version": "0.1.0"},
            previous_manifest=self.manifest,
        )
        self.assertEqual(result["written"], ["add.tf"])
        self.assertTrue((self.project / "add.tf").exists())
        manifest = json.loads((self.project / MANIFEST_NAME).read_text())
        self.assertIn("add.tf", manifest["files"])
        self.assertEqual(manifest["manifest_version"], 2)

    def test_apply_refuses_conflicts(self):
        _write(self.project, "keep.tf", "user")
        diff = self._diff()
        with self.assertRaises(BuilderUpgradeError):
            apply_upgrade(
                self.project, self.tree, diff,
                new_manifest=self.manifest, previous_manifest=self.manifest,
            )
        self.assertEqual((self.project / "keep.tf").read_text(), "user")

    def test_apply_does_not_delete_removed_files(self):
        _write(self.project, "old.tf", "old")
        diff = self._diff()
        apply_upgrade(
            self.project, self.tree, diff,
            new_manifest=self.manifest, previous_manifest=self.manifest,
        )
        self.assertTrue((self.project / "old.tf").exists())

    def test_apply_keeps_user_modified_files(self):
        _write(self.project, "keep.tf", "user")
        # keep.tf wird nicht mehr generiert -> REMOVE_CANDIDATE, keine Loeschung
        (self.tree / "keep.tf").unlink()
        diff = diff_project(self.project, self.tree, self.manifest)
        self.assertEqual(diff.by_category(REMOVE_CANDIDATE)[0].path, "keep.tf")
        apply_upgrade(
            self.project, self.tree, diff,
            new_manifest=self.manifest, previous_manifest=self.manifest,
        )
        self.assertEqual((self.project / "keep.tf").read_text(), "user")

    def test_path_traversal_rejected(self):
        with self.assertRaises(BuilderUpgradeError):
            safe_target(self.project, "../outside.tf")
        with self.assertRaises(BuilderUpgradeError):
            safe_target(self.project, "/etc/passwd")

    def test_symlink_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.project / "link").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(BuilderUpgradeError):
            safe_target(self.project, "link/file.tf")

    def test_write_error_does_not_claim_success(self):
        diff = self._diff()
        before = (self.project / MANIFEST_NAME).exists()
        with patch("module_builder.upgrade.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(BuilderUpgradeError):
                apply_upgrade(
                    self.project, self.tree, diff,
                    new_manifest=self.manifest, previous_manifest=self.manifest,
                )
        self.assertEqual((self.project / MANIFEST_NAME).exists(), before)

    def test_repeat_upgrade_is_idempotent(self):
        diff = self._diff()
        apply_upgrade(
            self.project, self.tree, diff,
            new_manifest={**self.manifest, "files": _hashes(self.tree, _iter_project(self.tree))},
            previous_manifest=self.manifest,
        )
        manifest = json.loads((self.project / MANIFEST_NAME).read_text())
        second = diff_project(self.project, self.tree, manifest)
        self.assertEqual(decide_status(MANAGED_PROJECT, second)[0], NO_CHANGES)


def _iter_project(root: Path):
    return [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]


class TestReport(unittest.TestCase):
    def test_report_has_no_secrets_or_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "p"
            tree = root / "t"
            project.mkdir()
            tree.mkdir()
            _write(tree, "a.tf", "SECRET_TOKEN_123")
            diff = diff_project(project, tree, _manifest({}))
            status, code = decide_status(MANAGED_PROJECT, diff)
            report = build_report(
                project_dir=project, manifest=_manifest({}),
                new_manifest={"builder_version": "0.1.0"},
                diff=diff, project_status=MANAGED_PROJECT,
                status=status, code=code, target_version="0.1.0",
            )
            payload = json.dumps(report)
            self.assertNotIn("SECRET_TOKEN_123", payload)
            self.assertEqual(report["result"]["status"], READY)
            for key in ("project", "builder", "modules", "fileChanges",
                        "configChanges", "conflicts", "security", "result",
                        "manualSteps", "installerPrerequisites"):
                self.assertIn(key, report)


class TestRealBuildAndCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.project = self.root / "proj"
        build(self.project, project_name="up-test", modules=["dynamodb"])

    def test_manifest_v2_written(self):
        manifest = json.loads((self.project / MANIFEST_NAME).read_text())
        self.assertEqual(manifest["manifest_version"], 2)
        self.assertTrue(manifest["files"])
        self.assertIn("terraform/main.tf", manifest["files"])

    def test_dry_run_does_not_change_files(self):
        before = {p.relative_to(self.project).as_posix(): p.read_bytes()
                  for p in self.project.rglob("*") if p.is_file()
                  and ".mays-builder" not in p.parts}
        code = builder_main(["upgrade", "--project", str(self.project), "--dry-run"])
        after = {p.relative_to(self.project).as_posix(): p.read_bytes()
                 for p in self.project.rglob("*") if p.is_file()
                 and ".mays-builder" not in p.parts}
        self.assertEqual(code, 0)
        self.assertEqual(before, after)

    def test_dry_run_detects_conflict(self):
        (self.project / "terraform" / "main.tf").write_text("# user change")
        code = builder_main(["upgrade", "--project", str(self.project), "--dry-run"])
        self.assertEqual(code, 1)

    def test_target_version_mismatch(self):
        code = builder_main([
            "upgrade", "--project", str(self.project), "--dry-run",
            "--target-version", "9.9.9",
        ])
        self.assertEqual(code, 1)

    def test_missing_project(self):
        code = builder_main(["upgrade", "--project", str(self.root / "nope"), "--dry-run"])
        self.assertEqual(code, 1)

    def test_requires_dry_run_or_apply(self):
        code = builder_main(["upgrade", "--project", str(self.project)])
        self.assertEqual(code, 2)

    def test_apply_noop(self):
        code = builder_main(["upgrade", "--project", str(self.project), "--apply"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
