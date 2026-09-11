#!/usr/bin/env python3
"""
East Devon District Council Waste Collection Schedule Fetcher
Simplified version that uses the addressfinder API correctly

Requirements:
    pip install requests beautifulsoup4

Usage:
    python east_devon_waste.py
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import logging
import re
from typing import List, Dict, Optional

from config import config
from base_fetcher import BaseFetcher, http_get_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EastDevonWasteCollector(BaseFetcher):
    def __init__(self, uprn: str, postcode: str):
        super().__init__(cache_file="bin_collections_cache.json", cache_expiry_minutes=config.get('data_refresh.bin_collections_cache_expiry', 1440)) # Cache for 24 hours
        self.uprn = uprn
        self.postcode = postcode
        self.base_url = "https://eastdevon.gov.uk"
        self.session = requests.Session()

        # Set headers to match browser request
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://eastdevon.gov.uk/recycling-and-waste/recycling-waste-information/when-is-my-bin-collected/'
        })

    def _fetch_data_from_source(self) -> Optional[List[Dict]]:
        """
        Fetch the waste collection schedule from the East Devon website.

        Returns:
            List of collection events with dates and types
        """
        try:
            # Call the addressfinder API
            search_url = f"{self.base_url}/repositories/hidden-pages/address-finder/"
            params = {
                'qtype': 'bins',
                'term': self.postcode.lower()
            }

            logger.info(f"Searching for addresses with postcode: {self.postcode}")
            addresses = http_get_json(
                search_url,
                params=params,
                timeout=15,
                session=self.session,
                description="East Devon address finder",
            )
            if addresses is None:
                return None
            if not isinstance(addresses, list):
                logger.error("East Devon address finder returned an unexpected response shape")
                return None
            logger.info(f"Found {len(addresses)} addresses")

            # Find the address matching our UPRN
            target_address = None
            for address in addresses:
                if not isinstance(address, dict):
                    logger.warning(f"Skipping malformed address result: {address!r}")
                    continue
                if str(address.get('UPRN', '')) == str(self.uprn):
                    target_address = address
                    logger.info(f"Found matching address: {address.get('label', 'Unknown address')}")
                    break

            if not target_address:
                logger.error(f"No address found with UPRN {self.uprn}")
                return None

            # Parse the HTML Results field
            html_results = target_address.get('Results', '')
            if not html_results:
                logger.error("No Results field found in address data")
                return None

            collections = self._parse_collection_html(html_results)
            if not collections:
                logger.error("No collection dates found in East Devon address result")
                return None

            return collections

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error(f"Unexpected East Devon response shape: {e}", exc_info=True)
            return None

    def _parse_collection_html(self, html_content: str) -> Optional[List[Dict]]:
        """
        Parse HTML content to extract collection dates

        Args:
            html_content: HTML string from the Results field

        Returns:
            List of collection dictionaries
        """
        collections = []

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Look for paragraphs with collection dates
            # East Devon format: <p class="boxtext-important text-centre">Your next X collection will be on <em>Day<br/>Date</em></p>
            important_paras = soup.find_all('p', class_='boxtext-important')

            for para in important_paras:
                para_text = para.get_text()

                # Determine collection type from the paragraph text
                collection_type = self._extract_collection_type(para_text)

                # Extract date from the <em> tag
                em_tag = para.find('em')
                if em_tag:
                    # Get the HTML content and replace <br/> with space before extracting text
                    em_html = str(em_tag)
                    em_html = re.sub(r'<br\s*/?>', ' ', em_html)
                    # Now create new soup and get text
                    em_soup = BeautifulSoup(em_html, 'html.parser')
                    date_text = em_soup.get_text()
                    # Normalize whitespace
                    date_text = ' '.join(date_text.split())

                    # Parse the date
                    date_obj = self._parse_date(date_text)
                    if date_obj:
                        collections.append({
                            'date': date_obj.isoformat(),
                            'type': collection_type,
                            'source': 'east_devon_api'
                        })
                        logger.info(f"Found collection: {collection_type} on {date_obj.strftime('%A, %d %B %Y')}")

            return sorted(collections, key=lambda x: x['date']) or None

        except (AttributeError, TypeError) as e:
            logger.error(f"HTML parsing error: {e}")
            return None

    def _extract_collection_type(self, text: str) -> str:
        """Extract collection type from paragraph text"""
        text_lower = text.lower()

        if 'recycling and food waste' in text_lower:
            return 'Recycling & Food Waste'
        elif 'rubbish' in text_lower:
            return 'General Waste'
        elif 'green waste' in text_lower:
            return 'Garden Waste'
        else:
            return 'Collection'

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse date from East Devon format

        Args:
            date_text: Date string like "Thursday 25 September 2025"

        Returns:
            datetime object or None
        """
        try:
            # Clean the text
            date_text = date_text.strip()

            # East Devon format: "Thursday 25 September 2025"
            # Remove day name if present
            parts = date_text.split()
            if len(parts) >= 3:
                # Try to find the date part (skip day name)
                for i in range(len(parts) - 2):
                    date_part = ' '.join(parts[i:i+3])
                    try:
                        # Try parsing as "25 September 2025"
                        return datetime.strptime(date_part, '%d %B %Y')
                    except ValueError:
                        continue

            # Try other common formats
            date_formats = [
                '%A %d %B %Y',     # Thursday 25 September 2025
                '%d %B %Y',        # 25 September 2025
                '%d %b %Y',        # 25 Sep 2025
                '%A %d %b %Y',     # Thursday 25 Sep 2025
                '%d/%m/%Y',        # 25/09/2025
                '%d-%m-%Y',        # 25-09-2025
            ]

            for fmt in date_formats:
                try:
                    return datetime.strptime(date_text, fmt)
                except ValueError:
                    continue

            logger.warning(f"Could not parse date: '{date_text}'")
            return None

        except (TypeError, ValueError) as e:
            logger.warning(f"Date parsing error for '{date_text}': {e}")
            return None

    def save_to_file(self, filename: str = 'waste_collections.json'):
        """Save collection data to a JSON file"""
        collections = self.fetch_data()

        output_data = {
            'uprn': self.uprn,
            'postcode': self.postcode,
            'last_updated': datetime.now().isoformat(),
            'collections': collections
        }

        try:
            with open(filename, 'w') as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"Data saved to {filename}")
        except OSError as e:
            logger.error(f"Error saving to file: {e}")

def main():
    """Main function to run the waste collection fetcher"""
    # Load location data from config file
    UPRN = config.get('locations.uprn')
    POSTCODE = config.get('locations.postcode')

    if not UPRN or not POSTCODE:
        logger.error("Error: UPRN and postcode not found in configuration.")
        logger.error("Please add your location data to the config file under locations")
        exit(1)

    logger.info("East Devon District Council Waste Collection Fetcher")
    logger.info("=" * 50)
    logger.info(f"UPRN: {UPRN}")
    logger.info(f"Postcode: {POSTCODE}")
    logger.info("")

    # Create collector instance
    collector = EastDevonWasteCollector(uprn=UPRN, postcode=POSTCODE)

    try:
        logger.info("Fetching waste collection schedule...")
        collections = collector.fetch_data()

        if not collections:
            logger.info("No collection data found.")
            logger.info("\nTroubleshooting:")
            logger.info("1. Check that your UPRN and postcode are correct")
            logger.info("2. Verify the East Devon website is accessible")
            logger.info("3. The website structure may have changed")
            return

        logger.info(f"Found {len(collections)} scheduled collections")
        logger.info("")

        # Display all collections with days until each
        logger.info("Upcoming collections:")
        logger.info("-" * 30)
        today = datetime.now().date()
        for collection in collections:
            try:
                date_obj = datetime.fromisoformat(collection['date'])
                formatted_date = date_obj.strftime('%A, %d %B %Y')
                days_until = (date_obj.date() - today).days

                if days_until == 0:
                    day_text = "(TODAY)"
                elif days_until == 1:
                    day_text = "(TOMORROW)"
                else:
                    day_text = f"(in {days_until} days)"

                logger.info(f"{formatted_date} {day_text} - {collection['type']}")
            except (KeyError, TypeError, ValueError):
                if isinstance(collection, dict):
                    logger.info(f"{collection.get('date', 'Unknown date')} - {collection.get('type', 'Unknown collection')}")
                else:
                    logger.warning(f"Skipping malformed collection row: {collection!r}")

        # Save to file
        collector.save_to_file()
        logger.info(f"\nCollection data saved to waste_collections.json")

    except KeyboardInterrupt:
        logger.info("\n\nCancelled by user")
    except (OSError, RuntimeError, ValueError) as e:
        logger.error(f"\nError: {e}")
        logger.exception("Unexpected error occurred")

if __name__ == "__main__":
    main()
