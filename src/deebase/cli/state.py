"""Migration state management for DeeBase CLI.

Manages:
- Project configuration (.deebase/config.toml)
- Secrets (.deebase/.env)
- Migration state (.deebase/state.json)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# Try to import toml, fall back to tomllib (Python 3.11+)
try:
    import toml
except ImportError:
    try:
        import tomllib as toml  # type: ignore
    except ImportError:
        toml = None  # type: ignore


@dataclass
class ProjectConfig:
    """Project configuration from .deebase/config.toml.

    Attributes:
        name: Project name
        version: Project version
        database_type: Database type ('sqlite' or 'postgres')
        sqlite_path: Path to SQLite database file
        models_output: Path to generated models file
        models_module: Python import path for models
        migrations_directory: Path to migrations directory
        auto_seal: Whether to seal migrations automatically
    """
    name: str = "myproject"
    version: str = "0.1.0"
    database_type: str = "sqlite"
    sqlite_path: str = "data/app.db"
    models_output: str = "models/tables.py"
    models_module: str = "models.tables"
    migrations_directory: str = "migrations"
    auto_seal: bool = False

    def get_database_url(self) -> str:
        """Get the database URL for this project.

        Returns:
            SQLAlchemy database URL
        """
        # First check for DATABASE_URL in environment
        if url := os.environ.get('DATABASE_URL'):
            return url

        if self.database_type == 'sqlite':
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        elif self.database_type == 'postgres':
            # PostgreSQL URL must come from environment
            raise ValueError(
                "PostgreSQL requires DATABASE_URL environment variable. "
                "Set it in .deebase/.env"
            )
        else:
            raise ValueError(f"Unknown database type: {self.database_type}")


@dataclass
class MigrationState:
    """Migration state from .deebase/state.json.

    Attributes:
        current_migration: Name of the current migration file (without .py)
        sealed: Whether the current migration is sealed (immutable)
        db_version: Database version number (matches migration number)
    """
    current_migration: str = "0000-initial"
    sealed: bool = False
    db_version: int = 0


def find_project_root() -> Optional[Path]:
    """Find the project root by looking for .deebase directory.

    Searches current directory and parent directories.

    Returns:
        Path to project root, or None if not found
    """
    current = Path.cwd()

    while current != current.parent:
        if (current / '.deebase').is_dir():
            return current
        current = current.parent

    # Check current directory itself
    if (Path.cwd() / '.deebase').is_dir():
        return Path.cwd()

    return None


def load_config(project_root: Optional[Path] = None) -> ProjectConfig:
    """Load project configuration from .deebase/config.toml.

    Args:
        project_root: Project root directory (auto-detected if None)

    Returns:
        ProjectConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    if project_root is None:
        project_root = find_project_root()

    if project_root is None:
        raise FileNotFoundError(
            "No DeeBase project found. Run 'deebase init' to create one."
        )

    config_path = project_root / '.deebase' / 'config.toml'

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    if toml is None:
        raise ImportError("toml package required. Install with: pip install toml")

    # Load and parse config
    with open(config_path) as f:
        if hasattr(toml, 'load'):
            data = toml.load(f)
        else:
            # tomllib requires binary mode
            f.close()
            with open(config_path, 'rb') as fb:
                data = toml.load(fb)

    # Extract sections
    project = data.get('project', {})
    database = data.get('database', {})
    models = data.get('models', {})
    migrations = data.get('migrations', {})

    return ProjectConfig(
        name=project.get('name', 'myproject'),
        version=project.get('version', '0.1.0'),
        database_type=database.get('type', 'sqlite'),
        sqlite_path=database.get('sqlite_path', 'data/app.db'),
        models_output=models.get('output', 'models/tables.py'),
        models_module=models.get('module', 'models.tables'),
        migrations_directory=migrations.get('directory', 'migrations'),
        auto_seal=migrations.get('auto_seal', False),
    )


def save_config(config: ProjectConfig, project_root: Path) -> None:
    """Save project configuration to .deebase/config.toml.

    Args:
        config: ProjectConfig instance
        project_root: Project root directory
    """
    if toml is None:
        raise ImportError("toml package required. Install with: pip install toml")

    config_path = project_root / '.deebase' / 'config.toml'

    data = {
        'project': {
            'name': config.name,
            'version': config.version,
        },
        'database': {
            'type': config.database_type,
            'sqlite_path': config.sqlite_path,
        },
        'models': {
            'output': config.models_output,
            'module': config.models_module,
        },
        'migrations': {
            'directory': config.migrations_directory,
            'auto_seal': config.auto_seal,
        },
    }

    # Only toml (not tomllib) has dumps
    if hasattr(toml, 'dumps'):
        with open(config_path, 'w') as f:
            toml.dump(data, f)
    else:
        # Manual TOML generation if tomllib (read-only)
        _write_toml_manually(config_path, data)


def _write_toml_manually(path: Path, data: dict) -> None:
    """Write TOML file manually (when toml package not available).

    Args:
        path: Path to write to
        data: Dictionary to write as TOML
    """
    lines = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            else:
                lines.append(f"{key} = {value}")
        lines.append("")

    with open(path, 'w') as f:
        f.write("\n".join(lines))


def load_state(project_root: Optional[Path] = None) -> MigrationState:
    """Load migration state from .deebase/state.json.

    Args:
        project_root: Project root directory (auto-detected if None)

    Returns:
        MigrationState instance
    """
    if project_root is None:
        project_root = find_project_root()

    if project_root is None:
        raise FileNotFoundError(
            "No DeeBase project found. Run 'deebase init' to create one."
        )

    state_path = project_root / '.deebase' / 'state.json'

    if not state_path.exists():
        # Return default state
        return MigrationState()

    with open(state_path) as f:
        data = json.load(f)

    return MigrationState(
        current_migration=data.get('current_migration', '0000-initial'),
        sealed=data.get('sealed', False),
        db_version=data.get('db_version', 0),
    )


def save_state(state: MigrationState, project_root: Path) -> None:
    """Save migration state to .deebase/state.json.

    Args:
        state: MigrationState instance
        project_root: Project root directory
    """
    state_path = project_root / '.deebase' / 'state.json'

    with open(state_path, 'w') as f:
        json.dump(asdict(state), f, indent=2)


def load_env(project_root: Optional[Path] = None) -> None:
    """Load environment variables from .deebase/.env.

    Args:
        project_root: Project root directory (auto-detected if None)
    """
    if project_root is None:
        project_root = find_project_root()

    if project_root is None:
        return

    env_path = project_root / '.deebase' / '.env'

    if not env_path.exists():
        return

    # Simple .env parser (no python-dotenv dependency)
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                os.environ[key] = value


def append_to_migration(
    code: str,
    project_root: Path,
    state: MigrationState,
) -> None:
    """Append operation code to the current unsealed migration.

    Args:
        code: Python code to append
        project_root: Project root directory
        state: Current migration state

    Raises:
        ValueError: If migration is sealed
    """
    if state.sealed:
        raise ValueError(
            f"Migration '{state.current_migration}' is sealed. "
            f"Run 'deebase migrate seal' to create a new migration."
        )

    config = load_config(project_root)
    migrations_dir = project_root / config.migrations_directory
    migration_file = migrations_dir / f"{state.current_migration}.py"

    if not migration_file.exists():
        # Create new migration file with template
        template = _get_migration_template(state.current_migration)
        migration_file.write_text(template)

    # Read existing content
    content = migration_file.read_text()

    # Find the upgrade() function and append to it
    # Look for the marker comment
    marker = "    # === Operations below this line ==="

    if marker in content:
        # Append after marker
        parts = content.split(marker)
        new_content = parts[0] + marker + "\n" + _indent(code, 4) + "\n" + parts[1]
    else:
        # Find end of upgrade function and insert before it
        # This is a simplified approach - real implementation would parse AST
        lines = content.split('\n')
        insert_idx = None
        in_upgrade = False

        for i, line in enumerate(lines):
            if 'async def upgrade(' in line:
                in_upgrade = True
            elif in_upgrade and (line.startswith('async def') or line.startswith('def')):
                insert_idx = i
                break

        if insert_idx:
            lines.insert(insert_idx, _indent(code, 4))
            new_content = '\n'.join(lines)
        else:
            # Fallback: append to end of file
            new_content = content + "\n" + _indent(code, 4) + "\n"

    migration_file.write_text(new_content)


def _get_migration_template(name: str) -> str:
    """Get the template for a new migration file.

    Args:
        name: Migration name (e.g., '0000-initial')

    Returns:
        Migration file template
    """
    description = name.split('-', 1)[1] if '-' in name else name

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


def _indent(code: str, spaces: int) -> str:
    """Indent code by the specified number of spaces.

    Args:
        code: Code to indent
        spaces: Number of spaces to indent

    Returns:
        Indented code
    """
    indent = " " * spaces
    lines = code.split('\n')
    return '\n'.join(indent + line if line.strip() else line for line in lines)
