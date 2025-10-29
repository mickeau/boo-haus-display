# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Boo Haus Display is a home information display system for Raspberry Pi with Inky Impression 7.3" e-ink display. It cycles through 6 modular screens showing weather, calendar events, news, NFL scores, birthdays, and weekly summaries.

## Architecture

### Core Components

**Display Manager** (`boo_haus_main.py`)
- Orchestrates screen cycling and state management
- Manages automatic news scraper execution at 3 AM
- Persists state to `display_state.json`
- Entry point: `python3 boo_haus_main.py [--once|--cycle|--screen <name>]`

**Base Screen Class** (`base_screen.py`)
- Abstract base class for all screens
- Provides common header with pastel blue background (PASTEL_BLUE = (86, 108, 230))
- Header height: 70px, content starts at y=75
- Displays special date greetings (configured in `boo_haus_config.json`)
- Utility methods: `draw_section_title()`, `wrap_text()`, `draw_text_box()`, `draw_weather_icon()`
- All screens must implement `name` property and `render_content()` method

**Screen Implementations** (`screens/` directory)
- Each screen inherits from `BaseScreen`
- Screens can be enabled/disabled via config: `config['screens'][screen_name]['enabled']`
- Screen order in cycle is determined by order in `BooHausDisplayManager.__init__()`
- Individual screens: WeatherScreen, WeekScreen, NFLScreen, CalendarScreen, NewsScreen, BirthdayScreen

### Data Architecture

**Data Fetchers** (independent scripts)
- `weather_fetcher.py` - OpenWeather API integration
- `bin_collections.py` - East Devon Council waste collection scraper
- `tide_times.py` - BBC tide data scraper for Exmouth
- `water_quality.py` - Environment Agency beach water quality
- `direct_sewage_api.py` - Sewage overflow status
- `nfl_scores.py` - ESPN NFL data
- `calendar_fetcher.py` / `calendar_display.py` - Google Calendar integration
- `news_scraper.py` - RSS feed scraper with digest detection
- `news_summariser.py` - News summarization pipeline

**News System Architecture**
- Modular design with separate concerns:
  - `config.py` - Site-specific selectors and patterns
  - `date_handler.py` - Date parsing and validation
  - `digest_detector.py` - Detects digest articles vs regular articles
  - `digest_parsers.py` - Parses digest content into individual stories
  - `news_scraper.py` - Main scraper orchestrating above modules
- News cache: `headline_summaries_cache.json` (consumed by NewsScreen)
- News display state: `news_display_state.json` (tracks cycling position)

### Configuration System

**Main Config** (`boo_haus_config.json`)
- `display` - Display dimensions, cycle interval, save/show settings
- `screens` - Per-screen enable/disable and settings
- `special_dates` - Format: "DD-MM": "Greeting message"
- `api_keys` - OpenWeather API key (HARDCODED IN screens/__init__.py:165 - consider refactoring)
- `locations` - UPRN, postcode, lat/long for local services
- `data_refresh` - News scraper scheduling

**Birthday Data** (`birthdays.json`)
- Array of objects: `{"name": "string", "month": int, "day": int}`

## Common Development Tasks

### Testing and Debugging

Run full diagnostics:
```bash
python3 test_display.py
```

Test individual screens without e-ink display:
```bash
python3 test_display.py --quick
```

Test specific screen:
```bash
python3 boo_haus_main.py --screen weather
python3 boo_haus_main.py --screen week
# Options: weather, week, nfl, calendar, news, birthday
```

Display next screen once:
```bash
python3 boo_haus_main.py --once
```

Run continuous cycling (Ctrl+C to stop):
```bash
python3 boo_haus_main.py --cycle
```

### Manual Data Fetcher Testing

Test individual data sources:
```bash
python3 weather_fetcher.py
python3 bin_collections.py
python3 tide_times.py
python3 nfl_scores.py
python3 news_scraper.py
python3 news_summariser.py
```

### Installation and Setup

Run quick setup (creates directories, installs dependencies):
```bash
chmod +x quick_start.sh
./quick_start.sh
```

Install all dependencies manually:
```bash
pip3 install pillow requests beautifulsoup4 feedparser pytz
pip3 install inky[rpi,example-depends]  # Raspberry Pi only
pip3 install google-auth-httplib2 google-auth-oauthlib google-api-python-client  # Optional: Google Calendar
```

### Monitoring and Logs

View logs:
```bash
tail -f logs/display.log
tail -f logs/scraper.log
tail -f logs/summariser.log
```

Check display state:
```bash
cat display_state.json
```

Check saved images:
```bash
ls -lht display_images/
```

## Important Implementation Details

### Screen Rendering Flow
1. `BooHausDisplayManager.display_screen()` calls `screen.render()`
2. `BaseScreen.render()` creates new image, calls `draw_header()`, then `render_content()`
3. Each screen implements `render_content()` to draw content area below header
4. Image saved to `display_images/` and optionally displayed on Inky

### State Management
- `display_state.json`: Tracks current screen index and last update time
- `news_display_state.json`: Tracks which news stories have been shown
- State is loaded on startup and saved after each screen update

### Special Date Handling
- Format in config: `"DD-MM": "Greeting message"` (e.g., "25-12": "Merry Christmas!")
- `BaseScreen.get_special_greeting()` checks current date against config
- Special greeting displayed centered in header on white text over pastel blue

### Color Palette
Defined in `BaseScreen`:
- BLACK = (0, 0, 0)
- WHITE = (255, 255, 255)
- RED = (255, 0, 0)
- YELLOW = (255, 255, 0)
- ORANGE = (255, 140, 0)
- GREEN = (0, 255, 0)
- BLUE = (0, 0, 255)
- PINK = (255, 192, 203)
- PALE_GREEN = (200, 255, 200)
- PASTEL_BLUE = (86, 108, 230) - Used for header background

### Font Sizes (Increased from original)
- `font_title`: 30pt (was 26)
- `font_large`: 28pt (was 24)
- `font_medium`: 22pt (was 18)
- `font_small`: 18pt (was 14)
- `font_tiny`: 14pt (was 12)
- `font_special`: 24pt (for special day messages)

## Adding a New Screen

1. Create new file in `screens/` directory (e.g., `screens/my_screen.py`)
2. Import and inherit from `BaseScreen`
3. Implement `name` property returning screen identifier
4. Implement `render_content()` method
5. Add import to `screens/__init__.py`
6. Add to screen list in `boo_haus_main.py` (line 41-47)
7. Add config section to `boo_haus_config.json`
8. Test with `python3 boo_haus_main.py --screen my_screen`

## Configuration Architecture

All sensitive data (API keys, location data, calendar IDs) are now loaded from `boo_haus_config.json`:

- **API Keys**: `config['api_keys']['openweather']` - OpenWeather API key
- **Location Data**: `config['locations']['uprn']`, `config['locations']['postcode']` - UK property data
- **Calendar IDs**: `config['screens']['calendar']['calendar_ids']` - Google Calendar identifiers

**Note**: The actual config file (`boo_haus_config.json`) is excluded from version control. Use `boo_haus_config.example.json` as a template.

## Automatic Scheduling

### Systemd Service (Recommended)

The preferred method is running as a systemd service for automatic startup on boot.

**Installation:**
```bash
cd ~/boo_haus_display
chmod +x install_service.sh
# If file has Windows line endings, convert first:
dos2unix install_service.sh
sudo ./install_service.sh
```

**Service Management:**
```bash
# Check status
sudo systemctl status boo-haus-display

# Start/stop/restart
sudo systemctl start boo-haus-display
sudo systemctl stop boo-haus-display
sudo systemctl restart boo-haus-display

# Enable/disable autostart on boot
sudo systemctl enable boo-haus-display
sudo systemctl disable boo-haus-display

# View logs
tail -f ~/boo_haus_display/logs/display.log
sudo journalctl -u boo-haus-display -f
```

**After Making Code Changes:**
Always restart the service to apply changes:
```bash
sudo systemctl restart boo-haus-display
```

**Service Benefits:**
- Runs automatically on boot
- Auto-restarts on failure
- Background operation (no SSH session needed)
- Buttons work normally
- Can still SSH in to make edits

**Service Files:**
- Service definition: `/etc/systemd/system/boo-haus-display.service`
- Installation script: `install_service.sh`
- Documentation: `SERVICE_GUIDE.md`

### Cron Setup (Alternative)

For simpler scheduled updates without continuous running:

```cron
# Update display every 5 minutes
*/5 * * * * cd /home/pi/boo_haus_display && /usr/bin/python3 boo_haus_main.py --once >> logs/display.log 2>&1

# Run news scraper daily at 3 AM
0 3 * * * cd /home/pi/boo_haus_display && /usr/bin/python3 news_scraper.py >> logs/scraper.log 2>&1

# Run news summariser daily at 3:30 AM
30 3 * * * cd /home/pi/boo_haus_display && /usr/bin/python3 news_summariser.py >> logs/summariser.log 2>&1
```

**Note:** Buttons do NOT work with cron method (only with systemd service using `--cycle` mode)

## Button Functionality

### Button Handler System

The Inky Impression 7.3" has 4 side-mounted buttons that are fully integrated:

**Button Mapping** (GPIO pins):
- **Button A** (GPIO 5): Previous screen - Navigate backward through screen cycle
- **Button B** (GPIO 6): Next screen - Navigate forward through screen cycle
- **Button C** (GPIO 16): Pause/Resume - Toggle automatic cycling on/off
- **Button D** (GPIO 24): Force refresh - Update current screen with fresh data

**Implementation:**
- `button_handler.py` - Handles GPIO button detection using `gpiod` library
- Button callbacks registered in `BooHausDisplayManager._setup_button_handler()`
- Background thread monitors button presses continuously
- When paused, yellow "⏸ PAUSED" indicator appears in top-right of display

**Configuration:**
```json
"buttons": {
  "enabled": true,
  "show_pause_indicator": true
}
```

**Testing buttons:**
```bash
python3 button_handler.py  # Test button detection standalone
```

**Requirements:**
- `gpiod` library (Python bindings for libgpiod)
- Install: `pip3 install gpiod`
- Only works on Raspberry Pi with GPIO access

### Button State Management

- `is_paused` flag tracks pause state
- Button actions update display immediately
- State persists only during runtime (resets on restart)
- Pause state respected in `run_continuous()` method

## Key Files Reference

### Core Application
- `boo_haus_main.py` (420+ lines) - Main application controller with button integration
- `base_screen.py` (297 lines) - Abstract base for all screens
- `button_handler.py` (260+ lines) - GPIO button handling with gpiod and debouncing
- `screens/__init__.py` (621 lines) - All screen implementations
- `boo_haus_config.json` - System configuration including button settings

### Service & Deployment
- `install_service.sh` - Systemd service installer script
- `boo-haus-display.service` - Systemd service definition file
- `SERVICE_GUIDE.md` - Complete service management documentation

### Testing & Utilities
- `test_display.py` - Comprehensive testing suite
- `test_buttons.py` - Button hardware diagnostic tool
- `health_check.py` - System health monitoring
- `backup_restore.py` - Backup and restore utilities

### Documentation
- `CLAUDE.md` - This file - technical documentation for developers
- `BUTTON_GUIDE.md` - Button functionality user guide
- `SERVICE_GUIDE.md` - Service management guide
- `boo_haus_readme.md` - Main project README
- `installation_guide.md` - Installation instructions
- `project_summary.md` - Project overview
- `file_manifest.md` - File reference guide

## Development Workflow

### When Service is Running

The typical workflow when the service is installed and running:

```bash
# 1. SSH into the Pi
ssh pi@your-pi-address

# 2. Stop the service (optional but recommended)
sudo systemctl stop boo-haus-display

# 3. Make your changes
cd ~/boo_haus_display
nano boo_haus_config.json
# or edit Python files

# 4. Test changes manually (optional)
python3 boo_haus_main.py --once

# 5. Restart the service
sudo systemctl restart boo-haus-display

# 6. Monitor logs to verify
tail -f ~/boo_haus_display/logs/display.log
```

### Quick Changes Without Stopping Service

For small config changes, you can edit and restart in one go:
```bash
nano boo_haus_config.json
sudo systemctl restart boo-haus-display
```

The service will:
- Stop the old process
- Start a new process with updated code/config
- Resume from the current screen position (from state file)

### Testing Changes Without Service

To test without interfering with the service:
```bash
# Stop service temporarily
sudo systemctl stop boo-haus-display

# Test your changes
python3 boo_haus_main.py --cycle
# Press Ctrl+C when done

# Restart service
sudo systemctl start boo-haus-display
```

### File Transfer Methods

**Using SCP (from your local machine):**
```bash
scp button_handler.py pi@your-pi:/home/pi/boo_haus_display/
scp boo_haus_config.json pi@your-pi:/home/pi/boo_haus_display/
```

**Using SFTP/WinSCP:** Connect and drag-and-drop files

**Converting Windows Line Endings:**
If you transfer scripts from Windows, always convert line endings:
```bash
dos2unix filename.sh
# or
sed -i 's/\r$//' filename.sh
```

## Development Environment

Target platform: Raspberry Pi (3/4/5 or Zero W) with Raspbian/Raspberry Pi OS
Display: Pimoroni Inky Impression 7.3" (800x480px, 7-color e-ink)
Python: 3.7+
Dependencies: See `quick_start.sh` or `installation_guide.md`

## Notes for Future Development

### Known Implementation Details

- **Sleep Interval:** The `run_continuous()` method breaks the cycle interval into 1-second sleeps to allow responsive button handling. This is critical for button functionality during the 300-second wait period.

- **Button Debouncing:** Button D has a longer debounce time (2 seconds vs 0.5 seconds for A/B/C) to prevent false triggers caused by electrical interference during display refreshes. The display refresh takes ~27 seconds and can cause GPIO noise.

- **Thread Safety:** Button callbacks run in a background thread. The `button_action_pending` flag is used to coordinate between the button thread and main loop.

- **State Persistence:** The display position is saved to `display_state.json` after each update. Service restarts will resume from the last position.

### Code-Specific Notes

- News scraper has sophisticated digest detection (see `digest_detector.py` and `config.py`)
- Calendar and news screens use existing display modules (`calendar_display.py`, `news_display.py`) and paste content area into base screen layout
- Water quality and sewage data are UK-specific (East Devon/Exmouth)
- Bin collection scraper is specific to East Devon Council
- Consider refactoring hardcoded API keys and location data from `screens/__init__.py` into config

### Common Gotchas

1. **Windows Line Endings:** Scripts transferred from Windows must be converted with `dos2unix` or they won't execute on Linux
2. **GPIO Permissions:** User must be in `gpio` group for button functionality
3. **Service vs Manual:** Buttons only work in `--cycle` mode (used by service), not in `--once` mode (used by cron)
4. **Display Refresh Time:** Inky display refresh takes ~10-15 seconds, during which button presses may queue up (handled by debouncing)
