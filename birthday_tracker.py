#!/usr/bin/env python3
"""
E-ink Birthday Display for Exmouth, Devon
Displays upcoming birthdays from a JSON file

Requirements:
    pip install pillow

For Raspberry Pi with Inky Impression 7.3" display, also install:
    pip install inky[rpi,example-depends]

Usage:
    python birthday_display.py [--display] [--save-image] [--max-birthdays 10]
"""

import datetime
import json
import logging
import argparse
import sys
import os
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BirthdayData:
    """Birthday data loader from JSON file"""
    
    def __init__(self, json_file: str = 'birthdays.json'):
        self.json_file = json_file
        self.birthdays = []
    
    def load_birthdays(self) -> bool:
        """Load birthdays from JSON file"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                self.birthdays = json.load(f)
            logger.info(f"Loaded {len(self.birthdays)} birthdays from {self.json_file}")
            return True
        except FileNotFoundError:
            logger.error(f"Birthday file not found: {self.json_file}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON file: {e}")
            return False
    
    def get_upcoming_birthdays(self, max_count: int = 10) -> List[Dict]:
        """Get the next N upcoming birthdays"""
        today = datetime.date.today()
        current_year = today.year
        
        upcoming = []
        
        for birthday in self.birthdays:
            month = birthday['month']
            day = birthday['day']
            
            # Calculate next birthday
            try:
                next_birthday = datetime.date(current_year, month, day)
                
                # If birthday already passed this year, use next year
                if next_birthday < today:
                    next_birthday = datetime.date(current_year + 1, month, day)
                
                days_until = (next_birthday - today).days
                
                upcoming.append({
                    'name': birthday['name'],
                    'date': next_birthday,
                    'days_until': days_until,
                    'month': month,
                    'day': day
                })
            except ValueError:
                logger.warning(f"Invalid date for {birthday['name']}: {month}/{day}")
                continue
        
        # Sort by days until birthday
        upcoming.sort(key=lambda x: x['days_until'])
        
        return upcoming[:max_count]

class EInkBirthdayDisplay:
    """Birthday display class for rendering to e-ink display"""
    
    def __init__(self, width: int = 800, height: int = 480):
        self.width = width
        self.height = height
        # Use RGB mode for color support on Inky
        self.image = Image.new('RGB', (width, height), (255, 255, 255))
        self.draw = ImageDraw.Draw(self.image)
        
        # Define Inky color palette (matching calendar display)
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.RED = (255, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.ORANGE = (255, 140, 0)
        self.GREEN = (0, 255, 0)
        self.BLUE = (0, 0, 255)
        self.PINK = (255, 192, 203)
        
        # Load fonts
        self.font_large = self._load_font(24)
        self.font_medium = self._load_font(18)
        self.font_small = self._load_font(14)
        self.font_tiny = self._load_font(12)
    
    def _load_font(self, size: int) -> ImageFont.ImageFont:
        """Load font with fallback to default"""
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Arial.ttf",
        ]
        
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            except:
                continue
        
        return ImageFont.load_default()
    
    def draw_header(self):
        """Draw the header with location, date, and time"""
        now = datetime.datetime.now()
        
        # Location (top left) - in blue
        self.draw.text((10, 5), "Exmouth, Devon", font=self.font_medium, fill=self.BLUE)
        
        # Date and time (top right)
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%H:%M")
        
        date_bbox = self.draw.textbbox((0, 0), date_str, font=self.font_small)
        time_bbox = self.draw.textbbox((0, 0), time_str, font=self.font_medium)
        
        date_width = date_bbox[2] - date_bbox[0]
        time_width = time_bbox[2] - time_bbox[0]
        
        self.draw.text((self.width - date_width - 10, 5), date_str, 
                      font=self.font_small, fill=self.BLACK)
        self.draw.text((self.width - time_width - 10, 25), time_str, 
                      font=self.font_medium, fill=self.BLACK)
        
        # Draw separator line
        self.draw.line([(0, 50), (self.width, 50)], fill=self.BLACK, width=2)
    
    def draw_birthday(self, birthday: Dict, x: int, y: int, width: int) -> int:
        """Draw a single birthday and return height used"""
        margin = 5
        current_y = y + margin
        
        # Date indicator (left side)
        date_x = x + margin
        
        # Color code based on how soon the birthday is
        days = birthday['days_until']
        if days == 0:
            box_color = self.RED  # Today - red
            text_color = self.WHITE
        elif days == 1:
            box_color = self.ORANGE  # Tomorrow - orange
            text_color = self.WHITE
        elif days <= 7:
            box_color = self.PINK  # This week - pink
            text_color = self.BLACK
        else:
            box_color = self.BLUE  # Future - blue
            text_color = self.WHITE
        
        # Draw date box
        box_width = 50
        box_height = 45
        self.draw.rectangle([date_x, current_y, date_x + box_width, current_y + box_height],
                          outline=self.BLACK, fill=box_color, width=2)
        
        # Day of month (large)
        day_num = birthday['date'].strftime('%d')
        self.draw.text((date_x + 12, current_y + 5), day_num, 
                      font=self.font_medium, fill=text_color)
        
        # Month (small, below)
        month_str = birthday['date'].strftime('%b')
        self.draw.text((date_x + 12, current_y + 27), month_str, 
                      font=self.font_tiny, fill=text_color)
        
        # Birthday details (right of date box)
        details_x = date_x + box_width + 10
        details_width = width - box_width - margin * 2 - 10
        
        # Person's name (bold)
        name = birthday['name']
        if len(name) > 35:
            name = name[:35] + "..."
        self.draw.text((details_x, current_y + 2), name, font=self.font_small, fill=self.BLACK)
        current_y += 18
        
        # Days until indicator
        if days == 0:
            day_text = "Today! 🎉"
        elif days == 1:
            day_text = "Tomorrow"
        else:
            day_text = f"in {days} days"
        
        # Full date display
        full_date = birthday['date'].strftime('%A, %B %d')
        info_text = f"{full_date} • {day_text}"
        self.draw.text((details_x, current_y + 2), info_text, font=self.font_tiny, fill=self.BLACK)
        current_y += 14
        
        # Calculate total height used
        total_height = max(box_height, current_y - y) + margin
        return total_height
    
    def render_birthdays(self, birthdays: List[Dict]):
        """Render the complete birthday display with two columns"""
        # Clear image
        self.draw.rectangle([0, 0, self.width, self.height], fill=self.WHITE)
        
        # Draw header
        self.draw_header()
        
        # Title
        title_y = 60
        self.draw.text((10, title_y), "Upcoming Birthdays at Boo Haus", font=self.font_large, fill=self.BLACK)
        
        # Draw border around title
        self.draw.line([(10, title_y + 30), (self.width - 10, title_y + 30)], 
                      fill=self.BLACK, width=1)
        
        if not birthdays:
            self.draw.text((10, title_y + 50), "No upcoming birthdays", 
                         font=self.font_medium, fill=self.BLACK)
            return self.image
        
        # Calculate available space and column dimensions
        content_y = title_y + 40
        content_height = self.height - content_y - 10
        
        # Two columns with vertical divider
        column_width = (self.width - 30) // 2  # 30px for margins and divider
        column_x_left = 10
        column_x_right = column_x_left + column_width + 10
        
        # Draw vertical divider between columns
        divider_x = column_x_left + column_width + 5
        self.draw.line([(divider_x, content_y), (divider_x, self.height - 10)], 
                      fill=self.BLACK, width=1)
        
        # Split birthdays into two columns
        mid_point = (len(birthdays) + 1) // 2
        left_birthdays = birthdays[:mid_point]
        right_birthdays = birthdays[mid_point:]
        
        # Draw left column
        current_y_left = content_y
        available_height = content_height
        
        for i, birthday in enumerate(left_birthdays):
            if available_height < 60:
                break
            
            birthday_height = self.draw_birthday(birthday, column_x_left, current_y_left, column_width)
            current_y_left += birthday_height
            available_height -= birthday_height
            
            # Draw separator line between birthdays
            if i < len(left_birthdays) - 1 and available_height > 60:
                self.draw.line([(column_x_left + 5, current_y_left), 
                              (column_x_left + column_width - 5, current_y_left)], 
                             fill=self.BLACK, width=1)
                current_y_left += 8
                available_height -= 8
        
        # Draw right column
        current_y_right = content_y
        available_height = content_height
        
        for i, birthday in enumerate(right_birthdays):
            if available_height < 60:
                break
            
            birthday_height = self.draw_birthday(birthday, column_x_right, current_y_right, column_width)
            current_y_right += birthday_height
            available_height -= birthday_height
            
            # Draw separator line between birthdays
            if i < len(right_birthdays) - 1 and available_height > 60:
                self.draw.line([(column_x_right + 5, current_y_right), 
                              (column_x_right + column_width - 5, current_y_right)], 
                             fill=self.BLACK, width=1)
                current_y_right += 8
                available_height -= 8
        
        # Draw border around content area
        self.draw.rectangle([5, content_y - 5, self.width - 5, self.height - 5], 
                          outline=self.BLACK, width=1)
        
        return self.image

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='E-ink Birthday Display for Exmouth')
    parser.add_argument('--display', action='store_true',
                       help='Display on Inky screen (Raspberry Pi)')
    parser.add_argument('--save-image', action='store_true',
                       help='Save display as PNG image')
    parser.add_argument('--image-file', default='birthday_display.png',
                       help='Output image filename')
    parser.add_argument('--max-birthdays', type=int, default=10,
                       help='Maximum number of birthdays to display (default: 10)')
    parser.add_argument('--json-file', default='birthdays.json',
                       help='JSON file containing birthdays (default: birthdays.json)')
    
    args = parser.parse_args()
    
    print("Birthday E-ink Display")
    print("=" * 40)
    
    # Load birthday data
    print(f"Loading birthdays from {args.json_file}...")
    birthday_data = BirthdayData(args.json_file)
    
    if not birthday_data.load_birthdays():
        print(f"Failed to load birthdays from {args.json_file}")
        sys.exit(1)
    
    print("Calculating upcoming birthdays...")
    upcoming = birthday_data.get_upcoming_birthdays(args.max_birthdays)
    
    if not upcoming:
        print("No upcoming birthdays found")
    
    # Create display
    print("Rendering birthday display...")
    display = EInkBirthdayDisplay()
    image = display.render_birthdays(upcoming)
    
    # Save image if requested
    if args.save_image:
        try:
            image.save(args.image_file)
            print(f"Display saved as {args.image_file}")
        except Exception as e:
            print(f"Error saving image: {e}")
    
    # Display on Inky if requested
    if args.display:
        try:
            from inky.auto import auto
            
            print("Initializing Inky Impression 7.3\" display...")
            
            inky = auto(ask_user=True, verbose=True)
            inky.set_image(image)
            inky.show()
            
            print("Birthday display shown on Inky screen")
            
        except ImportError:
            print("Inky display library not installed.")
            print("    Install with: pip install inky[rpi,example-depends]")
        except Exception as e:
            print(f"Inky display error: {e}")
    
    # Show summary
    print("\nDisplay Summary:")
    print(f"   Birthdays displayed: {len(upcoming)}")
    for i, birthday in enumerate(upcoming, 1):
        date_str = birthday['date'].strftime('%b %d')
        print(f"   {i}. {birthday['name']} - {date_str} (in {birthday['days_until']} days)")
    
    print("\nBirthday display update complete!")

if __name__ == "__main__":
    main()