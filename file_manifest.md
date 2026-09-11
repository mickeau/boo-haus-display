# Boo Haus Display File Manifest

This is a quick map of the maintained project files. Use `README.md` for setup
instructions and `CLAUDE.md` for current engineering context.

## Core Runtime

- `boo_haus_main.py` - display manager, screen cycling, state, buttons, Inky rendering, and scheduled news jobs.
- `base_screen.py` - shared screen drawing, fonts, colors, header, wrapping, and alignment helpers.
- `config.py` - loads example config, local config, `.env`, and config-driven runtime paths.
- `base_fetcher.py` - shared fetcher cache, HTTP helpers, offline mode, user agent, and sanitized request errors.
- `web_dashboard.py` - optional Flask dashboard for preview, logs, and screen requests.
- `health_check.py` - local diagnostics for config, runtime files, caches, and data sources.

## Screens

- `screens/weather_screen.py` - weather, forecast, tides, water quality, and sewage status.
- `screens/week_screen.py` - week number, forecast summary, bin collections, birthdays, and holidays.
- `screens/nfl_screen.py` - NFL scores and schedules.
- `screens/calendar_screen.py` - Google Calendar events.
- `screens/news_screen.py` - summarized/raw/legacy news display.
- `screens/birthday_screen.py` - upcoming birthdays.
- `screens/status_screen.py` - system and data-source status.
- `screens/__init__.py` - screen exports.

## Fetchers And Data Processing

- `weather_fetcher.py` - OpenWeather One Call API fetcher.
- `weather_data_utils.py` - weather payload normalization.
- `weather_icon_utils.py` - weather icon filename and PNG helpers.
- `tide_times.py` - BBC tide table scraping and caching.
- `water_quality.py` - Environment Agency bathing water quality.
- `direct_sewage_api.py` - sewage overflow alerts.
- `bin_collections.py` - East Devon bin collection lookup.
- `nfl_scores.py` - ESPN NFL scoreboard integration.
- `calendar_fetcher.py` - Google Calendar API integration.
- `birthday_fetcher.py` - configured local birthday JSON loader.
- `news_config.py` - RSS source, digest, selector, and scraper settings.
- `news_models.py` - story normalization, IDs, sorting, and display records.
- `digest_detector.py` - digest article detection.
- `digest_parsers.py` - digest article splitting.
- `news_scraper.py` - RSS/story scraping and raw story database generation.
- `news_summariser.py` - optional Anthropic summary generation.
- `date_handler.py` - timezone-aware date parsing utilities for news cleanup.

## Compatibility CLIs And Helpers

- `calendar_display.py` - compatibility wrapper around `CalendarScreen`.
- `birthday_tracker.py` - compatibility wrapper around `BirthdayScreen`.
- `add_birthday.py` - interactive birthday JSON editor.
- `test_buttons.py` - manual button/GPIO check helper.
- `check_rss_dates.py` - RSS date inspection helper.

## Configuration And Private Runtime Files

Committed templates:

- `boo_haus_config.example.json`
- `.env.example`
- `birthdays.example.json`
- `requirements.txt`
- `requirements-optional.txt`

Private local files that should stay ignored:

- `.env` - simple API keys such as `OPENWEATHER_API_KEY` and `ANTHROPIC_API_KEY`.
- `boo_haus_config.json` - local display, location, and screen settings.
- `credentials.json` - Google Calendar OAuth client JSON.
- `token.json` - Google Calendar OAuth token generated/refreshed by the client library.
- `birthdays.json` - personal birthday data.

Generated runtime files that should stay ignored:

- `display_state.json`
- `news_display_state.json`
- `combined_news_recent.json`
- `news_stories.json`
- `news_summaries.json`
- `headline_summaries_cache.json`
- `*_cache.json`
- `waste_collections.json`
- `display_images/`
- `logs/`
- `backups/`

## Installation And Services

- `quick_start.sh` - interactive local setup script.
- `install_all_deps.sh` - dependency installer with optional integration prompts.
- `install_service.sh` - systemd service installer; use `--dashboard` for the dashboard service and `--no-start` to avoid starting immediately.
- `boo-haus-display.service` - display service template.
- `boo-haus-dashboard.service` - dashboard service template.
- `systemd_service.txt` - example service file using placeholders.
- `SERVICE_GUIDE.md` - service install, restart, logging, and uninstall guide.
- `DEPLOYMENT_CHECKLIST.md` - safe Pi update checklist that preserves local secrets and runtime data.
- `installation_guide.md` - deprecated pointer to current setup docs.

## Documentation

- `README.md` - current setup and operation guide.
- `BUTTON_GUIDE.md` - Inky button behavior and service notes.
- `CLAUDE.md` - current context for coding agents.
- `DEPLOYMENT_CHECKLIST.md` - deployment checklist for updating the Pi checkout.
- `GEMINI.md` - compact project overview for Gemini-style agents.
- `project_summary.md` - deprecated pointer to `README.md`.

## Tests

- `test_config_handling.py`
- `test_backup_restore.py`
- `test_fetcher_behaviour.py`
- `test_news_pipeline.py`
- `test_runtime_behaviour.py`
- `test_runtime_edge_cases.py`
- `test_screen_fixtures.py`
- `test_health_check.py`
- `test_service_install_files.py`
- `test_display.py`
- `test_digest_detection.py`

Useful local check:

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
