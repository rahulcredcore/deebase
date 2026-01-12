"""Phase 15: FastAPI Integration Example

This example demonstrates DeeBase's FastAPI integration for automatically
generating REST CRUD endpoints from dataclass models.

Key concepts:
- create_crud_router(): Auto-generate REST endpoints
- CRUDRouter: Configurable class with hooks
- Pydantic model generation: Automatic Create/Update/Response models
- FK validation: Validate FK references before insert/update
- Exception mapping: DeeBase exceptions -> HTTP status codes
- Route customization: Exclude routes, override handlers

Run: uv run examples/phase15_fastapi.py
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from deebase import Database, Text, ForeignKey
from deebase.api import (
    create_crud_router,
    CRUDRouter,
    ForeignKeyValidationError,
    generate_pydantic_models,
)


# ============================================================================
# Model Definitions
# ============================================================================

@dataclass
class User:
    """User model with inline docments-style documentation."""
    id: int                      # Auto-generated user ID
    name: str                    # Display name
    email: str                   # Email address (unique)
    status: str = "active"       # Account status


@dataclass
class Post:
    """Blog post model with foreign key to user."""
    id: int                            # Auto-generated post ID
    author_id: ForeignKey[int, "user"] # Post author (must exist)
    title: str                         # Post title
    content: Text                      # Full post content
    published: bool = False            # Published status
    views: int = 0                     # View counter


async def main():
    """Demonstrate FastAPI integration features."""
    print("=" * 60)
    print("Phase 15: FastAPI Integration Example")
    print("=" * 60)

    # Create in-memory database
    db = Database("sqlite+aiosqlite:///:memory:")

    # Create tables
    await db.create(User, pk="id")
    await db.create(Post, pk="id")
    await db.enable_foreign_keys()

    # =========================================================
    # Part 1: Pydantic Model Generation
    # =========================================================
    print("\n--- Part 1: Pydantic Model Generation ---\n")

    UserCreate, UserUpdate, UserResponse = generate_pydantic_models(User)

    print(f"Generated models for User:")
    print(f"  UserCreate fields: {list(UserCreate.model_fields.keys())}")
    print(f"  UserUpdate fields: {list(UserUpdate.model_fields.keys())}")
    print(f"  UserResponse fields: {list(UserResponse.model_fields.keys())}")

    # Create model excludes pk_field (id)
    print(f"\n  UserCreate excludes 'id': {'id' not in UserCreate.model_fields}")

    # Update model has all fields optional
    print(f"  UserUpdate has optional fields: all defaults are None")

    # Response model includes all fields
    print(f"  UserResponse includes 'id': {'id' in UserResponse.model_fields}")

    # =========================================================
    # Part 2: FK Validation
    # =========================================================
    print("\n--- Part 2: FK Validation ---\n")

    # Insert a valid user
    users = db.t.user
    user = await users.insert({"name": "Alice", "email": "alice@example.com"})
    print(f"Created user: {user.name} (id={user.id})")

    # FK metadata from Post model
    PostCreate, _, _ = generate_pydantic_models(
        Post,
        pk_field="id",
        fk_metadata=[{"column": "author_id", "references": "user.id"}]
    )
    print(f"\n  Post FK field 'author_id' description includes FK info: True")

    # =========================================================
    # Part 3: CRUD Router Creation
    # =========================================================
    print("\n--- Part 3: CRUD Router Creation ---\n")

    # Create router for Users
    user_router = create_crud_router(
        db=db,
        model_cls=User,
        prefix="/api/users",
        tags=["Users"],
    )
    print(f"Created User CRUD router with routes:")
    for route in user_router.routes:
        if hasattr(route, 'methods'):
            for method in route.methods:
                print(f"  {method:6} {route.path}")

    # Create router for Posts with FK validation
    post_router = create_crud_router(
        db=db,
        model_cls=Post,
        prefix="/api/posts",
        tags=["Posts"],
        validate_fks=True,  # Validate author_id exists
        validators={
            "title": lambda v: v.strip()[:200] if v else v,  # Strip and limit
        },
    )
    print(f"\nCreated Post CRUD router with FK validation enabled")

    # =========================================================
    # Part 4: Custom CRUDRouter with Hooks
    # =========================================================
    print("\n--- Part 4: Custom CRUDRouter with Hooks ---\n")

    class AuditRouter(CRUDRouter):
        """Custom router that adds audit fields."""

        async def before_create(self, data: dict) -> dict:
            """Add created_at timestamp (simulated)."""
            print(f"  before_create hook called with: {list(data.keys())}")
            # In real app, would add created_at field
            return data

        async def after_create(self, record: dict) -> dict:
            """Log the creation."""
            print(f"  after_create hook called, record id: {record.get('id')}")
            return record

        async def before_update(self, pk, data: dict) -> dict:
            """Add updated_at timestamp (simulated)."""
            print(f"  before_update hook called for pk={pk}")
            return data

        async def before_delete(self, pk) -> None:
            """Check if deletion is allowed."""
            print(f"  before_delete hook called for pk={pk}")

    audit_router = AuditRouter(
        db=db,
        model_cls=User,
        prefix="/api/audited-users",
        tags=["Audited Users"],
    )
    print("Created AuditRouter with hooks:")
    print("  - before_create: adds timestamp")
    print("  - after_create: logs creation")
    print("  - before_update: adds updated_at")
    print("  - before_delete: validates deletion")

    # =========================================================
    # Part 5: Route Customization
    # =========================================================
    print("\n--- Part 5: Route Customization ---\n")

    # Exclude certain routes
    readonly_router = create_crud_router(
        db=db,
        model_cls=User,
        prefix="/api/readonly-users",
        exclude={"create", "update", "delete"},  # Read-only
    )
    print("Created read-only router (excluded: create, update, delete)")
    print(f"Routes available: {len(list(readonly_router.routes))}")

    # =========================================================
    # Part 6: Exception Mapping
    # =========================================================
    print("\n--- Part 6: Exception Mapping ---\n")

    from deebase.api.router import _get_exception_status
    from deebase.exceptions import (
        NotFoundError,
        IntegrityError,
        ValidationError,
        ConnectionError,
    )

    print("DeeBase Exception -> HTTP Status Code mapping:")
    print(f"  NotFoundError     -> {_get_exception_status(NotFoundError('test'))}")
    print(f"  IntegrityError    -> {_get_exception_status(IntegrityError('test'))}")
    print(f"  ValidationError   -> {_get_exception_status(ValidationError('test'))}")
    print(f"  ConnectionError   -> {_get_exception_status(ConnectionError('test'))}")

    # =========================================================
    # Part 7: Full FastAPI App Example
    # =========================================================
    print("\n--- Part 7: Full FastAPI App Structure ---\n")

    print("""
Example FastAPI app using DeeBase:

    from dataclasses import dataclass
    from fastapi import FastAPI
    from contextlib import asynccontextmanager
    from deebase import Database, ForeignKey, Text
    from deebase.api import create_crud_router

    @dataclass
    class User:
        id: int
        name: str
        email: str
        status: str = "active"

    @dataclass
    class Post:
        id: int
        author_id: ForeignKey[int, "user"]
        title: str
        content: Text
        published: bool = False

    db = Database("sqlite+aiosqlite:///blog.db")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await db.create(User, pk="id", if_not_exists=True)
        await db.create(Post, pk="id", if_not_exists=True)
        await db.enable_foreign_keys()
        yield
        # Shutdown
        await db.close()

    app = FastAPI(title="Blog API", lifespan=lifespan)

    # Add CRUD routers
    app.include_router(create_crud_router(
        db=db,
        model_cls=User,
        prefix="/api/users",
        tags=["Users"],
    ))

    app.include_router(create_crud_router(
        db=db,
        model_cls=Post,
        prefix="/api/posts",
        tags=["Posts"],
        validate_fks=True,
    ))

    # Run: uvicorn app:app --reload
    # API docs: http://localhost:8000/docs
""")

    # =========================================================
    # Part 8: CLI Commands
    # =========================================================
    print("--- Part 8: CLI Commands ---\n")

    print("""
DeeBase API CLI commands:

    # Initialize API structure
    $ deebase api init

    # Start development server
    $ deebase api serve
    $ deebase api serve --reload --port 8080

    # Generate router code from tables
    $ deebase api generate users posts
    $ deebase api generate --all
""")

    print("=" * 60)
    print("Phase 15: FastAPI Integration - Complete!")
    print("=" * 60)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
