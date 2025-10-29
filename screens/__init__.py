#!/usr/bin/env python3
"""
Screen implementations for Boo Haus Display System
Save as: screens/__init__.py and individual files in screens/ directory
"""

# screens/weather_screen.py
from datetime import datetime
from base_screen import BaseScreen
import sys
sys.path.append('.')

class WeatherScreen(BaseScreen):
    """Weather display with tide times and water quality"""
    
    @property
    def name(self) -> str:
        return "Weather"
    
    def render_content(self):
        """Render weather information"""
        x, y, width, height = self.get_content_area()
        current_y = y
        
        # Get weather data
        weather_data = self.get_weather_data()
        if not weather_data:
            self.draw.text((x, current_y), "Unable to fetch weather data", 
                         font=self.font_medium, fill=self.RED)
            return
        
        # Main weather section (left side)
        left_width = int(width * 0.6)
        
        # Weather icon and current temp
        current = weather_data['current']
        self.draw_weather_icon(current['description'], x, current_y, size=60)
        
        # Temperature info (next to icon)
        temp_x = x + 80
        temp_str = f"{current['temp']}°C"
        self.draw.text((temp_x, current_y), temp_str, font=self.font_title, fill=self.BLACK)
        
        feels_like = f"Feels like {current['feels_like']}°C"
        self.draw.text((temp_x, current_y + 32), feels_like, font=self.font_small, fill=self.BLACK)
        
        # High/Low
        high_low = f"↑ {current['high']}°C  ↓ {current['low']}°C"
        self.draw.text((temp_x, current_y + 52), high_low, font=self.font_medium, fill=self.BLUE)
        
        current_y += 85
        
        # Weather details grid
        details_y = current_y
        col1_x = x
        col2_x = x + int(left_width / 2)
        row_height = 25
        
        # Column 1
        details = [
            ("☀ Sunrise:", current['sunrise']),
            ("🌙 Sunset:", current['sunset']),
            ("💧 Rain:", f"{current['rain_chance']}%"),
        ]
        
        for i, (label, value) in enumerate(details):
            y_pos = details_y + (i * row_height)
            self.draw.text((col1_x, y_pos), label, font=self.font_small, fill=self.BLACK)
            self.draw.text((col1_x + 100, y_pos), value, font=self.font_small, fill=self.BLUE)
        
        # Column 2
        details2 = [
            ("🧭 Wind:", f"{current['wind_dir']} {current['wind_speed']} mph"),
            ("☢ UV:", f"{current['uv_current']} (peak {current['uv_peak']})"),
        ]
        
        for i, (label, value) in enumerate(details2):
            y_pos = details_y + (i * row_height)
            self.draw.text((col2_x, y_pos), label, font=self.font_small, fill=self.BLACK)
            self.draw.text((col2_x + 70, y_pos), value, font=self.font_tiny, fill=self.BLUE)
        
        current_y = details_y + (3 * row_height) + 10
        
        # Tide times
        tides = self.get_tide_data()
        if tides:
            self.draw.line([(x, current_y), (x + left_width, current_y)], 
                          fill=self.BLACK, width=1)
            current_y += 5
            
            self.draw.text((x, current_y), "🌊 Exmouth Tides", 
                         font=self.font_medium, fill=self.BLUE)
            current_y += 22
            
            for tide in tides[:4]:  # Show up to 4 tides
                icon = "↑" if tide['type'] == 'High' else "↓"
                tide_text = f"{icon} {tide['type']} at {tide['time']} ({tide['height']}m)"
                self.draw.text((x + 10, current_y), tide_text, 
                             font=self.font_small, fill=self.BLACK)
                current_y += 20
        
        # Right side - Water Quality Widget
        right_x = x + left_width + 20
        right_width = width - left_width - 20
        right_y = y
        
        # Draw separator
        self.draw.line([(right_x - 10, y), (right_x - 10, y + height)], 
                      fill=self.BLACK, width=2)
        
        # Water Quality
        water_quality = self.get_water_quality()
        if water_quality:
            self.draw.text((right_x, right_y), "Beach Water Quality", 
                         font=self.font_medium, fill=self.BLUE)
            right_y += 25
            
            rating = water_quality.get('rating', 'Unknown')
            rating_color = self.GREEN if rating == 'Excellent' else (
                self.BLUE if rating == 'Good' else self.ORANGE)
            
            self.draw.text((right_x, right_y), rating, 
                         font=self.font_large, fill=rating_color)
            right_y += 30
            
            if water_quality.get('latest_sample'):
                sample = water_quality['latest_sample']
                self.draw.text((right_x, right_y), f"Sampled: {sample['date']}", 
                             font=self.font_tiny, fill=self.BLACK)
                right_y += 18
        
        # Sewage overflow status
        sewage = self.get_sewage_status()
        if sewage:
            right_y += 10
            self.draw.line([(right_x, right_y), (right_x + right_width, right_y)], 
                          fill=self.BLACK, width=1)
            right_y += 10
            
            self.draw.text((right_x, right_y), "Sewage Alerts", 
                         font=self.font_medium, fill=self.BLACK)
            right_y += 25
            
            status = sewage['status']
            status_colors = {
                'GOOD': self.GREEN,
                'CAUTION': self.ORANGE,
                'UNSAFE': self.RED,
                'UNAVAILABLE': self.BLACK
            }
            
            status_text = sewage['message']
            color = status_colors.get(status, self.BLACK)
            
            # Wrap text for sewage message
            lines = self.wrap_text(status_text, right_width - 10, self.font_small)
            for line in lines:
                self.draw.text((right_x, right_y), line, font=self.font_small, fill=color)
                right_y += 18
    
    def get_weather_data(self):
        """Fetch weather data from weather_fetcher.py"""
        try:
            from weather_fetcher import WeatherFetcher
            # Get API key from config file
            API_KEY = self.config.get('api_keys', {}).get('openweather')
            if not API_KEY:
                print("Error: OpenWeather API key not found in config")
                return None

            fetcher = WeatherFetcher(API_KEY)
            raw_data = fetcher.get_weather_data()
            
            if not raw_data:
                return None
            
            current = raw_data['current']
            daily = raw_data['daily'][0]
            
            return {
                'current': {
                    'description': current['weather'][0]['description'].title(),
                    'temp': fetcher.kelvin_to_celsius(current['temp']),
                    'feels_like': fetcher.kelvin_to_celsius(current['feels_like']),
                    'high': fetcher.kelvin_to_celsius(daily['temp']['max']),
                    'low': fetcher.kelvin_to_celsius(daily['temp']['min']),
                    'rain_chance': round(daily.get('pop', 0) * 100),
                    'wind_dir': fetcher.get_wind_direction(current.get('wind_deg', 0)),
                    'wind_speed': fetcher.mps_to_mph(current['wind_speed']),
                    'uv_current': current.get('uvi', 0),
                    'uv_peak': fetcher.get_peak_uv_today(raw_data['hourly']) or current.get('uvi', 0),
                    'sunrise': fetcher.format_time(current['sunrise'], raw_data['timezone_offset']),
                    'sunset': fetcher.format_time(current['sunset'], raw_data['timezone_offset'])
                }
            }
        except Exception as e:
            print(f"Error fetching weather: {e}")
            return None
    
    def get_tide_data(self):
        """Fetch tide data"""
        try:
            from tide_times import get_tide_data
            tides = get_tide_data()
            
            return [{
                'type': tide['type'],
                'time': tide['time'].strftime('%H:%M'),
                'height': f"{tide['height']:.1f}"
            } for tide in tides]
        except Exception as e:
            print(f"Error fetching tides: {e}")
            return []
    
    def get_water_quality(self):
        """Fetch water quality data"""
        try:
            from water_quality import ExmouthWaterQuality
            monitor = ExmouthWaterQuality()
            data = monitor.generate_report()
            
            return {
                'rating': data['current_classification']['rating'],
                'latest_sample': data.get('latest_sample', {})
            }
        except Exception as e:
            print(f"Error fetching water quality: {e}")
            return None
    
    def get_sewage_status(self):
        """Fetch sewage overflow status"""
        try:
            from direct_sewage_api import get_exmouth_overflow_status
            return get_exmouth_overflow_status()
        except Exception as e:
            print(f"Error fetching sewage status: {e}")
            return None


# screens/week_screen.py
class WeekScreen(BaseScreen):
    """This week summary: forecast, bins, birthdays"""
    
    @property
    def name(self) -> str:
        return "Week"
    
    def render_content(self):
        """Render this week's information"""
        x, y, width, height = self.get_content_area()
        
        # 5-day forecast (top section)
        forecast_y = self.draw_section_title("5-Day Forecast", y)
        forecast_y = self.draw_5_day_forecast(x, forecast_y, width)
        
        # Bins and birthdays (bottom section, two columns)
        forecast_y += 15
        col_width = int(width / 2) - 10
        
        # Bins (left column)
        bins_y = self.draw_section_title("Upcoming Bin Collections", forecast_y)
        self.draw_bin_collections(x, bins_y, col_width)
        
        # Birthdays (right column)
        bday_x = x + col_width + 20
        bday_y = self.draw_section_title("This Week's Birthdays", forecast_y)
        self.draw_birthdays_this_week(bday_x, bday_y, col_width)
    
    def draw_5_day_forecast(self, x, y, width):
        """Draw 5-day weather forecast"""
        try:
            from weather_fetcher import WeatherFetcher
            # Get API key from config file
            API_KEY = self.config.get('api_keys', {}).get('openweather')
            if not API_KEY:
                self.draw.text((x, y), "API key not configured",
                             font=self.font_small, fill=self.BLACK)
                return y + 20

            fetcher = WeatherFetcher(API_KEY)
            data = fetcher.get_weather_data()
            
            if not data:
                self.draw.text((x, y), "Unable to fetch forecast", 
                             font=self.font_small, fill=self.RED)
                return y + 20
            
            # Draw 5 days horizontally
            day_width = width // 5
            current_y = y
            
            for i in range(5):
                day_data = data['daily'][i]
                day_x = x + (i * day_width)
                
                # Date
                date = datetime.fromtimestamp(day_data['dt']).strftime("%a %d")
                self.draw.text((day_x, current_y), date, 
                             font=self.font_small, fill=self.BLACK)
                
                # Weather icon (simplified)
                weather = day_data['weather'][0]['main']
                self.draw.text((day_x, current_y + 18), weather[:8], 
                             font=self.font_tiny, fill=self.BLUE)
                
                # Temps
                high = fetcher.kelvin_to_celsius(day_data['temp']['max'])
                low = fetcher.kelvin_to_celsius(day_data['temp']['min'])
                self.draw.text((day_x, current_y + 35), f"{high}°/{low}°", 
                             font=self.font_small, fill=self.BLACK)
                
                # Rain chance
                rain = round(day_data.get('pop', 0) * 100)
                self.draw.text((day_x, current_y + 52), f"💧 {rain}%", 
                             font=self.font_tiny, fill=self.BLUE)
                
                # Wind
                wind = fetcher.mps_to_mph(day_data['wind_speed'])
                self.draw.text((day_x, current_y + 68), f"🌬 {wind}mph", 
                             font=self.font_tiny, fill=self.BLACK)
            
            return current_y + 95
            
        except Exception as e:
            self.draw.text((x, y), f"Forecast error: {e}", 
                         font=self.font_tiny, fill=self.RED)
            return y + 20
    
    def draw_bin_collections(self, x, y, width):
        """Draw upcoming bin collections"""
        try:
            from bin_collections import EastDevonWasteCollector
            # Get location data from config file
            UPRN = self.config.get('locations', {}).get('uprn')
            POSTCODE = self.config.get('locations', {}).get('postcode')

            if not UPRN or not POSTCODE:
                self.draw.text((x, y), "Location not configured",
                             font=self.font_small, fill=self.BLACK)
                return

            collector = EastDevonWasteCollector(uprn=UPRN, postcode=POSTCODE)
            collections = collector.fetch_collection_schedule()
            
            if not collections:
                self.draw.text((x, y), "No bin data available", 
                             font=self.font_small, fill=self.BLACK)
                return
            
            today = datetime.now().date()
            current_y = y
            
            for collection in collections[:4]:  # Show next 4
                try:
                    date_obj = datetime.fromisoformat(collection['date'])
                    days_until = (date_obj.date() - today).days
                    
                    if days_until < 0:
                        continue
                    
                    # Date
                    date_str = date_obj.strftime('%a %d %b')
                    
                    # Days until
                    if days_until == 0:
                        day_text = "TODAY"
                        color = self.RED
                    elif days_until == 1:
                        day_text = "TOMORROW"
                        color = self.ORANGE
                    else:
                        day_text = f"in {days_until} days"
                        color = self.BLACK
                    
                    # Collection type
                    coll_type = collection['type']
                    
                    self.draw.text((x, current_y), f"📅 {date_str}", 
                                 font=self.font_small, fill=self.BLACK)
                    self.draw.text((x + 10, current_y + 18), coll_type, 
                                 font=self.font_tiny, fill=self.BLUE)
                    self.draw.text((x + 10, current_y + 33), day_text, 
                                 font=self.font_tiny, fill=color)
                    
                    current_y += 55
                except:
                    continue
                    
        except Exception as e:
            self.draw.text((x, y), f"Bin collection error", 
                         font=self.font_tiny, fill=self.RED)
    
    def draw_birthdays_this_week(self, x, y, width):
        """Draw birthdays occurring this week"""
        try:
            import json
            with open('birthdays.json', 'r') as f:
                birthdays = json.load(f)
            
            today = datetime.now().date()
            this_week_birthdays = []
            
            for birthday in birthdays:
                # Calculate next birthday
                try:
                    next_bday = datetime(today.year, birthday['month'], birthday['day']).date()
                    if next_bday < today:
                        next_bday = datetime(today.year + 1, birthday['month'], birthday['day']).date()
                    
                    days_until = (next_bday - today).days
                    
                    if 0 <= days_until <= 7:
                        this_week_birthdays.append({
                            'name': birthday['name'],
                            'date': next_bday,
                            'days': days_until
                        })
                except:
                    continue
            
            if not this_week_birthdays:
                self.draw.text((x, y), "No birthdays this week", 
                             font=self.font_small, fill=self.BLACK)
                return
            
            current_y = y
            for bday in sorted(this_week_birthdays, key=lambda x: x['days']):
                date_str = bday['date'].strftime('%a %d %b')
                
                if bday['days'] == 0:
                    day_text = "TODAY! 🎉"
                    color = self.RED
                elif bday['days'] == 1:
                    day_text = "Tomorrow"
                    color = self.ORANGE
                else:
                    day_text = f"in {bday['days']} days"
                    color = self.BLACK
                
                self.draw.text((x, current_y), f"🎂 {bday['name']}", 
                             font=self.font_small, fill=self.BLUE)
                self.draw.text((x + 10, current_y + 18), date_str, 
                             font=self.font_tiny, fill=self.BLACK)
                self.draw.text((x + 10, current_y + 33), day_text, 
                             font=self.font_tiny, fill=color)
                
                current_y += 55
                
        except Exception as e:
            self.draw.text((x, y), "Birthday data error", 
                         font=self.font_tiny, fill=self.RED)


# screens/nfl_screen.py
class NFLScreen(BaseScreen):
    """NFL scores and schedule"""
    
    @property
    def name(self) -> str:
        return "NFL"
    
    def render_content(self):
        """Render NFL scores"""
        try:
            from nfl_scores import NFLWeeklyDisplay
            
            nfl = NFLWeeklyDisplay()
            week_label, games, bye_teams = nfl.get_games_list(format_type='inky')
            
            x, y, width, height = self.get_content_area()
            
            # Title
            current_y = self.draw_section_title(f"NFL {week_label}", y)
            
            if not games:
                self.draw.text((x, current_y), "No games this week", 
                             font=self.font_medium, fill=self.BLACK)
                return
            
            # Draw games in two columns
            col_width = width // 2 - 10
            left_x = x
            right_x = x + col_width + 20
            left_y = current_y
            right_y = current_y
            
            # Draw vertical separator
            self.draw.line([(x + col_width + 10, current_y), 
                          (x + col_width + 10, y + height)], 
                         fill=self.BLACK, width=1)
            
            mid_point = len(games) // 2
            line_height = 18
            
            # Left column
            for game in games[:mid_point]:
                if left_y > y + height - 20:
                    break
                self.draw_nfl_game(game, left_x, left_y, col_width)
                left_y += line_height
            
            # Right column
            for game in games[mid_point:]:
                if right_y > y + height - 20:
                    break
                self.draw_nfl_game(game, right_x, right_y, col_width)
                right_y += line_height
            
            # Bye teams at bottom if space
            if bye_teams and max(left_y, right_y) < y + height - 40:
                bye_y = max(left_y, right_y) + 10
                self.draw.line([(x, bye_y), (x + width, bye_y)], 
                              fill=self.BLACK, width=1)
                bye_y += 8
                
                bye_text = "BYE: " + ", ".join(bye_teams)
                lines = self.wrap_text(bye_text, width, self.font_tiny)
                for line in lines[:2]:  # Max 2 lines
                    self.draw.text((x, bye_y), line, font=self.font_tiny, fill=self.BLACK)
                    bye_y += 12
                    
        except Exception as e:
            x, y, width, height = self.get_content_area()
            self.draw.text((x, y), f"NFL data error: {e}", 
                         font=self.font_small, fill=self.RED)
    
    def draw_nfl_game(self, game, x, y, width):
        """Draw a single NFL game line"""
        # Parse the game line
        line = game['line']
        
        # Simple rendering - can be enhanced
        self.draw.text((x, y), line[:60], font=self.font_tiny, fill=self.BLACK)


# screens/calendar_screen.py, news_screen.py, birthday_screen.py would follow similar patterns
# Continuing with abbreviated versions...

class CalendarScreen(BaseScreen):
    """Calendar events screen"""
    
    @property
    def name(self) -> str:
        return "Calendar"
    
    def render_content(self):
        """Render calendar events - uses existing calendar_display.py logic"""
        try:
            from calendar_display import CalendarData, EInkCalendarDisplay

            # Get calendar IDs from config file
            calendar_ids = self.config.get('screens', {}).get('calendar', {}).get('calendar_ids', [])

            if not calendar_ids:
                x, y, width, height = self.get_content_area()
                self.draw.text((x, y), "Calendar IDs not configured",
                             font=self.font_medium, fill=self.BLACK)
                return

            calendar = CalendarData(calendar_ids)
            calendar.authenticate()
            events = calendar.get_events(max_results=10, days_ahead=14)
            formatted_events = [calendar.format_event_for_display(e) for e in events]
            
            # Use the existing display logic but adapt to our layout
            display = EInkCalendarDisplay(self.width, self.height)
            temp_image = display.render_calendar(formatted_events)
            
            # Copy the content area to our image
            self.image.paste(temp_image.crop((0, 55, self.width, self.height)), 
                           (0, self.header_height))
            
        except Exception as e:
            x, y, _, _ = self.get_content_area()
            self.draw.text((x, y), f"Calendar error: {e}", 
                         font=self.font_small, fill=self.RED)


class NewsScreen(BaseScreen):
    """News summaries screen"""
    
    @property
    def name(self) -> str:
        return "News"
    
    def render_content(self):
        """Render news summaries - uses existing news_display.py logic"""
        try:
            from news_display import NewsData, EInkNewsDisplay
            
            news_data = NewsData('headline_summaries_cache.json')
            stories = news_data.load_stories(num_stories=4)
            
            if not stories:
                x, y, _, _ = self.get_content_area()
                self.draw.text((x, y), "No news available", 
                             font=self.font_medium, fill=self.BLACK)
                return
            
            display = EInkNewsDisplay(self.width, self.height)
            temp_image = display.render_news(stories)
            
            # Copy content area
            self.image.paste(temp_image.crop((0, 55, self.width, self.height)), 
                           (0, self.header_height))
            
        except Exception as e:
            x, y, _, _ = self.get_content_area()
            self.draw.text((x, y), f"News error: {e}", 
                         font=self.font_small, fill=self.RED)


class BirthdayScreen(BaseScreen):
    """Birthday tracker screen"""
    
    @property
    def name(self) -> str:
        return "Birthday"
    
    def render_content(self):
        """Render birthday tracker - uses existing birthday_tracker.py logic"""
        try:
            from birthday_tracker import BirthdayData, EInkBirthdayDisplay
            
            bday_data = BirthdayData('birthdays.json')
            bday_data.load_birthdays()
            upcoming = bday_data.get_upcoming_birthdays(max_count=12)
            
            display = EInkBirthdayDisplay(self.width, self.height)
            temp_image = display.render_birthdays(upcoming)
            
            # Copy content area
            self.image.paste(temp_image.crop((0, 55, self.width, self.height)), 
                           (0, self.header_height))
            
        except Exception as e:
            x, y, _, _ = self.get_content_area()
            self.draw.text((x, y), f"Birthday error: {e}", 
                         font=self.font_small, fill=self.RED)