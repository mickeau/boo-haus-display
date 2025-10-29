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

logger = logging.getLogger(__name__)


class WeatherScreen(BaseScreen):
    """Weather display with comprehensive local information"""
    
    @property
    def name(self) -> str:
        return "weather"
    
    def __init__(self, config):
        super().__init__(config)
        self.icon_dir = "weather_icons"  # Directory containing PNG icons
        
    def load_weather_icon(self, description: str) -> Image.Image:
        """Load appropriate PNG weather icon based on description"""
        desc_lower = description.lower()
        
        # Map weather descriptions to icon filenames
        icon_mapping = {
            'clear': 'sun.png',           # Clear/sunny
            'sun': 'sun.png',
            'few clouds': 'partly_cloudy.png',
            'partly': 'partly_cloudy.png',
            'scattered clouds': 'partly_cloudy.png',
            'broken clouds': 'partly_cloudy.png',
            'overcast': 'cloudy.png',
            'clouds': 'cloudy.png',
            'mist': 'mist.png',
            'fog': 'fog.png',
            'rain': 'rain.png',
            'drizzle': 'drizzle.png',
            'shower': 'drizzle.png',
            'snow': 'snow.png',
            'thunderstorm': 'thunderstorm.png',
            'storm': 'thunderstorm.png',
        }
        
        # Find matching icon
        icon_file = 'cloudy.png'  # Default
        for key, filename in icon_mapping.items():
            if key in desc_lower:
                icon_file = filename
                break
        
        # Load icon
        icon_path = os.path.join(self.icon_dir, icon_file)
        
        try:
            if os.path.exists(icon_path):
                icon = Image.open(icon_path)
                # Resize to consistent size (120x120 pixels)
                icon = icon.resize((120, 120), Image.Resampling.LANCZOS)
                return icon
            else:
                logger.warning(f"Weather icon not found: {icon_path}")
                return None
        except Exception as e:
            logger.error(f"Error loading weather icon: {e}")
            return None
    
    def render_content(self):
        """Render weather information with new layout"""
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
        centre_x = width // 2
        
        # Weather icon (large, on left)
        icon = self.load_weather_icon(current['description'])
        if icon:
            # Paste icon at top left
            icon_width = 120
            self.image.paste(icon,(centre_x - icon_width - 50, weather_y + 15), icon if icon.mode == 'RGBA' else None)
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
    
    def draw_tide_times_compact(self, x, y, width):
        """Draw next high and low tide in chronological order"""
        from  datetime import datetime, time as dt_time

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
               
               # Check if tide is in the future
               if  tide_time > now:
                   tide['time_obj'] = tide_time # Store for sorting
                   future_tides.append(tide)
            except:
                  continue

            # Get next 2 tides
            next_tides = future_tides[:2]

        if not next_tides:
             self.draw.text((x + 5, y), "No more tides today",
                             font=self.font_tiny, fill=self.BLACK)
             return y + 20

        # Display each tide in order
        for tide in next_tides:
            tide_type = tide['type']
            icon = "⬆" if tide_type == 'High' else "⬇"
            color = self.BLACK

            tide_text = f"{icon} {tide_type:4s}   {tide['time']}"
            self.draw.text((x + 25, y), tide_text, 
                          font = self.font_medium, fill=color)
            self.draw.text((x + 220, y), f"{tide['height']}m",
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
        x += 20
        """Draw compact sewage overflow alert status"""
        self.draw.text((x, y), "Sewage Overflow Discharges", 
                     font=self.font_medium, fill=self.BLACK)
        y += 30
        
        sewage = self.get_sewage_status()
        if not sewage:
            self.draw.text((x, y), "Data unavailable", 
                         font=self.font_tiny, fill=self.BLACK)
            return
        
        status = sewage['status']
        message = sewage['message']
        
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
            from weather_fetcher import WeatherFetcher

            # Get API key from config file
            api_key = self.config.get('api_keys', {}).get('openweather')
            if not api_key:
                logger.error("OpenWeather API key not found in config")
                return None

            fetcher = WeatherFetcher(api_key)
            raw_data = fetcher.get_weather_data()
            
            if not raw_data:
                logger.error("No weather data returned")
                return None
            
            current = raw_data['current']
            daily = raw_data['daily'][0]
            hourly = raw_data['hourly']
            
            return {
                'current': {
                    'description': current['weather'][0]['description'].title(),
                    'temp': fetcher.kelvin_to_celsius(current['temp']),
                    'feels_like': fetcher.kelvin_to_celsius(current['feels_like']),
                    'high': fetcher.kelvin_to_celsius(daily['temp']['max']),
                    'low': fetcher.kelvin_to_celsius(daily['temp']['min']),
                    'humidity': current.get('humidity', 0),
                    'rain_chance': round(daily.get('pop', 0) * 100),
                    'wind_dir': fetcher.get_wind_direction(current.get('wind_deg', 0)),
                    'wind_speed': fetcher.mps_to_mph(current['wind_speed']),
                    'uv_current': round(current.get('uvi', 0), 1),
                    'uv_peak': round(fetcher.get_peak_uv_today(hourly) or current.get('uvi', 0), 1),
                    'sunrise': fetcher.format_time(current['sunrise'], raw_data['timezone_offset']),
                    'sunset': fetcher.format_time(current['sunset'], raw_data['timezone_offset'])
                }
            }
        except Exception as e:
            logger.error(f"Error fetching weather: {e}", exc_info=True)
            return None
    
    def get_tide_data(self):
        """Fetch tide data from tide_times.py"""
        try:
            from tide_times import get_tide_data
            tides = get_tide_data()
            
            return [{
                'type': tide['type'],
                'time': tide['time'].strftime('%H:%M'),
                'height': f"{tide['height']:.1f}"
            } for tide in tides]
        except Exception as e:
            logger.error(f"Error fetching tides: {e}")
            return []
    
    def get_water_quality(self):
        """Fetch water quality data from water_quality.py"""
        try:
            from water_quality import ExmouthWaterQuality
            monitor = ExmouthWaterQuality()
            data = monitor.generate_report()
            
            return {
                'rating': data['latest_sample'].get('overall_rating', 'Unknown'),
                'annual_rating': data['current_classification']['rating'],
                'year': data['current_classification']['year'],
                'latest_sample': data.get('latest_sample', {})
            }
        except Exception as e:
            logger.error(f"Error fetching water quality: {e}")
            return None
    
    def get_sewage_status(self):
        """Fetch sewage overflow status from direct_sewage_api.py"""
        try:
            from direct_sewage_api import get_exmouth_overflow_status
            return get_exmouth_overflow_status()
        except Exception as e:
            logger.error(f"Error fetching sewage status: {e}")
            return None
