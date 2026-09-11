#!/usr/bin/env python3
"""
Static checks for service and install files.

Run with:
    python3 test_service_install_files.py
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_display_service_loads_env_and_cycles():
    service = read("boo-haus-display.service")

    assert_true("EnvironmentFile=-" in service, "display service should load optional .env")
    assert_true("boo_haus_main.py" in service and "--cycle" in service, "display service should run cycle mode")


def test_dashboard_service_loads_env_and_dashboard():
    service = read("boo-haus-dashboard.service")

    assert_true("EnvironmentFile=-" in service, "dashboard service should load optional .env")
    assert_true("web_dashboard.py" in service, "dashboard service should run web_dashboard.py")


def test_installer_supports_dashboard_and_no_start():
    installer = read("install_service.sh")

    assert_true("--dashboard" in installer, "installer should support dashboard service installation")
    assert_true("--no-start" in installer, "installer should support install-without-start")
    assert_true("EnvironmentFile=-$INSTALL_DIR/.env" in installer, "generated services should load .env")


def test_quick_start_uses_example_config_and_env():
    quick_start = read("quick_start.sh")

    assert_true("requirements.txt" in quick_start, "quick start should install base requirements")
    assert_true("boo_haus_config.example.json" in quick_start, "quick start should build from example config")
    assert_true(".env.example" in quick_start, "quick start should build local .env from template")
    assert_true("gpiod" in quick_start, "quick start should install gpiod with Pi display/button support")
    assert_true("cat > install_service.sh" not in quick_start, "quick start should not generate a stale installer")


def test_requirements_files_cover_optional_integrations():
    requirements = read("requirements.txt")
    optional = read("requirements-optional.txt")
    installer = read("install_all_deps.sh")

    for package in ("pillow", "requests", "beautifulsoup4", "feedparser", "pytz", "flask"):
        assert_true(package in requirements, f"base requirements should include {package}")

    for package in ("anthropic", "google-api-python-client", "gpiod", "inky"):
        assert_true(package in optional, f"optional requirements should include {package}")
        assert_true(package in installer, f"dependency installer should mention {package}")


def test_gitignore_covers_private_runtime_files():
    gitignore = read(".gitignore")

    for path in (
        ".env",
        "boo_haus_config.json",
        "credentials.json",
        "token.json",
        "birthdays.json",
        "waste_collections.json",
        "display_images/",
        "logs/",
        "*_cache.json",
    ):
        assert_true(path in gitignore, f".gitignore should cover {path}")


def test_deployment_checklist_preserves_private_files():
    checklist = read("DEPLOYMENT_CHECKLIST.md")
    readme = read("README.md")

    assert_true("DEPLOYMENT_CHECKLIST.md" in readme, "README should link the deployment checklist")
    assert_true("rsync -av --delete" in checklist, "deployment checklist should include rsync command")

    for path in (
        ".env",
        "boo_haus_config.json",
        "credentials.json",
        "token.json",
        "birthdays.json",
        "combined_news_recent.json",
        "*_cache.json",
        "waste_collections.json",
        "logs/",
        "display_images/",
    ):
        assert_true(path in checklist, f"deployment checklist should preserve {path}")


def main():
    tests = [
        test_display_service_loads_env_and_cycles,
        test_dashboard_service_loads_env_and_dashboard,
        test_installer_supports_dashboard_and_no_start,
        test_quick_start_uses_example_config_and_env,
        test_requirements_files_cover_optional_integrations,
        test_gitignore_covers_private_runtime_files,
        test_deployment_checklist_preserves_private_files,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} service/install file tests")


if __name__ == "__main__":
    main()
