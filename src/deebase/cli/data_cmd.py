"""Data management commands for DeeBase CLI.

Commands:
    deebase data insert <table> - Insert a record
    deebase data list <table>   - List records from a table
    deebase data get <table> <pk> - Get a single record
    deebase data update <table> <pk> - Update a record
    deebase data delete <table> <pk> - Delete a record
"""

import click
import json
import sys
from pathlib import Path
from typing import Any

from .utils import run_async
from .state import (
    find_project_root,
    load_config,
    load_env,
)


@click.group()
def data():
    """Data management commands."""
    pass


@data.command('insert')
@click.argument('table')
@click.option('--from-file', '-F', type=click.Path(exists=True), help='JSON file with records')
@click.option('--field', '-f', multiple=True, help='Field values as field=value')
@click.option('--json', '-j', 'json_input', help='JSON string with record data')
def data_insert(table: str, from_file: str, field: tuple, json_input: str):
    """Insert records into a table.

    Supports three input methods:
    - Individual fields with -f/--field
    - JSON string with -j/--json
    - JSON file with -F/--from-file

    Examples:

        # Insert with individual fields
        deebase data insert users -f name=Alice -f email=alice@example.com

        # Insert with JSON string
        deebase data insert users -j '{"name": "Alice", "email": "alice@example.com"}'

        # Batch insert from JSON file
        deebase data insert users -F users.json
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_data_insert(config, project_root, table, from_file, field, json_input))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _data_insert(
    config,
    project_root: Path,
    table_name: str,
    from_file: str | None,
    fields: tuple,
    json_input: str | None,
):
    """Insert records into a table."""
    from deebase import Database
    from deebase.validation import apply_validators, validate_foreign_keys

    url = config.get_database_url()
    db = Database(url)

    try:
        # Reflect table
        await db.reflect()

        # Check table exists
        try:
            tbl = db.t[table_name]
        except AttributeError:
            click.echo(f"Error: Table '{table_name}' not found", err=True)
            sys.exit(1)

        # Load validators from project
        validators = _load_project_validators(project_root, table_name)

        if from_file:
            # Batch insert from JSON file
            with open(from_file) as f:
                records = json.load(f)

            if not isinstance(records, list):
                records = [records]

            count = 0
            for record in records:
                validated = apply_validators(record, validators)
                await validate_foreign_keys(db, tbl, validated)
                await tbl.insert(validated)
                count += 1

            click.echo(f"Inserted {count} records into {table_name}")
        else:
            # Single record
            if json_input:
                data = json.loads(json_input)
            elif fields:
                data = _parse_field_values(fields)
            else:
                click.echo("Error: Provide fields with -f, JSON with -j, or file with -F", err=True)
                sys.exit(1)

            # Validate
            validated = apply_validators(data, validators)
            await validate_foreign_keys(db, tbl, validated)

            # Insert
            record = await tbl.insert(validated)

            # Get PK column name
            pk_cols = list(tbl.sa_table.primary_key.columns)
            if pk_cols:
                pk_col = pk_cols[0].name
                click.echo(f"Created {table_name} with {pk_col}: {record[pk_col]}")
            else:
                click.echo(f"Created record in {table_name}")

    finally:
        await db.close()


@data.command('list')
@click.argument('table')
@click.option('--limit', '-l', type=int, default=100, help='Max records to show')
@click.option('--format', '-f', 'fmt', type=click.Choice(['table', 'json', 'csv']), default='table', help='Output format')
def data_list(table: str, limit: int, fmt: str):
    """List records from a table.

    Examples:

        # List with default table format
        deebase data list users

        # Limit results
        deebase data list users --limit 10

        # JSON output
        deebase data list users --format json

        # CSV output
        deebase data list users --format csv
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_data_list(config, table, limit, fmt))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _data_list(config, table_name: str, limit: int, fmt: str):
    """List records from a table."""
    from deebase import Database

    url = config.get_database_url()
    db = Database(url)

    try:
        # Reflect table
        await db.reflect()

        # Check table exists
        try:
            tbl = db.t[table_name]
        except AttributeError:
            click.echo(f"Error: Table '{table_name}' not found", err=True)
            sys.exit(1)

        # Get records
        records = await tbl(limit=limit)

        if not records:
            click.echo(f"No records found in {table_name}")
            return

        # Output in requested format
        if fmt == 'json':
            _output_json(records)
        elif fmt == 'csv':
            _output_csv(records)
        else:
            _output_table(records)

    finally:
        await db.close()


@data.command('get')
@click.argument('table')
@click.argument('pk')
@click.option('--format', '-f', 'fmt', type=click.Choice(['json', 'table']), default='json', help='Output format')
def data_get(table: str, pk: str, fmt: str):
    """Get a single record by primary key.

    Examples:

        # Get user with ID 1
        deebase data get users 1

        # Get in table format
        deebase data get users 1 --format table
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_data_get(config, table, pk, fmt))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _data_get(config, table_name: str, pk: str, fmt: str):
    """Get a single record by primary key."""
    from deebase import Database
    from deebase.exceptions import NotFoundError

    url = config.get_database_url()
    db = Database(url)

    try:
        # Reflect table
        await db.reflect()

        # Check table exists
        try:
            tbl = db.t[table_name]
        except AttributeError:
            click.echo(f"Error: Table '{table_name}' not found", err=True)
            sys.exit(1)

        # Try to convert pk to int if it looks like a number
        try:
            pk_value: Any = int(pk)
        except ValueError:
            pk_value = pk

        # Get record
        try:
            record = await tbl[pk_value]
        except NotFoundError:
            click.echo(f"Error: Record with pk={pk} not found in {table_name}", err=True)
            sys.exit(1)

        # Output
        if fmt == 'json':
            _output_json([record] if isinstance(record, dict) else [dict(record.__dict__) if hasattr(record, '__dict__') else record])
            # Actually just output the single record
            if isinstance(record, dict):
                click.echo(json.dumps(record, indent=2, default=str))
            else:
                click.echo(json.dumps(dict(record.__dict__) if hasattr(record, '__dict__') else record, indent=2, default=str))
        else:
            _output_table([record])

    finally:
        await db.close()


@data.command('update')
@click.argument('table')
@click.argument('pk')
@click.option('--field', '-f', multiple=True, help='Field values as field=value')
@click.option('--json', '-j', 'json_input', help='JSON string with update data')
def data_update(table: str, pk: str, field: tuple, json_input: str):
    """Update a record.

    Examples:

        # Update with individual fields
        deebase data update users 1 -f status=inactive

        # Update with JSON
        deebase data update users 1 -j '{"status": "inactive", "email": "new@example.com"}'
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_data_update(config, project_root, table, pk, field, json_input))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _data_update(
    config,
    project_root: Path,
    table_name: str,
    pk: str,
    fields: tuple,
    json_input: str | None,
):
    """Update a record."""
    from deebase import Database
    from deebase.exceptions import NotFoundError
    from deebase.validation import apply_validators, validate_foreign_keys

    url = config.get_database_url()
    db = Database(url)

    try:
        # Reflect table
        await db.reflect()

        # Check table exists
        try:
            tbl = db.t[table_name]
        except AttributeError:
            click.echo(f"Error: Table '{table_name}' not found", err=True)
            sys.exit(1)

        # Try to convert pk to int if it looks like a number
        try:
            pk_value: Any = int(pk)
        except ValueError:
            pk_value = pk

        # Get existing record
        try:
            existing = await tbl[pk_value]
        except NotFoundError:
            click.echo(f"Error: Record with pk={pk} not found in {table_name}", err=True)
            sys.exit(1)

        # Parse update data
        if json_input:
            update_data = json.loads(json_input)
        elif fields:
            update_data = _parse_field_values(fields)
        else:
            click.echo("Error: Provide fields with -f or JSON with -j", err=True)
            sys.exit(1)

        # Merge with existing record
        if isinstance(existing, dict):
            merged = {**existing, **update_data}
        else:
            merged = {**existing.__dict__, **update_data}

        # Load validators from project
        validators = _load_project_validators(project_root, table_name)

        # Validate
        validated = apply_validators(merged, validators)
        await validate_foreign_keys(db, tbl, validated)

        # Update
        await tbl.update(validated)
        click.echo(f"Updated {table_name} with pk={pk}")

    finally:
        await db.close()


@data.command('delete')
@click.argument('table')
@click.argument('pk')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def data_delete(table: str, pk: str, yes: bool):
    """Delete a record.

    Examples:

        # Delete with confirmation
        deebase data delete users 1

        # Skip confirmation
        deebase data delete users 1 -y
    """
    project_root = find_project_root()

    if project_root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)

    # Confirm unless --yes
    if not yes:
        if not click.confirm(f"Delete record with pk={pk} from {table}?"):
            click.echo("Aborted.")
            return

    # Load configuration
    load_env(project_root)
    config = load_config(project_root)

    try:
        run_async(_data_delete(config, table, pk))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _data_delete(config, table_name: str, pk: str):
    """Delete a record."""
    from deebase import Database
    from deebase.exceptions import NotFoundError

    url = config.get_database_url()
    db = Database(url)

    try:
        # Reflect table
        await db.reflect()

        # Check table exists
        try:
            tbl = db.t[table_name]
        except AttributeError:
            click.echo(f"Error: Table '{table_name}' not found", err=True)
            sys.exit(1)

        # Try to convert pk to int if it looks like a number
        try:
            pk_value: Any = int(pk)
        except ValueError:
            pk_value = pk

        # Check record exists
        try:
            await tbl[pk_value]
        except NotFoundError:
            click.echo(f"Error: Record with pk={pk} not found in {table_name}", err=True)
            sys.exit(1)

        # Delete
        await tbl.delete(pk_value)
        click.echo(f"Deleted {table_name} with pk={pk}")

    finally:
        await db.close()


def _parse_field_values(fields: tuple) -> dict:
    """Parse field=value pairs into a dict.

    Handles type conversion for common formats:
    - Integers: "123"
    - Floats: "3.14"
    - Booleans: "true", "false"
    - JSON arrays/objects: "[1,2,3]", '{"key": "value"}'
    - Null: "null", "None"
    - Everything else: string

    Args:
        fields: Tuple of "field=value" strings

    Returns:
        Dict of field names to values
    """
    result = {}

    for f in fields:
        if '=' not in f:
            raise ValueError(f"Invalid field format: {f}. Use field=value")

        # Split only on first =
        name, value = f.split('=', 1)
        name = name.strip()
        value = value.strip()

        # Type conversion
        result[name] = _convert_value(value)

    return result


def _convert_value(value: str) -> Any:
    """Convert string value to appropriate Python type."""
    # Null
    if value.lower() in ('null', 'none'):
        return None

    # Boolean
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False

    # Try integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Try JSON (for arrays and objects)
    if value.startswith('[') or value.startswith('{'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    # String
    return value


def _load_project_validators(project_root: Path, table_name: str) -> dict:
    """Load validators from project's validators/ directory.

    Args:
        project_root: Project root directory
        table_name: Name of the table

    Returns:
        Dict of field_name -> validator_function
    """
    validators_dir = project_root / "validators"
    if not validators_dir.exists():
        return {}

    try:
        # Add project root to path temporarily
        import sys
        original_path = sys.path.copy()
        sys.path.insert(0, str(project_root))

        try:
            from validators import get_validators
            return get_validators(table_name)
        except ImportError:
            return {}
        finally:
            sys.path = original_path

    except Exception:
        return {}


def _output_json(records: list):
    """Output records as JSON."""
    # Convert records to dicts if needed
    output = []
    for r in records:
        if isinstance(r, dict):
            output.append(r)
        elif hasattr(r, '__dict__'):
            output.append({k: v for k, v in r.__dict__.items() if not k.startswith('_')})
        else:
            output.append(r)

    click.echo(json.dumps(output, indent=2, default=str))


def _output_csv(records: list):
    """Output records as CSV."""
    import csv
    import io

    if not records:
        return

    # Get column names from first record
    first = records[0]
    if isinstance(first, dict):
        columns = list(first.keys())
    elif hasattr(first, '__dict__'):
        columns = [k for k in first.__dict__.keys() if not k.startswith('_')]
    else:
        click.echo("Cannot convert records to CSV")
        return

    # Write CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()

    for r in records:
        if isinstance(r, dict):
            writer.writerow(r)
        elif hasattr(r, '__dict__'):
            writer.writerow({k: v for k, v in r.__dict__.items() if not k.startswith('_')})

    click.echo(output.getvalue().strip())


def _output_table(records: list):
    """Output records as a table."""
    if not records:
        return

    # Get column names from first record
    first = records[0]
    if isinstance(first, dict):
        columns = list(first.keys())
        get_value = lambda r, c: r.get(c, '')
    elif hasattr(first, '__dict__'):
        columns = [k for k in first.__dict__.keys() if not k.startswith('_')]
        get_value = lambda r, c: getattr(r, c, '')
    else:
        click.echo("Cannot format records as table")
        return

    # Calculate column widths
    widths = {c: len(c) for c in columns}
    for r in records:
        for c in columns:
            val = str(get_value(r, c))
            widths[c] = max(widths[c], min(len(val), 50))  # Cap at 50 chars

    # Print header
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    click.echo(header)
    click.echo("-" * len(header))

    # Print rows
    for r in records:
        row_values = []
        for c in columns:
            val = str(get_value(r, c))
            if len(val) > 50:
                val = val[:47] + "..."
            row_values.append(val.ljust(widths[c]))
        click.echo(" | ".join(row_values))
