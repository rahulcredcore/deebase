"""Exception classes for deebase."""

from typing import Any


class DeeBaseError(Exception):
    """Base exception for all DeeBase errors."""
    pass


class NotFoundError(DeeBaseError):
    """Raised when a query returns no results or a record is not found.

    Attributes:
        message: Error message
        table_name: Name of the table (if applicable)
        filters: Filters that were applied (if applicable)
    """

    def __init__(self, message: str, table_name: str = None, filters: dict = None):
        super().__init__(message)
        self.message = message
        self.table_name = table_name
        self.filters = filters


class IntegrityError(DeeBaseError):
    """Raised when a database integrity constraint is violated.

    This includes primary key violations, foreign key violations,
    unique constraint violations, and check constraint violations.

    Attributes:
        message: Error message
        constraint: Name of the violated constraint (if available)
        table_name: Name of the table (if applicable)
    """

    def __init__(self, message: str, constraint: str = None, table_name: str = None):
        super().__init__(message)
        self.message = message
        self.constraint = constraint
        self.table_name = table_name


class ConnectionError(DeeBaseError):
    """Raised when there's a problem connecting to the database.

    Attributes:
        message: Error message
        database_url: Sanitized database URL (without password)
    """

    def __init__(self, message: str, database_url: str = None):
        super().__init__(message)
        self.message = message
        self.database_url = database_url


class InvalidOperationError(DeeBaseError):
    """Raised when an invalid operation is attempted.

    For example, trying to insert/update/delete on a read-only view.

    Attributes:
        message: Error message
        operation: Name of the invalid operation
        target: Target object (table/view name)
    """

    def __init__(self, message: str, operation: str = None, target: str = None):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.target = target


class ValidationError(DeeBaseError):
    """Raised when data validation fails.

    Attributes:
        message: Error message
        field: Field name that failed validation (if applicable)
        value: Invalid value (if applicable)
    """

    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.value = value


class SchemaError(DeeBaseError):
    """Raised when there's a schema-related error.

    For example, column not found, table not found, type mismatch.

    Attributes:
        message: Error message
        table_name: Name of the table (if applicable)
        column_name: Name of the column (if applicable)
    """

    def __init__(self, message: str, table_name: str = None, column_name: str = None):
        super().__init__(message)
        self.message = message
        self.table_name = table_name
        self.column_name = column_name
