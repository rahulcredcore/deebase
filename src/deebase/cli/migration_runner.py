"""Migration runner for DeeBase CLI.

Provides functionality to apply and rollback database migrations.

Classes:
    Migration: Dataclass representing a single migration file
    MigrationRunner: Executes migrations up/down and tracks versions

Example:
    >>> runner = MigrationRunner(db, Path("migrations"))
    >>> await runner.up()  # Apply all pending migrations
    >>> await runner.down()  # Rollback last migration
"""

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from deebase import Database


@dataclass
class Migration:
    """Represents a migration file.

    Attributes:
        version: Migration version number (e.g., 1 for 0001-initial.py)
        name: Migration description (e.g., 'initial' from 0001-initial.py)
        path: Path to the migration file
        module: Loaded Python module (set after loading)
    """

    version: int
    name: str
    path: Path
    module: Optional[object] = None


class MigrationRunner:
    """Executes database migrations.

    Handles discovering, loading, and executing migration files.
    Tracks applied migrations in the _deebase_migrations table.

    Attributes:
        db: Database instance for executing migrations
        migrations_dir: Directory containing migration files

    Example:
        >>> from deebase import Database
        >>> from deebase.cli.migration_runner import MigrationRunner
        >>>
        >>> db = Database("sqlite+aiosqlite:///app.db")
        >>> runner = MigrationRunner(db, Path("migrations"))
        >>>
        >>> # Apply all pending migrations
        >>> await runner.up()
        >>>
        >>> # Apply up to a specific version
        >>> await runner.up(to_version=3)
        >>>
        >>> # Rollback last migration
        >>> await runner.down()
        >>>
        >>> # Rollback to a specific version
        >>> await runner.down(to_version=1)
        >>>
        >>> # Check migration status
        >>> status = await runner.status()
        >>> print(f"Current version: {status['current_version']}")
        >>> print(f"Pending: {len(status['pending'])}")
    """

    # Version tracking table name
    VERSION_TABLE = "_deebase_migrations"

    def __init__(self, db: "Database", migrations_dir: Path):
        """Initialize the migration runner.

        Args:
            db: Database instance for executing migrations
            migrations_dir: Directory containing migration files
        """
        self.db = db
        self.migrations_dir = migrations_dir

    async def up(self, to_version: Optional[int] = None) -> list[Migration]:
        """Apply pending migrations up to target version.

        Args:
            to_version: Target version to migrate to (None = apply all pending)

        Returns:
            List of applied migrations

        Example:
            >>> applied = await runner.up()
            >>> for m in applied:
            ...     print(f"Applied: {m.version:04d}-{m.name}")
        """
        await self._ensure_version_table()
        current = await self._get_current_version()
        pending = self._discover_migrations(after=current, up_to=to_version)

        applied = []
        for migration in pending:
            # Load the migration module
            migration = self._load_migration(migration)

            # Check that upgrade function exists
            if not hasattr(migration.module, "upgrade"):
                raise RuntimeError(
                    f"Migration {migration.version:04d}-{migration.name} "
                    f"has no upgrade() function"
                )

            # Execute migration in a transaction
            async with self.db.transaction():
                await migration.module.upgrade(self.db)
                await self._record_migration(migration.version, migration.name)

            applied.append(migration)
            print(f"Applied: {migration.version:04d}-{migration.name}")

        if not applied:
            print("No pending migrations.")

        return applied

    async def down(self, to_version: Optional[int] = None) -> list[Migration]:
        """Rollback migrations down to target version.

        Args:
            to_version: Target version to rollback to. Options:
                - None (default): Rollback only the last applied migration
                - 0: Rollback ALL migrations (back to clean slate)
                - N: Rollback to version N (keeping N and below applied)

        Returns:
            List of rolled back migrations

        Example:
            >>> rolled_back = await runner.down()  # Rollback last migration
            >>> rolled_back = await runner.down(to_version=0)  # Rollback all
            >>> rolled_back = await runner.down(to_version=1)  # Rollback to v1
        """
        await self._ensure_version_table()
        current = await self._get_current_version()

        if current == 0:
            print("No migrations to rollback.")
            return []

        # If no target specified, rollback just the last one
        if to_version is None:
            # Rollback to version (current - 1), i.e., rollback just the latest
            to_version = current - 1

        # Get migrations to rollback (in reverse order)
        to_rollback = self._discover_migrations(after=to_version, up_to=current)

        rolled_back = []
        for migration in reversed(to_rollback):
            # Load the migration module
            migration = self._load_migration(migration)

            # Check that downgrade function exists and is not just 'pass'
            if not hasattr(migration.module, "downgrade"):
                raise RuntimeError(
                    f"Migration {migration.version:04d}-{migration.name} "
                    f"has no downgrade() function"
                )

            # Execute rollback in a transaction
            async with self.db.transaction():
                await migration.module.downgrade(self.db)
                await self._remove_migration(migration.version)

            rolled_back.append(migration)
            print(f"Rolled back: {migration.version:04d}-{migration.name}")

        if not rolled_back:
            print("Nothing to rollback.")

        return rolled_back

    async def status(self) -> dict:
        """Get migration status.

        Returns:
            Dictionary with:
                - current_version: Highest applied migration version
                - applied: List of applied migration versions
                - pending: List of pending Migration objects
                - available: List of all available Migration objects

        Example:
            >>> status = await runner.status()
            >>> print(f"Current: {status['current_version']}")
            >>> print(f"Applied: {status['applied']}")
            >>> print(f"Pending: {len(status['pending'])} migrations")
        """
        await self._ensure_version_table()
        applied = await self._get_applied_migrations()
        available = self._discover_migrations()
        pending = [m for m in available if m.version not in applied]

        return {
            "current_version": max(applied) if applied else 0,
            "applied": sorted(applied),
            "pending": pending,
            "available": available,
        }

    # --- Private Methods ---

    async def _ensure_version_table(self) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        await self.db.q(f"""
            CREATE TABLE IF NOT EXISTS {self.VERSION_TABLE} (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def _get_current_version(self) -> int:
        """Get the highest applied migration version.

        Returns:
            Highest version number, or 0 if no migrations applied
        """
        result = await self.db.q(
            f"SELECT MAX(version) as v FROM {self.VERSION_TABLE}"
        )
        return result[0]["v"] or 0 if result else 0

    async def _get_applied_migrations(self) -> list[int]:
        """Get all applied migration versions.

        Returns:
            List of version numbers in ascending order
        """
        result = await self.db.q(
            f"SELECT version FROM {self.VERSION_TABLE} ORDER BY version"
        )
        return [r["version"] for r in result]

    async def _record_migration(self, version: int, name: str) -> None:
        """Record a migration as applied.

        Args:
            version: Migration version number
            name: Migration name/description
        """
        # Use parameterized query to avoid SQL injection
        await self.db.q(
            f"INSERT INTO {self.VERSION_TABLE} (version, name) "
            f"VALUES ({version}, '{name}')"
        )

    async def _remove_migration(self, version: int) -> None:
        """Remove a migration record (for rollback).

        Args:
            version: Migration version number to remove
        """
        await self.db.q(
            f"DELETE FROM {self.VERSION_TABLE} WHERE version = {version}"
        )

    def _discover_migrations(
        self, after: int = 0, up_to: Optional[int] = None
    ) -> list[Migration]:
        """Discover migration files in the migrations directory.

        Args:
            after: Only include migrations with version > after
            up_to: Only include migrations with version <= up_to

        Returns:
            List of Migration objects in version order
        """
        if not self.migrations_dir.exists():
            return []

        migrations = []
        # Pattern: NNNN-description.py (4 digits, hyphen, description)
        pattern = re.compile(r"^(\d{4})-(.+)\.py$")

        for path in sorted(self.migrations_dir.glob("*.py")):
            # Skip __init__.py and other special files
            if path.name.startswith("_"):
                continue

            match = pattern.match(path.name)
            if match:
                version = int(match.group(1))
                name = match.group(2)

                # Apply version filters
                if version > after and (up_to is None or version <= up_to):
                    migrations.append(Migration(version=version, name=name, path=path))

        # Sort by version
        return sorted(migrations, key=lambda m: m.version)

    def _load_migration(self, migration: Migration) -> Migration:
        """Load a migration module from its file.

        Args:
            migration: Migration with path to load

        Returns:
            Migration with module attribute set
        """
        spec = importlib.util.spec_from_file_location(
            f"migration_{migration.version:04d}", migration.path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load migration: {migration.path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return Migration(
            version=migration.version,
            name=migration.name,
            path=migration.path,
            module=module,
        )
