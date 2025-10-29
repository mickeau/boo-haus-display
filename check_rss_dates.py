#!/usr/bin/env python3
"""
Check what dates are actually in the RSS feeds
"""

import feedparser
from datetime import datetime, timezone, timedelta

def check_feed(name, url):
    print(f"\n{'='*70}")
    print(f"Checking: {name}")
    print(f"URL: {url}")
    print('='*70)
    
    feed = feedparser.parse(url)
    
    print(f"\nTotal entries in feed: {len(feed.entries)}")
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    print(f"2-day cutoff date: {cutoff.date()}")
    
    print(f"\nAll entries with dates:")
    print("-" * 70)
    
    recent_count = 0
    for i, entry in enumerate(feed.entries, 1):
        title = entry.title[:60] + '...' if len(entry.title) > 60 else entry.title
        
        # Try to get date
        date_str = None
        if hasattr(entry, 'published'):
            date_str = entry.published
        elif hasattr(entry, 'updated'):
            date_str = entry.updated
        
        # Parse date
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            date_display = dt.strftime('%Y-%m-%d %H:%M')
            is_recent = dt >= cutoff
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            date_display = dt.strftime('%Y-%m-%d %H:%M')
            is_recent = dt >= cutoff
        else:
            date_display = "NO DATE"
            is_recent = False
        
        status = "✓ RECENT" if is_recent else "✗ OLD"
        if is_recent:
            recent_count += 1
        
        print(f"{i:2d}. [{status}] {date_display} | {title}")
    
    print("-" * 70)
    print(f"\nSummary: {recent_count} recent entries (last 2 days) out of {len(feed.entries)} total")

# Check both feeds
check_feed(
    "Only Good News Daily",
    "https://www.onlygoodnewsdaily.com/blog-feed.xml"
)

check_feed(
    "Positive News",
    "https://positive.news/feed"
)

print("\n" + "="*70)
print("Analysis complete!")
print("="*70)