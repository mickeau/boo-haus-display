#!/usr/bin/env python3
"""
Google Calendar Events Fetcher

This script fetches upcoming events from your Google Calendar using the Google Calendar API.
"""

import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def authenticate_google_calendar():
    """Authenticate and return the Google Calendar service object."""
    creds = None
    
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('calendar', 'v3', credentials=creds)

def get_upcoming_events(service, calendar_id='primary', max_results=10, days_ahead=7):
    """Fetch upcoming events from the specified calendar."""
    try:
        # Call the Calendar API with timezone-aware datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        end_time = now + datetime.timedelta(days=days_ahead)
        
        # Format times in RFC3339 format
        time_min = now.isoformat()
        time_max = end_time.isoformat()
        
        print(f'Getting upcoming events from {now.strftime("%Y-%m-%d")} to {end_time.strftime("%Y-%m-%d")}')
        print(f'Calendar: {calendar_id}')
        
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            print('No upcoming events found.')
            return []
        
        return events
        
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def get_events_from_multiple_calendars(service, calendar_ids, max_results=10, days_ahead=7):
    """Fetch events from multiple calendars and combine them."""
    all_events = []
    
    for calendar_id in calendar_ids:
        try:
            events = get_upcoming_events(service, calendar_id, max_results, days_ahead)
            # Add calendar info to each event
            for event in events:
                event['calendar_id'] = calendar_id
            all_events.extend(events)
        except Exception as e:
            print(f"Error fetching events from calendar {calendar_id}: {e}")
    
    # Sort all events by start time with proper timezone handling
    def get_event_start_time(event):
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        try:
            if 'T' in start:  # It's a datetime
                # Handle timezone-aware datetimes
                if start.endswith('Z'):
                    # UTC timezone
                    dt = datetime.datetime.fromisoformat(start[:-1]).replace(tzinfo=datetime.timezone.utc)
                elif '+' in start or start.count('-') > 2:  # Has timezone offset
                    dt = datetime.datetime.fromisoformat(start)
                else:
                    # Assume UTC if no timezone info
                    dt = datetime.datetime.fromisoformat(start).replace(tzinfo=datetime.timezone.utc)
            else:  # It's a date (all-day event)
                # Convert date to datetime at start of day in UTC
                dt = datetime.datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
            
            return dt
            
        except Exception as e:
            print(f"Error parsing date '{start}': {e}")
            # Fallback: return current time
            return datetime.datetime.now(datetime.timezone.utc)
    
    all_events.sort(key=get_event_start_time)
    return all_events[:max_results]

def format_event_time(event):
    """Format event start time for display."""
    start = event['start'].get('dateTime', event['start'].get('date'))
    
    try:
        if 'T' in start:  # It's a datetime
            if start.endswith('Z'):
                # UTC timezone
                dt = datetime.datetime.fromisoformat(start[:-1]).replace(tzinfo=datetime.timezone.utc)
            elif '+' in start or start.count('-') > 2:  # Has timezone offset
                dt = datetime.datetime.fromisoformat(start)
            else:
                # Assume UTC if no timezone info
                dt = datetime.datetime.fromisoformat(start).replace(tzinfo=datetime.timezone.utc)
            
            # Convert to local time for display
            local_dt = dt.astimezone()
            return local_dt.strftime('%Y-%m-%d %H:%M')
        else:  # It's an all-day event
            return f"{start} (All day)"
    except Exception as e:
        print(f"Error formatting time '{start}': {e}")
        return start

def display_events(events, show_calendar_info=False):
    """Display events in a formatted way."""
    print(f'\nFound {len(events)} upcoming events:')
    print('-' * 60)
    
    for i, event in enumerate(events, 1):
        summary = event.get('summary', 'No Title')
        start_time = format_event_time(event)
        location = event.get('location', 'No location specified')
        description = event.get('description', 'No description')
        
        print(f"{i}. {summary}")
        print(f"   Time: {start_time}")
        print(f"   Location: {location}")
        
        # Show which calendar this event is from if multiple calendars
        if show_calendar_info and 'calendar_id' in event:
            print(f"   Calendar: {event['calendar_id']}")
        
        # Truncate long descriptions
        if len(description) > 100:
            description = description[:100] + "..."
        print(f"   Description: {description}")
        print()

def get_all_calendars(service):
    """Get list of all available calendars."""
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        return calendars
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def display_calendars(calendars):
    """Display available calendars."""
    print("Available calendars:")
    print('-' * 40)
    for calendar in calendars:
        print(f"- {calendar['summary']} (ID: {calendar['id']})")
        if calendar.get('primary'):
            print("  [PRIMARY CALENDAR]")
        print()

def main():
    """Main function to run the calendar fetcher."""
    print("Google Calendar Events Fetcher")
    print("=" * 40)
    
    try:
        # Authenticate and create service
        service = authenticate_google_calendar()
        print("Successfully authenticated with Google Calendar!")

        # Load calendar IDs from config file
        try:
            with open('boo_haus_config.json', 'r') as f:
                config = json.load(f)
            calendar_ids = config.get('screens', {}).get('calendar', {}).get('calendar_ids', [])

            if not calendar_ids:
                print("Error: Calendar IDs not found in boo_haus_config.json")
                print("Please add calendar IDs to config file under screens.calendar.calendar_ids")
                return
        except FileNotFoundError:
            print("Error: boo_haus_config.json not found")
            print("Please create config file from boo_haus_config.example.json")
            return

        print("Fetching events from configured calendars...")
        print()

        # Fetch events from the specified calendars
        events = get_events_from_multiple_calendars(service, calendar_ids, max_results=20, days_ahead=14)
        
        if events:
            display_events(events, show_calendar_info=True)
            
            # Optional: Export to a file
            export_choice = input("\nWould you like to export events to a text file? (y/n): ").lower()
            if export_choice == 'y':
                export_to_file(events)
        else:
            print("No upcoming events found in the specified calendars.")
            
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def export_to_file(events):
    """Export events to a text file."""
    filename = f"calendar_events_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("Google Calendar Events Export\n")
            f.write(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            
            for i, event in enumerate(events, 1):
                summary = event.get('summary', 'No Title')
                start_time = format_event_time(event)
                location = event.get('location', 'No location specified')
                description = event.get('description', 'No description')
                
                f.write(f"{i}. {summary}\n")
                f.write(f"   Time: {start_time}\n")
                f.write(f"   Location: {location}\n")
                f.write(f"   Description: {description}\n\n")
        
        print(f"Events exported to: {filename}")
        
    except Exception as e:
        print(f"Error exporting to file: {e}")

if __name__ == '__main__':
    main()