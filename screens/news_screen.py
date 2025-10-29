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

logger = logging.getLogger(__name__)


class NewsScreen(BaseScreen):
    """News summaries display"""
    
    @property
    def name(self) -> str:
        return "news"
    
    def __init__(self, config):
        super().__init__(config)
        self.state_file = "news_display_state.json"
    
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
            # Get cache file from config
            cache_file = self.config.get('screens', {}).get('news', {}).get(
                'cache_file', 'headline_summaries_cache.json')
            
            num_stories = self.config.get('screens', {}).get('news', {}).get(
                'stories_per_screen', 4)
            
            # Load cache file
            if not os.path.exists(cache_file):
                logger.error(f"News cache file not found: {cache_file}")
                return []
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract stories from summaries
            if not isinstance(data, dict) or 'summaries' not in data:
                logger.error("Invalid cache file format")
                return []
            
            summaries = data['summaries']
            
            # Convert to list of stories
            all_stories = []
            for story_id, story_data in summaries.items():
                if 'original_title' in story_data and 'summary' in story_data:
                    all_stories.append({
                        'headline': story_data['original_title'],
                        'summary': story_data['summary'],
                        'generated_at': story_data.get('generated_at', '')
                    })
            
            if not all_stories:
                logger.error("No valid stories in cache")
                return []
            
            # Load current position from state
            current_position = self.load_state()
            
            # Ensure position is valid
            if current_position >= len(all_stories):
                current_position = 0
            
            # Select stories starting from current position
            num_to_select = min(num_stories, len(all_stories))
            selected = []
            
            for i in range(num_to_select):
                index = (current_position + i) % len(all_stories)
                selected.append(all_stories[index])
            
            # Save next position for next time
            next_position = (current_position + num_to_select) % len(all_stories)
            self.save_state(next_position)
            
            logger.info(f"Loaded {num_to_select} stories (position {current_position}-{current_position + num_to_select - 1} of {len(all_stories)})")
            return selected
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing news cache: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading news: {e}", exc_info=True)
            return []
    
    def load_state(self):
        """Load the current position in the story cycle"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('current_position', 0)
        except Exception as e:
            logger.warning(f"Could not load news state: {e}")
        return 0
    
    def save_state(self, position):
        """Save the current position in the story cycle"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({'current_position': position}, f)
        except Exception as e:
            logger.warning(f"Could not save news state: {e}")
