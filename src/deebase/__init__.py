"""DeeBase - Async SQLAlchemy-based implementation of the fastlite API."""

from .database import Database
from .table import Table
from .view import View
from .column import Column, ColumnAccessor
from .exceptions import (
    DeeBaseError,
    NotFoundError,
    IntegrityError,
    ConnectionError,
    InvalidOperationError,
    ValidationError,
    SchemaError,
    ForeignKeyValidationError,
)
from .validation import (
    apply_validators,
    apply_validators_async,
    validate_foreign_keys,
    ValidatedTable,
)
from .types import Text, ForeignKey, Index
from .dataclass_utils import dataclass_src, create_mod, create_mod_from_tables

__version__ = "0.1.0"

__all__ = [
    "Database",
    "Table",
    "View",
    "Column",
    "ColumnAccessor",
    "DeeBaseError",
    "NotFoundError",
    "IntegrityError",
    "ConnectionError",
    "InvalidOperationError",
    "ValidationError",
    "SchemaError",
    "ForeignKeyValidationError",
    "Text",
    "ForeignKey",
    "Index",
    "dataclass_src",
    "create_mod",
    "create_mod_from_tables",
    "apply_validators",
    "apply_validators_async",
    "validate_foreign_keys",
    "ValidatedTable",
]
