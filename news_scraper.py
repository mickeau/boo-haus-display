#!/usr/bin/env python3
"""
Refactored Combined News RSS Feed Scraper
Modular architecture with fixed date handling and digest detection
"""

try:
    import feedparser
except ImportError:
    feedparser = None
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional
from types import SimpleNamespace
from email.utils import parsedate_to_datetime
import time
import logging
import os

# Import our modules
from base_fetcher import http_get
from news_config import SCRAPER_CONFIG, SITES_CONFIG, DATE_PATTERNS, UNWANTED_ELEMENTS, LOGGING_CONFIG
from config import config as app_config
from date_handler import DateHandler
from digest_detector import DigestDetectorFactory
from digest_parsers import DigestParserFactory
from news_models import normalize_story, sort_stories, story_identity

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format']
)
logger = logging.getLogger(__name__)


class ArticleScraper:
    """Handles scraping of individual article content and metadata"""

    def __init__(self, session, date_handler: DateHandler):
        self.session = session
        self.date_handler = date_handler

    def extract_publish_date_from_rss(self, entry) -> Optional[str]:
        """Extract publish date from RSS entry"""
        date_fields = ['published', 'updated', 'created']

        for field in date_fields:
            if hasattr(entry, field):
                try:
                    date_str = getattr(entry, field)
                    if date_str:
                        # Try parsed time tuple first
                        if hasattr(entry, f"{field}_parsed") and getattr(entry, f"{field}_parsed"):
                            time_tuple = getattr(entry, f"{field}_parsed")
                            dt = datetime(*time_tuple[:6])
                            # Make timezone aware
                            from datetime import timezone
                            dt = dt.replace(tzinfo=timezone.utc)
                            return dt.isoformat()

                        # Try ISO parsing
                        dt = self.date_handler.parse_iso_date(date_str)
                        if dt:
                            return dt.isoformat()

                        # Try standard RSS/RFC 822 dates, e.g. Mon, 07 Sep 2026 10:04:14 +0000
                        try:
                            dt = parsedate_to_datetime(date_str)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            return dt.isoformat()
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Could not parse {field} date '{date_str}': {e}")
                    continue

        return None

    def extract_publish_date_from_article(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract publish date from article page"""
        # Check meta tags first
        for selector in DATE_PATTERNS['meta_selectors']:
            meta_tag = soup.select_one(selector)
            if meta_tag:
                content = meta_tag.get('content')
                if content:
                    dt = self.date_handler.parse_iso_date(content)
                    if dt:
                        return dt.isoformat()

        # Check HTML elements
        for selector in DATE_PATTERNS['html_selectors']:
            date_element = soup.select_one(selector)
            if date_element:
                # Try datetime attribute
                datetime_attr = date_element.get('datetime')
                if datetime_attr:
                    dt = self.date_handler.parse_iso_date(datetime_attr)
                    if dt:
                        return dt.isoformat()

                # Try parsing text content
                date_text = date_element.get_text(strip=True)
                if date_text:
                    dt = self._parse_date_from_text(date_text)
                    if dt:
                        return dt.isoformat()

        return None

    def _parse_date_from_text(self, date_text: str) -> Optional[datetime]:
        """Parse date from text using various patterns"""
        for pattern in DATE_PATTERNS['regex_patterns']:
            match = re.search(pattern, date_text)
            if match:
                date_str = match.group()

                # Try different format parsers
                if 'T' in date_str:
                    return self.date_handler.parse_date_string(
                        date_str,
                        DATE_PATTERNS['strptime_formats']['iso_with_time']
                    )
                elif '/' in date_str:
                    return self.date_handler.parse_date_string(
                        date_str,
                        DATE_PATTERNS['strptime_formats']['us_slash']
                    )
                elif ',' in date_str:
                    return self.date_handler.parse_date_string(
                        date_str,
                        DATE_PATTERNS['strptime_formats']['month_name_comma']
                    )
                elif ' ' in date_str and ',' not in date_str:
                    return self.date_handler.parse_date_string(
                        date_str,
                        DATE_PATTERNS['strptime_formats']['day_month_name']
                    )
                else:
                    dt = self.date_handler.parse_iso_date(date_str)
                    if dt:
                        return dt

        return None

    @staticmethod
    def _dedupe_text_blocks(text_blocks: List[str]) -> List[str]:
        """Remove duplicate text blocks while preserving order."""
        deduped = []
        seen = set()
        for text in text_blocks:
            normalized = re.sub(r'\s+', ' ', text).strip()
            if not normalized:
                continue

            key = normalized.lower()
            if key in seen:
                continue

            seen.add(key)
            deduped.append(normalized)

        return deduped

    def _extract_text_from_element(self, element) -> str:
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in element.find_all('p')
            if p.get_text(strip=True)
        ]
        if paragraphs:
            return ' '.join(self._dedupe_text_blocks(paragraphs))

        return re.sub(r'\s+', ' ', element.get_text(separator=' ', strip=True)).strip()

    def scrape_article_content(self, url: str, site_name: str) -> tuple[str, Optional[str]]:
        """Scrape full content and date from article URL"""
        try:
            logger.info(f"Scraping article content from {url}")
            response = http_get(
                url,
                timeout=SCRAPER_CONFIG['request_timeout'],
                session=self.session,
                description=f"{site_name} article",
            )
            if response is None:
                return "", None

            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove unwanted elements
            for element in soup(UNWANTED_ELEMENTS):
                element.decompose()

            # Extract publish date
            publish_date = self.extract_publish_date_from_article(soup, url)

            # Extract content using site-specific selectors
            site_config = SITES_CONFIG.get(site_name, {})
            content_selectors = site_config.get('content_selectors', [])

            content = ""
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    # Remove nested unwanted elements
                    for unwanted in content_element(UNWANTED_ELEMENTS):
                        unwanted.decompose()

                    content = self._extract_text_from_element(content_element)
                    if len(content) > 100:
                        break

            # Fallback: get all paragraph text
            if not content or len(content) < 100:
                paragraphs = [
                    p.get_text(" ", strip=True)
                    for p in soup.find_all('p')
                    if p.get_text(strip=True)
                ]
                content = ' '.join(self._dedupe_text_blocks(paragraphs))

            return content, publish_date

        except Exception as e:
            logger.error(f"Error scraping article content from {url}: {e}")
            return "", None


class CombinedNewsRSSScraper:
    """Main scraper orchestrator"""

    def __init__(self):
        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': SCRAPER_CONFIG['user_agent']
        })

        # Initialize utilities
        self.date_handler = DateHandler(
            recent_days=SCRAPER_CONFIG['article_recent_days'],
            cleanup_days=SCRAPER_CONFIG['cleanup_threshold_days']
        )
        self.article_scraper = ArticleScraper(self.session, self.date_handler)

        # Initialize site-specific components
        self.digest_detectors = {}
        self.digest_parsers = {}

        for site_name, site_config in SITES_CONFIG.items():
            self.digest_detectors[site_name] = DigestDetectorFactory.create(
                site_name, site_config
            )
            self.digest_parsers[site_name] = DigestParserFactory.create(
                site_name, self.session, site_config, self.date_handler
            )

    @staticmethod
    def normalize_article(article: Dict) -> Dict:
        """Convert regular and digest items into one story database shape."""
        return normalize_story(article)

    @staticmethod
    def sort_articles(articles: List[Dict]) -> List[Dict]:
        """Return articles newest-first using canonical publish fields."""
        return sort_stories(articles)

    def fetch_rss_feed(self, rss_url: str):
        """Fetch and parse RSS feed"""
        try:
            logger.info(f"Fetching RSS feed from {rss_url}")
            response = http_get(
                rss_url,
                timeout=SCRAPER_CONFIG['request_timeout'],
                session=self.session,
                description="RSS feed",
            )
            if response is None:
                return None

            if feedparser is None:
                return self.parse_rss_feed_without_feedparser(response.content)

            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"RSS feed has parsing errors: {feed.bozo_exception}")

            logger.info(f"Found {len(feed.entries)} entries in RSS feed")
            return feed
        except Exception as e:
            logger.error(f"Error fetching RSS feed: {e}")
            return None

    def fetch_rss_feed_without_feedparser(self, rss_url: str):
        """Minimal RSS/Atom parser used when feedparser is not installed."""
        response = http_get(
            rss_url,
            timeout=SCRAPER_CONFIG['request_timeout'],
            session=self.session,
            description="RSS feed",
        )
        if response is None:
            return None

        return self.parse_rss_feed_without_feedparser(response.content)

    def parse_rss_feed_without_feedparser(self, content):
        """Minimal RSS/Atom parser for already-fetched feed content."""
        soup = BeautifulSoup(content, 'xml')
        items = soup.find_all('item') or soup.find_all('entry')
        entries = []

        for item in items:
            title = self._find_feed_text(item, ['title'])
            link = self._find_feed_link(item)
            published = self._find_feed_text(item, ['pubDate', 'published', 'updated'])
            summary = self._find_feed_text(item, ['description', 'summary'])
            content = self._find_feed_text(item, ['content:encoded', 'encoded'])

            if not title or not link:
                continue

            entries.append(SimpleNamespace(
                title=title,
                link=link,
                published=published,
                summary=summary,
                content=[SimpleNamespace(value=content)] if content else []
            ))

        logger.info(f"Found {len(entries)} entries in RSS feed")
        return SimpleNamespace(entries=entries, bozo=False)

    @staticmethod
    def _find_feed_text(item, tag_names: List[str]) -> str:
        for tag_name in tag_names:
            tag = item.find(tag_name)
            if tag and tag.get_text(strip=True):
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _find_feed_link(item) -> str:
        link = item.find('link')
        if not link:
            return ""
        return link.get('href') or link.get_text(strip=True)

    def scrape_site(self, site_name: str, process_digests: bool = True) -> List[Dict]:
        """Scrape articles from a specific site"""
        site_config = SITES_CONFIG[site_name]
        feed = self.fetch_rss_feed(site_config['rss_url'])
        if not feed:
            return []

        articles = []
        digest_detector = self.digest_detectors[site_name]
        digest_parser = self.digest_parsers[site_name]

        for entry in feed.entries:
            try:
                title = entry.title
                url = entry.link

                logger.info(f"\n{'='*60}")
                logger.info(f"Processing {site_name}: {title}")
                logger.info(f"URL: {url}")

                # Check if this is a digest article
                is_digest = digest_detector.is_digest(title, url)

                if is_digest:
                    logger.info(f"→ Identified as DIGEST article")
                    if process_digests:
                        # Extract individual stories from digest
                        digest_stories = digest_parser.extract_digest_stories(url)

                        # Use the RSS entry date for all stories in this digest
                        # This makes sense because the RSS feed is showing this digest recently
                        rss_publish_date = self.article_scraper.extract_publish_date_from_rss(entry)

                        if not rss_publish_date:
                            # Fallback to current date if no RSS date available
                            rss_publish_date = self.date_handler.get_current_iso_date()
                            logger.info(f"No RSS date found, using current date: {rss_publish_date}")
                        else:
                            logger.info(f"Using RSS entry date for digest stories: {rss_publish_date}")

                        # Override the scraped article date with RSS entry date
                        for story in digest_stories:
                            story['original_digest_date'] = story.get('publish_date')  # Keep original for reference
                            story['publish_date'] = rss_publish_date  # Use RSS date

                        # Filter stories by date (using RSS entry date)
                        recent_stories = []
                        for story in digest_stories:
                            if self.date_handler.is_recent(story.get('publish_date')):
                                recent_stories.append(self.normalize_article(story))
                            else:
                                logger.debug(f"Skipping old digest story: {story['title']}")

                        articles.extend(recent_stories)
                        logger.info(f"✓ Added {len(recent_stories)}/{len(digest_stories)} recent stories from digest")
                    else:
                        logger.info(f"Skipping digest article (process_digests=False)")
                    continue

                # Process regular article
                logger.info(f"→ Processing as REGULAR article")
                publish_date = self.article_scraper.extract_publish_date_from_rss(entry)

                if publish_date:
                    logger.info(f"RSS date: {publish_date}")

                # Check if article is recent enough
                if not self.date_handler.is_recent(publish_date):
                    logger.info(f"✗ Skipping - article is too old (before {self.date_handler.get_cutoff_date_str()})")
                    continue

                # Get RSS content
                rss_content = ""
                if hasattr(entry, 'content') and entry.content:
                    rss_content = BeautifulSoup(entry.content[0].value, 'html.parser').get_text(strip=True)
                elif hasattr(entry, 'summary') and entry.summary:
                    rss_content = BeautifulSoup(entry.summary, 'html.parser').get_text(strip=True)

                # Scrape full content from article page
                full_content, article_date = self.article_scraper.scrape_article_content(url, site_name)

                # Use article date if RSS date not available
                if not publish_date and article_date:
                    publish_date = article_date
                    logger.info(f"Using scraped date: {publish_date}")

                # Check again with scraped date
                if not self.date_handler.is_recent(publish_date):
                    logger.info(f"✗ Skipping - article is too old after scraping (before {self.date_handler.get_cutoff_date_str()})")
                    continue

                # Use full content if available, otherwise fall back to RSS content
                content = full_content if full_content else rss_content

                # Skip weekly roundup/synopsis articles by checking content
                content_lower = content.lower()
                title_lower = title.lower()

                # Check for weekly retrospective indicators in title or content
                weekly_indicators = ['synopsis', 'roundup', 'round-up', 'round up']
                weekly_title_phrases = ['great week', 'good week', 'this week', 'the week']

                is_weekly_roundup = (
                    # Original check: "last week" + roundup words in content
                    ('last week' in content_lower and any(word in content_lower for word in weekly_indicators)) or
                    # New check: weekly phrases in title
                    any(phrase in title_lower for phrase in weekly_title_phrases) or
                    # New check: weekly URL pattern
                    any(phrase in url.lower() for phrase in ['week-for', 'weekly', 'this-week'])
                )

                if is_weekly_roundup:
                    logger.info(f"✗ Skipping weekly roundup/retrospective article: {title}")
                    continue

                # Skip if content is too short (likely video stories)
                if len(content) < 300:
                    logger.info(f"✗ Skipping short article (likely video): {title} ({len(content)} chars)")
                    continue

                article = {
                    "title": title,
                    "url": url,
                    "content": content,
                    "publish_date": publish_date,
                    "source_type": "regular_article",
                    "source_site": site_name
                }

                articles.append(self.normalize_article(article))
                logger.info(f"✓ Added regular article ({len(content)} chars)")

                # Be respectful with requests
                time.sleep(SCRAPER_CONFIG['request_delay'])

            except Exception as e:
                logger.error(f"Error processing {site_name} article '{entry.title}': {e}", exc_info=True)
                continue

        return articles

    def scrape_all_sites(self, process_digests: bool = True) -> List[Dict]:
        """Scrape articles from all configured sites"""
        all_articles = []

        for site_name in SITES_CONFIG.keys():
            logger.info(f"\n{'#'*60}")
            logger.info(f"# Starting scrape of {site_name}")
            logger.info(f"{'#'*60}")
            site_articles = self.scrape_site(site_name, process_digests)
            all_articles.extend(site_articles)
            logger.info(f"\n✓ Completed {site_name}: {len(site_articles)} recent articles")

        return all_articles

    def load_existing_articles(self, filename: str) -> List[Dict]:
        """Load existing articles from JSON file and filter out old ones"""
        if not os.path.exists(filename):
            logger.info(f"No existing file found at {filename}")
            return []

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            existing_articles = data.get('stories') or data.get('articles', [])
            logger.info(f"Loaded {len(existing_articles)} existing articles")

            # Filter out articles older than threshold
            filtered_articles = []
            removed_count = 0

            for article in existing_articles:
                normalized = self.normalize_article(article)
                if not self.date_handler.is_too_old(normalized.get('publish_date')):
                    filtered_articles.append(normalized)
                else:
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Removed {removed_count} articles older than {self.date_handler.get_cleanup_threshold_str()}")

            return filtered_articles

        except Exception as e:
            logger.error(f"Error loading existing articles: {e}")
            return []

    def merge_articles(self, existing_articles: List[Dict], new_articles: List[Dict]) -> List[Dict]:
        """Merge new articles with existing ones, avoiding duplicates"""
        existing_ids = {
            story_identity(a)
            for a in existing_articles
        }

        merged = existing_articles.copy()
        added_count = 0

        for article in new_articles:
            article = self.normalize_article(article)
            article_id = article.get('story_id')
            if article_id not in existing_ids:
                merged.append(article)
                existing_ids.add(article_id)
                added_count += 1

        logger.info(f"Added {added_count} new unique articles")
        return self.sort_articles(merged)

    def save_to_json(self, articles: List[Dict], filename: str):
        """Save articles to JSON file with metadata"""
        try:
            # Calculate statistics
            by_site = {}
            by_type = {}

            articles = self.sort_articles(articles)

            for article in articles:
                site = article.get('source_site', 'unknown')
                article_type = article.get('source_type', 'unknown')

                by_site[site] = by_site.get(site, 0) + 1
                by_type[article_type] = by_type.get(article_type, 0) + 1

            output_data = {
                "extraction_metadata": {
                    "extracted_at": self.date_handler.get_current_iso_date(),
                    "date_filter": f"Last {SCRAPER_CONFIG['article_recent_days']} days (since {self.date_handler.get_cutoff_date_str()})",
                    "cleanup_threshold": f"Removed articles older than {self.date_handler.get_cleanup_threshold_str()}",
                    "total_articles": len(articles),
                    "by_site": by_site,
                    "by_type": by_type,
                    "sites_scraped": list(SITES_CONFIG.keys())
                },
                "stories": articles,
                "articles": articles
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logger.info(f"\n✓ Saved {len(articles)} total articles to {filename}")
            for site, count in by_site.items():
                logger.info(f"  - {site}: {count} articles")

        except Exception as e:
            logger.error(f"Error saving to JSON: {e}")


def main():
    """Main entry point"""
    scraper = CombinedNewsRSSScraper()

    print("\n" + "="*60)
    print("COMBINED NEWS SCRAPER - REFACTORED")
    print("="*60)
    print(f"Filtering: Articles from last {SCRAPER_CONFIG['article_recent_days']} days")
    print(f"           (since {scraper.date_handler.get_cutoff_date_str()})")
    print(f"Cleanup:   Removing articles older than {SCRAPER_CONFIG['cleanup_threshold_days']} days")
    print(f"           (before {scraper.date_handler.get_cleanup_threshold_str()})")
    print("="*60 + "\n")

    # Load existing articles and clean up old ones
    filename = app_config.runtime_path('screens.news.raw_story_file', SCRAPER_CONFIG['output_filename'])
    existing_articles = scraper.load_existing_articles(filename)

    # Scrape new articles
    new_articles = scraper.scrape_all_sites(process_digests=True)

    # Merge with existing articles
    all_articles = scraper.merge_articles(existing_articles, new_articles)

    # Save to JSON
    scraper.save_to_json(all_articles, filename)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total articles in database: {len(all_articles)}")
    print(f"  - Kept from previous run: {len(existing_articles)}")
    print(f"  - Added new: {len(all_articles) - len(existing_articles)}")

    # Statistics
    by_site = {}
    by_type = {}
    for article in all_articles:
        site = article.get('source_site', 'unknown')
        article_type = article.get('source_type', 'unknown')
        by_site[site] = by_site.get(site, 0) + 1
        by_type[article_type] = by_type.get(article_type, 0) + 1

    print(f"\nBy site:")
    for site, count in by_site.items():
        print(f"  - {site.replace('_', ' ').title()}: {count}")

    print(f"\nBy type:")
    for article_type, count in by_type.items():
        print(f"  - {article_type.replace('_', ' ').title()}: {count}")

    # Sample headlines
    if all_articles:
        print(f"\nSample recent headlines:")
        for article in all_articles[:5]:
            site = article.get('source_site', '').replace('_', ' ').title()
            article_type = article.get('source_type', '')
            type_badge = "[DIGEST]" if article_type == "digest_story" else "[ARTICLE]"
            print(f"  {type_badge} [{site}] {article['title'][:70]}...")

    print("\n" + "="*60)
    print("✓ Scraping complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
