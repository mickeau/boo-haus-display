#!/usr/bin/env python3
"""
Inspect RSS entry dates for configured news sources.

Examples:
    python3 check_rss_dates.py
    python3 check_rss_dates.py --source positive_news --days 7
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from base_fetcher import http_get_text
from news_config import SCRAPER_CONFIG, SITES_CONFIG


try:
    import feedparser
except ImportError:
    feedparser = None


def parse_entry_datetime(entry):
    """Return the best parsed datetime for a feed entry, or None."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


def entry_date_label(entry, dt):
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M")

    return (
        getattr(entry, "published", None)
        or getattr(entry, "updated", None)
        or "NO DATE"
    )


def check_feed(source_name, source_config, days):
    rss_url = source_config.get("rss_url")
    print("\n" + "=" * 70)
    print(f"Checking: {source_name}")
    print(f"URL: {rss_url}")
    print("=" * 70)

    if not rss_url:
        print("No rss_url configured for this source.")
        return False

    feed_text = http_get_text(rss_url, timeout=SCRAPER_CONFIG["request_timeout"])
    if feed_text is None:
        print("Could not fetch RSS feed. Network may be disabled or the source failed.")
        return False

    feed = feedparser.parse(feed_text)
    entries = getattr(feed, "entries", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"\nTotal entries in feed: {len(entries)}")
    print(f"{days}-day cutoff date: {cutoff.date()}")
    print("\nAll entries with dates:")
    print("-" * 70)

    recent_count = 0
    for index, entry in enumerate(entries, 1):
        title = getattr(entry, "title", "(untitled)")
        title = title[:60] + "..." if len(title) > 60 else title

        dt = parse_entry_datetime(entry)
        is_recent = bool(dt and dt >= cutoff)
        if is_recent:
            recent_count += 1

        status = "RECENT" if is_recent else "OLD"
        print(f"{index:2d}. [{status}] {entry_date_label(entry, dt)} | {title}")

    print("-" * 70)
    print(f"Summary: {recent_count} recent entries in last {days} days out of {len(entries)} total")
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect configured RSS feed dates")
    parser.add_argument(
        "--source",
        choices=sorted(SITES_CONFIG.keys()),
        help="Specific configured source to inspect; defaults to all sources",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=SCRAPER_CONFIG["article_recent_days"],
        help="Recent cutoff window in days",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if feedparser is None:
        print("feedparser is not installed. Install with: pip3 install feedparser")
        return 1

    days = max(1, args.days)
    sources = (
        {args.source: SITES_CONFIG[args.source]}
        if args.source
        else SITES_CONFIG
    )

    successes = 0
    for source_name, source_config in sources.items():
        if check_feed(source_name, source_config, days):
            successes += 1

    print("\n" + "=" * 70)
    print(f"Analysis complete. Checked {successes}/{len(sources)} feeds.")
    print("=" * 70)
    return 0 if successes else 1


if __name__ == "__main__":
    sys.exit(main())
