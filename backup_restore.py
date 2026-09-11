#!/usr/bin/env python3
"""
Boo Haus Display - Backup and Restore Utility
Backs up configuration, data, and state files
"""

import os
import json
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
import logging

from config import config

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class BackupManager:
    """Manage backups of the display system"""

    def __init__(self, backup_dir='backups'):
        self.project_root = config.project_root
        self.backup_dir = config.resolve_path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

    def _relative_path(self, path):
        path = Path(path)
        return path if path.is_absolute() else self.project_root / path

    def _add_file(self, tar, path, arcname):
        path = self._relative_path(path)
        if path.exists():
            tar.add(path, arcname=arcname)
            logger.info(f"  ✓ Added: {arcname}")
        else:
            logger.info(f"  ⊘ Skipped: {arcname} (not found)")

    def _safe_tar_members(self, tar):
        """Reject archive members that would write outside the project root."""
        root = self.project_root.resolve()
        safe_members = []

        for member in tar.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"Unsafe backup member path: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError(f"Unsupported backup member type: {member.name}")
            safe_members.append(member)

        return safe_members
    
    def create_backup(self, include_images=False, include_logs=False):
        """Create a backup of important files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"boo_haus_backup_{timestamp}"
        backup_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        logger.info("Creating backup...")
        logger.info(f"Backup file: {backup_path}")
        
        # Files to backup
        files_to_backup = [
            (config.config_file, config.config_file),
            (config.get('screens.birthday.birthday_file', 'birthdays.json'), 'birthdays.json'),
            (config.get('state_file', 'display_state.json'), 'display_state.json'),
            (config.get('screens.news.state_file', 'news_display_state.json'), 'news_display_state.json'),
            (config.get('screens.news.raw_story_file', 'combined_news_recent.json'), 'combined_news_recent.json'),
            (config.get('screens.news.story_file', 'news_stories.json'), 'news_stories.json'),
            (config.get('screens.news.cache_file', 'headline_summaries_cache.json'), 'headline_summaries_cache.json'),
            (config.get('screens.calendar.credentials_file', 'credentials.json'), 'credentials.json'),
            (config.get('screens.calendar.token_file', 'token.json'), 'token.json'),
        ]
        
        # Directories to backup
        dirs_to_backup = ['screens']
        
        if include_images:
            dirs_to_backup.append('display_images')
        
        if include_logs:
            dirs_to_backup.append('logs')
        
        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Add files
                for file, arcname in files_to_backup:
                    self._add_file(tar, file, arcname)

                # Add directories
                for dir_name in dirs_to_backup:
                    path = self._relative_path(dir_name)
                    if path.is_dir():
                        tar.add(path, arcname=dir_name)
                        logger.info(f"  ✓ Added: {dir_name}/")
            
            # Get backup size
            size_mb = backup_path.stat().st_size / (1024 * 1024)
            
            logger.info(f"\n✅ Backup created successfully!")
            logger.info(f"   File: {backup_path}")
            logger.info(f"   Size: {size_mb:.2f} MB")
            
            # Create metadata file
            self.create_backup_metadata(backup_name, backup_path, 
                                       include_images, include_logs)
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return None
    
    def create_backup_metadata(self, name, path, include_images, include_logs):
        """Create metadata file for backup"""
        metadata = {
            'name': name,
            'timestamp': datetime.now().isoformat(),
            'path': str(path),
            'size_bytes': path.stat().st_size,
            'include_images': include_images,
            'include_logs': include_logs
        }
        
        metadata_file = path.with_suffix('.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def list_backups(self):
        """List all available backups"""
        backups = sorted(self.backup_dir.glob('*.tar.gz'), 
                        key=lambda x: x.stat().st_mtime,
                        reverse=True)
        
        if not backups:
            logger.info("No backups found")
            return []
        
        logger.info("\n📦 Available backups:")
        logger.info("="*60)
        
        backup_info = []
        
        for i, backup in enumerate(backups, 1):
            size_mb = backup.stat().st_size / (1024 * 1024)
            mod_time = datetime.fromtimestamp(backup.stat().st_mtime)
            age = datetime.now() - mod_time
            
            logger.info(f"\n{i}. {backup.name}")
            logger.info(f"   Size: {size_mb:.2f} MB")
            logger.info(f"   Created: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   Age: {age.days} days, {age.seconds // 3600} hours")
            
            # Load metadata if available
            metadata_file = backup.with_suffix('.json')
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    if metadata.get('include_images'):
                        logger.info("   Includes: Images")
                    if metadata.get('include_logs'):
                        logger.info("   Includes: Logs")
                except:
                    pass
            
            backup_info.append({
                'path': backup,
                'size_mb': size_mb,
                'created': mod_time,
                'age_days': age.days
            })
        
        return backup_info
    
    def restore_backup(self, backup_file, dry_run=False, confirm=True):
        """Restore from a backup file"""
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            logger.error(f"❌ Backup file not found: {backup_file}")
            return False
        
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Restoring from: {backup_path}")
        
        # Warn about overwriting
        if not dry_run and confirm:
            response = input("\n⚠️  This will overwrite existing files. Continue? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Restore cancelled")
                return False
        
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                members = self._safe_tar_members(tar)
                
                logger.info(f"\nFiles to restore:")
                for member in members:
                    logger.info(f"  {'[would restore]' if dry_run else '✓'} {member.name}")
                
                if not dry_run:
                    tar.extractall(path=self.project_root, members=members)
                    logger.info(f"\n✅ Restore completed successfully!")
                else:
                    logger.info(f"\n✓ Dry run complete - no files were changed")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count=5):
        """Remove old backups, keeping only the most recent N"""
        backups = sorted(self.backup_dir.glob('*.tar.gz'), 
                        key=lambda x: x.stat().st_mtime,
                        reverse=True)
        
        if len(backups) <= keep_count:
            logger.info(f"Only {len(backups)} backups found, nothing to clean up")
            return
        
        logger.info(f"Keeping {keep_count} most recent backups...")
        
        for backup in backups[keep_count:]:
            logger.info(f"  Deleting: {backup.name}")
            backup.unlink()
            
            # Delete metadata file too
            metadata_file = backup.with_suffix('.json')
            if metadata_file.exists():
                metadata_file.unlink()
        
        logger.info(f"✓ Cleanup complete")


def export_config_template():
    """Export a template configuration file"""
    template = {
        "display": {
            "width": 800,
            "height": 480,
            "cycle_interval_seconds": 300,
            "save_images": True,
            "display_on_inky": True,
            "image_directory": "display_images"
        },
        "screens": {
            "weather": {"enabled": True},
            "week": {"enabled": True},
            "nfl": {"enabled": True},
            "calendar": {"enabled": False},
            "news": {"enabled": True},
            "birthday": {"enabled": True}
        },
        "special_dates": {
            "11-07": "Happy Booversary!",
            "21-03": "Happy Birthday Daddy!",
            "19-11": "Happy Birthday Mummy!",
            "29-06": "Happy Birthday Alice!",
            "22-10": "Happy Birthday Rosie!",
            "25-12": "Merry Christmas!",
            "01-01": "Happy New Year!"
        },
        "data_refresh": {
            "news_scraper_hour": 3,
            "news_scraper_enabled": True
        },
        "locations": {
            "uprn": "YOUR_UPRN_HERE",
            "postcode": "YOUR_POSTCODE_HERE"
        },
        "api_keys": {
            "openweather": "YOUR_API_KEY_HERE"
        },
        "state_file": "display_state.json"
    }
    
    filename = 'boo_haus_config_template.json'
    with open(filename, 'w') as f:
        json.dump(template, f, indent=2)
    
    logger.info(f"✓ Template configuration exported to: {filename}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Boo Haus Display Backup & Restore Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a backup (configuration and data only)
  python3 backup_restore.py --backup
  
  # Create a full backup including images and logs
  python3 backup_restore.py --backup --include-images --include-logs
  
  # List all backups
  python3 backup_restore.py --list
  
  # Restore from a backup (dry run first)
  python3 backup_restore.py --restore backups/boo_haus_backup_20250101_120000.tar.gz --dry-run
  
  # Actually restore
  python3 backup_restore.py --restore backups/boo_haus_backup_20250101_120000.tar.gz
  
  # Clean up old backups (keep only 5 most recent)
  python3 backup_restore.py --cleanup 5
        """
    )
    
    parser.add_argument('--backup', action='store_true',
                       help='Create a new backup')
    parser.add_argument('--include-images', action='store_true',
                       help='Include saved images in backup')
    parser.add_argument('--include-logs', action='store_true',
                       help='Include log files in backup')
    parser.add_argument('--list', action='store_true',
                       help='List all available backups')
    parser.add_argument('--restore', type=str, metavar='FILE',
                       help='Restore from backup file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Test restore without actually changing files')
    parser.add_argument('--cleanup', type=int, metavar='N',
                       help='Remove old backups, keeping only N most recent')
    parser.add_argument('--export-template', action='store_true',
                       help='Export template configuration file')
    
    args = parser.parse_args()
    
    manager = BackupManager()
    
    if args.export_template:
        export_config_template()
    elif args.backup:
        manager.create_backup(
            include_images=args.include_images,
            include_logs=args.include_logs
        )
    elif args.list:
        manager.list_backups()
    elif args.restore:
        manager.restore_backup(args.restore, dry_run=args.dry_run)
    elif args.cleanup is not None:
        manager.cleanup_old_backups(keep_count=args.cleanup)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
