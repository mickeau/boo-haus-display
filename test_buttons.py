#!/usr/bin/env python3
"""
Simple button test script with detailed diagnostics
Run this to verify button hardware and GPIO configuration
"""

import sys
import time

print("="*60)
print("Inky Impression Button Diagnostic Tool")
print("="*60)
print()

# Test 1: Check gpiod library
print("[1/5] Checking gpiod library...")
try:
    import gpiod
    from gpiod.line import Direction, Edge, Bias
    print("✓ gpiod library available")
    print(f"  Version info: {gpiod.__file__}")
except ImportError as e:
    print("✗ gpiod library NOT available")
    print(f"  Error: {e}")
    print("  Install with: pip3 install gpiod")
    sys.exit(1)
print()

# Test 2: Find GPIO chip
print("[2/5] Finding GPIO chip...")
chip = None
chip_path = None
for potential_chip in ["/dev/gpiochip4", "/dev/gpiochip0", "/dev/gpiochip1"]:
    try:
        chip = gpiod.Chip(potential_chip)
        chip_path = potential_chip
        print(f"✓ Found GPIO chip: {chip_path}")
        print(f"  Name: {chip.get_info().name}")
        print(f"  Label: {chip.get_info().label}")
        print(f"  Number of lines: {chip.get_info().num_lines}")
        break
    except Exception as e:
        print(f"  Tried {potential_chip}: Not available")

if not chip:
    print("✗ No GPIO chip found!")
    print("  This might be a permissions issue.")
    print("  Try: sudo usermod -a -G gpio $USER")
    print("  Then logout and login again.")
    sys.exit(1)
print()

# Test 3: Check button GPIO pins
print("[3/5] Checking button GPIO pins...")
BUTTON_PINS = {'A': 5, 'B': 6, 'C': 16, 'D': 24}

for button_name, pin in BUTTON_PINS.items():
    try:
        line_info = chip.get_line_info(pin)
        print(f"  Button {button_name} (GPIO {pin}): {line_info.name if line_info.name else 'unnamed'}")
        if line_info.used:
            print(f"    ⚠ WARNING: Pin already in use by: {line_info.consumer}")
    except Exception as e:
        print(f"  Button {button_name} (GPIO {pin}): Error - {e}")
print()

# Test 4: Configure button inputs
print("[4/5] Configuring button inputs...")
try:
    input_settings = gpiod.LineSettings(
        direction=Direction.INPUT,
        bias=Bias.PULL_UP,
        edge_detection=Edge.FALLING
    )

    button_pins = list(BUTTON_PINS.values())
    line_config = {pin: input_settings for pin in button_pins}

    request = chip.request_lines(
        consumer="button-test",
        config=line_config
    )

    print("✓ Button inputs configured successfully")
    print(f"  Monitoring GPIO pins: {button_pins}")
except Exception as e:
    print(f"✗ Failed to configure buttons: {e}")
    sys.exit(1)
print()

# Test 5: Monitor button presses
print("[5/5] Monitoring button presses...")
print()
print("="*60)
print("Press buttons A, B, C, or D on your Inky Impression")
print("Press Ctrl+C to exit")
print("="*60)
print()

button_map = {v: k for k, v in BUTTON_PINS.items()}
press_count = 0

try:
    # Check if wait_edge_events is available
    has_wait = hasattr(request, 'wait_edge_events')
    if has_wait:
        print("Using wait_edge_events() method (efficient)")
    else:
        print("Using read_edge_events() method (fallback)")
    print()

    while True:
        try:
            if has_wait:
                # Modern gpiod with wait
                if request.wait_edge_events(timeout=0.5):
                    for event in request.read_edge_events():
                        gpio_pin = event.line_offset
                        button_name = button_map.get(gpio_pin, 'UNKNOWN')
                        press_count += 1
                        print(f"[{press_count}] Button {button_name} pressed! (GPIO {gpio_pin})")
            else:
                # Fallback for older gpiod
                try:
                    for event in request.read_edge_events():
                        gpio_pin = event.line_offset
                        button_name = button_map.get(gpio_pin, 'UNKNOWN')
                        press_count += 1
                        print(f"[{press_count}] Button {button_name} pressed! (GPIO {gpio_pin})")
                except:
                    pass
                time.sleep(0.1)

        except Exception as e:
            print(f"Error reading events: {e}")
            time.sleep(0.5)

except KeyboardInterrupt:
    print()
    print("="*60)
    print(f"Test complete! Detected {press_count} button presses.")
    print("="*60)
finally:
    request.release()
    print("GPIO resources released.")
