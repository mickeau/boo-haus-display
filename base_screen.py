#!/usr/bin/env python3
"""
Base Screen Class for Boo Haus Display System
Handles common header, layout, and utilities
UPDATED: Improved header with pastel blue background and centered special messages
"""

import os
from datetime import datetime, date
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from abc import ABC, abstractmethod


class BaseScreen(ABC):
    """Base class for all display screens"""
    
    # Color palette (matching Inky Impression)
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    YELLOW = (255, 255, 0)
    ORANGE = (255, 140, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    PINK = (255, 192, 203)
    PALE_GREEN = (200, 255, 200)
    
    # NEW: Pastel blue for header
    PASTEL_BLUE = (86, 108, 230)  # Light blue
    
    def __init__(self, config: dict):
        self.config = config
        self.width = config.get('display', {}).get('width', 800)
        self.height = config.get('display', {}).get('height', 480)
        
        # Create image and draw objects
        self.image = Image.new('RGB', (self.width, self.height), self.WHITE)
        self.draw = ImageDraw.Draw(self.image)
        
        # Load fonts - INCREASED SIZES
        self.font_title = self._load_font(30)      # Was 26, now 30
        self.font_large = self._load_font(28)      # Was 24, now 28
        self.font_medium = self._load_font(22)     # Was 18, now 22
        self.font_small = self._load_font(18)      # Was 14, now 18
        self.font_tiny = self._load_font(14)       # Was 12, now 14
        
        # NEW: Font for special messages (even larger)
        self.font_special = self._load_font(24)    # For special day messages
        
        # Header dimensions - INCREASED HEIGHT for larger text
        self.header_height = 70  # Was 55, now 70
        self.content_start_y = self.header_height + 5
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Screen name/identifier"""
        pass
    
    def is_enabled(self) -> bool:
        """Check if this screen is enabled in config"""
        screen_config = self.config.get('screens', {}).get(self.name.lower(), {})
        return screen_config.get('enabled', True)
    
    def _load_font(self, size: int) -> ImageFont.ImageFont:
        """Load font with fallback to default"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Arial.ttf",
        ]
        
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            except:
                continue
        
        return ImageFont.load_default()
    
    def get_special_greeting(self) -> Optional[str]:
        """Get special greeting for current date if any"""
        now = datetime.now()
        today_key = now.strftime('%d-%m')  # Format: DD-MM
        
        special_dates = self.config.get('special_dates', {})
        
        # Check for exact date match
        if today_key in special_dates:
            return special_dates[today_key]
        
        # Check for Easter (more complex calculation)
        if self._is_easter():
            return special_dates.get('easter', 'Happy Easter!')
        
        return None
    
    def _is_easter(self) -> bool:
        """Check if today is Easter Sunday"""
        # Simple check - could be enhanced with proper Easter calculation
        # For now, just return False
        # You could add python-dateutil and use easter(year)
        return False
    
    def draw_header(self):
        """Draw the standard header with pastel blue background and centered special greeting"""
        # Draw pastel blue background for header
        self.draw.rectangle([0, 0, self.width, self.header_height], 
                          fill=self.PASTEL_BLUE, outline=self.BLACK, width=2)
        
        now = datetime.now()
        
        # Check for special greeting
        greeting = self.get_special_greeting()
        
        if greeting:
            # LAYOUT WITH SPECIAL GREETING (3 lines)
            
            # Line 1: Title on left
            self.draw.text((15, 8), "Boo Haus Admin", 
                         font=self.font_medium, fill=self.BLACK)
            
            # Line 1: Date on right
            date_str = now.strftime("%A, %B %d")
            date_bbox = self.draw.textbbox((0, 0), date_str, font=self.font_small)
            date_width = date_bbox[2] - date_bbox[0]
            self.draw.text((self.width - date_width - 15, 8), date_str, 
                         font=self.font_small, fill=self.BLACK)
            
            # Line 2: SPECIAL GREETING CENTERED (larger)
            greeting_bbox = self.draw.textbbox((0, 0), greeting, font=self.font_special)
            greeting_width = greeting_bbox[2] - greeting_bbox[0]
            greeting_x = (self.width - greeting_width) // 2
            self.draw.text((greeting_x, 32), greeting, 
                         font=self.font_special, fill=self.WHITE)
            
        else:
            # LAYOUT WITHOUT SPECIAL GREETING (2 lines)
            
            # Line 1: Title on left
            self.draw.text((15, 16), "Boo Haus Admin", 
                         font=self.font_title, fill=self.BLACK)
            
            # Line 1: Date on right
            date_str = now.strftime("%A, %B %d")
            date_bbox = self.draw.textbbox((0, 0), date_str, font=self.font_medium)
            date_width = date_bbox[2] - date_bbox[0]
            self.draw.text((self.width - date_width - 15, 20), date_str, 
                         font=self.font_medium, fill=self.BLACK)
    
    def draw_section_title(self, title: str, y: int, color: Tuple = None) -> int:
        """Draw a section title and return the Y position after it"""
        if color is None:
            color = self.BLACK
        
        self.draw.text((15, y), title, font=self.font_large, fill=color)
        
        # Draw underline
        title_bbox = self.draw.textbbox((15, y), title, font=self.font_large)
        line_y = title_bbox[3] + 5
        self.draw.line([(15, line_y), (self.width - 15, line_y)], 
                      fill=color, width=2)
        
        return line_y + 10
    
    def wrap_text(self, text: str, max_width: int, font: ImageFont.ImageFont) -> list:
        """Wrap text to fit within max_width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = self.draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def draw_text_box(self, text: str, x: int, y: int, width: int, 
                     font: ImageFont.ImageFont, color: Tuple = None) -> int:
        """Draw text in a box with wrapping, return height used"""
        if color is None:
            color = self.BLACK
        
        lines = self.wrap_text(text, width, font)
        current_y = y
        
        for line in lines:
            self.draw.text((x, current_y), line, font=font, fill=color)
            bbox = self.draw.textbbox((x, current_y), line, font=font)
            current_y = bbox[3] + 2
        
        return current_y - y
    
    def draw_icon_with_label(self, icon_text: str, label: str, value: str,
                            x: int, y: int, icon_color: Tuple = None) -> int:
        """Draw an icon (emoji/symbol), label, and value. Return width used."""
        if icon_color is None:
            icon_color = self.BLACK
        
        # Draw icon
        self.draw.text((x, y), icon_text, font=self.font_medium, fill=icon_color)
        icon_bbox = self.draw.textbbox((x, y), icon_text, font=self.font_medium)
        
        # Draw label and value next to icon
        text_x = icon_bbox[2] + 5
        self.draw.text((text_x, y), label, font=self.font_small, fill=self.BLACK)
        
        label_bbox = self.draw.textbbox((text_x, y), label, font=self.font_small)
        value_x = label_bbox[2] + 5
        self.draw.text((value_x, y), value, font=self.font_medium, fill=icon_color)
        
        value_bbox = self.draw.textbbox((value_x, y), value, font=self.font_medium)
        return value_bbox[2] - x
    
    def draw_weather_icon(self, description: str, x: int, y: int, size: int = 50):
        """Draw a simple weather icon based on description"""
        # Simple text-based weather icons
        # In a real implementation, you might use actual icon images
        desc_lower = description.lower()
        
        if 'clear' in desc_lower or 'sun' in desc_lower:
            icon = '☀'
            color = self.YELLOW
        elif 'cloud' in desc_lower:
            icon = '☁'
            color = self.BLACK
        elif 'rain' in desc_lower:
            icon = '🌧'
            color = self.BLUE
        elif 'snow' in desc_lower:
            icon = '❄'
            color = self.BLUE
        elif 'storm' in desc_lower or 'thunder' in desc_lower:
            icon = '⛈'
            color = self.BLACK
        else:
            icon = '🌤'
            color = self.BLACK
        
        # Draw icon
        try:
            icon_font = self._load_font(size)
            self.draw.text((x, y), icon, font=icon_font, fill=color)
        except:
            # Fallback to text if emoji not supported
            self.draw.text((x, y), description[:10], font=self.font_small, fill=color)
    
    @abstractmethod
    def render_content(self):
        """Render the screen-specific content. Must be implemented by subclasses."""
        pass
    
    def render(self) -> Image.Image:
        """Main render method - draws header then content"""
        # Clear image
        self.image = Image.new('RGB', (self.width, self.height), self.WHITE)
        self.draw = ImageDraw.Draw(self.image)
        
        # Draw header
        self.draw_header()
        
        # Draw content (implemented by subclass)
        try:
            self.render_content()
        except Exception as e:
            # Draw error message if content rendering fails
            error_msg = f"Error rendering {self.name}: {str(e)}"
            self.draw.text((15, self.content_start_y), error_msg, 
                         font=self.font_small, fill=self.RED)
        
        return self.image
    
    def get_content_area(self) -> Tuple[int, int, int, int]:
        """Get the content area coordinates (x, y, width, height)"""
        padding = 15
        return (
            padding,
            self.content_start_y,
            self.width - (2 * padding),
            self.height - self.content_start_y - padding
        )
