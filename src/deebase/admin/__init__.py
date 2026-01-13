"""DeeBase Admin Interface.

A Django-like admin interface for managing database records through a web UI.

This module provides a simple, auto-generated admin interface that:
- Lists all tables in the database
- Provides list/view/create/edit/delete views for each table
- Supports FK dropdown fields populated from parent tables
- Uses the same validation layer as CLI and API
- Supports custom field renderers via displays/ directory

URL Structure (Phase 17):
    /admin/                         - Dashboard
    /admin/{table}/                 - List records (clickable rows)
    /admin/{table}/new              - Create form
    /admin/{table}/{pk}             - Read-only detail view
    /admin/{table}/{pk}/edit        - Edit form
    /admin/{table}/{pk}/delete      - Delete confirmation

Usage:
    from deebase import Database
    from deebase.admin import create_admin_router

    db = Database("sqlite+aiosqlite:///app.db")

    # Add to FastAPI app
    app.include_router(create_admin_router(db))

Or enable via CLI:
    deebase api serve --admin

Custom Field Renderers:
    Create displays/{table_name}.py with a DISPLAYS dict:

        # displays/articles.py
        def render_tags(value, record):
            return "<span class='tag'>" + value + "</span>"

        DISPLAYS = {"tags": render_tags}
"""

from .router import create_admin_router
from .renderers import render_field, clear_display_cache

__all__ = ["create_admin_router", "render_field", "clear_display_cache"]
