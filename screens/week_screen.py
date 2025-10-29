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
import json
import logging

logger = logging.getLogger(__name__)


class WeekScreen(BaseScreen):
    """This week summary: forecast, bins, birthdays"""
    
    @property
    def name(self) -> str:
        return "week"
    
    def __init__(self, config):
        super().__init__(config)
        self.icon_dir = "weather_icons"
    
    def load_weather_icon_small(self, description: str) -> Image.Image:
        """Load small weather icon (60x60)"""
        desc_lower = description.lower()
        
        # Map weather descriptions to icon filenames
        icon_mapping = {
            'clear': 'sun.png',
            'sun': 'sun.png',
            'few clouds': 'partly_cloudy.png',
            'partly': 'partly_cloudy.png',
            'scattered clouds': 'partly_cloudy.png',
            'overcast clouds': 'cloudy.png',
            'broken clouds': 'partly_cloudy.png',
            'overcast': 'overcast.png',
            'light rain': 'drizzle.png',
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
        
        icon_path = os.path.join(self.icon_dir, icon_file)
        
        try:
            if os.path.exists(icon_path):
                icon = Image.open(icon_path)
                icon = icon.resize((60, 60), Image.Resampling.LANCZOS)
                return icon
            else:
                return None
        except Exception as e:
            logger.error(f"Error loading weather icon: {e}")
            return None
    
    def render_content(self):
        """Render this week's information"""
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
        self.draw.text((events_x, section2_y), "Celebrations", 
                      font=self.font_large, fill=self.BLUE)
        
        # Draw underline for title
        title_bbox = self.draw.textbbox((events_x, section2_y), " ", 
                                       font=self.font_large)
        line_y = title_bbox[3] + 5
        self.draw.line([(events_x, line_y), (x + width - 5, line_y)], 
                      fill=self.BLUE, width=2)
        
        events_y = line_y + 10
        self.draw_events_this_week(events_x, events_y, col_width, height - (events_y - y))
    
    def draw_5_day_forecast(self, x, y, width):
        """Draw 5-day weather forecast with icons"""
        try:
            from weather_fetcher import WeatherFetcher

            # Get API key from config file
            api_key = self.config.get('api_keys', {}).get('openweather')
            if not api_key:
                return []  # Return empty list if no API key

            fetcher = WeatherFetcher(api_key)
            data = fetcher.get_weather_data()
            
            if not data:
                self.draw.text((x, y), "Unable to fetch forecast", 
                             font=self.font_small, fill=self.RED)
                return y + 30
            
            # Configuration
            num_days = self.config.get('screens', {}).get('week', {}).get('forecast_days', 5)
            day_width = width // num_days
            current_y = y
            
            # Draw each day
            for i in range(num_days):
                if i >= len(data['daily']):
                    break
                    
                day_data = data['daily'][i]
                day_x = x + (i * day_width)
                
                # Draw vertical separator between days
                if i > 0:
                    self.draw.line([(day_x - 5, current_y), 
                                  (day_x - 5, current_y + 130)], 
                                 fill=self.BLACK, width=1)
                
                # Define day spacing for right justify
                day_right = day_x + day_width - 15

                # Day name and date
                date = datetime.fromtimestamp(day_data['dt'])
                day_name = date.strftime("%a")
                date_num = date.strftime("%d")
                
                if i == 0:
                    day_text = "Today"
                    day_color = self.GREEN
                elif i == 1:
                    day_text = "Tomozzy"
                    day_color = self.BLUE
                else:
                    day_text = day_name
                    day_color = self.BLACK
                
                def get_text_width(text, font):
                   text_bbox = self.draw.textbbox((0, 0), text, font)
                   text_width = text_bbox[2] - text_bbox[0]
                   return text_width
                
                # Day name (larger font)
                self.draw.text((day_x + 5, current_y), day_text, 
                             font=self.font_medium, fill=day_color)
                
                # Date number
                date_width = get_text_width(date_num, self.font_medium)
                self.draw.text((day_right - date_width, current_y), date_num, 
                             font=self.font_medium, fill=self.BLACK)
                
                # Weather icon
                weather_main = day_data['weather'][0]['main']
                weather_desc = day_data['weather'][0]['description'].title()
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
                
                # Weather description
                if weather_desc == "Heavy Intensity Rain":
                    weather_text = "Heavy Rain"
                else:
                    weather_text = weather_desc[:18]
                desc_y = current_y + 28
                desc_width = get_text_width(weather_text, self.font_tiny)
                self.draw.text((day_x + 7, desc_y), weather_text, 
                                 font=self.font_tiny, fill=self.BLACK)
                
                # Temperature high/low (larger font)
                high = fetcher.kelvin_to_celsius(day_data['temp']['max'])
                low = fetcher.kelvin_to_celsius(day_data['temp']['min'])
                
                high_width = get_text_width(f"HI {high:.0f}°", self.font_small)
                low_width = get_text_width(f"LO {low:.0f}°", self.font_small)
                self.draw.text((day_x + day_width - (high_width +  15), current_y + 50), 
                             f"HI {high:.0f}°", font=self.font_small, fill=self.RED)
                self.draw.text((day_x + day_width - (low_width + 15), current_y + 72), 
                             f"LO {low:.0f}°", font=self.font_small, fill=self.BLUE)

                """
                # Old text with up and down arrows for high and low temp
                self.draw.text((day_x + 80, current_y + 30), f"↑{high}°",
                             font=self.font_small, fill=self.RED)
                self.draw.text((day_x + 80, current_y + 52), f"↓{low}°",
                             font=self.font_small, fill=self.BLUE)

                # Left this in case of trying to put high and low side-by-side
                self.draw.text((day_x + 80, current_y + 30), f"{high}°",
                             font=self.font_small, fill=self.RED)
                self.draw.text((day_x + 80, current_y + 52), f"{low}°",
                             font=self.font_small, fill=self.BLUE)

                """

                # Wind speed and rain chance
                wind = fetcher.mps_to_mph(day_data['wind_speed'])
                wind_text = f"Wind {wind:.0f}mph"
                rain = round(day_data.get('pop', 0) * 100)
                rain_text = f"Rain {rain}%"
                rain_width = get_text_width(rain_text, self.font_tiny)
                wind_width = get_text_width(wind_text, self.font_tiny)
                self.draw.text((day_right - rain_width, current_y + 95), rain_text, 
                             font=self.font_tiny, fill=self.BLACK)
                self.draw.text((day_right - wind_width, current_y + 112), wind_text,
                             font=self.font_tiny, fill=self.BLACK)
            
            return current_y + 120
            
        except Exception as e:
            logger.error(f"Forecast error: {e}", exc_info=True)
            self.draw.text((x, y), f"Forecast unavailable", 
                         font=self.font_small, fill=self.RED)
            return y + 50
    
    def draw_bin_collections(self, x, y, width, max_height):
        """Draw upcoming bin collections in single line format"""
        try:
            from bin_collections import EastDevonWasteCollector

            # Get location data from config file
            uprn = self.config.get('locations', {}).get('uprn')
            postcode = self.config.get('locations', {}).get('postcode')

            if not uprn or not postcode:
                self.draw.text((x, y), "Location not configured",
                             font=self.font_small, fill=self.BLACK)
                return y + 20

            collector = EastDevonWasteCollector(uprn=uprn, postcode=postcode)
            collections = collector.fetch_collection_schedule()
            
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
                    
                except Exception as e:
                    logger.error(f"Error processing collection: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Bin collection error: {e}", exc_info=True)
            self.draw.text((x, y), "Bin data unavailable", 
                         font=self.font_tiny, fill=self.RED)
    
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
        all_events = birthdays + holidays
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
            
            event_type = event['type']
            name = event['name']
            date_obj = event['date']
            days = event['days']
            
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
            birthday_file = self.config.get('screens', {}).get('birthday', {}).get(
                'birthday_file', 'birthdays.json')
            
            with open(birthday_file, 'r') as f:
                birthdays = json.load(f)
            
            today = datetime.now().date()
            this_week_birthdays = []
            
            for birthday in birthdays:
                try:
                    # Calculate next birthday
                    next_bday = datetime(today.year, birthday['month'], birthday['day']).date()
                    if next_bday < today:
                        next_bday = datetime(today.year + 1, birthday['month'], birthday['day']).date()
                    
                    days_until = (next_bday - today).days
                    
                    # Include if within next 7 days
                    if 0 <= days_until <= 7:
                        this_week_birthdays.append({
                            'type': 'birthday',
                            'name': birthday['name'],
                            'date': next_bday,
                            'days': days_until
                        })
                except Exception as e:
                    logger.error(f"Error processing birthday: {e}")
                    continue
            
            return this_week_birthdays
            
        except FileNotFoundError:
            logger.error(f"Birthday file not found: {birthday_file}")
            return []
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
                except Exception as e:
                    logger.error(f"Error processing holiday {date_key}: {e}")
                    continue
            
            return holidays
            
        except Exception as e:
            logger.error(f"Holiday error: {e}")
            return []
