# Inky Impression Button Guide

## Button Layout

The Inky Impression 7.3" has 4 tactile buttons on the left side (when viewing the display):

```
┌─────────┐
│    [A]  │ ← Top
│    [B]  │
│    [C]  │
│    [D]  │ ← Bottom
└─────────┘
```

## Button Functions

### Button A - Previous Screen
**GPIO Pin:** 5

Press Button A to navigate backward through your screens. If you're on the Weather screen and press A, you'll go to the Birthday screen (wrapping around the cycle).

**Example Use Cases:**
- Quickly check the previous screen
- Navigate back if you missed something
- Browse screens manually instead of waiting for auto-cycle

### Button B - Next Screen
**GPIO Pin:** 6

Press Button B to navigate forward through your screens. This is the same direction as the automatic cycle, but happens immediately when pressed.

**Example Use Cases:**
- Skip ahead to see the next screen
- Manually control which screen is displayed
- Quickly check all screens without waiting

### Button C - Pause/Resume Auto-Cycling
**GPIO Pin:** 16

Press Button C to pause automatic screen cycling. Press again to resume. When paused, a yellow "⏸ PAUSED" indicator appears in the top-right corner of the display.

**Example Use Cases:**
- Pause on a screen you want to study (weather forecast, calendar events, etc.)
- Stop cycling while you're near the display
- Leave a specific screen visible for an extended period
- Resume normal cycling when you're done

**Visual Feedback:**
- Paused: Yellow box with "⏸ PAUSED" text in top-right corner
- Resumed: Indicator disappears, normal cycling resumes

### Button D - Force Refresh
**GPIO Pin:** 24

Press Button D to immediately refresh the current screen with the latest data. This is useful when you know data has changed (weather update, new calendar event, etc.) and don't want to wait for the next cycle.

**Example Use Cases:**
- Update weather after seeing a storm coming
- Refresh news after knowing something important happened
- Force calendar reload after adding a new event
- Get latest NFL scores during game time

## Setup Instructions

### 1. Install Required Library

On your Raspberry Pi:

```bash
pip3 install gpiod
```

### 2. Enable Button Functionality

Edit `boo_haus_config.json`:

```json
{
  "buttons": {
    "enabled": true,
    "show_pause_indicator": true
  }
}
```

### 3. Test Button Detection

Run the standalone button test:

```bash
cd ~/boo_haus_display
python3 button_handler.py
```

Press each button (A, B, C, D) and verify output like:
```
Button A pressed - Previous screen
Button B pressed - Next screen
Button C pressed - Pause/Resume
Button D pressed - Force refresh
```

Press Ctrl+C to exit the test.

### 4. Run Normal Display

Start the display with button support:

```bash
python3 boo_haus_main.py --cycle
```

Buttons are now active! Try pressing them to control the display.

## Troubleshooting

### Buttons Not Working

**Problem:** Pressing buttons has no effect

**Solutions:**
1. Check if `gpiod` is installed:
   ```bash
   python3 -c "import gpiod; print('gpiod available')"
   ```

2. Check if buttons are enabled in config:
   ```bash
   cat boo_haus_config.json | grep -A 5 "buttons"
   ```

3. Check logs for button-related errors:
   ```bash
   tail -f logs/display.log | grep -i button
   ```

4. Verify GPIO permissions (may need to add user to `gpio` group):
   ```bash
   sudo usermod -a -G gpio $USER
   # Then logout and login again
   ```

### Button Test Shows "gpiod not available"

**Problem:** `button_handler.py` test says gpiod not found

**Solution:**
```bash
pip3 install gpiod
# Or if that fails, try:
pip3 install --user gpiod
```

### Pause Indicator Not Showing

**Problem:** Button C pauses cycling but no yellow indicator appears

**Solutions:**
1. Check config setting:
   ```json
   "buttons": {
     "show_pause_indicator": true
   }
   ```

2. The indicator appears in the top-right corner - verify it's not being cut off

3. Check logs to confirm pause state:
   ```bash
   tail logs/display.log | grep -i pause
   ```

### Wrong Button Does Wrong Action

**Problem:** Button labels don't match actions (e.g., Button A goes forward instead of backward)

**Solution:** The button positions are fixed by hardware. If they seem reversed, you may be looking at the display from the wrong orientation. Buttons should be on the LEFT side when viewing the display normally.

## Configuration Options

### Disable Buttons

Edit `boo_haus_config.json`:
```json
"buttons": {
  "enabled": false
}
```

### Hide Pause Indicator

Edit `boo_haus_config.json`:
```json
"buttons": {
  "enabled": true,
  "show_pause_indicator": false
}
```

## Technical Details

### GPIO Pin Mapping
- Button A: BCM GPIO 5 (Physical Pin 29)
- Button B: BCM GPIO 6 (Physical Pin 31)
- Button C: BCM GPIO 16 (Physical Pin 36)
- Button D: BCM GPIO 24 (Physical Pin 18)

### Implementation
- Uses `gpiod` (libgpiod Python bindings) for modern GPIO handling
- Buttons configured with pull-up resistors
- Falling-edge detection for button presses
- Background thread monitors button events
- Thread-safe callback system

### Button Behavior
- Buttons are **active** during `--cycle` mode
- Buttons are **inactive** during `--once` mode (single update)
- Buttons work immediately - no debouncing delay needed (hardware handles this)
- Each button press logs to `logs/display.log`

## Usage Tips

1. **Pause Before Looking Closely**: Press Button C to pause when you want to read details on the current screen

2. **Quick Browse**: Use Buttons A and B to quickly flip through all screens

3. **Force Updates**: Use Button D before checking the display if you know important data changed

4. **Resume and Walk Away**: Press Button C again when you're done to resume automatic cycling

5. **Manual Mode**: Keep display paused and use A/B buttons to control it manually

## Integration with Cron/Systemd

Buttons work with both automation methods:

**With Cron** (--once mode):
- Buttons are NOT active during cron updates
- To use buttons, run in --cycle mode instead

**With Systemd** (--cycle mode):
- Buttons are ALWAYS active
- This is the recommended setup for button functionality

To use buttons, prefer systemd service over cron:
```bash
sudo systemctl start boo-haus-display
```

## Future Enhancements

Potential button customizations you could add:

1. **Long Press Detection**: Different action if button held for 2+ seconds
2. **Button Combinations**: Press A+B together for special action
3. **Configurable Actions**: Change what each button does via config file
4. **Screen Bookmarks**: Press button to save/jump to favorite screens
5. **Brightness Control**: Use buttons to adjust e-ink refresh strength

See `button_handler.py` to implement custom button behaviors.

## Support

If buttons aren't working after following this guide:

1. Run the button test: `python3 button_handler.py`
2. Check system logs: `tail -f logs/display.log`
3. Verify hardware: Physical buttons should click when pressed
4. Check permissions: User needs GPIO access
5. Review CLAUDE.md for technical details

Happy button pressing! 🔘
