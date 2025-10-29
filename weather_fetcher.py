import requests
import json
from datetime import datetime, timezone

class WeatherFetcher:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def get_coordinates(self):
        """Return hardcoded coordinates for Exmouth, UK"""
        # Exmouth, Devon, UK coordinates
        return 50.6208, -3.4131
    
    def kelvin_to_celsius(self, kelvin):
        """Convert Kelvin to Celsius"""
        return round(kelvin - 273.15, 1)
    
    def mps_to_mph(self, mps):
        """Convert meters per second to miles per hour"""
        return round(mps * 2.237, 1)
    
    def get_wind_direction(self, degrees):
        """Convert wind direction degrees to cardinal direction"""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / 22.5) % 16
        return directions[index]
    
    def format_time(self, timestamp, timezone_offset):
        """Format timestamp to readable time"""
        dt = datetime.fromtimestamp(timestamp + timezone_offset, tz=timezone.utc)
        return dt.strftime("%H:%M")
    
    def get_weather_data(self):
        """Fetch weather data using One Call API 3.0"""
        lat, lon = self.get_coordinates()
        
        url = "https://api.openweathermap.org/data/3.0/onecall"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'exclude': 'minutely,alerts'
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error fetching weather data: {response.status_code} - {response.text}")
            return None
    
    def get_peak_uv_today(self, hourly_data):
        """Get the peak UV index for today from hourly data"""
        if not hourly_data:
            return None
        
        today_uv_values = []
        
        # Look through hourly data to find UV values
        for hour in hourly_data:
            uv_value = hour.get('uvi', 0)
            # Only include UV values > 0 (daytime hours)
            if uv_value > 0:
                today_uv_values.append(uv_value)
        
        if today_uv_values:
            return max(today_uv_values)
        return None
    
    def get_tomorrow_forecast(self, daily_data):
        """Get tomorrow's forecast from daily data"""
        if len(daily_data) >= 2:
            return daily_data[1]  # Index 1 is tomorrow (0 is today)
        return None
    
    def display_weather(self):
        """Display formatted weather data"""
        weather_data = self.get_weather_data()
        if not weather_data:
            return
        
        current = weather_data['current']
        daily = weather_data['daily']
        hourly = weather_data['hourly']
        timezone_offset = weather_data['timezone_offset']
        
        print(f"🌤️  Weather for Exmouth, UK")
        print("=" * 40)
        
        # TODAY'S WEATHER
        print("\n📅 TODAY:")
        print(f"   Description: {current['weather'][0]['description'].title()}")
        print(f"   Temperature: {self.kelvin_to_celsius(current['temp'])}°C")
        print(f"   Feels like: {self.kelvin_to_celsius(current['feels_like'])}°C")
        print(f"   Daily High: {self.kelvin_to_celsius(daily[0]['temp']['max'])}°C")
        print(f"   Daily Low: {self.kelvin_to_celsius(daily[0]['temp']['min'])}°C")
        print(f"   Chance of Rain: {round(daily[0].get('pop', 0) * 100)}%")
        
        # Wind
        wind_speed = self.mps_to_mph(current['wind_speed'])
        wind_dir = self.get_wind_direction(current.get('wind_deg', 0))
        print(f"   Wind: {wind_dir} {wind_speed} mph")
        
        # UV Index (current and peak upcoming)
        current_uv = current.get('uvi', 0)
        peak_uv = self.get_peak_uv_today(hourly)
        
        if peak_uv is not None and peak_uv > current_uv:
            print(f"   UV Index: {current_uv} (current) / {peak_uv} (peak upcoming)")
        else:
            print(f"   UV Index: {current_uv}")
        
        # Sunrise/Sunset
        print(f"   Sunrise: {self.format_time(current['sunrise'], timezone_offset)}")
        print(f"   Sunset: {self.format_time(current['sunset'], timezone_offset)}")
        
        # TOMORROW'S WEATHER
        tomorrow = self.get_tomorrow_forecast(daily)
        if tomorrow:
            print(f"\n📅 TOMORROW:")
            print(f"   Description: {tomorrow['weather'][0]['description'].title()}")
            print(f"   Temperature: {self.kelvin_to_celsius(tomorrow['temp']['day'])}°C")
            print(f"   Chance of Rain: {round(tomorrow.get('pop', 0) * 100)}%")
            print(f"   Wind Speed: {self.mps_to_mph(tomorrow['wind_speed'])} mph")
        
        # 7-DAY FORECAST (excluding today and tomorrow)
        print(f"\n📅 7-DAY FORECAST:")
        for i in range(2, min(9, len(daily))):  # Start from day after tomorrow, up to 7 more days
            day = daily[i]
            date = datetime.fromtimestamp(day['dt']).strftime("%A, %b %d")
            temp_high = self.kelvin_to_celsius(day['temp']['max'])
            temp_low = self.kelvin_to_celsius(day['temp']['min'])
            weather_type = day['weather'][0]['main']
            
            print(f"   {date}: {temp_high}°C / {temp_low}°C - {weather_type}")

# Usage
if __name__ == "__main__":
    import json

    # Load API key from config file
    try:
        with open('boo_haus_config.json', 'r') as f:
            config = json.load(f)
        API_KEY = config.get('api_keys', {}).get('openweather')

        if not API_KEY:
            print("Error: OpenWeather API key not found in boo_haus_config.json")
            print("Please add your API key to the config file under api_keys.openweather")
            exit(1)

        weather_fetcher = WeatherFetcher(API_KEY)
        weather_fetcher.display_weather()
    except FileNotFoundError:
        print("Error: boo_haus_config.json not found")
        print("Please create config file from boo_haus_config.example.json")
        exit(1)