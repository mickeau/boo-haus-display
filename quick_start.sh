#!/bin/bash
# Boo Haus Display - Quick Start Installation Script
# Run this script to set up the display system

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
INSTALL_DIR_DEFAULT="$SCRIPT_DIR"
read -p "Enter installation directory (default: $INSTALL_DIR_DEFAULT): " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$INSTALL_DIR_DEFAULT}

echo "📂 Installation directory: $INSTALL_DIR"
read -p "Is this correct? (y/n): " CONFIRM_DIR
if [ "$CONFIRM_DIR" != "y" ]; then
    echo "Exiting. Please re-run and specify the correct directory."
    exit 1
fi
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ Directory not found: $INSTALL_DIR"
    echo "Clone or copy the repository first, then run quick_start.sh from that checkout."
    exit 1
fi

cd "$INSTALL_DIR"

if [ ! -f "boo_haus_main.py" ] || [ ! -f "boo_haus_config.example.json" ]; then
    echo "❌ $INSTALL_DIR does not look like a complete Boo Haus Display checkout."
    echo "Expected boo_haus_main.py and boo_haus_config.example.json."
    exit 1
fi

# Create runtime directories
echo "Creating runtime directories..."
mkdir -p display_images
mkdir -p logs

echo "✅ Runtime directories created"
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

if [ -f "requirements.txt" ]; then
    pip3 install --user -r requirements.txt
else
    pip3 install --user pillow requests beautifulsoup4 feedparser pytz flask
fi

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

# Install Anthropic dependency for optional news summaries
echo ""
echo "Install Anthropic support for AI news summaries? (y/n)"
read -r INSTALL_ANTHROPIC
if [ "$INSTALL_ANTHROPIC" = "y" ]; then
    pip3 install --user anthropic
    echo "✅ Anthropic support installed"
else
    echo "⏭️  Skipping Anthropic support"
fi

# Install Inky display library (Raspberry Pi only)
echo ""
echo "Install Inky display library? (y for Raspberry Pi, n for testing on other systems)"
read -r INSTALL_INKY
if [ "$INSTALL_INKY" = "y" ]; then
    pip3 install --user gpiod inky[rpi,example-depends]
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

    read -p "Enter your OpenWeather API key (leave blank to skip weather): " OPENWEATHER_API_KEY
    read -p "Enter your Anthropic API key for news summaries (leave blank to skip summaries): " ANTHROPIC_API_KEY
    read -p "Enter your UPRN (UK Property Reference Number, leave blank if unknown): " UPRN
    read -p "Enter your Postcode: " POSTCODE
    read -p "Enter your Latitude: " LATITUDE
    read -p "Enter your Longitude: " LONGITUDE

    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            python3 - << EOF
from pathlib import Path

env_path = Path(".env")
content = env_path.read_text()
content = content.replace("YOUR_OPENWEATHER_API_KEY_HERE", "${OPENWEATHER_API_KEY:-YOUR_OPENWEATHER_API_KEY_HERE}")
content = content.replace("YOUR_ANTHROPIC_API_KEY_HERE", "${ANTHROPIC_API_KEY:-YOUR_ANTHROPIC_API_KEY_HERE}")
env_path.write_text(content)
EOF
        else
            cat > .env << EOF
# Boo Haus Display local secrets.
# This file is ignored by git.

OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY:-YOUR_OPENWEATHER_API_KEY_HERE}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-YOUR_ANTHROPIC_API_KEY_HERE}
EOF
        fi
        chmod 600 .env
        echo "✅ Local .env file created"
    else
        echo "ℹ️  .env already exists, keeping existing"
    fi

    if [ ! -f "boo_haus_config.example.json" ]; then
        echo "❌ boo_haus_config.example.json not found. Run this script from a complete checkout."
        exit 1
    fi

    export UPRN POSTCODE LATITUDE LONGITUDE
    python3 - << 'EOF'
import json
import os
from pathlib import Path

example_path = Path("boo_haus_config.example.json")
config_path = Path("boo_haus_config.json")
data = json.loads(example_path.read_text())

locations = data.setdefault("locations", {})
if os.environ.get("UPRN"):
    locations["uprn"] = os.environ["UPRN"]
if os.environ.get("POSTCODE"):
    locations["postcode"] = os.environ["POSTCODE"]

for env_key, config_key in (("LATITUDE", "latitude"), ("LONGITUDE", "longitude")):
    value = os.environ.get(env_key, "").strip()
    if not value:
        continue
    try:
        locations[config_key] = float(value)
    except ValueError:
        print(f"⚠️  Ignoring invalid {env_key.lower()}: {value}")

config_path.write_text(json.dumps(data, indent=2) + "\n")
EOF
    echo "✅ Configuration file created"
    read -p "Would you like to open boo_haus_config.json for further editing now? (y/n): " EDIT_CONFIG
    if [ "$EDIT_CONFIG" = "y" ]; then
        nano boo_haus_config.json
    fi
else
    echo "ℹ️  Configuration file already exists, keeping existing"
    read -p "Would you like to open boo_haus_config.json for editing? (y/n): " EDIT_CONFIG
    if [ "$EDIT_CONFIG" = "y" ]; then
        nano boo_haus_config.json
    fi
fi

# Create sample birthdays.json if not exists
if [ ! -f "birthdays.json" ]; then
    echo "Creating sample birthdays file..."
    echo "You can add multiple birthdays. Type 'done' when finished."
    BIRTHDAYS_JSON="["
    FIRST_BIRTHDAY=true
    while true; do
        read -p "Enter name for birthday (or 'done' to finish): " B_NAME
        if [ "$B_NAME" = "done" ]; then
            break
        fi
        read -p "Enter month for $B_NAME (1-12): " B_MONTH
        read -p "Enter day for $B_NAME (1-31): " B_DAY

        if [ "$FIRST_BIRTHDAY" = false ]; then
            BIRTHDAYS_JSON+=","
        fi
        BIRTHDAYS_JSON+="\n  {\n    \"name\": \"$B_NAME\",\n    \"month\": $B_MONTH,\n    \"day\": $B_DAY\n  }"
        FIRST_BIRTHDAY=false
    done
    BIRTHDAYS_JSON+="\n]"

    echo -e "$BIRTHDAYS_JSON" > birthdays.json
    echo "✅ Sample birthdays file created"
    read -p "Would you like to open birthdays.json for further editing now? (y/n): " EDIT_BIRTHDAYS
    if [ "$EDIT_BIRTHDAYS" = "y" ]; then
        nano birthdays.json
    fi
else
    echo "ℹ️  Birthdays file already exists, keeping existing"
    read -p "Would you like to open birthdays.json for editing? (y/n): " EDIT_BIRTHDAYS
    if [ "$EDIT_BIRTHDAYS" = "y" ]; then
        nano birthdays.json
    fi
fi

echo ""
echo "======================================"
echo "✅ Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Review and customize your configuration files:"
echo "   - .env (OpenWeather and Anthropic API keys)"
echo "   - boo_haus_config.json (locations, calendar IDs, screen settings)"
echo "   - birthdays.json (personal birthdays)"
echo ""
echo "2. Test the display:"
echo "   cd $INSTALL_DIR"
echo "   python3 boo_haus_main.py --once"
echo ""
read -p "Would you like to run a test display now? (y/n): " RUN_TEST
if [ "$RUN_TEST" = "y" ]; then
    echo "Running test display... (Press Ctrl+C to stop)"
    python3 boo_haus_main.py --once
    echo "Test display finished."
fi

echo "3. Set up automatic cycling with systemd:"
echo "   sudo $INSTALL_DIR/install_service.sh"
echo "   sudo $INSTALL_DIR/install_service.sh --dashboard  # also install dashboard"
echo ""
echo "   Cron is possible for simple one-shot updates, but buttons only work in"
echo "   --cycle mode and daily news refresh is already handled by boo_haus_main.py."
echo ""
echo "For Google Calendar:"
echo "   - Get credentials.json from Google Cloud Console"
echo "   - Place in $INSTALL_DIR"
echo "   - Enable calendar screen in config (boo_haus_config.json)"
echo ""
echo "======================================"
echo ""

echo "The checked-in install_service.sh is ready to use when you want systemd setup."

echo ""
echo "Happy displaying! 🎨📺"
