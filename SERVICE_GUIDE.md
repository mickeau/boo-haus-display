# Boo Haus Display - Service Management Guide

## Overview

Running Boo Haus Display as a systemd service means:
- ✅ Starts automatically when Raspberry Pi boots
- ✅ Runs in the background continuously
- ✅ Automatically restarts if it crashes
- ✅ You can still SSH in and make changes anytime
- ✅ Logs are saved automatically

## Installation

### Step 1: Install the Service

On your Raspberry Pi, run:

```bash
cd ~/boo_haus_display
chmod +x install_service.sh
sudo ./install_service.sh
```

This will:
1. Create the systemd service file
2. Enable it to start on boot
3. Start the service immediately
4. Show you the status

### Step 2: Verify It's Running

```bash
sudo systemctl status boo-haus-display
```

You should see:
- **Active: active (running)** in green
- Recent log entries
- Process ID (PID)

## Daily Usage

### Check If Display Is Running

```bash
sudo systemctl status boo-haus-display
```

### View Live Logs

**Option 1: View application logs**
```bash
tail -f ~/boo_haus_display/logs/display.log
```

**Option 2: View system logs**
```bash
sudo journalctl -u boo-haus-display -f
```

Press `Ctrl+C` to exit log viewing.

### See Recent Log Entries

```bash
# Last 50 lines
sudo journalctl -u boo-haus-display -n 50

# Last 10 minutes
sudo journalctl -u boo-haus-display --since "10 minutes ago"

# Today's logs
sudo journalctl -u boo-haus-display --since today
```

## Making Changes to Your Code

When you SSH in to edit files, the service keeps running. After making changes, you need to restart it:

### Workflow for Making Changes

```bash
# 1. SSH into your Pi
ssh pi@your-pi-address

# 2. Stop the service (optional, but recommended)
sudo systemctl stop boo-haus-display

# 3. Make your edits
cd ~/boo_haus_display
nano boo_haus_config.json
# or
nano weather_fetcher.py
# etc.

# 4. Test your changes (optional but recommended)
python3 boo_haus_main.py --once

# 5. Restart the service
sudo systemctl restart boo-haus-display

# 6. Check it's running
sudo systemctl status boo-haus-display
```

### Quick Restart After Changes

If you just want to apply changes quickly:

```bash
sudo systemctl restart boo-haus-display
```

## Service Control Commands

### Start the Service

```bash
sudo systemctl start boo-haus-display
```

Starts the display if it's stopped.

### Stop the Service

```bash
sudo systemctl stop boo-haus-display
```

Stops the display. Useful when:
- Making extensive changes
- Testing manually
- Troubleshooting

### Restart the Service

```bash
sudo systemctl restart boo-haus-display
```

Stops and starts the service. Use this after:
- Editing configuration files
- Updating Python code
- Installing new dependencies

### Reload Configuration

```bash
sudo systemctl daemon-reload
```

Only needed if you edit the service file itself (`boo-haus-display.service`).

### Check Status

```bash
sudo systemctl status boo-haus-display
```

Shows:
- Whether service is running
- How long it's been running
- Recent log entries
- Any errors

### Enable/Disable Autostart

**Disable autostart on boot:**
```bash
sudo systemctl disable boo-haus-display
```

The service won't start automatically, but you can still start it manually.

**Re-enable autostart:**
```bash
sudo systemctl enable boo-haus-display
```

## Testing Without the Service

Sometimes you want to test changes without the service running:

```bash
# 1. Stop the service
sudo systemctl stop boo-haus-display

# 2. Run manually
cd ~/boo_haus_display
python3 boo_haus_main.py --once     # Test single update
# or
python3 boo_haus_main.py --cycle    # Test continuous mode

# 3. When done, restart service
sudo systemctl start boo-haus-display
```

## Troubleshooting

### Service Won't Start

**Check for errors:**
```bash
sudo journalctl -u boo-haus-display -n 50
```

**Common issues:**
- Configuration file syntax error
- Missing dependencies
- Permission issues

**Try running manually to see the error:**
```bash
sudo systemctl stop boo-haus-display
cd ~/boo_haus_display
python3 boo_haus_main.py --cycle
```

### Service Keeps Restarting

The service is configured to restart automatically if it crashes. Check logs to see why:

```bash
sudo journalctl -u boo-haus-display | grep -i error
```

### Display Not Updating

**Check if service is running:**
```bash
sudo systemctl status boo-haus-display
```

**Check recent logs:**
```bash
tail -f ~/boo_haus_display/logs/display.log
```

**Force a restart:**
```bash
sudo systemctl restart boo-haus-display
```

### Buttons Not Working

Buttons should work fine with the service running. If they don't:

1. Check logs for button errors:
   ```bash
   tail -f ~/boo_haus_display/logs/display.log | grep -i button
   ```

2. Verify gpiod is installed:
   ```bash
   python3 -c "import gpiod; print('OK')"
   ```

3. Check GPIO permissions:
   ```bash
   groups pi | grep gpio
   ```

### Can't SSH In

The service doesn't affect SSH. If you can't SSH:
- Check Pi is powered on and connected to network
- Verify SSH is enabled: `sudo systemctl status ssh`
- Check IP address: Connect monitor/keyboard and run `ip addr`

## Log Management

Logs grow over time. Here's how to manage them:

### View Log Files

```bash
ls -lh ~/boo_haus_display/logs/
```

### Clear Old Logs

```bash
# Clear display logs
> ~/boo_haus_display/logs/display.log
> ~/boo_haus_display/logs/error.log

# Clear system logs for the service
sudo journalctl --vacuum-time=7d
```

### Rotate Logs Automatically

Add to crontab:
```bash
crontab -e
```

Add this line:
```
0 0 * * 0 cd ~/boo_haus_display && mv logs/display.log logs/display.log.old && touch logs/display.log
```

This rotates logs weekly (keeps last week's log as backup).

## Uninstalling the Service

If you want to remove the service:

```bash
# Stop the service
sudo systemctl stop boo-haus-display

# Disable autostart
sudo systemctl disable boo-haus-display

# Remove service file
sudo rm /etc/systemd/system/boo-haus-display.service

# Reload systemd
sudo systemctl daemon-reload
```

You can still run the display manually with:
```bash
python3 boo_haus_main.py --cycle
```

## Advanced: Service File Customization

The service file is located at: `/etc/systemd/system/boo-haus-display.service`

To edit it:
```bash
sudo nano /etc/systemd/system/boo-haus-display.service
```

After editing, reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart boo-haus-display
```

### Useful Customizations

**Change restart delay (default 10 seconds):**
```ini
RestartSec=30
```

**Start after network is fully online:**
```ini
After=network-online.target
Wants=network-online.target
```

**Limit restart attempts:**
```ini
StartLimitBurst=5
StartLimitIntervalSec=300
```

## Quick Reference Card

Save this for quick access:

```bash
# Check status
sudo systemctl status boo-haus-display

# Start/Stop/Restart
sudo systemctl start boo-haus-display
sudo systemctl stop boo-haus-display
sudo systemctl restart boo-haus-display

# View logs
tail -f ~/boo_haus_display/logs/display.log
sudo journalctl -u boo-haus-display -f

# After making code changes
sudo systemctl restart boo-haus-display

# Disable/Enable autostart
sudo systemctl disable boo-haus-display
sudo systemctl enable boo-haus-display
```

## Summary

**Benefits of running as a service:**
- ✅ Automatic startup on boot
- ✅ Runs in background
- ✅ Auto-restarts on failure
- ✅ Easy log management
- ✅ Standard Linux service controls
- ✅ Can still SSH and edit anytime

**Remember:** After editing code, always restart the service:
```bash
sudo systemctl restart boo-haus-display
```

Happy displaying! 🎨📺
