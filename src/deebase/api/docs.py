"""Documentation extraction using fastcore.docments.

This module extracts field descriptions from dataclass inline comments
for use in Pydantic model Field descriptions and OpenAPI documentation.
"""

from dataclasses import is_dataclass
from typing import Any, get_type_hints

try:
    from fastcore.docments import docments
    FASTCORE_AVAILABLE = True
except ImportError:
    FASTCORE_AVAILABLE = False
    docments = None


def extract_field_docs(cls: type) -> dict[str, str]:
    """Extract field documentation from a dataclass using fastcore.docments.

    Parses inline comments from dataclass source code to extract field
    descriptions. Falls back to empty strings if fastcore is not available
    or if comments cannot be extracted.

    Args:
        cls: A dataclass class (must be decorated with @dataclass)

    Returns:
        Dict mapping field names to their documentation strings

    Example:
        >>> @dataclass
        ... class User:
        ...     id: int           # Auto-generated user ID
        ...     name: str         # Display name
        ...     email: str        # Email address (unique)
        ...
        >>> docs = extract_field_docs(User)
        >>> docs['id']
        'Auto-generated user ID'
        >>> docs['name']
        'Display name'
    """
    if not is_dataclass(cls):
        # Not a dataclass, return empty docs
        return {}

    if not FASTCORE_AVAILABLE:
        # fastcore not installed, return empty docs
        return {}

    try:
        # docments() returns a dict with field name -> docstring
        # It parses the source code to find inline comments
        docs = docments(cls)

        # Convert to simple string dict
        result = {}
        for field_name, doc in docs.items():
            if doc is not None:
                result[field_name] = str(doc).strip()
            else:
                result[field_name] = ""

        return result

    except Exception:
        # If parsing fails for any reason, return empty docs
        return {}


def get_field_description(
    field_name: str,
    field_docs: dict[str, str],
    is_fk: bool = False,
    fk_reference: str | None = None
) -> str:
    """Get the description for a field, optionally adding FK info.

    Args:
        field_name: Name of the field
        field_docs: Dict of field documentation from extract_field_docs()
        is_fk: Whether this field is a foreign key
        fk_reference: FK reference string (e.g., "user.id")

    Returns:
        Description string for the field
    """
    base_doc = field_docs.get(field_name, "")

    if is_fk and fk_reference:
        fk_note = f"(FK -> {fk_reference})"
        if base_doc:
            return f"{base_doc} {fk_note}"
        return fk_note

    return base_doc


def get_class_description(cls: type) -> str:
    """Get the class docstring for use in Pydantic/OpenAPI.

    Args:
        cls: A class (typically a dataclass)

    Returns:
        The class docstring if present, otherwise empty string
    """
    doc = getattr(cls, '__doc__', None)
    if doc:
        return doc.strip()
    return ""
