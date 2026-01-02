"""Migration commands for DeeBase CLI.

Commands:
    deebase migrate up                  - Apply pending migrations
    deebase migrate up --to N           - Apply migrations up to version N
    deebase migrate down                - Rollback last migration
    deebase migrate down --to N         - Rollback to version N
    deebase migrate seal "description"  - Seal current migration and create new
    deebase migrate status              - Show migration status
"""

import click
import sys
from pathlib import Path

from .state import (
    find_project_root,
    load_config,
    load_env,
    load_state,
    save_state,
    MigrationState,
)
from .utils import run_async


@click.group()
def migrate():
    """Migration management commands.

    Apply, rollback, and manage database migrations.

    Examples:

        # Apply all pending migrations
        deebase migrate up

        # Apply up to version 3
        deebase migrate up --to 3

        # Rollback last migration
        deebase migrate down

        # Rollback to version 1
        deebase migrate down --to 1

        # Show migration status
        deebase migrate status

        # Seal current migration and start new one
        deebase migrate seal "add user preferences"
    """
    pass


@migrate.command("up")
@click.option("--to", "to_version", type=int, help="Target version (e.g., 3 for 0003)")
def up(to_version: int):
    """Apply pending migrations.

    Applies all pending migrations in order, or up to the specified
    version if --to is provided.

    Examples:

        # Apply all pending migrations
        deebase migrate up

        # Apply migrations up to version 3
        deebase migrate up --to 3
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    run_async(_migrate_up(project_root, to_version))


async def _migrate_up(project_root: Path, to_version: int = None):
    """Apply pending migrations."""
    from deebase import Database
    from .migration_runner import MigrationRunner

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)
    migrations_dir = project_root / config.migrations_directory

    if not migrations_dir.exists():
        click.echo(f"Error: Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    # Connect to database
    url = config.get_database_url()
    db = Database(url)

    try:
        runner = MigrationRunner(db, migrations_dir)
        await runner.up(to_version=to_version)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
    finally:
        await db.close()


@migrate.command("down")
@click.option(
    "--to", "to_version", type=int, default=None, help="Target version to rollback to"
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def down(to_version: int, yes: bool):
    """Rollback migrations.

    Rolls back the last applied migration, or down to the specified
    version if --to is provided.

    Examples:

        # Rollback last migration
        deebase migrate down

        # Rollback to version 1 (keeping only version 1 applied)
        deebase migrate down --to 1

        # Rollback all migrations
        deebase migrate down --to 0

        # Skip confirmation
        deebase migrate down -y
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Confirm rollback
    if not yes:
        if to_version is not None:
            msg = f"Rollback migrations to version {to_version}?"
        else:
            msg = "Rollback last migration?"

        if not click.confirm(msg):
            click.echo("Cancelled.")
            return

    run_async(_migrate_down(project_root, to_version))


async def _migrate_down(project_root: Path, to_version: int = None):
    """Rollback migrations."""
    from deebase import Database
    from .migration_runner import MigrationRunner

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)
    migrations_dir = project_root / config.migrations_directory

    if not migrations_dir.exists():
        click.echo(f"Error: Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    # Connect to database
    url = config.get_database_url()
    db = Database(url)

    try:
        runner = MigrationRunner(db, migrations_dir)
        # Pass to_version as-is: None means "rollback last one", 0 means "rollback all"
        await runner.down(to_version=to_version)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
    finally:
        await db.close()


@migrate.command('seal')
@click.argument('description')
def seal(description: str):
    """Seal the current migration and create a new one.

    Once a migration is sealed, it becomes immutable and no new
    operations can be added to it. A new migration file is created
    for subsequent changes.

    Example:

        deebase migrate seal "initial schema with users and posts"
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load state
    config = load_config(project_root)
    state = load_state(project_root)

    if state.sealed:
        click.echo(f"Migration '{state.current_migration}' is already sealed.")
        return

    # Get current migration file
    migrations_dir = project_root / config.migrations_directory
    current_file = migrations_dir / f"{state.current_migration}.py"

    if not current_file.exists():
        click.echo(f"Warning: Migration file '{current_file}' not found.")

    # Parse current version number
    current_num = int(state.current_migration.split('-')[0])

    # Create new migration name
    new_num = current_num + 1
    # Sanitize description for filename
    safe_desc = description.lower().replace(' ', '-').replace('_', '-')
    safe_desc = ''.join(c for c in safe_desc if c.isalnum() or c == '-')
    new_migration = f"{new_num:04d}-{safe_desc}"

    click.echo(f"Sealing migration: {state.current_migration}")

    # Update state
    new_state = MigrationState(
        current_migration=new_migration,
        sealed=False,
        db_version=new_num,
    )
    save_state(new_state, project_root)

    # Create new migration file
    new_file = migrations_dir / f"{new_migration}.py"
    new_file.write_text(_get_migration_template(new_migration, description))

    click.echo(f"Created new migration: {new_migration}")
    click.echo(f"  File: {new_file}")


def _get_migration_template(name: str, description: str) -> str:
    """Get template for a new migration file."""
    return f'''"""Migration: {description}

Auto-generated by deebase CLI.
"""

from deebase import Database, Text, ForeignKey, Index


async def upgrade(db: Database):
    """Apply this migration."""
    # === Operations below this line ===
    pass


async def downgrade(db: Database):
    """Reverse this migration."""
    pass
'''


@migrate.command('status')
def status():
    """Show migration status.

    Displays the current migration, whether it's sealed, and the
    database version.
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load state and config
    config = load_config(project_root)
    state = load_state(project_root)

    click.echo("Migration Status")
    click.echo("=" * 40)
    click.echo(f"Current Migration: {state.current_migration}")
    click.echo(f"Sealed: {'Yes' if state.sealed else 'No (accepting new operations)'}")
    click.echo(f"Database Version: {state.db_version}")

    # Show migration files
    migrations_dir = project_root / config.migrations_directory
    if migrations_dir.exists():
        migration_files = sorted(migrations_dir.glob('*.py'))
        if migration_files:
            click.echo("")
            click.echo("Migration Files:")
            for f in migration_files:
                is_current = f.stem == state.current_migration
                marker = " <-- current" if is_current else ""
                click.echo(f"  {f.name}{marker}")
    else:
        click.echo("")
        click.echo("No migrations directory found.")


@migrate.command('new')
@click.argument('description')
def new(description: str):
    """Create a new empty migration.

    Use this when you need to start a new migration manually,
    without sealing the previous one.

    Example:

        deebase migrate new "add user preferences"
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load config
    config = load_config(project_root)
    state = load_state(project_root)

    # Parse current version number
    current_num = int(state.current_migration.split('-')[0])

    # Create new migration name
    new_num = current_num + 1
    safe_desc = description.lower().replace(' ', '-').replace('_', '-')
    safe_desc = ''.join(c for c in safe_desc if c.isalnum() or c == '-')
    new_migration = f"{new_num:04d}-{safe_desc}"

    # Create migration file
    migrations_dir = project_root / config.migrations_directory
    new_file = migrations_dir / f"{new_migration}.py"

    if new_file.exists():
        click.echo(f"Error: Migration '{new_migration}' already exists.")
        sys.exit(1)

    new_file.write_text(_get_migration_template(new_migration, description))

    # Update state to point to new migration
    new_state = MigrationState(
        current_migration=new_migration,
        sealed=False,
        db_version=new_num,
    )
    save_state(new_state, project_root)

    click.echo(f"Created migration: {new_migration}")
    click.echo(f"  File: {new_file}")
