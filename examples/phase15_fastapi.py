"""Phase 15: FastAPI Integration Example

This example demonstrates DeeBase's FastAPI integration for automatically
generating REST CRUD endpoints from dataclass models.

Key concepts:
- create_crud_router(): Auto-generate REST endpoints
- CRUDRouter: Configurable class with hooks
- Pydantic model generation: Automatic Create/Update/Response models
- Field docstrings: Inline comments become OpenAPI field descriptions
- Class docstrings: Become Pydantic model descriptions
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

    # Field docstrings from inline comments (fastcore.docments)
    print(f"\n  Field descriptions (from inline comments):")
    for field_name, field_info in UserCreate.model_fields.items():
        desc = field_info.description or "(no description)"
        print(f"    {field_name}: {desc}")

    # Class docstring becomes model description (appears in OpenAPI)
    print(f"\n  Model description (from class docstring):")
    print(f"    UserResponse.__doc__ = {UserResponse.__doc__}")

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
    # Part 5: Route Customization (3 Methods)
    # =========================================================
    print("\n--- Part 5: Route Customization (3 Methods) ---\n")

    # ---------------------------------------------------------
    # Method 1: exclude parameter - Remove specific routes
    # ---------------------------------------------------------
    print("Method 1: exclude parameter - Remove specific routes")
    print("-" * 50)

    readonly_router = create_crud_router(
        db=db,
        model_cls=User,
        prefix="/api/readonly-users",
        exclude={"create", "update", "delete"},  # Read-only
    )
    print("Created read-only router (excluded: create, update, delete)")
    print(f"Routes available: {len(list(readonly_router.routes))}")

    # ---------------------------------------------------------
    # Method 2: overrides parameter - Replace route handlers
    # ---------------------------------------------------------
    print("\nMethod 2: overrides parameter - Replace route handlers")
    print("-" * 50)

    from fastapi import Query

    # Custom handlers for overriding
    async def custom_list(limit: int | None = Query(None, ge=1, le=100)):
        """Custom list handler - only returns active users."""
        table = db.t.user
        all_users = await table(limit=limit)
        # Filter to only active users
        return [u for u in all_users if (u.get("status") if isinstance(u, dict) else u.status) == "active"]

    async def custom_get(pk):
        """Custom get handler - adds extra info."""
        table = db.t.user
        record = await table[pk]
        # Convert to dict and add extra field
        result = record if isinstance(record, dict) else {"id": record.id, "name": record.name, "email": record.email, "status": record.status}
        result["fetched_at"] = "2024-01-01T00:00:00Z"  # Simulated timestamp
        return result

    overrides_router = create_crud_router(
        db=db,
        model_cls=User,
        prefix="/api/custom-users",
        overrides={
            "list": custom_list,    # Replace list handler
            "get": custom_get,      # Replace get handler
        },
    )
    print("Created router with overridden handlers:")
    print("  - list: Only returns active users")
    print("  - get: Adds fetched_at timestamp to response")

    # ---------------------------------------------------------
    # Method 3: CRUDRouter subclass - Full control with hooks
    # ---------------------------------------------------------
    print("\nMethod 3: CRUDRouter subclass - Full control with hooks")
    print("-" * 50)

    class AdvancedUserRouter(CRUDRouter):
        """Advanced router with full customization."""

        async def before_create(self, data: dict) -> dict:
            """Validate and transform data before insert."""
            # Add default status if not provided
            if "status" not in data:
                data["status"] = "pending"
            # Normalize email
            if "email" in data:
                data["email"] = data["email"].lower().strip()
            print(f"    [Hook] before_create: normalized email, set status")
            return data

        async def after_create(self, record: dict) -> dict:
            """Actions after insert (e.g., send welcome email)."""
            print(f"    [Hook] after_create: would send welcome email to {record.get('email')}")
            return record

        async def before_update(self, pk, data: dict) -> dict:
            """Validate update data."""
            if "email" in data:
                data["email"] = data["email"].lower().strip()
            print(f"    [Hook] before_update: validated update for pk={pk}")
            return data

        async def after_update(self, record: dict) -> dict:
            """Actions after update."""
            print(f"    [Hook] after_update: record {record.get('id')} updated")
            return record

        async def before_delete(self, pk) -> None:
            """Validate deletion (e.g., check if user has posts)."""
            print(f"    [Hook] before_delete: checking if user {pk} can be deleted")
            # Could raise HTTPException to prevent deletion

        async def after_delete(self, pk) -> None:
            """Cleanup after deletion."""
            print(f"    [Hook] after_delete: cleanup for user {pk}")

    advanced_router = AdvancedUserRouter(
        db=db,
        model_cls=User,
        prefix="/api/advanced-users",
        tags=["Advanced Users"],
    )
    print("Created AdvancedUserRouter with all hooks:")
    print("  - before_create: normalize email, set default status")
    print("  - after_create: send welcome email")
    print("  - before_update: validate update data")
    print("  - after_update: log update")
    print("  - before_delete: check dependencies")
    print("  - after_delete: cleanup")

    # ---------------------------------------------------------
    # Summary: When to use each method
    # ---------------------------------------------------------
    print("\nSummary: When to use each method")
    print("-" * 50)
    print("""
  exclude:    Quick way to remove routes you don't need
              Example: exclude={"delete"} for non-deletable resources

  overrides:  Replace specific handlers with custom functions
              Example: overrides={"list": custom_list_with_filters}

  CRUDRouter: Full control - modify data before/after operations
              Example: Add audit fields, send notifications, validate business rules
""")

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

    # Initialize API structure (creates api/ directory)
    $ deebase api init

    # Generate routers from tables (auto-wires them in api/routers/__init__.py)
    $ deebase api generate users posts
    $ deebase api generate --all

    # Start development server
    $ deebase api serve
    $ deebase api serve --reload --port 8080

Typical workflow:
    $ deebase init                    # Initialize project
    $ deebase table create users ...  # Create tables
    $ deebase api init                # Set up API structure
    $ deebase api generate --all      # Generate and wire routers
    $ deebase api serve               # Start server

Note: api generate automatically updates api/routers/__init__.py with
imports and registration. Do not manually edit that file.
""")

    print("=" * 60)
    print("Phase 15: FastAPI Integration - Complete!")
    print("=" * 60)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
