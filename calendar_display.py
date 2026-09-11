#!/usr/bin/env python3
"""
Compatibility CLI for rendering the Boo Haus calendar screen.

The maintained Google Calendar fetcher lives in calendar_fetcher.py and the
maintained display layout lives in screens/calendar_screen.py. This wrapper
keeps the older command usable without carrying a second calendar pipeline.
"""

import argparse
import logging
import sys
from pathlib import Path

from config import config
from screens.calendar_screen import CalendarScreen


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
    config._set_in_memory('screens.calendar.max_events', args.max_events)
    config._set_in_memory('screens.calendar.days_ahead', args.days_ahead)


def main():
    parser = argparse.ArgumentParser(description='Render the Boo Haus calendar screen')
    parser.add_argument('--display', action='store_true',
                        help='Display on Inky screen')
    parser.add_argument('--save-image', action='store_true',
                        help='Save rendered image to disk')
    parser.add_argument('--image-file', default='calendar_display.png',
                        help='Output image filename')
    parser.add_argument('--max-events', type=int, default=config.get('screens.calendar.max_events', 10),
                        help='Maximum number of events to display')
    parser.add_argument('--days-ahead', type=int, default=config.get('screens.calendar.days_ahead', 14),
                        help='Number of days ahead to fetch events')
    args = parser.parse_args()

    calendar_ids = config.get('screens.calendar.calendar_ids', [])
    if not calendar_ids:
        print("Error: Calendar IDs are not configured.")
        print("Add them under screens.calendar.calendar_ids in the local config.")
        return 1

    _apply_cli_overrides(args)

    screen = CalendarScreen()
    image = screen.render()

    if args.save_image:
        image_path = Path(args.image_file)
        image.save(image_path)
        print(f"Saved calendar image to {image_path}")

    if args.display:
        if _show_on_inky(image):
            print("Calendar displayed on Inky screen")
        else:
            return 1

    events = screen.last_events
    print(f"Calendar events available: {len(events)}")
    for index, event in enumerate(events, 1):
        day = event['datetime'].strftime('%a %d %b')
        time = event['time_str']
        print(f"{index}. {event['summary']} - {day} {time}".rstrip())

    return 0


if __name__ == "__main__":
    sys.exit(main())
