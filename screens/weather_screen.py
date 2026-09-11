#!/usr/bin/env python3
"""
Weather Screen for Boo Haus Display
UPDATED: Uses PNG weather icons, improved layout, shows only next high/low tide
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_screen import BaseScreen
from PIL import Image
import logging

from base_fetcher import network_disabled
from weather_data_utils import normalize_current_weather
from weather_icon_utils import load_weather_icon_image

logger = logging.getLogger(__name__)


class WeatherScreen(BaseScreen):
    """Weather display with comprehensive local information"""

    @property
    def name(self) -> str:
        return "weather"

    def __init__(self, config=None):
        super().__init__(config)
        self.icon_dir = "weather_icons"  # Directory containing PNG icons

        from weather_fetcher import WeatherFetcher
        from tide_times import TideFetcher
        from water_quality import WaterQualityFetcher
        from direct_sewage_api import SewageFetcher

        self.weather_fetcher = WeatherFetcher()
        self.tide_fetcher = TideFetcher()
        self.water_quality_fetcher = WaterQualityFetcher()
        self.sewage_fetcher = SewageFetcher()

    def load_weather_icon(self, description: str) -> Image.Image:
        """Load appropriate PNG weather icon based on description"""
        return load_weather_icon_image(description, self.icon_dir, (120, 120), logger)

    def render_content(self):
        """Render weather information with new layout"""
        try:
            x, y, width, height = self.get_content_area()

            # Get weather data
            weather_data = self.get_weather_data()
            if not weather_data:
                self.draw.text((x, y), "Unable to fetch weather data",
                             font=self.font_medium, fill=self.RED)
                return

            current = weather_data['current']

            # ===== MAIN WEATHER SECTION (Top - takes bulk of screen) =====

            weather_y = y
            centre_x = x + width // 2

            # Weather icon (large, on left)
            icon = self.load_weather_icon(current['description'])
            if icon:
                # Paste icon at top left
                icon_width = 120
                self.image.paste(icon, (centre_x - icon_width - 50, weather_y + 15),
                                 icon if icon.mode == 'RGBA' else None)
            else:
                # Fallback to drawing if icon fails
                icon_width = 100
                self.draw.text(((width // 2) - icon_width, weather_y), "☁", font=self._load_font(80), fill=self.BLACK)

            # Temperature and details (right of icon)
            temp_x = centre_x + 20
            temp_y = weather_y

            # Large temperature
            temp_str = f"{current['temp']}°C"
            self.draw.text((temp_x, temp_y), temp_str,
                          font=self._load_font(48), fill=self.BLACK)

            # Description
            self.draw.text((temp_x, temp_y + 55), current['description'],
                          font=self.font_medium, fill=self.BLACK)

            # Feels like
            feels_like = f"Feels like {current['feels_like']}°C"
            self.draw.text((temp_x, temp_y + 85), feels_like,
                          font=self.font_small, fill=self.BLACK)

            # High/Low (prominent)
            high_low = f"↑ {current['high']}°  ↓ {current['low']}°"
            self.draw.text((temp_x, temp_y + 105), high_low,
                          font=self.font_medium, fill=self.BLACK)

            # Weather details grid (below icon and temp)
            details_y = weather_y + 140

            # Draw separator line
            self.draw.line([(x, details_y), (x + width, details_y)],
                          fill=self.BLACK, width=2)
            details_y += 25

            # Three columns of weather details
            col1_x = x
            col2_x = x + int(width / 3)
            col3_x = x + int(2 * width / 3)
            row_height = 35

            details_col1 = [
                ("Sunrise:", current['sunrise']),
                ("Sunset:", current['sunset']),
            ]

            details_col2 = [
                ("Rain: ", f"{current['rain_chance']}%"),
                ("Wind: ", f"{current['wind_dir']} {current['wind_speed']} mph"),
            ]

            details_col3 = [
                ("UV:", f"{current['uv_current']} // {current['uv_peak']}"),
                ("",   f"{self.get_uv_rating(current['uv_peak'])}"),
            ]

            # Draw column 1
            for i, (label, value) in enumerate(details_col1):
                y_pos = details_y + (i * row_height)
                self.draw.text((col1_x + 30, y_pos), label,
                             font=self.font_medium, fill=self.BLACK)
                self.draw.text((col1_x + 130, y_pos), value,
                             font=self.font_medium, fill=self.BLACK)

            # Draw column 2
            for i, (label, value) in enumerate(details_col2):
                y_pos = details_y + (i * row_height)
                self.draw.text((col2_x + 30, y_pos), label,
                             font=self.font_medium, fill=self.BLACK)
                self.draw.text((col2_x + 100, y_pos), value,
                             font=self.font_medium, fill=self.BLACK)

            # Draw column 3
            for i, (label, value) in enumerate(details_col3):
                y_pos = details_y + (i * row_height)
                self.draw.text((col3_x + 40, y_pos), label,
                             font=self.font_medium, fill=self.BLACK)
                self.draw.text((col3_x + 90, y_pos), value,
                             font=self.font_medium, fill=self.BLACK)

            # ===== BOTTOM SECTION: Tides and Water Quality (Two Columns) =====

            bottom_y = details_y + 85

            # Draw separator
            self.draw.line([(x, bottom_y), (x + width, bottom_y)],
                          fill=self.BLACK, width=2)
            bottom_y += 10

            # Two columns at bottom
            left_col_width = int(width / 2) - 10
            right_col_x = x + left_col_width + 20

            # Draw vertical separator
            separator_x = x + left_col_width + 10
            self.draw.line([(separator_x, bottom_y), (separator_x, y + height)],
                          fill=self.BLACK, width=2)

            # LEFT COLUMN: Tide Times
            tide_y = self.draw_tide_times_compact(x, bottom_y, left_col_width)

            # RIGHT COLUMN: Water Quality
            quality_y = bottom_y
            quality_y = self.draw_water_quality_compact(right_col_x, quality_y,
                                                        width - left_col_width - 30)

            # Sewage status below water quality
            quality_y += 10
            self.draw_sewage_status_compact(right_col_x, quality_y,
                                           width - left_col_width - 30)
        except Exception as e:
            logger.error(f"Error rendering WeatherScreen: {e}", exc_info=True)
            x, y, width, height = self.get_content_area()
            self.draw.text((x, y), "Error loading weather data",
                         font=self.font_medium, fill=self.RED)
            self.draw.text((x, y + 30), str(e)[:50],
                         font=self.font_small, fill=self.RED)

    def draw_tide_times_compact(self, x, y, width):
        """Draw next high and low tide in chronological order"""
        from datetime import datetime

        # Title
        x += 35
        self.draw.text((x, y), "Exmouth Beach: Tide Times",
                     font=self.font_medium, fill=self.BLUE)
        y += 40
        # Get tide data
        tides = self.get_tide_data()
        if not tides:
            self.draw.text((x + 5, y), "Unavailable",
                         font=self.font_tiny, fill=self.BLACK)
            return y + 20
        #  Get current time
        now = datetime.now().time()

        # Filter to only future tides
        future_tides = []

        for tide in tides:
            try:
                # Parse tide time (Format: "HH:MM")
                tide_time = datetime.strptime(tide['time'], '%H:%M').time()
            except (KeyError, TypeError, ValueError):
                tide_value = tide.get('time') if isinstance(tide, dict) else tide
                logger.warning(f"Skipping unparsable tide time: {tide_value}")
                continue

            # Check if tide is in the future
            if tide_time > now:
                future_tides.append((tide_time, tide))

        future_tides.sort(key=lambda item: item[0])
        next_tides = [tide for _, tide in future_tides[:2]]

        if not next_tides:
            self.draw.text((x + 5, y), "No more tides today",
                           font=self.font_tiny, fill=self.BLACK)
            return y + 20

        # Display each tide in order
        for tide in next_tides:
            tide_type = tide.get('type', 'Unknown')
            icon = "⬆" if tide_type == 'High' else "⬇"
            color = self.BLACK

            tide_text = f"{icon} {tide_type:4s}   {tide.get('time', '--:--')}"
            self.draw.text((x + 25, y), tide_text,
                          font=self.font_medium, fill=color)
            self.draw.text((x + 220, y), f"{tide.get('height', '?')}m",
                          font=self.font_medium, fill=self.BLACK)

            y += 35

        return y

    def draw_water_quality_compact(self, x, y, width):
        """Draw compact water quality widget"""
        x += 20
        self.draw.text((x + 65, y), "Beach Water Safety",
                     font=self.font_medium, fill=self.BLUE)
        y += 30

        water_quality = self.get_water_quality()
        if not water_quality:
            self.draw.text((x, y), "Data unavailable",
                         font=self.font_small, fill=self.BLACK)
            return y + 25

        # Rating with color coding
        rating = water_quality.get('rating', 'Unknown')

        rating_colors = {
            'Excellent': self.GREEN,
            'Good': self.BLUE,
            'Sufficient': self.ORANGE,
            'Poor': self.RED,
            'Unknown': self.BLACK
        }

        rating_color = rating_colors.get(rating, self.BLACK)

        # Draw rating (large)
        self.draw.text((x, y), "Latest Water Quality: " + rating,
                     font=self.font_medium, fill=self.BLACK)
        y += 32

        # Sample date (small)
        latest_sample = water_quality.get('latest_sample', {})
        if latest_sample and latest_sample.get('date'):
            sample_text = f"Sampled: {latest_sample['date']}"
            self.draw.text((x, y), sample_text,
                         font=self.font_tiny, fill=self.BLACK)
            y += 12

        return y

    def draw_sewage_status_compact(self, x, y, width):
        """Draw compact sewage overflow alert status"""
        x += 20
        self.draw.text((x, y), "Sewage Overflow Discharges",
                     font=self.font_medium, fill=self.BLACK)
        y += 30

        sewage = self.get_sewage_status()
        if not sewage:
            self.draw.text((x, y), "Data unavailable",
                         font=self.font_tiny, fill=self.BLACK)
            return

        status = sewage.get('status', 'UNAVAILABLE')
        message = sewage.get('message', 'Data temporarily unavailable')

        # Status colors
        status_colors = {
            'GOOD': self.GREEN,
            'CAUTION': self.RED,
            'UNSAFE': self.RED,
            'UNAVAILABLE': self.BLACK
        }

        status_icons = {
            'GOOD': '',
            'CAUTION': '',
            'UNSAFE': '',
            'UNAVAILABLE': ''
        }

        color = status_colors.get(status, self.BLACK)
        icon = status_icons.get(status, '')

        # Draw status with icon
        self.draw.text((x, y), icon, font=self.font_medium, fill=color)

        # Draw message (wrapped, max 2 lines)
        lines = self.wrap_text(message, width - 35, self.font_small)
        for line in lines[:2]:
            self.draw.text((x, y), line,
                         font=self.font_small, fill=color)
            y += 20

    def get_uv_rating(self, uv_value):
        """Get UV index rating text"""
        if uv_value < 3:
            return " (Low)"
        elif uv_value < 6:
            return " (Mod)"
        elif uv_value < 8:
            return " (High)"
        elif uv_value < 11:
            return " (V.High)"
        else:
            return " (Extreme)"

    def get_weather_data(self):
        """Fetch weather data from weather_fetcher.py"""
        try:
            raw_data = self.weather_fetcher.fetch_data()
        except Exception as e:
            logger.error(f"Weather fetcher failed: {e}", exc_info=True)
            return None

        if not raw_data:
            if network_disabled():
                logger.info("No weather data returned while network is disabled")
            else:
                logger.error("No weather data returned")
            return None

        try:
            return {
                'current': normalize_current_weather(raw_data, self.weather_fetcher)
            }
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Weather data has unexpected shape: {e}")
            return None

    def get_tide_data(self):
        """Fetch tide data from tide_times.py"""
        try:
            tides = self.tide_fetcher.fetch_data()
        except Exception as e:
            logger.error(f"Tide fetcher failed: {e}", exc_info=True)
            return []

        if not tides:
            return []

        normalized = []
        for tide in tides:
            try:
                height = tide['height']
                normalized.append({
                    'type': tide['type'],
                    'time': tide['time'],  # Already a string like '09:40'
                    'height': f"{height:.1f}" if isinstance(height, (int, float)) else str(height)
                })
            except (KeyError, TypeError) as e:
                logger.warning(f"Skipping malformed tide record {tide!r}: {e}")
        return normalized

    def get_water_quality(self):
        """Fetch water quality data from water_quality.py"""
        try:
            data = self.water_quality_fetcher.fetch_data()
        except Exception as e:
            logger.error(f"Water quality fetcher failed: {e}", exc_info=True)
            return None

        if not data:
            return None

        try:
            latest_sample = data.get('latest_sample', {})
            classification = data.get('current_classification', {})

            return {
                'rating': latest_sample.get('overall_rating', 'Unknown'),
                'annual_rating': classification.get('rating', 'Unknown'),
                'year': classification.get('year', 'N/A'),
                'latest_sample': latest_sample
            }
        except AttributeError as e:
            logger.warning(f"Water quality data has unexpected shape: {e}")
            return None

    def get_sewage_status(self):
        """Fetch sewage overflow status from direct_sewage_api.py"""
        try:
            return self.sewage_fetcher.fetch_data()
        except Exception as e:
            logger.error(f"Error fetching sewage status: {e}")
            return None
