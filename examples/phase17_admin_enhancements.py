"""Phase 17: Admin UI Enhancements

This example demonstrates the Phase 17 admin interface improvements:
- Read-only detail view at /{table}/{pk}
- Edit form moved to /{table}/{pk}/edit
- Clickable rows in list view
- Type-based field renderers
- Custom display functions via displays/ directory

Run this example:
    uv run examples/phase17_admin_enhancements.py

Then visit: http://localhost:8000/admin/
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from deebase import Database, Text
from deebase.admin import create_admin_router, render_field


# ============================================================================
# Sample Models
# ============================================================================

@dataclass
class Article:
    """Blog article with various field types to demonstrate rendering."""
    id: int
    title: str
    content: Text        # Long text - rendered with line breaks
    metadata: dict       # JSON - rendered as formatted pre block
    status: str = "draft"
    views: int = 0
    published: bool = False


@dataclass
class Author:
    """Article author."""
    id: int
    name: str
    email: str
    bio: Optional[Text] = None


# ============================================================================
# Demonstrate Field Renderers
# ============================================================================

def demo_renderers():
    """Show how field renderers work."""
    print("=" * 60)
    print("Field Renderers Demo")
    print("=" * 60)
    print()

    # JSON rendering
    json_value = {"tags": ["python", "database"], "author": "Alice"}
    print("JSON field rendering:")
    print(render_field("article", "metadata", "JSON", json_value, {}))
    print()

    # TEXT rendering (newlines become <br>)
    text_value = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    print("TEXT field rendering (preserves newlines):")
    print(render_field("article", "content", "TEXT", text_value, {}))
    print()

    # Boolean rendering
    print("BOOLEAN field rendering:")
    print(f"True  -> {render_field('article', 'published', 'BOOLEAN', True, {})}")
    print(f"False -> {render_field('article', 'published', 'BOOLEAN', False, {})}")
    print()

    # NULL rendering
    print("NULL value rendering:")
    print(f"None -> {render_field('article', 'bio', 'TEXT', None, {})}")
    print()


# ============================================================================
# Main Example
# ============================================================================

async def main():
    # Demo renderers first
    demo_renderers()

    print("=" * 60)
    print("Admin UI Demo")
    print("=" * 60)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # Create tables
    await db.create(Author, pk="id")
    await db.create(Article, pk="id")

    # Insert sample data
    authors = db.t.author
    await authors.insert({
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "bio": "Tech writer and Python enthusiast.\n\nLoves databases and clean code."
    })
    await authors.insert({
        "name": "Bob Smith",
        "email": "bob@example.com",
        "bio": None
    })

    articles = db.t.article
    await articles.insert({
        "title": "Getting Started with DeeBase",
        "content": "DeeBase is an async database library.\n\nIt provides a simple, ergonomic API for SQLite and PostgreSQL.\n\nThis guide will walk you through the basics.",
        "metadata": {"tags": ["tutorial", "beginner"], "read_time": 5},
        "status": "published",
        "views": 1500,
        "published": True,
    })
    await articles.insert({
        "title": "Advanced Query Patterns",
        "content": "Learn about transactions, FK navigation, and views.\n\nThese patterns help you build robust applications.",
        "metadata": {"tags": ["advanced", "patterns"], "read_time": 10},
        "status": "draft",
        "views": 0,
        "published": False,
    })

    print("Sample data created!")
    print()

    # Show URL structure
    print("Phase 17 URL Structure:")
    print("-" * 40)
    print("  /admin/                     - Dashboard")
    print("  /admin/article/             - List articles (clickable rows)")
    print("  /admin/article/1            - View article #1 (read-only)")
    print("  /admin/article/1/edit       - Edit article #1 (form)")
    print("  /admin/article/1/delete     - Delete confirmation")
    print("  /admin/article/new          - Create new article")
    print()

    print("Key Phase 17 Changes:")
    print("-" * 40)
    print("  1. /{table}/{pk} is now a read-only detail view")
    print("  2. Edit form moved to /{table}/{pk}/edit")
    print("  3. List rows are clickable (navigate to detail)")
    print("  4. JSON fields rendered as formatted <pre> blocks")
    print("  5. TEXT fields preserve line breaks")
    print("  6. Boolean fields rendered as Yes/No with styling")
    print("  7. Custom displays via displays/{table}.py")
    print()

    # Start the server
    try:
        from fastapi import FastAPI
        import uvicorn

        app = FastAPI(title="DeeBase Admin Demo")
        app.include_router(create_admin_router(db))

        print("Starting admin server...")
        print("Visit: http://localhost:8000/admin/")
        print()
        print("Try these URLs:")
        print("  - http://localhost:8000/admin/article/        (list with clickable rows)")
        print("  - http://localhost:8000/admin/article/1       (read-only detail)")
        print("  - http://localhost:8000/admin/article/1/edit  (edit form)")
        print()
        print("Press Ctrl+C to stop.")

        uvicorn.run(app, host="127.0.0.1", port=8000)

    except ImportError:
        print("Note: Install FastAPI dependencies to run the server:")
        print("  uv add deebase[api]")
        print()
        print("Or install manually:")
        print("  pip install fastapi uvicorn jinja2 python-multipart")


if __name__ == "__main__":
    asyncio.run(main())
