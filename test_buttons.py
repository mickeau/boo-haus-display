#!/usr/bin/env python3
"""
Manual button diagnostic for the Inky Impression side buttons.

Run on the Raspberry Pi:
    python3 test_buttons.py
    python3 test_buttons.py --duration 30
"""

import argparse
import sys
import time

from button_handler import ButtonHandler


GPIO_CHIPS = ("/dev/gpiochip4", "/dev/gpiochip0", "/dev/gpiochip1")


def print_header(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def load_gpiod():
    print("[1/5] Checking gpiod library...")
    try:
        import gpiod
        from gpiod.line import Bias, Direction, Edge
    except ImportError as exc:
        print("gpiod library is not available.")
        print(f"Error: {exc}")
        print("Install with: pip3 install gpiod")
        return None, None, None, None

    print("gpiod library available")
    print(f"Version path: {gpiod.__file__}")
    return gpiod, Bias, Direction, Edge


def open_gpio_chip(gpiod):
    print("\n[2/5] Finding GPIO chip...")
    for chip_path in GPIO_CHIPS:
        try:
            chip = gpiod.Chip(chip_path)
        except (OSError, RuntimeError) as exc:
            print(f"  Tried {chip_path}: {exc}")
            continue

        info = chip.get_info()
        print(f"Found GPIO chip: {chip_path}")
        print(f"  Name: {info.name}")
        print(f"  Label: {info.label}")
        print(f"  Number of lines: {info.num_lines}")
        return chip, chip_path

    print("No GPIO chip found.")
    print("This may be a hardware, OS, or permissions issue.")
    print("Try: sudo usermod -a -G gpio $USER")
    return None, None


def check_button_lines(chip):
    print("\n[3/5] Checking button GPIO pins...")
    for button_name, pin in ButtonHandler.BUTTON_PINS.items():
        try:
            line_info = chip.get_line_info(pin)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"  Button {button_name} (GPIO {pin}): error - {exc}")
            continue

        line_name = line_info.name if line_info.name else "unnamed"
        print(f"  Button {button_name} (GPIO {pin}): {line_name}")
        if line_info.used:
            print(f"    Warning: pin already in use by {line_info.consumer}")


def request_button_lines(gpiod, chip, Bias, Direction, Edge):
    print("\n[4/5] Configuring button inputs...")
    input_settings = gpiod.LineSettings(
        direction=Direction.INPUT,
        bias=Bias.PULL_UP,
        edge_detection=Edge.FALLING,
    )

    button_pins = list(ButtonHandler.BUTTON_PINS.values())
    line_config = {pin: input_settings for pin in button_pins}

    try:
        request = chip.request_lines(consumer="button-test", config=line_config)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Failed to configure buttons: {exc}")
        return None

    print("Button inputs configured successfully")
    print(f"Monitoring GPIO pins: {button_pins}")
    return request


def read_events(request, has_wait):
    if has_wait:
        if not request.wait_edge_events(timeout=0.5):
            return []
    else:
        time.sleep(0.1)

    return request.read_edge_events()


def monitor_buttons(request, duration=None):
    print("\n[5/5] Monitoring button presses...")
    print_header("Press buttons A, B, C, or D. Press Ctrl+C to exit.")

    button_map = {pin: name for name, pin in ButtonHandler.BUTTON_PINS.items()}
    press_count = 0
    start_time = time.monotonic()
    has_wait = hasattr(request, "wait_edge_events")
    method = "wait_edge_events()" if has_wait else "read_edge_events() fallback"
    print(f"Using {method}\n")

    try:
        while True:
            if duration is not None and time.monotonic() - start_time >= duration:
                break

            try:
                events = read_events(request, has_wait)
            except (OSError, RuntimeError, AttributeError) as exc:
                print(f"Error reading events: {exc}")
                time.sleep(0.5)
                continue

            for event in events:
                gpio_pin = getattr(event, "line_offset", None)
                button_name = button_map.get(gpio_pin, "UNKNOWN")
                press_count += 1
                print(f"[{press_count}] Button {button_name} pressed (GPIO {gpio_pin})")
    except KeyboardInterrupt:
        pass

    print_header(f"Test complete. Detected {press_count} button presses.")


def parse_args():
    parser = argparse.ArgumentParser(description="Manual Inky button diagnostic")
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional number of seconds to monitor before exiting",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print_header("Inky Impression Button Diagnostic Tool")
    gpiod, Bias, Direction, Edge = load_gpiod()
    if gpiod is None:
        return 1

    chip, _chip_path = open_gpio_chip(gpiod)
    if chip is None:
        return 1

    check_button_lines(chip)
    request = request_button_lines(gpiod, chip, Bias, Direction, Edge)
    if request is None:
        return 1

    try:
        monitor_buttons(request, duration=args.duration)
    finally:
        try:
            request.release()
        except (OSError, RuntimeError) as exc:
            print(f"Failed to release GPIO resources: {exc}")
        else:
            print("GPIO resources released.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
