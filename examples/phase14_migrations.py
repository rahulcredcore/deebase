"""Phase 14: Migrations Example

This example demonstrates DeeBase's migration system for managing
database schema changes over time.

Key concepts:
- MigrationRunner: Executes migrations up/down
- Migration files: NNNN-description.py format
- Version tracking: _deebase_migrations table
- Rollback support: downgrade() functions
- Database backups: SQLite and PostgreSQL

Run: uv run examples/phase14_migrations.py
"""

import asyncio
import tempfile
from pathlib import Path

from deebase import Database, Text, ForeignKey


async def main():
    """Demonstrate migration functionality."""
    print("=" * 60)
    print("Phase 14: Migrations Example")
    print("=" * 60)

    # Create a temporary directory for our demo
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        migrations_dir = tmpdir / "migrations"
        migrations_dir.mkdir()
        db_path = tmpdir / "app.db"

        # =========================================================
        # Part 1: enable_foreign_keys() helper
        # =========================================================
        print("\n--- Part 1: enable_foreign_keys() ---\n")

        db = Database(f"sqlite+aiosqlite:///{db_path}")

        # SQLite has FK enforcement disabled by default
        print("Before enable_foreign_keys():")
        result = await db.q("PRAGMA foreign_keys")
        print(f"  foreign_keys = {result[0]['foreign_keys']}")

        # Enable FK enforcement
        await db.enable_foreign_keys()

        print("After enable_foreign_keys():")
        result = await db.q("PRAGMA foreign_keys")
        print(f"  foreign_keys = {result[0]['foreign_keys']}")

        # Now FKs are enforced!
        await db.close()

        # =========================================================
        # Part 2: Create Migration Files
        # =========================================================
        print("\n--- Part 2: Create Migration Files ---\n")

        # Create migration files programmatically (normally done via CLI)
        migration1 = '''"""Migration: Create users table"""

from deebase import Database

async def upgrade(db: Database):
    """Apply this migration."""
    await db.q("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE
        )
    """)
    print("  Created users table")

async def downgrade(db: Database):
    """Reverse this migration."""
    await db.q("DROP TABLE users")
    print("  Dropped users table")
'''
        (migrations_dir / "0001-create-users.py").write_text(migration1)

        migration2 = '''"""Migration: Create posts table with FK"""

from deebase import Database

async def upgrade(db: Database):
    """Apply this migration."""
    await db.q("""
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL,
            content TEXT
        )
    """)
    print("  Created posts table")

async def downgrade(db: Database):
    """Reverse this migration."""
    await db.q("DROP TABLE posts")
    print("  Dropped posts table")
'''
        (migrations_dir / "0002-create-posts.py").write_text(migration2)

        migration3 = '''"""Migration: Create comments table"""

from deebase import Database

async def upgrade(db: Database):
    """Apply this migration."""
    await db.q("""
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER REFERENCES posts(id),
            author TEXT,
            body TEXT
        )
    """)
    print("  Created comments table")

async def downgrade(db: Database):
    """Reverse this migration."""
    await db.q("DROP TABLE comments")
    print("  Dropped comments table")
'''
        (migrations_dir / "0003-create-comments.py").write_text(migration3)

        print(f"Created 3 migration files in {migrations_dir}:")
        for f in sorted(migrations_dir.glob("*.py")):
            print(f"  - {f.name}")

        # =========================================================
        # Part 3: MigrationRunner - Apply Migrations
        # =========================================================
        print("\n--- Part 3: Apply Migrations with up() ---\n")

        from deebase.cli.migration_runner import MigrationRunner

        db = Database(f"sqlite+aiosqlite:///{db_path}")
        runner = MigrationRunner(db, migrations_dir)

        # Check status before applying
        status = await runner.status()
        print(f"Before up():")
        print(f"  Current version: {status['current_version']}")
        print(f"  Applied: {status['applied']}")
        print(f"  Pending: {len(status['pending'])} migrations")

        # Apply all pending migrations
        print("\nApplying all migrations:")
        applied = await runner.up()
        print(f"\nApplied {len(applied)} migrations")

        # Check status after applying
        status = await runner.status()
        print(f"\nAfter up():")
        print(f"  Current version: {status['current_version']}")
        print(f"  Applied: {status['applied']}")
        print(f"  Pending: {len(status['pending'])} migrations")

        # Verify tables exist
        print("\nTables in database:")
        result = await db.q(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        for row in result:
            print(f"  - {row['name']}")

        # =========================================================
        # Part 4: Rollback with down()
        # =========================================================
        print("\n--- Part 4: Rollback Migrations with down() ---\n")

        # Rollback the last migration
        print("Rolling back last migration:")
        rolled_back = await runner.down()
        print(f"\nRolled back {len(rolled_back)} migration")

        status = await runner.status()
        print(f"\nAfter down():")
        print(f"  Current version: {status['current_version']}")
        print(f"  Applied: {status['applied']}")
        print(f"  Pending: {len(status['pending'])} migrations")

        # =========================================================
        # Part 5: Apply Up to Specific Version
        # =========================================================
        print("\n--- Part 5: Apply to Specific Version ---\n")

        # Rollback all first
        await runner.down(to_version=0)
        print("Rolled back all migrations")

        # Apply only up to version 2
        print("\nApplying up to version 2 only:")
        await runner.up(to_version=2)

        status = await runner.status()
        print(f"  Current version: {status['current_version']}")
        print(f"  Applied: {status['applied']}")
        print(f"  Pending: {len(status['pending'])} migration(s)")

        # =========================================================
        # Part 6: Version Tracking Table
        # =========================================================
        print("\n--- Part 6: Version Tracking Table ---\n")

        # Show the migrations tracking table
        result = await db.q("SELECT * FROM _deebase_migrations ORDER BY version")
        print("_deebase_migrations table:")
        for row in result:
            print(f"  Version {row['version']}: {row['name']} (applied at {row['applied_at']})")

        await db.close()

        # =========================================================
        # Part 7: SQLite Backup (demonstration)
        # =========================================================
        print("\n--- Part 7: Database Backup ---\n")

        from deebase.cli.backup import create_backup_sqlite

        # Create a backup
        backup_path = create_backup_sqlite(db_path, tmpdir)
        print(f"Created backup: {backup_path}")
        print(f"Backup size: {backup_path.stat().st_size} bytes")

        # Verify backup contains data
        import sqlite3
        conn = sqlite3.connect(backup_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        print(f"Tables in backup: {[t[0] for t in tables]}")

    # =========================================================
    # Summary
    # =========================================================
    print("\n" + "=" * 60)
    print("Phase 14: Migrations - Summary")
    print("=" * 60)
    print("""
New features in Phase 14:

1. db.enable_foreign_keys()
   - Enables FK enforcement on SQLite (no-op on PostgreSQL)
   - Safe to call on any database

2. MigrationRunner class
   - up() - Apply pending migrations
   - up(to_version=N) - Apply up to version N
   - down() - Rollback last migration
   - down(to_version=N) - Rollback to version N
   - status() - Get migration status

3. Migration file format: NNNN-description.py
   - upgrade(db) - Apply changes
   - downgrade(db) - Rollback changes

4. Version tracking
   - _deebase_migrations table
   - Records version, name, applied_at timestamp

5. CLI commands:
   - deebase migrate up [--to N]
   - deebase migrate down [--to N] [-y]
   - deebase db backup [--output DIR]

6. Backup functions:
   - create_backup_sqlite() - SQLite native backup
   - create_backup_postgres() - Uses pg_dump
""")


if __name__ == "__main__":
    asyncio.run(main())
