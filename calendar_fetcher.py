#!/usr/bin/env python3
"""
Google Calendar Events Fetcher

This script fetches upcoming events from your Google Calendar using the Google Calendar API.
"""

import datetime
import os
import logging
from typing import List, Dict, Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_IMPORT_ERROR = None
except ImportError as e:
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None
    HttpError = Exception
    GOOGLE_IMPORT_ERROR = e

from config import config
from base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

class CalendarData(BaseFetcher):
    """Google Calendar data fetcher"""

    def __init__(self, calendar_ids: List[str]):
        super().__init__(cache_file="calendar_cache.json", cache_expiry_minutes=config.get('data_refresh.calendar_cache_expiry', 60))
        self.calendar_ids = calendar_ids
        self.credentials_file = config.runtime_path('screens.calendar.credentials_file', 'credentials.json')
        self.token_file = config.runtime_path('screens.calendar.token_file', 'token.json')
        self.service = None

    def authenticate(self):
        """Authenticate and return the Google Calendar service object."""
        if GOOGLE_IMPORT_ERROR is not None:
            logger.warning(f"Google Calendar dependencies unavailable: {GOOGLE_IMPORT_ERROR}")
            return False

        creds = None

        # The file token.json stores the user's access and refresh tokens.
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())

        self.service = build('calendar', 'v3', credentials=creds)
        return True

    def fetch_data(self, force_refresh=False, max_results=None, days_ahead=None):
        """Override to pass query parameters through to _fetch_data_from_source."""
        if max_results is not None:
            self._max_results = max_results
        if days_ahead is not None:
            self._days_ahead = days_ahead
        return super().fetch_data(force_refresh=force_refresh)

    def _fetch_data_from_source(self) -> Optional[List[Dict]]:
        """Fetch upcoming events from all configured calendars"""
        max_results = getattr(self, '_max_results', 10)
        days_ahead = getattr(self, '_days_ahead', 14)

        if not self.service:
            logger.error("Not authenticated. Call authenticate() first.")
            return None

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

                events = events_result.get('items', []) if isinstance(events_result, dict) else []
                if not isinstance(events, list):
                    logger.warning(f"Calendar {calendar_id} returned a malformed events list")
                    continue

                for event in events:
                    if not isinstance(event, dict):
                        logger.warning(f"Skipping malformed calendar event from {calendar_id}: {event!r}")
                        continue
                    event['calendar_id'] = calendar_id
                    all_events.append(event)

            except HttpError as e:
                logger.error(f"Error fetching from calendar {calendar_id}: {e}")

        # Sort by start time
        all_events.sort(key=self._get_event_start_time)
        return all_events[:max_results]

    def _get_event_start_time(self, event):
        try:
            start = event['start'].get('dateTime', event['start'].get('date'))
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

        except (KeyError, AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error parsing calendar event date: {e}")
            # Fallback: return current time
            return datetime.datetime.now(datetime.timezone.utc)

    def format_event_for_display(self, event: Dict) -> Dict:
        """Format a raw event dictionary for display on the screen."""
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))

        is_all_day = 'date' in event['start']

        event_datetime = self._get_event_start_time(event)
        today = datetime.datetime.now(datetime.timezone.utc).date()

        if is_all_day:
            # For all-day events, the 'date' is already local to the event's timezone
            # We just need to convert it to a date object for comparison
            event_date = datetime.datetime.strptime(start, '%Y-%m-%d').date()
            days_until = (event_date - today).days
            time_str = "All day"
        else:
            # For timed events, event_datetime is already timezone-aware
            days_until = (event_datetime.date() - today).days
            time_str = event_datetime.astimezone().strftime('%H:%M')

        return {
            'summary': event.get('summary', 'No Title'),
            'location': event.get('location', ''),
            'description': event.get('description', ''),
            'datetime': event_datetime,
            'time_str': time_str,
            'is_all_day': is_all_day,
            'days_until': days_until,
            'calendar_id': event.get('calendar_id', 'Unknown')
        }
