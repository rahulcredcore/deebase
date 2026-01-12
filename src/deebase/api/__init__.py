"""DeeBase FastAPI Integration.

This module provides automatic REST API generation from DeeBase models.

Main Entry Point:
    create_crud_router() - Generate FastAPI CRUD endpoints from a dataclass model

Classes:
    CRUDRouter - Configurable router class with hooks for customization

Exceptions:
    ForeignKeyValidationError - Raised when FK validation fails

Example:
    >>> from dataclasses import dataclass
    >>> from typing import Optional
    >>> from fastapi import FastAPI
    >>> from deebase import Database, ForeignKey, Text
    >>> from deebase.api import create_crud_router
    >>>
    >>> @dataclass
    ... class User:
    ...     id: int           # Auto-generated user ID
    ...     name: str         # Display name
    ...     email: str        # Email address (unique)
    ...     status: str = "active"  # Account status
    ...
    >>> @dataclass
    ... class Post:
    ...     id: int                            # Post ID
    ...     author_id: ForeignKey[int, "user"] # Author reference
    ...     title: str                         # Post title
    ...     content: Text                      # Full content
    ...     published: bool = False            # Published status
    ...
    >>> app = FastAPI(title="Blog API")
    >>> db = Database("sqlite+aiosqlite:///blog.db")
    >>>
    >>> @app.on_event("startup")
    ... async def startup():
    ...     await db.create(User, pk='id', if_not_exists=True)
    ...     await db.create(Post, pk='id', if_not_exists=True)
    ...     await db.enable_foreign_keys()
    ...
    >>> # Add CRUD routers
    >>> app.include_router(create_crud_router(
    ...     db=db,
    ...     model_cls=User,
    ...     prefix="/api/users",
    ...     tags=["Users"],
    ... ))
    >>>
    >>> app.include_router(create_crud_router(
    ...     db=db,
    ...     model_cls=Post,
    ...     prefix="/api/posts",
    ...     tags=["Posts"],
    ...     validate_fks=True,  # Validates author_id exists before insert
    ... ))

Installation:
    pip install deebase[api]

    Or with uv:
    uv add deebase[api]

Dependencies (installed with [api] extra):
    - fastapi
    - pydantic
    - fastcore (for docments)
    - uvicorn (for development server)
    - jinja2 (for HTML templates)
"""

from .router import create_crud_router, CRUDRouter
from .exceptions import ForeignKeyValidationError
from .models import generate_pydantic_models
from .validators import validate_foreign_keys, apply_validators

__all__ = [
    # Main entry point
    "create_crud_router",
    # Router class for subclassing
    "CRUDRouter",
    # Exceptions
    "ForeignKeyValidationError",
    # Utilities
    "generate_pydantic_models",
    "validate_foreign_keys",
    "apply_validators",
]
