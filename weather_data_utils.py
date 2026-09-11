"""
Shared normalization helpers for OpenWeather display data.
"""

from datetime import datetime
from typing import Dict


def normalize_current_weather(raw_data: Dict, weather_tools) -> Dict:
    """Convert raw OpenWeather data into the WeatherScreen display shape."""
    current = raw_data['current']
    daily = raw_data['daily'][0]
    hourly = raw_data['hourly']
    weather = current['weather'][0]

    return {
        'description': weather['description'].title(),
        'temp': weather_tools.kelvin_to_celsius(current['temp']),
        'feels_like': weather_tools.kelvin_to_celsius(current['feels_like']),
        'high': weather_tools.kelvin_to_celsius(daily['temp']['max']),
        'low': weather_tools.kelvin_to_celsius(daily['temp']['min']),
        'humidity': current.get('humidity', 0),
        'rain_chance': round(daily.get('pop', 0) * 100),
        'wind_dir': weather_tools.get_wind_direction(current.get('wind_deg', 0)),
        'wind_speed': weather_tools.mps_to_mph(current['wind_speed']),
        'uv_current': round(current.get('uvi', 0), 1),
        'uv_peak': round(weather_tools.get_peak_uv_today(hourly) or current.get('uvi', 0), 1),
        'sunrise': weather_tools.format_time(current['sunrise'], raw_data['timezone_offset']),
        'sunset': weather_tools.format_time(current['sunset'], raw_data['timezone_offset']),
    }


def normalize_forecast_day(day_data: Dict, weather_tools) -> Dict:
    """Convert one raw OpenWeather daily forecast item into display fields."""
    forecast_date = datetime.fromtimestamp(day_data['dt'])
    weather_desc = day_data['weather'][0]['description'].title()
    weather_text = "Heavy Rain" if weather_desc == "Heavy Intensity Rain" else weather_desc[:18]

    return {
        'date': forecast_date,
        'day_name': forecast_date.strftime("%a"),
        'date_num': forecast_date.strftime("%d"),
        'description': weather_desc,
        'display_description': weather_text,
        'high': weather_tools.kelvin_to_celsius(day_data['temp']['max']),
        'low': weather_tools.kelvin_to_celsius(day_data['temp']['min']),
        'wind': weather_tools.mps_to_mph(day_data['wind_speed']),
        'rain_chance': round(day_data.get('pop', 0) * 100),
    }
