#!/usr/bin/env python3
"""
Boo Haus Display - Health Check Monitor
Monitors system health and reports status
Can be run manually or via cron
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class HealthChecker:
    """System health monitoring"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.info = []
    
    def add_issue(self, message):
        """Add critical issue"""
        self.issues.append(f"❌ ISSUE: {message}")
    
    def add_warning(self, message):
        """Add warning"""
        self.warnings.append(f"⚠️  WARNING: {message}")
    
    def add_info(self, message):
        """Add info"""
        self.info.append(f"ℹ️  INFO: {message}")
    
    def check_last_update(self):
        """Check when display was last updated"""
        try:
            with open('display_state.json', 'r') as f:
                state = json.load(f)
            
            last_update = state.get('last_update')
            if not last_update:
                self.add_warning("No last update time recorded")
                return
            
            last_dt = datetime.fromisoformat(last_update)
            age = datetime.now() - last_dt
            
            if age > timedelta(hours=1):
                self.add_issue(f"Display not updated in {age.seconds // 60} minutes")
            elif age > timedelta(minutes=30):
                self.add_warning(f"Display last updated {age.seconds // 60} minutes ago")
            else:
                self.add_info(f"Display updated {age.seconds // 60} minutes ago")
                
        except FileNotFoundError:
            self.add_warning("No display state file found - may be first run")
        except Exception as e:
            self.add_issue(f"Error reading display state: {e}")
    
    def check_news_cache(self):
        """Check news cache freshness"""
        cache_file = 'headline_summaries_cache.json'
        
        if not os.path.exists(cache_file):
            self.add_warning("News cache file not found")
            return
        
        # Check age of cache file
        mod_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        age = datetime.now() - mod_time
        
        if age > timedelta(days=2):
            self.add_issue(f"News cache is {age.days} days old")
        elif age > timedelta(days=1):
            self.add_warning(f"News cache is {age.days} day(s) old")
        else:
            self.add_info(f"News cache updated {age.seconds // 3600} hours ago")
        
        # Check cache content
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            summaries = data.get('summaries', {})
            count = len(summaries)
            
            if count == 0:
                self.add_issue("News cache is empty")
            elif count < 5:
                self.add_warning(f"Only {count} news stories in cache")
            else:
                self.add_info(f"{count} news stories in cache")
                
        except Exception as e:
            self.add_issue(f"Error reading news cache: {e}")
    
    def check_log_files(self):
        """Check log file sizes and recent errors"""
        log_dir = Path('logs')
        
        if not log_dir.exists():
            self.add_warning("Logs directory not found")
            return
        
        # Check log sizes
        for log_file in log_dir.glob('*.log'):
            size_mb = log_file.stat().st_size / (1024 * 1024)
            
            if size_mb > 100:
                self.add_warning(f"{log_file.name} is {size_mb:.1f}MB (consider rotation)")
            
            # Check for recent errors
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                
                recent_errors = [l for l in lines[-100:] if 'ERROR' in l.upper()]
                
                if len(recent_errors) > 5:
                    self.add_warning(f"{len(recent_errors)} recent errors in {log_file.name}")
                    
            except Exception:
                pass
    
    def check_disk_space(self):
        """Check available disk space"""
        try:
            import shutil
            
            usage = shutil.disk_usage('.')
            free_gb = usage.free / (1024**3)
            percent_used = (usage.used / usage.total) * 100
            
            if free_gb < 1:
                self.add_issue(f"Low disk space: {free_gb:.1f}GB free")
            elif percent_used > 90:
                self.add_warning(f"Disk {percent_used:.0f}% full ({free_gb:.1f}GB free)")
            else:
                self.add_info(f"Disk space OK: {free_gb:.1f}GB free")
                
        except Exception as e:
            self.add_warning(f"Could not check disk space: {e}")
    
    def check_image_directory(self):
        """Check saved images"""
        img_dir = Path('display_images')
        
        if not img_dir.exists():
            self.add_warning("Display images directory not found")
            return
        
        images = list(img_dir.glob('*.png'))
        
        if len(images) == 0:
            self.add_warning("No saved images found")
        else:
            # Check age of latest images
            latest_files = sorted(images, key=lambda x: x.stat().st_mtime, reverse=True)[:5]
            latest = latest_files[0]
            
            mod_time = datetime.fromtimestamp(latest.stat().st_mtime)
            age = datetime.now() - mod_time
            
            if age > timedelta(hours=1):
                self.add_warning(f"No images saved in last {age.seconds // 60} minutes")
            else:
                self.add_info(f"{len(images)} saved images, latest {age.seconds // 60}m ago")
        
        # Check total size
        total_size = sum(f.stat().st_size for f in images) / (1024**2)
        
        if total_size > 500:
            self.add_warning(f"Images using {total_size:.0f}MB (consider cleanup)")
    
    def check_data_sources(self):
        """Quick check of data source availability"""
        import requests
        
        sources = [
            ('https://api.openweathermap.org', 'Weather API'),
            ('https://eastdevon.gov.uk', 'Bin collections'),
            ('https://www.bbc.co.uk', 'Tide data'),
        ]
        
        for url, name in sources:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code >= 500:
                    self.add_warning(f"{name} may be down (HTTP {response.status_code})")
            except requests.RequestException:
                self.add_warning(f"{name} unreachable")
    
    def check_configuration(self):
        """Check configuration file"""
        try:
            with open('boo_haus_config.json', 'r') as f:
                config = json.load(f)
            
            # Check API key
            api_key = config.get('api_keys', {}).get('openweather')
            if not api_key or api_key == 'YOUR_API_KEY_HERE':
                self.add_issue("OpenWeather API key not configured")
            
            # Check enabled screens
            screens = config.get('screens', {})
            enabled = sum(1 for s in screens.values() if s.get('enabled', False))
            
            if enabled == 0:
                self.add_issue("No screens enabled!")
            elif enabled < 3:
                self.add_warning(f"Only {enabled} screens enabled")
            else:
                self.add_info(f"{enabled} screens enabled")
                
        except FileNotFoundError:
            self.add_issue("Configuration file not found")
        except json.JSONDecodeError:
            self.add_issue("Configuration file invalid JSON")
    
    def run_all_checks(self):
        """Run all health checks"""
        logger.info("="*60)
        logger.info("Boo Haus Display - Health Check")
        logger.info("="*60)
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.check_configuration()
        self.check_last_update()
        self.check_news_cache()
        self.check_image_directory()
        self.check_log_files()
        self.check_disk_space()
        self.check_data_sources()
        
        # Report results
        if self.issues:
            logger.info("\n🚨 ISSUES FOUND:")
            for issue in self.issues:
                logger.info(f"  {issue}")
        
        if self.warnings:
            logger.info("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                logger.info(f"  {warning}")
        
        if self.info:
            logger.info("\n✅ STATUS:")
            for info in self.info:
                logger.info(f"  {info}")
        
        # Summary
        logger.info("\n" + "="*60)
        if self.issues:
            logger.info("❌ CRITICAL: Action required")
            return False
        elif self.warnings:
            logger.info("⚠️  WARNING: Review warnings above")
            return True
        else:
            logger.info("✅ HEALTHY: All checks passed")
            return True
    
    def get_status_dict(self):
        """Return status as dictionary for JSON output"""
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'critical' if self.issues else ('warning' if self.warnings else 'healthy'),
            'issues': self.issues,
            'warnings': self.warnings,
            'info': self.info
        }


def cleanup_old_files():
    """Clean up old files to save space"""
    logger.info("\n🧹 Cleaning up old files...")
    
    # Clean old images (keep last 50)
    img_dir = Path('display_images')
    if img_dir.exists():
        images = sorted(img_dir.glob('*.png'), 
                       key=lambda x: x.stat().st_mtime, 
                       reverse=True)
        
        if len(images) > 50:
            for img in images[50:]:
                if 'latest' not in img.name:  # Keep "latest" images
                    img.unlink()
                    logger.info(f"  Deleted old image: {img.name}")
    
    # Rotate logs if too large
    log_dir = Path('logs')
    if log_dir.exists():
        for log_file in log_dir.glob('*.log'):
            size_mb = log_file.stat().st_size / (1024 * 1024)
            
            if size_mb > 50:
                # Rotate log
                backup = log_file.with_suffix('.log.old')
                log_file.rename(backup)
                logger.info(f"  Rotated large log: {log_file.name}")
    
    logger.info("✓ Cleanup complete")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Boo Haus Display Health Check')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up old files')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON')
    parser.add_argument('--quiet', action='store_true',
                       help='Only show issues and warnings')
    
    args = parser.parse_args()
    
    # Run health checks
    checker = HealthChecker()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    healthy = checker.run_all_checks()
    
    # Output JSON if requested
    if args.json:
        print(json.dumps(checker.get_status_dict(), indent=2))
    
    # Cleanup if requested
    if args.cleanup:
        cleanup_old_files()
    
    # Exit code: 0 = healthy, 1 = warnings, 2 = issues
    if checker.issues:
        sys.exit(2)
    elif checker.warnings:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
