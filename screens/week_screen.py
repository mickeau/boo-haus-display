#!/usr/bin/env python3
"""
This Week Screen for Boo Haus Display
UPDATED: Weather icons, better fonts, improved bin layout, fixed calendar widget
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_screen import BaseScreen
from datetime import datetime, timedelta
from PIL import Image
import logging

from weather_data_utils import normalize_forecast_day
from weather_icon_utils import load_weather_icon_image

logger = logging.getLogger(__name__)


class WeekScreen(BaseScreen):
    """This week summary: forecast, bins, birthdays"""

    @property
    def name(self) -> str:
        return "week"

    def __init__(self, config=None):
        super().__init__(config)
        self.icon_dir = "weather_icons"

        from weather_fetcher import WeatherFetcher
        from bin_collections import EastDevonWasteCollector
        from birthday_fetcher import BirthdayFetcher
        from config import config as cfg

        self.weather_fetcher = WeatherFetcher()
        self.bin_collector = EastDevonWasteCollector(cfg.get('locations.uprn'), cfg.get('locations.postcode'))
        self.birthday_fetcher = BirthdayFetcher()

    def load_weather_icon_small(self, description: str) -> Image.Image:
        """Load small weather icon (60x60)"""
        return load_weather_icon_image(description, self.icon_dir, (60, 60), logger)

    def render_content(self):
        """Render this week's information"""
        try:
            x, y, width, height = self.get_content_area()

            # Section 1: 5-Day Forecast (top section)
            forecast_y = self.draw_section_title("This Week at a Glance", y)
            forecast_end_y = self.draw_5_day_forecast(x, forecast_y, width)

            # Section 2: Bins and Events (bottom section, two columns)
            section2_y = forecast_end_y + 25
            col_width = int(width / 2) - 10

            # Left column: Bins
            bins_y = self.draw_section_title("Waste Collections", section2_y, color=self.GREEN)
            self.draw_bin_collections(x, bins_y, col_width, height - (bins_y - y))

            # Right column: Events - draw title manually at correct x position
            events_x = x + col_width + 20
            events_y = self.draw_section_title_at(
                events_x,
                section2_y,
                "Celebrations",
                right_x=x + width - 5,
                color=self.BLUE,
            )
            self.draw_events_this_week(events_x, events_y, col_width, height - (events_y - y))
        except Exception as e:
            logger.error(f"Error rendering WeekScreen: {e}", exc_info=True)
            x, y, width, height = self.get_content_area()
            self.draw.text((x, y), "Error loading week data",
                         font=self.font_medium, fill=self.RED)
            self.draw.text((x, y + 30), str(e)[:50],
                         font=self.font_small, fill=self.RED)

    def draw_5_day_forecast(self, x, y, width):
        """Draw 5-day weather forecast with icons"""
        try:
            data = self.weather_fetcher.fetch_data()
        except Exception as e:
            logger.error(f"Forecast fetcher failed: {e}", exc_info=True)
            self.draw.text((x, y), "Forecast unavailable",
                         font=self.font_small, fill=self.RED)
            return y + 50

        if not data:
            self.draw.text((x, y), "Unable to fetch forecast",
                         font=self.font_small, fill=self.RED)
            return y + 30

        # Configuration
        num_days = self.config.get('screens.week.forecast_days', 5)
        day_width = width // num_days
        current_y = y

        try:
            days = data['daily']
        except (KeyError, TypeError) as e:
            logger.warning(f"Forecast data has unexpected shape: {e}")
            self.draw.text((x, y), "Forecast unavailable",
                         font=self.font_small, fill=self.RED)
            return y + 50

        # Draw each day
        for i in range(num_days):
            if i >= len(days):
                break

            try:
                day_data = days[i]
                day = normalize_forecast_day(day_data, self.weather_fetcher)
                day_x = x + (i * day_width)

                # Draw vertical separator between days
                if i > 0:
                    self.draw.line([(day_x - 5, current_y),
                                  (day_x - 5, current_y + 130)],
                                 fill=self.BLACK, width=1)

                # Define day spacing for right justify
                day_right = day_x + day_width - 15

                if i == 0:
                    day_text = "Today"
                    day_color = self.GREEN
                elif i == 1:
                    day_text = "Tomozzy"
                    day_color = self.BLUE
                else:
                    day_text = day['day_name']
                    day_color = self.BLACK

                # Day name (larger font)
                self.draw.text((day_x + 5, current_y), day_text,
                             font=self.font_medium, fill=day_color)

                # Date number
                self.draw_right_aligned_text(day_right, current_y, day['date_num'],
                                             self.font_medium, self.BLACK)

                # Weather icon
                weather_desc = day['description']
                icon = self.load_weather_icon_small(weather_desc)

                if icon:
                    # Paste icon
                    icon_y = current_y + 45
                    self.image.paste(icon, (day_x + 5, icon_y),
                                   icon if icon.mode == 'RGBA' else None)
                else:
                    # Fallback to text
                    self.draw.text((day_x + 5, current_y + 25), weather_desc[:9],
                                 font=self.font_tiny, fill=self.BLUE)

                desc_y = current_y + 28
                self.draw.text((day_x + 7, desc_y), day['display_description'],
                                 font=self.font_tiny, fill=self.BLACK)

                # Temperature high/low (larger font)
                high = day['high']
                low = day['low']

                self.draw_right_aligned_text(day_x + day_width - 15, current_y + 50,
                                             f"HI {high:.0f}°", self.font_small, self.RED)
                self.draw_right_aligned_text(day_x + day_width - 15, current_y + 72,
                                             f"LO {low:.0f}°", self.font_small, self.BLUE)

                # Wind speed and rain chance
                wind = day['wind']
                wind_text = f"Wind {wind:.0f}mph"
                rain_text = f"Rain {day['rain_chance']}%"
                self.draw_right_aligned_text(day_right, current_y + 95, rain_text,
                                             self.font_tiny, self.BLACK)
                self.draw_right_aligned_text(day_right, current_y + 112, wind_text,
                                             self.font_tiny, self.BLACK)

            except (KeyError, IndexError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed forecast day {i}: {e}")
                continue

        return current_y + 120

    def draw_bin_collections(self, x, y, width, max_height):
        """Draw upcoming bin collections in single line format"""
        try:
            collections = self.bin_collector.fetch_data()
        except Exception as e:
            logger.error(f"Bin collection fetcher failed: {e}", exc_info=True)
            self.draw.text((x, y), "Bin data unavailable",
                         font=self.font_tiny, fill=self.RED)
            return

        if not collections:
            self.draw.text((x, y), "No bin data available",
                         font=self.font_small, fill=self.BLACK)
            return

        today = datetime.now().date()
        current_y = y
        displayed_count = 0
        available_height = max_height - 20

        # Show next 5 collections (compact format allows more)
        for collection in collections:
            if displayed_count >= 5:
                break

            # Check if we have space
            if current_y - y > available_height - 25:
                break

            try:
                date_obj = datetime.fromisoformat(collection['date'])
                days_until = (date_obj.date() - today).days

                # Skip past collections
                if days_until < 0:
                    continue

                # Collection type and color
                coll_type = collection['type']

                # Color based on waste type
                if 'Recycling' in coll_type:
                    type_color = self.BLUE
                elif 'Garden' in coll_type:
                    type_color = self.GREEN
                else:
                    type_color = self.BLACK

                # Urgency color
                if days_until == 0:
                    urgency_color = self.RED
                    day_text = "TODAY"
                elif days_until == 1:
                    urgency_color = self.RED
                    day_text = "Tomorrow"
                elif days_until <= 3:
                    urgency_color = self.BLUE
                    day_text = f"in {days_until} days"
                else:
                    urgency_color = self.BLACK
                    day_text = f"in {days_until} days"

                # Format: "Thu 16 October - in 4 days"
                date_str = date_obj.strftime('%a %d %B')
                full_text = f"{date_str} - {day_text}"

                # Draw waste type with color
                self.draw.text((x + 15, current_y), f"• {coll_type}:",
                             font=self.font_small, fill=type_color)

                # Draw date and countdown
                self.draw.text((x + 15, current_y + 25), full_text,
                             font=self.font_small, fill=urgency_color)

                current_y += 50
                displayed_count += 1

            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed bin collection {collection!r}: {e}")
                continue

    def draw_events_this_week(self, x, y, width, max_height):
        """Draw birthdays and holidays occurring this week"""
        current_y = y
        events_shown = 0
        available_height = max_height - 20

        # Get birthdays
        birthdays = self.get_birthdays_this_week()

        # Get holidays
        holidays = self.get_holidays_this_week()

        # Combine and sort by date
        all_events = []
        for event in birthdays + holidays:
            if isinstance(event, dict) and 'date' in event:
                all_events.append(event)
            else:
                logger.warning(f"Skipping malformed week event {event!r}: missing date")
        all_events.sort(key=lambda e: e['date'])

        if not all_events:
            self.draw.text((x, current_y), "No events this week",
                         font=self.font_small, fill=self.BLACK)
            return

        # Display events (compact format allows 4-5 events)
        for event in all_events[:5]:
            # Check if we have space
            if current_y - y > available_height - 50:
                break

            try:
                event_type = event['type']
                name = event['name']
                date_obj = event['date']
                days = event['days']
            except (KeyError, TypeError) as e:
                logger.warning(f"Skipping malformed week event {event!r}: {e}")
                continue

            # Choose icon and color
            if event_type == 'birthday':
                icon = "'s Birthday!"
                color = self.BLACK
            else:  # holiday
                icon = " Bank Holibob"
                color = self.BLUE

            # Format: "Thu 16 October - Birthday Name"
            date_str = date_obj.strftime('%a %d %B')

            # Days until text
            if days == 0:
                day_text = "TODAY!"
                text_color = self.RED
            elif days == 1:
                day_text = "Tomorrow"
                text_color = self.ORANGE
            else:
                day_text = f"in {days} days"
                text_color = self.BLACK

            # Draw icon and event name (make it prominent)
            name_text = f"{name}{icon}"
            self.draw.text((x, current_y), name_text,
                         font=self.font_small, fill=color)

            # Draw date and countdown
            full_text = f"{date_str} - {day_text}"
            self.draw.text((x, current_y + 20), full_text,
                         font=self.font_tiny, fill=self.BLACK)

            current_y += 45
            events_shown += 1

    def get_birthdays_this_week(self):
        """Get birthdays occurring in the next 7 days"""
        try:
            return self.birthday_fetcher.get_upcoming_birthdays(days_ahead=7)

        except Exception as e:
            logger.error(f"Birthday error: {e}")
            return []

    def get_holidays_this_week(self):
        """Get holidays occurring in the next 7 days"""
        try:
            today = datetime.now().date()
            special_dates = self.config.get('special_dates', {})

            holidays = []

            # Check each special date
            for date_key, greeting in special_dates.items():
                if date_key == 'easter':
                    continue

                try:
                    # Parse DD-MM format
                    day, month = map(int, date_key.split('-'))

                    # Calculate next occurrence
                    next_date = datetime(today.year, month, day).date()
                    if next_date < today:
                        next_date = datetime(today.year + 1, month, day).date()

                    days_until = (next_date - today).days

                    # Include if within next 7 days
                    if 0 <= days_until <= 7:
                        # Extract holiday name from greeting
                        name = greeting.replace('Happy ', '').replace('Merry ', '').replace('!', '')

                        # Skip if it's a birthday (those are handled separately)
                        if 'Birthday' in name:
                            continue

                        holidays.append({
                            'type': 'holiday',
                            'name': name,
                            'date': next_date,
                            'days': days_until
                        })
                except (TypeError, ValueError) as e:
                    logger.error(f"Error processing holiday {date_key}: {e}")
                    continue

            return holidays

        except AttributeError as e:
            logger.error(f"Holiday error: {e}")
            return []
