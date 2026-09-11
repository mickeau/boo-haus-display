#!/usr/bin/env python3
"""
Status Screen for Boo Haus Display
Shows system health, network, data source status, and display stats.
"""

import sys
import os
import json
import shutil
import socket
import subprocess
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_screen import BaseScreen
import logging

logger = logging.getLogger(__name__)

# Cache files written by each BaseFetcher subclass
DATA_SOURCES = {
    'Weather':    'weather_cache.json',
    'Tides':      'tide_cache.json',
    'Water Qual': 'water_quality_cache.json',
    'Sewage':     'sewage_cache.json',
    'Calendar':   'calendar_cache.json',
}

# News uses a different cache format (not BaseFetcher)
NEWS_CACHE_KEYS = [
    ('screens.news.story_file', 'news_stories.json'),
    ('screens.news.raw_story_file', 'combined_news_recent.json'),
    ('screens.news.legacy_story_file', 'news_summaries.json'),
    ('screens.news.cache_file', 'headline_summaries_cache.json'),
]


class StatusScreen(BaseScreen):
    """System status and diagnostics display"""

    @property
    def name(self) -> str:
        return "status"

    def __init__(self, display_manager=None):
        super().__init__()
        self.display_manager = display_manager

    # ------------------------------------------------------------------
    # Data collection helpers (all wrapped in try/except)
    # ------------------------------------------------------------------

    def _get_cpu_temp(self):
        try:
            result = subprocess.run(
                ['vcgencmd', 'measure_temp'],
                capture_output=True, text=True, timeout=5
            )
            # Output: "temp=48.3'C"
            return result.stdout.strip().replace("temp=", "").replace("'C", "°C")
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return "N/A"

    def _get_memory(self):
        """Return (used_mb, total_mb, percent)."""
        try:
            result = subprocess.run(
                ['free', '-m'], capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split('\n')
            # Second line: Mem: total used free ...
            parts = lines[1].split()
            total = int(parts[1])
            used = int(parts[2])
            pct = round(used / total * 100)
            return used, total, pct
        except (FileNotFoundError, IndexError, OSError, subprocess.TimeoutExpired, ValueError, ZeroDivisionError):
            return None, None, None

    def _get_disk(self):
        """Return (used_gb, total_gb, percent)."""
        try:
            usage = shutil.disk_usage('/')
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            pct = round(used_gb / total_gb * 100)
            return round(used_gb, 1), round(total_gb, 1), pct
        except (OSError, ZeroDivisionError):
            return None, None, None

    def _get_uptime(self):
        try:
            with open('/proc/uptime', 'r') as f:
                seconds = float(f.readline().split()[0])
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            mins = int((seconds % 3600) // 60)
            if days > 0:
                return f"{days}d {hours}h {mins}m"
            return f"{hours}h {mins}m"
        except (OSError, IndexError, ValueError):
            return "N/A"

    def _get_wifi_info(self):
        """Return (ssid, signal_dbm, signal_pct)."""
        try:
            result = subprocess.run(
                ['iwconfig', 'wlan0'],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout

            # Parse SSID
            ssid = "Unknown"
            if 'ESSID:"' in output:
                ssid = output.split('ESSID:"')[1].split('"')[0]

            # Parse signal level
            signal_dbm = None
            signal_pct = None
            if 'Signal level=' in output:
                sig_str = output.split('Signal level=')[1].split()[0]
                signal_dbm = int(sig_str.replace('dBm', ''))
                # Convert dBm to rough percentage (-30=100%, -90=0%)
                signal_pct = max(0, min(100, 2 * (signal_dbm + 100)))

            return ssid, signal_dbm, signal_pct
        except (FileNotFoundError, IndexError, OSError, subprocess.TimeoutExpired, ValueError):
            return None, None, None

    def _get_ip_address(self):
        try:
            result = subprocess.run(
                ['hostname', '-I'], capture_output=True, text=True, timeout=5
            )
            ips = result.stdout.strip().split()
            return ips[0] if ips else "No IP"
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return "N/A"

    def _check_internet(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def _get_cache_age(self, cache_file):
        """Read a BaseFetcher cache file and return age in minutes, or None."""
        try:
            from config import config
            cache_path = config.resolve_path(cache_file)
            if not cache_path.exists():
                return None
            with open(cache_path, 'r') as f:
                data = json.load(f)
            ts = data.get('timestamp')
            if not ts:
                return None
            cached_time = datetime.fromisoformat(ts)
            now = datetime.now(cached_time.tzinfo) if cached_time.tzinfo else datetime.now()
            age_mins = (now - cached_time).total_seconds() / 60
            return round(age_mins)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _get_news_cache_age(self):
        """News cache uses file modification time, not BaseFetcher format."""
        try:
            from config import config
            cache_file = next(
                (
                    config.runtime_path(key, default)
                    for key, default in NEWS_CACHE_KEYS
                    if os.path.exists(config.runtime_path(key, default))
                ),
                None
            )
            if cache_file is None:
                return None
            mtime = os.path.getmtime(cache_file)
            age_mins = (datetime.now().timestamp() - mtime) / 60
            return round(age_mins)
        except OSError:
            return None

    def _format_age(self, minutes):
        """Format age in minutes to a readable string."""
        if minutes is None:
            return "No data"
        if minutes < 1:
            return "Just now"
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"

    def _age_color(self, minutes, warn_mins=120, error_mins=360):
        """Return GREEN / ORANGE / RED based on age."""
        if minutes is None:
            return self.RED
        if minutes <= warn_mins:
            return self.GREEN
        if minutes <= error_mins:
            return self.ORANGE
        return self.RED

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_content(self):
        x, y, width, height = self.get_content_area()

        # Grid layout
        mid_x = x + width // 2
        mid_y = y + (height // 2) - 5

        # Separator lines
        self.draw.line([(mid_x, y), (mid_x, y + height)],
                       fill=self.BLACK, width=1)
        self.draw.line([(x, mid_y), (x + width, mid_y)],
                       fill=self.BLACK, width=1)

        left_w = width // 2 - 15
        right_w = width // 2 - 15
        right_x = mid_x + 10
        section_h = (height // 2) - 10

        # Draw four sections
        self._draw_system_health(x, y, left_w)
        self._draw_network(right_x, y, right_w)
        self._draw_data_sources(x, mid_y + 8, left_w)
        self._draw_display_stats(right_x, mid_y + 8, right_w)

    def _draw_section_header(self, title, x, y):
        """Draw a section title and return y after it."""
        self.draw.text((x, y), title, font=self.font_medium, fill=self.PASTEL_BLUE)
        line_y = y + 26
        self.draw.line([(x, line_y), (x + 200, line_y)],
                       fill=self.PASTEL_BLUE, width=1)
        return line_y + 6

    def _draw_row(self, label, value, x, y, value_color=None):
        """Draw a label: value row. Returns y for next row."""
        if value_color is None:
            value_color = self.BLACK
        self.draw.text((x, y), label, font=self.font_small, fill=self.BLACK)
        # Right-align value
        label_bbox = self.draw.textbbox((0, 0), label, font=self.font_small)
        label_w = label_bbox[2] - label_bbox[0]
        self.draw.text((x + label_w + 5, y), str(value),
                       font=self.font_small, fill=value_color)
        return y + 24

    def _draw_system_health(self, x, y, w):
        y = self._draw_section_header("System Health", x, y)

        # CPU temp
        temp = self._get_cpu_temp()
        temp_color = self.BLACK
        try:
            temp_val = float(temp.replace("°C", ""))
            if temp_val > 70:
                temp_color = self.RED
            elif temp_val > 55:
                temp_color = self.ORANGE
        except (AttributeError, ValueError):
            pass
        y = self._draw_row("CPU Temp:", temp, x, y, temp_color)

        # Memory
        used, total, pct = self._get_memory()
        if used is not None:
            mem_color = self.RED if pct > 85 else (self.ORANGE if pct > 70 else self.BLACK)
            y = self._draw_row("Memory:", f"{used}/{total}MB ({pct}%)", x, y, mem_color)
        else:
            y = self._draw_row("Memory:", "N/A", x, y)

        # Disk
        used_gb, total_gb, pct = self._get_disk()
        if used_gb is not None:
            disk_color = self.RED if pct > 90 else (self.ORANGE if pct > 75 else self.BLACK)
            y = self._draw_row("Disk:", f"{used_gb}/{total_gb}GB ({pct}%)", x, y, disk_color)
        else:
            y = self._draw_row("Disk:", "N/A", x, y)

        # Uptime
        uptime = self._get_uptime()
        y = self._draw_row("Uptime:", uptime, x, y)

    def _draw_network(self, x, y, w):
        y = self._draw_section_header("Network", x, y)

        # WiFi
        ssid, signal_dbm, signal_pct = self._get_wifi_info()
        if ssid:
            y = self._draw_row("SSID:", ssid, x, y)
            if signal_pct is not None:
                sig_color = self.RED if signal_pct < 30 else (self.ORANGE if signal_pct < 50 else self.BLACK)
                y = self._draw_row("Signal:", f"{signal_pct}% ({signal_dbm}dBm)", x, y, sig_color)
        else:
            y = self._draw_row("WiFi:", "Not connected", x, y, self.RED)

        # IP
        ip = self._get_ip_address()
        y = self._draw_row("IP:", ip, x, y)

        # Internet
        online = self._check_internet()
        y = self._draw_row("Internet:",
                           "Connected" if online else "Offline",
                           x, y,
                           self.GREEN if online else self.RED)

    def _draw_data_sources(self, x, y, w):
        y = self._draw_section_header("Data Sources", x, y)

        for name, cache_file in DATA_SOURCES.items():
            age = self._get_cache_age(cache_file)
            age_str = self._format_age(age)
            color = self._age_color(age)

            # Status dot
            dot_y = y + 6
            self.draw.ellipse([(x, dot_y), (x + 10, dot_y + 10)], fill=color)

            # Source name and age
            self.draw.text((x + 16, y), name, font=self.font_tiny, fill=self.BLACK)
            self.draw.text((x + 110, y), age_str, font=self.font_tiny, fill=color)
            y += 20

        # News (separate cache format)
        news_age = self._get_news_cache_age()
        age_str = self._format_age(news_age)
        color = self._age_color(news_age, warn_mins=1500, error_mins=3000)  # News refreshes daily
        dot_y = y + 6
        self.draw.ellipse([(x, dot_y), (x + 10, dot_y + 10)], fill=color)
        self.draw.text((x + 16, y), "News", font=self.font_tiny, fill=self.BLACK)
        self.draw.text((x + 110, y), age_str, font=self.font_tiny, fill=color)

    def _draw_display_stats(self, x, y, w):
        y = self._draw_section_header("Display", x, y)

        # Read state file
        state = {}
        try:
            from config import config
            with open(config.runtime_path('state_file', 'display_state.json'), 'r') as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

        # Current screen
        current = state.get('current_screen', 0)
        total = len(self.display_manager.screens) if self.display_manager else '?'
        y = self._draw_row("Screen:", f"{current + 1} of {total}", x, y)

        # Cycle count
        cycles = state.get('cycle_count', 0)
        y = self._draw_row("Cycles:", str(cycles), x, y)

        # Last update
        last_update = state.get('last_update')
        if last_update:
            try:
                dt = datetime.fromisoformat(last_update)
                y = self._draw_row("Last update:", dt.strftime('%H:%M:%S'), x, y)
            except (TypeError, ValueError):
                y = self._draw_row("Last update:", "N/A", x, y)
        else:
            y = self._draw_row("Last update:", "N/A", x, y)

        # Cycle interval
        from config import config
        interval = config.get('display.cycle_interval_seconds', 300)
        y = self._draw_row("Interval:", f"{interval}s", x, y)

        # Last news scrape
        last_scrape = state.get('last_news_scrape')
        if last_scrape:
            try:
                dt = datetime.fromisoformat(last_scrape)
                now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
                age = (now - dt).total_seconds() / 3600
                y = self._draw_row("News scrape:", f"{int(age)}h ago", x, y)
            except (TypeError, ValueError):
                pass
