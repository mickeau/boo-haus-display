# CLAUDE.md

This file gives coding agents the current operating context for the Boo Haus
Display repository.

## Project Overview

Boo Haus Display is a Raspberry Pi home information display for a Pimoroni Inky
Impression 7.3" e-ink display. The app cycles through modular screens for:

- Weather
- Week summary
- NFL
- Calendar
- News
- Birthdays
- Status

Main entry point:

```bash
python3 boo_haus_main.py [--once|--cycle|--screen <name>]
```

Use `--cycle` for the systemd service and button support. Use `--screen <name>`
or `--once` for local checks.

## Current Architecture

### Display Manager

`boo_haus_main.py` owns screen construction, state loading/saving, screen
cycling, optional button setup, preview image saving, Inky rendering, and daily
news scraper scheduling.

Important details:

- Screen state is stored at `config.runtime_path('state_file', 'display_state.json')`.
- Requested dashboard/button screen changes are stored by screen name in
  `requested_screen`.
- Button handling is only enabled for cycle mode unless config/environment
  explicitly disables it.
- Screen initialization is defensive: one broken optional screen should not
  prevent the whole app from starting.

### Screens

Screen modules live under `screens/` and inherit from `BaseScreen` in
`base_screen.py`. `screens/__init__.py` should stay as thin exports only.
`BaseScreen` owns common text measurement and right-aligned drawing helpers;
prefer those over repeating `textbbox` width calculations in screen modules.
Use `draw_section_title_at()` for section headings that need a custom x
position or underline width; `draw_section_title()` is the standard left-aligned
wrapper.

Current screen classes:

- `WeatherScreen`
- `WeekScreen`
- `NFLScreen`
- `CalendarScreen`
- `NewsScreen`
- `BirthdayScreen`
- `StatusScreen`

Each screen must implement `name` and `render_content()`.

Older standalone display scripts should not carry their own data/rendering
pipelines. `calendar_display.py` and `birthday_tracker.py` are compatibility
CLI wrappers around the maintained fetcher/screen modules. Keep future one-off
render commands thin in the same way so display behavior has one source of
truth.

`button_handler.py` should stay hardware-optional and safe to import on
development machines. Disabled mode must not require `gpiod`; callback failures
should be logged with traceback and contained so the monitoring thread keeps
running. Button D intentionally has a longer debounce window than A/B/C.

Broad render guards in `boo_haus_main.py` are intentional at two boundaries:
individual screen initialization and individual screen rendering. Those guards
keep one broken optional screen from taking down the whole display. Prefer
narrower exceptions for predictable file, subprocess, signal, dashboard, and
parser failures elsewhere.

### Fetchers

Data fetchers are independent modules/scripts:

- `weather_fetcher.py` - OpenWeather One Call API
- `tide_times.py` - BBC tide table scraping for Exmouth
- `water_quality.py` - Environment Agency water quality
- `direct_sewage_api.py` - sewage overflow status
- `bin_collections.py` - East Devon Council collection scraping
- `nfl_scores.py` - ESPN NFL scoreboard
- `calendar_fetcher.py` - Google Calendar API
- `birthday_fetcher.py` - local birthday JSON
- `news_scraper.py` - RSS/story scraping and digest splitting
- `news_summariser.py` - optional Anthropic summary generation
- `weather_icon_utils.py` - shared weather icon filename mapping and PNG loading
- `weather_data_utils.py` - shared OpenWeather API normalization for display

Most network fetchers use `BaseFetcher`, which resolves relative cache files
under the project root and treats empty list/dict responses as valid cacheable
results. Network fetch paths should use `http_get()`, `http_get_json()`, or
`http_get_text()` from `base_fetcher.py` so timeout handling, the shared user
agent, offline test mode, and sanitized request logging stay consistent. The
display fetchers currently migrated to this path are weather, tides, NFL, water
quality, sewage, and bin collections. The news RSS fetcher, article scraper,
and digest parsers also use the shared helper.

Fetcher source methods should return `None` for network, API, or parser
failures so `BaseFetcher` can fall back to stale cache. Return an empty list or
dict only when a successful response genuinely contains no data.
Local-file fetchers follow the same rule: unreadable or invalid files should
return `None` so stale cache survives, while a valid empty file can return an
empty list. `BirthdayFetcher` is the shared path for both birthday display and
week-screen birthday events.

`bin_collections.py` uses East Devon's current autocomplete endpoint,
`/repositories/hidden-pages/address-finder/?qtype=bins&term=<postcode>`.
The older `/addressfinder?qtype=bins` endpoint now returns 404. For bin
collections, an empty HTML parse should be treated as `None` rather than `[]`,
because a successful address result with no parsed date rows usually means the
site markup changed and should not overwrite a useful cache. A stale cache with
`"data": []` will make the week screen show "No bin data available" until the
fixed fetcher successfully refreshes `bin_collections_cache.json`.

## Configuration

Runtime configuration is loaded by `config.py`:

- `boo_haus_config.example.json` provides default values.
- `boo_haus_config.json` overlays local/private values when present.
- `.env` is loaded for local secrets without overriding process environment
  variables.
- `BOO_HAUS_CONFIG_FILE` can point to an alternate local config file.
- `OPENWEATHER_API_KEY` overrides `api_keys.openweather`.
- `ANTHROPIC_API_KEY` overrides `api_keys.anthropic`.
- Missing local config should not auto-create `boo_haus_config.json`.
- Relative runtime paths must be resolved with `config.runtime_path(...)` or
  `config.resolve_path(...)`.
- Placeholder values such as `YOUR_...`, `REPLACE_WITH_...`, `changeme`, and
  blank strings must not be treated as configured secrets.

Use `.env` for simple API keys only. Do not move Google Calendar OAuth JSON into
environment variables. Keep Google auth as local ignored files because
`credentials.json` is structured JSON and `token.json` may be refreshed/replaced
by the Google client library. Their paths are configured with:

- `screens.calendar.credentials_file`
- `screens.calendar.token_file`

Sensitive local files are intentionally ignored by git:

- `.env`
- `boo_haus_config.json`
- `credentials.json`
- `token.json`
- `birthdays.json`

Use `.env.example` as the template for local API key setup.

`add_birthday.py` is the maintained birthday editor. By default it writes to the
configured `screens.birthday.birthday_file`, sanitizes malformed rows, and saves
with an atomic file replace.

Dependency references:

- `requirements.txt` contains base packages for local/runtime checks.
- `requirements-optional.txt` contains optional integrations for Anthropic,
  Google Calendar, GPIO buttons, and the Inky display.
- `quick_start.sh` uses `requirements.txt` for base installs and prompts for
  optional Google, Anthropic, and Inky/GPIO packages.

Do not print API keys, calendar tokens, credentials, or full URLs containing
secrets. Weather request errors must pass through `redact_weather_error()` before
logging.

## News Pipeline

The news code now separates source-specific configuration from app runtime
configuration:

- `news_config.py` - RSS source definitions, digest patterns, selectors, and
  scraper settings
- `news_models.py` - shared story normalization, stable IDs, sorting, fallback
  summaries, and display-record extraction
- `digest_detector.py` - identifies digest articles
- `digest_parsers.py` - splits digest articles into individual stories
- `news_scraper.py` - fetches RSS entries, scrapes regular stories, expands
  digest articles, deduplicates, and writes the raw story database
- `news_summariser.py` - optionally summarizes raw stories into display-ready
  summaries
- `screens/news_screen.py` - prefers display-ready summaries, then raw story
  database, then legacy files

Digest articles are expected to be chopped into individual story records before
they enter the display pipeline. Deduplication should happen by stable story ID
where possible, with URL/title fallback.

Default configured news files:

- Raw story database: `combined_news_recent.json`
- Display summaries: `news_stories.json`
- Legacy summaries: `news_summaries.json`
- Summary cache: `headline_summaries_cache.json`
- News display state: `news_display_state.json`

## Dashboard And Services

`web_dashboard.py` is a small Flask dashboard. By default it binds to localhost:

```bash
python3 web_dashboard.py
```

Set these only when remote access is intended:

```bash
BOO_HAUS_DASHBOARD_HOST=0.0.0.0
BOO_HAUS_DASHBOARD_PORT=5000
```

The dashboard uses the configured state, log, and image paths. It writes screen
requests by screen name so changing enabled screen order does not break "Show
Now".

Systemd files:

- `boo-haus-display.service`
- `boo-haus-dashboard.service`
- `install_service.sh`
- `DEPLOYMENT_CHECKLIST.md`

`install_service.sh` installs the display service by default. Use
`sudo ./install_service.sh --dashboard` to also install the dashboard service,
and `--no-start` when you want files installed/enabled without immediately
starting services. Both generated service files include
`EnvironmentFile=-<install-dir>/.env`.

After code or config changes are deployed on the Pi, restart the relevant
service:

```bash
sudo systemctl restart boo-haus-display
sudo systemctl restart boo-haus-dashboard
```

Use `DEPLOYMENT_CHECKLIST.md` before updating the Pi checkout. It lists the
private files to preserve, recommended `rsync` excludes, post-copy checks, and
rollback commands. Do not run those deployment steps unless Mike explicitly asks
for Pi update/deployment work.

## Testing

Run syntax checks for touched Python files:

```bash
python3 -m py_compile config.py boo_haus_main.py web_dashboard.py
```

Focused regression tests:

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

`test_screen_fixtures.py` renders all seven screens with deterministic fixture
data and records text draw calls, so layout/data-contract regressions can be
caught without live APIs or image OCR. It also covers weather data
normalization and malformed row/file handling for weather, week, calendar, NFL,
and news adapters.

`test_fetcher_behaviour.py` covers shared cache and network behavior, including
offline mode, stale-cache fallback, invalid cache timestamps, malformed cache
roots, secret redaction, cacheable empty-list responses, and malformed source
payloads for the sewage, NFL, bin collection, and water-quality fetchers. It
also covers birthday local-file failure behavior and birthday event
normalization.

`test_runtime_behaviour.py` covers service-mode control paths, the optional
Google Calendar integration boundary, malformed calendar API events, and import
behavior for the legacy display wrapper CLIs.

`test_runtime_edge_cases.py` covers utility-level behavior for hardware-optional
button handling, button debouncing/callback containment, birthday editor
sanitization/atomic saves, stricter URL date extraction, and dashboard edge
handling.

Manual helpers `test_buttons.py` and `check_rss_dates.py` are retained as
diagnostics. They should remain import-light, config-driven where possible, and
safe to syntax-check on development machines without GPIO or live network
access.

`waste_collections.json` is local generated runtime output and can contain UPRN
and postcode data. Keep it ignored and do not use it as a committed fixture.

`test_health_check.py` covers health-check parsing for raw news story databases,
timezone-aware display state timestamps, offline data-source checks, and
machine-readable `--json` output.

`test_service_install_files.py` statically checks that service files and install
scripts keep `.env`, display cycle mode, dashboard service wiring, and installer
flags aligned.

Screen data adapters should prefer targeted handling for malformed records:
skip bad rows/files with a warning, keep rendering valid nearby data, and reserve
whole-screen fallback messages for missing data or real rendering failures.

Manual app checks:

```bash
python3 boo_haus_main.py --screen weather
python3 boo_haus_main.py --screen week
python3 boo_haus_main.py --screen nfl
python3 boo_haus_main.py --screen calendar
python3 boo_haus_main.py --screen news
python3 boo_haus_main.py --screen birthday
python3 boo_haus_main.py --screen status
```

Diagnostics:

```bash
python3 health_check.py
python3 health_check.py --skip-network
python3 health_check.py --skip-network --json
```

In sandboxed/offline environments, `health_check.py` and live script runs may
report external weather, tide, bin, news, or NFL fetch failures unless
`--skip-network` or `BOO_HAUS_OFFLINE=1` is used. `test_display.py --quick`
sets `BOO_HAUS_OFFLINE=1`, so display fetchers must render fallback/cache
states without making live network calls. `test_news_pipeline.py` includes a
regression check that the news RSS fetch path also obeys `BOO_HAUS_OFFLINE`.

## Backup And Restore

Use `backup_restore.py` for local backups:

```bash
python3 backup_restore.py --backup
python3 backup_restore.py --backup --include-images --include-logs
python3 backup_restore.py --list
python3 backup_restore.py --restore backups/<file>.tar.gz --dry-run
```

Restore validates tar members before extraction and rejects path traversal,
symlinks, hard links, and device entries.

## Development Rules For This Repo

- Prefer existing project patterns over broad rewrites.
- During this review, keep work local to repository files. Do not restart
  systemd services, copy files to the e-ink device, or otherwise deploy changes
  unless Mike explicitly asks for deployment/update advice.
- Keep runtime file paths config-driven and project-root-relative.
- Keep optional integrations optional: missing Google Calendar, Anthropic,
  Flask, Inky, or GPIO packages should not break unrelated screens/tests.
- Do not commit generated runtime files, caches, logs, image previews, local
  config, tokens, or credentials.
- Use `rg` for searching.
- Use `apply_patch` for manual edits.
- Be careful with the existing dirty worktree. Many files may already be
  modified or untracked; do not revert unrelated changes.

## Known Remaining Review Targets

These are good next audit/refactor targets:

- Continue replacing broad `except Exception` logging with narrower exception
  handling in lower-risk display adapters where it affects runtime recovery or
  hides schema drift. The broad catches in display manager screen
  initialization/rendering and button callback containment are intentional.
