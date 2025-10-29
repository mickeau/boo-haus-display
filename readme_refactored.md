# Refactored News Scraper

A modular, robust news scraper with fixed date handling and digest detection.

## File Structure

```
news_scraper/
├── config.py                      # All configuration settings
├── date_handler.py                # Date parsing and comparison
├── digest_detector.py             # Digest article detection
├── digest_parsers.py              # Extract stories from digests
├── news_scraper_refactored.py     # Main scraper
├── test_digest_detection.py       # Test script (optional)
└── combined_news_recent.json      # Output file
```

## Key Fixes

### 1. **Date Handling** (date_handler.py)
- **Problem**: Inconsistent timezone handling caused recent articles to be flagged as old
- **Fix**: All dates are now timezone-aware (UTC), consistent comparisons
- **Benefit**: Accurate date filtering, no more false positives

### 2. **Digest Detection** (digest_detector.py)
- **Problem**: OGN detection was too broad - any article with day names matched
- **Fix**: 
  - OGN: Must contain BOTH a day name (monday-sunday) AND either "news" or "ogn"
  - Positive News: Flexible regex matching for title variations
- **Benefit**: Regular articles no longer misidentified as digests

Examples:
- ✅ "Today's Good News Monday 30 Sept" → digest
- ✅ "Today's Positive News 2 Oct 2025" → digest  
- ✅ "OGN Friday Edition" → digest
- ❌ "Monday Morning Motivation" → regular (has day, no news/ogn)
- ❌ "Breaking News Update" → regular (has news, no day)

### 3. **Modular Architecture**
- **Separation of Concerns**: Each module has a single responsibility
- **Testability**: Individual components can be tested independently
- **Maintainability**: Easy to add new sites or modify behavior
- **Configuration**: All settings in one place

## Configuration

Edit `config.py` to adjust:

```python
# Scraper behavior
SCRAPER_CONFIG = {
    'article_recent_days': 2,        # How far back to scrape
    'cleanup_threshold_days': 7,     # When to remove old articles
    'request_delay': 1,              # Seconds between requests
    'output_filename': 'combined_news_recent.json'
}

# Site-specific settings
SITES_CONFIG = {
    'only_good_news_daily': {
        'digest_detection': {
            'title_keywords': ['today\'s good news'],
            'day_names': ['monday', 'tuesday', ...],
            'require_all': True  # Both must match
        }
    }
}
```

## Usage

### Basic Usage

```bash
python news_scraper_refactored.py
```

### What It Does

1. **Loads** existing articles from JSON
2. **Cleans** articles older than 7 days
3. **Scrapes** RSS feeds from configured sites
4. **Detects** digest vs regular articles
5. **Extracts** individual stories from digests
6. **Filters** by date (last 2 days)
7. **Merges** with existing articles (deduplicates)
8. **Saves** to JSON with metadata

### Output

```json
{
  "extraction_metadata": {
    "extracted_at": "2025-10-02T10:30:00+00:00",
    "date_filter": "Last 2 days (since 2025-09-30)",
    "total_articles": 47,
    "by_site": {
      "only_good_news_daily": 25,
      "positive_news": 22
    },
    "by_type": {
      "digest_story": 40,
      "regular_article": 7
    }
  },
  "articles": [...]
}
```

## Logging

The scraper provides detailed logging to help debug issues:

```
================================================================
# Starting scrape of only_good_news_daily
================================================================
============================================================
Processing only_good_news_daily: Today's Good News Monday 30 Sept 2025
URL: https://www.onlygoodnewsdaily.com/...
→ Identified as DIGEST article
✓ Identified as OGN digest: 'Today's Good News Monday 30 Sept 2025'
Extracting stories from OGN digest: ...
Found 15 potential headlines
✓ Extracted 12 stories from OGN digest
✓ Added 12/12 recent stories from digest
```

## Adding New Sites

1. Add configuration to `config.py`:
```python
SITES_CONFIG['new_site'] = {
    'rss_url': 'https://...',
    'digest_detection': {...},
    'content_selectors': [...]
}
```

2. Create parser in `digest_parsers.py`:
```python
class NewSiteDigestParser(BaseDigestParser):
    def extract_digest_stories(self, url: str) -> List[Dict]:
        # Implementation
        pass
```

3. Update factory:
```python
def create(site_name: str, ...):
    if site_name == 'new_site':
        return NewSiteDigestParser(...)
```

## Testing Digest Detection

Create `test_digest_detection.py`:

```python
from config import SITES_CONFIG
from digest_detector import DigestDetectorFactory

# Test OGN
ogn_config = SITES_CONFIG['only_good_news_daily']
ogn_detector = DigestDetectorFactory.create('only_good_news_daily', ogn_config)

# These should be TRUE (digests)
assert ogn_detector.is_digest("Today's Good News Monday 30 Sept 2025")
assert ogn_detector.is_digest("Today's Good News Friday 27 Sept 2025")

# These should be FALSE (regular articles)
assert not ogn_detector.is_digest("5 Inspiring Stories from Monday's Rally")
assert not ogn_detector.is_digest("Tuesday's Breakthrough in Cancer Research")

print("✓ All OGN tests passed!")

# Test Positive News
pn_config = SITES_CONFIG['positive_news']
pn_detector = DigestDetectorFactory.create('positive_news', pn_config)

# These should be TRUE
assert pn_detector.is_digest(
    "What went right this week: the good news that matters",
    "https://positive.news/good-news-from-week-39-of-2025"
)

# These should be FALSE
assert not pn_detector.is_digest(
    "Scientists Discover New Renewable Energy Source",
    "https://positive.news/environment/renewable-energy-breakthrough"
)

print("✓ All Positive News tests passed!")
```

## Troubleshooting

### Articles Being Skipped

Check the logs for:
- `✗ Skipping - article is too old` → Adjust `article_recent_days` in config
- `Skipping excluded headline` → Check exclusion patterns in config
- `Not a digest` → Verify digest detection patterns match actual titles

### Date Issues

- All dates are stored as ISO format with timezone (UTC)
- If dates seem wrong, check `extract_article_date` methods in parsers
- Enable DEBUG logging to see date parsing details:
  ```python
  logging.basicConfig(level=logging.DEBUG)
  ```

### Digest Not Detected

1. Print the actual title from RSS:
   ```python
   for entry in feed.entries:
       print(f"Title: '{entry.title}'")
       print(f"URL: '{entry.link}'")
   ```

2. Verify pattern in config matches exactly

3. Test with `test_digest_detection.py`

## Performance

- Default 1 second delay between requests (respectful)
- Average scrape time: 2-5 minutes for both sites
- Incremental updates: Only scrapes new content
- Auto-cleanup: Removes articles >7 days old

## Dependencies

```bash
pip install feedparser requests beautifulsoup4
```

## License

Same as original project
