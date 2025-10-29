# 🏠 Boo Haus Display

> A modular, extensible e-ink display system for Raspberry Pi with Inky Impression 7.3" display

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Platform: Raspberry Pi](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)

Perfect for home dashboards showing weather, calendar events, news, NFL scores, birthdays, and more!

## ✨ Features

- **6 Built-in Information Screens** - Weather, Calendar, News, NFL Scores, Weekly Forecast, Birthdays
- **Physical Button Controls** - 4 side-mounted buttons for navigation and control
- **Auto-Cycling Display** - Automatically rotates through enabled screens
- **Special Date Greetings** - Custom messages for birthdays, holidays, and anniversaries
- **Systemd Service Support** - Runs automatically on boot
- **Modular Architecture** - Easy to add custom screens
- **Privacy-First** - Config files with sensitive data excluded from repository

## 📸 Hardware

- **Display:** Pimoroni Inky Impression 7.3" (800x480px, 7-color e-ink)
- **Platform:** Raspberry Pi (3/4/5 or Zero W)
- **OS:** Raspberry Pi OS / Raspbian
- **Buttons:** 4 built-in GPIO buttons (Previous, Next, Pause, Refresh)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/boo-haus-display.git
cd boo-haus-display
```

### 2. Run Installation Script

```bash
chmod +x quick_start.sh
./quick_start.sh
```

### 3. Set Up Configuration

```bash
# Copy example configs and customize with your data
cp boo_haus_config.example.json boo_haus_config.json
cp birthdays.example.json birthdays.json

# Edit with your API keys and personal data
nano boo_haus_config.json
```

**You'll need:**
- OpenWeather API key (free from [openweathermap.org](https://openweathermap.org/api))
- Google Calendar credentials (optional - for calendar features)
- Your location coordinates

### 4. Test

```bash
# Test a single screen
python3 boo_haus_main.py --screen weather

# Start cycling
python3 boo_haus_main.py --cycle
```

### 5. Install as Service

```bash
# For automatic startup on boot
sudo ./install_service.sh
```

## 📖 Full Documentation

- **[Complete README](boo_haus_readme.md)** - Full features and configuration guide
- **[Installation Guide](installation_guide.md)** - Detailed setup instructions
- **[Button Guide](BUTTON_GUIDE.md)** - How to use physical buttons
- **[Service Guide](SERVICE_GUIDE.md)** - Managing the systemd service
- **[Developer Guide](CLAUDE.md)** - Technical documentation for developers

## ⚙️ Configuration

All configuration is in `boo_haus_config.json`:

```json
{
  "display": {
    "cycle_interval_seconds": 300
  },
  "screens": {
    "weather": {"enabled": true},
    "calendar": {"enabled": true},
    "news": {"enabled": true},
    "nfl": {"enabled": false}
  },
  "api_keys": {
    "openweather": "YOUR_API_KEY_HERE"
  }
}
```

## 🔘 Button Controls

- **Button A** - Previous screen
- **Button B** - Next screen
- **Button C** - Pause/Resume auto-cycling
- **Button D** - Force refresh current screen

## 🎨 Included Screens

1. **Weather** - Current conditions, 5-day forecast, tide times, water quality
2. **This Week** - 5-day forecast, bin collections, upcoming birthdays
3. **NFL Scores** - Live scores and schedules
4. **Calendar** - Upcoming Google Calendar events
5. **News** - Daily news summaries
6. **Birthdays** - Upcoming birthday tracker

## 🔒 Privacy & Security

**Important:** This repository excludes files with sensitive data:

- `boo_haus_config.json` - Contains API keys and location data
- `birthdays.json` - Personal birthday information
- `credentials.json` - Google OAuth credentials
- `token.json` - Authentication tokens

Use the provided `.example.json` files as templates. See `.gitignore` for full list.

## 🛠️ System Requirements

### Software
- Python 3.7+
- Pillow (image processing)
- Inky library (for e-ink display)
- gpiod (for button support)
- Requests, BeautifulSoup4, feedparser (for data fetching)
- Google Calendar API libraries (optional)

### Hardware (Recommended)
- Raspberry Pi 4 or 5
- Inky Impression 7.3" display
- Power supply (official Raspberry Pi PSU recommended)
- MicroSD card (16GB+)

## 📊 Project Structure

```
boo_haus_display/
├── boo_haus_main.py           # Main application
├── base_screen.py             # Base screen class
├── button_handler.py          # GPIO button handling
├── boo_haus_config.json       # Your config (not in repo)
├── boo_haus_config.example.json  # Config template
├── screens/                   # Screen implementations
│   ├── weather_screen.py
│   ├── calendar_screen.py
│   └── ...
├── install_service.sh         # Systemd installer
└── [data fetchers]            # Data source scripts
```

## 🤝 Contributing

Contributions welcome! To add a new screen:

1. Create a class inheriting from `BaseScreen`
2. Implement `name` property and `render_content()` method
3. Add to screen list in `boo_haus_main.py`
4. Test thoroughly
5. Submit a pull request

See [Developer Guide](CLAUDE.md) for detailed instructions.

## 📄 License

This project is open source. Please comply with:
- OpenWeather API terms of service
- Google Calendar API terms of service
- Third-party data source terms

## 🆘 Support

**Issues?**
1. Check [Troubleshooting](boo_haus_readme.md#troubleshooting) section
2. Review logs: `tail -f ~/boo_haus_display/logs/display.log`
3. Test components individually
4. Verify configuration

**Component Support:**
- [Pimoroni Support](https://support.pimoroni.com/) - Inky Display
- [Google Calendar API](https://developers.google.com/calendar) - Calendar integration
- [OpenWeather API](https://openweathermap.org/api) - Weather data

## 🙏 Acknowledgments

Built with:
- [Pimoroni Inky Impression](https://shop.pimoroni.com/products/inky-impression) - E-ink display
- [Pillow](https://python-pillow.org/) - Image processing
- [OpenWeatherMap](https://openweathermap.org/) - Weather data

---

Made with ❤️ for the Boo Haus family
