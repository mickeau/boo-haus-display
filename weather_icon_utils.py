"""
Shared weather icon loading for display screens.
"""

import os
from typing import Optional, Tuple

from PIL import Image


ICON_MAPPING = (
    ('clear', 'sun.png'),
    ('sun', 'sun.png'),
    ('few clouds', 'partly_cloudy.png'),
    ('partly', 'partly_cloudy.png'),
    ('scattered clouds', 'partly_cloudy.png'),
    ('overcast clouds', 'cloudy.png'),
    ('broken clouds', 'partly_cloudy.png'),
    ('overcast', 'overcast.png'),
    ('light rain', 'drizzle.png'),
    ('clouds', 'cloudy.png'),
    ('mist', 'mist.png'),
    ('fog', 'fog.png'),
    ('rain', 'rain.png'),
    ('drizzle', 'drizzle.png'),
    ('shower', 'drizzle.png'),
    ('snow', 'snow.png'),
    ('thunderstorm', 'thunderstorm.png'),
    ('storm', 'thunderstorm.png'),
)


def icon_filename_for_description(description: str) -> str:
    """Return the configured icon filename for a weather description."""
    desc_lower = (description or '').lower()
    for key, filename in ICON_MAPPING:
        if key in desc_lower:
            return filename
    return 'cloudy.png'


def load_weather_icon_image(
    description: str,
    icon_dir: str = 'weather_icons',
    size: Tuple[int, int] = (60, 60),
    logger=None,
) -> Optional[Image.Image]:
    """Load and resize a PNG weather icon, returning None on missing/bad files."""
    icon_file = icon_filename_for_description(description)
    icon_path = os.path.join(icon_dir, icon_file)

    try:
        if not os.path.exists(icon_path):
            if logger:
                logger.warning(f"Weather icon not found: {icon_path}")
            return None

        with Image.open(icon_path) as img:
            return img.resize(size, Image.Resampling.LANCZOS)
    except Exception as e:
        if logger:
            logger.error(f"Error loading weather icon: {e}")
        return None
