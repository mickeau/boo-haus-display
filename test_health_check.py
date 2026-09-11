#!/usr/bin/env python3
"""
Tests for health_check diagnostics.

Run with:
    python3 test_health_check.py
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import health_check


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def restore_env(key, previous_value):
    if previous_value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = previous_value


class FakeConfig:
    def __init__(self, root, paths=None, screens=None):
        self.project_root = Path(root)
        self.paths = paths or {}
        self.screens = screens or {
            'weather': {'enabled': True},
            'week': {'enabled': True},
            'news': {'enabled': True},
        }
        self.using_example_only = False

    def runtime_path(self, key, default):
        return str(self.project_root / self.paths.get(key, default))

    def resolve_path(self, path):
        return self.project_root / path

    def has_real_value(self, key):
        return True

    def get(self, key, default=None):
        if key == 'screens':
            return self.screens
        return default


def write_json(path, data):
    path.write_text(json.dumps(data), encoding='utf-8')


def test_news_cache_counts_raw_story_lists():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        raw_file = root / "combined_news_recent.json"
        write_json(raw_file, [
            {"title": "Story one"},
            {"title": "Story two"},
            {"title": "Story three"},
            {"title": "Story four"},
            {"title": "Story five"},
        ])

        old_config = health_check.config
        health_check.config = FakeConfig(root)
        try:
            checker = health_check.HealthChecker()
            checker.check_news_cache()
        finally:
            health_check.config = old_config

    assert_true(not checker.issues, "raw list-shaped news DB should not be reported unreadable")
    assert_true(any("5 news stories" in item for item in checker.info), "raw list count should be reported")


def test_last_update_handles_timezone_aware_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        state_file = root / "display_state.json"
        write_json(state_file, {
            "last_update": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        })

        old_config = health_check.config
        health_check.config = FakeConfig(root)
        try:
            checker = health_check.HealthChecker()
            checker.check_last_update()
        finally:
            health_check.config = old_config

    assert_true(not checker.issues, "timezone-aware state timestamp should not raise a health issue")
    assert_true(any("Display updated" in item for item in checker.info), "recent update should be reported")


def test_offline_data_source_check_does_not_call_network():
    old_http_get = health_check.http_get
    old_offline = os.environ.get("BOO_HAUS_OFFLINE")
    os.environ["BOO_HAUS_OFFLINE"] = "1"
    health_check.http_get = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called"))

    try:
        checker = health_check.HealthChecker()
        checker.check_data_sources()
    finally:
        health_check.http_get = old_http_get
        restore_env("BOO_HAUS_OFFLINE", old_offline)

    assert_true(not checker.warnings, "offline data-source check should not warn about unreachable services")
    assert_true(any("Network checks skipped" in item for item in checker.info), "offline skip should be reported")


def test_malformed_screens_config_reports_issue():
    with tempfile.TemporaryDirectory() as tmpdir:
        old_config = health_check.config
        health_check.config = FakeConfig(tmpdir, screens=["not", "a", "dict"])
        try:
            checker = health_check.HealthChecker()
            checker.check_configuration()
        finally:
            health_check.config = old_config

    assert_true(
        any("screens section" in item for item in checker.issues),
        "malformed screens config should be reported as a health issue",
    )


def test_json_cli_outputs_parseable_json():
    result = subprocess.run(
        [sys.executable, "health_check.py", "--skip-network", "--json"],
        cwd=Path(__file__).resolve().parent,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)

    assert_true(payload["status"] in {"healthy", "warning", "critical"}, "JSON status should be structured")
    assert_true(isinstance(payload["issues"], list), "JSON issues should be a list")
    assert_true(result.returncode in {0, 1, 2}, "health CLI should return documented status codes")


def main():
    tests = [
        test_news_cache_counts_raw_story_lists,
        test_last_update_handles_timezone_aware_state,
        test_offline_data_source_check_does_not_call_network,
        test_malformed_screens_config_reports_issue,
        test_json_cli_outputs_parseable_json,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} health check tests")


if __name__ == "__main__":
    main()
