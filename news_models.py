"""
Shared helpers for news story records.

The scraper, summarizer, and display screen all handle the same records. Keep
normalization here so digest stories and regular articles have one database
shape.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional


VALID_READY_STATUSES = {"ready", "needs_summary"}


def normalize_text(text: str) -> str:
    """Collapse whitespace in display/database text."""
    return re.sub(r'\s+', ' ', text or '').strip()


def stable_story_id(story: Dict) -> str:
    """Build a stable identifier across scraper and summarizer runs."""
    source_site = story.get('source_site', 'unknown')
    source_type = story.get('source_type', 'regular_article')
    source_url = story.get('source_url') or story.get('url', '')
    digest_url = story.get('digest_url', '')
    title = normalize_text(story.get('title', '')).lower()
    key = f"{source_site}|{source_type}|{digest_url or source_url}|{title}"
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]


def story_identity(story: Dict):
    """Return the canonical identity used for de-duping stories."""
    return story.get('story_id') or stable_story_id(story)


def quality_score(story: Dict) -> float:
    """Score whether a scraped story has enough content to display/summarize."""
    title = story.get('title', '')
    content = story.get('content') or story.get('summary', '')
    score = 1.0

    if not title:
        score -= 0.5
    if len(content) < 120:
        score -= 0.35
    elif len(content) < 250:
        score -= 0.15
    if not story.get('publish_date') and not story.get('published_at'):
        score -= 0.2
    if content.lower().count('image:') + content.lower().count('photo:') > 2:
        score -= 0.2

    return max(0.0, round(score, 2))


def normalize_story(story: Dict, now: Optional[datetime] = None) -> Dict:
    """Convert regular and digest items into one story database shape."""
    normalized = story.copy()
    normalized['title'] = normalize_text(normalized.get('title', ''))
    normalized['content'] = normalize_text(normalized.get('content', ''))

    published_at = normalized.get('published_at') or normalized.get('publish_date')
    source_url = normalized.get('source_url') or normalized.get('url', '')

    normalized['story_id'] = normalized.get('story_id') or stable_story_id(normalized)
    normalized['source_url'] = source_url
    normalized['url'] = source_url
    normalized['published_at'] = published_at
    normalized['publish_date'] = published_at
    normalized['scraped_at'] = normalized.get('scraped_at') or (now or datetime.now(timezone.utc)).isoformat()
    normalized['quality_score'] = quality_score(normalized)

    display_text = normalized['content'] or normalized.get('summary', '')
    is_displayable = normalized['quality_score'] >= 0.5 and normalized['title'] and display_text
    current_status = normalized.get('status')
    if not is_displayable:
        normalized['status'] = 'rejected'
    elif current_status in VALID_READY_STATUSES:
        normalized['status'] = current_status
    elif normalized.get('summary'):
        normalized['status'] = 'ready'
    else:
        normalized['status'] = 'needs_summary'

    return normalized


def parse_story_datetime(story: Dict) -> Optional[datetime]:
    """Parse a story's best available date as a timezone-aware datetime."""
    date_str = (
        story.get('published_at') or
        story.get('publish_date') or
        story.get('summary_generated_at') or
        story.get('generated_at')
    )
    if not date_str:
        return None

    try:
        dt = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def sort_stories(stories: Iterable[Dict]) -> List[Dict]:
    """Return stories newest-first using canonical publish fields."""
    return sorted(
        stories,
        key=lambda story: parse_story_datetime(story) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def fallback_summary(content: str, max_chars: int = 220) -> str:
    """Create a short display summary when no generated summary exists."""
    content = normalize_text(content)
    if not content:
        return ''

    sentence_end = content.find('. ')
    if 80 <= sentence_end <= max_chars:
        return content[:sentence_end + 1]

    return content[:max_chars].rstrip() + ('...' if len(content) > max_chars else '')


def display_story_from_record(record: Dict) -> Optional[Dict]:
    """Map a story database record to the smaller shape expected by NewsScreen."""
    if record.get('status') == 'rejected':
        return None

    title = record.get('title') or record.get('headline')
    summary = record.get('summary') or fallback_summary(record.get('content', ''))
    if not title or not summary:
        return None

    return {
        'headline': title,
        'summary': summary,
        'published_at': record.get('published_at') or record.get('publish_date'),
        'generated_at': record.get('summary_generated_at') or record.get('generated_at', ''),
        'source_site': record.get('source_site', 'unknown'),
        'source_type': record.get('source_type', 'unknown'),
        'story_id': record.get('story_id'),
    }


def extract_display_stories(data: Dict) -> List[Dict]:
    """Extract NewsScreen display records from supported news JSON formats."""
    if not isinstance(data, dict):
        return []

    records = data.get('stories') or data.get('articles')
    if isinstance(records, list):
        stories = []
        for record in records:
            story = display_story_from_record(record)
            if story:
                stories.append(story)
        return stories

    summaries = data.get('summaries')
    if isinstance(summaries, dict):
        stories = []
        for story_id, story_data in summaries.items():
            if 'original_title' in story_data and 'summary' in story_data:
                stories.append({
                    'headline': story_data['original_title'],
                    'summary': story_data['summary'],
                    'generated_at': story_data.get('generated_at', ''),
                    'source_site': 'unknown',
                    'source_type': 'unknown',
                    'story_id': story_id,
                })
        return stories

    return []
