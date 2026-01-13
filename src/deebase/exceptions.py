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
        errors: List of validation errors (for multiple field failures)
    """

    def __init__(
        self,
        message: str,
        field: str = None,
        value: Any = None,
        errors: list[dict] = None
    ):
        super().__init__(message)
        self.message = message
        self.field = field
        self.value = value
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON error response.

        Returns:
            Dict with 'type' and 'errors' keys suitable for HTTP response
        """
        if self.errors:
            return {
                "type": "validation_error",
                "errors": self.errors
            }
        return {
            "type": "validation_error",
            "field": self.field,
            "value": self.value,
            "message": self.message
        }


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


class ForeignKeyValidationError(DeeBaseError):
    """Raised when foreign key validation fails before insert/update.

    This is an application-level validation error that provides better
    error messages than database constraint failures.

    Attributes:
        errors: List of FK validation errors with field, value, and message
    """

    def __init__(self, errors: list[dict[str, Any]]):
        """Initialize with a list of FK validation errors.

        Args:
            errors: List of dicts with 'field', 'value', 'message' keys

        Example:
            >>> raise ForeignKeyValidationError([
            ...     {
            ...         'field': 'author_id',
            ...         'value': 999,
            ...         'message': 'Referenced user with id=999 does not exist'
            ...     }
            ... ])
        """
        self.errors = errors
        # Build a summary message
        error_msgs = [f"{e['field']}: {e['message']}" for e in errors]
        message = f"Foreign key validation failed: {'; '.join(error_msgs)}"
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON error response.

        Returns:
            Dict with 'type' and 'errors' keys suitable for HTTP response
        """
        return {
            "type": "foreign_key_validation_error",
            "errors": self.errors
        }
