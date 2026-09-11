"""
Digest article parsers for extracting individual stories
Separated into modular, testable components
"""

from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from base_fetcher import http_get
from date_handler import DateHandler

logger = logging.getLogger(__name__)


class BaseDigestParser:
    """Base class for digest parsers"""

    def __init__(self, session, site_config: Dict, date_handler: DateHandler):
        self.session = session
        self.config = site_config
        self.parsing_config = site_config.get('digest_parsing', {})
        self.date_handler = date_handler

    def extract_digest_stories(self, url: str) -> List[Dict]:
        """Extract individual stories from digest article"""
        raise NotImplementedError("Subclasses must implement extract_digest_stories")


class OGNDigestParser(BaseDigestParser):
    """Only Good News Daily digest parser"""

    def extract_article_date(self, url: str) -> Optional[str]:
        """Extract date from OGN URL pattern"""
        pattern = self.config['date_extraction']['url_pattern']
        month_map = self.config['date_extraction']['month_names']

        return self.date_handler.extract_date_from_url(url, pattern, month_map)

    def extract_digest_stories(self, url: str) -> List[Dict]:
        """Extract individual stories from OGN digest article"""
        try:
            logger.info(f"Extracting stories from OGN digest: {url}")
            response = http_get(
                url,
                timeout=30,
                session=self.session,
                description="Only Good News Daily digest",
            )
            if response is None:
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            date_published = self.extract_article_date(url)

            if not date_published:
                logger.warning(f"Could not extract date from OGN URL: {url}")
                date_published = self.date_handler.get_current_iso_date()

            stories = []
            exclusions = set(self.parsing_config.get('exclusion_patterns', []))
            min_content_length = self.parsing_config.get('min_content_length', 300)

            # Method 1: Try CSS selector approach (old structure)
            headline_elements = soup.find_all('h5', class_='bD4A0 _9j-5z ewTCf rgwei')

            if headline_elements:
                logger.info(f"Found {len(headline_elements)} headlines using CSS selector")
                for headline_elem in headline_elements:
                    headline_text = headline_elem.get_text(strip=True)
                    headline_lower = headline_text.lower()

                    if any(exc in headline_lower for exc in exclusions):
                        continue
                    if headline_text.startswith('"'):
                        continue

                    content_paragraphs = self._extract_story_content(headline_elem)
                    if content_paragraphs:
                        content_text = '\n\n'.join(content_paragraphs)
                        if len(content_text) >= min_content_length:
                            story = {
                                'title': headline_text,
                                'url': url,
                                'content': content_text,
                                'publish_date': date_published,
                                'source_type': 'digest_story',
                                'source_site': 'only_good_news_daily',
                                'digest_url': url
                            }
                            stories.append(story)
            else:
                # Method 2: Parse text structure (new layout)
                logger.info("CSS selectors not found, using text parsing method")

                # Find all paragraphs - preserve paragraph structure better
                # Use separator that won't break on hyperlinks
                all_text = soup.get_text(separator='|||LINEBREAK|||')
                # Now split on our marker and filter
                lines = [l.strip() for l in all_text.split('|||LINEBREAK|||') if l.strip() and len(l.strip()) > 3]

                i = 0
                while i < len(lines):
                    line = lines[i]
                    line_lower = line.lower()

                    # HARD STOP at "On This Day" section
                    if 'on this day' in line_lower:
                        logger.info(f"Stopping extraction at 'On This Day' section")
                        break

                    # Skip other exclusions but don't stop
                    if any(exc in line_lower for exc in exclusions):
                        i += 1
                        continue

                    # Potential headline: short line (5-50 chars) not starting with special chars
                    # Must also check it's not just a hyperlink fragment or sentence fragment
                    is_potential_headline = (
                        5 < len(line) < 50 and
                        not line.startswith(('Image:', 'Credit:', 'Photo:', 'http', '-', '•', 'In ', 'The ', 'A ')) and
                        not line.endswith(('ago', 'read', 'OGN Daily', 'said', 'says', '.', ',')) and
                        line[0].isupper() and  # Must start with capital
                        not any(char.isdigit() for char in line[:3])  # No numbers in first 3 chars
                    )

                    if is_potential_headline and i + 1 < len(lines):
                        next_line = lines[i + 1]

                        # Next line must be substantial content (>150 chars for better accuracy)
                        # and start with a capital letter (proper sentence)
                        if len(next_line) > 150 and next_line[0].isupper():
                            headline = line
                            content_parts = []

                            # Gather content lines
                            j = i + 1
                            while j < len(lines):
                                content_line = lines[j]
                                content_lower = content_line.lower()

                                # Stop at next headline or exclusion
                                if any(exc in content_lower for exc in exclusions):
                                    break
                                if (5 < len(content_line) < 50 and
                                    not content_line.startswith(('Image:', 'Credit:', 'Photo:')) and
                                    j + 1 < len(lines) and len(lines[j + 1]) > 60):
                                    break

                                # Add content if substantial
                                if len(content_line) > 30 and not content_line.startswith(('Image:', 'Credit:', 'Photo:')):
                                    content_parts.append(content_line)

                                j += 1

                            # Create story if content is sufficient
                            if content_parts:
                                content_text = ' '.join(content_parts)
                                if len(content_text) >= min_content_length:
                                    story = {
                                        'title': headline,
                                        'url': url,
                                        'content': content_text,
                                        'publish_date': date_published,
                                        'source_type': 'digest_story',
                                        'source_site': 'only_good_news_daily',
                                        'digest_url': url
                                    }
                                    stories.append(story)
                                    logger.debug(f"Extracted: {headline} ({len(content_text)} chars)")

                            i = j
                            continue

                    i += 1

            logger.info(f"✓ Extracted {len(stories)} stories from OGN digest")
            return stories

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error(f"Error extracting OGN digest stories from {url}: {e}", exc_info=True)
            return []

    def _extract_story_content(self, headline_elem) -> List[str]:
        """Extract content paragraphs following a headline"""
        headline_sel = self.parsing_config['headline_selector']
        content_sel = self.parsing_config['content_selector']
        divider_sel = self.parsing_config['divider_selector']
        max_depth = self.parsing_config.get('max_traversal_depth', 20)
        min_length = self.parsing_config.get('min_content_length', 30)

        content_paragraphs = []
        current = headline_elem.parent

        # Traverse DOM to find content
        for _ in range(max_depth):
            current = current.find_next_sibling()
            if not current:
                break

            # Collect content paragraphs
            for p in current.find_all(content_sel['tag'], class_=content_sel['class']):
                text = p.get_text(strip=True)
                if (len(text) > min_length and
                    not text.startswith(('Credit:', 'Image:', 'Photo:'))):
                    content_paragraphs.append(text)

            # Stop at next headline or divider
            if (current.find(headline_sel['tag'], class_=headline_sel['class']) or
                current.find(divider_sel['tag'], attrs=divider_sel['attrs'])):
                break

        return content_paragraphs


class PositiveNewsDigestParser(BaseDigestParser):
    """Positive News digest parser"""

    def extract_article_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract date from Positive News article page"""
        try:
            date_sel = self.config['date_extraction']['sidebar_selector']
            date_element = soup.find(date_sel['tag'], class_=date_sel['class'])

            if date_element:
                date_text = date_element.get_text(strip=True)
                date_format = self.config['date_extraction']['date_format']

                dt = self.date_handler.parse_date_string(date_text, date_format)
                if dt:
                    return dt.isoformat()
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.debug(f"Could not parse Positive News article date: {e}")

        return self.date_handler.get_current_iso_date()

    def extract_digest_stories(self, url: str) -> List[Dict]:
        """Extract individual stories from Positive News digest article"""
        logger.info(f"Extracting stories from Positive News digest: {url}")

        try:
            response = http_get(
                url,
                timeout=30,
                session=self.session,
                description="Positive News digest",
            )
            if response is None:
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            date_published = self.extract_article_date(soup)
            stories = []

            # Find story containers
            container_sel = self.parsing_config['container_selector']
            item_containers = soup.find_all(
                container_sel['tag'],
                class_=container_sel['class']
            )

            logger.info(f"Found {len(item_containers)} story containers")

            for container in item_containers:
                story_data = self._extract_story_from_container(
                    container,
                    date_published,
                    url
                )
                if story_data:
                    stories.append(story_data)
                    logger.debug(f"Extracted story: {story_data['title'][:50]}...")

            logger.info(f"✓ Extracted {len(stories)} stories from Positive News digest")
            return stories

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error(f"Error extracting Positive News digest stories from {url}: {e}", exc_info=True)
            return []

    def _extract_story_from_container(self, container, date_published: str,
                                     digest_url: str) -> Optional[Dict]:
        """Extract story data from a single container"""
        content_sel = self.parsing_config['content_selector']
        title_sel = self.parsing_config['title_selector']
        min_length = self.parsing_config.get('min_content_length', 50)
        credit_prefixes = tuple(self.parsing_config.get('credit_prefixes', []))

        # Find content element
        content_element = container.find(
            content_sel['tag'],
            class_=content_sel['class']
        )
        if not content_element:
            return None

        # Extract headline
        headline_element = content_element.find(
            title_sel['tag'],
            class_=title_sel['class']
        )
        if not headline_element:
            return None

        headline = headline_element.get_text(strip=True)

        # Extract content paragraphs
        content_paragraphs = []
        paragraphs = content_element.find_all('p')

        if paragraphs:
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and not text.startswith(credit_prefixes):
                    content_paragraphs.append(text)
        else:
            # Fallback: get text and clean
            fallback_text = content_element.get_text(strip=True)
            if headline in fallback_text:
                fallback_text = fallback_text.replace(headline, '').strip()

            if fallback_text and len(fallback_text) > min_length:
                sentences = [s.strip() + '.' for s in fallback_text.split('. ')
                           if len(s.strip()) > 20]
                content_paragraphs = sentences

        if not content_paragraphs:
            return None

        return {
            'title': headline,
            'url': digest_url,
            'content': '\n\n'.join(content_paragraphs),
            'publish_date': date_published,
            'source_type': 'digest_story',
            'source_site': 'positive_news',
            'digest_url': digest_url
        }


class DigestParserFactory:
    """Factory for creating site-specific digest parsers"""

    @staticmethod
    def create(site_name: str, session, site_config: Dict,
               date_handler: DateHandler) -> BaseDigestParser:
        """Create appropriate digest parser for site"""
        if site_name == 'only_good_news_daily':
            return OGNDigestParser(session, site_config, date_handler)
        elif site_name == 'positive_news':
            return PositiveNewsDigestParser(session, site_config, date_handler)
        else:
            raise ValueError(f"Unknown site: {site_name}")
