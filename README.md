# Boo Haus Display

A modular home information display for a Raspberry Pi with a Pimoroni Inky
Impression 7.3" e-ink display.

## Screens

- Weather, tides, beach water quality, and sewage status
- Week summary with forecast, waste collections, and celebrations
- NFL scores and schedules
- Google Calendar events
- Positive news feed
- Birthdays
- System status

## Quick Start

```bash
git clone <repo-url> boo_haus_display
cd boo_haus_display
chmod +x quick_start.sh
./quick_start.sh
```

For an existing checkout, the minimum local setup is:

```bash
pip3 install --user -r requirements.txt
cp boo_haus_config.example.json boo_haus_config.json
cp .env.example .env
cp birthdays.example.json birthdays.json
chmod 600 .env
```

Optional integrations are listed in `requirements-optional.txt`. Install the
parts you use, or install the whole file on the Raspberry Pi:

```bash
pip3 install --user -r requirements-optional.txt
```

Edit `.env` for simple API keys:

```bash
OPENWEATHER_API_KEY=...
ANTHROPIC_API_KEY=...
```

Edit `boo_haus_config.json` for location, screen settings, calendar IDs, and
runtime paths. Google Calendar uses local OAuth files, not environment
variables:

- `credentials.json`
- `token.json`

## Running

Render one named screen:

```bash
python3 boo_haus_main.py --screen weather
python3 boo_haus_main.py --screen week
python3 boo_haus_main.py --screen status
```

Render the next enabled screen once:

```bash
python3 boo_haus_main.py --once
```

Run continuous cycling, which is what the display service uses:

```bash
python3 boo_haus_main.py --cycle
```

## Services

Install the display service:

```bash
sudo ./install_service.sh
```

Install the display and dashboard services:

```bash
sudo ./install_service.sh --dashboard
```

Install without starting services:

```bash
sudo ./install_service.sh --dashboard --no-start
```

See [SERVICE_GUIDE.md](SERVICE_GUIDE.md) for service management commands.
Use [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) when updating an existing
Pi checkout while preserving local secrets and runtime data.

## Testing

Focused regression checks:

```bash
python3 test_config_handling.py
python3 test_backup_restore.py
python3 test_fetcher_behaviour.py
python3 test_news_pipeline.py
python3 test_runtime_behaviour.py
python3 test_screen_fixtures.py
python3 test_health_check.py
python3 test_service_install_files.py
```

Render all screens without updating the e-ink display:

```bash
python3 test_display.py --quick
```

Diagnostics:

```bash
python3 health_check.py --skip-network
python3 health_check.py --skip-network --json
```

## Data Fetchers

Individual fetchers can be run directly when investigating data-source issues:

```bash
python3 weather_fetcher.py
python3 bin_collections.py
python3 tide_times.py
python3 news_scraper.py
python3 news_summariser.py
```

Most network fetchers use the shared helper in `base_fetcher.py` for timeouts,
offline mode, user-agent handling, and secret-safe request logging.

## Local Files

These files are private/local and should not be committed:

- `.env`
- `boo_haus_config.json`
- `credentials.json`
- `token.json`
- `birthdays.json`
- `waste_collections.json`
- runtime caches, logs, generated news data, and generated display images

## Documentation

- [BUTTON_GUIDE.md](BUTTON_GUIDE.md)
- [SERVICE_GUIDE.md](SERVICE_GUIDE.md)
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
- [CLAUDE.md](CLAUDE.md)
