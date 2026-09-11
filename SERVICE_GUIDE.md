# Boo Haus Display - Service Guide

This project can run as two optional systemd services:

- `boo-haus-display` runs `boo_haus_main.py --cycle`
- `boo-haus-dashboard` runs `web_dashboard.py`

Both services load local API keys from `.env` when it exists.

## Install

Install the display service from a deployed checkout:

```bash
cd ~/boo_haus_display
sudo ./install_service.sh
```

Install both the display and dashboard services:

```bash
sudo ./install_service.sh --dashboard
```

Install and enable services without starting them:

```bash
sudo ./install_service.sh --dashboard --no-start
```

## Manage

```bash
sudo systemctl status boo-haus-display
sudo systemctl restart boo-haus-display
sudo journalctl -u boo-haus-display -f
```

Dashboard commands, when installed:

```bash
sudo systemctl status boo-haus-dashboard
sudo systemctl restart boo-haus-dashboard
sudo journalctl -u boo-haus-dashboard -f
```

Run `sudo systemctl daemon-reload` only after changing a service file.

For updating an existing Pi checkout from reviewed local files, use
[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) before restarting services.

## Local Secrets

Use `.env` for simple API keys:

```bash
OPENWEATHER_API_KEY=...
ANTHROPIC_API_KEY=...
```

Google Calendar still uses local OAuth JSON files:

- `credentials.json`
- `token.json`

Keep those files in the project root or configure their paths in
`boo_haus_config.json`.

## Testing Before Restart

Before restarting a deployed service, test locally from the checkout:

```bash
python3 health_check.py --skip-network
python3 test_display.py --quick
python3 boo_haus_main.py --screen weather
```

`test_display.py --quick` uses offline mode and should not make live network
requests.

## Dashboard Access

By default the dashboard binds to localhost. For remote access, set these in
the service environment or `.env`:

```bash
BOO_HAUS_DASHBOARD_HOST=0.0.0.0
BOO_HAUS_DASHBOARD_PORT=5000
```

Only expose the dashboard on networks you trust.

## Uninstall

```bash
sudo systemctl stop boo-haus-display
sudo systemctl disable boo-haus-display
sudo rm /etc/systemd/system/boo-haus-display.service

sudo systemctl stop boo-haus-dashboard
sudo systemctl disable boo-haus-dashboard
sudo rm /etc/systemd/system/boo-haus-dashboard.service

sudo systemctl daemon-reload
```
