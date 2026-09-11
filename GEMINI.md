# Project Summary: Boo Haus Display

## Overview

Boo Haus Display is a Python application for a Raspberry Pi connected to a
Pimoroni Inky Impression 7.3" e-ink display. It cycles through modular screens
with local household information and API-backed data.

## Current Screens

1. Weather, tides, water quality, and sewage status.
2. Week summary with forecast, bin collections, birthdays, and holidays.
3. NFL scores and schedules.
4. Google Calendar events.
5. Positive news stories and summaries.
6. Upcoming birthdays from local JSON.
7. System and data-source status.

## Runtime Shape

- `boo_haus_main.py` owns screen cycling, Inky rendering, state, button wiring,
  and scheduled news jobs.
- Screens live in `screens/` and inherit from `BaseScreen`.
- Fetchers use `BaseFetcher` where practical for cache handling, shared HTTP
  behavior, offline mode, and sanitized request logging.
- The Flask dashboard in `web_dashboard.py` is optional and defaults to
  localhost.
- GPIO buttons use `gpiod` and are active only when the display runs in
  `--cycle` mode.

## Configuration

- `boo_haus_config.example.json` contains defaults.
- `boo_haus_config.json` contains local display, location, and screen settings.
- `.env` contains simple API keys such as `OPENWEATHER_API_KEY` and
  `ANTHROPIC_API_KEY`.
- Google Calendar credentials stay as local JSON files:
  `credentials.json` and `token.json`.

## News Pipeline

The news scraper expands digest articles into individual story records before
they enter the raw news database. `news_summariser.py` can then create
display-ready summaries with Anthropic when `ANTHROPIC_API_KEY` is configured.
The news screen prefers summarized stories, then the raw story database, then
legacy summary files.

## Setup And Services

Use `README.md` and `SERVICE_GUIDE.md` as the primary setup references.
`install_service.sh` installs the display service by default and can install the
dashboard service with `--dashboard`. Use `--no-start` when service files should
be installed without starting local services immediately.

## Tests

Run focused regression tests with:

```bash
python3 test_config_handling.py
python3 test_backup_restore.py
python3 test_fetcher_behaviour.py
python3 test_news_pipeline.py
python3 test_runtime_behaviour.py
python3 test_runtime_edge_cases.py
python3 test_screen_fixtures.py
python3 test_health_check.py
python3 test_service_install_files.py
python3 test_display.py --quick
bash -n install_service.sh quick_start.sh install_all_deps.sh
```
