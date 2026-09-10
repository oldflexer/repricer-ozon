"""
Base repository class with connection pooling support.
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

from config.settings import settings


class BaseRepository:
    """Base repository with connection management and pooling."""
    
    # Thread-local storage for connection pooling
    _local = threading.local()
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        """
        Initialize repository.
        
        Args:
            db_path: Path to SQLite database file. Defaults to settings.
        """
        self.db_path = db_path or settings.database_path_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection from the pool or create a new one.
        
        Uses thread-local storage to maintain one connection per thread.
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {settings.SQLITE_BUSY_TIMEOUT}")
            conn.execute(f"PRAGMA journal_mode = {settings.SQLITE_JOURNAL_MODE}")
            self._local.connection = conn
        return self._local.connection  # type: ignore[no-any-return]
    
    def close_connection(self) -> None:
        """Close the thread-local connection if it exists."""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _initialize_schema(self) -> None:
        """Create tables if they don't exist (for tests and simple runs)."""
        sql_dir = Path(__file__).resolve().parent.parent.parent / "migrations" / "sql"
        
        # Execute migration 001
        sql_001 = sql_dir / "001_initial_schema.sql"
        if sql_001.exists():
            with self._get_connection() as conn, sql_001.open(encoding="utf-8") as f:
                conn.executescript(f.read())
        
        # Execute migration 002
        sql_002 = sql_dir / "002_add_daily_aggregates_and_logs.sql"
        if sql_002.exists():
            with self._get_connection() as conn, sql_002.open(encoding="utf-8") as f:
                conn.executescript(f.read())


# Backward compatibility: DBConnectionMixin
class DBConnectionMixin:
    """Mixin providing database connection (for backward compatibility)."""
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Initialize base repository for connection handling
        self._base_repo = BaseRepository()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return self._base_repo._get_connection()