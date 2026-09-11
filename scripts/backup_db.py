#!/usr/bin/env python
"""
Database backup script for SQLite.

Creates a consistent backup using SQLite's .backup() API with WAL checkpoint.
Can be scheduled via cron/systemd for regular backups.

Usage:
    python scripts/backup_db.py [--output-dir BACKUP_DIR] [--keep N]
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings


def create_backup(backup_dir: Path, db_path: Path, keep: int = 7) -> Path:
    """
    Create a consistent backup of the SQLite database.
    
    Uses SQLite's backup API which handles WAL checkpointing automatically
    and provides a consistent snapshot even if the database is in use.
    
    Args:
        backup_dir: Directory to store backups
        db_path: Path to the source database
        keep: Number of recent backups to keep (older ones deleted)
        
    Returns:
        Path to the created backup file
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{db_path.stem}_{timestamp}.db"
    backup_path = backup_dir / backup_name
    
    print(f"Creating backup: {backup_path}")
    
    # Use SQLite's backup API for consistent backup
    # This handles WAL checkpointing automatically
    source_conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    dest_conn = sqlite3.connect(backup_path)
    
    try:
        with dest_conn:
            source_conn.backup(dest_conn)
        print(f"Backup created successfully: {backup_path}")
    finally:
        source_conn.close()
        dest_conn.close()
    
    # Clean up old backups
    cleanup_old_backups(backup_dir, db_path.stem, keep)
    
    return backup_path


def cleanup_old_backups(backup_dir: Path, prefix: str, keep: int) -> None:
    """Remove old backups, keeping only the most recent N."""
    backups = sorted(
        backup_dir.glob(f"{prefix}_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    for old_backup in backups[keep:]:
        print(f"Removing old backup: {old_backup}")
        old_backup.unlink()


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
        print(f"Backup verification passed. Tables found: {len(tables)}")
        return True
    except Exception as e:
        print(f"Backup verification failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Create SQLite database backup")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backups"),
        help="Directory to store backups (default: backups/)"
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Number of recent backups to keep (default: 7)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify backup after creation"
    )
    
    args = parser.parse_args()
    
    db_path = settings.database_path_path
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    backup_path = create_backup(args.output_dir, db_path, args.keep)
    
    if args.verify:
        if not verify_backup(backup_path):
            sys.exit(1)
    
    print("Backup completed successfully")


if __name__ == "__main__":
    main()