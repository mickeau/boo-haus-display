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
    Manages button input from Inky Impression's 4 side buttons.

    Button mappings:
    - Button A (GPIO 5): Previous screen
    - Button B (GPIO 6): Next screen
    - Button C (GPIO 16): Pause/Resume auto-cycling
    - Button D (GPIO 24): Force refresh current screen
    """

    BUTTON_PINS = {
        'A': 5,
        'B': 6,
        'C': 16,
        'D': 24,
    }
    GPIO_CHIPS = ("/dev/gpiochip4", "/dev/gpiochip0")

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.callbacks: Dict[str, Optional[Callable]] = {
            'A': None,
            'B': None,
            'C': None,
            'D': None,
        }
        self.monitoring = False
        self.monitor_thread = None
        self.gpiod_available = False
        self.request = None
        self.chip = None

        self.last_press_time: Dict[str, float] = {
            'A': 0,
            'B': 0,
            'C': 0,
            'D': 0,
        }
        self.debounce_time = 0.5
        self.debounce_time_d = 2.0

        if not self.enabled:
            logger.info("Button handler disabled by configuration")
            return

        try:
            import gpiod
            from gpiod.line import Bias, Direction, Edge
        except ImportError:
            logger.warning("gpiod not available - button functionality disabled")
            self.enabled = False
            return

        self.gpiod = gpiod
        self.Direction = Direction
        self.Edge = Edge
        self.Bias = Bias
        self.gpiod_available = True
        logger.info("gpiod library available - using for button handling")
        self._setup_buttons()

    def _open_gpio_chip(self):
        """Return the first accessible GPIO chip, or None when none can open."""
        for chip_path in self.GPIO_CHIPS:
            try:
                chip = self.gpiod.Chip(chip_path)
            except (OSError, RuntimeError) as exc:
                logger.debug("GPIO chip %s unavailable: %s", chip_path, exc)
                continue

            logger.info("Using GPIO chip: %s", chip_path)
            return chip

        return None

    def _setup_buttons(self):
        """Setup GPIO pins for button input."""
        if not self.gpiod_available:
            return

        self.chip = self._open_gpio_chip()
        if self.chip is None:
            logger.error("Failed to setup buttons: no GPIO chip found")
            self.enabled = False
            return

        try:
            input_settings = self.gpiod.LineSettings(
                direction=self.Direction.INPUT,
                bias=self.Bias.PULL_UP,
                edge_detection=self.Edge.FALLING,
            )
            button_pins = list(self.BUTTON_PINS.values())
            line_config = {pin: input_settings for pin in button_pins}

            self.request = self.chip.request_lines(
                consumer="boo-haus-buttons",
                config=line_config,
            )

            logger.info("Button handler initialized on GPIO pins: %s", button_pins)
            logger.info("Button monitoring ready - press any button to test")
        except (OSError, RuntimeError, ValueError) as exc:
            logger.error("Failed to setup buttons: %s", exc, exc_info=True)
            self.enabled = False
            self.request = None

    def set_callback(self, button: str, callback: Callable):
        """Set callback function for a button press."""
        if button in self.callbacks:
            self.callbacks[button] = callback
            logger.debug("Set callback for button %s", button)
            return

        logger.warning("Invalid button name: %s", button)

    def _get_button_name(self, gpio_pin: int) -> Optional[str]:
        """Get button name from GPIO pin number."""
        for name, pin in self.BUTTON_PINS.items():
            if pin == gpio_pin:
                return name
        return None

    def _debounce_threshold(self, button_name: str) -> float:
        return self.debounce_time_d if button_name == 'D' else self.debounce_time

    def _handle_button_press(self, button_name: str, gpio_pin: int, now: Optional[float] = None) -> bool:
        """Handle one button event. Return True when the callback was eligible."""
        now = now if now is not None else time.time()
        time_since_last = now - self.last_press_time[button_name]
        debounce_threshold = self._debounce_threshold(button_name)

        if time_since_last < debounce_threshold:
            logger.debug(
                "Button %s debounced (pressed %.2fs after last press, threshold %.2fs)",
                button_name,
                time_since_last,
                debounce_threshold,
            )
            return False

        self.last_press_time[button_name] = now
        logger.info(
            "Button %s pressed (GPIO %s) - %.2fs since last press",
            button_name,
            gpio_pin,
            time_since_last,
        )

        callback = self.callbacks.get(button_name)
        if not callback:
            logger.debug("No callback registered for button %s", button_name)
            return True

        try:
            callback()
        except Exception:
            logger.error("Error in button %s callback", button_name, exc_info=True)
        return True

    def _handle_edge_event(self, event):
        try:
            gpio_pin = event.line_offset
        except AttributeError:
            logger.warning("Ignoring GPIO event without line_offset: %r", event)
            return

        button_name = self._get_button_name(gpio_pin)
        if button_name is None:
            logger.warning("Unknown button pressed on GPIO %s", gpio_pin)
            return

        self._handle_button_press(button_name, gpio_pin)

    def _read_pending_events(self):
        if hasattr(self.request, "wait_edge_events"):
            if not self.request.wait_edge_events(timeout=0.1):
                return []
        else:
            time.sleep(0.1)

        return self.request.read_edge_events()

    def _monitor_buttons(self):
        """Monitor button presses in background thread."""
        logger.info("Button monitoring thread started")

        while self.monitoring:
            if not self.request:
                time.sleep(0.5)
                continue

            try:
                for event in self._read_pending_events():
                    self._handle_edge_event(event)
                time.sleep(0.01)
            except (OSError, RuntimeError, AttributeError) as exc:
                logger.error("Error monitoring buttons: %s", exc, exc_info=True)
                time.sleep(0.5)

        logger.info("Button monitoring thread stopped")

    def start_monitoring(self):
        """Start monitoring buttons in background thread."""
        if not self.enabled or not self.request:
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
        """Stop monitoring buttons."""
        if not self.monitoring:
            return

        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            if self.monitor_thread.is_alive():
                logger.warning("Button monitoring thread did not stop within timeout")
        logger.info("Button monitoring stopped")

    def cleanup(self):
        """Clean up GPIO resources."""
        self.stop_monitoring()
        if not self.request:
            return

        try:
            self.request.release()
        except (OSError, RuntimeError) as exc:
            logger.warning("Failed to release button GPIO resources: %s", exc)
        else:
            logger.info("Button GPIO resources released")
        finally:
            self.request = None
