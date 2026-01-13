"""Field renderers for admin detail view.

Each renderer takes (value, record, col_type) and returns HTML string.
Custom displays can override per table/field.
"""

import html
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional


def render_json(value: Any, record: dict, col_type: str) -> str:
    """Default renderer for JSON/dict types."""
    if value is None:
        return '<span class="null">—</span>'
    try:
        formatted = json.dumps(value, indent=2, ensure_ascii=False)
        escaped = html.escape(formatted)
        return f'<pre class="json-value">{escaped}</pre>'
    except (TypeError, ValueError):
        return f'<pre class="json-value">{html.escape(str(value))}</pre>'


def render_text(value: Any, record: dict, col_type: str) -> str:
    """Default renderer for TEXT columns (long text)."""
    if value is None:
        return '<span class="null">—</span>'
    escaped = html.escape(str(value))
    # Preserve newlines
    escaped = escaped.replace('\n', '<br>')
    return f'<div class="text-value">{escaped}</div>'


def render_boolean(value: Any, record: dict, col_type: str) -> str:
    """Default renderer for BOOLEAN columns."""
    if value is None:
        return '<span class="null">—</span>'
    if value is True or value == 1:
        return '<span class="bool-true">Yes</span>'
    elif value is False or value == 0:
        return '<span class="bool-false">No</span>'
    return html.escape(str(value))


def render_datetime(value: Any, record: dict, col_type: str) -> str:
    """Default renderer for DATETIME/TIMESTAMP columns."""
    if value is None:
        return '<span class="null">—</span>'
    return f'<span class="datetime-value">{html.escape(str(value))}</span>'


def render_integer(value: Any, record: dict, col_type: str) -> str:
    """Default renderer for INTEGER columns."""
    if value is None:
        return '<span class="null">—</span>'
    return f'<span class="int-value">{html.escape(str(value))}</span>'


def render_float(value: Any, record: dict, col_type: str) -> str:
    """Default renderer for FLOAT/REAL columns."""
    if value is None:
        return '<span class="null">—</span>'
    return f'<span class="float-value">{html.escape(str(value))}</span>'


def render_default(value: Any, record: dict, col_type: str) -> str:
    """Default renderer for unknown column types."""
    if value is None:
        return '<span class="null">—</span>'
    escaped = html.escape(str(value))
    return escaped


# Type -> renderer mapping
# Keys are checked via substring match (case-insensitive)
TYPE_RENDERERS: dict[str, Callable[[Any, dict, str], str]] = {
    "JSON": render_json,
    "TEXT": render_text,
    "BOOLEAN": render_boolean,
    "BOOL": render_boolean,
    "DATETIME": render_datetime,
    "TIMESTAMP": render_datetime,
    "INTEGER": render_integer,
    "INT": render_integer,
    "BIGINT": render_integer,
    "SMALLINT": render_integer,
    "FLOAT": render_float,
    "REAL": render_float,
    "DOUBLE": render_float,
    "NUMERIC": render_float,
    "DECIMAL": render_float,
}


def get_renderer(col_type: str) -> Callable[[Any, dict, str], str]:
    """Get default renderer for a column type.

    Args:
        col_type: SQLAlchemy column type string (e.g., "VARCHAR(255)", "INTEGER")

    Returns:
        Renderer function
    """
    col_type_upper = col_type.upper()
    for type_key, renderer in TYPE_RENDERERS.items():
        if type_key in col_type_upper:
            return renderer
    return render_default


# Cache for loaded display modules
_display_cache: dict[str, Optional[dict]] = {}


def _load_custom_display(table_name: str, field_name: str) -> Optional[Callable]:
    """Auto-discover displays/{table_name}.py and look up field.

    Args:
        table_name: Name of the table
        field_name: Name of the field

    Returns:
        Custom display function if found, None otherwise
    """
    # Check cache first
    cache_key = table_name
    if cache_key not in _display_cache:
        displays_dir = Path.cwd() / "displays"
        if not displays_dir.exists():
            _display_cache[cache_key] = None
        else:
            try:
                # Add cwd to path if needed
                cwd_str = str(Path.cwd())
                if cwd_str not in sys.path:
                    sys.path.insert(0, cwd_str)

                # Try to import the module
                import importlib
                module = importlib.import_module(f"displays.{table_name}")
                _display_cache[cache_key] = getattr(module, "DISPLAYS", {})
            except ImportError:
                _display_cache[cache_key] = None

    # Get from cache
    displays = _display_cache.get(cache_key)
    if displays is None:
        return None
    return displays.get(field_name)


def render_field(table_name: str, col_name: str, col_type: str, value: Any, record: dict) -> str:
    """Render a field value - checks custom displays first, then type default.

    This is the main entry point for field rendering in templates.

    Args:
        table_name: Name of the table
        col_name: Name of the column
        col_type: SQLAlchemy column type string
        value: The field value to render
        record: The full record (for context-aware rendering)

    Returns:
        HTML string for display
    """
    # Check for custom display first
    custom = _load_custom_display(table_name, col_name)
    if custom:
        try:
            return custom(value, record)
        except Exception:
            # Fall back to type renderer on error
            pass

    # Use type-based renderer
    renderer = get_renderer(col_type)
    return renderer(value, record, col_type)


def clear_display_cache() -> None:
    """Clear the display module cache.

    Useful for testing or when displays are modified.
    """
    _display_cache.clear()
