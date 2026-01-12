"""CRUD Router generation for FastAPI.

This module provides automatic REST API generation from DeeBase models.
"""

from dataclasses import is_dataclass
from typing import Any, Callable, Set, Type

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from .models import generate_pydantic_models
from .validators import validate_foreign_keys, apply_validators
from .exceptions import ForeignKeyValidationError


# Exception to HTTP status code mapping
EXCEPTION_STATUS_MAP = {
    "NotFoundError": 404,
    "IntegrityError": 422,
    "ValidationError": 422,
    "ForeignKeyValidationError": 422,
    "SchemaError": 500,
    "ConnectionError": 503,
    "InvalidOperationError": 400,
}


def _get_exception_status(exc: Exception) -> int:
    """Get HTTP status code for a DeeBase exception."""
    exc_name = type(exc).__name__
    return EXCEPTION_STATUS_MAP.get(exc_name, 500)


def _handle_deebase_exception(exc: Exception) -> HTTPException:
    """Convert a DeeBase exception to an HTTPException."""
    status_code = _get_exception_status(exc)

    if isinstance(exc, ForeignKeyValidationError):
        return HTTPException(
            status_code=status_code,
            detail=exc.to_dict()
        )

    # For other exceptions, use the message
    detail = str(exc)
    if hasattr(exc, "message"):
        detail = exc.message

    return HTTPException(status_code=status_code, detail=detail)


class CRUDRouter:
    """A configurable CRUD router for DeeBase models.

    Provides hooks for customizing CRUD operations and supports
    subclassing for more advanced customization.

    Attributes:
        router: The FastAPI APIRouter instance
        db: Database instance
        model_cls: The dataclass model class
        table_name: Database table name
        pk_field: Primary key field name
        validate_fks: Whether to validate FK references
        validators: Custom field validators

    Example:
        >>> class CustomPostRouter(CRUDRouter):
        ...     async def before_create(self, data: dict) -> dict:
        ...         data["created_at"] = datetime.now().isoformat()
        ...         return data
        ...
        >>> router = CustomPostRouter(db, Post, prefix="/api/posts")
        >>> app.include_router(router.router)
    """

    def __init__(
        self,
        db: "Database",
        model_cls: type,
        *,
        table_name: str | None = None,
        prefix: str = "",
        tags: list[str] | None = None,
        pk_field: str = "id",
        validate_fks: bool = True,
        validators: dict[str, Callable[[Any], Any]] | None = None,
        exclude: Set[str] | None = None,
        overrides: dict[str, Callable] | None = None,
        response_model_exclude: Set[str] | None = None,
    ):
        """Initialize the CRUD router.

        Args:
            db: DeeBase Database instance
            model_cls: Dataclass model class
            table_name: Table name (default: model class name lowercase)
            prefix: URL prefix for routes
            tags: OpenAPI tags
            pk_field: Primary key field name
            validate_fks: Whether to validate FK references before mutations
            validators: Custom field validators {field: callable}
            exclude: Routes to exclude {"list", "get", "create", "update", "delete"}
            overrides: Route handlers to override {"create": handler, ...}
            response_model_exclude: Fields to exclude from responses
        """
        self.db = db
        self.model_cls = model_cls
        self.table_name = table_name or model_cls.__name__.lower()
        self.pk_field = pk_field
        self.validate_fks = validate_fks
        self.validators = validators or {}
        self.exclude = exclude or set()
        self.overrides = overrides or {}
        self.response_model_exclude = response_model_exclude

        # Get table (will need reflection if not in cache)
        self._table = None

        # Get FK metadata from model class annotations
        self._fk_metadata = self._extract_fk_metadata()

        # Generate Pydantic models
        self.CreateModel, self.UpdateModel, self.ResponseModel = generate_pydantic_models(
            model_cls,
            pk_field=pk_field,
            fk_metadata=self._fk_metadata,
        )

        # Create the router
        self.router = APIRouter(prefix=prefix, tags=tags or [model_cls.__name__])

        # Register routes
        self._register_routes()

    def _extract_fk_metadata(self) -> list[dict]:
        """Extract FK metadata from model class annotations."""
        from ..types import is_foreign_key, get_foreign_key_info

        fk_metadata = []

        # Get raw annotations (not resolved through get_type_hints)
        # because ForeignKey[T, "ref"] returns a _ForeignKeyType instance
        annotations = getattr(self.model_cls, "__annotations__", {})

        for field_name, field_type in annotations.items():
            # Check if this is a ForeignKey type (a _ForeignKeyType instance)
            if is_foreign_key(field_type):
                _, table, column = get_foreign_key_info(field_type)
                fk_metadata.append({
                    "column": field_name,
                    "references": f"{table}.{column}"
                })

        return fk_metadata

    async def _get_table(self):
        """Get the table, reflecting if needed."""
        if self._table is None:
            table = self.db._get_table(self.table_name)
            if table is None:
                # Try to reflect
                table = await self.db.reflect_table(self.table_name)
            self._table = table
        return self._table

    def _register_routes(self):
        """Register all CRUD routes on the router."""
        # Capture models for use in closures
        CreateModel = self.CreateModel
        UpdateModel = self.UpdateModel

        # List (GET /)
        if "list" not in self.exclude:
            handler = self.overrides.get("list", self._list_handler)
            self.router.add_api_route(
                "/",
                handler,
                methods=["GET"],
                response_model=list[self.ResponseModel],
                summary=f"List all {self.model_cls.__name__}s",
            )

        # Get (GET /{pk})
        if "get" not in self.exclude:
            handler = self.overrides.get("get", self._get_handler)
            self.router.add_api_route(
                "/{pk}",
                handler,
                methods=["GET"],
                response_model=self.ResponseModel,
                summary=f"Get a {self.model_cls.__name__} by ID",
            )

        # Create (POST /)
        if "create" not in self.exclude:
            # Create a typed handler that FastAPI can inspect
            async def create_handler(data: CreateModel) -> dict:  # type: ignore[valid-type]
                return await self._create_handler_impl(data)

            handler = self.overrides.get("create", create_handler)
            self.router.add_api_route(
                "/",
                handler,
                methods=["POST"],
                response_model=self.ResponseModel,
                status_code=201,
                summary=f"Create a {self.model_cls.__name__}",
            )

        # Update (PATCH /{pk})
        if "update" not in self.exclude:
            # Create a typed handler that FastAPI can inspect
            async def update_handler(pk: Any, data: UpdateModel) -> dict:  # type: ignore[valid-type]
                return await self._update_handler_impl(pk, data)

            handler = self.overrides.get("update", update_handler)
            self.router.add_api_route(
                "/{pk}",
                handler,
                methods=["PATCH"],
                response_model=self.ResponseModel,
                summary=f"Update a {self.model_cls.__name__}",
            )

        # Delete (DELETE /{pk})
        if "delete" not in self.exclude:
            handler = self.overrides.get("delete", self._delete_handler)
            self.router.add_api_route(
                "/{pk}",
                handler,
                methods=["DELETE"],
                status_code=204,
                response_class=Response,
                summary=f"Delete a {self.model_cls.__name__}",
            )

    # Hook methods for subclasses to override
    async def before_create(self, data: dict) -> dict:
        """Hook called before insert. Override to modify data."""
        return data

    async def after_create(self, record: dict) -> dict:
        """Hook called after insert. Override to modify response."""
        return record

    async def before_update(self, pk: Any, data: dict) -> dict:
        """Hook called before update. Override to modify data."""
        return data

    async def after_update(self, record: dict) -> dict:
        """Hook called after update. Override to modify response."""
        return record

    async def before_delete(self, pk: Any) -> None:
        """Hook called before delete. Override to add validation."""
        pass

    async def after_delete(self, pk: Any) -> None:
        """Hook called after delete. Override to add cleanup."""
        pass

    # Default route handlers
    async def _list_handler(
        self,
        limit: int | None = Query(None, ge=1, le=1000, description="Maximum number of records to return")
    ) -> list[dict]:
        """List all records."""
        try:
            table = await self._get_table()
            records = await table(limit=limit)
            # Convert to dicts if dataclass
            return [self._record_to_dict(r) for r in records]
        except Exception as e:
            raise _handle_deebase_exception(e)

    async def _get_handler(self, pk: Any) -> dict:
        """Get a single record by primary key."""
        try:
            table = await self._get_table()
            record = await table[pk]
            return self._record_to_dict(record)
        except Exception as e:
            raise _handle_deebase_exception(e)

    async def _create_handler_impl(self, data: BaseModel) -> dict:
        """Implementation for create handler."""
        try:
            table = await self._get_table()
            data_dict = data.model_dump(exclude_unset=True)

            # Apply custom validators
            data_dict = await apply_validators(data_dict, self.validators)

            # Validate FKs
            if self.validate_fks and self._fk_metadata:
                await validate_foreign_keys(self.db, table, data_dict)

            # Call before_create hook
            data_dict = await self.before_create(data_dict)

            # Insert
            record = await table.insert(data_dict)

            # Call after_create hook
            record = await self.after_create(self._record_to_dict(record))

            return record
        except HTTPException:
            # Re-raise HTTP exceptions directly (from hooks)
            raise
        except ForeignKeyValidationError as e:
            raise _handle_deebase_exception(e)
        except Exception as e:
            raise _handle_deebase_exception(e)

    async def _update_handler_impl(self, pk: Any, data: BaseModel) -> dict:
        """Implementation for update handler."""
        try:
            table = await self._get_table()

            # Get existing record first
            existing = await table[pk]
            existing_dict = self._record_to_dict(existing)

            # Get only the fields that were actually set in the request
            data_dict = data.model_dump(exclude_unset=True)

            if not data_dict:
                # No fields to update, return existing record
                return existing_dict

            # Apply custom validators
            data_dict = await apply_validators(data_dict, self.validators)

            # Validate FKs
            if self.validate_fks and self._fk_metadata:
                await validate_foreign_keys(self.db, table, data_dict)

            # Call before_update hook
            data_dict = await self.before_update(pk, data_dict)

            # Merge with existing and include pk
            update_data = {**existing_dict, **data_dict, self.pk_field: pk}

            # Update
            record = await table.update(update_data)

            # Call after_update hook
            record = await self.after_update(self._record_to_dict(record))

            return record
        except HTTPException:
            # Re-raise HTTP exceptions directly (from hooks)
            raise
        except ForeignKeyValidationError as e:
            raise _handle_deebase_exception(e)
        except Exception as e:
            raise _handle_deebase_exception(e)

    async def _delete_handler(self, pk: Any) -> None:
        """Delete a record."""
        try:
            table = await self._get_table()

            # Call before_delete hook
            await self.before_delete(pk)

            # Delete
            await table.delete(pk)

            # Call after_delete hook
            await self.after_delete(pk)

        except HTTPException:
            # Re-raise HTTP exceptions directly (from hooks)
            raise
        except Exception as e:
            raise _handle_deebase_exception(e)

    def _record_to_dict(self, record: Any) -> dict:
        """Convert a record (dict or dataclass) to dict."""
        if isinstance(record, dict):
            return record
        if is_dataclass(record) and not isinstance(record, type):
            from dataclasses import asdict
            return asdict(record)
        # Fallback - try to convert to dict
        if hasattr(record, "__dict__"):
            return record.__dict__
        return dict(record)


def create_crud_router(
    db: "Database",
    model_cls: type,
    *,
    table_name: str | None = None,
    prefix: str = "",
    tags: list[str] | None = None,
    pk_field: str = "id",
    validate_fks: bool = True,
    validators: dict[str, Callable[[Any], Any]] | None = None,
    exclude: Set[str] | None = None,
    overrides: dict[str, Callable] | None = None,
    response_model_exclude: Set[str] | None = None,
) -> APIRouter:
    """Create a FastAPI CRUD router from a DeeBase model.

    This is the main entry point for generating REST API endpoints.

    Args:
        db: DeeBase Database instance
        model_cls: Dataclass model class (must be @dataclass decorated)
        table_name: Table name (default: model class name lowercase)
        prefix: URL prefix for routes (e.g., "/api/users")
        tags: OpenAPI tags for documentation grouping
        pk_field: Primary key field name (default: "id")
        validate_fks: Whether to validate FK references before insert/update
        validators: Custom field validators/transformers {field: callable}
        exclude: Routes to exclude {"list", "get", "create", "update", "delete"}
        overrides: Route handlers to override {"create": custom_handler, ...}
        response_model_exclude: Fields to exclude from response models

    Returns:
        FastAPI APIRouter with CRUD endpoints

    Example:
        >>> from deebase.api import create_crud_router
        >>> from deebase import Database, ForeignKey
        >>> from dataclasses import dataclass
        >>> from fastapi import FastAPI
        >>>
        >>> @dataclass
        ... class Post:
        ...     id: int                            # Post ID
        ...     author_id: ForeignKey[int, "user"] # Author reference
        ...     title: str                         # Post title
        ...     published: bool = False            # Published status
        ...
        >>> app = FastAPI()
        >>> db = Database("sqlite+aiosqlite:///blog.db")
        >>>
        >>> app.include_router(create_crud_router(
        ...     db=db,
        ...     model_cls=Post,
        ...     prefix="/api/posts",
        ...     tags=["Posts"],
        ...     validate_fks=True,
        ...     validators={
        ...         "title": lambda v: v.strip()[:200] if v else v,
        ...     },
        ... ))

    Generated Endpoints:
        GET /api/posts/         - List all posts
        GET /api/posts/{id}     - Get post by ID
        POST /api/posts/        - Create a new post
        PATCH /api/posts/{id}   - Update a post
        DELETE /api/posts/{id}  - Delete a post
    """
    if not is_dataclass(model_cls):
        raise ValueError(
            f"{model_cls.__name__} must be a dataclass. "
            f"Use @dataclass decorator to define your model."
        )

    crud_router = CRUDRouter(
        db=db,
        model_cls=model_cls,
        table_name=table_name,
        prefix=prefix,
        tags=tags,
        pk_field=pk_field,
        validate_fks=validate_fks,
        validators=validators,
        exclude=exclude,
        overrides=overrides,
        response_model_exclude=response_model_exclude,
    )

    return crud_router.router
