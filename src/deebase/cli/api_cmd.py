"""CLI commands for FastAPI integration.

Commands:
    deebase api init    - Initialize API with dependency installation
    deebase api serve   - Start development server
    deebase api generate - Generate router code from models
"""

import os
import sys
import subprocess
from pathlib import Path

import click

from .utils import run_async
from .state import load_config, load_env, find_project_root


def ensure_initialized():
    """Check that we're in an initialized DeeBase project."""
    root = find_project_root()
    if root is None:
        click.echo("Error: No DeeBase project found. Run 'deebase init' first.")
        sys.exit(1)


@click.group()
def api():
    """FastAPI integration commands."""
    pass


@api.command("init")
@click.option("--skip-deps", is_flag=True, help="Skip installing dependencies")
def api_init(skip_deps: bool):
    """Initialize API with structure and dependencies.

    Creates the api/ directory structure and installs required dependencies
    (fastapi, pydantic, fastcore, uvicorn, jinja2).
    """
    ensure_initialized()
    config = load_config()

    # Create api directory structure
    api_dir = Path("api")
    api_dir.mkdir(exist_ok=True)

    # Create __init__.py
    init_file = api_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""API module for FastAPI endpoints."""\n')
        click.echo(f"  Created: {init_file}")

    # Create app.py
    app_file = api_dir / "app.py"
    if not app_file.exists():
        app_content = '''"""FastAPI application entry point."""

import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .dependencies import get_db, init_db
from .routers import register_routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    db = get_db()

    # Register CRUD routers (must be after init_db so db is available)
    register_routers(app)

    # Register admin interface if enabled
    if os.environ.get("DEEBASE_ADMIN_ENABLED") == "1" and db:
        try:
            from deebase.admin import create_admin_router
            # Reflect tables for admin
            await db.reflect()
            app.include_router(create_admin_router(db))
        except ImportError:
            print("Warning: deebase.admin not available. Install with: pip install deebase[api]")

    yield

    # Shutdown
    if db:
        await db.close()


app = FastAPI(
    title="DeeBase API",
    description="Auto-generated REST API",
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
'''
        app_file.write_text(app_content)
        click.echo(f"  Created: {app_file}")

    # Create dependencies.py
    deps_file = api_dir / "dependencies.py"
    if not deps_file.exists():
        deps_content = '''"""Database dependencies for FastAPI."""

import os
from deebase import Database

# Global database instance
_db: Database | None = None


def get_db() -> Database | None:
    """Get the database instance."""
    return _db


async def init_db():
    """Initialize the database connection."""
    global _db

    # Load database URL from environment or config
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Default to SQLite
        db_url = "sqlite+aiosqlite:///data/app.db"

    _db = Database(db_url)
    await _db.enable_foreign_keys()
'''
        deps_file.write_text(deps_content)
        click.echo(f"  Created: {deps_file}")

    # Create routers/ directory with __init__.py
    routers_dir = api_dir / "routers"
    routers_dir.mkdir(exist_ok=True)
    routers_init = routers_dir / "__init__.py"
    if not routers_init.exists():
        routers_content = '''"""Router registration for FastAPI app."""

from fastapi import FastAPI

from ..dependencies import get_db


def register_routers(app: FastAPI):
    """Register all CRUD routers.

    Add your routers here. Example:

        from deebase.api import create_crud_router
        from models.tables import User, Post

        db = get_db()
        if db:
            app.include_router(create_crud_router(
                db=db,
                model_cls=User,
                prefix="/api/users",
                tags=["Users"],
            ))

    Or after running 'deebase api generate':

        from .users import create_users_router
        app.include_router(create_users_router(db))
    """
    # TODO: Add your routers here
    # After running 'deebase api generate', import and register generated routers
    pass
'''
        routers_init.write_text(routers_content)
        click.echo(f"  Created: {routers_init}")

    click.echo()
    click.echo("API structure created:")
    click.echo("  api/")
    click.echo("    __init__.py")
    click.echo("    app.py              # FastAPI application")
    click.echo("    routers/__init__.py # Router registration")
    click.echo("    dependencies.py     # Database dependency")
    click.echo()

    # Install dependencies
    if not skip_deps:
        click.echo("Installing API dependencies...")
        try:
            # Try uv first
            result = subprocess.run(
                ["uv", "add", "deebase[api]"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                click.echo("  Dependencies installed via uv")
            else:
                # Fall back to pip
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "deebase[api]"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    click.echo("  Dependencies installed via pip")
                else:
                    click.echo("  Warning: Could not install dependencies automatically")
                    click.echo("  Run manually: pip install deebase[api]")
        except FileNotFoundError:
            # uv not found, try pip
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "deebase[api]"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    click.echo("  Dependencies installed via pip")
                else:
                    click.echo("  Warning: Could not install dependencies")
            except Exception as e:
                click.echo(f"  Warning: Could not install dependencies: {e}")

    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Run: deebase api generate --all  (generates and wires routers)")
    click.echo("  2. Run: deebase api serve")
    click.echo("  Or for admin-only: deebase api serve --admin")
    click.echo()


@api.command("serve")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--admin", is_flag=True, help="Enable admin interface at /admin/")
def api_serve(host: str, port: int, reload: bool, admin: bool):
    """Start the FastAPI development server.

    Runs uvicorn to serve the API at http://host:port

    Use --admin to enable the Django-like admin interface.
    """
    ensure_initialized()
    load_env()

    # Check if api/app.py exists
    app_file = Path("api/app.py")
    if not app_file.exists():
        click.echo("Error: api/app.py not found. Run 'deebase api init' first.")
        sys.exit(1)

    # Set admin environment variable if flag is set
    if admin:
        os.environ['DEEBASE_ADMIN_ENABLED'] = '1'
        click.echo("Admin interface enabled at /admin/")

    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "api.app:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")

    click.echo(f"Starting server at http://{host}:{port}")
    click.echo(f"API docs at http://{host}:{port}/docs")
    if admin:
        click.echo(f"Admin interface at http://{host}:{port}/admin/")
    click.echo()

    # Run uvicorn
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        click.echo("\nServer stopped.")
    except FileNotFoundError:
        click.echo("Error: uvicorn not found. Install with: pip install uvicorn")
        sys.exit(1)


@api.command("generate")
@click.argument("tables", nargs=-1)
@click.option("--all", "all_tables", is_flag=True, help="Generate for all tables")
@click.option("--output", "-o", default="api/routers", help="Output directory")
def api_generate(tables: tuple, all_tables: bool, output: str):
    """Generate router code from models.

    Generates FastAPI router code for the specified tables.
    Uses the models from the models directory.
    """
    ensure_initialized()
    load_env()

    if not tables and not all_tables:
        click.echo("Error: Specify table names or use --all")
        click.echo("Example: deebase api generate users posts")
        click.echo("         deebase api generate --all")
        sys.exit(1)

    run_async(_generate_routers(tables, all_tables, output))


async def _generate_routers(tables: tuple, all_tables: bool, output: str):
    """Generate router files for specified tables."""
    from deebase import Database

    config = load_config()
    db_url = config.get_database_url()

    db = Database(db_url)

    try:
        # Reflect tables
        await db.reflect()

        # Get table list
        if all_tables:
            table_list = list(db._tables.keys())
            # Filter out internal tables
            table_list = [t for t in table_list if not t.startswith("_")]
        else:
            table_list = list(tables)

        if not table_list:
            click.echo("No tables found to generate routers for.")
            return

        # Create output directory
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check for legacy api/routers.py file that conflicts with api/routers/ directory
        legacy_routers_file = output_dir.parent / "routers.py"
        if legacy_routers_file.exists() and output_dir.name == "routers":
            click.echo(f"Warning: Found legacy {legacy_routers_file}")
            click.echo("  This file conflicts with the api/routers/ directory.")
            click.echo("  Please delete it: rm api/routers.py")
            click.echo()

        # Load available models from models file
        available_models = _find_available_models(config)
        if available_models:
            click.echo(f"Found models: {', '.join(available_models.keys())}")
        else:
            click.echo("Note: No models file found. Generating placeholder routers.")
            click.echo("  Run 'deebase codegen' first, or routers will only have GET / endpoint.")
            click.echo()

        # Generate router for each table
        tables_with_models = []
        tables_without_models = []
        for table_name in table_list:
            model_info = _find_model_for_table(table_name, available_models)
            router_content = _generate_router_code(table_name, db, model_info, config)
            router_file = output_dir / f"{table_name}.py"
            router_file.write_text(router_content)

            if model_info:
                tables_with_models.append(table_name)
                click.echo(f"Generated: {router_file} (full CRUD with {model_info['class_name']})")
            else:
                tables_without_models.append(table_name)
                click.echo(f"Generated: {router_file} (placeholder - no model found)")

        # Generate/update __init__.py with imports and register_routers
        init_content = _generate_init_code(table_list)
        init_file = output_dir / "__init__.py"
        init_file.write_text(init_content)
        click.echo(f"Updated: {init_file}")

        click.echo()
        if tables_with_models:
            click.echo(f"Full CRUD routers: {len(tables_with_models)} tables")
        if tables_without_models:
            click.echo(f"Placeholder routers: {len(tables_without_models)} tables")
            click.echo("  To get full CRUD, create tables with 'deebase table create'")
        click.echo()
        click.echo("Run 'deebase api serve' to start the server.")

    finally:
        await db.close()


def _table_to_class_name(table_name: str) -> str:
    """Convert table name to class name (users -> User, user_posts -> UserPosts)."""
    # Handle common pluralization
    name = table_name
    if name.endswith('ies'):
        name = name[:-3] + 'y'  # categories -> category
    elif name.endswith('sses'):
        name = name[:-2]  # classes -> class
    elif name.endswith('xes') or name.endswith('zes') or name.endswith('shes') or name.endswith('ches'):
        name = name[:-2]  # boxes -> box, dishes -> dish
    elif name.endswith('oes'):
        name = name[:-2]  # heroes -> hero (but not ctypes -> ctyp)
    elif name.endswith('s') and not name.endswith('ss'):
        name = name[:-1]  # users -> user, ctypes -> ctype

    # Convert to title case
    return name.title().replace("_", "")


def _find_model_for_table(table_name: str, available_models: dict) -> dict | None:
    """Find a model for a table, trying multiple naming conventions.

    Tries multiple naming conventions to match table names to class names:
    - singular: users -> User
    - plural: users -> Users
    - capitalize: test_docs -> Test_docs (preserves underscores)
    - title: test_docs -> Test_Docs (capitalizes each word)
    """
    # Try singular form first (users -> User)
    singular = _table_to_class_name(table_name)
    if singular in available_models:
        return available_models[singular]

    # Try plural/original form (users -> Users)
    plural = table_name.title().replace("_", "")
    if plural in available_models:
        return available_models[plural]

    # Try capitalize (test_docs -> Test_docs) - preserves underscores
    capitalized = table_name.capitalize()
    if capitalized in available_models:
        return available_models[capitalized]

    # Try exact table name title-cased (ctypes -> Ctypes)
    exact = table_name.replace("_", " ").title().replace(" ", "")
    if exact in available_models:
        return available_models[exact]

    return None


def _find_available_models(config) -> dict:
    """Find available dataclass models from the models file.

    Returns dict mapping class name to module path info.
    """
    models_path = Path(config.models_output)
    if not models_path.exists():
        return {}

    # Parse the models file to find @dataclass classes
    content = models_path.read_text()
    models = {}

    import re
    # Find @dataclass decorated classes
    pattern = r'@dataclass\s*\nclass\s+(\w+)'
    for match in re.finditer(pattern, content):
        class_name = match.group(1)
        # Convert models/tables.py -> models.tables
        module_path = str(models_path.with_suffix('')).replace('/', '.').replace('\\', '.')
        models[class_name] = {
            'class_name': class_name,
            'module_path': module_path,
        }

    return models


def _generate_init_code(table_list: list) -> str:
    """Generate __init__.py code with imports and register_routers."""
    imports = []
    registrations = []

    for table_name in sorted(table_list):
        imports.append(f"from .{table_name} import create_{table_name}_router")
        registrations.append(f"        app.include_router(create_{table_name}_router(db))")

    imports_str = "\n".join(imports)
    registrations_str = "\n".join(registrations)

    return f'''"""Generated API routers."""

from fastapi import FastAPI

from ..dependencies import get_db

{imports_str}


def register_routers(app: FastAPI):
    """Register all CRUD routers."""
    db = get_db()
    if db:
{registrations_str}
'''


def _generate_router_code(table_name: str, db, model_info: dict | None, config) -> str:
    """Generate router code for a single table.

    If model_info is provided, generates fully-wired create_crud_router() code.
    Otherwise generates a placeholder router with just GET /.
    """
    class_name = _table_to_class_name(table_name)

    if model_info:
        # Generate fully-wired router with create_crud_router()
        module_path = model_info['module_path']
        model_class = model_info['class_name']

        return f'''"""CRUD router for {table_name} table.

Auto-generated by: deebase api generate
"""

from deebase import Database
from deebase.api import create_crud_router
from {module_path} import {model_class}


def create_{table_name}_router(db: Database):
    """Create the CRUD router for {table_name}.

    Provides full CRUD endpoints:
        GET    /api/{table_name}/       - List all records
        GET    /api/{table_name}/{{id}}   - Get record by ID
        POST   /api/{table_name}/       - Create new record
        PUT    /api/{table_name}/{{id}}   - Update record
        DELETE /api/{table_name}/{{id}}   - Delete record
    """
    return create_crud_router(
        db=db,
        model_cls={model_class},
        prefix="/api/{table_name}",
        tags=["{class_name}"],
        validate_fks=True,
    )
'''
    else:
        # Generate placeholder router (no model found)
        return f'''"""CRUD router for {table_name} table.

Auto-generated by: deebase api generate

NOTE: This is a placeholder router with only GET / endpoint.
To get full CRUD, create the table with 'deebase table create' which
generates the model, then re-run 'deebase api generate'.
"""

from fastapi import APIRouter
from deebase import Database


def create_{table_name}_router(db: Database):
    """Create a placeholder router for {table_name}.

    Only provides GET / endpoint. For full CRUD:
    1. Create table with: deebase table create {table_name} ...
    2. Re-run: deebase api generate {table_name}
    """
    router = APIRouter(prefix="/api/{table_name}", tags=["{class_name}"])

    @router.get("/")
    async def list_{table_name}():
        """List all {table_name}."""
        table = db.t.{table_name}
        return await table()

    return router
'''
