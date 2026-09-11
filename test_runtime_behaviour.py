#!/usr/bin/env python3
"""
Runtime behavior tests for service-mode control paths.

Run with:
    python3 test_runtime_behaviour.py
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

from boo_haus_main import BooHausDisplayManager


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_manager_starts_without_buttons_by_default():
    manager = BooHausDisplayManager()

    assert_true(manager.button_handler is None, "buttons should be inactive outside --cycle mode")
    assert_true(len(manager.screens) > 0, "manager should initialize available screens")


def test_requested_screen_is_consumed_by_name():
    manager = BooHausDisplayManager()
    displayed = []

    with tempfile.TemporaryDirectory() as tmpdir:
        manager.state_file = os.path.join(tmpdir, "display_state.json")
        manager.state = {
            "current_screen": 0,
            "last_update": None,
            "last_news_scrape": "2099-01-01T00:00:00",
            "requested_screen": "news",
        }
        manager.check_and_run_news_scraper = lambda: None
        manager.display_screen = lambda index: displayed.append(manager.screens[index].name)

        manager.cycle_once()

        with open(manager.state_file, "r", encoding="utf-8") as f:
            saved_state = json.load(f)

    assert_true(displayed == ["news"], "requested screen should be displayed by name")
    assert_true("requested_screen" not in saved_state, "requested screen should be cleared after use")
    assert_true(
        saved_state["current_screen"] == manager.get_screen_index_by_name("news"),
        "state index should match the live manager screen list",
    )


def test_calendar_fetcher_imports_without_optional_google_dependencies():
    import calendar_fetcher

    assert_true(
        hasattr(calendar_fetcher, "CalendarData"),
        "calendar_fetcher should import even when optional Google dependencies are absent",
    )

    if calendar_fetcher.GOOGLE_IMPORT_ERROR is not None:
        fetcher = calendar_fetcher.CalendarData([])
        assert_true(fetcher.authenticate() is False, "missing Google dependencies should disable authentication cleanly")


def test_legacy_display_wrappers_import_without_optional_integrations():
    import birthday_tracker
    import calendar_display

    assert_true(hasattr(birthday_tracker, "main"), "birthday_tracker should expose a CLI main")
    assert_true(hasattr(calendar_display, "main"), "calendar_display should expose a CLI main")


def test_calendar_fetcher_skips_malformed_api_events():
    import calendar_fetcher

    class FakeCalendarRequest:
        def execute(self):
            valid_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            return {
                "items": [
                    {"summary": "Valid Event", "start": {"dateTime": valid_date}, "end": {"dateTime": valid_date}},
                    "not-an-event",
                ]
            }

    class FakeEventsResource:
        def list(self, **kwargs):
            return FakeCalendarRequest()

    class FakeCalendarService:
        def events(self):
            return FakeEventsResource()

    with tempfile.TemporaryDirectory() as tmpdir:
        fetcher = calendar_fetcher.CalendarData(["home"])
        fetcher.cache_file = os.path.join(tmpdir, "calendar_cache.json")
        fetcher._cache = {"timestamp": None, "data": None}
        fetcher.service = FakeCalendarService()

        events = fetcher.fetch_data(force_refresh=True, max_results=5, days_ahead=7)

    assert_true(len(events) == 1, "malformed calendar API events should be skipped")
    assert_true(events[0]["summary"] == "Valid Event", "valid calendar API events should be preserved")
    assert_true(events[0]["calendar_id"] == "home", "calendar id should be added to valid events")


def main():
    tests = [
        test_manager_starts_without_buttons_by_default,
        test_requested_screen_is_consumed_by_name,
        test_calendar_fetcher_imports_without_optional_google_dependencies,
        test_legacy_display_wrappers_import_without_optional_integrations,
        test_calendar_fetcher_skips_malformed_api_events,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} runtime behavior tests")


if __name__ == "__main__":
    main()
