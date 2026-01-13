"""Tests for deebase.admin module - Admin UI (Phase 17)."""

import pytest
import pytest_asyncio
from dataclasses import dataclass
from typing import Optional

from deebase import Database, ForeignKey, Text


# Test Models
@dataclass
class Article:
    id: int
    title: str
    content: Text
    metadata: dict  # JSON field
    views: int = 0
    published: bool = False


@dataclass
class Author:
    id: int
    name: str
    email: str


@dataclass
class Post:
    id: int
    author_id: ForeignKey[int, "author"]
    title: str


# ============================================================================
# Renderers Tests
# ============================================================================

class TestRenderers:
    """Tests for deebase.admin.renderers module."""

    def test_render_json_with_dict(self):
        """Should render dict as formatted JSON."""
        from deebase.admin.renderers import render_json

        result = render_json({"key": "value", "nested": {"a": 1}}, {}, "JSON")
        assert "<pre" in result
        assert "key" in result
        assert "value" in result

    def test_render_json_with_none(self):
        """Should render null marker for None."""
        from deebase.admin.renderers import render_json

        result = render_json(None, {}, "JSON")
        assert "null" in result.lower() or "—" in result

    def test_render_json_escapes_html(self):
        """Should escape HTML in JSON values."""
        from deebase.admin.renderers import render_json

        result = render_json({"script": "<script>alert(1)</script>"}, {}, "JSON")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_render_text_preserves_newlines(self):
        """Should convert newlines to <br> tags."""
        from deebase.admin.renderers import render_text

        result = render_text("line1\nline2\nline3", {}, "TEXT")
        assert "<br>" in result
        assert "line1" in result
        assert "line3" in result

    def test_render_text_with_none(self):
        """Should render null marker for None."""
        from deebase.admin.renderers import render_text

        result = render_text(None, {}, "TEXT")
        assert "null" in result.lower() or "—" in result

    def test_render_text_escapes_html(self):
        """Should escape HTML in text values."""
        from deebase.admin.renderers import render_text

        result = render_text("<b>bold</b>", {}, "TEXT")
        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_render_boolean_true(self):
        """Should render True as 'Yes'."""
        from deebase.admin.renderers import render_boolean

        result = render_boolean(True, {}, "BOOLEAN")
        assert "Yes" in result
        assert "bool-true" in result

    def test_render_boolean_false(self):
        """Should render False as 'No'."""
        from deebase.admin.renderers import render_boolean

        result = render_boolean(False, {}, "BOOLEAN")
        # Note: "No" might be in class name "bool-false", so check for it
        assert "bool-false" in result or "No" in result

    def test_render_boolean_with_integer(self):
        """Should handle 1/0 as boolean."""
        from deebase.admin.renderers import render_boolean

        assert "Yes" in render_boolean(1, {}, "BOOLEAN")

    def test_render_default_with_none(self):
        """Should render null marker for None."""
        from deebase.admin.renderers import render_default

        result = render_default(None, {}, "VARCHAR")
        assert "null" in result.lower() or "—" in result

    def test_render_default_escapes_html(self):
        """Should escape HTML in default rendering."""
        from deebase.admin.renderers import render_default

        result = render_default("<script>", {}, "VARCHAR")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_get_renderer_for_json(self):
        """Should return JSON renderer for JSON type."""
        from deebase.admin.renderers import get_renderer, render_json

        renderer = get_renderer("JSON")
        assert renderer == render_json

    def test_get_renderer_for_text(self):
        """Should return TEXT renderer for TEXT type."""
        from deebase.admin.renderers import get_renderer, render_text

        renderer = get_renderer("TEXT")
        assert renderer == render_text

    def test_get_renderer_for_boolean(self):
        """Should return boolean renderer for BOOLEAN type."""
        from deebase.admin.renderers import get_renderer, render_boolean

        renderer = get_renderer("BOOLEAN")
        assert renderer == render_boolean

    def test_get_renderer_for_unknown(self):
        """Should return default renderer for unknown type."""
        from deebase.admin.renderers import get_renderer, render_default

        renderer = get_renderer("UNKNOWN_TYPE")
        assert renderer == render_default

    def test_get_renderer_case_insensitive(self):
        """Should match types case-insensitively."""
        from deebase.admin.renderers import get_renderer, render_json

        # Should find JSON even in mixed case
        assert get_renderer("json") == render_json
        assert get_renderer("Json") == render_json

    def test_render_field_uses_type_renderer(self):
        """render_field should use appropriate type renderer."""
        from deebase.admin.renderers import render_field

        result = render_field("articles", "metadata", "JSON", {"key": "value"}, {})
        assert "<pre" in result
        assert "key" in result

    def test_render_field_handles_none(self):
        """render_field should handle None values."""
        from deebase.admin.renderers import render_field

        result = render_field("articles", "content", "TEXT", None, {})
        assert "null" in result.lower() or "—" in result


# ============================================================================
# Admin Router Tests
# ============================================================================

class TestAdminRouter:
    """Tests for admin router routes."""

    @pytest_asyncio.fixture
    async def db_with_data(self, db):
        """Database with tables and sample data."""
        await db.create(Author, pk="id")
        await db.create(Article, pk="id")

        authors = db.t.author
        await authors.insert({"name": "Alice", "email": "alice@example.com"})

        articles = db.t.article
        await articles.insert({
            "title": "Test Article",
            "content": "This is the content",
            "metadata": {"tags": ["test", "example"]},
            "views": 100,
            "published": True,
        })

        return db

    @pytest.mark.asyncio
    async def test_admin_dashboard(self, db_with_data):
        """GET /admin/ should show dashboard."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/")
            assert response.status_code == 200
            assert "author" in response.text or "article" in response.text

    @pytest.mark.asyncio
    async def test_admin_list_view(self, db_with_data):
        """GET /admin/{table}/ should list records."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/")
            assert response.status_code == 200
            assert "Test Article" in response.text
            # Should have clickable row
            assert "clickable-row" in response.text

    @pytest.mark.asyncio
    async def test_admin_view_route(self, db_with_data):
        """GET /admin/{table}/{pk} should show read-only detail view."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/1")
            assert response.status_code == 200
            # Should show view page (not edit form)
            assert "Test Article" in response.text
            # Should have Edit button
            assert "/admin/article/1/edit" in response.text
            # Should have Delete button
            assert "/admin/article/1/delete" in response.text

    @pytest.mark.asyncio
    async def test_admin_view_renders_json(self, db_with_data):
        """View page should render JSON fields properly."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/1")
            assert response.status_code == 200
            # JSON should be rendered with pre tag
            assert "<pre" in response.text or "tags" in response.text

    @pytest.mark.asyncio
    async def test_admin_edit_form_route(self, db_with_data):
        """GET /admin/{table}/{pk}/edit should show edit form."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/1/edit")
            assert response.status_code == 200
            # Should show edit form
            assert "<form" in response.text
            assert "Test Article" in response.text
            # Form should post to /edit
            assert 'action="/admin/article/1/edit"' in response.text

    @pytest.mark.asyncio
    async def test_admin_update_submit(self, db_with_data):
        """POST /admin/{table}/{pk}/edit should update record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.post(
                "/admin/article/1/edit",
                data={"title": "Updated Title", "content": "Updated content"},
                follow_redirects=False
            )
            # Should redirect to view page
            assert response.status_code == 303
            assert response.headers["location"] == "/admin/article/1"

            # Verify update
            response = client.get("/admin/article/1")
            assert "Updated Title" in response.text

    @pytest.mark.asyncio
    async def test_admin_create_redirects_to_view(self, db_with_data):
        """POST /admin/{table}/new should redirect to view page."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.post(
                "/admin/author/new",
                data={"name": "Bob", "email": "bob@example.com"},
                follow_redirects=False
            )
            # Should redirect to view page (/{pk})
            assert response.status_code == 303
            # Location should be /admin/author/{pk}
            assert "/admin/author/" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_admin_delete_route(self, db_with_data):
        """GET /admin/{table}/{pk}/delete should show confirmation."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/1/delete")
            assert response.status_code == 200
            assert "delete" in response.text.lower()

    @pytest.mark.asyncio
    async def test_admin_view_not_found(self, db_with_data):
        """GET /admin/{table}/{pk} should return 404 for missing record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/999")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_edit_not_found(self, db_with_data):
        """GET /admin/{table}/{pk}/edit should return 404 for missing record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/999/edit")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_has_view_edit_delete_links(self, db_with_data):
        """List page should have View, Edit, Delete links."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from deebase.admin import create_admin_router

        app = FastAPI()
        app.include_router(create_admin_router(db_with_data))

        with TestClient(app) as client:
            response = client.get("/admin/article/")
            assert response.status_code == 200
            # Should have all action links
            assert "/admin/article/1" in response.text  # View link
            assert "/admin/article/1/edit" in response.text  # Edit link
            assert "/admin/article/1/delete" in response.text  # Delete link


# ============================================================================
# Display Module Cache Tests
# ============================================================================

class TestDisplayCache:
    """Tests for display module caching."""

    def test_clear_display_cache(self):
        """clear_display_cache should clear the cache."""
        from deebase.admin.renderers import clear_display_cache, _display_cache

        # Set some cache value
        _display_cache["test"] = {"field": lambda v, r: str(v)}

        clear_display_cache()

        assert len(_display_cache) == 0

    def test_custom_display_not_found(self):
        """Should return None when display module doesn't exist."""
        from deebase.admin.renderers import _load_custom_display, clear_display_cache

        clear_display_cache()
        result = _load_custom_display("nonexistent_table", "field")
        assert result is None
