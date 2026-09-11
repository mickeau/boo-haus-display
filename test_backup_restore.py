#!/usr/bin/env python3
"""
Tests for backup/restore safety.

Run with:
    python3 test_backup_restore.py
"""

import io
import tarfile
import tempfile
from pathlib import Path

from backup_restore import BackupManager


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def add_text_member(tar, name, text):
    payload = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    tar.addfile(info, io.BytesIO(payload))


def test_safe_restore_extracts_inside_project_root():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        backup = root / "backup.tar.gz"
        with tarfile.open(backup, "w:gz") as tar:
            add_text_member(tar, "restored.txt", "ok")

        manager = BackupManager(backup_dir=root / "backups")
        manager.project_root = root

        assert_true(manager.restore_backup(backup, dry_run=True), "safe dry run should pass")
        assert_true(manager.restore_backup(backup, dry_run=False, confirm=False), "safe restore should pass")
        assert_true((root / "restored.txt").read_text() == "ok", "safe member should be restored")


def test_restore_rejects_path_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        backup = root / "evil.tar.gz"
        with tarfile.open(backup, "w:gz") as tar:
            add_text_member(tar, "../escape.txt", "bad")

        manager = BackupManager(backup_dir=root / "backups")
        manager.project_root = root

        assert_true(not manager.restore_backup(backup, dry_run=True), "path traversal should be rejected")
        assert_true(not (root.parent / "escape.txt").exists(), "unsafe member must not be written")


def main():
    tests = [
        test_safe_restore_extracts_inside_project_root,
        test_restore_rejects_path_traversal,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} backup restore tests")


if __name__ == "__main__":
    main()
