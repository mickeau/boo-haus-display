#!/usr/bin/env python3
"""
Tests for shared fetcher behavior.

Run with:
    python3 test_fetcher_behaviour.py
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from base_fetcher import BaseFetcher, sanitize_request_error
from birthday_fetcher import BirthdayFetcher
import bin_collections
import direct_sewage_api
import water_quality
from nfl_scores import NFLWeeklyDisplay


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def restore_env(key, previous_value):
    if previous_value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = previous_value


class CountingFetcher(BaseFetcher):
    def __init__(self, cache_file):
        self.source_calls = 0
        super().__init__(str(cache_file), cache_expiry_minutes=1)

    def _fetch_data_from_source(self):
        self.source_calls += 1
        return {"fresh": True}


class NullFetcher(BaseFetcher):
    def __init__(self, cache_file):
        super().__init__(str(cache_file), cache_expiry_minutes=1)

    def _fetch_data_from_source(self):
        return None


class EmptyListFetcher(BaseFetcher):
    def __init__(self, cache_file):
        super().__init__(str(cache_file), cache_expiry_minutes=1)

    def _fetch_data_from_source(self):
        return []


def write_cache(path, timestamp, data):
    path.write_text(
        json.dumps({"timestamp": timestamp.isoformat(), "data": data}),
        encoding="utf-8",
    )


def test_request_error_redacts_common_secret_query_params():
    message = (
        "GET https://example.test/path?appid=openweather-secret&token=session-secret"
        "&q=exmouth failed"
    )

    redacted = sanitize_request_error(message)

    assert_true("openweather-secret" not in redacted, "appid value should be redacted")
    assert_true("session-secret" not in redacted, "token value should be redacted")
    assert_true("q=exmouth" in redacted, "non-secret query params should remain visible")


def test_offline_mode_returns_stale_cache_without_source_call():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "cache.json"
        write_cache(cache_file, datetime.now() - timedelta(hours=2), {"cached": True})

        old_offline = os.environ.get("BOO_HAUS_OFFLINE")
        os.environ["BOO_HAUS_OFFLINE"] = "1"
        try:
            fetcher = CountingFetcher(cache_file)
            data = fetcher.fetch_data(force_refresh=True)

            assert_true(data == {"cached": True}, "offline mode should return stale cache")
            assert_true(fetcher.source_calls == 0, "offline mode should not call the source")
        finally:
            restore_env("BOO_HAUS_OFFLINE", old_offline)


def test_offline_mode_without_cache_does_not_call_source():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "cache.json"

        old_offline = os.environ.get("BOO_HAUS_OFFLINE")
        os.environ["BOO_HAUS_OFFLINE"] = "1"
        try:
            fetcher = CountingFetcher(cache_file)
            data = fetcher.fetch_data()

            assert_true(data is None, "offline mode without cache should return None")
            assert_true(fetcher.source_calls == 0, "offline mode should not call the source")
        finally:
            restore_env("BOO_HAUS_OFFLINE", old_offline)


def test_failed_fetch_returns_stale_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "cache.json"
        write_cache(cache_file, datetime.now() - timedelta(hours=2), {"cached": True})

        fetcher = NullFetcher(cache_file)
        data = fetcher.fetch_data(force_refresh=True)

        assert_true(data == {"cached": True}, "failed fetch should fall back to stale cache")


def test_empty_list_is_valid_fresh_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "cache.json"

        fetcher = EmptyListFetcher(cache_file)
        data = fetcher.fetch_data(force_refresh=True)

        assert_true(data == [], "empty list should remain valid fetch data")
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
        assert_true(cached["data"] == [], "empty list should be written to cache")


def test_invalid_cache_timestamp_is_treated_as_stale():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "cache.json"
        cache_file.write_text(
            json.dumps({"timestamp": "not-a-date", "data": {"cached": True}}),
            encoding="utf-8",
        )

        old_offline = os.environ.get("BOO_HAUS_OFFLINE")
        os.environ["BOO_HAUS_OFFLINE"] = "1"
        try:
            fetcher = CountingFetcher(cache_file)
            data = fetcher.fetch_data()

            assert_true(data == {"cached": True}, "invalid timestamp cache should remain usable as stale data")
            assert_true(fetcher.source_calls == 0, "offline mode should not call the source")
        finally:
            restore_env("BOO_HAUS_OFFLINE", old_offline)


def test_malformed_cache_root_does_not_crash_fetcher():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "cache.json"
        cache_file.write_text(json.dumps(["not", "a", "cache", "dict"]), encoding="utf-8")

        fetcher = CountingFetcher(cache_file)
        data = fetcher.fetch_data()

        assert_true(data == {"fresh": True}, "malformed cache root should fall back to fresh source data")
        assert_true(fetcher.source_calls == 1, "malformed cache root should trigger one source fetch")


def test_sewage_api_skips_malformed_features():
    old_http_get_json = direct_sewage_api.http_get_json
    direct_sewage_api.http_get_json = lambda *args, **kwargs: {
        "features": [
            {"attributes": {"latitude": 50.62, "longitude": -3.41, "status": 0}},
            "not-a-feature",
            {"attributes": "not-a-dict"},
        ]
    }

    try:
        overflows = direct_sewage_api._fetch_all_overflows()
    finally:
        direct_sewage_api.http_get_json = old_http_get_json

    assert_true(len(overflows) == 1, "only well-formed sewage features should be returned")
    assert_true(overflows[0]["status"] == 0, "valid sewage feature attributes should be preserved")


def test_nfl_fetcher_skips_malformed_events():
    fetcher = NFLWeeklyDisplay()
    current_week_date = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    valid_event = {
        "date": current_week_date,
        "competitions": [{
            "competitors": [
                {"team": {"displayName": "Dallas Cowboys"}, "records": [{"summary": "1-0"}]},
                {"team": {"displayName": "New York Giants"}, "records": [{"summary": "0-1"}]},
            ]
        }],
        "status": {"type": {"name": "STATUS_SCHEDULED"}},
    }
    data = {
        "week": {"number": 1},
        "season": {"type": 2},
        "events": [
            valid_event,
            {"date": current_week_date, "competitions": []},
            {"not": "an event"},
        ],
    }
    fetcher.fetch_data = lambda force_refresh=False: data

    week_label, games, bye_teams = fetcher.get_games_list(format_type='inky')

    assert_true(week_label == "Week 1", "valid week metadata should still be used")
    assert_true(len(games) == 1, "malformed NFL events should be skipped")
    assert_true("Dallas Cowboys" not in bye_teams, "valid game teams should not be marked on bye")


def test_birthday_fetcher_uses_stale_cache_when_file_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "birthdays_cache.json"
        cached_birthdays = [{"name": "Ada", "month": 12, "day": 10}]
        write_cache(cache_file, datetime.now() - timedelta(days=2), cached_birthdays)

        fetcher = BirthdayFetcher()
        fetcher.cache_file = str(cache_file)
        fetcher._cache = fetcher._load_cache()
        fetcher.birthday_file = Path(tmpdir) / "missing_birthdays.json"

        data = fetcher.fetch_data(force_refresh=True)

    assert_true(data == cached_birthdays, "missing birthday file should fall back to stale cache")


def test_birthday_fetcher_empty_file_is_valid_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        birthday_file = Path(tmpdir) / "birthdays.json"
        cache_file = Path(tmpdir) / "birthdays_cache.json"
        birthday_file.write_text("[]", encoding="utf-8")

        fetcher = BirthdayFetcher()
        fetcher.cache_file = str(cache_file)
        fetcher._cache = {"timestamp": None, "data": None}
        fetcher.birthday_file = birthday_file

        data = fetcher.fetch_data(force_refresh=True)

        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)

    assert_true(data == [], "valid empty birthday file should return an empty list")
    assert_true(cached["data"] == [], "valid empty birthday file should be cached")


def test_birthday_fetcher_normalizes_upcoming_birthdays():
    fetcher = BirthdayFetcher()
    tomorrow = (datetime.now().date() + timedelta(days=1))
    later = (datetime.now().date() + timedelta(days=5))
    fetcher.fetch_data = lambda force_refresh=False: [
        {"name": "Later", "month": later.month, "day": later.day},
        {"name": "Tomorrow", "month": tomorrow.month, "day": tomorrow.day},
        {"name": "Broken", "month": 99, "day": 99},
        {"month": tomorrow.month, "day": tomorrow.day},
    ]

    upcoming = fetcher.get_next_birthdays(limit=3)

    assert_true([event["name"] for event in upcoming] == ["Tomorrow", "Later"], "birthdays should be sorted and malformed rows skipped")
    assert_true(upcoming[0]["days"] == upcoming[0]["days_until"], "birthday events should expose both days fields")
    assert_true(upcoming[0]["days_until"] == 1, "tomorrow should be one day away")


def test_bin_collector_parses_current_east_devon_address_shape():
    old_http_get_json = bin_collections.http_get_json
    bin_collections.http_get_json = lambda *args, **kwargs: [
        {
            "label": "Target Address",
            "UPRN": "123",
            "Results": (
                '<h2>Your recycling and food waste</h2>'
                '<p class="boxtext-important text-centre">Your next recycling and food waste '
                'collection will be on <em>Thursday<br/>17 September 2026</em></p>'
                '<h2>Your rubbish</h2>'
                '<p class="boxtext-important text-centre">Your next rubbish collection will be on '
                '<em>Thursday<br/>1 October 2026</em></p>'
            ),
        }
    ]

    try:
        collector = bin_collections.EastDevonWasteCollector("123", "EX8 3AB")
        collections = collector._fetch_data_from_source()
    finally:
        bin_collections.http_get_json = old_http_get_json

    assert_true(len(collections) == 2, "current East Devon response shape should parse collection dates")
    assert_true(collections[0]["type"] == "Recycling & Food Waste", "recycling collection should be detected")
    assert_true(collections[1]["type"] == "General Waste", "rubbish collection should be detected")


def test_bin_collector_empty_parse_is_fetch_failure():
    old_http_get_json = bin_collections.http_get_json
    bin_collections.http_get_json = lambda *args, **kwargs: [
        {"label": "Target Address", "UPRN": "123", "Results": "<p>No date rows here</p>"}
    ]

    try:
        collector = bin_collections.EastDevonWasteCollector("123", "EX8 3AB")
        collections = collector._fetch_data_from_source()
    finally:
        bin_collections.http_get_json = old_http_get_json

    assert_true(collections is None, "empty bin parse should be treated as a failed fetch")


def test_water_quality_rejects_malformed_required_responses():
    old_api_get = water_quality._api_get
    responses = [
        [],
    ]

    def fake_api_get(*args, **kwargs):
        return responses.pop(0)

    water_quality._api_get = fake_api_get
    try:
        fetcher = water_quality.WaterQualityFetcher()
        data = fetcher._fetch_data_from_source()
    finally:
        water_quality._api_get = old_api_get

    assert_true(data is None, "malformed required EA beach response should be fetch failure")


def test_water_quality_skips_bad_optional_history_and_sample_rows():
    old_api_get = water_quality._api_get
    responses = [
        {
            "primaryTopic": {
                "name": {"_value": "Exmouth"},
                "samplingPoint": {},
                "latestComplianceAssessment": {"complianceClassification": {"name": {"_value": "Good"}}},
            }
        },
        {
            "result": {
                "items": [
                    "bad sample",
                    {
                        "sampleDateTime": {"inXSDDateTime": "2026-09-11T10:00:00Z"},
                        "escherichiaColiCount": "12",
                        "intestinalEnterococciCount": "not-a-number",
                    },
                ]
            }
        },
        {"result": {"items": ["bad history"]}},
    ]

    def fake_api_get(*args, **kwargs):
        return responses.pop(0)

    water_quality._api_get = fake_api_get
    try:
        fetcher = water_quality.WaterQualityFetcher()
        data = fetcher._fetch_data_from_source()
    finally:
        water_quality._api_get = old_api_get

    assert_true(data is not None, "valid sample data should survive malformed optional history")
    assert_true(len(data["recent_samples"]) == 1, "malformed sample rows should be skipped")
    assert_true(data["latest_sample"]["ecoli_rating"] == "Excellent", "numeric string counts should be rated")
    assert_true(data["latest_sample"]["enterococci_rating"] == "Unknown", "bad count values should be unknown")


def main():
    tests = [
        test_request_error_redacts_common_secret_query_params,
        test_offline_mode_returns_stale_cache_without_source_call,
        test_offline_mode_without_cache_does_not_call_source,
        test_failed_fetch_returns_stale_cache,
        test_empty_list_is_valid_fresh_data,
        test_invalid_cache_timestamp_is_treated_as_stale,
        test_malformed_cache_root_does_not_crash_fetcher,
        test_sewage_api_skips_malformed_features,
        test_nfl_fetcher_skips_malformed_events,
        test_birthday_fetcher_uses_stale_cache_when_file_missing,
        test_birthday_fetcher_empty_file_is_valid_data,
        test_birthday_fetcher_normalizes_upcoming_birthdays,
        test_bin_collector_parses_current_east_devon_address_shape,
        test_bin_collector_empty_parse_is_fetch_failure,
        test_water_quality_rejects_malformed_required_responses,
        test_water_quality_skips_bad_optional_history_and_sample_rows,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} fetcher behavior tests")


if __name__ == "__main__":
    main()
