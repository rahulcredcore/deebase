"""Validators for API operations.

This module provides FK validation and custom field validators
for use with CRUD operations.
"""

from typing import Any, Callable

from .exceptions import ForeignKeyValidationError


async def validate_foreign_keys(
    db: "Database",
    table: "Table",
    data: dict[str, Any]
) -> None:
    """Validate that all FK references exist before insert/update.

    This provides better error messages than database constraint failures
    by checking FK existence at the application level.

    Args:
        db: Database instance for looking up referenced tables
        table: Table being inserted/updated
        data: Dict of field values to validate

    Raises:
        ForeignKeyValidationError: If any FK references don't exist

    Example:
        >>> await validate_foreign_keys(db, posts_table, {"author_id": 999})
        ForeignKeyValidationError: Foreign key validation failed: author_id: Referenced user with id=999 does not exist
    """
    from ..exceptions import NotFoundError

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


async def apply_validators(
    data: dict[str, Any],
    validators: dict[str, Callable[[Any], Any]] | None
) -> dict[str, Any]:
    """Apply custom field validators/transformers to data.

    Validators can transform values (e.g., strip strings) or
    raise ValidationError if validation fails.

    Args:
        data: Dict of field values
        validators: Dict mapping field names to validator functions

    Returns:
        Transformed data dict

    Raises:
        ValidationError: If any validator fails

    Example:
        >>> validators = {
        ...     "title": lambda v: v.strip()[:200] if v else v,
        ...     "email": lambda v: v.lower() if v else v,
        ... }
        >>> result = await apply_validators(data, validators)
    """
    if not validators:
        return data

    result = data.copy()

    for field_name, validator in validators.items():
        if field_name in result:
            value = result[field_name]
            if value is not None:
                # Apply the validator
                # Validators can be sync or async
                import inspect
                if inspect.iscoroutinefunction(validator):
                    result[field_name] = await validator(value)
                else:
                    result[field_name] = validator(value)

    return result


# Type alias for validator functions
ValidatorFunc = Callable[[Any], Any]
