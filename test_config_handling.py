#!/usr/bin/env python3
"""
Tests for configuration loading and path handling.

Run with:
    python3 test_config_handling.py
"""

import json
import os
import tempfile
from pathlib import Path

from base_fetcher import BaseFetcher
from config import Config, PROJECT_ROOT, load_env_file
from weather_fetcher import redact_weather_error


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def build_config(config_file=None, project_root=None):
    Config._instance = None
    return Config(config_file=config_file, project_root=project_root)


def restore_env(keys, previous_values):
    for key in keys:
        if previous_values[key] is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous_values[key]


def test_missing_local_config_uses_example_without_creating_real_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_json(root / "boo_haus_config.example.json", {"display": {"width": 800}})

        cfg = build_config(project_root=root)

        assert_true(cfg.get("display.width") == 800, "example config should be loaded as fallback")
        assert_true(cfg.using_example_only, "config should know only the example was loaded")
        assert_true(not (root / "boo_haus_config.json").exists(), "fallback load must not create real config")


def test_local_config_overlays_example_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_json(root / "boo_haus_config.example.json", {
            "display": {"width": 800, "height": 480},
            "screens": {"status": {"enabled": True}},
        })
        write_json(root / "boo_haus_config.json", {
            "display": {"width": 640},
        })

        cfg = build_config(project_root=root)

        assert_true(cfg.get("display.width") == 640, "local config should override defaults")
        assert_true(cfg.get("display.height") == 480, "example defaults should fill missing nested keys")
        assert_true(cfg.get("screens.status.enabled") is True, "new example sections should be retained")
        assert_true(not cfg.using_example_only, "real config should be marked as loaded")


def test_environment_config_file_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_json(root / "boo_haus_config.example.json", {"display": {"width": 800}})
        write_json(root / "custom.json", {"display": {"width": 600}})

        old_env = os.environ.get("BOO_HAUS_CONFIG_FILE")
        os.environ["BOO_HAUS_CONFIG_FILE"] = "custom.json"
        try:
            cfg = build_config(project_root=root)
        finally:
            if old_env is None:
                os.environ.pop("BOO_HAUS_CONFIG_FILE", None)
            else:
                os.environ["BOO_HAUS_CONFIG_FILE"] = old_env

        assert_true(cfg.config_file == "custom.json", "environment config override should be honored")
        assert_true(cfg.get("display.width") == 600, "environment-selected config should load")


def test_dotenv_file_loads_without_overriding_existing_environment():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        env_file = root / ".env"
        env_file.write_text(
            "\n".join([
                "# local secrets",
                "ANTHROPIC_API_KEY=from-dotenv",
                "OPENWEATHER_API_KEY='from-dotenv-weather'",
            ]),
            encoding="utf-8",
        )

        keys = ["ANTHROPIC_API_KEY", "OPENWEATHER_API_KEY"]
        previous = {key: os.environ.get(key) for key in keys}
        os.environ["ANTHROPIC_API_KEY"] = "from-process-env"
        os.environ.pop("OPENWEATHER_API_KEY", None)
        try:
            loaded_path = load_env_file(root)

            assert_true(loaded_path == env_file, ".env loader should report the loaded file")
            assert_true(os.environ["ANTHROPIC_API_KEY"] == "from-process-env", ".env must not override process env")
            assert_true(os.environ["OPENWEATHER_API_KEY"] == "from-dotenv-weather", "quoted .env values should load")
        finally:
            restore_env(keys, previous)


def test_api_key_environment_overrides_config_placeholders():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_json(root / "boo_haus_config.example.json", {
            "api_keys": {
                "openweather": "YOUR_OPENWEATHER_API_KEY_HERE",
                "anthropic": "YOUR_ANTHROPIC_API_KEY_HERE",
            }
        })

        keys = ["ANTHROPIC_API_KEY", "OPENWEATHER_API_KEY"]
        previous = {key: os.environ.get(key) for key in keys}
        os.environ["ANTHROPIC_API_KEY"] = "real-anthropic-key"
        os.environ["OPENWEATHER_API_KEY"] = "real-weather-key"
        try:
            cfg = build_config(project_root=root)

            assert_true(cfg.get("api_keys.anthropic") == "real-anthropic-key", "Anthropic env key should override config")
            assert_true(cfg.get("api_keys.openweather") == "real-weather-key", "OpenWeather env key should override config")
            assert_true(cfg.has_real_value("api_keys.anthropic"), "Anthropic env key should count as configured")
        finally:
            restore_env(keys, previous)


def test_environment_api_keys_are_not_persisted_on_save():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        config_path = root / "boo_haus_config.json"
        write_json(root / "boo_haus_config.example.json", {
            "api_keys": {
                "anthropic": "YOUR_ANTHROPIC_API_KEY_HERE",
            }
        })
        write_json(config_path, {
            "api_keys": {
                "anthropic": "YOUR_ANTHROPIC_API_KEY_HERE",
            }
        })

        keys = ["ANTHROPIC_API_KEY"]
        previous = {key: os.environ.get(key) for key in keys}
        os.environ["ANTHROPIC_API_KEY"] = "real-anthropic-key"
        try:
            cfg = build_config(project_root=root)
            cfg.set("display.width", 800)

            saved = json.loads(config_path.read_text(encoding="utf-8"))
            assert_true(cfg.get("api_keys.anthropic") == "real-anthropic-key", "env key should be available at read time")
            assert_true(
                saved["api_keys"]["anthropic"] == "YOUR_ANTHROPIC_API_KEY_HERE",
                "saving config should not persist env-provided API keys",
            )
        finally:
            restore_env(keys, previous)


def test_runtime_path_is_project_root_relative():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_json(root / "boo_haus_config.example.json", {"state_file": "state/display.json"})

        cfg = build_config(project_root=root)

        assert_true(
            cfg.runtime_path("state_file", "display_state.json") == str(root / "state/display.json"),
            "relative runtime paths should resolve under project root",
        )


def test_placeholder_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_json(root / "boo_haus_config.example.json", {
            "api_keys": {
                "openweather": "YOUR_OPENWEATHER_API_KEY_HERE",
                "anthropic": "REPLACE_WITH_ANTHROPIC_KEY",
                "other": "real-value",
            }
        })

        keys = ["ANTHROPIC_API_KEY", "OPENWEATHER_API_KEY"]
        previous = {key: os.environ.get(key) for key in keys}
        for key in keys:
            os.environ.pop(key, None)
        try:
            cfg = build_config(project_root=root)

            assert_true(not cfg.has_real_value("api_keys.openweather"), "YOUR_ placeholders should not count as configured")
            assert_true(not cfg.has_real_value("api_keys.anthropic"), "REPLACE_WITH_ placeholders should not count as configured")
            assert_true(cfg.has_real_value("api_keys.other"), "ordinary values should count as configured")
        finally:
            restore_env(keys, previous)


def test_base_fetcher_cache_paths_are_project_root_relative():
    class DummyFetcher(BaseFetcher):
        def _fetch_data_from_source(self):
            return []

    fetcher = DummyFetcher("dummy_runtime_cache.json")

    assert_true(
        fetcher.cache_file == str(PROJECT_ROOT / "dummy_runtime_cache.json"),
        "relative BaseFetcher caches should resolve under project root",
    )


def test_weather_error_redacts_openweather_api_key():
    message = (
        "HTTPSConnectionPool(host='api.openweathermap.org', port=443): "
        "Max retries exceeded with url: "
        "/data/3.0/onecall?lat=50.6208&lon=-3.4131&appid=secret-key-123&exclude=minutely"
    )

    redacted = redact_weather_error(message)

    assert_true("secret-key-123" not in redacted, "weather errors should not expose API keys")
    assert_true("appid=<redacted>" in redacted, "weather errors should show a redacted API key marker")


def main():
    tests = [
        test_missing_local_config_uses_example_without_creating_real_config,
        test_local_config_overlays_example_defaults,
        test_environment_config_file_override,
        test_dotenv_file_loads_without_overriding_existing_environment,
        test_api_key_environment_overrides_config_placeholders,
        test_environment_api_keys_are_not_persisted_on_save,
        test_runtime_path_is_project_root_relative,
        test_placeholder_detection,
        test_base_fetcher_cache_paths_are_project_root_relative,
        test_weather_error_redacts_openweather_api_key,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} config handling tests")


if __name__ == "__main__":
    main()
