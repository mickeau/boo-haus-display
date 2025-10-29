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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EastDevonWasteCollector:
    def __init__(self, uprn: str, postcode: str):
        """
        Initialize the waste collector
        
        Args:
            uprn: Your Unique Property Reference Number
            postcode: Your postcode for address search
        """
        self.uprn = uprn
        self.postcode = postcode
        self.base_url = "https://eastdevon.gov.uk"
        self.session = requests.Session()
        self._collections_cache = None  # Cache the collections to avoid multiple API calls
        
        # Set headers to match browser request
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://eastdevon.gov.uk/recycling-and-waste/recycling-waste-information/when-is-my-bin-collected/'
        })

    def fetch_collection_schedule(self) -> List[Dict]:
        """
        Fetch the waste collection schedule (cached after first call)
        
        Returns:
            List of collection events with dates and types
        """
        # Return cached results if available
        if self._collections_cache is not None:
            return self._collections_cache
            
        try:
            # Call the addressfinder API
            search_url = f"{self.base_url}/addressfinder"
            params = {
                'qtype': 'bins',
                'term': self.postcode.lower()
            }
            
            logger.info(f"Searching for addresses with postcode: {self.postcode}")
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            
            # Parse the JSON response
            addresses = response.json()
            logger.info(f"Found {len(addresses)} addresses")
            
            # Find the address matching our UPRN
            target_address = None
            for address in addresses:
                if str(address.get('UPRN', '')) == str(self.uprn):
                    target_address = address
                    logger.info(f"Found matching address: {address['label']}")
                    break
            
            if not target_address:
                logger.error(f"No address found with UPRN {self.uprn}")
                self._collections_cache = []
                return []
            
            # Parse the HTML Results field
            html_results = target_address.get('Results', '')
            if not html_results:
                logger.error("No Results field found in address data")
                self._collections_cache = []
                return []
            
            # Cache and return the results
            self._collections_cache = self._parse_collection_html(html_results)
            return self._collections_cache
            
        except requests.RequestException as e:
            logger.error(f"Network error: {e}")
            self._collections_cache = []
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            self._collections_cache = []
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self._collections_cache = []
            return []

    def _parse_collection_html(self, html_content: str) -> List[Dict]:
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
            
            return sorted(collections, key=lambda x: x['date'])
            
        except Exception as e:
            logger.error(f"HTML parsing error: {e}")
            return []

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
            
        except Exception as e:
            logger.warning(f"Date parsing error for '{date_text}': {e}")
            return None

    def save_to_file(self, filename: str = 'waste_collections.json'):
        """Save collection data to a JSON file"""
        collections = self.fetch_collection_schedule()
        
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
        except Exception as e:
            logger.error(f"Error saving to file: {e}")

def main():
    """Main function to run the waste collection fetcher"""
    import json

    # Load location data from config file
    try:
        with open('boo_haus_config.json', 'r') as f:
            config = json.load(f)
        UPRN = config.get('locations', {}).get('uprn')
        POSTCODE = config.get('locations', {}).get('postcode')

        if not UPRN or not POSTCODE:
            print("Error: UPRN and postcode not found in boo_haus_config.json")
            print("Please add your location data to the config file under locations")
            exit(1)
    except FileNotFoundError:
        print("Error: boo_haus_config.json not found")
        print("Please create config file from boo_haus_config.example.json")
        exit(1)

    print("East Devon District Council Waste Collection Fetcher")
    print("=" * 50)
    print(f"UPRN: {UPRN}")
    print(f"Postcode: {POSTCODE}")
    print()

    # Create collector instance
    collector = EastDevonWasteCollector(uprn=UPRN, postcode=POSTCODE)
    
    try:
        print("Fetching waste collection schedule...")
        collections = collector.fetch_collection_schedule()
        
        if not collections:
            print("No collection data found.")
            print("\nTroubleshooting:")
            print("1. Check that your UPRN and postcode are correct")
            print("2. Verify the East Devon website is accessible")
            print("3. The website structure may have changed")
            return
        
        print(f"Found {len(collections)} scheduled collections")
        print()
        
        # Display all collections with days until each
        print("Upcoming collections:")
        print("-" * 30)
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
                
                print(f"{formatted_date} {day_text} - {collection['type']}")
            except:
                print(f"{collection['date']} - {collection['type']}")
        
        # Save to file
        collector.save_to_file()
        print(f"\nCollection data saved to waste_collections.json")
        
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
        logger.exception("Unexpected error occurred")

if __name__ == "__main__":
    main()