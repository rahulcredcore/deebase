"""API-specific exception classes for deebase FastAPI integration.

Note: ForeignKeyValidationError has been moved to deebase.exceptions
for sharing between CLI, API, and admin. This module re-exports it
for backward compatibility.
"""

# Re-export from main exceptions module for backward compatibility
from ..exceptions import ForeignKeyValidationError

__all__ = ["ForeignKeyValidationError"]
