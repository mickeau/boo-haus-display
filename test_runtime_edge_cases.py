#!/usr/bin/env python3
"""
Focused tests for small runtime utility edge cases.

Run with:
    python3 test_runtime_edge_cases.py
"""

import json
import logging
import tempfile
from pathlib import Path

import add_birthday
from button_handler import ButtonHandler
from date_handler import DateHandler


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_button_handler_disabled_does_not_require_gpio():
    handler = ButtonHandler(enabled=False)

    assert_true(handler.enabled is False, "disabled button handler should stay disabled")
    assert_true(handler.gpiod_available is False, "disabled button handler should not import gpiod")
    assert_true(handler._get_button_name(5) == "A", "GPIO 5 should map to button A")
    assert_true(handler._get_button_name(99) is None, "unknown GPIO pin should not map to a button")


def test_button_handler_debounces_and_contains_callback_errors():
    handler = ButtonHandler(enabled=False)
    calls = []

    def callback():
        calls.append("called")

    handler.set_callback("A", callback)

    assert_true(handler._handle_button_press("A", 5, now=10.0) is True, "first press should be accepted")
    assert_true(handler._handle_button_press("A", 5, now=10.1) is False, "second press should be debounced")
    assert_true(handler._handle_button_press("A", 5, now=10.6) is True, "press after debounce should be accepted")
    assert_true(calls == ["called", "called"], "callback should run only for accepted presses")

    handler.set_callback("B", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    previous_disabled = logging.getLogger("button_handler").disabled
    logging.getLogger("button_handler").disabled = True
    try:
        accepted = handler._handle_button_press("B", 6, now=10.0)
    finally:
        logging.getLogger("button_handler").disabled = previous_disabled

    assert_true(accepted is True, "callback errors should not escape")


def test_add_birthday_sanitizes_and_saves_atomically():
    with tempfile.TemporaryDirectory() as tmpdir:
        birthday_file = Path(tmpdir) / "birthdays.json"
        birthday_file.write_text(
            json.dumps([
                {"name": "  Ada  ", "month": "12", "day": "10"},
                {"name": "", "month": 1, "day": 1},
                {"name": "Broken", "month": 99, "day": 99},
                "not-a-row",
            ]),
            encoding="utf-8",
        )

        birthdays = add_birthday.load_birthdays(birthday_file)
        assert_true(
            birthdays == [{"name": "Ada", "month": 12, "day": 10, "date": "12-10"}],
            "load should keep only normalized birthday rows",
        )

        add_birthday.save_birthdays(
            [
                {"name": "Later", "month": 12, "day": 10},
                {"name": "Sooner", "month": 1, "day": 2},
                {"name": "Invalid", "month": 2, "day": 31},
            ],
            birthday_file,
        )

        saved = json.loads(birthday_file.read_text(encoding="utf-8"))

    assert_true([row["name"] for row in saved] == ["Sooner", "Later"], "save should sort valid rows")
    assert_true(saved[0]["date"] == "01-02", "save should regenerate canonical date strings")


def test_date_handler_url_extraction_rejects_ambiguous_dates():
    month_map = {"jan": 1, "sep": 9}
    pattern = r"/(\d{1,2})-([a-z]{3})-(\d{4})/"

    valid = DateHandler.extract_date_from_url("/news/11-sep-2026/story", pattern, month_map)
    unknown_month = DateHandler.extract_date_from_url("/news/11-xxx-2026/story", pattern, month_map)
    bad_pattern = DateHandler.extract_date_from_url("/news/11-sep-2026/story", r"/(\d{1,2})/", month_map)

    assert_true(valid.startswith("2026-09-11T00:00:00"), "known month should produce ISO datetime")
    assert_true(unknown_month is None, "unknown month should not default to January")
    assert_true(bad_pattern is None, "pattern without day/month/year groups should be ignored")


def test_dashboard_parses_edges_when_flask_available():
    try:
        import web_dashboard
    except ImportError:
        return

    assert_true(web_dashboard.parse_line_count("bad") == 80, "bad line count should use default")
    assert_true(web_dashboard.parse_line_count("-10") == 1, "line count should be clamped to minimum")
    assert_true(web_dashboard.parse_line_count("9999") == 500, "line count should be clamped to maximum")

    previous_config_file = web_dashboard.CONFIG_FILE
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "boo_haus_config.json"
        config_file.write_text(json.dumps({"screens": {}}), encoding="utf-8")
        try:
            web_dashboard.CONFIG_FILE = config_file
            client = web_dashboard.app.test_client()

            unknown = client.post("/api/screen/not-a-screen/toggle")
            malformed = client.post("/api/config", data="{bad json", content_type="application/json")
        finally:
            web_dashboard.CONFIG_FILE = previous_config_file

    assert_true(unknown.status_code == 404, "unknown screen toggle should be rejected")
    assert_true(malformed.status_code == 400, "malformed config JSON should be rejected")


def main():
    tests = [
        test_button_handler_disabled_does_not_require_gpio,
        test_button_handler_debounces_and_contains_callback_errors,
        test_add_birthday_sanitizes_and_saves_atomically,
        test_date_handler_url_extraction_rejects_ambiguous_dates,
        test_dashboard_parses_edges_when_flask_available,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} runtime edge-case tests")


if __name__ == "__main__":
    main()
