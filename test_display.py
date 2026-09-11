#!/usr/bin/env python3
"""
Boo Haus Display - Testing and Debugging Script
Tests all components and generates diagnostic report
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

from config import config

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print formatted section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")

def print_test(name, passed, message=""):
    """Print test result"""
    status = f"{Colors.GREEN}✓ PASS{Colors.ENDC}" if passed else f"{Colors.RED}✗ FAIL{Colors.ENDC}"
    print(f"{status} - {name}")
    if message:
        print(f"       {message}")

def print_optional(name, installed, message=""):
    """Print optional dependency status without treating absence as failure."""
    if installed:
        print(f"{Colors.GREEN}✓ INSTALLED{Colors.ENDC} - {name}")
    else:
        print(f"{Colors.YELLOW}⊘ OPTIONAL{Colors.ENDC} - {name}")
    if message:
        print(f"       {message}")

def is_raspberry_pi():
    """Best-effort Raspberry Pi detection for hardware-specific checks."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except Exception:
        return False

def test_python_version():
    """Test Python version"""
    print_header("Python Version Check")
    version = sys.version_info
    passed = version.major == 3 and version.minor >= 7
    print_test("Python 3.7+", passed, f"Found: {version.major}.{version.minor}.{version.micro}")
    return passed

def test_dependencies():
    """Test required Python packages"""
    print_header("Python Dependencies Check")

    required_packages = [
        ('PIL', 'pillow'),
        ('requests', 'requests'),
        ('bs4', 'beautifulsoup4'),
        ('pytz', 'pytz'),
    ]

    optional_packages = [
        ('feedparser', 'feedparser'),
        ('inky', 'inky'),
        ('gpiod', 'gpiod'),
        ('google.auth', 'google-auth'),
        ('anthropic', 'anthropic'),
        ('flask', 'flask'),
    ]

    all_passed = True

    print("\nRequired packages:")
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print_test(package_name, True)
        except ImportError:
            print_test(package_name, False, f"Install with: pip3 install {package_name}")
            all_passed = False

    print("\nOptional packages:")
    for module_name, package_name in optional_packages:
        try:
            __import__(module_name)
            print_optional(package_name, True)
        except ImportError:
            print_optional(package_name, False, "Not installed")

    return all_passed

def test_file_structure():
    """Test required files exist"""
    print_header("File Structure Check")

    required_files = [
        'boo_haus_main.py',
        'base_screen.py',

        'birthdays.json',
    ]

    required_dirs = [
        'screens',
        'logs',
        'display_images',
    ]

    screen_files = [
        'screens/__init__.py',
        'screens/weather_screen.py',
        'screens/week_screen.py',
        'screens/nfl_screen.py',
        'screens/calendar_screen.py',
        'screens/news_screen.py',
        'screens/birthday_screen.py',
        'screens/status_screen.py',
    ]

    all_passed = True

    print("\nCore files:")
    for file in required_files:
        exists = os.path.exists(file)
        print_test(file, exists)
        if not exists:
            all_passed = False

    print("\nDirectories:")
    for dir in required_dirs:
        exists = os.path.isdir(dir)
        print_test(dir, exists)
        if not exists:
            all_passed = False

    print("\nScreen files:")
    for file in screen_files:
        exists = os.path.exists(file)
        print_test(file, exists)
        if not exists:
            all_passed = False

    return all_passed

def test_configuration():
    """Test configuration file"""
    print_header("Configuration Check")

    try:
        all_passed = True

        # Check required sections
        required_sections = ['display', 'screens', 'special_dates', 'api_keys']
        for section in required_sections:
            exists = config.get(section) is not None
            print_test(f"Section '{section}' exists", exists)
            all_passed = all_passed and exists

        # Check API keys
        api_keys = config.get('api_keys', {})
        has_weather_key = config.has_real_value('api_keys.openweather')
        print_test("OpenWeather API key configured", has_weather_key,
                  "" if has_weather_key else "Edit 'api_keys.openweather' in config")
        all_passed = all_passed and has_weather_key

        # Check enabled screens
        screens = config.get('screens', {})
        enabled_count = sum(1 for s in screens.values() if s.get('enabled', False))
        print_test(f"{enabled_count} screens enabled", enabled_count > 0)
        all_passed = all_passed and enabled_count > 0

        return all_passed

    except Exception as e:
        print_test("Configuration loading", False, str(e))
        return False

def test_data_fetchers():
    """Test data fetcher scripts"""
    print_header("Data Fetchers Check")

    fetchers = [
        ('weather_fetcher.py', 'Weather data'),
        ('bin_collections.py', 'Bin collections'),
        ('tide_times.py', 'Tide times'),
        ('water_quality.py', 'Water quality'),
        ('direct_sewage_api.py', 'Sewage alerts'),
        ('nfl_scores.py', 'NFL scores'),
    ]

    for file, description in fetchers:
        exists = os.path.exists(file)
        print_test(f"{description} ({file})", exists)

    return True

def test_screens():
    """Test each screen can be imported"""
    print_header("Screen Import Check")

    all_passed = True

    try:
        from screens.weather_screen import WeatherScreen
        from screens.week_screen import WeekScreen
        from screens.nfl_screen import NFLScreen
        from screens.calendar_screen import CalendarScreen
        from screens.news_screen import NewsScreen
        from screens.birthday_screen import BirthdayScreen
        from screens.status_screen import StatusScreen

        print_test("WeatherScreen", True)
        print_test("WeekScreen", True)
        print_test("NFLScreen", True)
        print_test("CalendarScreen", True)
        print_test("NewsScreen", True)
        print_test("BirthdayScreen", True)
        print_test("StatusScreen", True)

    except ImportError as e:
        print_test("Screen imports", False, str(e))
        all_passed = False

    return all_passed

def test_inky_display():
    """Test Inky display library"""
    print_header("Inky Display Check")

    try:
        from inky.auto import auto
        print_test("Inky library installed", True)

        try:
            inky = auto(ask_user=False, verbose=False)
            print_test("Inky display detected", True,
                      f"Type: {inky.__class__.__name__}")
            return True
        except Exception as e:
            print_test("Inky display detected", False,
                      "Display not found - may be running on non-Pi system")
            return False

    except ImportError:
        if not config.get('display.display_on_inky', True) or not is_raspberry_pi():
            print_optional("Inky library installed", False,
                           "Required only on the Raspberry Pi display host")
            return True
        print_test("Inky library installed", False,
                   "Install with: pip3 install inky[rpi,example-depends]")
        return False

def test_display_functionality():
    """Test creating a simple display"""
    print_header("Display Rendering Check")

    try:
        from PIL import Image, ImageDraw

        # Create test image
        img = Image.new('RGB', (800, 480), 'white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Test", fill='black')

        print_test("PIL image creation", True)

        # Try to save test image
        test_dir = Path('display_images')
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / 'test_render.png'
        img.save(test_file)

        print_test("Save test image", True, f"Saved to {test_file}")

        return True

    except Exception as e:
        print_test("Display rendering", False, str(e))
        return False

def test_internet_connectivity():
    """Test internet connection"""
    print_header("Internet Connectivity Check")

    import requests
    all_passed = True

    endpoints = [
        ('api.openweathermap.org', 'OpenWeather API'),
        ('www.google.com', 'General internet'),
        ('eastdevon.gov.uk', 'East Devon Council'),
    ]

    for endpoint, description in endpoints:
        try:
            response = requests.get(f"https://{endpoint}", timeout=5)
            passed = response.status_code < 500
            print_test(description, passed, f"Status: {response.status_code}")
            all_passed = all_passed and passed
        except Exception as e:
            print_test(description, False, str(e)[:50])
            all_passed = False

    return all_passed

def generate_diagnostic_report():
    """Generate complete diagnostic report"""
    print_header("Boo Haus Display - System Diagnostics")

    print(f"\n{Colors.BOLD}Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
    print(f"{Colors.BOLD}Working directory: {os.getcwd()}{Colors.ENDC}")

    results = {}

    results['Python Version'] = test_python_version()
    results['Dependencies'] = test_dependencies()
    results['File Structure'] = test_file_structure()
    results['Configuration'] = test_configuration()
    results['Data Fetchers'] = test_data_fetchers()
    results['Screen Imports'] = test_screens()
    results['Inky Display'] = test_inky_display()
    results['Display Rendering'] = test_display_functionality()
    results['Internet'] = test_internet_connectivity()

    # Summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if result else f"{Colors.RED}FAIL{Colors.ENDC}"
        print(f"  {status} - {test_name}")

    print(f"\n{Colors.BOLD}Overall: {passed}/{total} tests passed{Colors.ENDC}")

    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests passed! System ready.{Colors.ENDC}")
        return True
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Some tests failed. Review errors above.{Colors.ENDC}")
        return False

def quick_screen_test():
    """Quick test of each screen"""
    print_header("Quick Screen Test")

    print("\nTesting each screen (without Inky display)...")

    old_offline = os.environ.get("BOO_HAUS_OFFLINE")
    os.environ["BOO_HAUS_OFFLINE"] = "1"

    try:
        # Temporarily disable Inky display
        config.config['display']['display_on_inky'] = False
        config.config['display']['save_images'] = True

        from screens.weather_screen import WeatherScreen
        from screens.week_screen import WeekScreen
        from screens.nfl_screen import NFLScreen
        from screens.calendar_screen import CalendarScreen
        from screens.news_screen import NewsScreen
        from screens.birthday_screen import BirthdayScreen
        from screens.status_screen import StatusScreen

        screens = [
            ('Weather', WeatherScreen()),
            ('Week', WeekScreen()),
            ('NFL', NFLScreen()),
            ('Calendar', CalendarScreen()),
            ('News', NewsScreen()),
            ('Birthday', BirthdayScreen()),
            ('Status', StatusScreen()),
        ]

        for name, screen in screens:
            if not screen.is_enabled():
                print(f"  {Colors.YELLOW}⊘{Colors.ENDC} {name} - Disabled in config")
                continue

            try:
                img = screen.render()
                filename = f"display_images/test_{name.lower()}.png"
                img.save(filename)
                print(f"  {Colors.GREEN}✓{Colors.ENDC} {name} - Rendered successfully ({filename})")
            except Exception as e:
                print(f"  {Colors.RED}✗{Colors.ENDC} {name} - Error: {str(e)[:50]}")

        print("\n✓ Screen test complete. Check display_images/ directory.")

    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.ENDC} Screen test failed: {e}")
    finally:
        if old_offline is None:
            os.environ.pop("BOO_HAUS_OFFLINE", None)
        else:
            os.environ["BOO_HAUS_OFFLINE"] = old_offline

def main():
    """Main test function"""
    import argparse

    parser = argparse.ArgumentParser(description='Boo Haus Display Testing Tool')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick screen tests')
    parser.add_argument('--full', action='store_true',
                       help='Run full diagnostic suite')

    args = parser.parse_args()

    if args.quick:
        quick_screen_test()
    elif args.full:
        success = generate_diagnostic_report()
        sys.exit(0 if success else 1)
    else:
        # Default: run full diagnostics
        print(f"\n{Colors.BOLD}Boo Haus Display - Testing Tool{Colors.ENDC}")
        print("Run with --help for options\n")

        success = generate_diagnostic_report()

        print("\n" + "="*60)
        print("Run 'python3 test_display.py --quick' to test screen rendering")
        print("="*60 + "\n")

        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
