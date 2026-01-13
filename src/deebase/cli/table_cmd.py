"""Table commands for DeeBase CLI.

Commands:
    deebase table create <name> <fields...> - Create a new table
    deebase table list                       - List all tables
    deebase table schema <name>              - Show table schema
    deebase table drop <name>                - Drop a table
"""

import click
import sys
from pathlib import Path

from .utils import run_async
from .parser import parse_field, FieldDefinition
from .generator import generate_class_source, generate_create_call, generate_migration_code
from .state import (
    find_project_root,
    load_config,
    load_env,
    load_state,
    append_to_migration,
)


@click.group()
def table():
    """Table management commands."""
    pass


@table.command('create')
@click.argument('name')
@click.argument('fields', nargs=-1, required=True)
@click.option('--pk', default='id', help='Primary key column(s), comma-separated for composite')
@click.option('--index', '-i', 'indexes', multiple=True, help='Create index on column(s)')
@click.option('--if-not-exists', is_flag=True, help="Don't error if table exists")
@click.option('--description', '-d', help='Table/model description (becomes class docstring)')
def create(name: str, fields: tuple, pk: str, indexes: tuple, if_not_exists: bool, description: str):
    """Create a new table with the specified fields.

    Fields use the format: name:type[:modifier[:modifier...]][:docstring]

    Types: int, str, float, bool, bytes, Text, dict, datetime, date, time

    Modifiers:
        :unique     - UNIQUE constraint
        :nullable   - Allow NULL values
        :default=x  - Default value
        :fk=table   - Foreign key to table.id
        :fk=t.col   - Foreign key to table.column

    Field Docstrings:
        :"text"     - Field description (for OpenAPI docs)

    Examples:

        # Simple table with description
        deebase table create users id:int name:str email:str:unique --pk id \\
            --description "User accounts for the application"

        # With field docstrings
        deebase table create posts \\
            id:int \\
            'author_id:int:fk=users:"Post author"' \\
            'title:str:"Post title"' \\
            'status:str:default=draft:"Publication status"' \\
            --pk id --index author_id

        # Composite primary key
        deebase table create order_items \\
            order_id:int:fk=orders \\
            product_id:int:fk=products \\
            quantity:int:default=1 \\
            --pk order_id,product_id
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    # Parse fields
    try:
        parsed_fields = [parse_field(f) for f in fields]
    except ValueError as e:
        click.echo(f"Error parsing field: {e}")
        sys.exit(1)

    # Parse primary key
    pk_list = [p.strip() for p in pk.split(',')]

    # Validate PK columns exist
    field_names = {f.name for f in parsed_fields}
    for pk_col in pk_list:
        if pk_col not in field_names:
            click.echo(f"Error: Primary key column '{pk_col}' not found in fields.")
            sys.exit(1)

    # Generate class name (capitalize)
    class_name = name.capitalize()

    # Collect unique fields for index generation
    unique_fields = [f.name for f in parsed_fields if f.unique]

    click.echo(f"Creating table '{name}'...")

    # Generate and execute
    try:
        run_async(_create_table(
            config=config,
            table_name=name,
            class_name=class_name,
            fields=parsed_fields,
            pk=pk_list if len(pk_list) > 1 else pk_list[0],
            indexes=list(indexes),
            unique_fields=unique_fields,
            if_not_exists=if_not_exists,
        ))

        click.echo(f"Table '{name}' created successfully.")

        # Record in migration
        state = load_state(project_root)
        migration_code = generate_migration_code(
            class_name=class_name,
            fields=parsed_fields,
            pk=pk_list if len(pk_list) > 1 else pk_list[0],
            indexes=list(indexes),
        )

        try:
            append_to_migration(migration_code, project_root, state)
            click.echo(f"Recorded in migration: {state.current_migration}")
        except ValueError as e:
            click.echo(f"Warning: {e}")

        # Update models file
        _update_models_file(config, project_root, class_name, parsed_fields, description)

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _create_table(
    config,
    table_name: str,
    class_name: str,
    fields: list[FieldDefinition],
    pk,
    indexes: list[str],
    unique_fields: list[str],
    if_not_exists: bool,
):
    """Create the table in the database."""
    from deebase import Database, Text, ForeignKey, Index

    url = config.get_database_url()
    db = Database(url)

    try:
        # Reflect existing tables so FK references can find them
        await db.reflect()

        # Build class dynamically
        annotations = {}
        defaults = {}

        for field in fields:
            # Build type annotation
            if field.is_foreign_key:
                # Create ForeignKey type
                base_type = _get_python_type(field.type_name)
                ref = f"{field.fk_table}.{field.fk_column}" if field.fk_column != 'id' else field.fk_table
                annotations[field.name] = ForeignKey[base_type, ref]
            elif field.nullable:
                from typing import Optional
                base_type = _get_python_type(field.type_name)
                annotations[field.name] = Optional[base_type]
            else:
                annotations[field.name] = _get_python_type(field.type_name)

            # Set default if present
            if field.default is not None:
                defaults[field.name] = field.default

        # Create class
        cls = type(class_name, (), {'__annotations__': annotations, **defaults})

        # Build index list
        index_list = []
        for idx in indexes:
            if ',' in idx:
                # Composite index
                cols = tuple(c.strip() for c in idx.split(','))
                index_list.append(cols)
            else:
                index_list.append(idx)

        # Add unique indexes
        for field_name in unique_fields:
            idx_name = f"ix_{table_name}_{field_name}"
            index_list.append(Index(idx_name, field_name, unique=True))

        # Create table
        await db.create(cls, pk=pk, indexes=index_list if index_list else None, if_not_exists=if_not_exists)

    finally:
        await db.close()


def _get_python_type(type_name: str):
    """Get the Python type for a type name."""
    from datetime import datetime, date, time
    from deebase import Text

    type_map = {
        'int': int,
        'str': str,
        'float': float,
        'bool': bool,
        'bytes': bytes,
        'Text': Text,
        'text': Text,
        'dict': dict,
        'json': dict,
        'datetime': datetime,
        'date': date,
        'time': time,
    }
    return type_map.get(type_name, str)


def _update_models_file(config, project_root: Path, class_name: str, fields: list[FieldDefinition], description: str = None):
    """Update the models file with the new class."""
    from .generator import generate_models_code

    models_path = project_root / config.models_output
    models_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate models code
    models_code = generate_models_code(class_name, fields, description=description)

    if models_path.exists():
        # Append to existing file
        existing = models_path.read_text()
        # Check if class already exists
        if f"class {class_name}:" in existing:
            click.echo(f"Note: {class_name} already exists in {config.models_output}")
            return

        # Append with newlines
        new_content = existing.rstrip() + "\n\n\n" + models_code + "\n"
        models_path.write_text(new_content)
    else:
        # Create new file with header
        header = '"""Auto-generated database models."""\n\n'
        models_path.write_text(header + models_code + "\n")

    click.echo(f"Updated models file: {config.models_output}")


@table.command('list')
def list_tables():
    """List all tables in the database."""
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        tables = run_async(_get_tables(config))
        if tables:
            click.echo("Tables:")
            for table_name in sorted(tables):
                click.echo(f"  {table_name}")
        else:
            click.echo("No tables found.")
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _get_tables(config):
    """Get list of tables from database."""
    from deebase import Database
    import sqlalchemy as sa

    url = config.get_database_url()
    db = Database(url)

    try:
        async with db.engine.connect() as conn:
            def _get_table_names(sync_conn):
                inspector = sa.inspect(sync_conn)
                return inspector.get_table_names()

            return await conn.run_sync(_get_table_names)
    finally:
        await db.close()


@table.command('schema')
@click.argument('name')
def schema(name: str):
    """Show the schema for a table.

    Displays column names, types, constraints, and indexes.
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        schema_info = run_async(_get_table_schema(config, name))
        _print_schema(name, schema_info)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _get_table_schema(config, table_name: str):
    """Get schema information for a table."""
    from deebase import Database
    import sqlalchemy as sa

    url = config.get_database_url()
    db = Database(url)

    try:
        async with db.engine.connect() as conn:
            def _inspect_table(sync_conn):
                inspector = sa.inspect(sync_conn)

                columns = inspector.get_columns(table_name)
                pk = inspector.get_pk_constraint(table_name)
                fks = inspector.get_foreign_keys(table_name)
                indexes = inspector.get_indexes(table_name)
                uniques = inspector.get_unique_constraints(table_name)

                return {
                    'columns': columns,
                    'primary_key': pk,
                    'foreign_keys': fks,
                    'indexes': indexes,
                    'unique_constraints': uniques,
                }

            return await conn.run_sync(_inspect_table)
    finally:
        await db.close()


def _print_schema(table_name: str, schema_info: dict):
    """Print schema information in a readable format."""
    click.echo(f"Table: {table_name}")
    click.echo("=" * 60)

    # Columns
    click.echo("\nColumns:")
    click.echo("-" * 60)
    for col in schema_info['columns']:
        nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
        default = f" DEFAULT {col['default']}" if col.get('default') else ""
        click.echo(f"  {col['name']}: {col['type']} {nullable}{default}")

    # Primary Key
    pk = schema_info.get('primary_key', {})
    if pk and pk.get('constrained_columns'):
        click.echo(f"\nPrimary Key: {', '.join(pk['constrained_columns'])}")

    # Foreign Keys
    fks = schema_info.get('foreign_keys', [])
    if fks:
        click.echo("\nForeign Keys:")
        for fk in fks:
            local_cols = ', '.join(fk.get('constrained_columns', []))
            ref_table = fk.get('referred_table', '')
            ref_cols = ', '.join(fk.get('referred_columns', []))
            click.echo(f"  {local_cols} -> {ref_table}({ref_cols})")

    # Indexes
    indexes = schema_info.get('indexes', [])
    if indexes:
        click.echo("\nIndexes:")
        for idx in indexes:
            unique = "UNIQUE " if idx.get('unique') else ""
            cols = ', '.join(idx.get('column_names', []))
            click.echo(f"  {idx.get('name', 'unnamed')}: {unique}({cols})")

    # Unique Constraints
    uniques = schema_info.get('unique_constraints', [])
    if uniques:
        click.echo("\nUnique Constraints:")
        for uc in uniques:
            cols = ', '.join(uc.get('column_names', []))
            click.echo(f"  {uc.get('name', 'unnamed')}: ({cols})")


@table.command('drop')
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def drop(name: str, yes: bool):
    """Drop a table from the database.

    This action is irreversible and will delete all data in the table.
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Confirm unless --yes
    if not yes:
        if not click.confirm(f"Are you sure you want to drop table '{name}'? This cannot be undone."):
            click.echo("Aborted.")
            return

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_drop_table(config, name))
        click.echo(f"Table '{name}' dropped successfully.")

        # Record in migration
        state = load_state(project_root)
        migration_code = f'await db.t.{name}.drop()'
        try:
            append_to_migration(migration_code, project_root, state)
            click.echo(f"Recorded in migration: {state.current_migration}")
        except ValueError as e:
            click.echo(f"Warning: {e}")

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


async def _drop_table(config, table_name: str):
    """Drop a table from the database."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        await db.q(f"DROP TABLE IF EXISTS {table_name}")
    finally:
        await db.close()
