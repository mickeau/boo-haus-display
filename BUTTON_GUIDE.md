# Inky Impression Button Guide

## Button Layout

The Inky Impression 7.3" has four tactile buttons on the left side when
viewing the display:

```text
+---------+
|    [A]  |  Top
|    [B]  |
|    [C]  |
|    [D]  |  Bottom
+---------+
```

## Button Functions

### Button A - Previous Screen

GPIO pin: BCM 5, physical pin 29

Press Button A to navigate backward through the enabled screens. Navigation
wraps around from the first screen to the last screen.

### Button B - Next Screen

GPIO pin: BCM 6, physical pin 31

Press Button B to navigate forward through the enabled screens. This is the same
direction as automatic cycling, but happens immediately.

### Button C - Pause/Resume Auto-Cycling

GPIO pin: BCM 16, physical pin 36

Press Button C to pause or resume automatic screen cycling. When paused, the
current screen is refreshed and the pause indicator is shown if
`buttons.show_pause_indicator` is enabled.

### Button D - Force Refresh

GPIO pin: BCM 24, physical pin 18

Press Button D to immediately refresh the current screen. This is useful after a
weather, news, calendar, or score update. Button D has a longer debounce window
than the navigation buttons so display refresh activity is less likely to cause
duplicate refreshes.

## Configuration

Disable buttons:

```json
"buttons": {
  "enabled": false
}
```

Hide the pause indicator:

```json
"buttons": {
  "enabled": true,
  "show_pause_indicator": false
}
```

Button-triggered display feedback uses the normal update feedback setting:

```json
"display": {
  "visual_feedback_on_update": true,
  "visual_feedback_duration": 0.5
}
```

## Runtime Behavior

- Buttons are only started by `boo_haus_main.py --cycle`.
- Buttons are inactive for `--once` and `--screen <name>` one-shot renders.
- The handler uses the `gpiod` Python bindings and tries `/dev/gpiochip4` first,
  then `/dev/gpiochip0`.
- Buttons use falling-edge detection with pull-up bias.
- Button A/B/C use a 0.5 second debounce window.
- Button D uses a 2.0 second debounce window.
- Each accepted button press is logged to `logs/display.log`.

## Service Use

The recommended way to keep buttons active on the e-ink display is to run the
display service in cycle mode:

```bash
sudo ./install_service.sh
sudo systemctl status boo-haus-display
```

If the service is already installed, restart it after deploying code or config
changes:

```bash
sudo systemctl restart boo-haus-display
```

Cron one-shot updates can still refresh the display, but they cannot keep a
background GPIO monitoring thread alive between runs.

## Manual Diagnostic

Run this on the Raspberry Pi when checking GPIO hardware or permissions:

```bash
python3 test_buttons.py
python3 test_buttons.py --duration 30
```

## Useful Extensions

- Long press detection for secondary actions.
- Configurable button actions.
- A button shortcut to jump to a favorite screen.
- A safe shutdown or reboot action with a confirmation gesture.
