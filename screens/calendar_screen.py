#!/usr/bin/env python3
"""
Calendar Screen for Boo Haus Display
Shows upcoming Google Calendar events
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_screen import BaseScreen
from datetime import date, datetime, timezone
import logging

logger = logging.getLogger(__name__)


class CalendarScreen(BaseScreen):
    """Google Calendar events display"""

    @property
    def name(self) -> str:
        return "calendar"

    def __init__(self, config=None):
        super().__init__(config)
        self.calendar_fetcher = None
        self.calendar_error = None
        self.last_events = []

        try:
            from calendar_fetcher import CalendarData
            calendar_ids = self.config.get('screens.calendar.calendar_ids', [])
            self.calendar_fetcher = CalendarData(calendar_ids)
        except ImportError as e:
            self.calendar_error = str(e)
            logger.warning(f"Google Calendar dependencies unavailable: {e}")
        except Exception as e:
            self.calendar_error = str(e)
            logger.error(f"Calendar fetcher initialization failed: {e}", exc_info=True)

    def render_content(self):
        """Render calendar events"""
        try:
            x, y, width, height = self.get_content_area()

            # Title
            current_y = self.draw_section_title("Coming Soon @ Boo Haus", y)

            # Get calendar events
            events = self.get_calendar_events()
            self.draw_stale_note(self.calendar_fetcher, y)

            if not events:
                self.draw.text((x, current_y), "No upcoming events",
                             font=self.font_medium, fill=self.BLACK)
                if self.calendar_fetcher is not None and self.calendar_fetcher.is_stale():
                    hint = "Calendar can't be refreshed — check the internet connection"
                else:
                    hint = self.calendar_error or "Check Google Calendar authentication"
                self.draw.text((x, current_y + 30), hint,
                             font=self.font_tiny, fill=self.RED)
                return

            # Two-column layout
            col_width = (width - 30) // 2
            left_x = x
            right_x = x + col_width + 20

            # Draw vertical separator
            separator_x = x + col_width + 10
            self.draw.line([(separator_x, current_y),
                          (separator_x, y + height)],
                         fill=self.BLACK, width=2)

            # Split events between columns
            mid_point = (len(events) + 1) // 2
            left_events = events[:mid_point]
            right_events = events[mid_point:]

            # Draw left column
            self.draw_event_column(left_events, left_x, current_y,
                                   col_width, height)

            # Draw right column
            self.draw_event_column(right_events, right_x, current_y,
                                   col_width, height)
        except Exception as e:
            logger.error(f"Error rendering CalendarScreen: {e}", exc_info=True)
            x, y, width, height = self.get_content_area()
            self.draw.text((x, y), "Error loading calendar data",
                         font=self.font_medium, fill=self.RED)
            self.draw.text((x, y + 30), str(e)[:50],
                         font=self.font_small, fill=self.RED)

    def draw_event_column(self, events, x, y, width, max_height):
        """Draw a column of calendar events"""
        current_y = y
        margin = 5

        for i, event in enumerate(events):
            # Check available space
            if current_y - y > max_height - 70:
                break

            try:
                # Calculate days until event
                days = event['days_until']

                # Color coding based on urgency
                if days < 0:
                    date_color = self.PALE_GREEN  # Started but not finished
                    text_color = self.BLACK
                elif days == 0:
                    date_color = self.RED
                    text_color = self.WHITE
                elif days == 1:
                    date_color = self.ORANGE
                    text_color = self.WHITE
                else:
                    date_color = self.BLUE
                    text_color = self.WHITE

                # Date box (left side)
                box_width = 50
                box_height = 48

                self.draw.rectangle([x + margin, current_y,
                                   x + margin + box_width, current_y + box_height],
                                  outline=self.BLACK, fill=date_color, width=2)

                # Day number
                day_num = event['datetime'].strftime('%d')
                self.draw.text((x + margin + 13, current_y + 6), day_num,
                             font=self.font_medium, fill=text_color)

                # Month abbreviation
                month_str = event['datetime'].strftime('%b')
                self.draw.text((x + margin + 13, current_y + 28), month_str,
                             font=self.font_tiny, fill=text_color)

                # Event details (right of date box)
                details_x = x + margin + box_width + 10
                details_width = width - box_width - margin * 2 - 10

                # Event title (possibly wrapped)
                title = event['summary']
                title_lines = self.wrap_text(title, details_width, self.font_small)

                # Draw first line of title
                title_display = title_lines[0] if title_lines else title
                if len(title_display) > 25:
                    title_display = title_display[:25] + "..."

                self.draw.text((details_x, current_y), title_display,
                             font=self.font_medium, fill=self.BLACK)

                # Time or "All day"
                if event['is_all_day']:
                    time_text = "All day"
                else:
                    time_text = event['time_str']

                # Days until indicator
                if days < 0:
                    day_text = f"Started {abs(days)}d ago"
                elif days == 0:
                    day_text = "Today"
                elif days == 1:
                    day_text = "Tomorrow"
                else:
                    day_text = f"in {days} days"

                time_info = f"{time_text} • {day_text}"
                self.draw.text((details_x, current_y + 28), time_info,
                             font=self.font_small, fill=self.BLACK)

                # Location (if available and space permits)
                if event.get('location') and current_y + 38 < y + max_height - 30:
                    location = self.remove_emoji(event['location'])
                    location_lines = self.wrap_text(location, details_width, self.font_tiny)
                    location_text = location_lines[0] if location_lines else ''

                    if len(location_text) > 30:
                        location_text = location_text[:30] + "..."

                    if location_text:
                        self.draw.text((details_x, current_y + 35), location_text,
                                     font=self.font_tiny, fill=self.GREEN)

                # Calculate height used
                event_height = max(box_height, 50) + margin
                current_y += event_height
            except (KeyError, AttributeError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed calendar event {event!r}: {e}")
                continue

            # Separator line between events
            if i < len(events) - 1 and current_y < y + max_height - 60:
                self.draw.line([(x + margin + 5, current_y),
                              (x + width - margin - 5, current_y)],
                             fill=self.BLACK, width=1)
                current_y += 8

        return current_y

    @staticmethod
    def event_has_ended(event, now):
        """True if a raw Google Calendar event finished before now. An all-day
        event's end date is exclusive, so it has ended once that date arrives."""
        end = event.get('end') or {}
        if end.get('dateTime'):
            end_time = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            return end_time <= now
        if end.get('date'):
            return date.fromisoformat(end['date']) <= now.astimezone().date()
        return False

    def remove_emoji(self, text):
        """Remove emoji characters from text"""
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U00002600-\U000026FF"
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text).strip()

    def get_calendar_events(self):
        """Fetch events from Google Calendar"""
        try:
            self.last_events = []
            if self.calendar_fetcher is None:
                if self.calendar_error:
                    logger.warning(f"Calendar unavailable: {self.calendar_error}")
                return []

            if not self.calendar_fetcher.calendar_ids:
                x, y, width, height = self.get_content_area()
                self.draw.text((x, y), "Calendar IDs not configured",
                             font=self.font_medium, fill=self.BLACK)
                self.draw.text((x, y + 30), "Please add calendar_ids to config",
                             font=self.font_small, fill=self.BLACK)
                return []

            if not self.calendar_fetcher.service:
                if not self.calendar_fetcher.authenticate():
                    logger.error("Calendar authentication failed.")
                    return []

            max_events = self.config.get('screens.calendar.max_events', 10)
            days_ahead = self.config.get('screens.calendar.days_ahead', 14)

            events = self.calendar_fetcher.fetch_data(max_results=max_events,
                                        days_ahead=days_ahead)
            if not events:
                return []

            # Format for display
            formatted_events = []
            now = datetime.now(timezone.utc)
            for event in events:
                try:
                    # Cached events can be days old when refreshes fail; never
                    # show something that has already finished.
                    if self.event_has_ended(event, now):
                        continue
                    formatted = self.calendar_fetcher.format_event_for_display(event)
                    formatted_events.append(formatted)
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(f"Skipping malformed calendar API event {event!r}: {e}")
                    continue

            logger.info(f"Fetched {len(formatted_events)} calendar events")
            self.last_events = formatted_events
            return formatted_events

        except ImportError as e:
            logger.error(f"Calendar import error: {e}")
            logger.error("Make sure Google Calendar dependencies are installed:")
            logger.error("pip install google-auth-httplib2 google-auth-oauthlib google-api-python-client")
            return []
        except FileNotFoundError as e:
            logger.error(f"Calendar credentials not found: {e}")
            logger.error("Place credentials.json in the project directory")
            return []
        except Exception as e:
            logger.error(f"Calendar error: {e}", exc_info=True)
            return []
