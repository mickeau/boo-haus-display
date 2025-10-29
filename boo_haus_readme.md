# 🏠 Boo Haus Admin Display System

A modular, extensible e-ink display system for Inky Impression 7.3" that cycles through various information screens. Perfect for home dashboards showing weather, calendar events, news, NFL scores, and more!

## ✨ Features

- **6 Built-in Screens:**
  - 🌤️ **Weather**: Current conditions, 5-day forecast, tide times, water quality, sewage alerts
  - 📅 **This Week**: 5-day forecast, upcoming bin collections, birthdays
  - 🏈 **NFL Scores**: Live scores, schedules, and standings
  - 📆 **Calendar**: Google Calendar events
  - 📰 **News**: Cycling news summaries from cached stories
  - 🎂 **Birthdays**: Upcoming birthday tracker

- **Smart Features:**
  - Special greetings on birthdays, holidays, and anniversaries
  - Consistent, beautiful header across all screens
  - Automatic screen cycling (configurable interval)
  - Persistent state management
  - Automatic daily news updates (3 AM)
  - Error handling and graceful degradation

- **Easy Customization:**
  - JSON-based configuration
  - Modular screen architecture
  - Simple to add new screens
  - Flexible layout utilities
  - Enable/disable individual screens

## 📸 Screenshots

*(Images showing each screen type would go here)*

## 🚀 Quick Start

### 1. Run the Installation Script

```bash
chmod +x quick_start.sh
./quick_start.sh
```

This will:
- Create directory structure
- Install all Python dependencies
- Create default configuration files
- Set up logging directories

### 2. Set Up Configuration Files

The repository includes example configuration files that you need to customize with your own API keys and personal data:

```bash
cd ~/boo_haus_display

# Copy example config files to create your local versions
cp boo_haus_config.example.json boo_haus_config.json
cp birthdays.example.json birthdays.json
```

**Important:** The actual config files (`boo_haus_config.json`, `birthdays.json`, `credentials.json`, `token.json`) are excluded from git to protect your privacy and API keys.

#### Get Your API Keys

1. **OpenWeather API Key** (Required for weather features)
   - Sign up at [OpenWeatherMap](https://openweathermap.org/api)
   - Get a free API key
   - Add to `boo_haus_config.json` under `api_keys.openweather`

2. **Google Calendar Credentials** (Optional - for calendar features)
   - Follow [Google Calendar API Quickstart](https://developers.google.com/calendar/api/quickstart/python)
   - Download `credentials.json` and place in project root
   - First run will generate `token.json` automatically

3. **Update Your Location**
   - Edit `boo_haus_config.json` and update:
     - `locations.postcode` - Your UK postcode
     - `locations.latitude` and `locations.longitude` - Your coordinates
     - `locations.uprn` - UK Property Reference Number (optional)

4. **Add Your Birthdays**
   - Edit `birthdays.json` with your family and friends' birthdays
   - Use format: `{"name": "John", "month": 3, "day": 21, "date": "03-21"}`

5. **Customize Special Dates**
   - Edit `special_dates` section in `boo_haus_config.json`
   - Add your own special dates in DD-MM format

### 3. Copy Your Files (If migrating from existing setup)

```bash
cd ~/boo_haus_display

# If you already have these files elsewhere, copy them:
# cp /path/to/boo_haus_main.py .
# cp /path/to/base_screen.py .
# etc.

# Otherwise, all files are already in the repository
```

### 4. Configure

Edit `boo_haus_config.json` to customize your display:

```json
{
  "display": {
    "cycle_interval_seconds": 300  // 5 minutes per screen
  },
  "screens": {
    "weather": {"enabled": true},
    "nfl": {"enabled": false}  // Disable if not interested
  },
  "special_dates": {
    "25-12": "Merry Christmas!"
  }
}
```

### 5. Test It

```bash
# Test a single screen
python3 boo_haus_main.py --screen weather

# Display next screen in cycle
python3 boo_haus_main.py --once

# Start continuous cycling
python3 boo_haus_main.py --cycle
```

### 6. Set Up Automatic Updates

**Option A: Cron (Simple)**

```bash
crontab -e
```

Add these lines:

```cron
# Update display every 5 minutes
*/5 * * * * cd ~/boo_haus_display && python3 boo_haus_main.py --once >> logs/display.log 2>&1

# Run news scraper daily at 3 AM
0 3 * * * cd ~/boo_haus_display && python3 news_scraper.py >> logs/scraper.log 2>&1
0 3 * * * cd ~/boo_haus_display && python3 news_summariser.py >> logs/summariser.log 2>&1
```

**Option B: Systemd Service (Advanced)**

```bash
sudo ./install_service.sh
```

## 📁 Project Structure

```
boo_haus_display/
├── boo_haus_main.py              # Main application
├── base_screen.py                # Base screen class
├── boo_haus_config.json          # Configuration
├── quick_start.sh                # Installation script
├── install_service.sh            # Systemd service installer
├── screens/                      # Screen implementations
│   ├── __init__.py
│   ├── weather_screen.py
│   ├── week_screen.py
│   ├── nfl_screen.py
│   ├── calendar_screen.py
│   ├── news_screen.py
│   └── birthday_screen.py
├── birthdays.json                # Birthday data
├── display_state.json            # Current state (auto-generated)
├── logs/                         # Log files (auto-generated)
├── display_images/               # Saved screen images (auto-generated)
└── [data fetcher scripts]        # Your existing data fetchers
```

## 🔧 Configuration Reference

### Display Settings

```json
"display": {
  "width": 800,                      // Display width in pixels
  "height": 480,                     // Display height in pixels
  "cycle_interval_seconds": 300,     // Time between screen changes
  "save_images": true,               // Save PNG copies of screens
  "display_on_inky": true,           // Actually update the e-ink display
  "image_directory": "display_images"
}
```

### Screen Settings

```json
"screens": {
  "weather": {
    "enabled": true,
    "show_tide_times": true,
    "show_water_quality": true,
    "show_sewage_alerts": true
  },
  "nfl": {
    "enabled": true  // Set to false to disable
  }
}
```

### Special Dates

Date format is DD-MM (day-month):

```json
"special_dates": {
  "25-12": "Merry Christmas!",
  "01-01": "Happy New Year!",
  "14-02": "Happy Valentine's Day!"
}
```

### Data Refresh

```json
"data_refresh": {
  "news_scraper_hour": 3,        // Run news scraper at 3 AM
  "news_scraper_enabled": true
}
```

## 🎨 Creating Custom Screens

### 1. Create a New Screen File

Create `screens/my_custom_screen.py`:

```python
from base_screen import BaseScreen

class MyCustomScreen(BaseScreen):
    @property
    def name(self) -> str:
        return "MyCustom"
    
    def render_content(self):
        # Get the content area
        x, y, width, height = self.get_content_area()
        
        # Draw a section title
        y = self.draw_section_title("My Custom Screen", y)
        
        # Draw some text
        self.draw.text((x, y), "Hello from my custom screen!", 
                      font=self.font_large, fill=self.BLACK)
        
        # Use utility methods
        lines = self.wrap_text("Long text that needs wrapping...", 
                              width - 40, self.font_small)
        
        y += 30
        for line in lines:
            self.draw.text((x, y), line, 
                          font=self.font_small, fill=self.BLACK)
            y += 18
```

### 2. Register the Screen

Edit `boo_haus_main.py`:

```python
# Add import
from screens.my_custom_screen import MyCustomScreen

# Add to screens list in __init__
self.screens = [
    WeatherScreen(self.config),
    MyCustomScreen(self.config),  # Add here
    WeekScreen(self.config),
    # ...
]
```

### 3. Configure the Screen

Edit `boo_haus_config.json`:

```json
"screens": {
  "mycustom": {
    "enabled": true,
    "custom_setting": "value"
  }
}
```

### Available Utility Methods

From `BaseScreen`:

- `draw_section_title(title, y, color)` - Draw a section header
- `wrap_text(text, max_width, font)` - Wrap text to fit width
- `draw_text_box(text, x, y, width, font, color)` - Draw wrapped text
- `draw_icon_with_label(icon, label, value, x, y, color)` - Icon + text
- `draw_weather_icon(description, x, y, size)` - Weather icons
- `get_content_area()` - Get available drawing space
- `get_special_greeting()` - Check for special date greeting

### Color Palette

Available colors:
- `self.BLACK` - (0, 0, 0)
- `self.WHITE` - (255, 255, 255)
- `self.RED` - (255, 0, 0)
- `self.YELLOW` - (255, 255, 0)
- `self.ORANGE` - (255, 140, 0)
- `self.GREEN` - (0, 255, 0)
- `self.BLUE` - (0, 0, 255)
- `self.PINK` - (255, 192, 203)
- `self.PALE_GREEN` - (200, 255, 200)

## 🐛 Troubleshooting

### Display Not Updating

```bash
# Check if process is running
ps aux | grep boo_haus_main

# Test manually
cd ~/boo_haus_display
python3 boo_haus_main.py --once

# Check logs
tail -f logs/display.log
```

### Missing Data

```bash
# Test individual data fetchers
python3 weather_fetcher.py
python3 bin_collections.py
python3 tide_times.py

# Check configuration
cat boo_haus_config.json
```

### Inky Display Issues

```bash
# Test Inky library
python3 -c "from inky.auto import auto; print('OK')"

# Check I2C (if needed)
sudo i2cdetect -y 1
```

### Calendar Not Working

```bash
# Remove old token
rm token.json

# Re-authenticate
python3 calendar_display.py
```

### News Not Updating

```bash
# Run scraper manually
python3 news_scraper.py

# Check cache file
ls -lh headline_summaries_cache.json

# Verify cron job
crontab -l | grep news
```

## 📊 Monitoring

### View Logs

```bash
# Display logs
tail -f ~/boo_haus_display/logs/display.log

# Scraper logs
tail -f ~/boo_haus_display/logs/scraper.log

# System service logs
sudo journalctl -u boo-haus-display -f
```

### Check Status

```bash
# Service status
sudo systemctl status boo-haus-display

# Current state
cat display_state.json

# Last generated images
ls -lht display_images/ | head -10
```

## 🔄 Maintenance

### Daily
- Verify display is updating
- Check for error messages

### Weekly
- Review logs for issues
- Verify all data sources working

### Monthly
- Update birthdays.json
- Review special dates
- Clean old log files
- Update system packages

### As Needed
- Rotate API keys
- Re-authenticate services
- Add/remove screens
- Update configuration

## 🤝 Contributing

To add new features:

1. Create a new screen class
2. Add data fetcher if needed
3. Update configuration schema
4. Test thoroughly
5. Document in README

## 📄 License

This project integrates with various third-party services. Ensure compliance with:
- OpenWeather API terms of service
- Google Calendar API terms of service
- BBC website terms (for tide scraping)
- Environment Agency open data license
- ESPN API acceptable use

## 💡 Tips & Tricks

### Save Power
- Increase cycle_interval_seconds for less frequent updates
- Disable unused screens
- Use cron instead of continuous service mode

### Improve Performance
- Images are cached automatically
- Old images auto-deleted after 7 days
- State persists across restarts

### Debug Mode
```bash
# Save images without displaying
edit config: "display_on_inky": false

# Test specific screen
python3 boo_haus_main.py --screen weather

# View saved image
xdg-open display_images/weather_latest.png
```

### Custom Greetings
Add as many special dates as you want:
```json
"special_dates": {
  "01-04": "April Fools!",
  "31-10": "Happy Halloween!",
  "05-11": "Remember, remember..."
}
```

## 🆘 Support

For issues:
1. Check troubleshooting section
2. Review logs
3. Test individual components
4. Verify configuration

Component-specific support:
- Inky Display: [Pimoroni Support](https://support.pimoroni.com/)
- Google Calendar: [API Documentation](https://developers.google.com/calendar)
- OpenWeather: [API Support](https://openweathermap.org/api)

## 🎉 Enjoy Your Display!

Built with ❤️ for the Boo Haus family.
