"""Type mapping utilities for converting Python types to SQLAlchemy types."""

from typing import Any, get_origin, get_args, Generic, TypeVar
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


# Type variable for ForeignKey base type
T = TypeVar('T')


class _ForeignKeyType:
    """Internal class representing a parsed ForeignKey type annotation.

    Attributes:
        base_type: The underlying Python type (e.g., int)
        table: The referenced table name (e.g., "users")
        column: The referenced column name (e.g., "id")
    """

    def __init__(self, base_type: type, table: str, column: str):
        self.base_type = base_type
        self.table = table
        self.column = column

    def __repr__(self):
        return f'ForeignKey[{self.base_type.__name__}, "{self.table}.{self.column}"]'


class ForeignKey(Generic[T]):
    """Type annotation for foreign key columns.

    Use this in type annotations to specify a foreign key relationship:

    Example:
        from deebase import ForeignKey

        class Post:
            id: int
            author_id: ForeignKey[int, "users"]       # → FK to users.id
            category_id: ForeignKey[int, "categories.id"]  # → FK to categories.id

    The reference string can be:
    - "table" - references table.id (default column is 'id')
    - "table.column" - references table.column explicitly
    """

    def __class_getitem__(cls, params) -> _ForeignKeyType:
        """Handle ForeignKey[int, "users"] or ForeignKey[int, "users.id"] syntax."""
        if not isinstance(params, tuple):
            raise TypeError("ForeignKey requires two parameters: ForeignKey[type, 'table'] or ForeignKey[type, 'table.column']")

        if len(params) != 2:
            raise TypeError("ForeignKey requires exactly two parameters: ForeignKey[type, 'table'] or ForeignKey[type, 'table.column']")

        base_type, reference = params

        if not isinstance(reference, str):
            raise TypeError(f"ForeignKey reference must be a string, got {type(reference).__name__}")

        # Parse reference: "users" → ("users", "id"), "users.email" → ("users", "email")
        if '.' in reference:
            table, column = reference.rsplit('.', 1)
        else:
            table, column = reference, 'id'

        return _ForeignKeyType(base_type, table, column)


def is_foreign_key(type_hint: Any) -> bool:
    """Check if a type hint is a ForeignKey type.

    Args:
        type_hint: Type hint to check

    Returns:
        True if it's a ForeignKey type, False otherwise
    """
    return isinstance(type_hint, _ForeignKeyType)


def get_foreign_key_info(type_hint: _ForeignKeyType) -> tuple[type, str, str]:
    """Extract foreign key information from a ForeignKey type.

    Args:
        type_hint: A _ForeignKeyType instance

    Returns:
        Tuple of (base_type, table, column)
    """
    return (type_hint.base_type, type_hint.table, type_hint.column)


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
    # Handle ForeignKey[T, "table"] by extracting T
    if isinstance(python_type, _ForeignKeyType):
        return python_type_to_sqlalchemy(python_type.base_type)

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


class Index:
    """Named index definition for table creation.

    Use this to create explicit indexes on table columns:

    Example:
        from deebase import Index

        # Create table with indexes
        articles = await db.create(
            Article,
            pk='id',
            indexes=[
                "slug",                                    # Simple index
                ("author_id", "created_at"),               # Composite index
                Index("idx_slug", "slug", unique=True),    # Named unique index
            ]
        )

    Args:
        name: Index name
        *columns: Column name(s) to index
        unique: If True, create a unique index (default False)
    """

    def __init__(self, name: str, *columns: str, unique: bool = False):
        """Initialize an Index definition.

        Args:
            name: Index name (e.g., "idx_email")
            *columns: Column names to index
            unique: If True, creates a UNIQUE index
        """
        if not columns:
            raise ValueError("Index requires at least one column")
        self.name = name
        self.columns = list(columns)
        self.unique = unique

    def __repr__(self) -> str:
        cols = ", ".join(self.columns)
        unique_str = ", unique=True" if self.unique else ""
        return f'Index("{self.name}", {cols}{unique_str})'
