"""Type mapping utilities for converting Python types to SQLAlchemy types."""

from typing import Any, get_origin, get_args
from datetime import datetime, date, time
import sqlalchemy as sa


# Type marker for unlimited text columns
class Text:
    """Marker type for unlimited TEXT columns.

    Use this in type annotations to specify TEXT instead of VARCHAR:

    Example:
        from deebase.types import Text

        class Article:
            title: str      # → VARCHAR (limited string)
            content: Text   # → TEXT (unlimited text)
    """
    pass


def python_type_to_sqlalchemy(python_type: type) -> sa.types.TypeEngine:
    """Convert a Python type annotation to a SQLAlchemy type.

    Args:
        python_type: Python type (e.g., int, str, Optional[int])

    Returns:
        SQLAlchemy type instance

    Examples:
        >>> python_type_to_sqlalchemy(int)
        Integer()
        >>> python_type_to_sqlalchemy(str)
        String()
    """
    # Handle Optional[T] by extracting T
    origin = get_origin(python_type)
    if origin is not None:
        # This is a generic type like Optional[int], List[str], etc.
        args = get_args(python_type)
        if origin is type(None) or (len(args) == 2 and type(None) in args):
            # It's Optional[T] which is Union[T, None]
            inner_type = args[0] if args[1] is type(None) else args[1]
            return python_type_to_sqlalchemy(inner_type)

    # Check for special marker types first
    if python_type is Text or python_type == Text:
        return sa.Text()

    # Map basic Python types to SQLAlchemy types
    type_map = {
        int: sa.Integer,
        str: sa.String,      # VARCHAR (can add length later)
        float: sa.Float,
        bool: sa.Boolean,
        bytes: sa.LargeBinary,
        dict: sa.JSON,       # JSON in PostgreSQL, TEXT in SQLite (auto-serialized)
        datetime: sa.DateTime,
        date: sa.Date,
        time: sa.Time,
    }

    sa_type = type_map.get(python_type)
    if sa_type is None:
        raise ValueError(f"Unsupported type: {python_type}")

    return sa_type()


def is_optional(python_type: type) -> bool:
    """Check if a type annotation is Optional (Union[T, None]).

    Args:
        python_type: Python type annotation

    Returns:
        True if the type is Optional, False otherwise
    """
    origin = get_origin(python_type)
    if origin is None:
        return False

    args = get_args(python_type)
    # Check if it's Union[T, None] which is what Optional[T] expands to
    return type(None) in args
