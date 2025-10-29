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
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import button handler
try:
    from button_handler import ButtonHandler
    BUTTONS_AVAILABLE = True
except ImportError:
    BUTTONS_AVAILABLE = False
    logger.warning("button_handler not available - buttons disabled")


class BooHausDisplayManager:
    """Main display manager that orchestrates screen cycling"""
    
    def __init__(self, config_file: str = 'boo_haus_config.json'):
        self.config = self.load_config(config_file)
        self.state_file = self.config.get('state_file', 'display_state.json')
        self.state = self.load_state()

        # Import screen classes
        from screens.weather_screen import WeatherScreen
        from screens.week_screen import WeekScreen
        from screens.nfl_screen import NFLScreen
        from screens.calendar_screen import CalendarScreen
        from screens.news_screen import NewsScreen
        from screens.birthday_screen import BirthdayScreen

        # Initialize screens in display order
        self.screens = [
            WeatherScreen(self.config),
            WeekScreen(self.config),
            NFLScreen(self.config),
            CalendarScreen(self.config),
            NewsScreen(self.config),
            BirthdayScreen(self.config)
        ]

        # Enable/disable screens based on config
        self.screens = [s for s in self.screens if s.is_enabled()]

        logger.info(f"Initialized {len(self.screens)} screens")

        # Button handler state
        self.is_paused = False
        self.button_handler = None
        self.button_action_pending = False  # Flag for button presses during sleep

        # Initialize button handler if enabled
        buttons_enabled = self.config.get('buttons', {}).get('enabled', True)
        if BUTTONS_AVAILABLE and buttons_enabled:
            self._setup_button_handler()
        else:
            logger.info("Button handler disabled in config or not available")

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
        except Exception as e:
            logger.error(f"Failed to setup button handler: {e}")
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
        logger.info(">>> Button C: Action complete <<<")

    def button_force_refresh(self):
        """Button D: Force refresh current screen with fresh data"""
        logger.info(">>> Button D: Force refresh <<<")
        self.button_action_pending = True
        current_screen = self.state.get('current_screen', 0)
        self.display_screen(current_screen)
        self.state['last_update'] = datetime.now().isoformat()
        self.save_state()
        logger.info(">>> Button D: Action complete <<<")

    def load_config(self, config_file: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_file} not found, using defaults")
            return self.get_default_config()
    
    def get_default_config(self) -> dict:
        """Return default configuration"""
        return {
            "display": {
                "width": 800,
                "height": 480,
                "cycle_interval_seconds": 300,  # 5 minutes per screen
                "save_images": True,
                "image_directory": "display_images"
            },
            "screens": {
                "weather": {"enabled": True},
                "week": {"enabled": True},
                "nfl": {"enabled": True},
                "calendar": {"enabled": True},
                "news": {"enabled": True},
                "birthday": {"enabled": True}
            },
            "special_dates": {
                "11-07": "Happy Booversary!",
                "21-03": "Happy Birthday Daddy!",
                "19-11": "Happy Birthday Mummy!",
                "29-06": "Happy Birthday Alice!",
                "22-10": "Happy Birthday Rosie!",
                "25-12": "Merry Christmas!",
                "01-01": "Happy New Year!",
                "easter": "Happy Easter!"
            },
            "data_refresh": {
                "news_scraper_hour": 3,
                "news_scraper_enabled": True
            },
            "state_file": "display_state.json"
        }
    
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
    
    def save_state(self):
        """Save current display state"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def get_next_screen_index(self) -> int:
        """Get the index of the next screen to display"""
        current = self.state.get('current_screen', 0)
        next_screen = (current + 1) % len(self.screens)
        return next_screen
    
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
            if self.is_paused and self.config.get('buttons', {}).get('show_pause_indicator', True):
                image = self._add_pause_indicator(image)

            # Save image if configured
            if self.config['display'].get('save_images', True):
                self.save_screen_image(image, screen.name)

            # Display on Inky if available
            if self.config['display'].get('display_on_inky', True):
                self.show_on_inky(image)

            return image

        except Exception as e:
            logger.error(f"Error rendering screen {screen.name}: {e}", exc_info=True)
            # Return error screen
            return self.create_error_screen(str(e))

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
        except:
            font = ImageFont.load_default()

        # Get text size
        bbox = draw.textbbox((0, 0), indicator_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position in top right, inside the header
        x = self.config['display']['width'] - text_width - 15
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
        """Save screen image to file"""
        try:
            img_dir = Path(self.config['display'].get('image_directory', 'display_images'))
            img_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = img_dir / f"{screen_name}_{timestamp}.png"
            
            image.save(filename)
            logger.info(f"Saved image: {filename}")
            
            # Also save as "latest"
            latest_filename = img_dir / f"{screen_name}_latest.png"
            image.save(latest_filename)
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
    
    def show_on_inky(self, image: Image.Image):
        """Display image on Inky Impression"""
        try:
            from inky.auto import auto
            
            logger.info("Displaying on Inky Impression...")
            inky = auto(ask_user=False, verbose=False)
            inky.set_image(image)
            inky.show()
            logger.info("Display updated successfully")
            
        except ImportError:
            logger.warning("Inky library not installed, skipping display")
        except Exception as e:
            logger.error(f"Error displaying on Inky: {e}")
    
    def create_error_screen(self, error_message: str) -> Image.Image:
        """Create a simple error display screen"""
        from PIL import ImageDraw, ImageFont
        
        width = self.config['display']['width']
        height = self.config['display']['height']
        
        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        draw.text((20, 20), "Error Rendering Screen", font=font, fill='black')
        draw.text((20, 60), error_message[:100], font=font, fill='red')
        
        return image
    
    def check_and_run_news_scraper(self):
        """Check if news scraper should run and execute if needed"""
        if not self.config['data_refresh'].get('news_scraper_enabled', True):
            return
        
        now = datetime.now()
        scraper_hour = self.config['data_refresh'].get('news_scraper_hour', 3)
        
        last_scrape_str = self.state.get('last_news_scrape')
        
        # Check if we should run the scraper
        should_run = False
        
        if last_scrape_str is None:
            should_run = True
        else:
            last_scrape = datetime.fromisoformat(last_scrape_str)
            # Run if it's past the scraper hour and we haven't run today
            if now.hour >= scraper_hour and last_scrape.date() < now.date():
                should_run = True
        
        if should_run:
            logger.info("Running news scraper and summariser...")
            try:
                # Run scraper
                import subprocess
                subprocess.run(['python3', 'news_scraper.py'], check=True)
                
                # Run summariser
                subprocess.run(['python3', 'news_summariser.py'], check=True)
                
                # Update state
                self.state['last_news_scrape'] = now.isoformat()
                self.save_state()
                
                logger.info("News scraper completed successfully")
            except Exception as e:
                logger.error(f"Error running news scraper: {e}")
    
    def cycle_once(self):
        """Display the next screen in the cycle"""
        # Check if news scraper should run
        self.check_and_run_news_scraper()
        
        # Get next screen
        screen_index = self.get_next_screen_index()
        
        # Display it
        self.display_screen(screen_index)
        
        # Update state
        self.state['current_screen'] = screen_index
        self.state['last_update'] = datetime.now().isoformat()
        self.save_state()
    
    def run_continuous(self):
        """Run continuous cycling through screens"""
        logger.info("Starting continuous display cycling...")
        interval = self.config['display'].get('cycle_interval_seconds', 300)

        try:
            while True:
                # Only cycle if not paused
                if not self.is_paused:
                    self.cycle_once()
                    logger.info(f"Waiting {interval} seconds until next update...")
                else:
                    logger.debug("Auto-cycling paused by button")

                # Break sleep into 1-second intervals to be responsive to buttons
                # This allows button presses to be noticed quickly
                for i in range(interval):
                    time.sleep(1)

                    # Check if button was pressed during sleep
                    if self.button_action_pending:
                        self.button_action_pending = False
                        logger.info(f"Button action detected, resetting wait timer ({i+1}/{interval} seconds elapsed)")
                        # Don't break - let the current wait cycle complete
                        # but the display has already been updated by the button callback

        except KeyboardInterrupt:
            logger.info("Display cycling stopped by user")
        finally:
            # Cleanup button handler
            if self.button_handler:
                self.button_handler.cleanup()
    
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
    parser.add_argument('--config', type=str, default='boo_haus_config.json',
                       help='Path to configuration file')
    
    args = parser.parse_args()
    
    # Create display manager
    manager = BooHausDisplayManager(args.config)
    
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