"""
Direct API access to South West Water overflow data.
Uses the same ArcGIS REST API endpoint as POOPy.
Fetches live data and caches via BaseFetcher.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import config
from base_fetcher import BaseFetcher, http_get_json

logger = logging.getLogger(__name__)

# ArcGIS API endpoint (from POOPy source code)
API_ROOT = "https://services-eu1.arcgis.com/OMdMOtfhATJPcHe3/arcgis/rest/services/"
CURRENT_API_RESOURCE = "NEH_outlets_PROD/FeatureServer/0/query"

# Exmouth area defaults
EXMOUTH_LAT = 50.62
EXMOUTH_LON = -3.41
RADIUS_KM = 10


def _fetch_all_overflows() -> Optional[List[Dict]]:
    """Fetch all South West Water overflow data from ArcGIS REST API."""
    url = API_ROOT + CURRENT_API_RESOURCE
    params = {
        'where': '1=1',
        'outFields': '*',
        'returnGeometry': 'false',
        'f': 'json',
        'resultRecordCount': 1000
    }

    logger.info("Fetching sewage overflow data from ArcGIS API")
    data = http_get_json(url, params=params, timeout=30, description="ArcGIS sewage API")
    if data is None:
        return None

    if not isinstance(data, dict):
        logger.error("ArcGIS sewage API returned an unexpected response shape")
        return None

    if 'error' in data:
        logger.error(f"ArcGIS API error: {data['error']}")
        return None

    features = data.get('features', [])
    if not isinstance(features, list):
        logger.error("ArcGIS sewage API response did not include a feature list")
        return None

    overflows = []
    for feature in features:
        if not isinstance(feature, dict):
            logger.warning(f"Skipping malformed sewage feature: {feature!r}")
            continue
        attributes = feature.get('attributes', {})
        if not isinstance(attributes, dict):
            logger.warning(f"Skipping sewage feature with malformed attributes: {feature!r}")
            continue
        overflows.append(attributes)

    logger.info(f"Retrieved {len(overflows)} overflow monitors")
    return overflows


def _get_exmouth_status(all_overflows):
    """Filter overflows to Exmouth area and determine status."""
    if not all_overflows:
        return {
            'active_count': 0,
            'recent_count': 0,
            'active_overflows': [],
            'recent_overflows': [],
            'status': 'UNAVAILABLE',
            'message': 'Data temporarily unavailable',
            'timestamp': datetime.now().isoformat()
        }

    active_overflows = []
    recent_overflows = []
    current_time = datetime.now()
    cutoff_time = current_time - timedelta(hours=48)

    for overflow in all_overflows:
        lat = overflow.get('latitude')
        lon = overflow.get('longitude')

        if lat is None or lon is None:
            continue

        # Simple distance check (good enough for small distances)
        dlat = lat - EXMOUTH_LAT
        dlon = lon - EXMOUTH_LON
        distance_km = ((dlat * 111) ** 2 + (dlon * 111 * 0.7) ** 2) ** 0.5

        if distance_km <= RADIUS_KM:
            watercourse = overflow.get('receivingWaterCourse', 'Unknown watercourse')

            # status: 1 = discharging, 0 = not discharging, -1 = offline
            status = overflow.get('status')

            if status == 1:
                active_overflows.append(watercourse)

            # Check for recent activity (last 48 hours)
            latest_event_end = overflow.get('latestEventEnd')
            if latest_event_end:
                try:
                    end_dt = datetime.fromtimestamp(latest_event_end / 1000)
                    if end_dt > cutoff_time:
                        hours_ago = (current_time - end_dt).total_seconds() / 3600
                        recent_overflows.append((watercourse, int(hours_ago)))
                except (TypeError, ValueError, OverflowError, OSError):
                    logger.warning(f"Skipping sewage event with invalid latestEventEnd: {latest_event_end!r}")

    active_count = len(active_overflows)
    recent_count = len(recent_overflows)

    if active_count > 0:
        status = 'UNSAFE'
        unique_watercourses = list(set(active_overflows))
        names = ', '.join(unique_watercourses[:2])
        extra = f' +{len(unique_watercourses)-2} more' if len(unique_watercourses) > 2 else ''
        message = f'Active discharge to {names}{extra}'
    elif recent_count > 0:
        status = 'CAUTION'
        most_recent = min(recent_overflows, key=lambda x: x[1])
        watercourse, hours = most_recent
        message = f'{watercourse} {hours}h ago'
    else:
        status = 'GOOD'
        message = 'No recent discharges'

    return {
        'active_count': active_count,
        'recent_count': recent_count,
        'active_watercourses': list(set(active_overflows)),
        'recent_watercourses': list(set([wc for wc, _ in recent_overflows])),
        'status': status,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }


class SewageFetcher(BaseFetcher):
    """Fetches sewage overflow data for Exmouth from ArcGIS API."""

    def __init__(self):
        super().__init__(
            cache_file="sewage_cache.json",
            cache_expiry_minutes=config.get('data_refresh.sewage_cache_expiry', 60)
        )

    def _fetch_data_from_source(self) -> Optional[Dict]:
        """Fetch live sewage overflow status from ArcGIS API."""
        all_overflows = _fetch_all_overflows()
        if all_overflows is None:
            return None
        return _get_exmouth_status(all_overflows)

    def get_exmouth_overflow_status(self) -> Dict:
        """Returns the sewage overflow status (from cache or fresh)."""
        return self.fetch_data() or {
            'status': 'UNAVAILABLE',
            'message': 'Data temporarily unavailable'
        }


# Standalone function for backward compatibility
def get_exmouth_overflow_status():
    """Get sewage overflow status for Exmouth area."""
    fetcher = SewageFetcher()
    return fetcher.get_exmouth_overflow_status()


def get_sewage_status_line():
    """Get a one-line sewage status for display."""
    status = get_exmouth_overflow_status()
    status_icons = {
        'GOOD': '[OK]',
        'CAUTION': '[!]',
        'UNSAFE': '[!!]',
        'UNAVAILABLE': '[?]',
    }
    icon = status_icons.get(status.get('status'), '?')
    return f"Sewage: {icon} {status.get('message', 'Data temporarily unavailable')}"


if __name__ == "__main__":
    print("South West Water Sewage Overflow Status")
    print("=" * 50)
    status = get_exmouth_overflow_status()
    print(f"Status: {status['status']}")
    print(f"Message: {status['message']}")
    print(f"Active discharges: {status.get('active_count', 0)}")
    print(f"Recent (48h): {status.get('recent_count', 0)}")
