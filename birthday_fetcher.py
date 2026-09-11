import json
import logging
from datetime import date
from typing import List, Dict, Optional

from config import config
from base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

class BirthdayFetcher(BaseFetcher):
    def __init__(self):
        super().__init__(cache_file="birthdays_cache.json", cache_expiry_minutes=config.get('data_refresh.birthday_cache_expiry', 1440)) # Cache for 24 hours
        self.birthday_file = config.runtime_path('screens.birthday.birthday_file', 'birthdays.json')

    def _fetch_data_from_source(self) -> Optional[List[Dict]]:
        """Load birthdays from JSON file."""
        try:
            with open(self.birthday_file, 'r') as f:
                birthdays = json.load(f)
            if not isinstance(birthdays, list):
                logger.error(f"Birthday file must contain a list: {self.birthday_file}")
                return None
            logger.info(f"Loaded {len(birthdays)} birthdays from {self.birthday_file}")
            return birthdays
        except FileNotFoundError:
            logger.error(f"Birthday file not found: {self.birthday_file}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid birthday JSON in {self.birthday_file}: {e}")
            return None
        except OSError as e:
            logger.error(f"Error loading birthdays: {e}")
            return None

    def get_upcoming_birthdays(self, days_ahead: int = 7) -> List[Dict]:
        """Get birthdays occurring in the next X days."""
        all_birthdays = self.fetch_data()
        if not all_birthdays:
            return []

        return self._build_upcoming_birthdays(all_birthdays, days_ahead=days_ahead)

    def get_next_birthdays(self, limit: int = 12) -> List[Dict]:
        """Get the next N birthdays regardless of distance."""
        all_birthdays = self.fetch_data()
        if not all_birthdays:
            return []

        return self._build_upcoming_birthdays(all_birthdays, limit=limit)

    def _build_upcoming_birthdays(self, birthdays, days_ahead=None, limit=None) -> List[Dict]:
        """Normalize raw birthday rows into upcoming display events."""
        today = date.today()
        upcoming = []

        for birthday in birthdays:
            try:
                # Calculate next birthday
                month = birthday['month']
                day = birthday['day']
                next_bday = date(today.year, month, day)
                if next_bday < today:
                    next_bday = date(today.year + 1, month, day)

                days_until = (next_bday - today).days

                # Include if within next X days
                if days_ahead is None or 0 <= days_until <= days_ahead:
                    upcoming.append({
                        'type': 'birthday',
                        'name': birthday['name'],
                        'date': next_bday,
                        'days': days_until,
                        'days_until': days_until,
                        'month': month,
                        'day': day,
                    })
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed birthday entry {birthday!r}: {e}")
                continue

        upcoming.sort(key=lambda e: e['days_until'])
        if limit is not None:
            return upcoming[:limit]
        return upcoming
