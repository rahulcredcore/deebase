"""Pydantic model generation from DeeBase dataclasses.

This module generates Pydantic models (BaseModel subclasses) from dataclass
models, with proper type annotations, Field descriptions from docments,
and FK annotations.
"""

from dataclasses import fields, is_dataclass, MISSING
from datetime import datetime, date, time
from typing import Any, Optional, get_type_hints, get_origin, get_args, Type

from pydantic import BaseModel, Field, create_model

from .docs import extract_field_docs, get_field_description, get_class_description


# Type mapping from Python types to Pydantic-compatible types
TYPE_MAPPING = {
    int: int,
    str: str,
    float: float,
    bool: bool,
    bytes: bytes,
    datetime: datetime,
    date: date,
    time: time,
    dict: dict,
    list: list,
}


def _is_optional(type_hint: Any) -> bool:
    """Check if a type hint is Optional[T]."""
    origin = get_origin(type_hint)
    if origin is type(None):
        return True
    # Check for Union[X, None] which is Optional[X]
    try:
        from types import UnionType
        if origin is UnionType:
            args = get_args(type_hint)
            return type(None) in args
    except ImportError:
        pass
    # Standard typing.Union
    import typing
    if origin is typing.Union:
        args = get_args(type_hint)
        return type(None) in args
    return False


def _unwrap_optional(type_hint: Any) -> Any:
    """Unwrap Optional[T] to get T."""
    if not _is_optional(type_hint):
        return type_hint

    args = get_args(type_hint)
    for arg in args:
        if arg is not type(None):
            return arg
    return type_hint


def _is_foreign_key(type_hint: Any) -> tuple[bool, Any, str | None]:
    """Check if a type hint is ForeignKey[T, "table"] and extract info.

    Returns:
        Tuple of (is_fk, base_type, reference_string)
    """
    # Import the _ForeignKeyType from deebase.types
    try:
        from ..types import _ForeignKeyType
        if isinstance(type_hint, _ForeignKeyType):
            # This is a resolved ForeignKey type
            ref_str = f"{type_hint.table}.{type_hint.column}"
            return True, type_hint.base_type, ref_str
    except ImportError:
        pass

    # Check for class name
    type_name = getattr(type_hint, "__name__", "") or type(type_hint).__name__
    if type_name in ("ForeignKey", "_ForeignKeyType"):
        # Try to extract info from attributes
        if hasattr(type_hint, "base_type"):
            ref_str = None
            if hasattr(type_hint, "table"):
                col = getattr(type_hint, "column", "id")
                ref_str = f"{type_hint.table}.{col}"
            return True, type_hint.base_type, ref_str
        return True, int, None

    # Check if the string representation contains ForeignKey
    type_str = str(type_hint)
    if "ForeignKey[" in type_str:
        origin = get_origin(type_hint)
        if origin is not None:
            args = get_args(type_hint)
            if len(args) >= 2:
                base_type = args[0]
                ref_origin = get_origin(args[1])
                if ref_origin is not None:
                    ref_args = get_args(args[1])
                    if ref_args:
                        return True, base_type, str(ref_args[0])
                return True, base_type, None
            elif len(args) == 1:
                return True, args[0], None
        return True, int, None

    return False, type_hint, None


def _get_pydantic_type(type_hint: Any, for_update: bool = False) -> Any:
    """Convert a Python type hint to a Pydantic-compatible type.

    Args:
        type_hint: The original type hint
        for_update: If True, make the type Optional (for PATCH requests)

    Returns:
        Pydantic-compatible type
    """
    # Handle Optional first
    is_opt = _is_optional(type_hint)
    if is_opt:
        type_hint = _unwrap_optional(type_hint)

    # Handle ForeignKey
    is_fk, base_type, _ = _is_foreign_key(type_hint)
    if is_fk:
        type_hint = base_type

    # Handle Text type (our custom type for unlimited text)
    type_name = getattr(type_hint, "__name__", "") or type(type_hint).__name__
    if type_name == "Text":
        type_hint = str

    # Handle _ForeignKeyType that might have slipped through
    try:
        from ..types import _ForeignKeyType
        if isinstance(type_hint, _ForeignKeyType):
            type_hint = type_hint.base_type
    except ImportError:
        pass

    # Get the mapped type
    result_type = TYPE_MAPPING.get(type_hint, type_hint)

    # If result_type is not a basic type, default to str
    if result_type not in (int, str, float, bool, bytes, datetime, date, time, dict, list):
        # Try to get a sensible default
        if hasattr(result_type, "__origin__"):
            pass  # It's a generic type, keep it
        elif not isinstance(result_type, type):
            result_type = str  # Default to str for unknown types

    # Make optional if needed
    if is_opt or for_update:
        return Optional[result_type]

    return result_type


def generate_pydantic_models(
    dataclass_cls: type,
    pk_field: str = "id",
    fk_metadata: list[dict] | None = None,
) -> tuple[Type[BaseModel], Type[BaseModel], Type[BaseModel]]:
    """Generate Pydantic models from a dataclass.

    Generates three models:
    - Create model (for POST requests) - excludes pk_field, required fields
    - Update model (for PATCH requests) - all fields optional
    - Response model (for responses) - includes all fields including pk_field

    Args:
        dataclass_cls: The dataclass to generate models from
        pk_field: Name of the primary key field to exclude from Create model
        fk_metadata: List of FK definitions from table.foreign_keys

    Returns:
        Tuple of (CreateModel, UpdateModel, ResponseModel)

    Example:
        >>> @dataclass
        ... class Post:
        ...     id: int                            # Post ID
        ...     author_id: ForeignKey[int, "user"] # Author reference
        ...     title: str                         # Post title
        ...
        >>> PostCreate, PostUpdate, PostResponse = generate_pydantic_models(Post)
    """
    if not is_dataclass(dataclass_cls):
        raise ValueError(f"{dataclass_cls.__name__} must be a dataclass")

    class_name = dataclass_cls.__name__

    # Extract field and class documentation
    field_docs = extract_field_docs(dataclass_cls)
    class_doc = get_class_description(dataclass_cls)

    # Build FK lookup map
    fk_lookup = {}
    if fk_metadata:
        for fk in fk_metadata:
            fk_lookup[fk["column"]] = fk["references"]

    # Get type hints
    try:
        type_hints = get_type_hints(dataclass_cls)
    except Exception:
        # Fall back to __annotations__ if get_type_hints fails
        type_hints = getattr(dataclass_cls, "__annotations__", {})

    # Get dataclass fields for defaults
    dc_fields = {f.name: f for f in fields(dataclass_cls)}

    # Build field definitions for each model
    create_fields = {}
    update_fields = {}
    response_fields = {}

    for field_name, field_type in type_hints.items():
        # Get FK info
        is_fk, base_type, fk_ref = _is_foreign_key(field_type)
        if is_fk and field_name in fk_lookup:
            fk_ref = fk_lookup[field_name]

        # Get description
        description = get_field_description(
            field_name,
            field_docs,
            is_fk=is_fk,
            fk_reference=fk_ref
        )

        # Get default from dataclass
        dc_field = dc_fields.get(field_name)
        has_default = dc_field and dc_field.default is not MISSING
        has_default_factory = dc_field and dc_field.default_factory is not MISSING
        default_value = dc_field.default if has_default else None

        # Response model - include all fields
        response_type = _get_pydantic_type(field_type, for_update=False)
        if has_default:
            response_fields[field_name] = (
                response_type,
                Field(default=default_value, description=description)
            )
        elif has_default_factory:
            response_fields[field_name] = (
                response_type,
                Field(default_factory=dc_field.default_factory, description=description)
            )
        else:
            response_fields[field_name] = (
                response_type,
                Field(..., description=description)
            )

        # Skip pk_field for Create and Update models
        if field_name == pk_field:
            continue

        # Create model - required fields (unless they have defaults)
        create_type = _get_pydantic_type(field_type, for_update=False)
        if has_default:
            create_fields[field_name] = (
                create_type,
                Field(default=default_value, description=description)
            )
        elif has_default_factory:
            create_fields[field_name] = (
                create_type,
                Field(default_factory=dc_field.default_factory, description=description)
            )
        elif _is_optional(field_type):
            create_fields[field_name] = (
                create_type,
                Field(default=None, description=description)
            )
        else:
            create_fields[field_name] = (
                create_type,
                Field(..., description=description)
            )

        # Update model - all fields optional
        update_type = _get_pydantic_type(field_type, for_update=True)
        update_fields[field_name] = (
            update_type,
            Field(default=None, description=description)
        )

    # Create the models dynamically
    # Use class docstring if available, otherwise use generic description
    create_doc = f"{class_doc} (create request)" if class_doc else f"Request model for creating a {class_name}."
    update_doc = f"{class_doc} (update request)" if class_doc else f"Request model for updating a {class_name}."
    response_doc = class_doc if class_doc else f"Response model for {class_name}."

    CreateModel = create_model(
        f"{class_name}Create",
        __doc__=create_doc,
        **create_fields
    )

    UpdateModel = create_model(
        f"{class_name}Update",
        __doc__=update_doc,
        **update_fields
    )

    ResponseModel = create_model(
        f"{class_name}Response",
        __doc__=response_doc,
        **response_fields
    )

    return CreateModel, UpdateModel, ResponseModel
