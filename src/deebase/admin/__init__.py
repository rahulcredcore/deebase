"""DeeBase Admin Interface.

A Django-like admin interface for managing database records through a web UI.

This module provides a simple, auto-generated admin interface that:
- Lists all tables in the database
- Provides list/create/edit/delete views for each table
- Supports FK dropdown fields populated from parent tables
- Uses the same validation layer as CLI and API

Usage:
    from deebase import Database
    from deebase.admin import create_admin_router

    db = Database("sqlite+aiosqlite:///app.db")

    # Add to FastAPI app
    app.include_router(create_admin_router(db))

Or enable via CLI:
    deebase api serve --admin
"""

from .router import create_admin_router

__all__ = ["create_admin_router"]
