"""
Exmouth Beach Water Quality Monitor
Fetches live data from Environment Agency API and caches via BaseFetcher.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from config import config
from base_fetcher import BaseFetcher, http_get_json

logger = logging.getLogger(__name__)


# EU Bathing Water Directive thresholds
THRESHOLDS = {
    'ecoli': [(250, 'Excellent'), (500, 'Good'), (900, 'Sufficient')],
    'enterococci': [(100, 'Excellent'), (200, 'Good'), (330, 'Sufficient')]
}

EA_BASE_URL = "https://environment.data.gov.uk"


def _get_rating(value, bacteria_type):
    """Determine rating for bacterial count."""
    if value is None:
        return 'Unknown'

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 'Unknown'

    for threshold, rating in THRESHOLDS[bacteria_type]:
        if value < threshold:
            return rating
    return 'Poor'


def _get_overall_rating(ecoli, enterococci):
    """Get worst rating of the two bacteria types."""
    ratings = {'Excellent': 1, 'Good': 2, 'Sufficient': 3, 'Poor': 4, 'Unknown': 5}
    ecoli_rating = _get_rating(ecoli, 'ecoli')
    entero_rating = _get_rating(enterococci, 'enterococci')
    worst = max(ecoli_rating, entero_rating, key=lambda r: ratings.get(r, 5))
    return worst if worst != 'Unknown' else 'Unknown'


def _parse_datetime(date_str):
    """Parse datetime from EA API response."""
    try:
        if 'gregorian-instant' in str(date_str):
            date_str = date_str.split('/')[-1]
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return {
            'date': dt.strftime('%Y-%m-%d'),
            'time': dt.strftime('%H:%M:%S'),
            'datetime': dt.isoformat()
        }
    except (ValueError, AttributeError):
        return {'date': str(date_str), 'time': 'N/A', 'datetime': str(date_str)}


def _safe_get(obj, *keys, default='N/A'):
    """Safely navigate nested dictionaries/lists."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list) and obj:
            obj = obj[0]
        else:
            return default
    return obj if obj is not None else default


def _api_get(endpoint, params=None) -> Optional[Dict]:
    """Make EA API request and return JSON response."""
    url = f"{EA_BASE_URL}{endpoint}"
    return http_get_json(url, params=params, timeout=15, description=f"EA API {endpoint}")


class WaterQualityFetcher(BaseFetcher):
    """Fetches water quality data for Exmouth from the Environment Agency API."""

    def __init__(self):
        super().__init__(
            cache_file="water_quality_cache.json",
            cache_expiry_minutes=config.get('data_refresh.water_quality_cache_expiry', 1440)
        )
        self.beach_id = config.get('locations.beach_id', 'ukk4301-22300')

    def _fetch_data_from_source(self) -> Optional[Dict]:
        """Fetch live water quality report from EA API."""
        try:
            logger.info(f"Fetching water quality data for beach {self.beach_id}")

            # Get beach info and current classification
            beach_data = _api_get(f"/doc/bathing-water/{self.beach_id}.json")
            if beach_data is None:
                return None
            if not isinstance(beach_data, dict):
                logger.error("EA beach endpoint returned an unexpected response shape")
                return None

            beach = beach_data.get('primaryTopic', {})
            if not isinstance(beach, dict):
                logger.error("EA beach primaryTopic was not an object")
                return None
            sp = beach.get('samplingPoint', {})
            if not isinstance(sp, dict):
                sp = {}
            comp = beach.get('latestComplianceAssessment', {})
            if not isinstance(comp, dict):
                comp = {}

            beach_info = {
                'name': _safe_get(beach, 'name', '_value'),
                'id': self.beach_id,
                'easting': sp.get('easting'),
                'northing': sp.get('northing'),
                'latitude': sp.get('lat'),
                'longitude': sp.get('long'),
                'district': _safe_get(beach, 'district', 'name', '_value')
            }

            current_classification = {
                'rating': _safe_get(comp, 'complianceClassification', 'name', '_value'),
                'year': _safe_get(comp, 'sampleYear', 'ordinalYear')
            }

            # Get recent samples
            samples_endpoint = f"/doc/bathing-water-quality/in-season/bathing-water/{self.beach_id}.json"
            samples_data = _api_get(samples_endpoint, {'_pageSize': 10, '_sort': '-sampleDateTime'})
            if samples_data is None:
                return None
            if not isinstance(samples_data, dict):
                logger.error("EA samples endpoint returned an unexpected response shape")
                return None

            samples_result = samples_data.get('result', {})
            if not isinstance(samples_result, dict):
                logger.error("EA samples result was not an object")
                return None

            samples = []
            for item in samples_result.get('items', []):
                if not isinstance(item, dict):
                    logger.warning(f"Skipping malformed water quality sample: {item!r}")
                    continue

                ecoli = item.get('escherichiaColiCount')
                entero = item.get('intestinalEnterococciCount')

                date_obj = item.get('sampleDateTime', {})
                date_str = date_obj.get('inXSDDateTime', date_obj) if isinstance(date_obj, dict) else date_obj
                dt_info = _parse_datetime(str(date_str))

                samples.append({
                    'date': dt_info['date'],
                    'time': dt_info['time'],
                    'datetime': dt_info['datetime'],
                    'ecoli': ecoli,
                    'ecoli_rating': _get_rating(ecoli, 'ecoli') if ecoli else None,
                    'enterococci': entero,
                    'enterococci_rating': _get_rating(entero, 'enterococci') if entero else None,
                    'overall_rating': _get_overall_rating(ecoli, entero)
                })

            # Get compliance history
            history_endpoint = f"/doc/bathing-water-quality/compliance-rBWD/bathing-water/{self.beach_id}.json"
            history_data = _api_get(history_endpoint, {'_pageSize': 10})
            history = []
            if isinstance(history_data, dict):
                history_result = history_data.get('result', {})
                if isinstance(history_result, dict):
                    for item in history_result.get('items', []):
                        if not isinstance(item, dict):
                            logger.warning(f"Skipping malformed water quality history row: {item!r}")
                            continue
                        history.append({
                            'year': _safe_get(item, 'sampleYear', 'ordinalYear'),
                            'rating': _safe_get(item, 'complianceClassification', 'name', '_value')
                        })
                else:
                    logger.warning("EA compliance history result was not an object")
            elif history_data is not None:
                logger.warning("EA compliance history endpoint returned an unexpected response shape")

            report = {
                'generated_at': datetime.now().isoformat(),
                'beach_info': beach_info,
                'current_classification': current_classification,
                'latest_sample': samples[0] if samples else {},
                'recent_samples': samples,
                'compliance_history': history
            }

            logger.info(f"Water quality data fetched: {len(samples)} samples")
            return report

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error(f"Error fetching water quality data: {e}", exc_info=True)
            return None

    def generate_report(self) -> Dict:
        """Returns the water quality report (from cache or fresh)."""
        return self.fetch_data() or {}


# Standalone class for backward compatibility
class ExmouthWaterQuality:
    """Backward-compatible wrapper around WaterQualityFetcher."""

    def __init__(self, beach_id=None):
        self._fetcher = WaterQualityFetcher()
        if beach_id:
            self._fetcher.beach_id = beach_id

    def generate_report(self):
        return self._fetcher.generate_report()

    def save_json(self, filename='exmouth_water_quality.json'):
        data = self.generate_report()
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Exported to: {filename}")
            return data
        except IOError as e:
            print(f"Export failed: {e}")
            return None


if __name__ == "__main__":
    fetcher = WaterQualityFetcher()
    data = fetcher.fetch_data()
    if data:
        print(json.dumps(data, indent=2))
    else:
        print("No water quality data available")
