#!/usr/bin/env python3
"""
Boo Haus Admin Display System
Main application that cycles through different information screens on Inky Impression 7.3"
"""

import os
import sys
import json
import time
import logging
import subprocess
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
import signal


def setup_logging():
    """Configure logging to both console and rotating log file."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return  # Already configured

    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    root_logger.setLevel(logging.INFO)

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation (5MB per file, keep 3 backups)
    file_handler = RotatingFileHandler(
        log_dir / 'display.log',
        maxBytes=5 * 1024 * 1024,
        backupCount=3
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


setup_logging()
logger = logging.getLogger(__name__)

from config import config

# Import button handler
try:
    from button_handler import ButtonHandler
    BUTTONS_AVAILABLE = True
except ImportError:
    BUTTONS_AVAILABLE = False
    logger.warning("button_handler not available - buttons disabled")


class BooHausDisplayManager:
    """Main display manager that orchestrates screen cycling"""

    def __init__(self, enable_buttons: bool = False):
        self.state_file = config.runtime_path('state_file', 'display_state.json')
        self.state = self.load_state()
        self.is_paused = False
        self.button_handler = None
        self.button_action_pending = False
        self.enable_buttons = enable_buttons
        self.alarm_handler_installed = False

        # Import screen classes
        from screens.weather_screen import WeatherScreen
        from screens.week_screen import WeekScreen
        from screens.nfl_screen import NFLScreen
        from screens.calendar_screen import CalendarScreen
        from screens.news_screen import NewsScreen
        from screens.birthday_screen import BirthdayScreen
        from screens.status_screen import StatusScreen

        # Initialize screens in display order
        screen_specs = [
            ('weather', WeatherScreen, {}),
            ('week', WeekScreen, {}),
            ('nfl', NFLScreen, {}),
            ('calendar', CalendarScreen, {}),
            ('news', NewsScreen, {}),
            ('birthday', BirthdayScreen, {}),
            ('status', StatusScreen, {'display_manager': self}),
        ]

        self.screens = []
        for screen_name, screen_cls, kwargs in screen_specs:
            if not config.get(f'screens.{screen_name}.enabled', True):
                logger.info(f"Screen disabled in config: {screen_name}")
                continue

            try:
                screen = screen_cls(**kwargs)
                if screen.is_enabled():
                    self.screens.append(screen)
            except Exception as e:
                logger.error(f"Failed to initialize screen '{screen_name}': {e}", exc_info=True)

        if not self.screens:
            raise RuntimeError("No screens available. Check screen configuration and dependencies.")

        logger.info(f"Initialized {len(self.screens)} screens")

        # Initialize button handler if enabled
        buttons_enabled = config.get('buttons.enabled', True)
        if self.enable_buttons and BUTTONS_AVAILABLE and buttons_enabled:
            self._setup_button_handler()
        else:
            logger.info("Button handler disabled for this run mode, config, or environment")

    def _setup_button_handler(self):
        """Setup button handler and register callbacks"""
        try:
            self.button_handler = ButtonHandler(enabled=True)

            # Register button callbacks
            self.button_handler.set_callback('A', self.button_previous_screen)
            self.button_handler.set_callback('B', self.button_next_screen)
            self.button_handler.set_callback('C', self.button_toggle_pause)
            self.button_handler.set_callback('D', self.button_force_refresh)

            # Start monitoring buttons
            self.button_handler.start_monitoring()

            logger.info("Button handler setup complete")
        except (AttributeError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"Failed to setup button handler: {e}", exc_info=True)
            self.button_handler = None

    def button_previous_screen(self):
        """Button A: Go to previous screen"""
        logger.info(">>> Button A: Previous screen <<<")
        self.button_action_pending = True
        current = self.state.get('current_screen', 0)
        previous = (current - 1) % len(self.screens)
        self.display_screen(previous)
        self.state['current_screen'] = previous
        self.state['last_update'] = datetime.now().isoformat()
        self.save_state()
        self._wake_main_loop()
        logger.info(">>> Button A: Action complete <<<")

    def button_next_screen(self):
        """Button B: Go to next screen"""
        logger.info(">>> Button B: Next screen <<<")
        self.button_action_pending = True
        screen_index = self.get_next_screen_index()
        self.display_screen(screen_index)
        self.state['current_screen'] = screen_index
        self.state['last_update'] = datetime.now().isoformat()
        self.save_state()
        self._wake_main_loop()
        logger.info(">>> Button B: Action complete <<<")

    def button_toggle_pause(self):
        """Button C: Toggle pause/resume auto-cycling"""
        self.button_action_pending = True
        self.is_paused = not self.is_paused
        status = "PAUSED" if self.is_paused else "RESUMED"
        logger.info(f">>> Button C: {status} auto-cycling <<<")

        # Refresh display to show/hide pause indicator
        current_screen = self.state.get('current_screen', 0)
        self.display_screen(current_screen)
        self._wake_main_loop()
        logger.info(">>> Button C: Action complete <<<")

    def button_force_refresh(self):
        """Button D: Force refresh current screen with fresh data"""
        logger.info(">>> Button D: Force refresh <<<")
        self.button_action_pending = True
        current_screen = self.state.get('current_screen', 0)
        self.display_screen(current_screen)
        self.state['last_update'] = datetime.now().isoformat()
        self.save_state()
        self._wake_main_loop()
        logger.info(">>> Button D: Action complete <<<")

    def _wake_main_loop(self):
        """Wake the continuous loop if its SIGALRM handler is active."""
        if not self.alarm_handler_installed:
            return
        try:
            os.kill(os.getpid(), signal.SIGALRM)
        except OSError as e:
            logger.warning(f"Could not wake main loop: {e}")

    def load_state(self) -> dict:
        """Load current display state"""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'current_screen': 0,
                'last_update': None,
                'last_news_scrape': None
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"State file {self.state_file} is invalid; starting with default state: {e}")
            return {
                'current_screen': 0,
                'last_update': None,
                'last_news_scrape': None
            }

    def save_state(self):
        """Save current display state atomically.

        Writes to a temporary file first, then renames it into place.
        This prevents corruption if the process is killed mid-write.
        """
        try:
            tmp_file = self.state_file + '.tmp'
            with open(tmp_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            os.replace(tmp_file, self.state_file)
        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Error saving state: {e}")

    def get_next_screen_index(self) -> int:
        """Get the index of the next screen to display"""
        current = self.state.get('current_screen', 0)
        next_screen = (current + 1) % len(self.screens)
        return next_screen

    def get_screen_index_by_name(self, screen_name: str):
        """Return screen index by display name, or None if unavailable."""
        for index, screen in enumerate(self.screens):
            if screen.name.lower() == screen_name.lower():
                return index
        return None

    def display_screen(self, screen_index: int) -> Image.Image:
        """Render and display a specific screen"""
        if screen_index >= len(self.screens):
            screen_index = 0

        screen = self.screens[screen_index]
        logger.info(f"Rendering screen: {screen.name}")

        try:
            # Render the screen
            image = screen.render()

            # Add pause indicator if paused and enabled
            if self.is_paused and config.get('buttons.show_pause_indicator', True):
                image = self._add_pause_indicator(image)

            # Visual feedback for update
            if config.get('display.visual_feedback_on_update', True):
                self._flash_update_feedback(image.copy())

            # Save image if configured
            if config.get('display.save_images', True):
                self.save_screen_image(image, screen.name)

            # Display on Inky if available
            if config.get('display.display_on_inky', True):
                self.show_on_inky(image)

            return image

        except Exception as e:
            logger.error(f"Error rendering screen {screen.name}: {e}", exc_info=True)
            # Return error screen
            return self.create_error_screen(str(e))

    def _flash_update_feedback(self, image: Image.Image):
        """Briefly flash a border on the screen to indicate an update."""
        if not config.get('display.display_on_inky', True):
            return # Only flash if actually displaying on Inky

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        width = config.get('display.width')
        height = config.get('display.height')
        border_color = (0, 0, 0) # Black border
        border_width = 5

        # Draw border
        draw.rectangle([(0, 0), (width - 1, height - 1)], outline=border_color, width=border_width)

        # Show on Inky
        self.show_on_inky(image)
        time.sleep(config.get('display.visual_feedback_duration', 0.5)) # Flash for 0.5 seconds

    def _add_pause_indicator(self, image: Image.Image) -> Image.Image:
        """Add a pause indicator to the image"""
        from PIL import ImageDraw, ImageFont

        # Make a copy to avoid modifying original
        img = image.copy()
        draw = ImageDraw.Draw(img)

        # Draw pause indicator in top right corner
        indicator_text = "⏸ PAUSED"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except OSError:
            font = ImageFont.load_default()

        # Get text size
        bbox = draw.textbbox((0, 0), indicator_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position in top right, inside the header
        x = config.get('display.width') - text_width - 15
        y = 48  # Bottom of header area

        # Draw background box
        padding = 5
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(255, 255, 0),  # Yellow background
            outline=(0, 0, 0),
            width=2
        )

        # Draw text
        draw.text((x, y), indicator_text, font=font, fill=(0, 0, 0))

        return img

    def save_screen_image(self, image: Image.Image, screen_name: str):
        """Save screen image to file and prune old screenshots"""
        try:
            img_dir = Path(config.runtime_path('display.image_directory', 'display_images'))
            img_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = img_dir / f"{screen_name}_{timestamp}.png"

            image.save(filename)
            logger.info(f"Saved image: {filename}")

            # Also save as "latest"
            latest_filename = img_dir / f"{screen_name}_latest.png"
            image.save(latest_filename)

            # Prune old timestamped images — keep the most recent 50
            self._cleanup_old_images(img_dir, keep=50)

        except (OSError, ValueError) as e:
            logger.error(f"Error saving image: {e}")

    def _cleanup_old_images(self, img_dir: Path, keep: int = 50):
        """Delete old timestamped screenshots, keeping the N most recent.

        Only deletes files matching the <name>_YYYYMMDD_HHMMSS.png pattern;
        *_latest.png files are left alone.
        """
        try:
            import re
            timestamped = [
                f for f in img_dir.glob('*.png')
                if re.search(r'_\d{8}_\d{6}\.png$', f.name)
            ]
            if len(timestamped) <= keep:
                return
            # Sort oldest first
            timestamped.sort(key=lambda f: f.stat().st_mtime)
            to_delete = timestamped[:-keep]
            for f in to_delete:
                f.unlink()
            logger.info(f"Cleaned up {len(to_delete)} old display images")
        except (OSError, ValueError) as e:
            logger.warning(f"Image cleanup failed (non-critical): {e}")

    def show_on_inky(self, image: Image.Image):
        """Display image on Inky Impression, with timeout protection.

        Runs inky.show() in a subprocess so a hung display refresh
        (busy-wait timeout) can be killed without freezing the main process.
        """
        try:
            from inky.auto import auto
        except ImportError:
            logger.warning("Inky library not installed, skipping display")
            return

        try:
            import multiprocessing

            def _inky_worker(img_bytes, img_size):
                """Target for subprocess — imports inky and drives the display."""
                from PIL import Image as PILImage
                from inky.auto import auto as inky_auto
                img = PILImage.frombytes('RGB', img_size, img_bytes)
                display = inky_auto(ask_user=False, verbose=False)
                display.set_image(img)
                display.show()

            logger.info("Displaying on Inky Impression (with timeout)...")
            img_bytes = image.tobytes()
            img_size = image.size

            proc = multiprocessing.Process(
                target=_inky_worker,
                args=(img_bytes, img_size),
                daemon=True
            )
            proc.start()
            proc.join(timeout=90)  # 90 seconds — generous for a 7-colour refresh

            if proc.is_alive():
                logger.error("Inky display refresh timed out after 90s — killing subprocess")
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
            elif proc.exitcode != 0:
                logger.error(f"Inky display subprocess exited with code {proc.exitcode}")
            else:
                logger.info("Display updated successfully")

        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Error displaying on Inky: {e}")

    def create_error_screen(self, error_message: str) -> Image.Image:
        """Create a simple error display screen"""
        from PIL import ImageDraw, ImageFont

        width = config.get('display.width')
        height = config.get('display.height')

        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except OSError:
            font = ImageFont.load_default()

        draw.text((20, 20), "Error Rendering Screen", font=font, fill='black')
        draw.text((20, 60), error_message[:100], font=font, fill='red')

        return image

    def check_and_run_news_scraper(self):
        """Check if news scraper should run and execute if needed"""
        if not config.get('data_refresh.news_scraper_enabled', True):
            return

        now = datetime.now()
        scraper_hour = config.get('data_refresh.news_scraper_hour', 3)

        last_scrape_str = self.state.get('last_news_scrape')

        # Check if we should run the scraper
        should_run = False

        if last_scrape_str is None:
            should_run = True
        else:
            try:
                last_scrape = datetime.fromisoformat(last_scrape_str)
            except (TypeError, ValueError):
                logger.warning(f"Invalid last_news_scrape value '{last_scrape_str}', running news scraper")
                should_run = True
            else:
                # Run if it's past the scraper hour and we haven't run today
                if now.hour >= scraper_hour and last_scrape.date() < now.date():
                    should_run = True

        if should_run:
            logger.info("Running news scraper and summariser...")
            try:
                # Run scraper with 5-minute timeout
                subprocess.run([sys.executable, 'news_scraper.py'],
                               check=True, timeout=300)

                if config.get('data_refresh.news_summariser_enabled', True):
                    try:
                        subprocess.run([sys.executable, 'news_summariser.py'],
                                       check=True, timeout=600)
                    except subprocess.TimeoutExpired:
                        logger.error("News summariser timed out; raw scraped stories remain available")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"News summariser failed with exit code {e.returncode}; raw scraped stories remain available")
                else:
                    logger.info("News summariser disabled; using raw scraped stories")

                # Update state
                self.state['last_news_scrape'] = now.isoformat()
                self.save_state()

                logger.info("News scraper completed successfully")
            except subprocess.TimeoutExpired:
                logger.error("News scraper timed out; skipping this run")
            except subprocess.CalledProcessError as e:
                logger.error(f"News scraper failed with exit code {e.returncode}")
            except OSError as e:
                logger.error(f"Error running news scraper: {e}")

    def cycle_once(self):
        """Display the next screen in the cycle"""
        # Check if news scraper should run
        self.check_and_run_news_scraper()

        requested_screen = self.state.pop('requested_screen', None)
        if requested_screen:
            screen_index = self.get_screen_index_by_name(requested_screen)
            if screen_index is None:
                logger.warning(f"Requested screen '{requested_screen}' is not available")
                screen_index = self.get_next_screen_index()
        else:
            screen_index = self.get_next_screen_index()

        # Display it
        self.display_screen(screen_index)

        # Update state
        self.state['current_screen'] = screen_index
        self.state['last_update'] = datetime.now().isoformat()
        self.state['cycle_count'] = self.state.get('cycle_count', 0) + 1
        self.save_state()

    def _alarm_handler(self, signum, frame):
        """Signal handler for SIGALRM to trigger a cycle."""
        logger.debug("Alarm received, triggering cycle.")
        # This handler just needs to exist to break signal.pause()
        # The main loop will check self.is_paused and self.button_action_pending

    def run_continuous(self):
        """Run continuous cycling through screens"""
        logger.info("Starting continuous display cycling...")
        interval = config.get('display.cycle_interval_seconds', 300)

        # Set up signal handler for SIGALRM
        signal.signal(signal.SIGALRM, self._alarm_handler)
        self.alarm_handler_installed = True

        try:
            while True:
                # Only cycle if not paused or if a button action is pending
                if not self.is_paused or self.button_action_pending:
                    self.cycle_once()
                    self.button_action_pending = False # Reset after action
                    logger.info(f"Waiting {interval} seconds until next update...")
                else:
                    logger.debug("Auto-cycling paused, waiting for button press or unpause.")

                # Set a real-time alarm to wake up after 'interval' seconds
                # This will send SIGALRM, which will break signal.pause()
                signal.setitimer(signal.ITIMER_REAL, interval)

                # Wait for a signal (SIGALRM from timer or button press)
                signal.pause()

        except KeyboardInterrupt:
            logger.info("Display cycling stopped by user")
        finally:
            # Cleanup button handler
            if self.button_handler:
                self.button_handler.cleanup()
            # Disable the timer
            signal.setitimer(signal.ITIMER_REAL, 0)
            self.alarm_handler_installed = False

    def display_specific_screen(self, screen_name: str):
        """Display a specific screen by name"""
        for i, screen in enumerate(self.screens):
            if screen.name.lower() == screen_name.lower():
                self.display_screen(i)
                return
        logger.error(f"Screen '{screen_name}' not found")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Boo Haus Admin Display System')
    parser.add_argument('--cycle', action='store_true',
                       help='Run continuous cycling through screens')
    parser.add_argument('--once', action='store_true',
                       help='Display next screen once and exit')
    parser.add_argument('--screen', type=str,
                       help='Display specific screen (weather, week, nfl, calendar, news, birthday)')

    args = parser.parse_args()

    # Create display manager
    manager = BooHausDisplayManager(enable_buttons=args.cycle)

    if args.screen:
        # Display specific screen
        manager.display_specific_screen(args.screen)
    elif args.cycle:
        # Run continuous cycling
        manager.run_continuous()
    elif args.once:
        # Display next screen once
        manager.cycle_once()
    else:
        # Default: display next screen once
        print("Boo Haus Admin Display System")
        print("Usage:")
        print("  --cycle     Run continuous cycling")
        print("  --once      Display next screen once")
        print("  --screen X  Display specific screen")
        print("\nDisplaying next screen once...")
        manager.cycle_once()


if __name__ == "__main__":
    main()
