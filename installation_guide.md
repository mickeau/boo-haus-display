# Boo Haus Display - Complete Installation Guide

## 📦 What You Need

### Hardware
- Raspberry Pi (3/4/5 or Zero W recommended)
- Pimoroni Inky Impression 7.3" display
- MicroSD card (16GB+ recommended)
- Power supply

### Accounts & API Keys
- OpenWeather API key (free tier: https://openweathermap.org/api)
- Google Calendar API credentials (if using calendar screen)
- Internet connection

## 🚀 Step-by-Step Installation

### 1. Prepare Your Raspberry Pi

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
sudo apt-get install -y python3 python3-pip git
sudo apt-get install -y libjpeg-dev zlib1g-dev libfreetype6-dev
```

### 2. Create Project Directory

```bash
# Create and enter directory
mkdir -p ~/boo_haus_display
cd ~/boo_haus_display

# Create subdirectories
mkdir -p screens logs display_images
```

### 3. Install Python Dependencies

```bash
# Core dependencies
pip3 install pillow requests beautifulsoup4 feedparser pytz

# Inky display library (for Raspberry Pi)
pip3 install inky[rpi,example-depends]

# Google Calendar support (optional)
pip3 install google-auth-httplib2 google-auth-oauthlib google-api-python-client
```

### 4. Copy All Files

Copy the files into this structure:

```
~/boo_haus_display/
├── boo_haus_main.py              ← Main application
├── base_screen.py                ← Base screen class
├── boo_haus_config.json          ← Configuration
├── birthdays.json                ← Birthday data
│
├── screens/                      ← Screen implementations
│   ├── __init__.py
│   ├── weather_screen.py
│   ├── week_screen.py
│   ├── nfl_screen.py
│   ├── calendar_screen.py
│   ├── news_screen.py
│   └── birthday_screen.py
│
├── Data fetchers (your existing scripts)
│   ├── weather_fetcher.py
│   ├── bin_collections.py
│   ├── tide_times.py
│   ├── water_quality.py
│   ├── direct_sewage_api.py
│   ├── nfl_scores.py
│   ├── calendar_display.py
│   ├── news_display.py
│   ├── news_scraper.py
│   ├── news_summariser.py
│   └── birthday_tracker.py
│
├── logs/                         ← Auto-generated
├── display_images/               ← Auto-generated
├── display_state.json            ← Auto-generated
└── news_display_state.json       ← Auto-generated
```

### 5. Configure the System

#### Edit `boo_haus_config.json`:

```json
{
  "display": {
    "width": 800,
    "height": 480,
    "cycle_interval_seconds": 300,
    "save_images": true,
    "display_on_inky": true
  },
  "api_keys": {
    "openweather": "YOUR_API_KEY_HERE"
  },
  "locations": {
    "uprn": "YOUR_UPRN_HERE",
    "postcode": "YOUR_POSTCODE_HERE"
  },
  "screens": {
    "weather": {"enabled": true},
    "week": {"enabled": true},
    "nfl": {"enabled": true},
    "calendar": {"enabled": false},
    "news": {"enabled": true},
    "birthday": {"enabled": true}
  }
}
```

#### Edit `birthdays.json`:

```json
[
  {
    "name": "Alice",
    "month": 6,
    "day": 29
  },
  {
    "name": "Rosie",
    "month": 10,
    "day": 22
  }
]
```

### 6. Test Each Component

```bash
# Test individual data fetchers
python3 weather_fetcher.py
python3 bin_collections.py
python3 tide_times.py
python3 nfl_scores.py

# Test the display system
python3 boo_haus_main.py --screen weather
python3 boo_haus_main.py --screen week
```

### 7. Set Up Google Calendar (Optional)

If you want to use the calendar screen:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "Google Calendar API"
4. Create OAuth 2.0 credentials
5. Download as `credentials.json`
6. Place in `~/boo_haus_display/`
7. Run once to authenticate:
   ```bash
   python3 boo_haus_main.py --screen calendar
   ```
8. A browser will open - authorize the app
9. Enable in config:
   ```json
   "screens": {
     "calendar": {"enabled": true}
   }
   ```

### 8. Set Up Automatic Updates

#### Option A: Cron (Recommended for beginners)

```bash
crontab -e
```

Add these lines:

```cron
# Update display every 5 minutes
*/5 * * * * cd /home/pi/boo_haus_display && /usr/bin/python3 boo_haus_main.py --once >> logs/display.log 2>&1

# Run news scraper daily at 3 AM
0 3 * * * cd /home/pi/boo_haus_display && /usr/bin/python3 news_scraper.py >> logs/scraper.log 2>&1

# Run news summariser daily at 3:30 AM
30 3 * * * cd /home/pi/boo_haus_display && /usr/bin/python3 news_summariser.py >> logs/summariser.log 2>&1
```

#### Option B: Systemd Service (Advanced)

Create `/etc/systemd/system/boo-haus-display.service`:

```ini
[Unit]
Description=Boo Haus Admin Display
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/boo_haus_display
ExecStart=/usr/bin/python3 /home/pi/boo_haus_display/boo_haus_main.py --cycle
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/boo_haus_display/logs/display.log
StandardError=append:/home/pi/boo_haus_display/logs/error.log

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable boo-haus-display
sudo systemctl start boo-haus-display
sudo systemctl status boo-haus-display
```

## 🧪 Testing

### Test Individual Screens

```bash
cd ~/boo_haus_display

# Test each screen
python3 boo_haus_main.py --screen weather
python3 boo_haus_main.py --screen week
python3 boo_haus_main.py --screen nfl
python3 boo_haus_main.py --screen calendar
python3 boo_haus_main.py --screen news
python3 boo_haus_main.py --screen birthday
```

### Test Cycling

```bash
# Cycle once (display next screen)
python3 boo_haus_main.py --once

# Run continuous cycling (Ctrl+C to stop)
python3 boo_haus_main.py --cycle
```

### Check Saved Images

```bash
# Images are saved to display_images/ directory
ls -lht display_images/

# View latest image (if on desktop)
display display_images/weather_latest.png
```

## 🐛 Troubleshooting

### Display Not Updating

```bash
# Check if process is running
ps aux | grep boo_haus_main

# View logs
tail -f logs/display.log

# Test manually
python3 boo_haus_main.py --once
```

### Import Errors

```bash
# If you see "ModuleNotFoundError"
# Ensure you're in the correct directory
cd ~/boo_haus_display

# Check Python path
python3 -c "import sys; print(sys.path)"

# Reinstall dependencies
pip3 install --upgrade pillow requests beautifulsoup4
```

### Inky Display Not Working

```bash
# Test Inky library
python3 -c "from inky.auto import auto; print('OK')"

# Check I2C is enabled
sudo raspi-config
# Interface Options > I2C > Enable

# Check if display is detected
sudo i2cdetect -y 1
```

### Weather Data Not Loading

```bash
# Test API key
python3 weather_fetcher.py

# Check config
cat boo_haus_config.json | grep openweather

# Verify internet connection
ping -c 3 api.openweathermap.org
```

### Calendar Not Working

```bash
# Delete old token and re-authenticate
rm token.json
python3 boo_haus_main.py --screen calendar

# Check credentials file exists
ls -l credentials.json

# View calendar errors
tail -f logs/display.log | grep -i calendar
```

### News Not Updating

```bash
# Check cache file
ls -lh headline_summaries_cache.json

# Run scraper manually
python3 news_scraper.py

# Check scraper logs
tail -f logs/scraper.log

# Verify cron job
crontab -l | grep news
```

## 📊 Monitoring

### View Logs

```bash
# Real-time display log
tail -f logs/display.log

# Real-time scraper log
tail -f logs/scraper.log

# Service logs (if using systemd)
sudo journalctl -u boo-haus-display -f

# View all errors
grep -i error logs/*.log
```

### Check Status

```bash
# Display state
cat display_state.json

# News cycle state
cat news_display_state.json

# Last update time
ls -lt display_images/ | head -5

# Service status (if using systemd)
sudo systemctl status boo-haus-display
```

## 🔧 Customization

### Change Screen Order

Edit `boo_haus_main.py`, find this section:

```python
self.screens = [
    WeatherScreen(self.config),
    WeekScreen(self.config),
    NFLScreen(self.config),
    CalendarScreen(self.config),
    NewsScreen(self.config),
    BirthdayScreen(self.config)
]
```

Reorder as desired.

### Change Cycle Time

Edit `boo_haus_config.json`:

```json
"cycle_interval_seconds": 600  // 10 minutes
```

### Disable Screens

Edit `boo_haus_config.json`:

```json
"screens": {
  "nfl": {"enabled": false}  // Disable NFL screen
}
```

### Add Special Dates

Edit `boo_haus_config.json`:

```json
"special_dates": {
  "01-04": "April Fools!",
  "31-10": "Happy Halloween!"
}
```

## 🔄 Maintenance

### Daily
- Check display is updating

### Weekly
- Review logs for errors
- Verify data sources working

### Monthly
- Update birthdays.json
- Clean old log files
- Update system packages

### As Needed
- Rotate API keys
- Re-authenticate services
- Update Python dependencies

## 📚 Additional Resources

- [Inky Documentation](https://github.com/pimoroni/inky)
- [OpenWeather API](https://openweathermap.org/api)
- [Google Calendar API](https://developers.google.com/calendar)
- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)

## 🆘 Getting Help

If you encounter issues:

1. Check the troubleshooting section
2. Review logs for specific errors
3. Test individual components
4. Verify configuration files
5. Check internet connectivity
6. Ensure all dependencies are installed

## ✅ Quick Checklist

- [ ] Raspberry Pi set up with latest OS
- [ ] All Python dependencies installed
- [ ] Inky display connected and working
- [ ] All files copied to correct locations
- [ ] Configuration file edited
- [ ] Birthday data entered
- [ ] API keys configured
- [ ] Individual screens tested
- [ ] Automatic updates configured
- [ ] Display cycling successfully

Congratulations! Your Boo Haus Display is ready! 🎉
