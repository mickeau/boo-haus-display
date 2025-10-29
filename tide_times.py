#!/usr/bin/env python3
"""
Simple script to scrape tide times for Exmouth from BBC Weather
and display today's high and low tides.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime

def get_tide_data():
    """Scrape tide data from BBC Weather HTML tables."""
    url = "https://www.bbc.co.uk/weather/coast-and-sea/tide-tables/10/27"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the first table (today's tides)
        tables = soup.find_all('table')
        if not tables:
            print("No tide tables found on the page")
            return []
        
        table = tables[0]  # First table is today's data
        rows = table.find_all('tr')[1:]  # Skip header row
        
        tides = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                # Extract data: [Type, Time, Height]
                tide_type = cells[0].get_text().strip()    # 'High' or 'Low'
                time_str = cells[1].get_text().strip()     # '09:40'
                height_str = cells[2].get_text().strip()   # '3.7'
                
                try:
                    # Parse time
                    tide_time = datetime.strptime(time_str, '%H:%M').time()
                    # Parse height (convert string to float)
                    height = float(height_str)
                    
                    tides.append({
                        'time': tide_time,
                        'type': tide_type,
                        'height': height
                    })
                except ValueError as e:
                    print(f"Warning: Could not parse tide data - {e}")
                    continue
        
        return tides
        
    except Exception as e:
        print(f"Error fetching tide data: {e}")
        return []

def display_results(tides):
    """Display the tide times."""
    today = datetime.now().strftime('%A, %B %d, %Y')
    
    print(f"\n🌊 Exmouth Tide Times - {today}")
    print("=" * 40)
    
    if not tides:
        print("No tide data found for today.")
        return
    
    # Sort tides by time
    sorted_tides = sorted(tides, key=lambda x: x['time'])
    
    for tide in sorted_tides:
        tide_icon = "⬆️" if tide['type'] == 'High' else "⬇️"
        print(f"{tide_icon} {tide['type']} tide at {tide['time'].strftime('%H:%M')} ({tide['height']:.1f}m)")

def main():
    """Main function."""
    print("Fetching today's tide times for Exmouth from BBC Weather...")
    
    try:
        # Get today's tide data
        tides = get_tide_data()
        
        if tides:
            print(f"Found {len(tides)} tide times for today")
        else:
            print("No tide data found")
            return
        
        # Display results
        display_results(tides)
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("BBC Exmouth Tide Times Scraper")
    print("Required: pip install requests beautifulsoup4")
    print()
    main()