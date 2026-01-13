"""Tests for the deebase.validation module."""

import pytest
import pytest_asyncio
from dataclasses import dataclass

from deebase import (
    Database,
    ForeignKey,
    apply_validators,
    apply_validators_async,
    validate_foreign_keys,
    ValidatedTable,
    ValidationError,
    ForeignKeyValidationError,
)


class TestApplyValidators:
    """Tests for apply_validators function."""

    def test_transforms_values(self):
        """Test that validators can transform values."""
        validators = {
            "name": lambda v: v.strip(),
            "email": lambda v: v.lower(),
        }
        data = {"name": "  Alice  ", "email": "ALICE@EXAMPLE.COM"}

        result = apply_validators(data, validators)

        assert result["name"] == "Alice"
        assert result["email"] == "alice@example.com"

    def test_raises_validation_error_on_failure(self):
        """Test that validators raise ValidationError."""
        def validate_positive(v):
            if v <= 0:
                raise ValueError("Must be positive")
            return v

        validators = {"count": validate_positive}
        data = {"count": -1}

        with pytest.raises(ValidationError) as exc_info:
            apply_validators(data, validators)

        assert "Validation failed" in str(exc_info.value)
        assert exc_info.value.errors[0]["field"] == "count"
        assert "Must be positive" in exc_info.value.errors[0]["message"]

    def test_skips_none_values(self):
        """Test that validators skip None values."""
        validators = {
            "name": lambda v: v.strip(),
        }
        data = {"name": None, "email": "test@example.com"}

        result = apply_validators(data, validators)

        assert result["name"] is None
        assert result["email"] == "test@example.com"

    def test_skips_missing_fields(self):
        """Test that validators skip fields not in data."""
        validators = {
            "name": lambda v: v.strip(),
            "email": lambda v: v.lower(),
        }
        data = {"name": "  Alice  "}

        result = apply_validators(data, validators)

        assert result["name"] == "Alice"
        assert "email" not in result

    def test_returns_original_if_no_validators(self):
        """Test that original data is returned if no validators."""
        data = {"name": "Alice", "email": "alice@example.com"}

        result = apply_validators(data, None)
        assert result == data

        result = apply_validators(data, {})
        assert result == data

    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are collected."""
        def validate_non_empty(v):
            if not v:
                raise ValueError("Cannot be empty")
            return v

        validators = {
            "name": validate_non_empty,
            "email": validate_non_empty,
        }
        data = {"name": "", "email": ""}

        with pytest.raises(ValidationError) as exc_info:
            apply_validators(data, validators)

        assert len(exc_info.value.errors) == 2


class TestApplyValidatorsAsync:
    """Tests for apply_validators_async function."""

    @pytest.mark.asyncio
    async def test_supports_async_validators(self):
        """Test that async validators are supported."""
        async def validate_async(v):
            return v.upper()

        validators = {"name": validate_async}
        data = {"name": "alice"}

        result = await apply_validators_async(data, validators)

        assert result["name"] == "ALICE"

    @pytest.mark.asyncio
    async def test_supports_sync_validators(self):
        """Test that sync validators also work."""
        validators = {"name": lambda v: v.strip()}
        data = {"name": "  Alice  "}

        result = await apply_validators_async(data, validators)

        assert result["name"] == "Alice"


class TestValidateForeignKeys:
    """Tests for validate_foreign_keys function."""

    @pytest_asyncio.fixture
    async def db_with_tables(self):
        """Create database with related tables."""
        db = Database("sqlite+aiosqlite:///:memory:")

        class User:
            id: int
            name: str

        class Post:
            id: int
            author_id: ForeignKey[int, "user"]
            title: str

        await db.create(User, pk="id")
        await db.create(Post, pk="id")

        # Insert a user
        await db.t.user.insert({"name": "Alice"})

        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_valid_fk_passes(self, db_with_tables):
        """Test that valid FK references pass validation."""
        db = db_with_tables
        posts = db.t.post

        data = {"author_id": 1, "title": "Hello"}

        # Should not raise
        await validate_foreign_keys(db, posts, data)

    @pytest.mark.asyncio
    async def test_invalid_fk_raises(self, db_with_tables):
        """Test that invalid FK references raise error."""
        db = db_with_tables
        posts = db.t.post

        data = {"author_id": 999, "title": "Hello"}

        with pytest.raises(ForeignKeyValidationError) as exc_info:
            await validate_foreign_keys(db, posts, data)

        assert exc_info.value.errors[0]["field"] == "author_id"
        assert exc_info.value.errors[0]["value"] == 999

    @pytest.mark.asyncio
    async def test_null_fk_skipped(self, db_with_tables):
        """Test that null FK values are skipped."""
        db = db_with_tables
        posts = db.t.post

        data = {"author_id": None, "title": "Hello"}

        # Should not raise
        await validate_foreign_keys(db, posts, data)

    @pytest.mark.asyncio
    async def test_missing_fk_skipped(self, db_with_tables):
        """Test that missing FK fields are skipped."""
        db = db_with_tables
        posts = db.t.post

        data = {"title": "Hello"}

        # Should not raise
        await validate_foreign_keys(db, posts, data)


class TestValidatedTable:
    """Tests for ValidatedTable wrapper class."""

    @pytest_asyncio.fixture
    async def db_with_users(self):
        """Create database with users table."""
        db = Database("sqlite+aiosqlite:///:memory:")

        class User:
            id: int
            name: str
            email: str

        await db.create(User, pk="id")

        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_insert_validates(self, db_with_users):
        """Test that insert validates data."""
        db = db_with_users
        validators = {
            "name": lambda v: v.strip(),
            "email": lambda v: v.lower(),
        }

        vusers = ValidatedTable(db.t.user, validators=validators)

        record = await vusers.insert({
            "name": "  Alice  ",
            "email": "ALICE@EXAMPLE.COM"
        })

        assert record["name"] == "Alice"
        assert record["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_update_validates(self, db_with_users):
        """Test that update validates data."""
        db = db_with_users
        validators = {"name": lambda v: v.strip()}

        # Insert without validation
        await db.t.user.insert({"name": "Alice", "email": "alice@example.com"})

        # Update with validation
        vusers = ValidatedTable(db.t.user, validators=validators)
        await vusers.update({"id": 1, "name": "  Bob  ", "email": "bob@example.com"})

        # Verify
        user = await db.t.user[1]
        assert user["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_preserves_dataclass_behavior(self, db_with_users):
        """Test that dataclass returns are preserved."""
        db = db_with_users

        # Set dataclass mode
        UserDC = db.t.user.dataclass()

        vusers = ValidatedTable(db.t.user)

        # Insert
        record = await vusers.insert({"name": "Alice", "email": "alice@example.com"})

        # Should be dataclass
        assert hasattr(record, "name")
        assert record.name == "Alice"

    @pytest.mark.asyncio
    async def test_xtra_rewraps(self, db_with_users):
        """Test that xtra() returns a ValidatedTable."""
        db = db_with_users
        validators = {"name": lambda v: v.strip()}

        vusers = ValidatedTable(db.t.user, validators=validators)

        # Insert two users
        await vusers.insert({"name": "Alice", "email": "alice@example.com"})
        await vusers.insert({"name": "Bob", "email": "bob@example.com"})

        # Filter
        filtered = vusers.xtra(name="Alice")

        # Should still be ValidatedTable
        assert isinstance(filtered, ValidatedTable)

        # And still validates
        records = await filtered()
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_read_operations_passthrough(self, db_with_users):
        """Test that read operations work without modification."""
        db = db_with_users

        # Insert directly
        await db.t.user.insert({"name": "Alice", "email": "alice@example.com"})
        await db.t.user.insert({"name": "Bob", "email": "bob@example.com"})

        vusers = ValidatedTable(db.t.user)

        # Test select
        records = await vusers()
        assert len(records) == 2

        # Test get by pk
        user = await vusers[1]
        assert user["name"] == "Alice"

        # Test lookup
        user = await vusers.lookup(name="Bob")
        assert user["email"] == "bob@example.com"

    @pytest.mark.asyncio
    async def test_properties_passthrough(self, db_with_users):
        """Test that properties are accessible."""
        db = db_with_users
        vusers = ValidatedTable(db.t.user)

        assert vusers.name == "user"
        assert "id" in vusers.schema
        assert vusers.sa_table is not None


class TestForeignKeyValidationError:
    """Tests for ForeignKeyValidationError exception."""

    def test_error_contains_errors_list(self):
        """Test that error contains errors list."""
        errors = [
            {"field": "author_id", "value": 999, "message": "Not found"}
        ]
        exc = ForeignKeyValidationError(errors)

        assert exc.errors == errors
        assert len(exc.errors) == 1

    def test_to_dict_format(self):
        """Test to_dict() returns correct format."""
        errors = [
            {"field": "author_id", "value": 999, "message": "Not found"}
        ]
        exc = ForeignKeyValidationError(errors)

        result = exc.to_dict()

        assert result["type"] == "foreign_key_validation_error"
        assert result["errors"] == errors

    def test_message_includes_field_info(self):
        """Test that message includes field information."""
        errors = [
            {"field": "author_id", "value": 999, "message": "Not found"}
        ]
        exc = ForeignKeyValidationError(errors)

        assert "author_id" in str(exc)
        assert "Not found" in str(exc)


class TestValidationErrorEnhancements:
    """Tests for ValidationError enhancements."""

    def test_errors_list_attribute(self):
        """Test that errors list is available."""
        errors = [{"field": "name", "message": "Required"}]
        exc = ValidationError("Failed", errors=errors)

        assert exc.errors == errors

    def test_to_dict_with_errors(self):
        """Test to_dict() with errors list."""
        errors = [{"field": "name", "message": "Required"}]
        exc = ValidationError("Failed", errors=errors)

        result = exc.to_dict()

        assert result["type"] == "validation_error"
        assert result["errors"] == errors

    def test_to_dict_without_errors(self):
        """Test to_dict() without errors list."""
        exc = ValidationError("Invalid value", field="name", value="bad")

        result = exc.to_dict()

        assert result["type"] == "validation_error"
        assert result["field"] == "name"
        assert result["value"] == "bad"
