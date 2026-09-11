#!/usr/bin/env python3
"""
Tide times fetcher for Exmouth from BBC Weather.
Scrapes live data and caches via BaseFetcher.
"""

from bs4 import BeautifulSoup
from datetime import datetime
import logging
import re

from config import config
from base_fetcher import BaseFetcher, http_get_text

logger = logging.getLogger(__name__)

BBC_TIDE_URL = "https://www.bbc.co.uk/weather/coast-and-sea/tide-tables/10/27"

BBC_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}


class TideFetcher(BaseFetcher):
    """Fetches tide data for Exmouth by scraping BBC Weather."""

    def __init__(self):
        super().__init__(
            cache_file="tide_cache.json",
            cache_expiry_minutes=config.get('data_refresh.tide_cache_expiry', 60)
        )

    def _fetch_data_from_source(self):
        """Scrape today's tide data from BBC Weather."""
        try:
            logger.info(f"Fetching tide data from {BBC_TIDE_URL}")
            html = http_get_text(
                BBC_TIDE_URL,
                headers=BBC_HEADERS,
                timeout=15,
                description="BBC tide table",
            )
            if html is None:
                return None
            soup = BeautifulSoup(html, 'html.parser')

            tables = soup.find_all('table')
            if not tables:
                logger.warning("No tide tables found on the BBC page")
                return None

            table = tables[0]  # First table is today's data
            rows = table.find_all('tr')[1:]  # Skip header row

            tides = []
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    tide_type = cells[0].get_text().strip()   # 'High' or 'Low'
                    time_text = cells[1].get_text(" ", strip=True)
                    height_text = cells[2].get_text(" ", strip=True)

                    if tide_type not in ("High", "Low"):
                        logger.debug(f"Skipping non high/low tide row: {tide_type}")
                        continue

                    time_match = re.search(r'\b\d{1,2}:\d{2}\b', time_text)
                    height_match = re.search(r'\d+(?:\.\d+)?', height_text)
                    if not time_match or not height_match:
                        logger.warning(
                            f"Could not find tide time/height in row: "
                            f"{tide_type!r}, {time_text!r}, {height_text!r}"
                        )
                        continue

                    time_str = time_match.group(0)
                    height_str = height_match.group(0)

                    try:
                        # Validate time format
                        datetime.strptime(time_str, '%H:%M')
                        height = float(height_str)

                        tides.append({
                            'type': tide_type,
                            'time': time_str,
                            'height': height
                        })
                    except ValueError as e:
                        logger.warning(f"Could not parse tide data: {e}")
                        continue

            logger.info(f"Found {len(tides)} tide entries")
            return tides or None

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Unexpected error fetching tides: {e}")
            return None

    def get_tide_data(self):
        """Get today's tides as a list of dicts with string times."""
        return self.fetch_data() or []


# Standalone function for backward compatibility
def get_tide_data():
    """Scrape tide data from BBC Weather (standalone function)."""
    fetcher = TideFetcher()
    return fetcher.get_tide_data()


if __name__ == "__main__":
    print("BBC Exmouth Tide Times Scraper")
    print()
    tides = get_tide_data()
    if tides:
        today = datetime.now().strftime('%A, %B %d, %Y')
        print(f"Exmouth Tide Times - {today}")
        print("=" * 40)
        for tide in tides:
            icon = "^" if tide['type'] == 'High' else "v"
            print(f"  {icon} {tide['type']} tide at {tide['time']} ({tide['height']:.1f}m)")
    else:
        print("No tide data found")
