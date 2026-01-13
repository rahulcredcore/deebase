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

# Register CRUD routers
register_routers(app)


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

    # Create routers.py
    routers_file = api_dir / "routers.py"
    if not routers_file.exists():
        routers_content = '''"""Router registration for FastAPI app."""

from fastapi import FastAPI

from .dependencies import get_db


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
    """
    # TODO: Add your routers here
    pass
'''
        routers_file.write_text(routers_content)
        click.echo(f"  Created: {routers_file}")

    click.echo()
    click.echo("API structure created:")
    click.echo("  api/")
    click.echo("    __init__.py")
    click.echo("    app.py           # FastAPI application")
    click.echo("    routers.py       # Router registration")
    click.echo("    dependencies.py  # Database dependency")
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
    click.echo("  1. Edit api/routers.py to add your CRUD routers")
    click.echo("  2. Run: deebase api serve")
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

        # Create __init__.py if not exists
        init_file = output_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Generated API routers."""\n')

        # Generate router for each table
        for table_name in table_list:
            router_content = _generate_router_code(table_name, db)
            router_file = output_dir / f"{table_name}.py"
            router_file.write_text(router_content)
            click.echo(f"Generated: {router_file}")

    finally:
        await db.close()


def _generate_router_code(table_name: str, db) -> str:
    """Generate router code for a single table."""
    class_name = table_name.title().replace("_", "")

    return f'''"""CRUD router for {table_name} table.

Auto-generated by: deebase api generate
"""

from fastapi import APIRouter, Depends
from deebase import Database
from deebase.api import create_crud_router

# Import your model - adjust path as needed
# from models.tables import {class_name}


def create_{table_name}_router(db: Database) -> APIRouter:
    """Create the CRUD router for {table_name}.

    Args:
        db: Database instance

    Returns:
        FastAPI APIRouter with CRUD endpoints

    Example usage in api/routers.py:
        from .routers.{table_name} import create_{table_name}_router

        def register_routers(app: FastAPI):
            db = get_db()
            if db:
                app.include_router(create_{table_name}_router(db))
    """
    # TODO: Import your {class_name} model and uncomment below
    # return create_crud_router(
    #     db=db,
    #     model_cls={class_name},
    #     prefix="/api/{table_name}",
    #     tags=["{class_name}"],
    #     validate_fks=True,
    # )

    # Placeholder router until model is imported
    router = APIRouter(prefix="/api/{table_name}", tags=["{class_name}"])

    @router.get("/")
    async def list_{table_name}():
        """List all {table_name}."""
        table = db.t.{table_name}
        return await table()

    return router
'''
