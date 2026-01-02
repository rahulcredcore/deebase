"""Tests for DeeBase Migrations (Phase 14)."""

import pytest
import pytest_asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from deebase import Database
from deebase.cli.migration_runner import MigrationRunner, Migration
from deebase.cli.backup import create_backup_sqlite, create_backup_postgres


# ============================================================================
# MigrationRunner Tests
# ============================================================================


class TestMigrationRunner:
    """Tests for MigrationRunner class."""

    @pytest_asyncio.fixture
    async def db(self):
        """Create an in-memory SQLite database for testing."""
        database = Database("sqlite+aiosqlite:///:memory:")
        yield database
        await database.close()

    @pytest.fixture
    def migrations_dir(self, tmp_path):
        """Create a temporary migrations directory."""
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        return migrations

    def create_migration_file(self, migrations_dir: Path, version: int, name: str,
                               upgrade_code: str = "pass", downgrade_code: str = "pass"):
        """Helper to create a migration file."""
        filename = f"{version:04d}-{name}.py"
        content = f'''"""Migration: {name}"""

from deebase import Database

async def upgrade(db: Database):
    """Apply this migration."""
    {upgrade_code}

async def downgrade(db: Database):
    """Reverse this migration."""
    {downgrade_code}
'''
        (migrations_dir / filename).write_text(content)
        return migrations_dir / filename

    # --- Version Table Tests ---

    @pytest.mark.asyncio
    async def test_ensure_version_table_creates_table(self, db, migrations_dir):
        """Test that _ensure_version_table creates the tracking table."""
        runner = MigrationRunner(db, migrations_dir)
        await runner._ensure_version_table()

        # Verify table exists
        result = await db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_deebase_migrations'"
        )
        assert len(result) == 1
        assert result[0]["name"] == "_deebase_migrations"

    @pytest.mark.asyncio
    async def test_ensure_version_table_idempotent(self, db, migrations_dir):
        """Test that _ensure_version_table can be called multiple times safely."""
        runner = MigrationRunner(db, migrations_dir)
        await runner._ensure_version_table()
        await runner._ensure_version_table()  # Should not error

        result = await db.q("SELECT COUNT(*) as cnt FROM sqlite_master WHERE name='_deebase_migrations'")
        assert result[0]["cnt"] == 1

    @pytest.mark.asyncio
    async def test_get_current_version_empty(self, db, migrations_dir):
        """Test get_current_version returns 0 when no migrations applied."""
        runner = MigrationRunner(db, migrations_dir)
        await runner._ensure_version_table()
        version = await runner._get_current_version()
        assert version == 0

    @pytest.mark.asyncio
    async def test_record_and_get_migrations(self, db, migrations_dir):
        """Test recording migrations and retrieving them."""
        runner = MigrationRunner(db, migrations_dir)
        await runner._ensure_version_table()

        await runner._record_migration(1, "initial")
        await runner._record_migration(2, "add-users")

        applied = await runner._get_applied_migrations()
        assert applied == [1, 2]

        current = await runner._get_current_version()
        assert current == 2

    @pytest.mark.asyncio
    async def test_remove_migration(self, db, migrations_dir):
        """Test removing a migration record (for rollback)."""
        runner = MigrationRunner(db, migrations_dir)
        await runner._ensure_version_table()

        await runner._record_migration(1, "initial")
        await runner._record_migration(2, "add-users")
        await runner._remove_migration(2)

        applied = await runner._get_applied_migrations()
        assert applied == [1]

    # --- Migration Discovery Tests ---

    def test_discover_migrations_empty_dir(self, migrations_dir):
        """Test discovery with no migration files."""
        db_mock = MagicMock()
        runner = MigrationRunner(db_mock, migrations_dir)
        migrations = runner._discover_migrations()
        assert migrations == []

    def test_discover_migrations_finds_files(self, migrations_dir):
        """Test discovery finds migration files."""
        self.create_migration_file(migrations_dir, 1, "initial")
        self.create_migration_file(migrations_dir, 2, "add-users")

        db_mock = MagicMock()
        runner = MigrationRunner(db_mock, migrations_dir)
        migrations = runner._discover_migrations()

        assert len(migrations) == 2
        assert migrations[0].version == 1
        assert migrations[0].name == "initial"
        assert migrations[1].version == 2
        assert migrations[1].name == "add-users"

    def test_discover_migrations_sorted_by_version(self, migrations_dir):
        """Test migrations are sorted by version."""
        self.create_migration_file(migrations_dir, 3, "third")
        self.create_migration_file(migrations_dir, 1, "first")
        self.create_migration_file(migrations_dir, 2, "second")

        db_mock = MagicMock()
        runner = MigrationRunner(db_mock, migrations_dir)
        migrations = runner._discover_migrations()

        versions = [m.version for m in migrations]
        assert versions == [1, 2, 3]

    def test_discover_migrations_filters_by_version(self, migrations_dir):
        """Test filtering migrations by version range."""
        self.create_migration_file(migrations_dir, 1, "first")
        self.create_migration_file(migrations_dir, 2, "second")
        self.create_migration_file(migrations_dir, 3, "third")
        self.create_migration_file(migrations_dir, 4, "fourth")

        db_mock = MagicMock()
        runner = MigrationRunner(db_mock, migrations_dir)

        # Get migrations after version 1, up to version 3
        migrations = runner._discover_migrations(after=1, up_to=3)
        versions = [m.version for m in migrations]
        assert versions == [2, 3]

    def test_discover_migrations_ignores_special_files(self, migrations_dir):
        """Test that __init__.py and similar are ignored."""
        self.create_migration_file(migrations_dir, 1, "initial")
        (migrations_dir / "__init__.py").write_text("# init")
        (migrations_dir / "_private.py").write_text("# private")

        db_mock = MagicMock()
        runner = MigrationRunner(db_mock, migrations_dir)
        migrations = runner._discover_migrations()

        assert len(migrations) == 1
        assert migrations[0].version == 1

    def test_discover_migrations_ignores_invalid_names(self, migrations_dir):
        """Test that non-matching filenames are ignored."""
        self.create_migration_file(migrations_dir, 1, "initial")
        (migrations_dir / "invalid.py").write_text("# no version")
        (migrations_dir / "123-wrong.py").write_text("# wrong format")

        db_mock = MagicMock()
        runner = MigrationRunner(db_mock, migrations_dir)
        migrations = runner._discover_migrations()

        assert len(migrations) == 1

    # --- Migration Loading Tests ---

    def test_load_migration(self, migrations_dir):
        """Test loading a migration module."""
        path = self.create_migration_file(
            migrations_dir, 1, "initial",
            upgrade_code='await db.q("CREATE TABLE users (id INT)")'
        )

        db_mock = MagicMock()
        runner = MigrationRunner(db_mock, migrations_dir)
        migration = Migration(version=1, name="initial", path=path)
        loaded = runner._load_migration(migration)

        assert loaded.module is not None
        assert hasattr(loaded.module, "upgrade")
        assert hasattr(loaded.module, "downgrade")

    # --- Up Migration Tests ---

    @pytest.mark.asyncio
    async def test_up_applies_single_migration(self, db, migrations_dir):
        """Test applying a single migration."""
        self.create_migration_file(
            migrations_dir, 1, "initial",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")'
        )

        runner = MigrationRunner(db, migrations_dir)
        applied = await runner.up()

        assert len(applied) == 1
        assert applied[0].version == 1

        # Verify table was created
        result = await db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_up_applies_multiple_migrations(self, db, migrations_dir):
        """Test applying multiple migrations in order."""
        self.create_migration_file(
            migrations_dir, 1, "create-users",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")'
        )
        self.create_migration_file(
            migrations_dir, 2, "create-posts",
            upgrade_code='await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY)")'
        )

        runner = MigrationRunner(db, migrations_dir)
        applied = await runner.up()

        assert len(applied) == 2
        assert [m.version for m in applied] == [1, 2]

        # Verify both tables were created
        result = await db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'posts')"
        )
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_up_skips_applied_migrations(self, db, migrations_dir):
        """Test that already applied migrations are skipped."""
        self.create_migration_file(
            migrations_dir, 1, "initial",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")'
        )
        self.create_migration_file(
            migrations_dir, 2, "second",
            upgrade_code='await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY)")'
        )

        runner = MigrationRunner(db, migrations_dir)

        # First run applies both
        applied1 = await runner.up()
        assert len(applied1) == 2

        # Second run applies none
        applied2 = await runner.up()
        assert len(applied2) == 0

    @pytest.mark.asyncio
    async def test_up_to_specific_version(self, db, migrations_dir):
        """Test applying migrations up to a specific version."""
        self.create_migration_file(
            migrations_dir, 1, "first",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")'
        )
        self.create_migration_file(
            migrations_dir, 2, "second",
            upgrade_code='await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY)")'
        )
        self.create_migration_file(
            migrations_dir, 3, "third",
            upgrade_code='await db.q("CREATE TABLE comments (id INTEGER PRIMARY KEY)")'
        )

        runner = MigrationRunner(db, migrations_dir)
        applied = await runner.up(to_version=2)

        assert len(applied) == 2
        assert [m.version for m in applied] == [1, 2]

        # Only users and posts should exist
        result = await db.q("SELECT name FROM sqlite_master WHERE type='table' AND name='comments'")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_up_records_migrations(self, db, migrations_dir):
        """Test that applied migrations are recorded."""
        self.create_migration_file(
            migrations_dir, 1, "initial",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")'
        )

        runner = MigrationRunner(db, migrations_dir)
        await runner.up()

        # Verify migration is recorded
        result = await db.q("SELECT version, name FROM _deebase_migrations")
        assert len(result) == 1
        assert result[0]["version"] == 1
        assert result[0]["name"] == "initial"

    # --- Down Migration Tests ---

    @pytest.mark.asyncio
    async def test_down_rolls_back_last_migration(self, db, migrations_dir):
        """Test rolling back the last migration."""
        self.create_migration_file(
            migrations_dir, 1, "create-users",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")',
            downgrade_code='await db.q("DROP TABLE users")'
        )
        self.create_migration_file(
            migrations_dir, 2, "create-posts",
            upgrade_code='await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY)")',
            downgrade_code='await db.q("DROP TABLE posts")'
        )

        runner = MigrationRunner(db, migrations_dir)
        await runner.up()

        # Rollback last migration
        rolled_back = await runner.down()

        assert len(rolled_back) == 1
        assert rolled_back[0].version == 2

        # posts should be gone, users should remain
        result = await db.q("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
        assert len(result) == 0

        result = await db.q("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_down_to_specific_version(self, db, migrations_dir):
        """Test rolling back to a specific version."""
        self.create_migration_file(
            migrations_dir, 1, "first",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")',
            downgrade_code='await db.q("DROP TABLE users")'
        )
        self.create_migration_file(
            migrations_dir, 2, "second",
            upgrade_code='await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY)")',
            downgrade_code='await db.q("DROP TABLE posts")'
        )
        self.create_migration_file(
            migrations_dir, 3, "third",
            upgrade_code='await db.q("CREATE TABLE comments (id INTEGER PRIMARY KEY)")',
            downgrade_code='await db.q("DROP TABLE comments")'
        )

        runner = MigrationRunner(db, migrations_dir)
        await runner.up()

        # Rollback to version 1 (keeping only v1)
        rolled_back = await runner.down(to_version=1)

        assert len(rolled_back) == 2
        assert [m.version for m in rolled_back] == [3, 2]  # Rolled back in reverse order

    @pytest.mark.asyncio
    async def test_down_removes_migration_records(self, db, migrations_dir):
        """Test that rolled back migrations are removed from tracking."""
        self.create_migration_file(
            migrations_dir, 1, "initial",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")',
            downgrade_code='await db.q("DROP TABLE users")'
        )

        runner = MigrationRunner(db, migrations_dir)
        await runner.up()

        # Verify recorded
        result = await db.q("SELECT version FROM _deebase_migrations")
        assert len(result) == 1

        await runner.down()

        # Verify removed
        result = await db.q("SELECT version FROM _deebase_migrations")
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_down_empty_returns_empty(self, db, migrations_dir):
        """Test rolling back with no migrations applied."""
        runner = MigrationRunner(db, migrations_dir)
        await runner._ensure_version_table()

        rolled_back = await runner.down()
        assert rolled_back == []

    # --- Status Tests ---

    @pytest.mark.asyncio
    async def test_status_shows_pending(self, db, migrations_dir):
        """Test status shows pending migrations."""
        self.create_migration_file(migrations_dir, 1, "first")
        self.create_migration_file(migrations_dir, 2, "second")

        runner = MigrationRunner(db, migrations_dir)
        status = await runner.status()

        assert status["current_version"] == 0
        assert status["applied"] == []
        assert len(status["pending"]) == 2
        assert len(status["available"]) == 2

    @pytest.mark.asyncio
    async def test_status_after_up(self, db, migrations_dir):
        """Test status after applying migrations."""
        self.create_migration_file(
            migrations_dir, 1, "first",
            upgrade_code='await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")'
        )
        self.create_migration_file(migrations_dir, 2, "second")

        runner = MigrationRunner(db, migrations_dir)
        await runner.up(to_version=1)

        status = await runner.status()

        assert status["current_version"] == 1
        assert status["applied"] == [1]
        assert len(status["pending"]) == 1
        assert status["pending"][0].version == 2

    # --- Error Handling Tests ---

    @pytest.mark.asyncio
    async def test_up_rolls_back_on_error(self, db, migrations_dir):
        """Test that failed migrations roll back."""
        self.create_migration_file(
            migrations_dir, 1, "broken",
            upgrade_code='await db.q("INVALID SQL SYNTAX")'
        )

        runner = MigrationRunner(db, migrations_dir)

        with pytest.raises(Exception):
            await runner.up()

        # Migration should not be recorded
        result = await db.q("SELECT COUNT(*) as cnt FROM _deebase_migrations")
        assert result[0]["cnt"] == 0


# ============================================================================
# Backup Tests
# ============================================================================


class TestBackupSQLite:
    """Tests for SQLite backup functionality."""

    def test_create_backup_sqlite_success(self, tmp_path):
        """Test successful SQLite backup."""
        import sqlite3

        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO users (name) VALUES ('Alice')")
        conn.commit()
        conn.close()

        # Create backup
        backup_path = create_backup_sqlite(db_path)

        # Verify backup exists and has data
        assert backup_path.exists()
        assert backup_path.suffix == ".backup"

        conn = sqlite3.connect(backup_path)
        result = conn.execute("SELECT * FROM users").fetchall()
        conn.close()

        assert len(result) == 1
        assert result[0][1] == "Alice"

    def test_create_backup_sqlite_custom_output(self, tmp_path):
        """Test SQLite backup to custom directory."""
        import sqlite3

        # Create test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        conn.close()

        # Create backup in custom directory
        output_dir = tmp_path / "backups"
        output_dir.mkdir()
        backup_path = create_backup_sqlite(db_path, output_dir)

        assert backup_path.parent == output_dir
        assert backup_path.exists()

    def test_create_backup_sqlite_file_not_found(self, tmp_path):
        """Test SQLite backup with missing database."""
        db_path = tmp_path / "nonexistent.db"

        with pytest.raises(FileNotFoundError):
            create_backup_sqlite(db_path)


class TestBackupPostgres:
    """Tests for PostgreSQL backup functionality."""

    def test_create_backup_postgres_no_pg_dump(self, tmp_path):
        """Test PostgreSQL backup when pg_dump is not installed."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                create_backup_postgres("postgresql://localhost/test", tmp_path)

            assert "pg_dump not found" in str(exc_info.value)

    def test_create_backup_postgres_converts_asyncpg_url(self, tmp_path):
        """Test that asyncpg URLs are converted to standard format."""
        with patch("shutil.which", return_value="/usr/bin/pg_dump"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                create_backup_postgres(
                    "postgresql+asyncpg://user:pass@localhost/db",
                    tmp_path
                )

                # Verify URL was converted
                call_args = mock_run.call_args[0][0]
                assert "postgresql://user:pass@localhost/db" in call_args

    def test_create_backup_postgres_success(self, tmp_path):
        """Test successful PostgreSQL backup (mocked)."""
        with patch("shutil.which", return_value="/usr/bin/pg_dump"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")

                backup_path = create_backup_postgres(
                    "postgresql://localhost/test",
                    tmp_path
                )

                assert backup_path.parent == tmp_path
                assert backup_path.suffix == ".sql"

    def test_create_backup_postgres_failure(self, tmp_path):
        """Test PostgreSQL backup failure handling."""
        with patch("shutil.which", return_value="/usr/bin/pg_dump"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stderr="connection refused"
                )

                with pytest.raises(RuntimeError) as exc_info:
                    create_backup_postgres("postgresql://localhost/test", tmp_path)

                assert "pg_dump failed" in str(exc_info.value)


# ============================================================================
# enable_foreign_keys Tests
# ============================================================================


class TestEnableForeignKeys:
    """Tests for Database.enable_foreign_keys() method."""

    @pytest.mark.asyncio
    async def test_enable_foreign_keys_sqlite(self):
        """Test enable_foreign_keys on SQLite."""
        db = Database("sqlite+aiosqlite:///:memory:")

        try:
            await db.enable_foreign_keys()

            # Verify FK enforcement is on
            result = await db.q("PRAGMA foreign_keys")
            assert result[0]["foreign_keys"] == 1
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_enable_foreign_keys_enforces_fks(self):
        """Test that FKs are enforced after enabling."""
        db = Database("sqlite+aiosqlite:///:memory:")

        try:
            await db.enable_foreign_keys()

            # Create tables with FK
            await db.q("CREATE TABLE users (id INTEGER PRIMARY KEY)")
            await db.q("""
                CREATE TABLE posts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id)
                )
            """)

            # Try to insert with invalid FK (should fail)
            with pytest.raises(Exception):
                await db.q("INSERT INTO posts (user_id) VALUES (999)")
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_enable_foreign_keys_multiple_calls(self):
        """Test enable_foreign_keys can be called multiple times."""
        db = Database("sqlite+aiosqlite:///:memory:")

        try:
            await db.enable_foreign_keys()
            await db.enable_foreign_keys()  # Should not error

            result = await db.q("PRAGMA foreign_keys")
            assert result[0]["foreign_keys"] == 1
        finally:
            await db.close()


# ============================================================================
# CLI Integration Tests
# ============================================================================


class TestMigrateCLI:
    """Integration tests for migrate CLI commands."""

    def _create_project(self, tmp_path):
        """Create a minimal DeeBase project structure."""
        # Create .deebase directory
        deebase_dir = tmp_path / ".deebase"
        deebase_dir.mkdir()

        # Create config.toml
        config_content = '''[project]
name = "test"
version = "0.1.0"

[database]
type = "sqlite"
sqlite_path = "data/test.db"

[models]
output = "models/tables.py"
module = "models.tables"

[migrations]
directory = "migrations"
auto_seal = false
'''
        (deebase_dir / "config.toml").write_text(config_content)

        # Create state.json
        state_content = '{"current_migration": "0000-initial", "sealed": false, "db_version": 0}'
        (deebase_dir / "state.json").write_text(state_content)

        # Create directories
        (tmp_path / "data").mkdir()
        (tmp_path / "migrations").mkdir()
        (tmp_path / "models").mkdir()

        # Create empty database
        import sqlite3
        db_path = tmp_path / "data" / "test.db"
        conn = sqlite3.connect(db_path)
        conn.close()

        return tmp_path

    def test_migrate_up_no_project(self):
        """Test migrate up fails without project."""
        from click.testing import CliRunner
        from deebase.cli import main

        runner = CliRunner()
        # Use patch to mock find_project_root to return None
        with patch("deebase.cli.migrate_cmd.find_project_root", return_value=None):
            result = runner.invoke(main, ["migrate", "up"])
            assert result.exit_code != 0
            assert "No DeeBase project found" in result.output

    def test_migrate_status_shows_info(self, tmp_path):
        """Test migrate status shows migration info."""
        from click.testing import CliRunner
        from deebase.cli import main

        project_dir = self._create_project(tmp_path)

        runner = CliRunner()
        # Use patch to make find_project_root return our project
        with patch("deebase.cli.migrate_cmd.find_project_root", return_value=project_dir):
            result = runner.invoke(main, ["migrate", "status"])
            assert result.exit_code == 0
            assert "Migration Status" in result.output


# ============================================================================
# Migration Dataclass Tests
# ============================================================================


class TestMigrationDataclass:
    """Tests for Migration dataclass."""

    def test_migration_creation(self, tmp_path):
        """Test creating a Migration object."""
        path = tmp_path / "0001-initial.py"
        migration = Migration(version=1, name="initial", path=path)

        assert migration.version == 1
        assert migration.name == "initial"
        assert migration.path == path
        assert migration.module is None

    def test_migration_with_module(self, tmp_path):
        """Test Migration with module set."""
        path = tmp_path / "0001-initial.py"
        mock_module = MagicMock()
        migration = Migration(version=1, name="initial", path=path, module=mock_module)

        assert migration.module is mock_module
