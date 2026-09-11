from datetime import datetime, timedelta
import pytz
from PIL import Image, ImageDraw, ImageFont

import logging

from config import config
from base_fetcher import BaseFetcher, http_get_json, network_disabled

logger = logging.getLogger(__name__)

class NFLWeeklyDisplay(BaseFetcher):
    def __init__(self):
        super().__init__(cache_file="nfl_cache.json", cache_expiry_minutes=config.get('data_refresh.nfl_cache_expiry', 120))
        self.base_url = "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        self.all_nfl_teams = [
            "Arizona Cardinals", "Atlanta Falcons", "Baltimore Ravens", "Buffalo Bills",
            "Carolina Panthers", "Chicago Bears", "Cincinnati Bengals", "Cleveland Browns",
            "Dallas Cowboys", "Denver Broncos", "Detroit Lions", "Green Bay Packers",
            "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Kansas City Chiefs",
            "Las Vegas Raiders", "Los Angeles Chargers", "Los Angeles Rams", "Miami Dolphins",
            "Minnesota Vikings", "New England Patriots", "New Orleans Saints", "New York Giants",
            "New York Jets", "Philadelphia Eagles", "Pittsburgh Steelers", "San Francisco 49ers",
            "Seattle Seahawks", "Tampa Bay Buccaneers", "Tennessee Titans", "Washington Commanders"
        ]

    def _fetch_data_from_source(self):
        """Fetch scoreboard data from ESPN API"""
        data = http_get_json(self.base_url, timeout=15, description="ESPN NFL scoreboard")
        if data is not None:
            logger.info("Successfully fetched NFL scoreboard data.")
        return data

    def get_week_label(self, data):
        """Extract the week label from ESPN API data"""
        if not isinstance(data, dict):
            return "Current Week"

        week = data.get('week')
        if not isinstance(week, dict):
            return "Current Week"

        season = data.get('season', {})
        season_type = season.get('type', 2) if isinstance(season, dict) else 2
        week_number = week.get('number', 1)

        if season_type == 3:
            playoff_rounds = {
                1: "Wild Card", 2: "Divisional", 3: "Conference Champ",
                4: "Pro Bowl", 5: "Super Bowl"
            }
            return playoff_rounds.get(week_number, f"Postseason Wk {week_number}")
        elif season_type == 1:
            return f"Preseason Wk {week_number}"
        else:
            return f"Week {week_number}"

    def is_current_week(self, game_date_str):
        """Check if game is in current week (Wednesday to Tuesday)"""
        game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
        now = datetime.now(game_date.tzinfo)

        days_since_wednesday = (now.weekday() - 2) % 7
        week_start = (now - timedelta(days=days_since_wednesday)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        return week_start <= game_date < week_end

    def get_team_record(self, team_data):
        """Extract team record if available"""
        if not isinstance(team_data, dict):
            return ""

        records = team_data.get('records', [])
        if isinstance(records, list) and records and isinstance(records[0], dict):
            summary = records[0].get('summary', '')
            return f" ({summary})" if summary else ""
        return ""

    def get_uk_timezone(self, dt):
        """Determine if UK is on BST or GMT based on the date"""
        # pytz handles DST automatically, we just need to check the timezone offset
        london_tz = pytz.timezone('Europe/London')
        dt_london = dt.astimezone(london_tz)

        # Check if DST is in effect (BST has UTC+1, GMT has UTC+0)
        offset = dt_london.utcoffset().total_seconds() / 3600
        return 'BST' if offset == 1 else 'GMT'

    def format_game_line(self, competition, status, game_date, format_type='terminal'):
        """Format game as single line: [DAY] [matchup] [time/status]"""
        home_team = competition['competitors'][0]
        away_team = competition['competitors'][1]

        home_name = home_team['team']['displayName']
        away_name = away_team['team']['displayName']
        home_record = self.get_team_record(home_team)
        away_record = self.get_team_record(away_team)
        home_score = home_team.get('score', '')
        away_score = away_team.get('score', '')

        # Convert to UK time
        london_tz = pytz.timezone('Europe/London')
        uk_time = game_date.astimezone(london_tz)
        day_abbr = uk_time.strftime('%a').upper()[:3]

        status_name = status['type']['name']
        is_final = status_name == 'STATUS_FINAL'
        is_live = status_name == 'STATUS_IN_PROGRESS'

        # Build matchup string with bold for winning team
        if home_score and away_score:
            home_score_int = int(home_score)
            away_score_int = int(away_score)

            if format_type == 'terminal':
                # Use ANSI codes for terminal
                if away_score_int > home_score_int:
                    # Away team winning
                    matchup = f"\033[1m{away_name}{away_record} {away_score}\033[0m @ {home_name}{home_record} {home_score}"
                elif home_score_int > away_score_int:
                    # Home team winning
                    matchup = f"{away_name}{away_record} {away_score} @ \033[1m{home_name}{home_record} {home_score}\033[0m"
                else:
                    # Tie
                    matchup = f"{away_name}{away_record} {away_score} @ {home_name}{home_record} {home_score}"
            else:
                # Plain text for Inky (bold will be handled by font)
                matchup = f"{away_name}{away_record} {away_score} @ {home_name}{home_record} {home_score}"
        else:
            matchup = f"{away_name}{away_record} @ {home_name}{home_record}"

        # Build status string
        if is_final:
            status_str = "FINAL"
        elif is_live:
            # Try to get quarter/period information
            period = status.get('period', '')
            display_clock = status.get('displayClock', '')
            if period:
                quarter_map = {1: '1Q', 2: '2Q', 3: '3Q', 4: '4Q', 5: 'OT'}
                quarter = quarter_map.get(period, f'Q{period}')
                if display_clock:
                    status_str = f"{quarter} {display_clock}"
                else:
                    status_str = quarter
            else:
                status_str = "LIVE"
        else:
            # Game not started - show UK time
            tz_abbr = self.get_uk_timezone(uk_time)
            status_str = f"{uk_time.strftime('%H:%M')} {tz_abbr}"

        return f"{day_abbr} {matchup} | {status_str}"

    def get_teams_on_bye(self, events):
        """Determine which teams are on bye this week"""
        playing_teams = set()

        for event in events:
            try:
                game_date_str = event['date']
                if self.is_current_week(game_date_str):
                    competition = event['competitions'][0]
                    home_team = competition['competitors'][0]['team']['displayName']
                    away_team = competition['competitors'][1]['team']['displayName']
                    playing_teams.add(home_team)
                    playing_teams.add(away_team)
            except (KeyError, IndexError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed NFL event while calculating byes: {e}")

        bye_teams = [team for team in self.all_nfl_teams if team not in playing_teams]
        return sorted(bye_teams)

    def get_games_list(self, format_type='terminal'):
        """Get formatted list of games for current week"""
        data = self.fetch_data()
        if not data:
            if network_disabled():
                logger.info("No NFL scoreboard data available while network is disabled.")
            else:
                logger.error("No NFL scoreboard data available.")
            return None, [], []
        if not isinstance(data, dict):
            logger.error("NFL scoreboard data has unexpected shape.")
            return None, [], []

        week_label = self.get_week_label(data)
        events = data.get('events', [])
        if not isinstance(events, list):
            logger.warning("NFL scoreboard response did not include an events list")
            return week_label, [], self.all_nfl_teams

        if not events:
            return week_label, [], self.all_nfl_teams

        # Collect all games with their dates
        games = []
        for event in events:
            try:
                game_date_str = event['date']
                if not self.is_current_week(game_date_str):
                    continue

                game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
                competition = event['competitions'][0]

                game_line = self.format_game_line(
                    competition,
                    event['status'],
                    game_date,
                    format_type
                )

                # Store raw data for Inky rendering
                home_team = competition['competitors'][0]
                away_team = competition['competitors'][1]
                home_score = home_team.get('score', '')
                away_score = away_team.get('score', '')
                winner = None

                if home_score and away_score:
                    if int(away_score) > int(home_score):
                        winner = 'away'
                    elif int(home_score) > int(away_score):
                        winner = 'home'

                games.append({
                    'date': game_date,
                    'line': game_line,
                    'winner': winner,
                    'competition': competition,
                    'status': event['status']
                })
            except (KeyError, IndexError, TypeError, ValueError) as e:
                logger.warning(f"Skipping malformed NFL event: {e}")

        # Sort by date
        games.sort(key=lambda x: x['date'])

        # Get bye teams
        bye_teams = self.get_teams_on_bye(events)

        return week_label, games, bye_teams

    def display_terminal(self):
        """Display games in terminal format"""
        week_label, games, bye_teams = self.get_games_list(format_type='terminal')

        if week_label is None:
            logger.error("Error fetching data for terminal display")
            return

        logger.info("\n" + "="*80)
        logger.info(f"NFL {week_label}")
        logger.info("="*80)

        if not games:
            logger.info("No games found for current week.")
            return

        for game in games:
            logger.info(game['line'])

        if bye_teams:
            logger.info("\n" + "-"*80)
            logger.info("TEAMS ON BYE: " + ", ".join(bye_teams))

    def generate_inky_image(self, output_file="nfl_inky.png"):
        """Generate image for Inky Impression 7.3 (800x480)"""
        week_label, games, bye_teams = self.get_games_list(format_type='inky')

        if week_label is None:
            logger.error("Error fetching data for Inky image generation")
            return

        # Create image - white background for e-ink
        width, height = 800, 480
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # Try to load fonts, fall back to default if not available
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            game_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
            game_font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 14)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except OSError:
            logger.warning("Could not load custom fonts, using default.")
            title_font = ImageFont.load_default()
            game_font = ImageFont.load_default()
            game_font_bold = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Draw title
        title = f"NFL {week_label}"
        draw.text((10, 10), title, fill='black', font=title_font)

        # Draw line under title
        draw.line([(10, 45), (790, 45)], fill='black', width=2)

        # Draw games
        y_position = 55
        line_height = 18

        if not games:
            draw.text((10, y_position), "No games found for current week.", fill='black', font=game_font)
        else:
            for game in games:
                if y_position > height - 60:  # Leave space for bye teams
                    break

                # Parse the game line to apply bold to winner
                line = game['line']
                winner = game['winner']

                # For Inky, we need to draw with selective bold
                # Split the line at " @ " to separate away and home
                if winner and '@' in line:
                    parts = line.split(' @ ')
                    day_away = parts[0]  # "DAY AwayTeam (record) score"
                    home_status = parts[1]  # "HomeTeam (record) score | status"

                    # Split home_status at " | "
                    home_part = home_status.split(' | ')[0]
                    status_part = ' | ' + home_status.split(' | ')[1]

                    x_pos = 10

                    if winner == 'away':
                        # Bold the away team part
                        draw.text((x_pos, y_position), day_away, fill='black', font=game_font_bold)
                        bbox = draw.textbbox((x_pos, y_position), day_away, font=game_font_bold)
                        x_pos = bbox[2]

                        draw.text((x_pos, y_position), ' @ ' + home_part, fill='black', font=game_font)
                        bbox = draw.textbbox((x_pos, y_position), ' @ ' + home_part, font=game_font)
                        x_pos = bbox[2]
                    else:  # winner == 'home'
                        # Bold the home team part
                        draw.text((x_pos, y_position), day_away + ' @ ', fill='black', font=game_font)
                        bbox = draw.textbbox((x_pos, y_position), day_away + ' @ ', font=game_font)
                        x_pos = bbox[2]

                        draw.text((x_pos, y_position), home_part, fill='black', font=game_font_bold)
                        bbox = draw.textbbox((x_pos, y_position), home_part, font=game_font_bold)
                        x_pos = bbox[2]

                    draw.text((x_pos, y_position), status_part, fill='black', font=game_font)
                else:
                    # No winner yet (scheduled game) or no scores
                    draw.text((10, y_position), line, fill='black', font=game_font)

                y_position += line_height

        # Draw bye teams at bottom
        if bye_teams and y_position < height - 40:
            draw.line([(10, y_position + 5), (790, y_position + 5)], fill='black', width=1)
            y_position += 15
            bye_text = "BYE: " + ", ".join(bye_teams)

            # Wrap bye text if too long
            if len(bye_text) > 110:
                words = bye_text.split()
                lines = []
                current_line = words[0]
                for word in words[1:]:
                    if len(current_line + " " + word) <= 110:
                        current_line += " " + word
                    else:
                        lines.append(current_line)
                        current_line = word
                lines.append(current_line)

                for line in lines:
                    if y_position < height - 15:
                        draw.text((10, y_position), line, fill='black', font=small_font)
                        y_position += 14
            else:
                draw.text((10, y_position), bye_text, fill='black', font=small_font)

        # Save image
        img.save(output_file)
        logger.info(f"\nInky Impression image saved to: {output_file}")
        logger.info(f"Image size: {width}x{height} pixels")

def main():
    nfl = NFLWeeklyDisplay()

    logger.info("\n" + "="*80)
    logger.info("NFL WEEKLY DISPLAY")
    logger.info("="*80)

    while True:
        print("\nOptions:")
        print("1. Display in terminal")
        print("2. Generate Inky Impression image")
        print("3. Exit")

        choice = input("\nEnter your choice (1-3): ")

        if choice == '1':
            nfl.display_terminal()
        elif choice == '2':
            filename = f"nfl_inky_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            nfl.generate_inky_image(filename)
        elif choice == '3':
            logger.info("\nThanks for using NFL Weekly Display!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
