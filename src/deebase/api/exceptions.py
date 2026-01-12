"""API-specific exception classes for deebase FastAPI integration."""

from typing import Any


class ForeignKeyValidationError(Exception):
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
