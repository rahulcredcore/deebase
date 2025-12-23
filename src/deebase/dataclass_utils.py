"""Utilities for working with dataclasses and database records."""

from typing import Any, get_type_hints
from dataclasses import dataclass, fields, is_dataclass, asdict, make_dataclass
import sqlalchemy as sa


def extract_annotations(cls: type) -> dict[str, type]:
    """Extract type annotations from a class.

    Args:
        cls: Class to extract annotations from

    Returns:
        Dictionary mapping field names to their types
    """
    try:
        return get_type_hints(cls)
    except Exception:
        # Fallback to __annotations__ if get_type_hints fails
        return getattr(cls, '__annotations__', {})


def make_table_dataclass(table_name: str, sa_table: sa.Table) -> type:
    """Generate a dataclass from a SQLAlchemy Table.

    All fields are made Optional to support auto-generated values like
    auto-incrementing primary keys.

    Args:
        table_name: Name for the dataclass
        sa_table: SQLAlchemy Table instance

    Returns:
        Generated dataclass type
    """
    # Map SQLAlchemy types back to Python types
    field_definitions = []

    for column in sa_table.columns:
        python_type = sqlalchemy_type_to_python(column.type)

        # Make all fields Optional (default to None) to handle auto-generated values
        field_definitions.append((column.name, python_type | None, None))

    # Create the dataclass
    return make_dataclass(
        table_name.capitalize(),
        field_definitions,
        frozen=False
    )


def sqlalchemy_type_to_python(sa_type: sa.types.TypeEngine) -> type:
    """Convert a SQLAlchemy type to a Python type.

    Args:
        sa_type: SQLAlchemy type instance

    Returns:
        Corresponding Python type
    """
    from datetime import datetime, date, time

    # Map SQLAlchemy types to Python types
    type_map = {
        sa.Integer: int,
        sa.String: str,
        sa.Text: str,
        sa.Float: float,
        sa.Boolean: bool,
        sa.LargeBinary: bytes,
        sa.JSON: dict,
        sa.DateTime: datetime,
        sa.Date: date,
        sa.Time: time,
    }

    for sa_base_type, python_type in type_map.items():
        if isinstance(sa_type, sa_base_type):
            return python_type

    # Default to Any if we can't determine the type
    return Any


def record_to_dict(record: Any) -> dict:
    """Convert a record (dict, dataclass, or object) to a dictionary.

    Args:
        record: Record to convert (dict, dataclass instance, or object)

    Returns:
        Dictionary representation of the record
    """
    if isinstance(record, dict):
        return record

    if is_dataclass(record):
        return asdict(record)

    # For regular objects, extract __dict__
    if hasattr(record, '__dict__'):
        return {k: v for k, v in record.__dict__.items() if not k.startswith('_')}

    raise ValueError(f"Cannot convert {type(record)} to dict")


def dict_to_dataclass(data: dict, cls: type) -> Any:
    """Instantiate a dataclass from a dictionary.

    Args:
        data: Dictionary with field values
        cls: Dataclass type to instantiate

    Returns:
        Instance of the dataclass
    """
    if not is_dataclass(cls):
        raise ValueError(f"{cls} is not a dataclass")

    # Get the field names that the dataclass expects
    field_names = {f.name for f in fields(cls)}

    # Filter data to only include fields that exist in the dataclass
    filtered_data = {k: v for k, v in data.items() if k in field_names}

    return cls(**filtered_data)
