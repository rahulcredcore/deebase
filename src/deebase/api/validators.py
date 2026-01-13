"""Validators for API operations.

Note: Validation functions have been moved to deebase.validation
for sharing between CLI, API, and admin. This module re-exports them
for backward compatibility.

This module provides FK validation and custom field validators
for use with CRUD operations.
"""

# Re-export from shared validation module for backward compatibility
from ..validation import (
    apply_validators_async as apply_validators,  # API uses async version
    validate_foreign_keys,
    ValidatorFunc,
)
from .exceptions import ForeignKeyValidationError

__all__ = [
    "apply_validators",
    "validate_foreign_keys",
    "ForeignKeyValidationError",
    "ValidatorFunc",
]
