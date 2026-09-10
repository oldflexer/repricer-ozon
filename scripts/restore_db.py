#!/usr/bin/env python
"""
Database restore script for SQLite.

Restores database from a backup file created by backup_db.py.
Supports point-in-time recovery from backup + WAL.

Usage:
    python scripts/restore_db.py BACKUP_FILE [--target-dir TARGET_DIR] [--force]
"""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings


def restore_backup(backup_path: Path, target_path: Path, force: bool = False) -> bool:
    """
    Restore database from backup.
    
    Args:
        backup_path: Path to backup file
        target_path: Path where database should be restored
        force: Overwrite existing database without confirmation
        
    Returns:
        True if restore successful, False otherwise
    """
    if not backup_path.exists():
        print(f"Error: Backup file not found: {backup_path}")
        return False
    
    if target_path.exists() and not force:
        response = input(f"Database {target_path} exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Restore cancelled")
            return False
    
    print(f"Restoring {backup_path} -> {target_path}")
    
    # Create parent directory if needed
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Verify backup integrity first
    if not verify_backup(backup_path):
        print("Backup verification failed, aborting restore")
        return False
    
    # Copy backup to target location
    try:
        shutil.copy2(backup_path, target_path)
        print(f"Database restored to: {target_path}")
    except Exception as e:
        print(f"Error copying backup: {e}")
        return False
    
    # Verify restored database
    if not verify_backup(target_path):
        print("Restored database verification failed!")
        return False
    
    print("Database restored and verified successfully")
    return True


def verify_backup(backup_path: Path) -> bool:
    """
    Verify backup integrity by checking if it can be opened and queried.
    
    Args:
        backup_path: Path to backup file
        
    Returns:
        True if backup is valid, False otherwise
    """
    try:
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        print(f"Verification passed. Tables found: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        return True
    except Exception as e:
        print(f"Verification failed: {e}")
        return False


def list_backups(backup_dir: Path, prefix: str = "") -> list[Path]:
    """List available backup files sorted by date (newest first)."""
    pattern = f"{prefix}_*.db" if prefix else "*.db"
    backups = sorted(
        backup_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return backups


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore SQLite database from backup")
    parser.add_argument(
        "backup_file",
        type=Path,
        nargs="?",
        help="Backup file to restore (if omitted, lists available backups)"
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Target directory for restored database (default: original location)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing database without confirmation"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups and exit"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("backups"),
        help="Directory containing backups (default: backups/)"
    )
    
    args = parser.parse_args()
    
    backup_dir = args.backup_dir
    if not backup_dir.exists():
        print(f"Backup directory not found: {backup_dir}")
        sys.exit(1)
    
    # List available backups
    if args.list or args.backup_file is None:
        backups = list_backups(backup_dir, settings.database_path_path.stem)
        if not backups:
            print("No backups found")
            return
        
        print("Available backups:")
        for i, backup in enumerate(backups):
            mtime = backup.stat().st_mtime
            from datetime import datetime
            dt = datetime.fromtimestamp(mtime)
            size_mb = backup.stat().st_size / (1024 * 1024)
            print(f"  {i+1}. {backup.name} ({dt.strftime('%Y-%m-%d %H:%M')}, {size_mb:.1f} MB)")
        return
    
    backup_path = args.backup_file
    # If it's a relative path and doesn't exist as-is, try relative to backup_dir
    if not backup_path.is_absolute() and not backup_path.exists():
        backup_path = backup_dir / backup_path
    
    target_path = args.target_dir or settings.database_path_path
    
    if restore_backup(backup_path, target_path, args.force):
        print("Restore completed successfully")
    else:
        print("Restore failed")
        sys.exit(1)


if __name__ == "__main__":
    main()