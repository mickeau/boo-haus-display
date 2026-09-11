"""
Configuration module for news scraper
Contains all site-specific settings, patterns, and selectors
Extracted from the original config.py before the Gemini rewrite
"""

from datetime import timedelta

# Scraper settings
SCRAPER_CONFIG = {
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'request_timeout': 30,
    'request_delay': 1,  # seconds between requests
    'article_recent_days': 3,  # articles from last N days
    'cleanup_threshold_days': 3,  # remove articles older than N days
    'output_filename': 'combined_news_recent.json'
}

# Site configurations
SITES_CONFIG = {
    'only_good_news_daily': {
        'name': 'Only Good News Daily',
        'rss_url': 'https://www.onlygoodnewsdaily.com/blog-feed.xml',
        'digest_detection': {
            'method': 'title_pattern',
            'day_names': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
            'required_words': ['news', 'ogn'],
            'require_day_and_word': True,
            'url_pattern': r'(?:good-news-(?:of-the-day|today)|global-good-news|global-upbeat-news-stories|today-s-(?:good|positive)-news(?:-around-the-world)?)-\d{1,2}-[a-z]+-\d{4}'
        },
        'date_extraction': {
            'url_pattern': r'(?:good-news-(?:of-the-day|today)|global-good-news|global-upbeat-news-stories|today-s-(?:good|positive)-news(?:-around-the-world)?)-(\d{1,2})-([a-z]+)-(\d{4})',
            'month_names': {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
        },
        'digest_parsing': {
            'headline_selector': {'tag': 'h5', 'class': 'bD4A0 _9j-5z ewTCf rgwei'},
            'content_selector': {'tag': 'p', 'class': 'l1t8- VSn1J ewTCf rgwei'},
            'divider_selector': {'tag': 'div', 'attrs': {'data-hook': 'divider'}},
            'max_traversal_depth': 20,
            'min_content_length': 30,
            'exclusion_patterns': [
                'on this day',
                'today\'s articles',
                'mood boosting video',
                'common sense',
                'samoojat',
                'fibonacci sequence',
                'leaves on the line'
            ]
        },
        'content_selectors': [
            'article',
            '.post-content',
            '.entry-content',
            '.article-content',
            '.content',
            'main',
            '[class*="content"]'
        ]
    },
    'positive_news': {
        'name': 'Positive News',
        'rss_url': 'https://positive.news/feed',
        'digest_detection': {
            'method': 'title_and_url',
            'title_pattern': r'^What went right this week:?\s*(?:the )?good news',
            'url_pattern': r'good-news-(?:stories-)?from-(?:the-)?week-\d+-of-\d{4}'
        },
        'date_extraction': {
            'sidebar_selector': {'tag': 'span', 'class': 'article__date'},
            'date_format': '%B %d, %Y'
        },
        'digest_parsing': {
            'container_selector': {'tag': 'div', 'class': 'half-and-half--item'},
            'content_selector': {'tag': 'div', 'class': 'half-and-half__content'},
            'title_selector': {'tag': 'span', 'class': 'half-and-half__title h5'},
            'min_content_length': 50,
            'credit_prefixes': ['Image:', 'Photo:']
        },
        'content_selectors': [
            '.article__content',
            'article .entry-content',
            '.post-content',
            '.entry-content',
            '.article-content',
            '.content',
            'article',
            'main',
            '.wp-block-post-content',
            '[class*="content"]'
        ]
    }
}

# Date parsing patterns for article extraction
DATE_PATTERNS = {
    'meta_selectors': [
        'meta[property="article:published_time"]',
        'meta[name="date"]',
        'meta[name="publish_date"]',
        'meta[name="publication_date"]',
        'meta[property="og:published_time"]',
        'meta[name="DC.date.issued"]'
    ],
    'html_selectors': [
        'time[datetime]',
        '.entry-date',
        '.published',
        '.post-date',
        '.article-date',
        '.date',
        '[class*="date"]',
        '[id*="date"]',
        '.wp-block-post-date'
    ],
    'regex_patterns': [
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        r'\d{4}-\d{2}-\d{2}',
        r'\d{1,2}/\d{1,2}/\d{4}',
        r'[A-Za-z]+ \d{1,2}, \d{4}',
        r'\d{1,2} [A-Za-z]+ \d{4}',
    ],
    'strptime_formats': {
        'iso_with_time': '%Y-%m-%dT%H:%M:%S',
        'iso_date': '%Y-%m-%d',
        'us_slash': '%m/%d/%Y',
        'month_name_comma': '%B %d, %Y',
        'day_month_name': '%d %B %Y'
    }
}

# Elements to remove during scraping
UNWANTED_ELEMENTS = [
    'script', 'style', 'nav', 'footer', 'header', 'aside',
    'advertisement', '.social-share', '.comments', '.related-posts'
]

# Logging configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(levelname)s - %(message)s'
}
