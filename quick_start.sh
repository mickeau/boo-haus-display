#!/bin/bash
# Boo Haus Display - Quick Start Installation Script
# Run this script to set up the display system

set -e  # Exit on error

echo "======================================"
echo "Boo Haus Display - Quick Start Setup"
echo "======================================"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: Not running on Raspberry Pi. Inky display features may not work."
    echo "   Press Enter to continue anyway, or Ctrl+C to cancel."
    read
fi

# Get installation directory
INSTALL_DIR="$HOME/boo_haus_display"
echo "📂 Installation directory: $INSTALL_DIR"
echo ""

# Create directory structure
echo "Creating directory structure..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/screens"
mkdir -p "$INSTALL_DIR/display_images"
mkdir -p "$INSTALL_DIR/logs"

cd "$INSTALL_DIR"

# Create __init__.py for screens package
touch screens/__init__.py

echo "✅ Directory structure created"
echo ""

# Check Python version
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3 first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION found"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
echo "This may take a few minutes..."
echo ""

pip3 install --user pillow requests beautifulsoup4 feedparser pytz

# Install Google Calendar dependencies (optional)
echo ""
echo "Install Google Calendar support? (y/n)"
read -r INSTALL_GCAL
if [ "$INSTALL_GCAL" = "y" ]; then
    pip3 install --user google-auth-httplib2 google-auth-oauthlib google-api-python-client
    echo "✅ Google Calendar support installed"
else
    echo "⏭️  Skipping Google Calendar support"
fi

# Install Inky display library (Raspberry Pi only)
echo ""
echo "Install Inky display library? (y for Raspberry Pi, n for testing on other systems)"
read -r INSTALL_INKY
if [ "$INSTALL_INKY" = "y" ]; then
    pip3 install --user inky[rpi,example-depends]
    echo "✅ Inky display library installed"
else
    echo "⏭️  Skipping Inky display library"
fi

echo ""
echo "✅ All dependencies installed"
echo ""

# Create default configuration if not exists
if [ ! -f "boo_haus_config.json" ]; then
    echo "Creating default configuration..."
    cat > boo_haus_config.json << 'EOF'
{
  "display": {
    "width": 800,
    "height": 480,
    "cycle_interval_seconds": 300,
    "save_images": true,
    "display_on_inky": true,
    "image_directory": "display_images"
  },
  "screens": {
    "weather": {"enabled": true},
    "week": {"enabled": true},
    "nfl": {"enabled": true},
    "calendar": {"enabled": false},
    "news": {"enabled": true},
    "birthday": {"enabled": true}
  },
  "special_dates": {
    "11-07": "Happy Booversary!",
    "21-03": "Happy Birthday Daddy!",
    "19-11": "Happy Birthday Mummy!",
    "29-06": "Happy Birthday Alice!",
    "22-10": "Happy Birthday Rosie!",
    "25-12": "Merry Christmas!",
    "01-01": "Happy New Year!"
  },
  "data_refresh": {
    "news_scraper_hour": 3,
    "news_scraper_enabled": true
  },
  "state_file": "display_state.json"
}
EOF
    echo "✅ Configuration file created"
else
    echo "ℹ️  Configuration file already exists, keeping existing"
fi

# Create sample birthdays.json if not exists
if [ ! -f "birthdays.json" ]; then
    echo "Creating sample birthdays file..."
    cat > birthdays.json << 'EOF'
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
EOF
    echo "✅ Sample birthdays file created"
else
    echo "ℹ️  Birthdays file already exists, keeping existing"
fi

echo ""
echo "======================================"
echo "✅ Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Copy your Python scripts to: $INSTALL_DIR"
echo "   - boo_haus_main.py"
echo "   - base_screen.py"
echo "   - All screen files to screens/ directory"
echo "   - Data fetcher scripts (weather_fetcher.py, etc.)"
echo ""
echo "2. Edit configuration: nano boo_haus_config.json"
echo ""
echo "3. Edit birthdays: nano birthdays.json"
echo ""
echo "4. Test the display:"
echo "   cd $INSTALL_DIR"
echo "   python3 boo_haus_main.py --once"
echo ""
echo "5. Set up automatic cycling:"
echo "   a) Using cron (simple):"
echo "      crontab -e"
echo "      Add: */5 * * * * cd $INSTALL_DIR && python3 boo_haus_main.py --once"
echo ""
echo "   b) Using systemd (advanced):"
echo "      sudo $INSTALL_DIR/install_service.sh"
echo ""
echo "6. Set up news scraper (optional):"
echo "   crontab -e"
echo "   Add: 0 3 * * * cd $INSTALL_DIR && python3 news_scraper.py"
echo "   Add: 0 3 * * * cd $INSTALL_DIR && python3 news_summariser.py"
echo ""
echo "For Google Calendar:"
echo "   - Get credentials.json from Google Cloud Console"
echo "   - Place in $INSTALL_DIR"
echo "   - Enable calendar screen in config"
echo ""
echo "======================================"
echo ""

# Offer to create service installer
echo "Create systemd service installer script? (y/n)"
read -r CREATE_SERVICE
if [ "$CREATE_SERVICE" = "y" ]; then
    cat > install_service.sh << 'SERVICEEOF'
#!/bin/bash
# Install Boo Haus Display as a systemd service

if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo: sudo ./install_service.sh"
    exit 1
fi

INSTALL_DIR="$HOME/boo_haus_display"
SERVICE_FILE="/etc/systemd/system/boo-haus-display.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Boo Haus Admin Display
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/boo_haus_main.py --cycle
Restart=always
RestartSec=10
StandardOutput=append:$INSTALL_DIR/logs/display.log
StandardError=append:$INSTALL_DIR/logs/error.log

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created: $SERVICE_FILE"
echo ""
echo "Enabling and starting service..."
systemctl daemon-reload
systemctl enable boo-haus-display
systemctl start boo-haus-display

echo ""
echo "✅ Service installed and started!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status boo-haus-display   # Check status"
echo "  sudo systemctl stop boo-haus-display     # Stop service"
echo "  sudo systemctl start boo-haus-display    # Start service"
echo "  sudo systemctl restart boo-haus-display  # Restart service"
echo "  sudo journalctl -u boo-haus-display -f   # View logs"
echo ""
SERVICEEOF
    
    chmod +x install_service.sh
    echo "✅ Created install_service.sh"
    echo "   Run with: sudo ./install_service.sh"
fi

echo ""
echo "Happy displaying! 🎨📺"