"""Field:type parser for CLI table creation.

Parses field specifications like:
    name:str
    email:str:unique
    bio:Text
    status:str:default=active
    author_id:int:fk=users
    category_id:int:fk=categories.id
"""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class FieldDefinition:
    """Parsed field definition from CLI syntax.

    Attributes:
        name: Field name
        type_name: Python type name (int, str, float, bool, bytes, Text, dict, datetime, date, time)
        unique: Whether field has UNIQUE constraint
        nullable: Whether field allows NULL values
        default: Default value (str, int, float, bool)
        fk_table: Foreign key target table
        fk_column: Foreign key target column (defaults to 'id')
    """
    name: str
    type_name: str
    unique: bool = False
    nullable: bool = False
    default: Optional[Any] = None
    fk_table: Optional[str] = None
    fk_column: Optional[str] = None

    @property
    def is_foreign_key(self) -> bool:
        """Check if this field is a foreign key."""
        return self.fk_table is not None

    @property
    def python_type(self) -> str:
        """Get the Python type annotation string."""
        # Map CLI type names to Python type names
        type_map = {
            'int': 'int',
            'str': 'str',
            'float': 'float',
            'bool': 'bool',
            'bytes': 'bytes',
            'Text': 'Text',
            'text': 'Text',  # Case-insensitive
            'dict': 'dict',
            'json': 'dict',  # Alias
            'datetime': 'datetime',
            'date': 'date',
            'time': 'time',
        }

        base_type = type_map.get(self.type_name, self.type_name)

        # Handle foreign keys
        if self.is_foreign_key:
            ref = f"{self.fk_table}.{self.fk_column}" if self.fk_column != 'id' else self.fk_table
            return f'ForeignKey[{base_type}, "{ref}"]'

        # Handle Optional
        if self.nullable:
            return f'Optional[{base_type}]'

        return base_type


def parse_field(field_spec: str) -> FieldDefinition:
    """Parse a field specification string.

    Format: name:type[:modifier[:modifier...]]

    Types:
        int, str, float, bool, bytes
        Text - Unlimited text
        dict (or json) - JSON column
        datetime, date, time

    Modifiers:
        :unique - UNIQUE constraint
        :nullable - Optional field (NULL allowed)
        :default=val - Default value
        :fk=table - Foreign key to table.id
        :fk=table.col - Foreign key to table.column

    Args:
        field_spec: Field specification string (e.g., "email:str:unique")

    Returns:
        FieldDefinition with parsed values

    Raises:
        ValueError: If the specification is invalid

    Examples:
        >>> parse_field("id:int")
        FieldDefinition(name='id', type_name='int')

        >>> parse_field("email:str:unique")
        FieldDefinition(name='email', type_name='str', unique=True)

        >>> parse_field("status:str:default=active")
        FieldDefinition(name='status', type_name='str', default='active')

        >>> parse_field("author_id:int:fk=users")
        FieldDefinition(name='author_id', type_name='int', fk_table='users', fk_column='id')
    """
    parts = field_spec.split(':')

    if len(parts) < 2:
        raise ValueError(
            f"Invalid field specification '{field_spec}'. "
            f"Expected format: name:type[:modifier[:modifier...]]"
        )

    name = parts[0].strip()
    type_name = parts[1].strip()
    modifiers = parts[2:]

    # Validate name
    if not name:
        raise ValueError(f"Field name cannot be empty in '{field_spec}'")

    if not name.isidentifier():
        raise ValueError(f"Invalid field name '{name}'. Must be a valid Python identifier.")

    # Validate type
    valid_types = {'int', 'str', 'float', 'bool', 'bytes', 'Text', 'text', 'dict', 'json', 'datetime', 'date', 'time'}
    if type_name not in valid_types:
        raise ValueError(
            f"Invalid type '{type_name}' in '{field_spec}'. "
            f"Valid types: {', '.join(sorted(valid_types))}"
        )

    # Parse modifiers
    unique = False
    nullable = False
    default = None
    fk_table = None
    fk_column = 'id'  # Default FK column

    for modifier in modifiers:
        modifier = modifier.strip()

        if modifier == 'unique':
            unique = True
        elif modifier == 'nullable':
            nullable = True
        elif modifier.startswith('default='):
            default_str = modifier[8:]  # Remove 'default='
            default = _parse_default_value(default_str, type_name)
        elif modifier.startswith('fk='):
            fk_ref = modifier[3:]  # Remove 'fk='
            if '.' in fk_ref:
                fk_table, fk_column = fk_ref.rsplit('.', 1)
            else:
                fk_table = fk_ref
                fk_column = 'id'
        elif modifier:
            raise ValueError(
                f"Unknown modifier '{modifier}' in '{field_spec}'. "
                f"Valid modifiers: unique, nullable, default=value, fk=table[.column]"
            )

    return FieldDefinition(
        name=name,
        type_name=type_name,
        unique=unique,
        nullable=nullable,
        default=default,
        fk_table=fk_table,
        fk_column=fk_column,
    )


def _parse_default_value(value_str: str, type_name: str) -> Any:
    """Parse a default value string into the appropriate Python type.

    Args:
        value_str: String representation of the default value
        type_name: The field type name

    Returns:
        Parsed default value
    """
    # Handle quoted strings
    if value_str.startswith('"') and value_str.endswith('"'):
        return value_str[1:-1]
    if value_str.startswith("'") and value_str.endswith("'"):
        return value_str[1:-1]

    # Try to infer type from the type_name
    if type_name == 'int':
        try:
            return int(value_str)
        except ValueError:
            raise ValueError(f"Invalid int default value: {value_str}")

    if type_name == 'float':
        try:
            return float(value_str)
        except ValueError:
            raise ValueError(f"Invalid float default value: {value_str}")

    if type_name == 'bool':
        if value_str.lower() in ('true', '1', 'yes'):
            return True
        elif value_str.lower() in ('false', '0', 'no'):
            return False
        else:
            raise ValueError(f"Invalid bool default value: {value_str}")

    # Default to string
    return value_str


def parse_fields(field_specs: list[str]) -> list[FieldDefinition]:
    """Parse multiple field specifications.

    Args:
        field_specs: List of field specification strings

    Returns:
        List of FieldDefinition objects
    """
    return [parse_field(spec) for spec in field_specs]
