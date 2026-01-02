"""Database commands for DeeBase CLI.

Commands:
    deebase db info     - Show database information
    deebase db shell    - Interactive SQL shell
    deebase db backup   - Create timestamped database backup
    deebase sql "..."   - Execute raw SQL (recorded in migration)
"""

import click
import sys
from pathlib import Path

from .utils import run_async
from .state import find_project_root, load_config, load_env, load_state, append_to_migration


@click.group()
def db():
    """Database management commands."""
    pass


@db.command()
def info():
    """Show database information.

    Displays connection info, tables, views, and migration status.
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        return

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)
    state = load_state(project_root)

    click.echo("DeeBase Project Information")
    click.echo("=" * 40)
    click.echo(f"Project: {config.name} v{config.version}")
    click.echo(f"Database: {config.database_type}")

    if config.database_type == 'sqlite':
        click.echo(f"SQLite Path: {config.sqlite_path}")
    else:
        click.echo("PostgreSQL: (URL in .deebase/.env)")

    click.echo("")
    click.echo("Migration Status")
    click.echo("-" * 40)
    click.echo(f"Current Migration: {state.current_migration}")
    click.echo(f"Sealed: {'Yes' if state.sealed else 'No'}")
    click.echo(f"Database Version: {state.db_version}")

    # Try to connect and show tables/views
    click.echo("")
    click.echo("Database Objects")
    click.echo("-" * 40)

    try:
        tables, views = run_async(_get_database_objects(config))
        if tables:
            click.echo(f"Tables: {', '.join(tables)}")
        else:
            click.echo("Tables: (none)")
        if views:
            click.echo(f"Views: {', '.join(views)}")
        else:
            click.echo("Views: (none)")
    except Exception as e:
        click.echo(f"Could not connect to database: {e}")


async def _get_database_objects(config):
    """Get list of tables and views from database."""
    from deebase import Database
    import sqlalchemy as sa

    url = config.get_database_url()
    db = Database(url)

    try:
        # Get tables
        async with db.engine.connect() as conn:
            def _get_tables(sync_conn):
                inspector = sa.inspect(sync_conn)
                tables = inspector.get_table_names()
                views = inspector.get_view_names()
                return tables, views

            tables, views = await conn.run_sync(_get_tables)
            return tables, views
    finally:
        await db.close()


@db.command()
def shell():
    """Start an interactive SQL shell.

    Commands entered in the shell are NOT recorded in migrations.
    Use 'deebase sql' for recorded operations.

    Type 'exit' or 'quit' to exit the shell.
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        return

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    click.echo(f"DeeBase SQL Shell - {config.database_type}")
    click.echo("Type 'exit' or 'quit' to exit. Commands are NOT recorded in migrations.")
    click.echo("")

    while True:
        try:
            query = input("sql> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nExiting...")
            break

        if not query:
            continue

        if query.lower() in ('exit', 'quit', '.exit', '.quit'):
            click.echo("Exiting...")
            break

        # Execute query
        try:
            results = run_async(_execute_query(config, query))
            if results:
                # Format results as table
                _print_results(results)
            else:
                click.echo("Query executed successfully.")
        except Exception as e:
            click.echo(f"Error: {e}")


@db.command()
@click.option(
    "--output", "-o", type=click.Path(), help="Output directory for backup file"
)
def backup(output: str):
    """Create a timestamped database backup.

    Creates a backup of the database with a timestamp in the filename.

    For SQLite: Uses SQLite's native backup API to create a .backup file.
    For PostgreSQL: Uses pg_dump to create a SQL dump file.

    Examples:

        # Create backup in default location
        deebase db backup

        # Create backup in specific directory
        deebase db backup --output /path/to/backups/

    Note:
        PostgreSQL backups require pg_dump to be installed.
        Install PostgreSQL client tools:
        - macOS: brew install postgresql
        - Ubuntu/Debian: apt install postgresql-client
        - Windows: Install PostgreSQL and add bin/ to PATH
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    output_dir = Path(output) if output else None

    try:
        if config.database_type == "sqlite":
            from .backup import create_backup_sqlite

            db_path = project_root / config.sqlite_path
            if not db_path.exists():
                click.echo(f"Error: Database file not found: {db_path}")
                sys.exit(1)

            backup_path = create_backup_sqlite(db_path, output_dir)
            click.echo(f"Backup created: {backup_path}")

        elif config.database_type == "postgres":
            from .backup import create_backup_postgres

            db_url = config.get_database_url()
            backup_path = create_backup_postgres(db_url, output_dir)
            click.echo(f"Backup created: {backup_path}")

        else:
            click.echo(f"Error: Unknown database type: {config.database_type}")
            sys.exit(1)

    except RuntimeError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error creating backup: {e}")
        sys.exit(1)


async def _execute_query(config, query: str):
    """Execute a SQL query and return results."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        return await db.q(query)
    finally:
        await db.close()


def _print_results(results: list[dict]):
    """Print query results in a formatted table."""
    if not results:
        return

    # Get column names
    columns = list(results[0].keys())

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in results:
        for col in columns:
            val_len = len(str(row.get(col, '')))
            widths[col] = max(widths[col], min(val_len, 50))  # Max 50 chars

    # Print header
    header = " | ".join(col.ljust(widths[col])[:widths[col]] for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)
    click.echo(header)
    click.echo(separator)

    # Print rows
    for row in results:
        row_str = " | ".join(
            str(row.get(col, '')).ljust(widths[col])[:widths[col]]
            for col in columns
        )
        click.echo(row_str)

    click.echo(f"\n({len(results)} row{'s' if len(results) != 1 else ''})")


@click.command()
@click.argument('query')
@click.option('--no-record', is_flag=True, help="Don't record this query in migrations")
def sql(query: str, no_record: bool):
    """Execute raw SQL query.

    The query is executed immediately and recorded in the current migration
    file (unless --no-record is used).

    Examples:

        # Create a view (recorded in migration)
        deebase sql "CREATE VIEW active_users AS SELECT * FROM users WHERE active = 1"

        # Quick query (not recorded)
        deebase sql "SELECT COUNT(*) FROM users" --no-record
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        return

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    # Execute query
    try:
        results = run_async(_execute_query(config, query))
        if results:
            _print_results(results)
        else:
            click.echo("Query executed successfully.")

        # Record in migration if not --no-record
        if not no_record:
            state = load_state(project_root)
            migration_code = f'await db.q("{query}")'
            try:
                append_to_migration(migration_code, project_root, state)
                click.echo(f"Recorded in migration: {state.current_migration}")
            except ValueError as e:
                click.echo(f"Warning: {e}")

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
