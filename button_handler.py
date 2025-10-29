#!/usr/bin/env python3
"""
Button Handler for Inky Impression 7.3"
Handles the 4 side-mounted buttons (A, B, C, D) on GPIO pins 5, 6, 16, 24
"""

import logging
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ButtonHandler:
    """
    Manages button input from Inky Impression's 4 side buttons

    Button mappings:
    - Button A (GPIO 5): Previous screen
    - Button B (GPIO 6): Next screen
    - Button C (GPIO 16): Pause/Resume auto-cycling
    - Button D (GPIO 24): Force refresh current screen
    """

    # GPIO pin numbers for each button
    BUTTON_PINS = {
        'A': 5,
        'B': 6,
        'C': 16,
        'D': 24
    }

    def __init__(self, enabled: bool = True):
        """
        Initialize button handler

        Args:
            enabled: Whether button handling is enabled
        """
        self.enabled = enabled
        self.callbacks: Dict[str, Optional[Callable]] = {
            'A': None,  # Previous screen
            'B': None,  # Next screen
            'C': None,  # Pause/Resume
            'D': None   # Force refresh
        }
        self.monitoring = False
        self.monitor_thread = None
        self.gpiod_available = False
        self.request = None

        # Debouncing: Track last press time for each button
        self.last_press_time: Dict[str, float] = {
            'A': 0,
            'B': 0,
            'C': 0,
            'D': 0
        }
        self.debounce_time = 0.5  # 500ms debounce
        # Longer debounce for Button D to prevent false triggers during display updates
        self.debounce_time_d = 2.0  # 2 seconds for Button D

        # Try to import gpiod (for Raspberry Pi 5 and newer)
        try:
            import gpiod
            from gpiod.line import Direction, Edge, Bias

            self.gpiod = gpiod
            self.Direction = Direction
            self.Edge = Edge
            self.Bias = Bias
            self.gpiod_available = True
            logger.info("gpiod library available - using for button handling")
        except ImportError:
            logger.warning("gpiod not available - button functionality disabled")
            self.enabled = False
            return

        if self.enabled:
            self._setup_buttons()

    def _setup_buttons(self):
        """Setup GPIO pins for button input"""
        if not self.gpiod_available:
            return

        try:
            # Get GPIO chip (usually gpiochip4 on Raspberry Pi 5, gpiochip0 on older models)
            chip_path = None
            for potential_chip in ["/dev/gpiochip4", "/dev/gpiochip0"]:
                try:
                    chip = self.gpiod.Chip(potential_chip)
                    chip_path = potential_chip
                    logger.info(f"Using GPIO chip: {chip_path}")
                    break
                except:
                    continue

            if not chip_path:
                raise Exception("No GPIO chip found")

            # Configure input settings with pull-up and edge detection
            input_settings = self.gpiod.LineSettings(
                direction=self.Direction.INPUT,
                bias=self.Bias.PULL_UP,
                edge_detection=self.Edge.FALLING
            )

            # Request lines for all buttons
            button_pins = list(self.BUTTON_PINS.values())
            line_config = {pin: input_settings for pin in button_pins}

            self.request = chip.request_lines(
                consumer="boo-haus-buttons",
                config=line_config
            )

            logger.info(f"Button handler initialized on GPIO pins: {button_pins}")
            logger.info("Button monitoring ready - press any button to test")

        except Exception as e:
            logger.error(f"Failed to setup buttons: {e}")
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            self.enabled = False

    def set_callback(self, button: str, callback: Callable):
        """
        Set callback function for a button press

        Args:
            button: Button name ('A', 'B', 'C', or 'D')
            callback: Function to call when button is pressed
        """
        if button in self.callbacks:
            self.callbacks[button] = callback
            logger.debug(f"Set callback for button {button}")
        else:
            logger.warning(f"Invalid button name: {button}")

    def _get_button_name(self, gpio_pin: int) -> Optional[str]:
        """Get button name from GPIO pin number"""
        for name, pin in self.BUTTON_PINS.items():
            if pin == gpio_pin:
                return name
        return None

    def _monitor_buttons(self):
        """Monitor button presses in background thread"""
        logger.info("Button monitoring thread started")

        while self.monitoring:
            try:
                if self.request:
                    # Check if there are any events waiting
                    # This is non-blocking if we poll with a small timeout
                    if self.request.wait_edge_events(timeout=0.1):
                        # Read all available edge events
                        for event in self.request.read_edge_events():
                            # Get the GPIO pin that triggered
                            gpio_pin = event.line_offset
                            button_name = self._get_button_name(gpio_pin)

                            if button_name:
                                # Check debounce time (use longer time for Button D)
                                current_time = time.time()
                                time_since_last = current_time - self.last_press_time[button_name]
                                debounce_threshold = self.debounce_time_d if button_name == 'D' else self.debounce_time

                                if time_since_last < debounce_threshold:
                                    logger.debug(f"Button {button_name} debounced (pressed {time_since_last:.2f}s after last press, threshold {debounce_threshold:.2f}s)")
                                    continue

                                # Update last press time
                                self.last_press_time[button_name] = current_time

                                logger.info(f"Button {button_name} pressed (GPIO {gpio_pin}) - {time_since_last:.2f}s since last press")

                                # Call the registered callback
                                callback = self.callbacks.get(button_name)
                                if callback:
                                    try:
                                        callback()
                                    except Exception as e:
                                        logger.error(f"Error in button {button_name} callback: {e}")
                                else:
                                    logger.debug(f"No callback registered for button {button_name}")
                            else:
                                logger.warning(f"Unknown button pressed on GPIO {gpio_pin}")

                    # Small sleep to prevent CPU spinning
                    time.sleep(0.01)

            except AttributeError as e:
                # wait_edge_events might not be available in older gpiod
                logger.warning(f"wait_edge_events not available, using fallback method")
                logger.warning(f"Button detection may be slower. Error: {e}")
                # Fall back to simpler polling
                try:
                    for event in self.request.read_edge_events():
                        gpio_pin = event.line_offset
                        button_name = self._get_button_name(gpio_pin)
                        if button_name:
                            # Check debounce time in fallback too (longer for Button D)
                            current_time = time.time()
                            time_since_last = current_time - self.last_press_time[button_name]
                            debounce_threshold = self.debounce_time_d if button_name == 'D' else self.debounce_time

                            if time_since_last < debounce_threshold:
                                continue

                            self.last_press_time[button_name] = current_time
                            logger.info(f"Button {button_name} pressed (GPIO {gpio_pin}) - {time_since_last:.2f}s since last press")
                            callback = self.callbacks.get(button_name)
                            if callback:
                                callback()
                except:
                    pass
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error monitoring buttons: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                time.sleep(0.5)  # Back off on errors

        logger.info("Button monitoring thread stopped")

    def start_monitoring(self):
        """Start monitoring buttons in background thread"""
        if not self.enabled:
            logger.info("Button handler disabled - not starting monitoring")
            return

        if self.monitoring:
            logger.warning("Button monitoring already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_buttons, daemon=True)
        self.monitor_thread.start()
        logger.info("Button monitoring started")

    def stop_monitoring(self):
        """Stop monitoring buttons"""
        if not self.monitoring:
            return

        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info("Button monitoring stopped")

    def cleanup(self):
        """Clean up GPIO resources"""
        self.stop_monitoring()
        if self.request:
            self.request.release()
            logger.info("Button GPIO resources released")


# Simple test function
def test_buttons():
    """Test button handler - prints button presses"""
    print("Button Handler Test")
    print("Press buttons A, B, C, or D")
    print("Press Ctrl+C to exit")
    print()

    def on_button_a():
        print("Button A pressed - Previous screen")

    def on_button_b():
        print("Button B pressed - Next screen")

    def on_button_c():
        print("Button C pressed - Pause/Resume")

    def on_button_d():
        print("Button D pressed - Force refresh")

    handler = ButtonHandler(enabled=True)

    if not handler.enabled:
        print("ERROR: Button handler not available (gpiod not found)")
        return

    handler.set_callback('A', on_button_a)
    handler.set_callback('B', on_button_b)
    handler.set_callback('C', on_button_c)
    handler.set_callback('D', on_button_d)

    handler.start_monitoring()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        handler.cleanup()


if __name__ == "__main__":
    # Set up logging for test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_buttons()
