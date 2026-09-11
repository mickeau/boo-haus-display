#!/bin/bash
echo "============================================"
echo "Boo Haus Display - Dependency Installation"
echo "============================================"

# Update system
echo ""
echo "Updating package lists..."
sudo apt-get update

# Install system packages where available
echo ""
echo "Installing system packages..."
sudo apt-get install -y \
    python3-pil \
    python3-requests \
    python3-bs4 \
    python3-feedparser \
    python3-flask \
    python3-tz \
    python3-pip

# Install packages only available via pip
echo ""
echo "Installing pip packages..."
sudo pip3 install --break-system-packages gpiod inky[rpi,example-depends]

# Ask about Google Calendar
echo ""
read -p "Install Google Calendar support? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing Google Calendar packages..."
    sudo pip3 install --break-system-packages \
        google-auth-httplib2 \
        google-auth-oauthlib \
        google-api-python-client
    echo "✓ Google Calendar support installed"
fi

# Ask about Anthropic summaries
echo ""
read -p "Install Anthropic support for news summaries? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing Anthropic package..."
    sudo pip3 install --break-system-packages anthropic
    echo "✓ Anthropic support installed"
fi

# Test installation
echo ""
echo "============================================"
echo "Testing installation..."
echo "============================================"

python3 << 'EOF'
import sys
print(f"Python version: {sys.version}\n")

test_packages = {
    'PIL': 'pillow',
    'requests': 'requests',
    'bs4': 'beautifulsoup4',
    'feedparser': 'feedparser',
    'flask': 'flask',
    'pytz': 'pytz',
    'gpiod': 'gpiod (needed for buttons)',
    'inky': 'inky (optional for non-Pi)',
}

failed = []
for module, package in test_packages.items():
    try:
        __import__(module)
        print(f"✓ {package}")
    except ImportError:
        print(f"✗ {package} - MISSING")
        failed.append(package)

if failed:
    print(f"\n❌ Failed packages: {', '.join(failed)}")
    print("Run: sudo pip3 install --break-system-packages " + ' '.join(failed))
else:
    print("\n✅ All required packages installed!")
EOF

echo ""
echo "============================================"
echo "Installation complete!"
echo "============================================"
