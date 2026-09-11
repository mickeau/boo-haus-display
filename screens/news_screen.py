#!/usr/bin/env python3
"""
News Screen for Boo Haus Display
Shows cycling news summaries from cached stories
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_screen import BaseScreen
import json
import logging
from datetime import datetime, timedelta, timezone

from config import config
from news_models import extract_display_stories, fallback_summary, parse_story_datetime

logger = logging.getLogger(__name__)


class NewsScreen(BaseScreen):
    """News summaries display"""

    @property
    def name(self) -> str:
        return "news"

    def __init__(self):
        super().__init__()
        self.state_file = config.runtime_path('screens.news.state_file', 'news_display_state.json')

    def render_content(self):
        """Render news summaries"""
        x, y, width, height = self.get_content_area()

        # Title
        current_y = self.draw_section_title("Recent Good News Headlines", y)

        # Get news stories (with cycling)
        stories = self.load_and_cycle_stories()

        if not stories:
            self.draw.text((x, current_y), "No news stories available",
                         font=self.font_medium, fill=self.BLACK)
            self.draw.text((x, current_y + 30),
                         "Run news_scraper.py to fetch stories",
                         font=self.font_tiny, fill=self.RED)
            return

        # Display stories
        available_height = height - (current_y - y) - 10
        current_y = self.draw_stories(stories, x, current_y, width, available_height)

    def draw_stories(self, stories, x, y, width, max_height):
        """Draw news stories with bullet points"""
        current_y = y + 20

        for i, story in enumerate(stories):
            # Check available space (need at least 60px for a story)
            if current_y - y > max_height - 60:
                break

            headline = story.get('headline', 'No headline')
            summary = story.get('summary', '')

            # Draw bullet point
            bullet_size = 8
            bullet_x = x + 10
            bullet_y = current_y + 5

            self.draw.ellipse([bullet_x, bullet_y,
                             bullet_x + bullet_size, bullet_y + bullet_size],
                            fill=self.BLUE, outline=self.BLUE)

            # Headline (bold/larger)
            text_x = x + 25
            text_width = width - 35

            headline_lines = self.wrap_text(headline, text_width, self.font_medium)

            # Draw headline (max 2 lines)
            for line_num, line in enumerate(headline_lines[:2]):
                if current_y - y > max_height - 40:
                    break
                self.draw.text((text_x, current_y), line,
                             font=self.font_medium, fill=self.BLACK)
                current_y += 22

            # Add space between headline and summary
            current_y += 5

            # Summary (smaller font)
            if summary and current_y - y < max_height - 40:
                summary_lines = self.wrap_text(summary, text_width, self.font_small)

                # Limit summary lines based on available space
                lines_remaining = (max_height - (current_y - y)) // 18
                max_summary_lines = min(4, lines_remaining - 1)  # Leave space for next story

                for line_num, line in enumerate(summary_lines[:max_summary_lines]):
                    if current_y - y > max_height - 25:
                        break
                    self.draw.text((text_x, current_y), line,
                                 font=self.font_small, fill=self.BLACK)
                    current_y += 18

                # Add ellipsis if summary was truncated
                if len(summary_lines) > max_summary_lines:
                    self.draw.text((text_x, current_y), "...",
                                 font=self.font_small, fill=self.BLACK)
                    current_y += 18

            # Spacing between stories
            current_y += 12

            # Draw separator line between stories (except after last)
            if i < len(stories) - 1 and current_y - y < max_height - 50:
                self.draw.line([(x + 20, current_y), (x + width - 10, current_y)],
                             fill=self.BLACK, width=1)
                current_y += 25

        return current_y

    def load_and_cycle_stories(self):
        """Load stories from cache and cycle through them"""
        try:
            story_file = config.runtime_path('screens.news.story_file', 'news_stories.json')
            cache_file = config.runtime_path('screens.news.cache_file', 'headline_summaries_cache.json')
            raw_story_file = config.runtime_path('screens.news.raw_story_file', 'combined_news_recent.json')
            num_stories = config.get('screens.news.stories_per_screen', 4)

            all_stories = []
            data_file = None
            for candidate in self._news_data_file_candidates(story_file, cache_file, raw_story_file):
                try:
                    with open(candidate, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid news file {candidate}: {e}")
                    continue
                except OSError as e:
                    logger.warning(f"Could not read news file {candidate}: {e}")
                    continue

                candidate_stories = self._filter_recent_stories(self._extract_stories(data))
                if candidate_stories:
                    data_file = candidate
                    all_stories = candidate_stories
                    break

                logger.info(f"No displayable stories in {candidate}, trying next news file")

            if not all_stories:
                logger.error("No displayable stories in any news story database or summary cache")
                return []

            all_stories.sort(
                key=lambda story: self._parse_story_datetime(story) or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )

            # Load current position from state
            current_position = self.load_state()

            # Ensure position is valid
            if current_position >= len(all_stories):
                current_position = 0

            # Select stories starting from current position, with a light source cap.
            num_to_select = min(num_stories, len(all_stories))
            selected = self._select_balanced_stories(all_stories, current_position, num_to_select)

            # Save next position for next time
            next_position = (current_position + num_to_select) % len(all_stories)
            self.save_state(next_position)

            logger.info(f"Loaded {num_to_select} stories (position {current_position}-{current_position + num_to_select - 1} of {len(all_stories)})")
            return selected

        except (TypeError, ValueError) as e:
            logger.error(f"Invalid news story data: {e}", exc_info=True)
            return []
        except OSError as e:
            logger.error(f"Error loading news: {e}", exc_info=True)
            return []

    def _news_data_file_candidates(self, story_file, cache_file, raw_story_file=None):
        candidates = [
            story_file,
            config.runtime_path('screens.news.story_file', 'news_stories.json'),
            config.runtime_path('screens.news.legacy_story_file', 'news_summaries.json'),
            raw_story_file or config.runtime_path('screens.news.raw_story_file', 'combined_news_recent.json'),
            cache_file,
        ]

        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if os.path.exists(candidate):
                yield candidate


    def _extract_stories(self, data):
        return extract_display_stories(data)

    @staticmethod
    def _fallback_summary(content):
        return fallback_summary(content)

    @staticmethod
    def _parse_story_datetime(story):
        return parse_story_datetime(story)

    def _filter_recent_stories(self, stories):
        max_age_days = config.get('screens.news.max_age_days', 7)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        recent = []

        for story in stories:
            story_date = self._parse_story_datetime(story)
            if story_date is None or story_date >= cutoff:
                recent.append(story)

        return recent

    def _select_balanced_stories(self, stories, current_position, num_to_select):
        max_per_source = config.get('screens.news.max_per_source_per_screen', 2)
        selected = []
        source_counts = {}
        attempts = 0
        index = current_position

        while len(selected) < num_to_select and attempts < len(stories) * 2:
            story = stories[index % len(stories)]
            source = story.get('source_site', 'unknown')

            if source_counts.get(source, 0) < max_per_source or len(stories) <= num_to_select:
                selected.append(story)
                source_counts[source] = source_counts.get(source, 0) + 1

            index += 1
            attempts += 1

        if len(selected) < num_to_select:
            selected_ids = {story.get('story_id') or story.get('headline') for story in selected}
            for story in stories:
                story_id = story.get('story_id') or story.get('headline')
                if story_id not in selected_ids:
                    selected.append(story)
                if len(selected) >= num_to_select:
                    break

        return selected

    def load_state(self):
        """Load the current position in the story cycle"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('current_position', 0)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"News state file is invalid; starting from first story: {e}")
        except OSError as e:
            logger.warning(f"Could not load news state: {e}")
        return 0

    def save_state(self, position):
        """Save the current position in the story cycle"""
        try:
            tmp_file = self.state_file + '.tmp'
            with open(tmp_file, 'w') as f:
                json.dump({'current_position': position}, f)
            os.replace(tmp_file, self.state_file)
        except OSError as e:
            logger.warning(f"Could not save news state: {e}")
