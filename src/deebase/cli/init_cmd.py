"""Initialize command for DeeBase CLI.

Creates project structure:
    .deebase/
        config.toml     - Project settings
        .env            - Database credentials (gitignored)
        state.json      - Migration state
    data/               - SQLite database files
    migrations/         - Migration files
    models/             - Generated model files
    validators/         - Shared validators for CLI and API
    displays/           - Custom field renderers for admin UI
"""

import click
from pathlib import Path

from .state import ProjectConfig, MigrationState, save_config, save_state


@click.command()
@click.option(
    '--package', '-p',
    help='Existing Python package to integrate with (models go to package/models/)'
)
@click.option(
    '--new-package',
    help='Create a new Python package with this name'
)
@click.option(
    '--postgres',
    is_flag=True,
    help='Configure for PostgreSQL instead of SQLite'
)
@click.option(
    '--name',
    help='Project name (default: current directory name)'
)
@click.pass_context
def init(ctx, package: str, new_package: str, postgres: bool, name: str):
    """Initialize a new DeeBase project.

    Creates the project structure with configuration files, migration
    directory, and model files.

    Examples:

        # Initialize standalone project
        deebase init

        # Initialize with existing Python package
        deebase init --package myapp

        # Create new Python package
        deebase init --new-package myapp

        # Initialize for PostgreSQL
        deebase init --postgres
    """
    project_root = Path.cwd()

    # Determine project name
    if name:
        project_name = name
    elif new_package:
        project_name = new_package
    elif package:
        project_name = package
    else:
        project_name = project_root.name

    click.echo(f"Initializing DeeBase project: {project_name}")

    # Check if already initialized
    deebase_dir = project_root / '.deebase'
    if deebase_dir.exists():
        if not click.confirm("Project already initialized. Reinitialize?"):
            click.echo("Aborted.")
            return
        click.echo("Reinitializing...")

    # Create new package if requested
    if new_package:
        _create_package(project_root, new_package)
        models_output = f"{new_package}/models/tables.py"
        models_module = f"{new_package}.models.tables"
    elif package:
        # Use existing package
        package_dir = project_root / package
        if not package_dir.exists():
            click.echo(f"Error: Package '{package}' not found. Use --new-package to create it.")
            ctx.exit(1)
        models_output = f"{package}/models/tables.py"
        models_module = f"{package}.models.tables"
        # Create models directory in package if needed
        models_dir = package_dir / 'models'
        models_dir.mkdir(exist_ok=True)
        (models_dir / '__init__.py').touch()
    else:
        # Standalone mode
        models_output = "models/tables.py"
        models_module = "models.tables"

    # Create directory structure
    directories = [
        '.deebase',
        'data',
        'migrations',
        'validators',  # Shared validators for CLI and API
        'displays',    # Custom field renderers for admin UI
    ]

    # Add models directory for standalone mode
    if not package and not new_package:
        directories.append('models')

    for dir_name in directories:
        dir_path = project_root / dir_name
        dir_path.mkdir(exist_ok=True)
        click.echo(f"  Created: {dir_name}/")

    # Create configuration
    config = ProjectConfig(
        name=project_name,
        database_type='postgres' if postgres else 'sqlite',
        sqlite_path='data/app.db',
        models_output=models_output,
        models_module=models_module,
    )
    save_config(config, project_root)
    click.echo("  Created: .deebase/config.toml")

    # Create .env file
    env_path = deebase_dir / '.env'
    if not env_path.exists():
        if postgres:
            env_content = '# PostgreSQL connection\nDATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname\n'
        else:
            env_content = f'# SQLite connection (optional - defaults to config.toml sqlite_path)\n# DATABASE_URL=sqlite+aiosqlite:///{config.sqlite_path}\n'
        env_path.write_text(env_content)
        click.echo("  Created: .deebase/.env")

    # Create state file
    state = MigrationState()
    save_state(state, project_root)
    click.echo("  Created: .deebase/state.json")

    # Create initial migration file
    migrations_dir = project_root / 'migrations'
    initial_migration = migrations_dir / '0000-initial.py'
    if not initial_migration.exists():
        initial_migration.write_text(_get_initial_migration_template())
        click.echo("  Created: migrations/0000-initial.py")

    # Create .gitignore entries
    gitignore_path = project_root / '.gitignore'
    gitignore_entries = [
        '# DeeBase',
        '.deebase/.env',
        'data/*.db',
        'data/*.db-journal',
        'data/*.db-wal',
        'data/*.db-shm',
    ]

    if gitignore_path.exists():
        existing = gitignore_path.read_text()
        new_entries = [e for e in gitignore_entries if e not in existing]
        if new_entries:
            with open(gitignore_path, 'a') as f:
                f.write('\n' + '\n'.join(new_entries) + '\n')
            click.echo("  Updated: .gitignore")
    else:
        gitignore_path.write_text('\n'.join(gitignore_entries) + '\n')
        click.echo("  Created: .gitignore")

    # Create models/__init__.py for standalone mode
    if not package and not new_package:
        models_init = project_root / 'models' / '__init__.py'
        if not models_init.exists():
            models_init.write_text('"""Generated database models."""\n')

    # Create validators/__init__.py and example.py
    validators_dir = project_root / 'validators'
    validators_init = validators_dir / '__init__.py'
    if not validators_init.exists():
        validators_init.write_text(_get_validators_init_template())
        click.echo("  Created: validators/__init__.py")

    validators_example = validators_dir / 'example.py'
    if not validators_example.exists():
        validators_example.write_text(_get_validators_example_template())
        click.echo("  Created: validators/example.py")

    # Create displays/__init__.py and example.py
    displays_dir = project_root / 'displays'
    displays_init = displays_dir / '__init__.py'
    if not displays_init.exists():
        displays_init.write_text(_get_displays_init_template())
        click.echo("  Created: displays/__init__.py")

    displays_example = displays_dir / 'example.py'
    if not displays_example.exists():
        displays_example.write_text(_get_displays_example_template())
        click.echo("  Created: displays/example.py")

    click.echo("")
    click.echo(f"Project '{project_name}' initialized successfully!")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Create tables:     deebase table create users id:int name:str email:str:unique --pk id")
    click.echo("  2. View tables:       deebase table list")
    click.echo("  3. Generate models:   deebase codegen")


def _create_package(project_root: Path, package_name: str) -> None:
    """Create a new Python package structure.

    Args:
        project_root: Project root directory
        package_name: Name of the package to create
    """
    package_dir = project_root / package_name
    package_dir.mkdir(exist_ok=True)
    (package_dir / '__init__.py').write_text(f'"""{package_name} package."""\n')

    models_dir = package_dir / 'models'
    models_dir.mkdir(exist_ok=True)
    (models_dir / '__init__.py').write_text('"""Database models."""\n')

    click.echo(f"  Created: {package_name}/")
    click.echo(f"  Created: {package_name}/__init__.py")
    click.echo(f"  Created: {package_name}/models/")
    click.echo(f"  Created: {package_name}/models/__init__.py")


def _get_initial_migration_template() -> str:
    """Get the template for the initial migration file."""
    return '''"""Initial migration.

Auto-generated by deebase init.
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


def _get_validators_init_template() -> str:
    """Get the template for validators/__init__.py."""
    return '''"""Validator registry for all tables.

Used by both CLI (deebase data) and API routes.
See validators/example.py for how to create validators.

To add validators for a table:
1. Create a file: validators/your_table.py
2. Define validator functions and VALIDATORS dict
3. Import and register here

Example:
    from . import users

    VALIDATORS = {
        "users": users.VALIDATORS,
    }
"""

# Table name -> validators dict
VALIDATORS: dict[str, dict] = {}


def get_validators(table_name: str) -> dict:
    """Get validators for a table.

    Args:
        table_name: Name of the table

    Returns:
        Dict of field_name -> validator_function
    """
    return VALIDATORS.get(table_name, {})
'''


def _get_validators_example_template() -> str:
    """Get the template for validators/example.py."""
    return '''"""Example validators - copy this file for your tables.

Validators are plain functions that:
- Receive a field value
- Return the (possibly transformed) value
- Raise ValueError with message on invalid input

These validators are used by BOTH:
- CLI: deebase data insert/update
- API: create_crud_router(validators=...)
- Admin: Web forms
"""
import re


def validate_email(value: str) -> str:
    """Validate and normalize email format."""
    if not re.match(r"^[^@]+@[^@]+\\.[^@]+$", value):
        raise ValueError("Invalid email format")
    return value.lower()  # Normalize


def validate_non_empty(value: str) -> str:
    """Ensure string is not empty or whitespace."""
    if not value or not value.strip():
        raise ValueError("Cannot be empty")
    return value.strip()


def validate_positive(value: int) -> int:
    """Ensure integer is positive."""
    if value <= 0:
        raise ValueError("Must be positive")
    return value


def validate_length(min_len: int = 0, max_len: int = None):
    """Create a length validator.

    Args:
        min_len: Minimum length (default: 0)
        max_len: Maximum length (default: None = unlimited)

    Returns:
        Validator function

    Example:
        >>> validators = {
        ...     "username": validate_length(3, 20),
        ...     "bio": validate_length(max_len=500),
        ... }
    """
    def validator(value: str) -> str:
        if len(value) < min_len:
            raise ValueError(f"Must be at least {min_len} characters")
        if max_len is not None and len(value) > max_len:
            raise ValueError(f"Must be at most {max_len} characters")
        return value
    return validator


# Register validators for this table
# Uncomment and modify as needed:
VALIDATORS = {
    # "email": validate_email,
    # "name": validate_non_empty,
}
'''


def _get_displays_init_template() -> str:
    """Get the template for displays/__init__.py."""
    return '''"""Custom field displays for admin UI.

Used by the admin interface to render field values.
See displays/example.py for how to create custom displays.

To add displays for a table:
1. Create a file: displays/your_table.py
2. Define display functions and DISPLAYS dict
3. The admin UI will auto-discover them

Example:
    # displays/articles.py
    def render_history(value, record):
        return "<pre>" + json.dumps(value, indent=2) + "</pre>"

    DISPLAYS = {
        "history": render_history,
    }
"""
'''


def _get_displays_example_template() -> str:
    """Get the template for displays/example.py."""
    return '''"""Example displays - copy this file for your tables.

Display functions customize how field values appear in the admin detail view.
They receive:
- value: The field value to render
- record: The full record dict (for context-aware rendering)

They return an HTML string.

Usage:
1. Copy this file to displays/your_table.py
2. Create display functions
3. Export them in the DISPLAYS dict
4. The admin UI will auto-discover them
"""
import html
import json
from typing import Any


def render_tags(value: Any, record: dict) -> str:
    """Render a JSON array of tags as styled badges."""
    if not value:
        return '<span class="null">—</span>'

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return html.escape(value)

    if not isinstance(value, list):
        return html.escape(str(value))

    badges = []
    for tag in value:
        escaped = html.escape(str(tag))
        badges.append(f'<span style="display:inline-block;padding:2px 8px;margin:2px;background:#e5e7eb;border-radius:4px;font-size:0.875rem;">{escaped}</span>')
    return "".join(badges)


def render_status(value: Any, record: dict) -> str:
    """Render a status field with color coding."""
    if value is None:
        return '<span class="null">—</span>'

    status = str(value).lower()
    colors = {
        "active": "#16a34a",
        "pending": "#ca8a04",
        "inactive": "#9ca3af",
        "error": "#dc2626",
        "draft": "#6b7280",
        "published": "#2563eb",
    }
    color = colors.get(status, "#374151")
    escaped = html.escape(str(value))
    return f'<span style="color:{color};font-weight:500;">{escaped}</span>'


def render_url(value: Any, record: dict) -> str:
    """Render a URL as a clickable link."""
    if not value:
        return '<span class="null">—</span>'

    escaped = html.escape(str(value))
    return f'<a href="{escaped}" target="_blank" rel="noopener">{escaped}</a>'


def render_email(value: Any, record: dict) -> str:
    """Render an email as a mailto link."""
    if not value:
        return '<span class="null">—</span>'

    escaped = html.escape(str(value))
    return f'<a href="mailto:{escaped}">{escaped}</a>'


# Register displays for this table
# Uncomment and modify as needed:
DISPLAYS = {
    # "tags": render_tags,
    # "status": render_status,
    # "website": render_url,
    # "email": render_email,
}
'''
