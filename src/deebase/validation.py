"""Shared validation utilities for DeeBase.

Used by CLI (deebase data), API (create_crud_router), and admin UI.
The core Table class does NOT use these automatically - they are opt-in.
"""

from typing import Any, Callable, TYPE_CHECKING
import inspect

if TYPE_CHECKING:
    from .database import Database
    from .table import Table


def apply_validators(
    data: dict[str, Any],
    validators: dict[str, Callable[[Any], Any]] | None
) -> dict[str, Any]:
    """Apply field validators to data.

    Validators are plain functions that:
    - Receive a field value
    - Return the (possibly transformed) value
    - Raise ValueError with message on invalid input

    Args:
        data: Record data dict
        validators: Dict of field_name -> validator_function

    Returns:
        Validated (possibly transformed) data

    Raises:
        ValidationError: If any validator fails

    Example:
        >>> validators = {
        ...     "email": lambda v: v.lower() if v else v,
        ...     "name": lambda v: v.strip() if v else v,
        ... }
        >>> result = apply_validators({"email": "ALICE@EXAMPLE.COM"}, validators)
        >>> result["email"]
        'alice@example.com'
    """
    from .exceptions import ValidationError

    if not validators:
        return data

    errors = []
    result = data.copy()

    for field, validator in validators.items():
        if field in result and result[field] is not None:
            try:
                result[field] = validator(result[field])
            except (ValueError, TypeError) as e:
                errors.append({"field": field, "message": str(e)})

    if errors:
        raise ValidationError(
            "Validation failed",
            errors=errors
        )

    return result


async def apply_validators_async(
    data: dict[str, Any],
    validators: dict[str, Callable[[Any], Any]] | None
) -> dict[str, Any]:
    """Apply custom field validators/transformers to data (async-aware).

    Like apply_validators but supports async validator functions.

    Args:
        data: Dict of field values
        validators: Dict mapping field names to validator functions (sync or async)

    Returns:
        Transformed data dict

    Raises:
        ValidationError: If any validator fails
    """
    from .exceptions import ValidationError

    if not validators:
        return data

    errors = []
    result = data.copy()

    for field_name, validator in validators.items():
        if field_name in result:
            value = result[field_name]
            if value is not None:
                try:
                    # Validators can be sync or async
                    if inspect.iscoroutinefunction(validator):
                        result[field_name] = await validator(value)
                    else:
                        result[field_name] = validator(value)
                except (ValueError, TypeError) as e:
                    errors.append({"field": field_name, "message": str(e)})

    if errors:
        raise ValidationError(
            "Validation failed",
            errors=errors
        )

    return result


async def validate_foreign_keys(
    db: "Database",
    table: "Table",
    data: dict[str, Any]
) -> None:
    """Validate FK references exist.

    This provides better error messages than database constraint failures
    by checking FK existence at the application level.

    Args:
        db: Database instance for looking up referenced tables
        table: Table being inserted/updated
        data: Record data to validate

    Raises:
        ForeignKeyValidationError: If any FK references don't exist

    Example:
        >>> await validate_foreign_keys(db, posts_table, {"author_id": 999})
        ForeignKeyValidationError: Foreign key validation failed: author_id: Referenced user with id=999 does not exist
    """
    from .exceptions import NotFoundError, ForeignKeyValidationError

    errors = []

    for fk in table.foreign_keys:
        column = fk["column"]

        # Skip if column not in data or is None
        if column not in data or data[column] is None:
            continue

        fk_value = data[column]

        # Parse the reference
        ref_parts = fk["references"].split(".")
        ref_table = ref_parts[0]
        ref_col = ref_parts[1] if len(ref_parts) > 1 else "id"

        # Look up the referenced table
        parent_table = db._get_table(ref_table)
        if parent_table is None:
            # Table not in cache - skip validation
            # (This could happen if the table was never reflected)
            continue

        # Check if the referenced record exists
        try:
            await parent_table[fk_value]
        except NotFoundError:
            errors.append({
                "field": column,
                "value": fk_value,
                "message": f"Referenced {ref_table} with {ref_col}={fk_value} does not exist"
            })

    if errors:
        raise ForeignKeyValidationError(errors)


class ValidatedTable:
    """Wrapper that adds validation to Table write operations.

    All read operations pass through unchanged. Write operations
    (insert, update, upsert) validate before delegating to the
    underlying table.

    This provides opt-in validation without modifying the core Table class.

    Example:
        >>> from deebase.validation import ValidatedTable
        >>>
        >>> # Define validators for the users table
        >>> validators = {
        ...     "email": lambda v: v.lower() if v else v,
        ...     "name": lambda v: v.strip() if v else v,
        ... }
        >>>
        >>> # Wrap the table with validation
        >>> vusers = ValidatedTable(users, validators=validators)
        >>>
        >>> # All writes go through validation
        >>> await vusers.insert({"name": "  Alice  ", "email": "ALICE@EXAMPLE.COM"})
        # Normalized: name="Alice", email="alice@example.com"
        >>>
        >>> # Original table unchanged - no validation
        >>> await users.insert(data)
    """

    def __init__(
        self,
        table: "Table",
        validators: dict[str, Callable[[Any], Any]] | None = None,
        validate_fks: bool = True
    ):
        """Initialize ValidatedTable wrapper.

        Args:
            table: Table instance to wrap
            validators: Dict of field_name -> validator_function
            validate_fks: Whether to validate FK references exist (default: True)
        """
        self._table = table
        self._validators = validators or {}
        self._validate_fks = validate_fks

    # === Write operations (with validation) ===

    async def insert(self, data: Any) -> Any:
        """Insert a record after validation.

        Args:
            data: Record to insert (dict or dataclass)

        Returns:
            Inserted record
        """
        validated = await self._validate(data)
        return await self._table.insert(validated)

    async def update(self, data: Any) -> Any:
        """Update a record after validation.

        Args:
            data: Record to update (dict or dataclass)

        Returns:
            Updated record
        """
        validated = await self._validate(data)
        return await self._table.update(validated)

    async def upsert(self, data: Any) -> Any:
        """Upsert a record after validation.

        Args:
            data: Record to upsert (dict or dataclass)

        Returns:
            Upserted record
        """
        validated = await self._validate(data)
        return await self._table.upsert(validated)

    async def delete(self, pk: Any) -> None:
        """Delete a record (no validation needed).

        Args:
            pk: Primary key value
        """
        return await self._table.delete(pk)

    # === Read operations (passthrough) ===

    async def __call__(
        self,
        limit: int | None = None,
        with_pk: bool = False
    ) -> list:
        """Select records from the table."""
        return await self._table(limit=limit, with_pk=with_pk)

    async def __getitem__(self, pk: Any) -> Any:
        """Get a record by primary key."""
        return await self._table[pk]

    async def lookup(self, **kwargs) -> Any:
        """Look up a record by column values."""
        return await self._table.lookup(**kwargs)

    # === Properties (passthrough) ===

    @property
    def schema(self) -> str:
        """Get the table schema."""
        return self._table.schema

    @property
    def foreign_keys(self) -> list[dict]:
        """Get foreign key metadata."""
        return self._table.foreign_keys

    @property
    def indexes(self) -> list[dict]:
        """Get index metadata."""
        return self._table.indexes

    @property
    def fk(self):
        """Get FK navigation helper."""
        return self._table.fk

    @property
    def name(self) -> str:
        """Get table name."""
        return self._table.name

    @property
    def sa_table(self):
        """Get underlying SQLAlchemy table."""
        return self._table.sa_table

    # === Methods that return Tables (re-wrap) ===

    def xtra(self, **kwargs) -> "ValidatedTable":
        """Create a filtered view with the same validators.

        Args:
            **kwargs: Filter conditions

        Returns:
            New ValidatedTable wrapping the filtered table
        """
        new_table = self._table.xtra(**kwargs)
        return ValidatedTable(new_table, self._validators, self._validate_fks)

    # === Dataclass support ===

    def dataclass(self):
        """Get or generate the dataclass for this table."""
        return self._table.dataclass()

    # === FK navigation ===

    async def get_parent(self, record: Any, fk_column: str) -> Any | None:
        """Get parent record via FK."""
        return await self._table.get_parent(record, fk_column)

    async def get_children(
        self,
        record: Any,
        child_table: str,
        fk_column: str
    ) -> list:
        """Get child records via FK."""
        return await self._table.get_children(record, child_table, fk_column)

    # === Index management ===

    async def create_index(
        self,
        columns: str | list[str],
        name: str | None = None,
        unique: bool = False
    ) -> None:
        """Create an index on the table."""
        return await self._table.create_index(columns, name, unique)

    async def drop_index(self, name: str) -> None:
        """Drop an index from the table."""
        return await self._table.drop_index(name)

    async def drop(self) -> None:
        """Drop the table."""
        return await self._table.drop()

    # === Internal ===

    async def _validate(self, data: Any) -> dict:
        """Validate and transform data.

        Args:
            data: Record data (dict or dataclass)

        Returns:
            Validated dict ready for database operation

        Raises:
            ValidationError: If field validation fails
            ForeignKeyValidationError: If FK validation fails
        """
        from .dataclass_utils import record_to_dict

        data_dict = record_to_dict(data)
        validated = apply_validators(data_dict, self._validators)

        if self._validate_fks:
            await validate_foreign_keys(self._table._db, self._table, validated)

        return validated


# Type alias for validator functions
ValidatorFunc = Callable[[Any], Any]
