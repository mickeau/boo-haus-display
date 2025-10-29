#!/bin/bash
# Install Boo Haus Display as a systemd service
# This will make the display run automatically on boot

set -e  # Exit on error

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
INSTALL_DIR="/home/$ACTUAL_USER/boo_haus_display"

echo "Installing service for user: $ACTUAL_USER"
echo "Installation directory: $INSTALL_DIR"
echo ""

# Check if directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ Directory not found: $INSTALL_DIR"
    echo "Please ensure boo_haus_display is installed in the home directory"
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
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/boo_haus_main.py --cycle
Restart=always
RestartSec=10
StandardOutput=append:$INSTALL_DIR/logs/display.log
StandardError=append:$INSTALL_DIR/logs/error.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created"
echo ""

# Reload systemd to recognize new service
echo "Reloading systemd daemon..."
systemctl daemon-reload
echo "✅ Systemd reloaded"
echo ""

# Enable service to start on boot
echo "Enabling service to start on boot..."
systemctl enable boo-haus-display
echo "✅ Service enabled"
echo ""

# Start the service now
echo "Starting service..."
systemctl start boo-haus-display
echo "✅ Service started"
echo ""

# Show status
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Service Status:"
systemctl status boo-haus-display --no-pager -l
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
echo ""
