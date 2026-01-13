"""Python code generator for CLI commands.

Generates Python classes and db.create() calls from parsed field definitions.
"""

from typing import Optional
from .parser import FieldDefinition


def generate_class_source(
    class_name: str,
    fields: list[FieldDefinition],
    as_dataclass: bool = False,
    description: str = None,
) -> str:
    """Generate Python class source code from field definitions.

    Args:
        class_name: Name for the generated class
        fields: List of FieldDefinition objects
        as_dataclass: If True, generate a @dataclass decorated class
        description: Optional class docstring

    Returns:
        Python source code string

    Example:
        >>> fields = [
        ...     FieldDefinition(name='id', type_name='int'),
        ...     FieldDefinition(name='name', type_name='str'),
        ...     FieldDefinition(name='status', type_name='str', default='active'),
        ... ]
        >>> print(generate_class_source('User', fields))
        class User:
            id: int
            name: str
            status: str = "active"
    """
    lines = []

    # Collect imports
    imports = _collect_imports(fields, as_dataclass)
    if imports:
        lines.extend(imports)
        lines.append("")
        lines.append("")

    # Class definition
    if as_dataclass:
        lines.append("@dataclass")
    lines.append(f"class {class_name}:")

    # Class docstring
    if description:
        lines.append(f'    """{description}"""')

    # Field definitions
    for field in fields:
        line = _generate_field_line(field, as_dataclass)
        lines.append(f"    {line}")

    return "\n".join(lines)


def generate_create_call(
    class_name: str,
    pk: str | list[str],
    indexes: Optional[list[str]] = None,
    unique_fields: Optional[list[str]] = None,
    if_not_exists: bool = False,
) -> str:
    """Generate a db.create() call.

    Args:
        class_name: Name of the class to create
        pk: Primary key column name(s)
        indexes: List of index specifications
        unique_fields: Fields with unique constraints (become unique indexes)
        if_not_exists: If True, add if_not_exists=True parameter

    Returns:
        Python source code for db.create() call

    Example:
        >>> print(generate_create_call('User', 'id', indexes=['email'], unique_fields=['email']))
        await db.create(User, pk='id', indexes=[
            Index('ix_user_email', 'email', unique=True),
        ])
    """
    parts = [f"await db.create({class_name}"]

    # Primary key
    if isinstance(pk, list):
        pk_str = "[" + ", ".join(f"'{p}'" for p in pk) + "]"
    else:
        pk_str = f"'{pk}'"
    parts.append(f"pk={pk_str}")

    # Indexes (combine regular indexes and unique constraints)
    all_indexes = []

    # Add regular indexes
    if indexes:
        for idx in indexes:
            if ',' in idx:
                # Composite index
                cols = idx.split(',')
                cols_str = ", ".join(f"'{c.strip()}'" for c in cols)
                all_indexes.append(f"({cols_str})")
            else:
                all_indexes.append(f"'{idx}'")

    # Add unique indexes for unique fields
    if unique_fields:
        for field in unique_fields:
            idx_name = f"ix_{class_name.lower()}_{field}"
            all_indexes.append(f"Index('{idx_name}', '{field}', unique=True)")

    if all_indexes:
        indexes_str = "[\n        " + ",\n        ".join(all_indexes) + ",\n    ]"
        parts.append(f"indexes={indexes_str}")

    # Optional parameters
    if if_not_exists:
        parts.append("if_not_exists=True")

    # Build final string
    if len(parts) == 2:
        # Simple case: just class and pk
        return f"{parts[0]}, {parts[1]})"
    else:
        # Complex case: multiple parameters
        return f"{parts[0]}, " + ", ".join(parts[1:]) + ")"


def generate_migration_code(
    class_name: str,
    fields: list[FieldDefinition],
    pk: str | list[str],
    indexes: Optional[list[str]] = None,
) -> str:
    """Generate complete migration code for a table creation.

    This generates the full code that goes into a migration file,
    including the class definition and the db.create() call.

    Args:
        class_name: Name for the generated class
        fields: List of FieldDefinition objects
        pk: Primary key column name(s)
        indexes: List of index specifications

    Returns:
        Complete Python source code for the migration
    """
    lines = []

    # Generate class definition
    class_src = generate_class_source(class_name, fields, as_dataclass=False)
    lines.append(class_src)
    lines.append("")

    # Collect unique fields for index generation
    unique_fields = [f.name for f in fields if f.unique]

    # Generate create call
    create_call = generate_create_call(
        class_name,
        pk,
        indexes=indexes,
        unique_fields=unique_fields,
    )
    lines.append(create_call)

    return "\n".join(lines)


def generate_models_code(
    class_name: str,
    fields: list[FieldDefinition],
    description: str = None,
) -> str:
    """Generate models file code for a table.

    Generates a @dataclass decorated class suitable for a models file.
    All fields are Optional with default None for auto-generated values.

    Args:
        class_name: Name for the generated class
        fields: List of FieldDefinition objects
        description: Optional class docstring

    Returns:
        Python source code for the models file
    """
    return generate_class_source(class_name, fields, as_dataclass=True, description=description)


def _collect_imports(fields: list[FieldDefinition], as_dataclass: bool) -> list[str]:
    """Collect required imports for the generated code.

    Args:
        fields: List of FieldDefinition objects
        as_dataclass: Whether generating a dataclass

    Returns:
        List of import statements
    """
    imports = set()

    if as_dataclass:
        imports.add("from dataclasses import dataclass")

    needs_optional = False
    needs_text = False
    needs_fk = False
    needs_datetime = False
    needs_date = False
    needs_time = False

    for field in fields:
        if field.nullable or as_dataclass:
            needs_optional = True
        if field.type_name in ('Text', 'text'):
            needs_text = True
        if field.is_foreign_key:
            needs_fk = True
        if field.type_name == 'datetime':
            needs_datetime = True
        if field.type_name == 'date':
            needs_date = True
        if field.type_name == 'time':
            needs_time = True

    if needs_optional:
        imports.add("from typing import Optional")
    if needs_text or needs_fk:
        deebase_imports = []
        if needs_text:
            deebase_imports.append("Text")
        if needs_fk:
            deebase_imports.append("ForeignKey")
        imports.add(f"from deebase import {', '.join(deebase_imports)}")

    datetime_imports = []
    if needs_datetime:
        datetime_imports.append("datetime")
    if needs_date:
        datetime_imports.append("date")
    if needs_time:
        datetime_imports.append("time")
    if datetime_imports:
        imports.add(f"from datetime import {', '.join(datetime_imports)}")

    return sorted(imports)


def _generate_field_line(field: FieldDefinition, as_dataclass: bool, auto_doc: bool = True) -> str:
    """Generate a single field line for a class definition.

    Args:
        field: FieldDefinition object
        as_dataclass: Whether generating a dataclass field
        auto_doc: If True and no doc provided, generate placeholder doc

    Returns:
        Field line string (without indentation)
    """
    type_str = field.python_type
    base_line = ""

    # For dataclasses, make everything Optional with None default
    if as_dataclass:
        if not field.nullable and not field.is_foreign_key:
            type_str = f"Optional[{type_str}]"

        # Add default value
        if field.default is not None:
            if isinstance(field.default, str):
                base_line = f'{field.name}: {type_str} = "{field.default}"'
            else:
                base_line = f'{field.name}: {type_str} = {field.default}'
        else:
            base_line = f'{field.name}: {type_str} = None'
    else:
        # Regular class
        if field.default is not None:
            if isinstance(field.default, str):
                base_line = f'{field.name}: {type_str} = "{field.default}"'
            else:
                base_line = f'{field.name}: {type_str} = {field.default}'
        else:
            base_line = f'{field.name}: {type_str}'

    # Add inline comment (docstring) in docments style
    doc = field.doc
    if doc is None and auto_doc:
        # Generate placeholder doc
        doc = _generate_placeholder_doc(field)

    if doc:
        return f'{base_line}  # {doc}'
    return base_line


def _generate_placeholder_doc(field: FieldDefinition) -> str:
    """Generate a placeholder documentation string for a field.

    Args:
        field: FieldDefinition object

    Returns:
        Placeholder documentation string
    """
    # For foreign keys, include the reference
    if field.is_foreign_key:
        ref = f"{field.fk_table}.{field.fk_column}" if field.fk_column != 'id' else field.fk_table
        return f"FK -> {ref}"

    # Humanize the field name for placeholder
    # e.g., user_id -> User ID, firstName -> First Name
    name = field.name

    # Handle snake_case
    words = name.replace('_', ' ').split()

    # Handle camelCase
    result = []
    for word in words:
        # Split camelCase
        chars = list(word)
        current = []
        for i, c in enumerate(chars):
            if c.isupper() and current and not chars[i-1].isupper():
                result.append(''.join(current))
                current = [c.lower()]
            else:
                current.append(c)
        if current:
            result.append(''.join(current))

    # Title case and join
    humanized = ' '.join(w.capitalize() for w in result)

    # Get base type for description
    type_display = field.type_name
    if type_display in ('Text', 'text'):
        type_display = 'text'
    elif type_display in ('dict', 'json'):
        type_display = 'JSON'

    return f"{humanized} ({type_display})"
