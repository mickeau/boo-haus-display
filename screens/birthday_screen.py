#!/usr/bin/env python3
"""
Birthday Screen for Boo Haus Display
Shows next 12 upcoming birthdays
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_screen import BaseScreen
from datetime import datetime, date
import json
import logging

logger = logging.getLogger(__name__)


class BirthdayScreen(BaseScreen):
    """Birthday tracker display"""
    
    @property
    def name(self) -> str:
        return "birthday"
    
    def render_content(self):
        """Render birthday tracker"""
        x, y, width, height = self.get_content_area()
        
        # Title
        current_y = self.draw_section_title("Upcoming Birthdays", y)
        
        # Get upcoming birthdays
        birthdays = self.get_upcoming_birthdays()
        
        if not birthdays:
            self.draw.text((x, current_y), "No birthday data available", 
                         font=self.font_medium, fill=self.BLACK)
            self.draw.text((x, current_y + 30), 
                         "Check birthdays.json file", 
                         font=self.font_tiny, fill=self.RED)
            return
        
        # Two-column layout
        col_width = (width - 30) // 2
        left_x = x
        right_x = x + col_width + 20
        
        # Draw vertical separator
        separator_x = x + col_width + 10
        self.draw.line([(separator_x, current_y), 
                      (separator_x, y + height)], 
                     fill=self.BLACK, width=2)
        
        # Split birthdays between columns
        mid_point = (len(birthdays) + 1) // 2
        left_birthdays = birthdays[:mid_point]
        right_birthdays = birthdays[mid_point:]
        
        # Draw left column
        left_y = self.draw_birthday_column(left_birthdays, left_x, current_y, 
                                          col_width, height)
        
        # Draw right column
        right_y = self.draw_birthday_column(right_birthdays, right_x, current_y, 
                                           col_width, height)
    
    def draw_birthday_column(self, birthdays, x, y, width, max_height):
        """Draw a column of birthdays"""
        current_y = y
        margin = 5
        
        for i, birthday in enumerate(birthdays):
            # Check available space
            if current_y - y > max_height - 60:
                break
            
            name = birthday['name']
            birth_date = birthday['date']
            days_until = birthday['days_until']
            
            # Color coding based on proximity
            if days_until == 0:
                date_color = self.YELLOW
                text_color = self.BLACK
            elif days_until == 1:
                date_color = self.RED
                text_color = self.WHITE
            elif days_until <= 7:
                date_color = self.BLUE
                text_color = self.WHITE
            elif days_until <= 30:
                date_color = self.GREEN
                text_color = self.WHITE
            else:
                date_color = self.BLACK
                text_color = self.WHITE
            
            # Date box (left side)
            box_width = 50
            box_height = 48
            
            self.draw.rectangle([x + margin, current_y, 
                               x + margin + box_width, current_y + box_height],
                              outline=self.BLACK, fill=date_color, width=2)
            
            # Day number
            day_num = birth_date.strftime('%d')
            self.draw.text((x + margin + 13, current_y + 6), day_num, 
                         font=self.font_medium, fill=text_color)
            
            # Month abbreviation
            month_str = birth_date.strftime('%b')
            self.draw.text((x + margin + 13, current_y + 28), month_str, 
                         font=self.font_tiny, fill=text_color)
            
            # Birthday details (right of date box)
            details_x = x + margin + box_width + 10
            details_width = width - box_width - margin * 2 - 10
            
            # Person's name
            name_lines = self.wrap_text(name, details_width, self.font_medium)
            name_display = name_lines[0] if name_lines else name
            if len(name_display) > 20:
                name_display = name_display[:20] + "..."
            
            self.draw.text((details_x, current_y + 2), name_display, 
                         font=self.font_medium, fill=self.BLACK)
            
            # Full date
            full_date = birth_date.strftime('%A, %B %d')
            self.draw.text((details_x, current_y + 30), full_date, 
                         font=self.font_small, fill=self.BLACK)
            
            # Days until text
            if days_until == 0:
                day_text = "TODAY!"
                day_color = self.BLACK
            elif days_until == 1:
                day_text = "TOMORROW"
                day_color = self.BLACK
            elif days_until <= 7:
                day_text = f"in {days_until} days"
                day_color = self.BLACK
            elif days_until <= 30:
                day_text = f"in {days_until} days"
                day_color = self.BLACK
            else:
                day_text = f"in {days_until} days"
                day_color = self.BLACK
            
            day_text_bbox = self.draw.textbbox((0, 0), day_text, font=self.font_small)
            day_text_width = day_text_bbox[2] - day_text_bbox[0]
            self.draw.text((x + width - day_text_width, current_y + 2), day_text, 
                         font=self.font_small, fill=day_color)
            
            # Calculate height used
            event_height = max(box_height, 50) + margin
            current_y += event_height
            
            # Separator line between birthdays
            if i < len(birthdays) - 1 and current_y < y + max_height - 60:
                self.draw.line([(x + margin + 5, current_y), 
                              (x + width - margin - 5, current_y)], 
                             fill=self.BLACK, width=1)
                current_y += 8
        
        return current_y
    
    def get_upcoming_birthdays(self):
        """Get next N upcoming birthdays"""
        try:
            # Get birthday file from config
            birthday_file = self.config.get('screens', {}).get('birthday', {}).get(
                'birthday_file', 'birthdays.json')
            
            max_birthdays = self.config.get('screens', {}).get('birthday', {}).get(
                'max_birthdays', 12)
            
            # Load birthday data
            if not os.path.exists(birthday_file):
                logger.error(f"Birthday file not found: {birthday_file}")
                return []
            
            with open(birthday_file, 'r', encoding='utf-8') as f:
                birthdays = json.load(f)
            
            today = date.today()
            current_year = today.year
            
            upcoming = []
            
            for birthday in birthdays:
                try:
                    month = birthday['month']
                    day = birthday['day']
                    
                    # Calculate next birthday
                    next_birthday = date(current_year, month, day)
                    
                    # If birthday already passed this year, use next year
                    if next_birthday < today:
                        next_birthday = date(current_year + 1, month, day)
                    
                    days_until = (next_birthday - today).days
                    
                    upcoming.append({
                        'name': birthday['name'],
                        'date': next_birthday,
                        'days_until': days_until,
                        'month': month,
                        'day': day
                    })
                except ValueError as e:
                    logger.warning(f"Invalid date for {birthday.get('name', 'Unknown')}: {month}/{day}")
                    continue
                except KeyError as e:
                    logger.warning(f"Missing field in birthday entry: {e}")
                    continue
            
            # Sort by days until birthday
            upcoming.sort(key=lambda x: x['days_until'])
            
            # Return up to max_birthdays
            result = upcoming[:max_birthdays]
            logger.info(f"Found {len(result)} upcoming birthdays")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing birthday file: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading birthdays: {e}", exc_info=True)
            return []
