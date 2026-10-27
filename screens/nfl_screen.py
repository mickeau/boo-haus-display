#!/usr/bin/env python3
"""
NFL Screen for Boo Haus Display
Shows current week's NFL scores, schedules, and bye teams
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_screen import BaseScreen
from datetime import datetime
import logging

from config import config

logger = logging.getLogger(__name__)


class NFLScreen(BaseScreen):
    """NFL scores and schedule display"""

    @property
    def name(self) -> str:
        return "nfl"

    def __init__(self):
        super().__init__()

    def is_enabled(self) -> bool:
        """Enabled only during NFL season (config dates, default Sep 1 - Feb 15)."""
        if not super().is_enabled():
            return False

        screen_cfg = self.config.get('screens', {}).get('nfl', {})
        season_start = screen_cfg.get('season_start', '09-01')  # MM-DD
        season_end = screen_cfg.get('season_end', '02-15')

        today = datetime.now().strftime('%m-%d')

        # Season wraps around the new year (Sep -> Feb)
        if season_start <= season_end:
            in_season = season_start <= today <= season_end
        else:
            in_season = today >= season_start or today <= season_end

        if not in_season:
            logger.info("NFL screen disabled — out of season")

        return in_season

    def render_content(self):
        """Render NFL scores and schedule"""
        try:
            from nfl_scores import NFLWeeklyDisplay

            # Get NFL data
            nfl = NFLWeeklyDisplay()
            week_label, games, bye_teams = nfl.get_games_list(format_type='inky')

            x, y, width, height = self.get_content_area()

            # Title with week number
            current_y = self.draw_section_title(f"NFL {week_label}", y)
            stale = self.draw_stale_note(nfl, y)

            if not games:
                # Old cached data filters down to nothing for the current week,
                # so "no games" would be misleading — say the data is old instead.
                message = ("NFL scores can't be refreshed — check the internet connection"
                           if stale else "No games found for this week")
                self.draw.text((x, current_y), message,
                             font=self.font_medium if not stale else self.font_small,
                             fill=self.RED if stale else self.BLACK)
                return

            # Calculate layout
            available_height = height - (current_y - y) - 40  # Leave space for bye teams

            # Two-column layout
            col_width = (width - 30) // 2
            left_x = x
            right_x = x + col_width + 20

            # Draw vertical separator
            separator_x = x + col_width + 10
            self.draw.line([(separator_x, current_y),
                          (separator_x, y + height - 30)],
                         fill=self.BLACK, width=2)

            # Split games between columns
            mid_point = (len(games) + 1) // 2
            left_games = games[:mid_point]
            right_games = games[mid_point:]

            # Draw left column
            left_y = self.draw_game_column(left_games, left_x, current_y,
                                          col_width, available_height)

            # Draw right column
            right_y = self.draw_game_column(right_games, right_x, current_y,
                                           col_width, available_height)

            # Draw bye teams at bottom
            bye_y = max(left_y, right_y, current_y + available_height) + 10
            if bye_teams and bye_y < y + height - 25:
                self.draw_bye_teams(bye_teams, x, bye_y, width)

        except Exception as e:
            logger.error(f"NFL data error: {e}", exc_info=True)
            x, y, _, _ = self.get_content_area()
            self.draw.text((x, y), f"NFL data unavailable",
                         font=self.font_medium, fill=self.RED)
            self.draw.text((x, y + 25), f"Error: {str(e)[:50]}",
                         font=self.font_tiny, fill=self.BLACK)

    def get_team_record(self, team_data):
        """Extract team record from competitor data"""
        if not isinstance(team_data, dict):
            return None

        # Try different possible record locations in ESPN API
        records = team_data.get('records', [])
        if records and isinstance(records, list) and isinstance(records[0], dict):
            record = records[0].get('summary', '')
            if record:
                return record

        # Method 2: direct record field
        if 'record' in team_data:
            return team_data['record']

        # Method 3: team.record
        team = team_data.get('team', {})
        if isinstance(team, dict) and 'record' in team:
            return team['record']

        return None

    def draw_game_column(self, games, x, y, width, max_height):
        """Draw a column of games"""
        current_y = y
        line_height = 18

        for i, game in enumerate(games):
            # Check if we have space
            if current_y - y > max_height - 25:
                break

            try:
                # Parse game data
                date = game['date']
                status = game['status']
                competition = game['competition']
                winner = game.get('winner')

                # Get team data
                home_team = competition['competitors'][0]
                away_team = competition['competitors'][1]

                home_name = home_team['team']['displayName']
                away_name = away_team['team']['displayName']
                home_score = home_team.get('score', '')
                away_score = away_team.get('score', '')

                # Get team records
                home_record = self.get_team_record(home_team)
                away_record = self.get_team_record(away_team)

                # Add records to names
                if home_record:
                    home_name = f"{home_name} ({home_record})"
                if away_record:
                    away_name = f"{away_name} ({away_record})"

                # Format day
                day_abbr = date.strftime('%a').upper()[:3]

                # Game status
                status_name = status['type']['name']
                is_final = status_name == 'STATUS_FINAL'
                is_live = status_name == 'STATUS_IN_PROGRESS'

                # Build display text
                if is_final:
                    status_text = "FINAL"
                    status_color = self.BLACK
                elif is_live:
                    period = status.get('period', '')
                    clock = status.get('displayClock', '')
                    quarter_map = {1: '1Q', 2: '2Q', 3: '3Q', 4: '4Q', 5: 'OT'}
                    quarter = quarter_map.get(period, f'Q{period}')
                    status_text = f"{quarter} {clock}" if clock else quarter
                    status_color = self.RED
                else:
                    # Scheduled game - show time
                    uk_time = date.astimezone()
                    time_str = uk_time.strftime('%H:%M')
                    status_text = time_str
                    status_color = self.BLACK

                # Draw game box
                box_height = 35

                # Highlight box if live
                if is_live:
                    self.draw.rectangle([x, current_y, x + width, current_y + box_height],
                                      fill=self.PALE_GREEN, outline=self.RED, width=2)

                # Day label
                self.draw.text((x + 3, current_y + 2), day_abbr,
                             font=self.font_tiny, fill=self.BLUE)

                # Teams and scores
                team_y = current_y + 2
                text_x = x + 50
                team_name_font = self.font_tiny

                # Away team
                away_text = away_name
                # away_text = self.shorten_team_name(away_name)
                if winner == 'away' and home_score and away_score:
                    # Bold winner by using black font
                    self.draw.text((text_x, team_y), away_text,
                                 font=team_name_font, fill=self.BLACK)
                else:
                    self.draw.text((text_x, team_y), away_text,
                                 font=team_name_font, fill=self.BLUE)

                # Away score
                if away_score:
                    score_x = x + width - 100
                    score_font = self.BLACK if winner == 'away' else self.BLUE
                    self.draw.text((score_x, team_y), str(away_score),
                                 font=team_name_font, fill=score_font)

                # @ symbol
                self.draw.text((text_x - 15, team_y + 16), "@",
                             font=self.font_tiny, fill=self.BLACK)

                # Home team
                team_y += 16
                home_text = home_name
                # home_text = self.shorten_team_name(home_name)
                if winner == 'home' and home_score and away_score:
                    self.draw.text((text_x, team_y), home_text,
                                 font=team_name_font, fill=self.BLACK)
                else:
                    self.draw.text((text_x, team_y), home_text,
                                 font=team_name_font, fill=self.BLUE)

                # Home score
                if home_score:
                    score_x = x + width - 100
                    score_font = self.BLACK if winner == 'home' else self.BLUE
                    self.draw.text((score_x, team_y), str(home_score),
                                 font=team_name_font, fill=score_font)

                # Status/time
                self.draw.text((x + width - 65, current_y + 2), status_text,
                             font=self.font_tiny, fill=status_color)

                current_y += box_height + 3
            except (KeyError, IndexError, AttributeError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed NFL game {game!r}: {e}")
                continue

            # Draw separator line between games
            if i < len(games):
                self.draw.line([(x + 5, current_y),
                              (x + width - 10, current_y)],
                             fill=self.BLACK, width=1)
                current_y += 3

        return current_y

    def shorten_team_name(self, full_name):
        """Shorten team names to fit better"""
        # Remove city for common long names
        replacements = {
            'Tampa Bay Buccaneers': 'Buccaneers',
            'Green Bay Packers': 'Packers',
            'Kansas City Chiefs': 'Chiefs',
            'San Francisco 49ers': '49ers',
            'Las Vegas Raiders': 'Raiders',
            'Los Angeles Rams': 'Rams',
            'Los Angeles Chargers': 'Chargers',
            'New England Patriots': 'Patriots',
            'New Orleans Saints': 'Saints',
            'New York Giants': 'Giants',
            'New York Jets': 'Jets',
        }

        short = replacements.get(full_name, full_name)

        # If still too long, truncate
        if len(short) > 15:
            short = short[:15]

        return short

    def draw_bye_teams(self, bye_teams, x, y, width):
        """Draw teams on bye week"""
        # Draw separator
        self.draw.line([(x, y), (x + width, y)], fill=self.BLACK, width=1)
        y += 8

        # Title
        self.draw.text((x, y), f"{len(bye_teams)} Teams on BYE:",
                     font=self.font_tiny, fill=self.BLUE)

        # Teams list (wrapped)
        bye_text = ", ".join(bye_teams)
        lines = self.wrap_text(bye_text, width - 10, self.font_tiny)

        for line in lines[:2]:  # Max 2 lines
            self.draw.text((x + 120, y), line,
                         font=self.font_tiny, fill=self.BLACK)
            y += 14
