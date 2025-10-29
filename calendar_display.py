#!/usr/bin/env python3
"""
E-ink Calendar Display for Exmouth, Devon
Displays upcoming calendar events from Google Calendar

Requirements:
    pip install pillow google-auth-httplib2 google-auth-oauthlib google-api-python-client

For Raspberry Pi with Inky Impression 7.3" display, also install:
    pip install inky[rpi,example-depends]

Usage:
    python calendar_display.py [--display] [--save-image] [--max-events 10]
"""

import datetime
import os.path
import logging
import argparse
import sys
import re
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Google Calendar API scope
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

class CalendarData:
    """Google Calendar data fetcher"""
    
    def __init__(self, calendar_ids: List[str]):
        self.calendar_ids = calendar_ids
        self.service = None
    
    def authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('calendar', 'v3', credentials=creds)
        return True
    
    def _get_event_start_time(self, event: Dict) -> datetime.datetime:
        """Parse event start time"""
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        try:
            if 'T' in start:  # DateTime
                if start.endswith('Z'):
                    dt = datetime.datetime.fromisoformat(start[:-1]).replace(
                        tzinfo=datetime.timezone.utc)
                elif '+' in start or start.count('-') > 2:
                    dt = datetime.datetime.fromisoformat(start)
                else:
                    dt = datetime.datetime.fromisoformat(start).replace(
                        tzinfo=datetime.timezone.utc)
            else:  # Date (all-day event)
                dt = datetime.datetime.strptime(start, '%Y-%m-%d').replace(
                    tzinfo=datetime.timezone.utc)
            
            return dt
        except Exception as e:
            logger.error(f"Error parsing date '{start}': {e}")
            return datetime.datetime.now(datetime.timezone.utc)
    
    def get_events(self, max_results: int = 10, days_ahead: int = 14) -> List[Dict]:
        """Fetch upcoming events from all configured calendars"""
        if not self.service:
            logger.error("Not authenticated. Call authenticate() first.")
            return []
        
        all_events = []
        now = datetime.datetime.now(datetime.timezone.utc)
        end_time = now + datetime.timedelta(days=days_ahead)
        
        for calendar_id in self.calendar_ids:
            try:
                events_result = self.service.events().list(
                    calendarId=calendar_id,
                    timeMin=now.isoformat(),
                    timeMax=end_time.isoformat(),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                for event in events:
                    event['calendar_id'] = calendar_id
                all_events.extend(events)
                
            except HttpError as e:
                logger.error(f"Error fetching from calendar {calendar_id}: {e}")
        
        # Sort by start time
        all_events.sort(key=self._get_event_start_time)
        return all_events[:max_results]
    
    def format_event_for_display(self, event: Dict) -> Dict:
        """Format event data for display"""
        start = event['start'].get('dateTime', event['start'].get('date'))
        dt = self._get_event_start_time(event)
        
        # Convert to local time
        local_dt = dt.astimezone()
        
        # Determine if it's an all-day event
        is_all_day = 'date' in event['start']
        
        # Calculate days until event
        today = datetime.datetime.now().date()
        event_date = local_dt.date()
        days_until = (event_date - today).days
        
        return {
            'summary': event.get('summary', 'Untitled Event'),
            'location': event.get('location', ''),
            'datetime': local_dt,
            'is_all_day': is_all_day,
            'days_until': days_until,
            'date_str': local_dt.strftime('%a %d %b'),
            'time_str': '' if is_all_day else local_dt.strftime('%H:%M'),
            'description': event.get('description', '')
        }

class EInkCalendarDisplay:
    """Calendar display class for rendering to e-ink display"""
    
    def __init__(self, width: int = 800, height: int = 480):
        self.width = width
        self.height = height
        # Use RGB mode for color support on Inky
        self.image = Image.new('RGB', (width, height), (255, 255, 255))
        self.draw = ImageDraw.Draw(self.image)
        
        # Define Inky color palette
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.RED = (255, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.ORANGE = (255, 140, 0)
        self.GREEN = (0, 255, 0)
        self.BLUE = (0, 0, 255)
        self.PALE_GREEN = (200, 255, 200)  # Pale green for past events
        
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
    
    def _remove_emoji(self, text: str) -> str:
        """Remove emoji characters from text"""
        # Emoji pattern - covers most emoji ranges
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # extended symbols
            "\U00002600-\U000026FF"  # misc symbols
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text).strip()
    
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
    
    def _wrap_text(self, text: str, max_width: int, font: ImageFont.ImageFont) -> List[str]:
        """Wrap text to fit within max_width pixels"""
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
    
    def draw_event(self, event: Dict, x: int, y: int, width: int) -> int:
        """Draw a single event and return height used"""
        margin = 5
        current_y = y + margin
        
        # Date indicator (left side)
        date_x = x + margin
        
        # Color code based on how soon the event is
        days = event['days_until']
        if days < 0:
            box_color = self.PALE_GREEN  # Started in the past - pale green
            text_color = self.BLACK  # Black text on pale green
        elif days == 0:
            box_color = self.RED  # Today - red
            text_color = self.WHITE
        elif days == 1:
            box_color = self.ORANGE  # Tomorrow - orange
            text_color = self.WHITE
        else:
            box_color = self.BLUE  # Future - blue
            text_color = self.WHITE
        
        # Draw date box (smaller for two-column layout)
        box_width = 50
        box_height = 45
        self.draw.rectangle([date_x, current_y, date_x + box_width, current_y + box_height],
                          outline=self.BLACK, fill=box_color, width=2)
        
        # Day of month (large)
        day_num = event['datetime'].strftime('%d')
        self.draw.text((date_x + 12, current_y + 5), day_num, 
                      font=self.font_medium, fill=text_color)
        
        # Month (small, below)
        month_str = event['datetime'].strftime('%b')
        self.draw.text((date_x + 12, current_y + 27), month_str, 
                      font=self.font_tiny, fill=text_color)
        
        # Event details (right of date box)
        details_x = date_x + box_width + 10
        details_width = width - box_width - margin * 2 - 10
        
        # Event title (bold, single line only) - remove emoji
        title = self._remove_emoji(event['summary'])
        title_lines = self._wrap_text(title, details_width, self.font_small)
        title_display = title_lines[0] if title_lines else title
        if len(title_display) > 35:
            title_display = title_display[:35] + "..."
        self.draw.text((details_x, current_y + 2), title_display, font=self.font_small, fill=self.BLACK)
        current_y += 18
        
        # Time or "All day"
        if event['is_all_day']:
            time_text = "All day"
        else:
            time_text = event['time_str']
        
        # Days until indicator
        if days < 0:
            day_text = f"Started {abs(days)} days ago"
        elif days == 0:
            day_text = "Today"
        elif days == 1:
            day_text = "Tomorrow"
        else:
            day_text = f"in {days} days"
        
        time_info = f"{time_text} • {day_text}"
        self.draw.text((details_x, current_y + 2), time_info, font=self.font_tiny, fill=self.BLACK)
        current_y += 14
        
        # Location (if available) - shortened, in green, remove emoji
        if event['location']:
            location = self._remove_emoji(event['location'])
            location_lines = self._wrap_text(location, details_width, self.font_tiny)
            location_text = location_lines[0] if location_lines else ''
            if len(location_text) > 30:
                location_text = location_text[:30] + "..."
            self.draw.text((details_x, current_y + 2), location_text, 
                          font=self.font_tiny, fill=self.GREEN)
            current_y += 12
        
        # Calculate total height used
        total_height = max(box_height, current_y - y) + margin
        return total_height
    
    def render_calendar(self, events: List[Dict]):
        """Render the complete calendar display with two columns"""
        # Clear image
        self.draw.rectangle([0, 0, self.width, self.height], fill=self.WHITE)
        
        # Draw header
        self.draw_header()
        
        # Title
        title_y = 60
        self.draw.text((10, title_y), "Upcoming Events at Boo Haus", font=self.font_large, fill=self.BLACK)
        
        # Draw border around title
        self.draw.line([(10, title_y + 30), (self.width - 10, title_y + 30)], 
                      fill=self.BLACK, width=1)
        
        if not events:
            self.draw.text((10, title_y + 50), "No upcoming events", 
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
        
        # Split events into two columns
        mid_point = (len(events) + 1) // 2
        left_events = events[:mid_point]
        right_events = events[mid_point:]
        
        # Draw left column
        current_y_left = content_y
        available_height = content_height
        
        for i, event in enumerate(left_events):
            if available_height < 60:
                break
            
            event_height = self.draw_event(event, column_x_left, current_y_left, column_width)
            current_y_left += event_height
            available_height -= event_height
            
            # Draw separator line between events
            if i < len(left_events) - 1 and available_height > 60:
                self.draw.line([(column_x_left + 5, current_y_left), 
                              (column_x_left + column_width - 5, current_y_left)], 
                             fill=self.BLACK, width=1)
                current_y_left += 8
                available_height -= 8
        
        # Draw right column
        current_y_right = content_y
        available_height = content_height
        
        for i, event in enumerate(right_events):
            if available_height < 60:
                break
            
            event_height = self.draw_event(event, column_x_right, current_y_right, column_width)
            current_y_right += event_height
            available_height -= event_height
            
            # Draw separator line between events
            if i < len(right_events) - 1 and available_height > 60:
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
    parser = argparse.ArgumentParser(description='E-ink Calendar Display for Exmouth')
    parser.add_argument('--display', action='store_true',
                       help='Display on Inky screen (Raspberry Pi)')
    parser.add_argument('--save-image', action='store_true',
                       help='Save display as PNG image')
    parser.add_argument('--image-file', default='calendar_display.png',
                       help='Output image filename')
    parser.add_argument('--max-events', type=int, default=10,
                       help='Maximum number of events to display (default: 10)')
    parser.add_argument('--days-ahead', type=int, default=14,
                       help='Number of days ahead to fetch events (default: 14)')
    
    args = parser.parse_args()
    
    print("📅 Exmouth E-ink Calendar Display")
    print("=" * 40)

    # Load calendar IDs from config file
    try:
        with open('boo_haus_config.json', 'r') as f:
            config = json.load(f)
        calendar_ids = config.get('screens', {}).get('calendar', {}).get('calendar_ids', [])

        if not calendar_ids:
            print("Error: Calendar IDs not found in boo_haus_config.json")
            print("Please add calendar IDs to config file under screens.calendar.calendar_ids")
            sys.exit(1)
    except FileNotFoundError:
        print("Error: boo_haus_config.json not found")
        print("Please create config file from boo_haus_config.example.json")
        sys.exit(1)

    # Fetch calendar events
    print("📡 Authenticating with Google Calendar...")
    calendar = CalendarData(calendar_ids)
    
    try:
        calendar.authenticate()
        print("✅ Authentication successful")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print("Make sure credentials.json exists in the current directory")
        sys.exit(1)
    
    print(f"📡 Fetching events for next {args.days_ahead} days...")
    events = calendar.get_events(args.max_events, args.days_ahead)
    
    if not events:
        print("⚠️  No upcoming events found")
    
    # Format events for display
    formatted_events = [calendar.format_event_for_display(event) for event in events]
    
    # Create display
    print("🎨 Rendering calendar display...")
    display = EInkCalendarDisplay()
    image = display.render_calendar(formatted_events)
    
    # Save image if requested
    if args.save_image:
        try:
            image.save(args.image_file)
            print(f"💾 Display saved as {args.image_file}")
        except Exception as e:
            print(f"❌ Error saving image: {e}")
    
    # Display on Inky if requested
    if args.display:
        try:
            from inky.auto import auto
            from PIL import Image
            
            print("🖥️  Initializing Inky Impression 7.3\" display...")
            
            inky = auto(ask_user=True, verbose=True)
            # Image is already in RGB format, so no conversion needed
            inky.set_image(image)
            inky.show()
            
            print("✅ Calendar displayed on Inky screen")
            
        except ImportError:
            print("⚠️  Inky display library not installed.")
            print("    Install with: pip install inky[rpi,example-depends]")
        except Exception as e:
            print(f"❌ Inky display error: {e}")
    
    # Show summary
    print("\n📊 Display Summary:")
    print(f"   Events displayed: {len(formatted_events)}")
    for i, event in enumerate(formatted_events, 1):
        print(f"   {i}. {event['summary']} - {event['date_str']}")
    
    print("\n✅ Calendar display update complete!")

if __name__ == "__main__":
    main()