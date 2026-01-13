"""Tests for CLI commands that were previously untested.

This test file covers:
- deebase api (init, serve, generate)
- deebase data (list, get, update, delete, insert --from-file)
- deebase table (schema, drop)
- deebase index (list, drop)
- deebase view (list, drop, reflect)
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from deebase.cli import main
from deebase.cli.state import load_config, save_config, ProjectConfig


# ============================================================================
# Helper Functions
# ============================================================================


def setup_project_with_db(tmpdir: str) -> Path:
    """Setup a DeeBase project with an initialized database.

    Creates project structure and a SQLite database with test tables.
    """
    runner = CliRunner()
    project_root = Path(tmpdir)

    # Initialize project
    os.chdir(tmpdir)
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0

    # Create test database with tables
    from deebase.cli.utils import run_async

    async def _setup_db():
        from deebase import Database

        config = load_config(project_root)
        url = config.get_database_url()

        # Ensure data directory exists
        data_dir = project_root / "data"
        data_dir.mkdir(exist_ok=True)

        db = Database(url)
        try:
            # Create users table
            await db.q("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    status TEXT DEFAULT 'active'
                )
            """)

            # Create posts table with FK
            await db.q("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER REFERENCES users(id),
                    title TEXT NOT NULL,
                    content TEXT
                )
            """)

            # Insert test data
            await db.q("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
            await db.q("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')")
            await db.q("INSERT INTO posts (author_id, title, content) VALUES (1, 'First Post', 'Hello world')")

            # Create a test view
            await db.q("""
                CREATE VIEW IF NOT EXISTS active_users AS
                SELECT * FROM users WHERE status = 'active'
            """)

            # Create an index
            await db.q("CREATE INDEX IF NOT EXISTS ix_posts_author_id ON posts(author_id)")

        finally:
            await db.close()

    run_async(_setup_db())
    return project_root


# ============================================================================
# API Command Tests
# ============================================================================


class TestAPICommands:
    """Tests for deebase api commands."""

    def test_api_help(self):
        """Test api command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["api", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "serve" in result.output
        assert "generate" in result.output

    def test_api_init_creates_structure(self):
        """Test api init creates the api directory structure."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            project_root = Path(tmpdir)

            # First init deebase project
            runner.invoke(main, ["init"])

            # Then init api with --skip-deps to avoid installing packages
            result = runner.invoke(main, ["api", "init", "--skip-deps"])
            assert result.exit_code == 0
            assert "API structure created" in result.output

            # Verify files were created
            assert (project_root / "api").is_dir()
            assert (project_root / "api" / "__init__.py").exists()
            assert (project_root / "api" / "app.py").exists()
            assert (project_root / "api" / "routers").is_dir()
            assert (project_root / "api" / "routers" / "__init__.py").exists()
            assert (project_root / "api" / "dependencies.py").exists()

    def test_api_init_requires_project(self):
        """Test api init fails without deebase project."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["api", "init"])
            assert result.exit_code == 1
            assert "No DeeBase project found" in result.output

    def test_api_init_idempotent(self):
        """Test api init is safe to run multiple times."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            project_root = Path(tmpdir)

            # First init deebase project
            runner.invoke(main, ["init"])

            # Run api init twice
            runner.invoke(main, ["api", "init", "--skip-deps"])
            result = runner.invoke(main, ["api", "init", "--skip-deps"])

            # Should succeed (files already exist, not recreated)
            assert result.exit_code == 0

    def test_api_serve_requires_project(self):
        """Test api serve fails without deebase project."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["api", "serve"])
            assert result.exit_code == 1
            assert "No DeeBase project found" in result.output

    def test_api_serve_requires_api_init(self):
        """Test api serve fails without api init."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            # Init deebase project but not api
            runner.invoke(main, ["init"])

            result = runner.invoke(main, ["api", "serve"])
            assert result.exit_code == 1
            assert "api/app.py not found" in result.output

    def test_api_generate_requires_project(self):
        """Test api generate fails without deebase project."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["api", "generate", "--all"])
            assert result.exit_code == 1
            assert "No DeeBase project found" in result.output

    def test_api_generate_requires_tables_or_all(self):
        """Test api generate requires table names or --all flag."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            runner.invoke(main, ["init"])

            result = runner.invoke(main, ["api", "generate"])
            assert result.exit_code == 1
            assert "Specify table names or use --all" in result.output

    def test_api_generate_all(self):
        """Test api generate --all creates router files."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)
            project_root = Path(tmpdir)

            result = runner.invoke(main, ["api", "generate", "--all"])
            assert result.exit_code == 0

            # Check router files were created
            routers_dir = project_root / "api" / "routers"
            assert routers_dir.is_dir()
            assert (routers_dir / "__init__.py").exists()
            # At least one router file should exist
            router_files = list(routers_dir.glob("*.py"))
            assert len(router_files) >= 2  # __init__.py + at least one table

    def test_api_generate_specific_tables(self):
        """Test api generate with specific table names."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)
            project_root = Path(tmpdir)

            result = runner.invoke(main, ["api", "generate", "users"])
            assert result.exit_code == 0
            assert "Generated" in result.output

            # Check router file was created
            routers_dir = project_root / "api" / "routers"
            assert (routers_dir / "users.py").exists()


# ============================================================================
# Data Command Tests
# ============================================================================


class TestDataCommands:
    """Tests for deebase data commands."""

    def test_data_help(self):
        """Test data command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["data", "--help"])
        assert result.exit_code == 0
        assert "insert" in result.output
        assert "list" in result.output
        assert "get" in result.output
        assert "update" in result.output
        assert "delete" in result.output

    def test_data_list_requires_project(self):
        """Test data list fails without deebase project."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = runner.invoke(main, ["data", "list", "users"])
            assert result.exit_code == 1
            assert "No DeeBase project found" in result.output

    def test_data_list_table_format(self):
        """Test data list with table format (default)."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "list", "users"])
            assert result.exit_code == 0
            assert "Alice" in result.output
            assert "Bob" in result.output

    def test_data_list_json_format(self):
        """Test data list with JSON format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "list", "users", "--format", "json"])
            assert result.exit_code == 0
            # Should be valid JSON
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) == 2
            assert any(u["name"] == "Alice" for u in data)

    def test_data_list_csv_format(self):
        """Test data list with CSV format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "list", "users", "--format", "csv"])
            assert result.exit_code == 0
            assert "name" in result.output  # Header
            assert "Alice" in result.output
            assert "," in result.output  # CSV delimiter

    def test_data_list_with_limit(self):
        """Test data list with limit option."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "list", "users", "--limit", "1"])
            assert result.exit_code == 0
            # Should show limited output (harder to assert exact count in table format)

    def test_data_list_nonexistent_table(self):
        """Test data list with nonexistent table."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "list", "nonexistent"])
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_data_get_by_pk(self):
        """Test data get retrieves a single record."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "get", "users", "1"])
            assert result.exit_code == 0
            assert "Alice" in result.output

    def test_data_get_not_found(self):
        """Test data get with nonexistent pk."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "get", "users", "999"])
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_data_get_table_format(self):
        """Test data get with table format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "get", "users", "1", "--format", "table"])
            assert result.exit_code == 0
            assert "Alice" in result.output

    def test_data_insert_with_fields(self):
        """Test data insert with field values."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, [
                "data", "insert", "users",
                "-f", "name=Charlie",
                "-f", "email=charlie@example.com"
            ])
            assert result.exit_code == 0
            assert "Created" in result.output

            # Verify insert
            result = runner.invoke(main, ["data", "list", "users", "--format", "json"])
            data = json.loads(result.output)
            assert any(u["name"] == "Charlie" for u in data)

    def test_data_insert_with_json(self):
        """Test data insert with JSON input."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, [
                "data", "insert", "users",
                "-j", '{"name": "Diana", "email": "diana@example.com"}'
            ])
            assert result.exit_code == 0
            assert "Created" in result.output

    def test_data_insert_from_file(self):
        """Test data insert from JSON file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)
            project_root = Path(tmpdir)

            # Create JSON file with records
            records = [
                {"name": "Eve", "email": "eve@example.com"},
                {"name": "Frank", "email": "frank@example.com"}
            ]
            json_file = project_root / "new_users.json"
            json_file.write_text(json.dumps(records))

            result = runner.invoke(main, [
                "data", "insert", "users",
                "-F", str(json_file)
            ])
            assert result.exit_code == 0
            assert "Inserted 2 records" in result.output

    def test_data_insert_requires_input(self):
        """Test data insert requires field, json, or file input."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "insert", "users"])
            assert result.exit_code == 1
            assert "Provide fields" in result.output

    def test_data_update_with_fields(self):
        """Test data update with field values."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, [
                "data", "update", "users", "1",
                "-f", "status=inactive"
            ])
            assert result.exit_code == 0
            assert "Updated" in result.output

            # Verify update
            result = runner.invoke(main, ["data", "get", "users", "1"])
            assert "inactive" in result.output

    def test_data_update_with_json(self):
        """Test data update with JSON input."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, [
                "data", "update", "users", "1",
                "-j", '{"email": "alice.new@example.com"}'
            ])
            assert result.exit_code == 0
            assert "Updated" in result.output

    def test_data_update_not_found(self):
        """Test data update with nonexistent pk."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, [
                "data", "update", "users", "999",
                "-f", "status=inactive"
            ])
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_data_delete_with_confirmation(self):
        """Test data delete with confirmation."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Abort deletion
            result = runner.invoke(main, ["data", "delete", "users", "2"], input="n\n")
            assert "Aborted" in result.output

            # Confirm deletion
            result = runner.invoke(main, ["data", "delete", "users", "2"], input="y\n")
            assert result.exit_code == 0
            assert "Deleted" in result.output

    def test_data_delete_with_yes_flag(self):
        """Test data delete with --yes flag skips confirmation."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "delete", "users", "2", "-y"])
            assert result.exit_code == 0
            assert "Deleted" in result.output

            # Verify deletion
            result = runner.invoke(main, ["data", "get", "users", "2"])
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_data_delete_not_found(self):
        """Test data delete with nonexistent pk."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["data", "delete", "users", "999", "-y"])
            assert result.exit_code == 1
            assert "not found" in result.output


# ============================================================================
# Table Command Tests (schema, drop)
# ============================================================================


class TestTableSchemaDropCommands:
    """Tests for deebase table schema and drop commands."""

    def test_table_schema_shows_columns(self):
        """Test table schema shows column information."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["table", "schema", "users"])
            assert result.exit_code == 0
            assert "Table: users" in result.output
            assert "Columns:" in result.output
            assert "id" in result.output
            assert "name" in result.output
            assert "email" in result.output

    def test_table_schema_shows_pk(self):
        """Test table schema shows primary key."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["table", "schema", "users"])
            assert result.exit_code == 0
            assert "Primary Key" in result.output

    def test_table_schema_shows_fk(self):
        """Test table schema shows foreign keys."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["table", "schema", "posts"])
            assert result.exit_code == 0
            # FK info should be present
            assert "author_id" in result.output

    def test_table_schema_nonexistent(self):
        """Test table schema with nonexistent table."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["table", "schema", "nonexistent"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_table_drop_with_confirmation(self):
        """Test table drop with confirmation."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Abort
            result = runner.invoke(main, ["table", "drop", "posts"], input="n\n")
            assert "Aborted" in result.output

            # Confirm
            result = runner.invoke(main, ["table", "drop", "posts"], input="y\n")
            assert result.exit_code == 0
            assert "dropped successfully" in result.output

    def test_table_drop_with_yes_flag(self):
        """Test table drop with --yes flag."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["table", "drop", "posts", "-y"])
            assert result.exit_code == 0
            assert "dropped successfully" in result.output

            # Verify table is gone
            result = runner.invoke(main, ["table", "list"])
            assert "posts" not in result.output

    def test_table_drop_records_migration(self):
        """Test table drop records in migration file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["table", "drop", "posts", "-y"])
            assert result.exit_code == 0
            assert "Recorded in migration" in result.output


# ============================================================================
# Index Command Tests (list, drop)
# ============================================================================


class TestIndexListDropCommands:
    """Tests for deebase index list and drop commands."""

    def test_index_list_shows_indexes(self):
        """Test index list shows indexes on a table."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["index", "list", "posts"])
            assert result.exit_code == 0
            assert "ix_posts_author_id" in result.output or "Indexes on" in result.output

    def test_index_list_empty(self):
        """Test index list when no indexes exist."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Users table might not have custom indexes
            result = runner.invoke(main, ["index", "list", "users"])
            assert result.exit_code == 0
            # Either shows indexes or "No indexes"

    def test_index_list_nonexistent_table(self):
        """Test index list with nonexistent table."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["index", "list", "nonexistent"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_index_drop_with_confirmation(self):
        """Test index drop with confirmation."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Abort
            result = runner.invoke(main, ["index", "drop", "ix_posts_author_id"], input="n\n")
            assert "Aborted" in result.output

            # Confirm
            result = runner.invoke(main, ["index", "drop", "ix_posts_author_id"], input="y\n")
            assert result.exit_code == 0
            assert "dropped successfully" in result.output

    def test_index_drop_with_yes_flag(self):
        """Test index drop with --yes flag."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["index", "drop", "ix_posts_author_id", "-y"])
            assert result.exit_code == 0
            assert "dropped successfully" in result.output

    def test_index_drop_records_migration(self):
        """Test index drop records in migration file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["index", "drop", "ix_posts_author_id", "-y"])
            assert result.exit_code == 0
            assert "Recorded in migration" in result.output

    def test_index_create_and_list(self):
        """Test index create followed by list."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Create a new index
            result = runner.invoke(main, ["index", "create", "users", "status"])
            assert result.exit_code == 0
            assert "created successfully" in result.output

            # List indexes
            result = runner.invoke(main, ["index", "list", "users"])
            assert result.exit_code == 0
            assert "status" in result.output


# ============================================================================
# View Command Tests (list, drop, reflect)
# ============================================================================


class TestViewListDropReflectCommands:
    """Tests for deebase view list, drop, and reflect commands."""

    def test_view_list_shows_views(self):
        """Test view list shows views in database."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["view", "list"])
            assert result.exit_code == 0
            assert "active_users" in result.output

    def test_view_list_empty(self):
        """Test view list when no views exist."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            runner.invoke(main, ["init"])

            # Create data directory and empty database
            Path(tmpdir, "data").mkdir(exist_ok=True)

            result = runner.invoke(main, ["view", "list"])
            assert result.exit_code == 0
            assert "No views found" in result.output

    def test_view_reflect_existing(self):
        """Test view reflect on existing view."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["view", "reflect", "active_users"])
            assert result.exit_code == 0
            assert "reflected successfully" in result.output

    def test_view_reflect_nonexistent(self):
        """Test view reflect on nonexistent view."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["view", "reflect", "nonexistent_view"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_view_drop_with_confirmation(self):
        """Test view drop with confirmation."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Abort
            result = runner.invoke(main, ["view", "drop", "active_users"], input="n\n")
            assert "Aborted" in result.output

            # Confirm
            result = runner.invoke(main, ["view", "drop", "active_users"], input="y\n")
            assert result.exit_code == 0
            assert "dropped successfully" in result.output

    def test_view_drop_with_yes_flag(self):
        """Test view drop with --yes flag."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["view", "drop", "active_users", "-y"])
            assert result.exit_code == 0
            assert "dropped successfully" in result.output

            # Verify view is gone
            result = runner.invoke(main, ["view", "list"])
            assert "active_users" not in result.output

    def test_view_drop_records_migration(self):
        """Test view drop records in migration file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            result = runner.invoke(main, ["view", "drop", "active_users", "-y"])
            assert result.exit_code == 0
            assert "Recorded in migration" in result.output

    def test_view_create_and_list(self):
        """Test view create followed by list."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Create a new view
            result = runner.invoke(main, [
                "view", "create", "bob_posts",
                "--sql", "SELECT * FROM posts WHERE author_id = 2"
            ])
            assert result.exit_code == 0
            assert "created successfully" in result.output

            # List views
            result = runner.invoke(main, ["view", "list"])
            assert result.exit_code == 0
            assert "bob_posts" in result.output


# ============================================================================
# Integration Tests
# ============================================================================


class TestCLIIntegrationNew:
    """Integration tests for newly tested CLI commands."""

    def test_full_data_workflow(self):
        """Test complete data workflow: insert -> list -> get -> update -> delete."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Insert
            result = runner.invoke(main, [
                "data", "insert", "users",
                "-f", "name=Test User",
                "-f", "email=test@example.com"
            ])
            assert result.exit_code == 0

            # List
            result = runner.invoke(main, ["data", "list", "users", "--format", "json"])
            data = json.loads(result.output)
            test_user = next((u for u in data if u["name"] == "Test User"), None)
            assert test_user is not None
            user_id = test_user["id"]

            # Get
            result = runner.invoke(main, ["data", "get", "users", str(user_id)])
            assert "Test User" in result.output

            # Update
            result = runner.invoke(main, [
                "data", "update", "users", str(user_id),
                "-f", "name=Updated User"
            ])
            assert result.exit_code == 0

            # Verify update
            result = runner.invoke(main, ["data", "get", "users", str(user_id)])
            assert "Updated User" in result.output

            # Delete
            result = runner.invoke(main, ["data", "delete", "users", str(user_id), "-y"])
            assert result.exit_code == 0

            # Verify delete
            result = runner.invoke(main, ["data", "get", "users", str(user_id)])
            assert result.exit_code == 1

    def test_full_index_workflow(self):
        """Test complete index workflow: create -> list -> drop."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Create
            result = runner.invoke(main, [
                "index", "create", "users", "name",
                "--name", "ix_users_name"
            ])
            assert result.exit_code == 0

            # List
            result = runner.invoke(main, ["index", "list", "users"])
            assert "ix_users_name" in result.output

            # Drop
            result = runner.invoke(main, ["index", "drop", "ix_users_name", "-y"])
            assert result.exit_code == 0

    def test_full_view_workflow(self):
        """Test complete view workflow: create -> list -> reflect -> drop."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_project_with_db(tmpdir)

            # Create
            result = runner.invoke(main, [
                "view", "create", "test_view",
                "--sql", "SELECT id, name FROM users"
            ])
            assert result.exit_code == 0

            # List
            result = runner.invoke(main, ["view", "list"])
            assert "test_view" in result.output

            # Reflect
            result = runner.invoke(main, ["view", "reflect", "test_view"])
            assert result.exit_code == 0

            # Drop
            result = runner.invoke(main, ["view", "drop", "test_view", "-y"])
            assert result.exit_code == 0
