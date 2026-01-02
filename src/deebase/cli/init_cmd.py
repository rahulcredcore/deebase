"""Initialize command for DeeBase CLI.

Creates project structure:
    .deebase/
        config.toml     - Project settings
        .env            - Database credentials (gitignored)
        state.json      - Migration state
    data/               - SQLite database files
    migrations/         - Migration files
    models/             - Generated model files
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
