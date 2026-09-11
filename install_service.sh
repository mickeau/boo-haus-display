#!/bin/bash
# Install Boo Haus Display as a systemd service
# This will make the display run automatically on boot

set -e  # Exit on error

INSTALL_DASHBOARD=false
START_SERVICES=true

while [ $# -gt 0 ]; do
    case "$1" in
        --dashboard)
            INSTALL_DASHBOARD=true
            ;;
        --no-start)
            START_SERVICES=false
            ;;
        --help|-h)
            echo "Usage: sudo ./install_service.sh [--dashboard] [--no-start]"
            echo "  --dashboard  Also install boo-haus-dashboard.service"
            echo "  --no-start   Install and enable services without starting them"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: sudo ./install_service.sh [--dashboard] [--no-start]"
            exit 1
            ;;
    esac
    shift
done

echo "======================================"
echo "Boo Haus Display - Service Installer"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run with sudo"
    echo "Usage: sudo ./install_service.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${BOO_HAUS_INSTALL_DIR:-$SCRIPT_DIR}"

echo "Installing service for user: $ACTUAL_USER"
echo "Installation directory: $INSTALL_DIR"
echo ""

# Check if directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ Directory not found: $INSTALL_DIR"
    echo "Run this installer from the boo_haus_display directory, or set BOO_HAUS_INSTALL_DIR."
    exit 1
fi

# Check if boo_haus_main.py exists
if [ ! -f "$INSTALL_DIR/boo_haus_main.py" ]; then
    echo "❌ boo_haus_main.py not found in $INSTALL_DIR"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$INSTALL_DIR/logs"
chown "$ACTUAL_USER:$ACTUAL_USER" "$INSTALL_DIR/logs"

# Copy service file to systemd directory
SERVICE_FILE="/etc/systemd/system/boo-haus-display.service"

echo "Creating service file: $SERVICE_FILE"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Boo Haus Admin Display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/boo_haus_main.py --cycle
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$INSTALL_DIR/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created"
echo ""

if [ "$INSTALL_DASHBOARD" = true ]; then
    DASHBOARD_SERVICE_FILE="/etc/systemd/system/boo-haus-dashboard.service"
    echo "Creating dashboard service file: $DASHBOARD_SERVICE_FILE"

    cat > "$DASHBOARD_SERVICE_FILE" << EOF
[Unit]
Description=Boo Haus Web Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/web_dashboard.py
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$INSTALL_DIR/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo "✅ Dashboard service file created"
    echo ""
fi

# Reload systemd to recognize new service
echo "Reloading systemd daemon..."
systemctl daemon-reload
echo "✅ Systemd reloaded"
echo ""

# Enable service to start on boot
echo "Enabling service to start on boot..."
systemctl enable boo-haus-display
echo "✅ Service enabled"
if [ "$INSTALL_DASHBOARD" = true ]; then
    systemctl enable boo-haus-dashboard
    echo "✅ Dashboard service enabled"
fi
echo ""

# Start the service now unless explicitly skipped
if [ "$START_SERVICES" = true ]; then
    echo "Starting service..."
    systemctl start boo-haus-display
    echo "✅ Service started"
    if [ "$INSTALL_DASHBOARD" = true ]; then
        systemctl start boo-haus-dashboard
        echo "✅ Dashboard service started"
    fi
else
    echo "ℹ️  Services installed and enabled but not started (--no-start)"
fi
echo ""

# Show status
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Service Status:"
systemctl status boo-haus-display --no-pager -l || true
if [ "$INSTALL_DASHBOARD" = true ]; then
    echo ""
    echo "Dashboard Service Status:"
    systemctl status boo-haus-dashboard --no-pager -l || true
fi
echo ""
echo "======================================"
echo "Useful Commands:"
echo "======================================"
echo ""
echo "Check status:"
echo "  sudo systemctl status boo-haus-display"
echo ""
echo "View logs (live):"
echo "  tail -f $INSTALL_DIR/logs/display.log"
echo "  sudo journalctl -u boo-haus-display -f"
echo ""
echo "Stop the service:"
echo "  sudo systemctl stop boo-haus-display"
echo ""
echo "Start the service:"
echo "  sudo systemctl start boo-haus-display"
echo ""
echo "Restart the service (after making changes):"
echo "  sudo systemctl restart boo-haus-display"
if [ "$INSTALL_DASHBOARD" = true ]; then
    echo "  sudo systemctl restart boo-haus-dashboard"
fi
echo ""
echo "Disable autostart on boot:"
echo "  sudo systemctl disable boo-haus-display"
echo ""
echo "======================================"
echo ""
echo "The display will now run automatically when the Pi boots!"
echo "You can still SSH in and make changes anytime."
echo "After making changes, restart the service with:"
echo "  sudo systemctl restart boo-haus-display"
if [ "$INSTALL_DASHBOARD" = true ]; then
    echo "  sudo systemctl restart boo-haus-dashboard"
fi
echo ""
