#!/usr/bin/env python3
"""
Compatibility CLI for rendering the Boo Haus birthday screen.

Birthday loading is maintained in birthday_fetcher.py and display rendering is
maintained in screens/birthday_screen.py. This wrapper keeps the older command
available without maintaining a second parser and layout.
"""

import argparse
import logging
import sys
from pathlib import Path

from config import config
from screens.birthday_screen import BirthdayScreen


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _show_on_inky(image):
    """Display an image on the attached Inky device when the library is present."""
    try:
        from inky.auto import auto
    except ImportError:
        print("Inky display library not installed.")
        return False

    try:
        inky = auto(ask_user=True, verbose=True)
        inky.set_image(image)
        inky.show()
        return True
    except Exception as exc:
        logger.error("Inky display error: %s", exc)
        return False


def _apply_cli_overrides(args):
    """Apply transient CLI settings to the in-memory config only."""
    config._set_in_memory('screens.birthday.max_birthdays', args.max_birthdays)
    config._set_in_memory('screens.birthday.birthday_file', args.json_file)


def main():
    parser = argparse.ArgumentParser(description='Render the Boo Haus birthday screen')
    parser.add_argument('--display', action='store_true',
                        help='Display on Inky screen')
    parser.add_argument('--save-image', action='store_true',
                        help='Save rendered image to disk')
    parser.add_argument('--image-file', default='birthday_display.png',
                        help='Output image filename')
    parser.add_argument('--max-birthdays', type=int, default=config.get('screens.birthday.max_birthdays', 12),
                        help='Maximum number of birthdays to display')
    parser.add_argument('--json-file', default=config.get('screens.birthday.birthday_file', 'birthdays.json'),
                        help='JSON file containing birthdays')
    args = parser.parse_args()

    _apply_cli_overrides(args)

    screen = BirthdayScreen()
    image = screen.render()

    if args.save_image:
        image_path = Path(args.image_file)
        image.save(image_path)
        print(f"Saved birthday image to {image_path}")

    if args.display:
        if _show_on_inky(image):
            print("Birthday display shown on Inky screen")
        else:
            return 1

    birthdays = screen.last_birthdays
    print(f"Birthdays available: {len(birthdays)}")
    for index, birthday in enumerate(birthdays, 1):
        date_str = birthday['date'].strftime('%b %d')
        print(f"{index}. {birthday['name']} - {date_str} (in {birthday['days_until']} days)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
