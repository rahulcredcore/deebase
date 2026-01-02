"""Index commands for DeeBase CLI.

Commands:
    deebase index create <table> <columns> - Create an index
    deebase index list <table>             - List indexes on a table
    deebase index drop <name>              - Drop an index
"""

import click
import sys

from .utils import run_async
from .state import (
    find_project_root,
    load_config,
    load_env,
    load_state,
    append_to_migration,
)


@click.group()
def index():
    """Index management commands."""
    pass


@index.command('create')
@click.argument('table_name')
@click.argument('columns')
@click.option('--name', '-n', help='Index name (auto-generated if not provided)')
@click.option('--unique', '-u', is_flag=True, help='Create unique index')
def create(table_name: str, columns: str, name: str, unique: bool):
    """Create an index on a table.

    COLUMNS can be a single column or comma-separated list for composite indexes.

    Examples:

        # Simple index
        deebase index create users email

        # Composite index
        deebase index create posts author_id,created_at

        # Named unique index
        deebase index create users email --name ix_users_email_unique --unique
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    # Parse columns
    column_list = [c.strip() for c in columns.split(',')]

    # Generate name if not provided
    if not name:
        name = f"ix_{table_name}_{'_'.join(column_list)}"

    click.echo(f"Creating index '{name}' on {table_name}({', '.join(column_list)})...")

    try:
        run_async(_create_index(config, table_name, column_list, name, unique))
        click.echo(f"Index '{name}' created successfully.")

        # Record in migration
        state = load_state(project_root)
        if len(column_list) == 1:
            cols_str = f"'{column_list[0]}'"
        else:
            cols_str = "[" + ", ".join(f"'{c}'" for c in column_list) + "]"

        unique_str = ", unique=True" if unique else ""
        migration_code = f"await db.t.{table_name}.create_index({cols_str}, name='{name}'{unique_str})"

        try:
            append_to_migration(migration_code, project_root, state)
            click.echo(f"Recorded in migration: {state.current_migration}")
        except ValueError as e:
            click.echo(f"Warning: {e}")

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _create_index(config, table_name: str, columns: list[str], name: str, unique: bool):
    """Create an index in the database."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        # Reflect the table
        table = await db.reflect_table(table_name)
        await table.create_index(columns, name=name, unique=unique)
    finally:
        await db.close()


@index.command('list')
@click.argument('table_name')
def list_indexes(table_name: str):
    """List all indexes on a table."""
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        indexes = run_async(_get_indexes(config, table_name))
        if indexes:
            click.echo(f"Indexes on '{table_name}':")
            for idx in indexes:
                unique = "UNIQUE " if idx.get('unique') else ""
                cols = ', '.join(idx.get('columns', idx.get('column_names', [])))
                click.echo(f"  {idx.get('name', 'unnamed')}: {unique}({cols})")
        else:
            click.echo(f"No indexes on '{table_name}'.")
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _get_indexes(config, table_name: str):
    """Get list of indexes on a table."""
    from deebase import Database
    import sqlalchemy as sa

    url = config.get_database_url()
    db = Database(url)

    try:
        async with db.engine.connect() as conn:
            def _inspect_indexes(sync_conn):
                inspector = sa.inspect(sync_conn)
                return inspector.get_indexes(table_name)

            return await conn.run_sync(_inspect_indexes)
    finally:
        await db.close()


@index.command('drop')
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def drop(name: str, yes: bool):
    """Drop an index by name.

    Note: The index name is required. Use 'deebase index list <table>'
    to see index names.
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Confirm unless --yes
    if not yes:
        if not click.confirm(f"Are you sure you want to drop index '{name}'?"):
            click.echo("Aborted.")
            return

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_drop_index(config, name))
        click.echo(f"Index '{name}' dropped successfully.")

        # Record in migration
        state = load_state(project_root)
        migration_code = f'await db.q("DROP INDEX {name}")'

        try:
            append_to_migration(migration_code, project_root, state)
            click.echo(f"Recorded in migration: {state.current_migration}")
        except ValueError as e:
            click.echo(f"Warning: {e}")

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _drop_index(config, index_name: str):
    """Drop an index from the database."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        await db.q(f"DROP INDEX IF EXISTS {index_name}")
    finally:
        await db.close()
