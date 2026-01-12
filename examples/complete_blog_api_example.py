"""
Complete Blog API Example: FastAPI Integration

This example demonstrates building a complete REST API blog application
using DeeBase's FastAPI integration (Phase 15).

Features demonstrated:
- CRUD router generation from dataclass models
- Pydantic model generation with field descriptions
- FK validation before insert/update
- Custom hooks (before_create, after_create, etc.)
- Route customization (exclude, overrides)
- Exception mapping to HTTP status codes
- HTML template rendering (bonus feature)

Installation:
    pip install deebase[api]
    # or: uv add deebase[api]

Run:
    uv run examples/complete_blog_api_example.py

Then open: http://localhost:8000/docs for API documentation
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

# FastAPI imports
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

# DeeBase imports
from deebase import Database, Text, ForeignKey
from deebase.api import create_crud_router, CRUDRouter, ForeignKeyValidationError


# ============================================================================
# Data Models (with docments-style inline comments for documentation)
# ============================================================================

@dataclass
class User:
    """Blog user/author."""
    id: int                      # Auto-generated user ID
    name: str                    # Display name
    email: str                   # Email address (unique)
    bio: Optional[Text] = None   # User biography
    status: str = "active"       # Account status: active, inactive, banned


@dataclass
class Category:
    """Blog category for organizing posts."""
    id: int                      # Auto-generated category ID
    name: str                    # Category name
    slug: str                    # URL-friendly slug


@dataclass
class Post:
    """Blog post with author and category relationships."""
    id: int                            # Auto-generated post ID
    author_id: ForeignKey[int, "user"] # Post author (must exist in users)
    category_id: ForeignKey[int, "category"]  # Post category
    title: str                         # Post title
    slug: str                          # URL-friendly slug
    content: Text                      # Full post content in markdown
    excerpt: Optional[str] = None      # Short excerpt for previews
    published: bool = False            # Publication status
    views: int = 0                     # View counter


@dataclass
class Comment:
    """Comment on a blog post."""
    id: int                            # Auto-generated comment ID
    post_id: ForeignKey[int, "post"]   # Parent post (must exist)
    author_name: str                   # Commenter's name
    email: str                         # Commenter's email
    content: Text                      # Comment content
    approved: bool = False             # Moderation status


# ============================================================================
# Custom Router with Hooks
# ============================================================================

class PostRouter(CRUDRouter):
    """Custom post router with audit hooks."""

    async def before_create(self, data: dict) -> dict:
        """Add creation timestamp and normalize slug."""
        # Normalize the slug
        if 'title' in data and 'slug' not in data:
            data['slug'] = data['title'].lower().replace(' ', '-')[:50]
        # Initialize views to 0 if not set
        if 'views' not in data:
            data['views'] = 0
        print(f"[Hook] before_create: Creating post '{data.get('title', 'Unknown')}'")
        return data

    async def after_create(self, record: dict) -> dict:
        """Log post creation."""
        print(f"[Hook] after_create: Post created with id={record.get('id')}")
        return record

    async def before_update(self, pk, data: dict) -> dict:
        """Log updates."""
        print(f"[Hook] before_update: Updating post {pk}")
        return data

    async def before_delete(self, pk) -> None:
        """Prevent deleting published posts."""
        table = await self._get_table()
        try:
            post = await table[pk]
            if isinstance(post, dict):
                published = post.get('published', False)
            else:
                published = getattr(post, 'published', False)

            if published:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete a published post. Unpublish it first."
                )
        except Exception as e:
            if "Cannot delete" in str(e):
                raise
            # Post doesn't exist, let the delete handler return 404
            pass
        print(f"[Hook] before_delete: Deleting post {pk}")


# ============================================================================
# Application Factory
# ============================================================================

def create_app(db: Database) -> FastAPI:
    """Create the FastAPI application with all routes."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan handler."""
        # Startup: Create tables
        await db.create(User, pk="id", if_not_exists=True)
        await db.create(Category, pk="id", if_not_exists=True)
        await db.create(Post, pk="id", if_not_exists=True)
        await db.create(Comment, pk="id", if_not_exists=True)
        await db.enable_foreign_keys()
        print("[Startup] Database tables created")
        yield
        # Shutdown
        print("[Shutdown] Closing database")

    app = FastAPI(
        title="DeeBase Blog API",
        description="""
A complete blog REST API built with DeeBase's FastAPI integration.

## Features

* **Users**: Manage blog authors
* **Categories**: Organize posts by topic
* **Posts**: Full CRUD with FK validation
* **Comments**: Nested comments with moderation

## Authentication

This demo API has no authentication. In production, add OAuth2 or JWT.
        """,
        version="1.0.0",
        lifespan=lifespan,
    )

    # ========================================================================
    # REST API Routes (auto-generated)
    # ========================================================================

    # Users - basic CRUD
    app.include_router(create_crud_router(
        db=db,
        model_cls=User,
        prefix="/api/users",
        tags=["Users"],
    ))

    # Categories - exclude delete (categories should be preserved)
    app.include_router(create_crud_router(
        db=db,
        model_cls=Category,
        prefix="/api/categories",
        tags=["Categories"],
        exclude={"delete"},  # Can't delete categories
    ))

    # Posts - custom router with hooks
    post_router = PostRouter(
        db=db,
        model_cls=Post,
        prefix="/api/posts",
        tags=["Posts"],
        validate_fks=True,  # Validate author_id and category_id exist
        validators={
            "title": lambda v: v.strip()[:200] if v else v,
            "slug": lambda v: v.lower().replace(' ', '-')[:50] if v else v,
        },
    )
    app.include_router(post_router.router)

    # Comments - with FK validation, approval workflow, and custom list handler
    # Demonstrates using 'overrides' to replace specific route handlers
    from fastapi import Query

    async def custom_comments_list(
        limit: int | None = Query(None, ge=1, le=100),
        approved_only: bool = Query(False, description="Only show approved comments")
    ):
        """Custom list handler that adds filtering for approved comments."""
        comments_table = db.t.comment
        all_comments = await comments_table(limit=limit)
        if approved_only:
            # Filter to only approved comments
            return [c for c in all_comments if (c.get("approved") if isinstance(c, dict) else c.approved)]
        return all_comments

    app.include_router(create_crud_router(
        db=db,
        model_cls=Comment,
        prefix="/api/comments",
        tags=["Comments"],
        validate_fks=True,  # Validate post_id exists
        overrides={
            "list": custom_comments_list,  # Override list to add approved_only filter
        },
    ))

    # ========================================================================
    # Custom HTML Routes (bonus feature)
    # ========================================================================

    @app.get("/", response_class=HTMLResponse, tags=["HTML"])
    async def home():
        """Blog homepage with recent posts."""
        posts_table = db.t.post
        posts = await posts_table(limit=5)

        html_posts = ""
        for p in posts:
            if isinstance(p, dict):
                title, slug = p.get('title', ''), p.get('slug', '')
            else:
                title, slug = p.title, p.slug
            html_posts += f'<li><a href="/posts/{slug}">{title}</a></li>'

        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>DeeBase Blog</title></head>
        <body>
            <h1>DeeBase Blog</h1>
            <p>A demo blog powered by DeeBase + FastAPI</p>
            <h2>Recent Posts</h2>
            <ul>{html_posts if html_posts else '<li>No posts yet</li>'}</ul>
            <p><a href="/docs">API Documentation</a></p>
        </body>
        </html>
        """

    @app.get("/posts/{slug}", response_class=HTMLResponse, tags=["HTML"])
    async def view_post(slug: str):
        """View a single blog post."""
        posts_table = db.t.post
        try:
            post = await posts_table.lookup(slug=slug)
            if isinstance(post, dict):
                title, content = post.get('title', ''), post.get('content', '')
            else:
                title, content = post.title, post.content

            return f"""
            <!DOCTYPE html>
            <html>
            <head><title>{title}</title></head>
            <body>
                <h1>{title}</h1>
                <div>{content}</div>
                <p><a href="/">Back to Home</a></p>
            </body>
            </html>
            """
        except Exception:
            return HTMLResponse(
                content="<h1>Post Not Found</h1><p><a href='/'>Go Home</a></p>",
                status_code=404
            )

    return app


# ============================================================================
# Demo: Test the API without starting a server
# ============================================================================

async def run_demo():
    """Demonstrate the API using FastAPI's TestClient."""
    print("=" * 70)
    print("Complete Blog API Example: FastAPI Integration (Phase 15)")
    print("=" * 70)
    print()

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # Create the app
    app = create_app(db)

    # Use TestClient for synchronous testing (no server needed!)
    print("Using FastAPI TestClient (no server required)")
    print("-" * 70)
    print()

    with TestClient(app) as client:
        # ====================================================================
        # 1. Create Users
        # ====================================================================
        print("1. Creating users...")

        response = client.post("/api/users/", json={
            "name": "Alice Smith",
            "email": "alice@example.com",
            "bio": "Tech writer and Python enthusiast"
        })
        assert response.status_code == 201
        alice = response.json()
        print(f"   Created: {alice['name']} (id={alice['id']})")

        response = client.post("/api/users/", json={
            "name": "Bob Jones",
            "email": "bob@example.com"
        })
        bob = response.json()
        print(f"   Created: {bob['name']} (id={bob['id']})")
        print()

        # ====================================================================
        # 2. Create Categories
        # ====================================================================
        print("2. Creating categories...")

        response = client.post("/api/categories/", json={
            "name": "Technology",
            "slug": "tech"
        })
        tech_cat = response.json()
        print(f"   Created: {tech_cat['name']} (id={tech_cat['id']})")

        response = client.post("/api/categories/", json={
            "name": "Tutorials",
            "slug": "tutorials"
        })
        tut_cat = response.json()
        print(f"   Created: {tut_cat['name']} (id={tut_cat['id']})")
        print()

        # ====================================================================
        # 3. Create Posts (with FK validation)
        # ====================================================================
        print("3. Creating posts (with FK validation)...")

        response = client.post("/api/posts/", json={
            "author_id": alice['id'],
            "category_id": tech_cat['id'],
            "title": "Getting Started with DeeBase",
            "slug": "getting-started-deebase",
            "content": "DeeBase is an async database library that makes working with databases a joy...",
            "excerpt": "Learn async database operations"
        })
        assert response.status_code == 201
        post1 = response.json()
        print(f"   Created: '{post1['title']}' (id={post1['id']})")

        response = client.post("/api/posts/", json={
            "author_id": bob['id'],
            "category_id": tut_cat['id'],
            "title": "FastAPI Integration Guide",
            "slug": "fastapi-integration",
            "content": "Learn how to build REST APIs with DeeBase and FastAPI...",
            "published": True
        })
        post2 = response.json()
        print(f"   Created: '{post2['title']}' (published={post2['published']})")
        print()

        # ====================================================================
        # 4. Test FK Validation
        # ====================================================================
        print("4. Testing FK validation...")

        response = client.post("/api/posts/", json={
            "author_id": 999,  # Non-existent user!
            "category_id": tech_cat['id'],
            "title": "Invalid Post",
            "slug": "invalid",
            "content": "This should fail"
        })
        assert response.status_code == 422
        error = response.json()
        detail = error['detail']
        # Detail can be a dict (from ForeignKeyValidationError) or a string
        if isinstance(detail, dict):
            print(f"   FK validation error: {detail['type']}")
            print(f"   Field: {detail['errors'][0]['field']}")
            print(f"   Message: {detail['errors'][0]['message']}")
        else:
            print(f"   FK validation error: {detail}")
        print()

        # ====================================================================
        # 5. Create Comments (with FK validation)
        # ====================================================================
        print("5. Creating comments...")

        response = client.post("/api/comments/", json={
            "post_id": post1['id'],
            "author_name": "Reader One",
            "email": "reader1@example.com",
            "content": "Great article, very helpful!"
        })
        comment1 = response.json()
        print(f"   Created comment (id={comment1['id']}, approved={comment1['approved']})")

        # Try commenting on non-existent post
        response = client.post("/api/comments/", json={
            "post_id": 999,
            "author_name": "Spammer",
            "email": "spam@example.com",
            "content": "This should fail"
        })
        assert response.status_code == 422
        print(f"   FK validation blocked comment on non-existent post")
        print()

        # ====================================================================
        # 6. List and Get Operations
        # ====================================================================
        print("6. List and get operations...")

        # List all posts
        response = client.get("/api/posts/")
        posts = response.json()
        print(f"   GET /api/posts/ -> {len(posts)} posts")

        # Get specific post
        response = client.get(f"/api/posts/{post1['id']}")
        post = response.json()
        print(f"   GET /api/posts/{post1['id']} -> '{post['title']}'")

        # Get non-existent post
        response = client.get("/api/posts/9999")
        assert response.status_code == 404
        print(f"   GET /api/posts/9999 -> 404 Not Found")
        print()

        # ====================================================================
        # 7. Update Operations
        # ====================================================================
        print("7. Update operations (partial update)...")

        response = client.patch(f"/api/posts/{post1['id']}", json={
            "published": True,
            "views": 100
        })
        updated = response.json()
        print(f"   PATCH /api/posts/{post1['id']}")
        print(f"   Updated: published={updated['published']}, views={updated['views']}")
        print()

        # ====================================================================
        # 8. Custom Hook: Delete Protection
        # ====================================================================
        print("8. Custom hook: delete protection for published posts...")

        # Try to delete published post
        response = client.delete(f"/api/posts/{post1['id']}")
        assert response.status_code == 400
        print(f"   DELETE /api/posts/{post1['id']} -> 400 (post is published)")
        print(f"   Error: {response.json()['detail']}")

        # Unpublish first, then delete comment (FK constraint), then delete post
        client.patch(f"/api/posts/{post1['id']}", json={"published": False})
        # Delete the comment first (FK constraint prevents deleting post with comments)
        client.delete(f"/api/comments/{comment1['id']}")
        response = client.delete(f"/api/posts/{post1['id']}")
        assert response.status_code == 204
        print(f"   After unpublishing and removing comments: DELETE succeeded (204)")
        print()

        # ====================================================================
        # 9. HTML Routes
        # ====================================================================
        print("9. HTML routes...")

        response = client.get("/")
        assert response.status_code == 200
        assert "DeeBase Blog" in response.text
        print(f"   GET / -> HTML homepage")

        response = client.get("/posts/fastapi-integration")
        assert response.status_code == 200
        assert "FastAPI Integration" in response.text
        print(f"   GET /posts/fastapi-integration -> HTML post view")
        print()

        # ====================================================================
        # 10. Exception Mapping
        # ====================================================================
        print("10. Exception to HTTP status mapping...")
        print("    NotFoundError -> 404")
        print("    IntegrityError -> 422")
        print("    ValidationError -> 422")
        print("    ForeignKeyValidationError -> 422")
        print("    ConnectionError -> 503")
        print()

    # Cleanup
    await db.close()

    print("=" * 70)
    print("Demo completed successfully!")
    print()
    print("To run as a real server:")
    print("  1. Create app.py with: app = create_app(db)")
    print("  2. Run: uvicorn app:app --reload")
    print("  3. Open: http://localhost:8000/docs")
    print("=" * 70)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    asyncio.run(run_demo())
