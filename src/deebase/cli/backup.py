"""Database backup functions for DeeBase CLI.

Provides backup functionality for SQLite and PostgreSQL databases.

Functions:
    create_backup_sqlite: Create SQLite backup using native API
    create_backup_postgres: Create PostgreSQL backup using pg_dump
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def create_backup_sqlite(db_path: Path, output_dir: Path = None) -> Path:
    """Create a timestamped backup using SQLite's backup mechanism.

    Uses SQLite's native backup API for consistent backups, even while
    the database is being accessed.

    Args:
        db_path: Path to the SQLite database file
        output_dir: Directory for backup file (default: same as db_path)

    Returns:
        Path to the backup file

    Raises:
        FileNotFoundError: If the database file doesn't exist
        RuntimeError: If the backup fails

    Example:
        >>> backup_path = create_backup_sqlite(Path("data/app.db"))
        >>> print(f"Backup created: {backup_path}")
        Backup created: data/app.20240115_143022.backup
    """
    import sqlite3

    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_dir or db_path.parent
    backup_path = output_dir / f"{db_path.stem}.{timestamp}.backup"

    # Use SQLite's backup API for consistency
    try:
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_path)
        source.backup(dest)
        source.close()
        dest.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"SQLite backup failed: {e}") from e

    return backup_path


def create_backup_postgres(
    db_url: str, output_dir: Path = None, filename: str = None
) -> Path:
    """Create a timestamped backup using pg_dump.

    Uses the standard PostgreSQL pg_dump utility to create a SQL dump
    of the database. The dump can be restored using psql.

    Args:
        db_url: PostgreSQL connection URL (asyncpg or standard format)
        output_dir: Directory for backup file (default: current directory)
        filename: Custom filename (default: backup_TIMESTAMP.sql)

    Returns:
        Path to the backup file

    Raises:
        RuntimeError: If pg_dump is not installed or fails

    Example:
        >>> url = "postgresql://user:pass@localhost/mydb"
        >>> backup_path = create_backup_postgres(url)
        >>> print(f"Backup created: {backup_path}")
        Backup created: backup_20240115_143022.sql

    Note:
        pg_dump must be installed and available in PATH.
        Install PostgreSQL client tools:
        - macOS: brew install postgresql
        - Ubuntu/Debian: apt install postgresql-client
        - Windows: Install PostgreSQL and add bin/ to PATH
    """
    # Check if pg_dump is available
    if shutil.which("pg_dump") is None:
        raise RuntimeError(
            "pg_dump not found. Please install PostgreSQL client tools:\n"
            "  - macOS: brew install postgresql\n"
            "  - Ubuntu/Debian: apt install postgresql-client\n"
            "  - Windows: Install PostgreSQL and add bin/ to PATH"
        )

    # Convert asyncpg URL format to standard PostgreSQL format if needed
    # postgresql+asyncpg://... -> postgresql://...
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_dir or Path.cwd()

    if filename:
        backup_path = output_dir / filename
    else:
        backup_path = output_dir / f"backup_{timestamp}.sql"

    # pg_dump accepts connection URL directly
    result = subprocess.run(
        ["pg_dump", db_url, "-f", str(backup_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Sanitize error message to remove potential password info
        error_msg = result.stderr
        if "@" in error_msg:
            # Remove password from error message
            error_msg = "pg_dump failed (credentials hidden)"
        raise RuntimeError(f"pg_dump failed: {error_msg}")

    return backup_path
