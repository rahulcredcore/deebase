"""Admin interface router for DeeBase.

Provides Django-like admin functionality with list/view/create/edit/delete views.

URL Structure (Phase 17):
    /admin/                         - Dashboard
    /admin/{table}/                 - List records
    /admin/{table}/new              - Create form
    /admin/{table}/{pk}             - Read-only detail view (NEW)
    /admin/{table}/{pk}/edit        - Edit form (MOVED from /{pk})
    /admin/{table}/{pk}/delete      - Delete confirmation
"""

from pathlib import Path
from typing import Any, TYPE_CHECKING

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .renderers import render_field

if TYPE_CHECKING:
    from deebase import Database


def create_admin_router(db: "Database") -> APIRouter:
    """Create admin interface router.

    Args:
        db: Database instance with tables to manage

    Returns:
        FastAPI router mounted at /admin/

    Example:
        >>> from deebase import Database
        >>> from deebase.admin import create_admin_router
        >>>
        >>> db = Database("sqlite+aiosqlite:///app.db")
        >>> app.include_router(create_admin_router(db))
    """
    router = APIRouter(prefix="/admin", tags=["Admin"])

    # Set up templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    # Add render_field to Jinja2 globals for use in templates
    templates.env.globals["render_field"] = render_field

    @router.get("/", response_class=HTMLResponse)
    async def admin_dashboard(request: Request):
        """Show dashboard with list of all tables."""
        # Get all tables from database cache
        tables = list(db._tables.keys())
        # Filter out internal tables
        tables = [t for t in tables if not t.startswith("_")]
        tables.sort()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "tables": tables,
        })

    @router.get("/{table_name}/", response_class=HTMLResponse)
    async def admin_list(
        request: Request,
        table_name: str,
        page: int = 1,
        per_page: int = 25
    ):
        """List records in a table with pagination."""
        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Note: Pagination is simplified since Table doesn't support offset
        # For now, just fetch records up to limit (full pagination would need SQL)
        records = await table(limit=per_page * page)

        # Convert dataclasses to dicts if needed
        records = [_record_to_dict(r) for r in records]

        # Get column names for header
        columns = [c.name for c in table.sa_table.columns]

        # Get PK column
        pk_cols = list(table.sa_table.primary_key.columns)
        pk_col = pk_cols[0].name if pk_cols else columns[0]

        return templates.TemplateResponse("list.html", {
            "request": request,
            "table_name": table_name,
            "columns": columns,
            "pk_col": pk_col,
            "records": records,
            "page": page,
            "per_page": per_page,
            "has_next": len(records) == per_page,
        })

    @router.get("/{table_name}/new", response_class=HTMLResponse)
    async def admin_create_form(request: Request, table_name: str):
        """Show create form for a new record."""
        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Get columns (exclude auto-increment PK)
        pk_cols = {c.name for c in table.sa_table.primary_key.columns}
        columns = []
        for c in table.sa_table.columns:
            # Skip auto-increment PKs
            if c.name in pk_cols and c.autoincrement:
                continue
            columns.append({
                "name": c.name,
                "type": str(c.type),
                "nullable": c.nullable,
                "default": c.default.arg if c.default is not None else None,
                "is_pk": c.name in pk_cols,
            })

        # Get FK options for dropdown fields
        fk_options = await _get_fk_options(db, table)

        return templates.TemplateResponse("create.html", {
            "request": request,
            "table_name": table_name,
            "columns": columns,
            "fk_options": fk_options,
            "fk_columns": set(fk_options.keys()),
        })

    @router.post("/{table_name}/new", response_class=HTMLResponse)
    async def admin_create_submit(request: Request, table_name: str):
        """Handle create form submission."""
        from deebase.validation import apply_validators, validate_foreign_keys
        from deebase.exceptions import ValidationError, ForeignKeyValidationError

        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Parse form data
        form_data = await request.form()
        data = _parse_form_data(dict(form_data), table)

        # Load and apply validators
        validators = _load_project_validators(table_name)

        try:
            validated = apply_validators(data, validators)
            await validate_foreign_keys(db, table, validated)

            record = await table.insert(validated)
            record_dict = _record_to_dict(record)

            # Get PK value for redirect
            pk_cols = list(table.sa_table.primary_key.columns)
            pk_col = pk_cols[0].name if pk_cols else "id"
            pk_value = record_dict.get(pk_col)

            return RedirectResponse(
                url=f"/admin/{table_name}/{pk_value}",
                status_code=303
            )

        except (ValidationError, ForeignKeyValidationError) as e:
            # Re-render form with error
            pk_cols = {c.name for c in table.sa_table.primary_key.columns}
            columns = []
            for c in table.sa_table.columns:
                if c.name in pk_cols and c.autoincrement:
                    continue
                columns.append({
                    "name": c.name,
                    "type": str(c.type),
                    "nullable": c.nullable,
                    "default": c.default.arg if c.default is not None else None,
                    "is_pk": c.name in pk_cols,
                })

            fk_options = await _get_fk_options(db, table)

            return templates.TemplateResponse("create.html", {
                "request": request,
                "table_name": table_name,
                "columns": columns,
                "fk_options": fk_options,
                "fk_columns": set(fk_options.keys()),
                "error": str(e),
                "values": data,
            })

    @router.get("/{table_name}/{pk}", response_class=HTMLResponse)
    async def admin_view(request: Request, table_name: str, pk: str):
        """Show read-only detail view for a record (Phase 17)."""
        from deebase.exceptions import NotFoundError

        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Convert pk to appropriate type
        pk_value = _convert_pk(pk, table)

        try:
            record = await table[pk_value]
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Record not found")

        record_dict = _record_to_dict(record)

        # Get columns with type info for rendering
        pk_cols = {c.name for c in table.sa_table.primary_key.columns}
        columns = []
        for c in table.sa_table.columns:
            columns.append({
                "name": c.name,
                "type": str(c.type),
                "is_pk": c.name in pk_cols,
            })

        return templates.TemplateResponse("view.html", {
            "request": request,
            "table_name": table_name,
            "pk": pk,
            "columns": columns,
            "record": record_dict,
        })

    @router.get("/{table_name}/{pk}/edit", response_class=HTMLResponse)
    async def admin_edit_form(request: Request, table_name: str, pk: str):
        """Show edit form for a record (Phase 17: moved from /{pk})."""
        from deebase.exceptions import NotFoundError

        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Convert pk to appropriate type
        pk_value = _convert_pk(pk, table)

        try:
            record = await table[pk_value]
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Record not found")

        record_dict = _record_to_dict(record)

        # Get columns
        pk_cols = {c.name for c in table.sa_table.primary_key.columns}
        columns = []
        for c in table.sa_table.columns:
            columns.append({
                "name": c.name,
                "type": str(c.type),
                "nullable": c.nullable,
                "is_pk": c.name in pk_cols,
            })

        # Get FK options
        fk_options = await _get_fk_options(db, table)

        return templates.TemplateResponse("edit.html", {
            "request": request,
            "table_name": table_name,
            "pk": pk,
            "columns": columns,
            "record": record_dict,
            "fk_options": fk_options,
            "fk_columns": set(fk_options.keys()),
        })

    @router.post("/{table_name}/{pk}/edit", response_class=HTMLResponse)
    async def admin_update_submit(request: Request, table_name: str, pk: str):
        """Handle update form submission (Phase 17: moved from POST /{pk})."""
        from deebase.validation import apply_validators, validate_foreign_keys
        from deebase.exceptions import ValidationError, ForeignKeyValidationError, NotFoundError

        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        pk_value = _convert_pk(pk, table)

        # Get existing record
        try:
            existing = await table[pk_value]
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Record not found")

        existing_dict = _record_to_dict(existing)

        # Parse form data and merge with existing
        form_data = await request.form()
        update_data = _parse_form_data(dict(form_data), table)

        # Merge - keep PK from existing
        merged = {**existing_dict, **update_data}

        # Load and apply validators
        validators = _load_project_validators(table_name)

        try:
            validated = apply_validators(merged, validators)
            await validate_foreign_keys(db, table, validated)

            await table.update(validated)

            return RedirectResponse(
                url=f"/admin/{table_name}/{pk}",
                status_code=303
            )

        except (ValidationError, ForeignKeyValidationError) as e:
            # Re-render form with error
            pk_cols = {c.name for c in table.sa_table.primary_key.columns}
            columns = []
            for c in table.sa_table.columns:
                columns.append({
                    "name": c.name,
                    "type": str(c.type),
                    "nullable": c.nullable,
                    "is_pk": c.name in pk_cols,
                })

            fk_options = await _get_fk_options(db, table)

            return templates.TemplateResponse("edit.html", {
                "request": request,
                "table_name": table_name,
                "pk": pk,
                "columns": columns,
                "record": merged,
                "fk_options": fk_options,
                "fk_columns": set(fk_options.keys()),
                "error": str(e),
            })

    @router.get("/{table_name}/{pk}/delete", response_class=HTMLResponse)
    async def admin_delete_confirm(request: Request, table_name: str, pk: str):
        """Show delete confirmation page."""
        from deebase.exceptions import NotFoundError

        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        pk_value = _convert_pk(pk, table)

        try:
            record = await table[pk_value]
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Record not found")

        record_dict = _record_to_dict(record)

        return templates.TemplateResponse("delete.html", {
            "request": request,
            "table_name": table_name,
            "pk": pk,
            "record": record_dict,
        })

    @router.post("/{table_name}/{pk}/delete")
    async def admin_delete_submit(request: Request, table_name: str, pk: str):
        """Handle delete confirmation."""
        from deebase.exceptions import NotFoundError

        table = _get_table(db, table_name)
        if table is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        pk_value = _convert_pk(pk, table)

        try:
            await table[pk_value]  # Verify exists
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Record not found")

        await table.delete(pk_value)

        return RedirectResponse(
            url=f"/admin/{table_name}/",
            status_code=303
        )

    return router


def _get_table(db: "Database", table_name: str):
    """Get table from database cache."""
    try:
        return db._get_table(table_name)
    except Exception:
        return None


def _record_to_dict(record: Any) -> dict:
    """Convert record to dict."""
    if isinstance(record, dict):
        return record
    if hasattr(record, '__dict__'):
        return {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
    return dict(record)


def _convert_pk(pk: str, table) -> Any:
    """Convert PK string to appropriate type."""
    # Get PK column type
    pk_cols = list(table.sa_table.primary_key.columns)
    if pk_cols:
        pk_type = pk_cols[0].type
        # Check if it's an integer type
        type_name = str(pk_type).upper()
        if 'INT' in type_name:
            try:
                return int(pk)
            except ValueError:
                pass
    return pk


def _parse_form_data(form_data: dict, table) -> dict:
    """Parse form data, converting types as needed."""
    result = {}

    for col in table.sa_table.columns:
        name = col.name
        if name not in form_data:
            continue

        value = form_data[name]

        # Skip empty strings for nullable fields
        if value == "" and col.nullable:
            result[name] = None
            continue
        if value == "":
            continue

        # Convert based on column type
        type_name = str(col.type).upper()

        if 'INT' in type_name:
            try:
                result[name] = int(value)
            except ValueError:
                result[name] = value
        elif 'FLOAT' in type_name or 'REAL' in type_name or 'DOUBLE' in type_name:
            try:
                result[name] = float(value)
            except ValueError:
                result[name] = value
        elif 'BOOL' in type_name:
            result[name] = value.lower() in ('true', '1', 'yes', 'on')
        else:
            result[name] = value

    return result


async def _get_fk_options(db: "Database", table) -> dict:
    """Get options for FK dropdown fields.

    Returns dict of column_name -> list of {value, label} dicts.
    """
    fk_options = {}

    for fk in table.foreign_keys:
        column = fk['column']
        ref_parts = fk['references'].split('.')
        ref_table_name = ref_parts[0]
        ref_col = ref_parts[1] if len(ref_parts) > 1 else 'id'

        try:
            ref_table = db._get_table(ref_table_name)
            if ref_table is None:
                continue

            records = await ref_table(limit=100)

            # Find a display field
            display_field = None
            if records:
                first = _record_to_dict(records[0])
                for field in ['name', 'title', 'label', 'email', 'username']:
                    if field in first:
                        display_field = field
                        break

            options = []
            for r in records:
                r_dict = _record_to_dict(r)
                pk_val = r_dict.get(ref_col)
                if display_field and display_field in r_dict:
                    label = f"{r_dict[display_field]} (id: {pk_val})"
                else:
                    label = str(pk_val)
                options.append({"value": pk_val, "label": label})

            fk_options[column] = options

        except Exception:
            fk_options[column] = []

    return fk_options


def _load_project_validators(table_name: str) -> dict:
    """Load validators from project's validators/ directory."""
    from pathlib import Path
    import sys

    validators_dir = Path.cwd() / "validators"
    if not validators_dir.exists():
        return {}

    try:
        original_path = sys.path.copy()
        sys.path.insert(0, str(Path.cwd()))

        try:
            from validators import get_validators
            return get_validators(table_name)
        except ImportError:
            return {}
        finally:
            sys.path = original_path

    except Exception:
        return {}
