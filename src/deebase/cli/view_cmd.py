"""View commands for DeeBase CLI.

Commands:
    deebase view create <name> --sql "..."  - Create a view
    deebase view reflect <name>             - Reflect an existing view
    deebase view list                       - List all views
    deebase view drop <name>                - Drop a view
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
def view():
    """View management commands."""
    pass


@view.command('create')
@click.argument('name')
@click.option('--sql', required=True, help='SQL SELECT query for the view')
@click.option('--replace', is_flag=True, help='Replace existing view')
def create(name: str, sql: str, replace: bool):
    """Create a database view.

    Views are virtual tables based on SQL SELECT queries.
    They support read-only operations (SELECT, GET, LOOKUP).

    Examples:

        # Create a simple view
        deebase view create active_users --sql "SELECT * FROM users WHERE active = 1"

        # Create a view with joins
        deebase view create user_posts --sql "SELECT u.name, p.title FROM users u JOIN posts p ON u.id = p.author_id"

        # Replace existing view
        deebase view create active_users --sql "SELECT * FROM users WHERE status = 'active'" --replace
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    click.echo(f"Creating view '{name}'...")

    try:
        run_async(_create_view(config, name, sql, replace))
        click.echo(f"View '{name}' created successfully.")

        # Record in migration
        state = load_state(project_root)
        replace_str = ", replace=True" if replace else ""
        # Escape quotes in SQL for the migration code
        escaped_sql = sql.replace('"', '\\"')
        migration_code = f'await db.create_view("{name}", "{escaped_sql}"{replace_str})'

        try:
            append_to_migration(migration_code, project_root, state)
            click.echo(f"Recorded in migration: {state.current_migration}")
        except ValueError as e:
            click.echo(f"Warning: {e}")

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _create_view(config, name: str, sql: str, replace: bool):
    """Create a view in the database."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        await db.create_view(name, sql, replace=replace)
    finally:
        await db.close()


@view.command('reflect')
@click.argument('name')
def reflect(name: str):
    """Reflect an existing view from the database.

    Use this to make a view created outside DeeBase available
    for use with the db.v accessor.

    Example:

        deebase view reflect legacy_report_view
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_reflect_view(config, name))
        click.echo(f"View '{name}' reflected successfully.")
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _reflect_view(config, name: str):
    """Reflect a view from the database."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        await db.reflect_view(name)
    finally:
        await db.close()


@view.command('list')
def list_views():
    """List all views in the database."""
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        views = run_async(_get_views(config))
        if views:
            click.echo("Views:")
            for view_name in sorted(views):
                click.echo(f"  {view_name}")
        else:
            click.echo("No views found.")
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _get_views(config):
    """Get list of views from database."""
    from deebase import Database
    import sqlalchemy as sa

    url = config.get_database_url()
    db = Database(url)

    try:
        async with db.engine.connect() as conn:
            def _get_view_names(sync_conn):
                inspector = sa.inspect(sync_conn)
                return inspector.get_view_names()

            return await conn.run_sync(_get_view_names)
    finally:
        await db.close()


@view.command('drop')
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def drop(name: str, yes: bool):
    """Drop a view from the database.

    Unlike dropping tables, dropping a view only removes the view
    definition and does not affect the underlying data.
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Confirm unless --yes
    if not yes:
        if not click.confirm(f"Are you sure you want to drop view '{name}'?"):
            click.echo("Aborted.")
            return

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_drop_view(config, name))
        click.echo(f"View '{name}' dropped successfully.")

        # Record in migration
        state = load_state(project_root)
        migration_code = f'await db.q("DROP VIEW IF EXISTS {name}")'

        try:
            append_to_migration(migration_code, project_root, state)
            click.echo(f"Recorded in migration: {state.current_migration}")
        except ValueError as e:
            click.echo(f"Warning: {e}")

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _drop_view(config, name: str):
    """Drop a view from the database."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        await db.q(f"DROP VIEW IF EXISTS {name}")
    finally:
        await db.close()
