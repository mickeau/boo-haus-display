"""
Date handling utilities with consistent timezone handling
Fixes the timezone comparison issues in the original code
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)


class DateHandler:
    """Handles all date parsing and comparison with consistent timezone handling"""
    
    def __init__(self, recent_days: int = 2, cleanup_days: int = 7):
        """
        Initialize with thresholds
        
        Args:
            recent_days: Articles newer than this are considered "recent"
            cleanup_days: Articles older than this are removed
        """
        # Always use UTC-aware datetimes for consistency
        now = datetime.now(timezone.utc)
        
        # Calculate cutoff date (subtract recent_days)
        self.cutoff_date = now - timedelta(days=recent_days)
        self.cutoff_date = self.cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate cleanup threshold (subtract cleanup_days)
        self.cleanup_threshold = now - timedelta(days=cleanup_days)
        self.cleanup_threshold = self.cleanup_threshold.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def parse_iso_date(date_str: str) -> Optional[datetime]:
        """
        Parse ISO format date string to timezone-aware datetime
        
        Args:
            date_str: ISO format date string
            
        Returns:
            Timezone-aware datetime or None if parsing fails
        """
        if not date_str:
            return None
        
        try:
            # Handle 'Z' timezone indicator
            date_str = date_str.replace('Z', '+00:00')
            
            # Parse the datetime
            dt = datetime.fromisoformat(date_str)
            
            # Make timezone-aware if naive (assume UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            return dt
            
        except (AttributeError, TypeError, ValueError) as e:
            logger.debug(f"Could not parse ISO date '{date_str}': {e}")
            return None
    
    @staticmethod
    def parse_date_string(date_str: str, format_str: str) -> Optional[datetime]:
        """
        Parse date string with specific format to timezone-aware datetime
        
        Args:
            date_str: Date string to parse
            format_str: strptime format string
            
        Returns:
            Timezone-aware datetime or None if parsing fails
        """
        if not date_str:
            return None
        
        try:
            dt = datetime.strptime(date_str, format_str)
            # Make timezone-aware (assume UTC for parsed dates)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (TypeError, ValueError) as e:
            logger.debug(f"Could not parse date '{date_str}' with format '{format_str}': {e}")
            return None
    
    @staticmethod
    def extract_date_from_url(url: str, pattern: str, month_map: dict) -> Optional[str]:
        """
        Extract date from URL using regex pattern
        
        Args:
            url: URL to extract date from
            pattern: Regex pattern with groups for day, month, year
            month_map: Dictionary mapping month abbreviations to numbers
            
        Returns:
            ISO format date string or None
        """
        if not url or not pattern:
            return None

        try:
            match = re.search(pattern, url)
        except (TypeError, re.error) as e:
            logger.debug(f"Could not apply date pattern to URL '{url}': {e}")
            return None

        if not match:
            return None

        groups = match.groups()
        if len(groups) < 3:
            logger.debug(f"Date pattern for URL '{url}' must capture day, month, and year")
            return None

        day, month_name, year = groups[:3]

        try:
            month_num = month_map[month_name.lower()]
        except (AttributeError, KeyError, TypeError) as e:
            logger.debug(f"Could not map month '{month_name}' from URL '{url}': {e}")
            return None

        try:
            dt = datetime(int(year), month_num, int(day), tzinfo=timezone.utc)
            return dt.isoformat()
        except (TypeError, ValueError) as e:
            logger.debug(f"Could not extract date from URL '{url}': {e}")
            return None
    
    def is_recent(self, date_str: Optional[str]) -> bool:
        """
        Check if article is recent (within cutoff threshold)
        
        Args:
            date_str: ISO format date string
            
        Returns:
            True if recent or date unknown, False if too old
        """
        if not date_str:
            logger.debug("No date provided, treating as recent")
            return True
        
        article_date = self.parse_iso_date(date_str)
        if not article_date:
            logger.debug(f"Could not parse date '{date_str}', treating as recent")
            return True
        
        is_recent = article_date >= self.cutoff_date
        logger.debug(f"Article date {article_date.date()} vs cutoff {self.cutoff_date.date()}: {'recent' if is_recent else 'old'}")
        return is_recent
    
    def is_too_old(self, date_str: Optional[str]) -> bool:
        """
        Check if article should be cleaned up (older than threshold)
        
        Args:
            date_str: ISO format date string
            
        Returns:
            True if too old, False if should be kept
        """
        if not date_str:
            logger.debug("No date provided, keeping article")
            return False
        
        article_date = self.parse_iso_date(date_str)
        if not article_date:
            logger.debug(f"Could not parse date '{date_str}', keeping article")
            return False
        
        too_old = article_date < self.cleanup_threshold
        logger.debug(f"Article date {article_date.date()} vs threshold {self.cleanup_threshold.date()}: {'removing' if too_old else 'keeping'}")
        return too_old
    
    @staticmethod
    def get_current_iso_date() -> str:
        """Get current datetime as ISO string"""
        return datetime.now(timezone.utc).isoformat()
    
    def get_cutoff_date_str(self) -> str:
        """Get cutoff date as formatted string"""
        return self.cutoff_date.strftime('%Y-%m-%d')
    
    def get_cleanup_threshold_str(self) -> str:
        """Get cleanup threshold as formatted string"""
        return self.cleanup_threshold.strftime('%Y-%m-%d')
