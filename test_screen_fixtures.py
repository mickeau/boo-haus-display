#!/usr/bin/env python3
"""
Fixture-backed screen rendering tests.

Run with:
    python3 test_screen_fixtures.py
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch


class RecordingDraw:
    """ImageDraw wrapper that records text while delegating all drawing."""

    def __init__(self, draw):
        self._draw = draw
        self.texts = []

    def text(self, xy, text, *args, **kwargs):
        self.texts.append(str(text))
        return self._draw.text(xy, text, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._draw, name)


class FakeFetcher:
    def __init__(self, data):
        self.data = data

    def fetch_data(self, *args, **kwargs):
        return self.data


class FakeWeatherTools(FakeFetcher):
    @staticmethod
    def kelvin_to_celsius(kelvin):
        return round(kelvin - 273.15)

    @staticmethod
    def mps_to_mph(mps):
        return round(mps * 2.23694)

    @staticmethod
    def get_wind_direction(degrees):
        return "S" if 135 <= degrees <= 225 else "N"

    @staticmethod
    def get_peak_uv_today(hourly):
        return max(item.get('uvi', 0) for item in hourly)

    @staticmethod
    def format_time(timestamp, timezone_offset):
        return datetime.fromtimestamp(timestamp + timezone_offset, timezone.utc).strftime('%H:%M')


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def attach_recorder(screen):
    recorder = RecordingDraw(screen.draw)
    screen.draw = recorder
    return recorder


def assert_text_seen(recorder, expected):
    haystack = "\n".join(recorder.texts)
    assert_true(expected in haystack, f"expected rendered text containing {expected!r}")


def fixture_weather_data():
    now = int(datetime(2026, 9, 8, 7, 0, tzinfo=timezone.utc).timestamp())
    return {
        'timezone_offset': 0,
        'current': {
            'weather': [{'description': 'light rain'}],
            'temp': 289.15,
            'feels_like': 288.15,
            'humidity': 72,
            'wind_deg': 180,
            'wind_speed': 5.2,
            'uvi': 2.4,
            'sunrise': now,
            'sunset': now + 43200,
        },
        'daily': [
            {
                'dt': now + i * 86400,
                'weather': [{'main': 'Rain', 'description': 'light rain'}],
                'temp': {'max': 291.15 + i, 'min': 282.15 + i},
                'pop': 0.35 + i * 0.05,
                'wind_speed': 4.0 + i,
            }
            for i in range(5)
        ],
        'hourly': [{'uvi': value} for value in (1.1, 2.4, 4.8, 3.2)],
    }


def test_weather_screen_fixture_render():
    from screens.weather_screen import WeatherScreen

    screen = WeatherScreen()
    screen.weather_fetcher = FakeWeatherTools(fixture_weather_data())
    screen.tide_fetcher = FakeFetcher([
        {'type': 'High', 'time': '23:10', 'height': 3.7},
        {'type': 'Low', 'time': '23:55', 'height': 0.8},
    ])
    screen.water_quality_fetcher = FakeFetcher({
        'latest_sample': {'overall_rating': 'Excellent', 'date': '2026-09-07'},
        'current_classification': {'rating': 'Excellent', 'year': '2026'},
    })
    screen.sewage_fetcher = FakeFetcher({
        'status': 'GOOD',
        'message': 'No active Exmouth discharges',
    })
    screen.load_weather_icon = lambda description: None
    recorder = attach_recorder(screen)

    screen.render_content()

    assert_text_seen(recorder, "Light Rain")
    assert_text_seen(recorder, "Exmouth Beach: Tide Times")
    assert_text_seen(recorder, "Latest Water Quality: Excellent")
    assert_text_seen(recorder, "No active Exmouth discharges")


def test_weather_adapters_skip_malformed_records():
    from screens.weather_screen import WeatherScreen

    screen = WeatherScreen()
    screen.tide_fetcher = FakeFetcher([
        {'type': 'High', 'time': '23:10', 'height': 3.7},
        {'type': 'Low', 'height': 0.8},
        "bad tide",
    ])
    screen.water_quality_fetcher = FakeFetcher("bad water quality")
    screen.weather_fetcher = FakeWeatherTools({'daily': []})

    tides = screen.get_tide_data()

    assert_true(len(tides) == 1, "malformed tide records should be skipped")
    assert_true(tides[0]['time'] == '23:10', "valid tide record should be preserved")
    assert_true(screen.get_water_quality() is None, "malformed water quality should return no display data")
    assert_true(screen.get_weather_data() is None, "malformed weather data should return no display data")


def test_weather_data_normalizers():
    from weather_data_utils import normalize_current_weather, normalize_forecast_day

    fixture = fixture_weather_data()
    current = normalize_current_weather(fixture, FakeWeatherTools(fixture))
    forecast_day = normalize_forecast_day(fixture['daily'][0], FakeWeatherTools(fixture))

    assert_true(current['description'] == "Light Rain", "current weather description should be title-cased")
    assert_true(current['rain_chance'] == 35, "current weather rain chance should be a percent")
    assert_true(current['wind_dir'] == "S", "current wind direction should be normalized")
    assert_true(forecast_day['display_description'] == "Light Rain", "forecast display description should be normalized")
    assert_true(forecast_day['high'] == 18, "forecast high should use the weather conversion helper")
    assert_true(forecast_day['rain_chance'] == 35, "forecast rain chance should be a percent")


def test_week_screen_fixture_render():
    from screens.week_screen import WeekScreen

    today = date.today()
    screen = WeekScreen()
    screen.weather_fetcher = FakeWeatherTools(fixture_weather_data())
    screen.bin_collector = FakeFetcher([
        {'type': 'Recycling', 'date': (today + timedelta(days=1)).isoformat()},
        {'type': 'General Waste', 'date': (today + timedelta(days=4)).isoformat()},
    ])
    screen.birthday_fetcher = FakeFetcher([])
    screen.get_birthdays_this_week = lambda: [{
        'type': 'birthday',
        'name': 'Ada',
        'date': today + timedelta(days=2),
        'days': 2,
    }]
    screen.get_holidays_this_week = lambda: [{
        'type': 'holiday',
        'name': 'Summer Bank Holiday',
        'date': today + timedelta(days=3),
        'days': 3,
    }]
    screen.load_weather_icon_small = lambda description: None
    recorder = attach_recorder(screen)

    screen.render_content()

    assert_text_seen(recorder, "This Week at a Glance")
    assert_text_seen(recorder, "Recycling:")
    assert_text_seen(recorder, "Ada's Birthday!")
    assert_text_seen(recorder, "Summer Bank Holiday Bank Holibob")


def test_week_screen_skips_malformed_rows():
    from screens.week_screen import WeekScreen

    today = date.today()
    weather_data = fixture_weather_data()
    weather_data['daily'] = [
        {'dt': int(datetime.now().timestamp())},
        weather_data['daily'][1],
    ]

    screen = WeekScreen()
    screen.weather_fetcher = FakeWeatherTools(weather_data)
    screen.bin_collector = FakeFetcher([
        {'date': (today + timedelta(days=1)).isoformat()},
        {'type': 'Recycling', 'date': (today + timedelta(days=2)).isoformat()},
    ])
    screen.get_birthdays_this_week = lambda: [
        {'name': 'Missing Date'},
        {
            'type': 'birthday',
            'name': 'Ada',
            'date': today + timedelta(days=1),
            'days': 1,
        },
    ]
    screen.get_holidays_this_week = lambda: ["bad holiday"]
    screen.load_weather_icon_small = lambda description: None
    recorder = attach_recorder(screen)

    _, y, width, _ = screen.get_content_area()
    screen.draw_5_day_forecast(15, y, width)
    screen.draw_bin_collections(15, y + 150, 300, 150)
    screen.draw_events_this_week(400, y + 150, 300, 150)

    assert_text_seen(recorder, "Tomozzy")
    assert_text_seen(recorder, "Recycling:")
    assert_text_seen(recorder, "Ada's Birthday!")


def test_calendar_screen_fixture_render():
    from screens.calendar_screen import CalendarScreen

    screen = CalendarScreen()
    event_time = datetime.now() + timedelta(days=1)
    screen.get_calendar_events = lambda: [
        {
            'summary': 'Beach Clean Planning',
            'datetime': event_time,
            'days_until': 1,
            'is_all_day': False,
            'time_str': '18:30',
            'location': 'Boo Haus',
        },
        {
            'summary': 'Neighbourhood Supper',
            'datetime': event_time + timedelta(days=2),
            'days_until': 2,
            'is_all_day': True,
            'time_str': '',
            'location': '',
        },
    ]
    recorder = attach_recorder(screen)

    screen.render_content()

    assert_text_seen(recorder, "Coming Soon @ Boo Haus")
    assert_text_seen(recorder, "Beach Clean Planning")
    assert_text_seen(recorder, "Tomorrow")


def test_calendar_screen_skips_malformed_events():
    from screens.calendar_screen import CalendarScreen

    screen = CalendarScreen()
    event_time = datetime.now() + timedelta(days=1)
    recorder = attach_recorder(screen)

    screen.draw_event_column([
        {'summary': 'Missing Date', 'days_until': 1, 'is_all_day': True, 'time_str': '', 'location': ''},
        {
            'summary': 'Valid Workshop',
            'datetime': event_time,
            'days_until': 1,
            'is_all_day': True,
            'time_str': '',
            'location': '',
        },
    ], 15, 90, 360, 300)

    assert_text_seen(recorder, "Valid Workshop")
    assert_text_seen(recorder, "Tomorrow")


def test_news_screen_fixture_render():
    from screens.news_screen import NewsScreen

    screen = NewsScreen()
    screen.load_and_cycle_stories = lambda: [
        {
            'headline': 'Libraries Launch Tool Share',
            'summary': 'Libraries opened a tool-sharing service that helps residents repair homes and reduce waste.',
            'published_at': datetime.now(timezone.utc).isoformat(),
            'source_site': 'positive_news',
        }
    ]
    recorder = attach_recorder(screen)

    screen.render_content()

    assert_text_seen(recorder, "Recent Good News Headlines")
    assert_text_seen(recorder, "Libraries Launch Tool Share")


def test_news_screen_skips_corrupt_preferred_file():
    import json
    import os
    import tempfile

    from config import config
    from screens.news_screen import NewsScreen

    old_news_config = dict(config.config['screens']['news'])
    old_state_file = config.config['screens']['news'].get('state_file')

    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_path = os.path.join(tmpdir, "news_stories.json")
        raw_path = os.path.join(tmpdir, "combined_news_recent.json")
        state_path = os.path.join(tmpdir, "news_display_state.json")

        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("{not json")

        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump({
                "stories": [{
                    "title": "Community Garden Opens",
                    "content": "A community garden opened with accessible beds and shared tools for local residents.",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "source_site": "positive_news",
                    "source_type": "regular_article",
                }]
            }, f)

        config.config['screens']['news'].update({
            'story_file': corrupt_path,
            'legacy_story_file': os.path.join(tmpdir, "missing_legacy.json"),
            'raw_story_file': raw_path,
            'cache_file': os.path.join(tmpdir, "missing_cache.json"),
            'state_file': state_path,
            'stories_per_screen': 1,
        })

        try:
            screen = NewsScreen()
            stories = screen.load_and_cycle_stories()
        finally:
            config.config['screens']['news'] = old_news_config
            if old_state_file is not None:
                config.config['screens']['news']['state_file'] = old_state_file

    assert_true(len(stories) == 1, "corrupt preferred news file should fall back to raw story database")
    assert_true(stories[0]['headline'] == "Community Garden Opens", "fallback raw story should be loaded")


def test_birthday_screen_fixture_render():
    from screens.birthday_screen import BirthdayScreen

    screen = BirthdayScreen()
    screen.get_upcoming_birthdays = lambda: [
        {
            'name': 'Grace Hopper',
            'date': date.today() + timedelta(days=1),
            'days_until': 1,
        }
    ]
    recorder = attach_recorder(screen)

    screen.render_content()

    assert_text_seen(recorder, "Upcoming Birthdays")
    assert_text_seen(recorder, "Grace Hopper")
    assert_text_seen(recorder, "TOMORROW")


def test_nfl_screen_fixture_render():
    from screens.nfl_screen import NFLScreen

    class FakeNFLWeeklyDisplay:
        def is_stale(self):
            return False

        def get_games_list(self, format_type='inky'):
            game_time = datetime.now(timezone.utc) + timedelta(days=2)
            return "Week 1", [
                {
                    'date': game_time,
                    'status': {'type': {'name': 'STATUS_SCHEDULED'}},
                    'competition': {
                        'competitors': [
                            {'team': {'displayName': 'Miami Dolphins'}, 'records': [{'summary': '1-0'}]},
                            {'team': {'displayName': 'Buffalo Bills'}, 'records': [{'summary': '0-1'}]},
                        ]
                    },
                }
            ], ['Chiefs']

    recorder = None
    with patch('nfl_scores.NFLWeeklyDisplay', FakeNFLWeeklyDisplay):
        screen = NFLScreen()
        recorder = attach_recorder(screen)
        screen.render_content()

    assert_text_seen(recorder, "NFL Week 1")
    assert_text_seen(recorder, "Miami Dolphins (1-0)")
    assert_text_seen(recorder, "Chiefs")


def test_nfl_screen_says_when_data_is_out_of_date():
    from screens.nfl_screen import NFLScreen

    # A failed refresh falls back to last week's cache, which filters down to no
    # games for the current week. That must not read as "no games this week".
    class StaleNFLWeeklyDisplay:
        def is_stale(self):
            return True

        def last_updated(self):
            return datetime(2026, 10, 18, 14, 2)

        def get_games_list(self, format_type='inky'):
            return "Week 6", [], []

    with patch('nfl_scores.NFLWeeklyDisplay', StaleNFLWeeklyDisplay):
        screen = NFLScreen()
        recorder = attach_recorder(screen)
        screen.render_content()

    assert_text_seen(recorder, "Not updated since Sun 18 Oct 14:02")
    assert_text_seen(recorder, "can't be refreshed")
    assert_true(not any("No games found" in t for t in recorder.texts),
                "stale NFL data must not claim there are no games")


def test_calendar_hides_events_that_have_ended():
    from screens.calendar_screen import CalendarScreen

    now = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
    ended = CalendarScreen.event_has_ended
    assert_true(ended({'end': {'dateTime': '2026-10-27T11:00:00Z'}}, now), "timed event this morning has ended")
    assert_true(not ended({'end': {'dateTime': '2026-10-27T13:00:00+00:00'}}, now), "timed event this afternoon has not")
    # All-day end dates are exclusive: a one-day event on the 26th ends on the 27th.
    assert_true(ended({'end': {'date': '2026-10-27'}}, now), "yesterday's all-day event has ended")
    assert_true(not ended({'end': {'date': '2026-10-28'}}, now), "today's all-day event has not")
    assert_true(not ended({}, now), "an event with no end is kept")


def test_nfl_screen_skips_malformed_games():
    from screens.nfl_screen import NFLScreen

    screen = NFLScreen()
    recorder = attach_recorder(screen)
    game_time = datetime.now(timezone.utc) + timedelta(days=2)

    screen.draw_game_column([
        {'date': game_time, 'status': {'type': {'name': 'STATUS_SCHEDULED'}}},
        {
            'date': game_time,
            'status': {'type': {'name': 'STATUS_SCHEDULED'}},
            'competition': {
                'competitors': [
                    {'team': {'displayName': 'Miami Dolphins'}, 'records': [{'summary': '1-0'}]},
                    {'team': {'displayName': 'Buffalo Bills'}, 'records': [{'summary': '0-1'}]},
                ]
            },
        },
    ], 15, 90, 360, 300)

    assert_text_seen(recorder, "Miami Dolphins (1-0)")
    assert_text_seen(recorder, "Buffalo Bills (0-1)")


def test_status_screen_fixture_render():
    from screens.status_screen import StatusScreen

    screen = StatusScreen(display_manager=type('Manager', (), {'screens': [1, 2, 3]})())
    screen._get_cpu_temp = lambda: "48.0 degC"
    screen._get_memory = lambda: (512, 1024, 50)
    screen._get_disk = lambda: (8.0, 32.0, 25)
    screen._get_uptime = lambda: "1d 2h 3m"
    screen._get_wifi_info = lambda: ("BooHausWiFi", -45, 90)
    screen._get_ip_address = lambda: "192.168.1.25"
    screen._check_internet = lambda: True
    screen._get_cache_age = lambda cache_file: 15
    screen._get_news_cache_age = lambda: 60
    recorder = attach_recorder(screen)

    screen.render_content()

    assert_text_seen(recorder, "System Health")
    assert_text_seen(recorder, "BooHausWiFi")
    assert_text_seen(recorder, "Weather")
    assert_text_seen(recorder, "Screen:")


def test_shared_weather_icon_mapping():
    from weather_icon_utils import icon_filename_for_description

    assert_true(icon_filename_for_description("clear sky") == "sun.png", "clear weather should use sun icon")
    assert_true(icon_filename_for_description("light rain") == "drizzle.png", "light rain should use drizzle icon")
    assert_true(icon_filename_for_description("heavy thunderstorm") == "thunderstorm.png", "storms should use storm icon")
    assert_true(icon_filename_for_description("unknown haze") == "cloudy.png", "unknown weather should use cloudy fallback")


def main():
    tests = [
        test_weather_screen_fixture_render,
        test_weather_adapters_skip_malformed_records,
        test_weather_data_normalizers,
        test_week_screen_fixture_render,
        test_week_screen_skips_malformed_rows,
        test_calendar_screen_fixture_render,
        test_calendar_screen_skips_malformed_events,
        test_news_screen_fixture_render,
        test_news_screen_skips_corrupt_preferred_file,
        test_birthday_screen_fixture_render,
        test_nfl_screen_fixture_render,
        test_nfl_screen_skips_malformed_games,
        test_nfl_screen_says_when_data_is_out_of_date,
        test_calendar_hides_events_that_have_ended,
        test_status_screen_fixture_render,
        test_shared_weather_icon_mapping,
    ]

    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    print(f"\nPASS {len(tests)} fixture-backed screen tests")


if __name__ == "__main__":
    main()
