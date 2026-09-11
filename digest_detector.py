"""
Robust digest article detection
Fixes the overly broad pattern matching in the original code
"""

import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DigestDetector:
    """Detects whether articles are digest pages requiring special parsing"""

    def __init__(self, site_config: Dict[str, Any]):
        """
        Initialize with site-specific configuration

        Args:
            site_config: Site configuration from config.py
        """
        self.site_config = site_config
        self.detection_config = site_config.get('digest_detection', {})
        self.method = self.detection_config.get('method', 'title_pattern')

    def is_digest(self, title: str, url: str = "") -> bool:
        """
        Determine if article is a digest page

        Args:
            title: Article title
            url: Article URL (optional, used for some detection methods)

        Returns:
            True if digest page, False otherwise
        """
        if self.method == 'title_pattern':
            return self._check_title_pattern(title, url)
        elif self.method == 'title_and_url':
            return self._check_title_and_url(title, url)
        else:
            logger.warning(f"Unknown digest detection method: {self.method}")
            return False

    def _check_title_pattern(self, title: str, url: str = "") -> bool:
        """
        Check if title matches OGN digest pattern

        OGN digest titles ALWAYS have:
        1. A day name (monday, tuesday, wednesday, etc.)
        2. Either "news" OR "ogn"

        SPECIAL CASE: Weekly roundups/synopsis articles should be EXCLUDED
        These contain phrases like "last week" + "round-up/roundup/synopsis"

        Examples that SHOULD match:
        - "Today's Good News Monday 30 Sept 2025"
        - "Today's Positive News 2 Oct 2025"
        - "OGN Friday Edition"
        - "Tuesday News Roundup"

        Examples that should NOT match:
        - "5 Ways to Improve Your Monday" (has day but no news/ogn)
        - "Breaking News in Science" (has news but no day)
        - "Good News Worth Celebrating" (weekly roundup - should skip entirely)
        - "Community Update" (has neither)

        Args:
            title: Article title

        Returns:
            True if matches digest pattern
        """
        title_lower = title.lower()

        url_pattern = self.detection_config.get('url_pattern', '')
        if url_pattern and url and re.search(url_pattern, url, re.IGNORECASE):
            logger.info(f"✓ URL matches digest pattern: '{url}'")
            return True

        # Check for weekly roundup/synopsis indicators - these should NOT be digests
        weekly_indicators = ['synopsis', 'roundup', 'round-up', 'round up']
        if any(indicator in title_lower for indicator in weekly_indicators):
            logger.info(f"Skipping weekly roundup article (not a daily digest): '{title}'")
            return False

        # Check for day name
        day_names = self.detection_config.get('day_names', [])
        has_day = any(
            re.search(rf'\b{re.escape(day)}\b', title_lower)
            for day in day_names
        )

        if not has_day:
            logger.debug(f"Title '{title}' does not contain a day name")
            return False

        # Check for required words (news OR ogn)
        required_words = self.detection_config.get('required_words', [])
        has_required_word = any(word in title_lower for word in required_words)

        if not has_required_word:
            logger.debug(f"Title '{title}' contains day name but not 'news' or 'ogn'")
            return False

        logger.info(f"✓ Identified as OGN digest: '{title}'")
        return True

    def _check_title_and_url(self, title: str, url: str) -> bool:
        """
        Check if title and/or URL match Positive News digest pattern

        Positive News digests:
        - Title matches pattern (flexible matching)
        - OR URL matches pattern

        Args:
            title: Article title
            url: Article URL

        Returns:
            True if matches digest pattern
        """
        # Check title pattern (case insensitive, flexible)
        title_pattern = self.detection_config.get('title_pattern', '')
        title_match = False

        if title_pattern:
            # Use regex for flexible matching
            title_match = bool(re.search(title_pattern, title, re.IGNORECASE))
            if title_match:
                logger.info(f"✓ Title matches Positive News digest pattern: '{title}'")

        # Check URL pattern
        url_pattern = self.detection_config.get('url_pattern', '')
        url_match = False

        if url_pattern:
            url_match = bool(re.search(url_pattern, url, re.IGNORECASE))
            if url_match:
                logger.info(f"✓ URL matches Positive News digest pattern: '{url}'")

        is_digest = title_match or url_match

        if is_digest:
            logger.info(f"✓ Identified as Positive News digest")
        else:
            logger.debug(f"Not a digest - Title: '{title}', URL: '{url}'")

        return is_digest


class DigestDetectorFactory:
    """Factory for creating site-specific digest detectors"""

    @staticmethod
    def create(site_name: str, site_config: Dict[str, Any]) -> DigestDetector:
        """
        Create a digest detector for the specified site

        Args:
            site_name: Name of the site
            site_config: Site configuration

        Returns:
            DigestDetector instance
        """
        return DigestDetector(site_config)
