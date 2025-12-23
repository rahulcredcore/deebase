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


def dataclass_src(cls: type) -> str:
    """Generate Python source code for a dataclass.

    Takes a dynamically generated dataclass (or any dataclass) and generates
    clean Python source code that can be saved to a file.

    Args:
        cls: Dataclass type to generate source for

    Returns:
        Python source code as a string

    Example:
        >>> from deebase import Database, dataclass_src
        >>> db = Database("sqlite+aiosqlite:///:memory:")
        >>> articles = await db.create(Article, pk='id')
        >>> ArticleDC = articles.dataclass()
        >>> src = dataclass_src(ArticleDC)
        >>> print(src)
        from dataclasses import dataclass
        from typing import Optional
        from datetime import datetime

        @dataclass
        class Article:
            id: Optional[int] = None
            title: Optional[str] = None
            content: Optional[str] = None
            ...
    """
    if not is_dataclass(cls):
        raise ValueError(f"{cls.__name__} is not a dataclass")

    # Collect imports needed
    imports = set()
    imports.add("from dataclasses import dataclass")

    # Check if we need typing imports
    needs_optional = False
    needs_dict = False
    needs_datetime = False
    needs_date = False
    needs_time = False

    # Get field information
    dc_fields = fields(cls)

    # Analyze fields to determine imports
    for field in dc_fields:
        field_type = field.type

        # Check for Optional (Union with None)
        if hasattr(field_type, '__origin__'):
            if field_type.__origin__ is type(None) or 'Union' in str(field_type):
                needs_optional = True
            # Handle dict type
            if field_type.__origin__ is dict:
                needs_dict = True

        # Check for datetime types
        type_str = str(field_type)
        if 'datetime.datetime' in type_str or type_str == "<class 'datetime.datetime'>":
            needs_datetime = True
        if 'datetime.date' in type_str or type_str == "<class 'datetime.date'>":
            needs_date = True
        if 'datetime.time' in type_str or type_str == "<class 'datetime.time'>":
            needs_time = True

        # Check base types
        if field_type is dict or (hasattr(field_type, '__origin__') and field_type.__origin__ is dict):
            needs_dict = True

    # Add imports
    if needs_optional or any('Union' in str(f.type) or '|' in str(f.type) for f in dc_fields):
        imports.add("from typing import Optional")
    if needs_dict:
        pass  # dict is built-in, no import needed

    datetime_imports = []
    if needs_datetime:
        datetime_imports.append("datetime")
    if needs_date:
        datetime_imports.append("date")
    if needs_time:
        datetime_imports.append("time")
    if datetime_imports:
        imports.add(f"from datetime import {', '.join(datetime_imports)}")

    # Sort imports
    import_lines = sorted(imports)

    # Generate class definition
    lines = []
    lines.extend(import_lines)
    lines.append("")
    lines.append("")
    lines.append("@dataclass")
    lines.append(f"class {cls.__name__}:")

    # Generate field definitions
    for field in dc_fields:
        # Format the type annotation
        type_str = _format_type_annotation(field.type)

        # Add default value if present
        if field.default is not field.default_factory:
            # Has a default value
            if field.default is None:
                lines.append(f"    {field.name}: {type_str} = None")
            elif isinstance(field.default, str):
                lines.append(f"    {field.name}: {type_str} = \"{field.default}\"")
            else:
                lines.append(f"    {field.name}: {type_str} = {field.default}")
        elif field.default_factory is not None and field.default_factory is not dataclass.MISSING:  # type: ignore
            # Has a default_factory
            lines.append(f"    {field.name}: {type_str} = field(default_factory={field.default_factory.__name__})")
        else:
            # No default
            lines.append(f"    {field.name}: {type_str}")

    return "\n".join(lines)


def _format_type_annotation(type_hint: Any) -> str:
    """Format a type annotation for source code generation.

    Args:
        type_hint: Type hint to format

    Returns:
        Formatted type annotation string
    """
    # Handle None type
    if type_hint is type(None):
        return "None"

    # Handle basic types
    if type_hint in (int, str, float, bool, bytes, dict):
        return type_hint.__name__

    # Handle typing types with __origin__ (Union, Optional, etc.)
    if hasattr(type_hint, '__origin__'):
        origin = type_hint.__origin__

        # Handle Union types (including Optional)
        if origin is type(None) or str(origin) == 'typing.Union':
            # Get the args
            args = getattr(type_hint, '__args__', ())

            # Check if it's Optional (Union with None)
            if type(None) in args:
                non_none_args = [arg for arg in args if arg is not type(None)]
                if len(non_none_args) == 1:
                    # It's Optional[T]
                    return f"Optional[{_format_type_annotation(non_none_args[0])}]"
                else:
                    # It's Union[T1, T2, ..., None]
                    formatted_args = [_format_type_annotation(arg) for arg in non_none_args]
                    return f"Union[{', '.join(formatted_args)}, None]"
            else:
                # Regular Union
                formatted_args = [_format_type_annotation(arg) for arg in args]
                return f"Union[{', '.join(formatted_args)}]"

        # Handle dict type
        if origin is dict:
            return "dict"

        # Handle other generic types
        if hasattr(type_hint, '__args__'):
            args = type_hint.__args__
            formatted_args = [_format_type_annotation(arg) for arg in args]
            return f"{origin.__name__}[{', '.join(formatted_args)}]"

    # Handle datetime types
    if hasattr(type_hint, '__module__') and hasattr(type_hint, '__name__'):
        if type_hint.__module__ == 'datetime':
            return type_hint.__name__

    # Check for | union syntax (Python 3.10+)
    type_str = str(type_hint)
    if '|' in type_str:
        # Convert to Optional if it ends with | None
        if type_str.endswith(' | None'):
            base_type = type_str.replace(' | None', '').replace("<class '", "").replace("'>", "")
            # Extract just the type name
            if '.' in base_type:
                base_type = base_type.split('.')[-1]
            return f"Optional[{base_type}]"

    # Default: try to get a readable name
    if hasattr(type_hint, '__name__'):
        return type_hint.__name__

    # Fallback to string representation
    type_str = str(type_hint)
    # Clean up the string representation
    type_str = type_str.replace("<class '", "").replace("'>", "")
    return type_str


def create_mod(module_path: str, *dataclasses: type, overwrite: bool = False) -> None:
    """Export dataclass definitions to a Python module file.

    Creates a Python file with the source code for one or more dataclasses.
    Useful for generating model files from database schemas.

    Args:
        module_path: Path to the output .py file
        *dataclasses: One or more dataclass types to export
        overwrite: If True, overwrite existing file; if False, raise error if file exists

    Raises:
        FileExistsError: If file exists and overwrite=False
        ValueError: If any argument is not a dataclass

    Example:
        >>> from deebase import Database, create_mod
        >>> db = Database("sqlite+aiosqlite:///myapp.db")
        >>> await db.reflect()
        >>> users = db.t.users
        >>> posts = db.t.posts
        >>>
        >>> # Generate dataclasses
        >>> UserDC = users.dataclass()
        >>> PostDC = posts.dataclass()
        >>>
        >>> # Export to models.py
        >>> create_mod("models.py", UserDC, PostDC, overwrite=True)
    """
    from pathlib import Path

    if not dataclasses:
        raise ValueError("At least one dataclass must be provided")

    # Verify all are dataclasses
    for cls in dataclasses:
        if not is_dataclass(cls):
            raise ValueError(f"{cls.__name__} is not a dataclass")

    # Check if file exists
    output_path = Path(module_path)
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"File {module_path} already exists. Use overwrite=True to replace it."
        )

    # Generate source code for all dataclasses
    sources = []
    all_imports = set()

    for cls in dataclasses:
        src = dataclass_src(cls)
        # Extract imports from the source
        imports = [line for line in src.split('\n') if line.startswith('from ') or line.startswith('import ')]
        all_imports.update(imports)
        # Extract just the class definition (skip imports)
        class_def = '\n'.join([line for line in src.split('\n') if not (line.startswith('from ') or line.startswith('import ') or line == '')])
        sources.append(class_def)

    # Combine everything
    output_lines = []
    output_lines.append('"""Auto-generated dataclass models from DeeBase."""')
    output_lines.append("")
    output_lines.extend(sorted(all_imports))
    output_lines.append("")
    output_lines.append("")

    # Add all class definitions with spacing
    for i, class_src in enumerate(sources):
        if i > 0:
            output_lines.append("")
            output_lines.append("")
        output_lines.append(class_src)

    # Write to file
    output_path.write_text('\n'.join(output_lines) + '\n')


def create_mod_from_tables(module_path: str, *tables, overwrite: bool = False) -> None:
    """Export dataclass definitions from Table instances to a Python module file.

    Convenience function that generates dataclasses from tables and exports them.

    Args:
        module_path: Path to the output .py file
        *tables: One or more Table instances to export
        overwrite: If True, overwrite existing file; if False, raise error if file exists

    Example:
        >>> from deebase import Database, create_mod_from_tables
        >>> db = Database("sqlite+aiosqlite:///myapp.db")
        >>> await db.reflect()
        >>>
        >>> # Export all tables to models.py
        >>> create_mod_from_tables("models.py", db.t.users, db.t.posts, overwrite=True)
    """
    dataclasses = []
    for table in tables:
        dc = table.dataclass()
        dataclasses.append(dc)

    create_mod(module_path, *dataclasses, overwrite=overwrite)
