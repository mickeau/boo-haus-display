#!/usr/bin/env python3
"""
News Headline Summarizer
Uses Claude API to generate concise headline summaries for e-ink display
Implements daily caching to minimize API calls and proper rate limiting
Automatically cleans up summaries older than 7 days

Daily Workflow:

Run the combined scraper to get recent articles
Run the summarizer - it will use cache for existing content and API for new articles
Use the summaries JSON for your e-ink display
Next day: cache automatically refreshes for truly new content

The system is designed to minimize API costs while ensuring you always have fresh, high-quality summaries for your e-ink display!
"""

import json
import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from pathlib import Path

from config import config
from news_models import normalize_story, parse_story_datetime, sort_stories, story_identity

try:
    import anthropic
except ImportError:
    anthropic = None

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HeadlineSummarizer:
    def __init__(self, api_key: str, cache_file: str = "headline_summaries_cache.json", requests_per_minute: int = 50):
        """
        Initialize the headline summarizer

        Args:
            api_key: Claude API key
            cache_file: Path to cache file for storing summaries
            requests_per_minute: API rate limit (varies by account type)
        """
        if anthropic is None:
            raise RuntimeError("The anthropic package is not installed; install it or disable news_summariser_enabled.")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.cache_file = cache_file
        self.cache_data = self._load_cache()

        # Rate limiting settings - configurable based on your account
        self.requests_per_minute = requests_per_minute
        self.request_delay = 60 / self.requests_per_minute + 0.2  # Add 0.2s buffer for safety
        logger.info(f"Rate limit: {self.requests_per_minute} requests/minute, using {self.request_delay:.1f}s delay between requests")

        # Cleanup threshold (7 days)
        self.cleanup_threshold = datetime.now() - timedelta(days=3)

        # Summary prompt template
        self.summary_prompt = """Please create a concise, informative headline summary of 20-30 words for this news story. The summary should capture all essential information since it will be displayed on an e-ink screen without clickable links.

Make the headline:
- Complete and self-contained (no need to click for key info)
- Specific with concrete details (numbers, locations, names when relevant)
- Clear and engaging
- Between 20-30 words exactly

Original headline: {title}

Story content: {content}

Generate only the summary headline, nothing else:"""

    def _load_cache(self) -> Dict:
        """Load existing cache data"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                if not isinstance(cache, dict):
                    logger.warning(f"Cache file {self.cache_file} does not contain an object; starting empty")
                    return self._create_empty_cache()
                summaries = cache.get('summaries', {})
                if not isinstance(summaries, dict):
                    logger.warning(f"Cache file {self.cache_file} has malformed summaries; starting empty")
                    return self._create_empty_cache()
                logger.info(f"Loaded cache with {len(summaries)} existing summaries")
                return cache
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error loading cache: {e}")
                return self._create_empty_cache()
        else:
            logger.info("No existing cache found, creating new cache")
            return self._create_empty_cache()

    def _create_empty_cache(self) -> Dict:
        """Create empty cache structure"""
        return {
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "cache_stats": {
                "total_summaries": 0,
                "api_calls_saved": 0,
                "last_refresh_date": None
            },
            "summaries": {}
        }

    def _cleanup_old_cache_entries(self):
        """Remove cache entries older than 7 days"""
        if "summaries" not in self.cache_data:
            return

        old_count = len(self.cache_data["summaries"])
        summaries_to_keep = {}
        removed_count = 0

        for content_hash, entry in self.cache_data["summaries"].items():
            try:
                if not isinstance(entry, dict):
                    raise TypeError("cache entry is not an object")
                generated_at = datetime.fromisoformat(entry["generated_at"])
                if generated_at >= self.cleanup_threshold:
                    summaries_to_keep[content_hash] = entry
                else:
                    removed_count += 1
            except (KeyError, TypeError, ValueError) as e:
                # Keep entries we can't parse the date for
                logger.debug(f"Could not parse date for cache entry, keeping it: {e}")
                summaries_to_keep[content_hash] = entry

        self.cache_data["summaries"] = summaries_to_keep

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} cache entries older than 7 days")
            self.cache_data["cache_stats"]["total_summaries"] = len(summaries_to_keep)

    def _save_cache(self):
        """Save cache data to file"""
        cache_path = Path(self.cache_file)
        tmp_file = cache_path.with_name(cache_path.name + '.tmp')
        try:
            self.cache_data["last_updated"] = datetime.now().isoformat()
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, cache_path)
            logger.info(f"Cache saved with {len(self.cache_data['summaries'])} summaries")
        except (OSError, TypeError, ValueError) as e:
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass
            logger.error(f"Error saving cache: {e}")

    def _generate_content_hash(self, title: str, content: str) -> str:
        """Generate a hash for the article content to use as cache key"""
        content_string = f"{title}|{content[:500]}"  # Use first 500 chars of content
        return hashlib.md5(content_string.encode('utf-8')).hexdigest()

    def _is_cache_fresh(self) -> bool:
        """Check if cache is from today (within last 24 hours)"""
        if not self.cache_data.get("cache_stats", {}).get("last_refresh_date"):
            return False

        try:
            last_refresh = datetime.fromisoformat(self.cache_data["cache_stats"]["last_refresh_date"])
            now = datetime.now(last_refresh.tzinfo) if last_refresh.tzinfo else datetime.now()
            return now - last_refresh < timedelta(hours=24)
        except (KeyError, TypeError, ValueError):
            return False

    def _should_use_cache(self, content_hash: str) -> bool:
        """Determine if we should use cached summary"""
        return content_hash in self.cache_data["summaries"]

    def _call_claude_api(self, title: str, content: str, max_retries: int = 3) -> str:
        """Call Claude API to generate summary with retry logic and fixed delay"""
        prompt = self.summary_prompt.format(title=title, content=content[:2000])  # Limit content length

        for attempt in range(max_retries):
            try:
                logger.info(f"Calling Claude API for: {title[:50]}... (attempt {attempt + 1})")

                response = self.client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=100,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                summary = response.content[0].text.strip()
                logger.info(f"Generated summary: {summary}")

                # Fixed delay after successful API call to respect rate limits
                logger.info(f"Waiting {self.request_delay:.1f}s before next request...")
                time.sleep(self.request_delay)

                return summary

            except anthropic.RateLimitError as e:
                wait_time = (attempt + 1) * 30  # Exponential backoff: 30, 60, 90 seconds
                logger.warning(f"Rate limit hit on attempt {attempt + 1}. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue

            except anthropic.APIError as e:
                logger.error(f"Claude API error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    break
                time.sleep(5)  # Brief wait before retry
                continue

            except (AttributeError, IndexError, TypeError, ValueError) as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    break
                time.sleep(5)
                continue

        # If all retries failed, create fallback
        logger.error(f"All API attempts failed for: {title[:50]}...")
        fallback = f"{title[:25]}..." if len(title) > 25 else title
        logger.info(f"Using fallback summary: {fallback}")
        return fallback

    def generate_summary(self, title: str, content: str, force_refresh: bool = False) -> str:
        """
        Generate or retrieve cached summary for an article

        Args:
            title: Article title
            content: Article content
            force_refresh: Force API call even if cached version exists

        Returns:
            Summary headline string
        """
        content_hash = self._generate_content_hash(title, content)

        # Check cache first (unless force refresh)
        if not force_refresh and self._should_use_cache(content_hash):
            cached_summary = self.cache_data["summaries"][content_hash]["summary"]
            self.cache_data["cache_stats"]["api_calls_saved"] += 1
            logger.info(f"Using cached summary for: {title[:50]}...")
            return cached_summary

        # Generate new summary via API
        summary = self._call_claude_api(title, content)

        # Store in cache
        self.cache_data["summaries"][content_hash] = {
            "original_title": title,
            "summary": summary,
            "generated_at": datetime.now().isoformat(),
            "content_preview": content[:200] + "..." if len(content) > 200 else content
        }

        # Update stats
        self.cache_data["cache_stats"]["total_summaries"] = len(self.cache_data["summaries"])
        self.cache_data["cache_stats"]["last_refresh_date"] = datetime.now().isoformat()

        # Save cache
        self._save_cache()

        return summary

    def is_article_too_old(self, publish_date_str: str) -> bool:
        """Check if article is older than 7 days"""
        if not publish_date_str:
            return False  # Keep articles without dates

        article_date = parse_story_datetime({'publish_date': publish_date_str})
        if article_date is None:
            logger.debug(f"Could not parse date {publish_date_str}")
            return False  # Keep if we can't parse the date

        threshold = self.cleanup_threshold
        if threshold.tzinfo is None:
            threshold = threshold.replace(tzinfo=article_date.tzinfo)
        return article_date < threshold

    def filter_old_articles(self, articles: List[Dict]) -> List[Dict]:
        """Filter out articles older than 7 days"""
        filtered_articles = []
        removed_count = 0

        for article in articles:
            normalized = normalize_story(article)
            if not self.is_article_too_old(normalized.get('publish_date')):
                filtered_articles.append(normalized)
            else:
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Filtered out {removed_count} articles older than 7 days")

        return filtered_articles

    def process_articles(self, articles: List[Dict], force_refresh: bool = False, batch_size: int = 10) -> List[Dict]:
        """
        Process a list of articles to generate summaries with batching

        Args:
            articles: List of article dictionaries with 'title' and 'content'
            force_refresh: Force API calls for all articles
            batch_size: Number of articles to process before saving cache

        Returns:
            List of articles with added 'summary' field
        """
        # First, filter out old articles
        articles = self.filter_old_articles(articles)

        logger.info(f"Processing {len(articles)} articles for summaries")

        processed_articles = []
        api_calls_made = 0
        cache_hits = 0

        for i, article in enumerate(articles, 1):
            if article.get('status') == 'rejected':
                logger.info(f"Skipping rejected article {i}: {article.get('title', '')[:50]}...")
                continue

            title = article.get('title', '')
            content = article.get('content', '')

            if not title or not content:
                logger.warning(f"Skipping article {i} - missing title or content")
                continue

            logger.info(f"Processing article {i}/{len(articles)}: {title[:50]}...")

            # Track if this will be a cache hit
            content_hash = self._generate_content_hash(title, content)
            will_use_cache = not force_refresh and self._should_use_cache(content_hash)

            # Generate summary
            summary = self.generate_summary(title, content, force_refresh)

            # Update counters
            if will_use_cache:
                cache_hits += 1
            else:
                api_calls_made += 1

            # Add summary to article
            processed_article = article.copy()
            processed_article['summary'] = summary
            processed_article['summary_generated_at'] = datetime.now().isoformat()
            processed_article['status'] = 'ready'

            processed_articles.append(normalize_story(processed_article))

            # Save cache periodically to prevent data loss
            if i % batch_size == 0:
                logger.info(f"Saving cache after processing {i} articles...")
                self._save_cache()

        # Final cache save
        self._save_cache()

        logger.info(f"Completed processing: {api_calls_made} API calls, {cache_hits} cache hits")
        return processed_articles

    def load_existing_summaries(self, filename: str) -> List[Dict]:
        """Load existing summaries and filter out old ones"""
        if not os.path.exists(filename):
            logger.info(f"No existing summaries file found at {filename}")
            return []

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            existing_articles = data.get('stories') or data.get('articles', [])
            logger.info(f"Loaded {len(existing_articles)} existing summarized articles")

            # Filter out old articles
            filtered_articles = self.filter_old_articles(existing_articles)

            return filtered_articles

        except (OSError, json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Error loading existing summaries: {e}")
            return []

    def merge_summaries(self, existing_summaries: List[Dict], new_summaries: List[Dict]) -> List[Dict]:
        """Merge new summaries with existing ones, avoiding duplicates"""
        # Create a set of existing article identifiers.
        existing_ids = {
            story_identity(a)
            for a in existing_summaries
        }

        # Start with existing summaries
        merged = existing_summaries.copy()
        added_count = 0
        updated_count = 0

        for article in new_summaries:
            article = normalize_story(article)
            article_id = story_identity(article)

            if article_id not in existing_ids:
                # New article
                merged.append(article)
                existing_ids.add(article_id)
                added_count += 1
            else:
                # Update existing article with new summary if it exists
                for i, existing in enumerate(merged):
                    existing_id = story_identity(existing)
                    if existing_id == article_id:
                        if 'summary' in article:
                            merged[i] = article
                            updated_count += 1
                        break

        if added_count > 0:
            logger.info(f"Added {added_count} new summarized articles")
        if updated_count > 0:
            logger.info(f"Updated {updated_count} existing summaries")

        return sort_stories(merged)

    def save_summaries_json(self, articles: List[Dict], filename: str = "news_summaries.json"):
        """Save articles with summaries to JSON file"""
        try:
            articles = sort_stories(normalize_story(article) for article in articles)
            output_data = {
                "generation_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "cleanup_threshold": f"Removed articles older than {self.cleanup_threshold.strftime('%Y-%m-%d')}",
                    "total_articles": len(articles),
                    "cache_file": self.cache_file,
                    "cache_stats": self.cache_data.get("cache_stats", {})
                },
                "stories": articles,
                "articles": articles
            }

            output_path = Path(filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = output_path.with_name(output_path.name + '.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, output_path)

            logger.info(f"Saved {len(articles)} articles with summaries to {filename}")

        except (OSError, TypeError, ValueError) as e:
            try:
                tmp_file.unlink(missing_ok=True)
            except (NameError, OSError):
                pass
            logger.error(f"Error saving summaries JSON: {e}")

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_file": self.cache_file,
            "cache_exists": os.path.exists(self.cache_file),
            "total_cached_summaries": len(self.cache_data.get("summaries", {})),
            "cache_stats": self.cache_data.get("cache_stats", {}),
            "cache_is_fresh": self._is_cache_fresh()
        }

def load_articles_from_json(filename: str) -> List[Dict]:
    """Load articles from the combined news scraper output"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            articles = data
        elif isinstance(data, dict):
            articles = data.get('stories') or data.get('articles', [])
        else:
            logger.error(f"Articles file {filename} has unexpected root type: {type(data).__name__}")
            return []

        if not isinstance(articles, list):
            logger.error(f"Articles file {filename} has unexpected articles type: {type(articles).__name__}")
            return []

        logger.info(f"Loaded {len(articles)} articles from {filename}")
        return articles

    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Error loading articles from {filename}: {e}")
        return []

def main():
    # Configuration
    CLAUDE_API_KEY = config.get('api_keys.anthropic')

    if not CLAUDE_API_KEY or config.is_placeholder(CLAUDE_API_KEY):
        print("Error: Anthropic API key not found in configuration.")
        print("Please add your API key to the config file under api_keys.anthropic")
        return

    INPUT_FILE = config.runtime_path('screens.news.raw_story_file', 'combined_news_recent.json')
    OUTPUT_FILE = config.runtime_path('screens.news.story_file', 'news_stories.json')
    LEGACY_OUTPUT_FILE = config.runtime_path('screens.news.legacy_story_file', 'news_summaries.json')
    CACHE_FILE = config.runtime_path('screens.news.cache_file', 'headline_summaries_cache.json')

    # Rate limiting - adjust based on your account type:
    # Free tier: ~5-15 requests/minute
    # Pro tier: ~50 requests/minute
    # API tier: varies by plan
    REQUESTS_PER_MINUTE = 50  # Adjust this based on your account

    print("NEWS HEADLINE SUMMARIZER")
    print("=" * 50)

    # Initialize summarizer
    try:
        summarizer = HeadlineSummarizer(CLAUDE_API_KEY, CACHE_FILE, REQUESTS_PER_MINUTE)
    except RuntimeError as e:
        print(f"Error: {e}")
        return

    # Clean up old cache entries
    summarizer._cleanup_old_cache_entries()

    # Show cache stats
    cache_stats = summarizer.get_cache_stats()
    print(f"Cache status: {'Fresh' if cache_stats['cache_is_fresh'] else 'Stale/Empty'}")
    print(f"Cached summaries: {cache_stats['total_cached_summaries']}")
    if cache_stats['cache_stats'].get('api_calls_saved'):
        print(f"API calls saved: {cache_stats['cache_stats']['api_calls_saved']}")
    print(f"Auto-cleanup: Removing articles older than 7 days (before {summarizer.cleanup_threshold.strftime('%Y-%m-%d')})")
    print()

    # Load existing summaries and clean up old ones
    existing_summaries = summarizer.load_existing_summaries(OUTPUT_FILE)

    # Load articles from scraper
    articles = load_articles_from_json(INPUT_FILE)
    if not articles:
        print(f"No articles found in {INPUT_FILE}")
        # Still save existing summaries if we have them
        if existing_summaries:
            summarizer.save_summaries_json(existing_summaries, OUTPUT_FILE)
            print(f"Saved {len(existing_summaries)} existing summaries to {OUTPUT_FILE}")
        return

    # Determine if we should force refresh
    force_refresh = config.get('screens.news.force_summary_refresh', False)
    if force_refresh:
        print("Configured to force refresh summaries via API")
    else:
        print("Will use cached summaries where available")
    print()

    # Estimate processing time for new articles
    new_articles = []
    for article in articles:
        title = article.get('title', '')
        content = article.get('content', '')
        content_hash = summarizer._generate_content_hash(title, content)
        if force_refresh or not summarizer._should_use_cache(content_hash):
            new_articles.append(article)

    if new_articles:
        estimated_time = len(new_articles) * summarizer.request_delay / 60
        print(f"Will process {len(new_articles)} new articles via API")
        print(f"Estimated time: {estimated_time:.1f} minutes")
        print()

    # Process articles to generate summaries
    processed_articles = summarizer.process_articles(articles, force_refresh=force_refresh)

    # Merge with existing summaries
    all_summaries = summarizer.merge_summaries(existing_summaries, processed_articles)

    # Save results
    summarizer.save_summaries_json(all_summaries, OUTPUT_FILE)
    if OUTPUT_FILE != LEGACY_OUTPUT_FILE:
        summarizer.save_summaries_json(all_summaries, LEGACY_OUTPUT_FILE)

    # Print summary
    print(f"\nSUMMARY")
    print("=" * 50)
    print(f"Total summarized articles in database: {len(all_summaries)}")
    print(f"  - Kept from previous: {len(existing_summaries)}")
    print(f"  - Processed from scraper: {len(processed_articles)}")
    print(f"Output saved to: {OUTPUT_FILE}")
    if OUTPUT_FILE != LEGACY_OUTPUT_FILE:
        print(f"Legacy output saved to: {LEGACY_OUTPUT_FILE}")
    print(f"Cache saved to: {CACHE_FILE}")

    final_stats = summarizer.get_cache_stats()
    print(f"Total cached summaries: {final_stats['total_cached_summaries']}")

    # Show sample summaries
    if all_summaries:
        print(f"\nSample summaries:")
        for i, article in enumerate(all_summaries[:3], 1):
            site = article.get('source_site', '').replace('_', ' ').title()
            print(f"{i}. [{site}] {article['summary']}")

if __name__ == "__main__":
    main()
