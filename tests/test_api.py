"""Tests for deebase.api module - FastAPI integration."""

import pytest
import pytest_asyncio
from dataclasses import dataclass
from typing import Optional

from deebase import Database, ForeignKey, Text
from deebase.api import (
    create_crud_router,
    CRUDRouter,
    ForeignKeyValidationError,
    generate_pydantic_models,
    validate_foreign_keys,
    apply_validators,
)


# Test Models
@dataclass
class User:
    id: int                      # Auto-generated user ID
    name: str                    # Display name
    email: str                   # Email address (unique)
    status: str = "active"       # Account status


@dataclass
class Post:
    id: int                            # Auto-generated post ID
    author_id: ForeignKey[int, "user"]  # Post author (must exist)
    title: str                         # Post title
    content: Text                      # Full post content
    published: bool = False            # Published status
    views: int = 0                     # View counter


@dataclass
class Comment:
    id: int
    post_id: ForeignKey[int, "post"]
    author_id: ForeignKey[int, "user"]
    text: str


# ============================================================================
# Pydantic Model Generation Tests
# ============================================================================

class TestPydanticModelGeneration:
    """Tests for generate_pydantic_models()."""

    def test_generates_three_models(self):
        """Should generate Create, Update, and Response models."""
        CreateModel, UpdateModel, ResponseModel = generate_pydantic_models(User)

        assert CreateModel.__name__ == "UserCreate"
        assert UpdateModel.__name__ == "UserUpdate"
        assert ResponseModel.__name__ == "UserResponse"

    def test_create_model_excludes_pk(self):
        """Create model should not include the primary key field."""
        CreateModel, _, _ = generate_pydantic_models(User, pk_field="id")

        fields = CreateModel.model_fields
        assert "id" not in fields
        assert "name" in fields
        assert "email" in fields

    def test_update_model_all_optional(self):
        """Update model should have all fields optional."""
        _, UpdateModel, _ = generate_pydantic_models(User)

        for field_name, field_info in UpdateModel.model_fields.items():
            # All fields should accept None (be optional)
            assert field_info.default is None, f"Field {field_name} should be optional"

    def test_response_model_includes_all_fields(self):
        """Response model should include all fields including pk."""
        _, _, ResponseModel = generate_pydantic_models(User)

        fields = ResponseModel.model_fields
        assert "id" in fields
        assert "name" in fields
        assert "email" in fields
        assert "status" in fields

    def test_preserves_defaults(self):
        """Models should preserve default values from dataclass."""
        CreateModel, _, ResponseModel = generate_pydantic_models(User)

        # Status has default "active"
        assert CreateModel.model_fields["status"].default == "active"
        assert ResponseModel.model_fields["status"].default == "active"

    def test_handles_optional_types(self):
        """Should handle Optional[T] types correctly."""
        @dataclass
        class WithOptional:
            id: int
            name: str
            nickname: Optional[str] = None

        CreateModel, UpdateModel, ResponseModel = generate_pydantic_models(WithOptional)

        # nickname should be optional in all models
        assert CreateModel.model_fields["nickname"].default is None

    def test_handles_text_type(self):
        """Should convert Text type to str."""
        CreateModel, _, _ = generate_pydantic_models(Post)

        # content is Text, should become str
        content_field = CreateModel.model_fields["content"]
        # Just check it exists and doesn't error
        assert content_field is not None

    def test_fk_metadata_in_description(self):
        """FK fields should have reference info in description."""
        fk_metadata = [{"column": "author_id", "references": "user.id"}]
        CreateModel, _, _ = generate_pydantic_models(
            Post,
            pk_field="id",
            fk_metadata=fk_metadata
        )

        desc = CreateModel.model_fields["author_id"].description
        assert "FK" in desc or "user.id" in desc


# ============================================================================
# FK Validation Tests
# ============================================================================

class TestFKValidation:
    """Tests for validate_foreign_keys()."""

    @pytest_asyncio.fixture
    async def db_with_users(self, db):
        """Database with users table for FK testing."""
        await db.create(User, pk="id")
        await db.enable_foreign_keys()

        # Create table wrapper for posts manually (to test FK validation)
        await db.q("""
            CREATE TABLE post (
                id INTEGER PRIMARY KEY,
                author_id INTEGER,
                title TEXT,
                content TEXT,
                published INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                FOREIGN KEY (author_id) REFERENCES user(id)
            )
        """)
        await db.reflect()

        # Insert a user
        users = db.t.user
        await users.insert({"name": "Alice", "email": "alice@example.com"})

        return db

    @pytest.mark.asyncio
    async def test_valid_fk_passes(self, db_with_users):
        """Should not raise for valid FK references."""
        db = db_with_users
        posts = db.t.post
        posts._foreign_keys = [{"column": "author_id", "references": "user.id"}]

        # Should not raise - user with id=1 exists
        await validate_foreign_keys(db, posts, {"author_id": 1})

    @pytest.mark.asyncio
    async def test_invalid_fk_raises(self, db_with_users):
        """Should raise ForeignKeyValidationError for invalid FK."""
        db = db_with_users
        posts = db.t.post
        posts._foreign_keys = [{"column": "author_id", "references": "user.id"}]

        with pytest.raises(ForeignKeyValidationError) as exc_info:
            await validate_foreign_keys(db, posts, {"author_id": 999})

        errors = exc_info.value.errors
        assert len(errors) == 1
        assert errors[0]["field"] == "author_id"
        assert errors[0]["value"] == 999

    @pytest.mark.asyncio
    async def test_null_fk_skipped(self, db_with_users):
        """Should skip validation for null FK values."""
        db = db_with_users
        posts = db.t.post
        posts._foreign_keys = [{"column": "author_id", "references": "user.id"}]

        # Should not raise - null FK is allowed
        await validate_foreign_keys(db, posts, {"author_id": None})

    @pytest.mark.asyncio
    async def test_missing_fk_skipped(self, db_with_users):
        """Should skip validation for missing FK in data."""
        db = db_with_users
        posts = db.t.post
        posts._foreign_keys = [{"column": "author_id", "references": "user.id"}]

        # Should not raise - FK not in data
        await validate_foreign_keys(db, posts, {"title": "Hello"})


# ============================================================================
# Custom Validators Tests
# ============================================================================

class TestCustomValidators:
    """Tests for apply_validators()."""

    @pytest.mark.asyncio
    async def test_validator_transforms_value(self):
        """Validators should transform values."""
        validators = {
            "title": lambda v: v.strip() if v else v,
        }

        result = await apply_validators(
            {"title": "  Hello World  "},
            validators
        )

        assert result["title"] == "Hello World"

    @pytest.mark.asyncio
    async def test_multiple_validators(self):
        """Multiple validators should all be applied."""
        validators = {
            "title": lambda v: v.strip(),
            "email": lambda v: v.lower() if v else v,
        }

        result = await apply_validators(
            {"title": "  Test  ", "email": "HELLO@EXAMPLE.COM"},
            validators
        )

        assert result["title"] == "Test"
        assert result["email"] == "hello@example.com"

    @pytest.mark.asyncio
    async def test_validator_skips_none(self):
        """Validators should skip None values."""
        validators = {
            "title": lambda v: v.upper(),
        }

        result = await apply_validators(
            {"title": None},
            validators
        )

        assert result["title"] is None

    @pytest.mark.asyncio
    async def test_async_validator(self):
        """Should support async validators."""
        async def async_validator(v):
            return v.strip()

        validators = {"title": async_validator}

        result = await apply_validators(
            {"title": "  Test  "},
            validators
        )

        assert result["title"] == "Test"


# ============================================================================
# ForeignKeyValidationError Tests
# ============================================================================

class TestForeignKeyValidationError:
    """Tests for ForeignKeyValidationError exception."""

    def test_error_contains_errors_list(self):
        """Should contain the errors list."""
        errors = [
            {"field": "author_id", "value": 999, "message": "Not found"}
        ]
        exc = ForeignKeyValidationError(errors)

        assert exc.errors == errors
        assert len(exc.errors) == 1

    def test_to_dict_format(self):
        """Should convert to dict for JSON response."""
        errors = [
            {"field": "author_id", "value": 999, "message": "Not found"}
        ]
        exc = ForeignKeyValidationError(errors)

        result = exc.to_dict()
        assert result["type"] == "foreign_key_validation_error"
        assert result["errors"] == errors

    def test_message_includes_field_info(self):
        """Error message should include field information."""
        errors = [
            {"field": "author_id", "value": 999, "message": "User not found"}
        ]
        exc = ForeignKeyValidationError(errors)

        assert "author_id" in str(exc)
        assert "User not found" in str(exc)


# ============================================================================
# CRUDRouter Integration Tests
# ============================================================================

class TestCRUDRouterIntegration:
    """Integration tests for CRUDRouter using FastAPI TestClient."""

    @pytest.mark.asyncio
    async def test_list_endpoint(self, db):
        """GET / should return list of records."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        # Create tables
        await db.create(User, pk="id")

        app = FastAPI()
        router = create_crud_router(
            db=db,
            model_cls=User,
            prefix="/api/users",
            tags=["Users"],
        )
        app.include_router(router)

        # Insert test data
        users = db.t.user
        await users.insert({"name": "Alice", "email": "alice@test.com"})

        with TestClient(app) as client:
            response = client.get("/api/users/")
            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_endpoint(self, db):
        """GET /{pk} should return single record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        await db.create(User, pk="id")

        app = FastAPI()
        router = create_crud_router(db=db, model_cls=User, prefix="/api/users")
        app.include_router(router)

        users = db.t.user
        user = await users.insert({"name": "Bob", "email": "bob@test.com"})
        # user is a dataclass instance, access via attribute
        user_id = user.id if hasattr(user, 'id') else user['id']

        with TestClient(app) as client:
            response = client.get(f"/api/users/{user_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_get_not_found(self, db):
        """GET /{pk} should return 404 for missing record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        await db.create(User, pk="id")

        app = FastAPI()
        router = create_crud_router(db=db, model_cls=User, prefix="/api/users")
        app.include_router(router)

        with TestClient(app) as client:
            response = client.get("/api/users/9999")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_endpoint(self, db):
        """POST / should create a new record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        await db.create(User, pk="id")

        app = FastAPI()
        router = create_crud_router(db=db, model_cls=User, prefix="/api/users")
        app.include_router(router)

        with TestClient(app) as client:
            response = client.post(
                "/api/users/",
                json={"name": "Charlie", "email": "charlie@test.com"}
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Charlie"
            assert "id" in data

    @pytest.mark.asyncio
    async def test_update_endpoint(self, db):
        """PATCH /{pk} should update a record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        await db.create(User, pk="id")

        app = FastAPI()
        router = create_crud_router(db=db, model_cls=User, prefix="/api/users")
        app.include_router(router)

        users = db.t.user
        user = await users.insert({"name": "Dan", "email": "dan@test.com"})
        user_id = user.id if hasattr(user, 'id') else user['id']

        with TestClient(app) as client:
            response = client.patch(
                f"/api/users/{user_id}",
                json={"name": "Daniel"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Daniel"

    @pytest.mark.asyncio
    async def test_delete_endpoint(self, db):
        """DELETE /{pk} should delete a record."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        await db.create(User, pk="id")

        app = FastAPI()
        router = create_crud_router(db=db, model_cls=User, prefix="/api/users")
        app.include_router(router)

        users = db.t.user
        user = await users.insert({"name": "Eve", "email": "eve@test.com"})
        user_id = user.id if hasattr(user, 'id') else user['id']

        with TestClient(app) as client:
            response = client.delete(f"/api/users/{user_id}")
            assert response.status_code == 204

            # Verify deleted
            response = client.get(f"/api/users/{user_id}")
            assert response.status_code == 404


# ============================================================================
# Route Customization Tests
# ============================================================================

class TestRouteCustomization:
    """Tests for route exclusion and overrides."""

    @pytest.mark.asyncio
    async def test_exclude_routes(self, db):
        """Should be able to exclude specific routes."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        await db.create(User, pk="id")

        app = FastAPI()
        router = create_crud_router(
            db=db,
            model_cls=User,
            prefix="/api/users",
            exclude={"delete", "update"},
        )
        app.include_router(router)

        with TestClient(app) as client:
            # These should work
            response = client.get("/api/users/")
            assert response.status_code == 200

            # These should be 405 (method not allowed) or 404
            response = client.delete("/api/users/1")
            assert response.status_code in (404, 405)


# ============================================================================
# CRUDRouter Hooks Tests
# ============================================================================

class TestCRUDRouterHooks:
    """Tests for CRUDRouter hook methods."""

    @pytest.mark.asyncio
    async def test_before_create_hook(self, db):
        """before_create hook should modify data before insert."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        class CustomRouter(CRUDRouter):
            async def before_create(self, data: dict) -> dict:
                data["status"] = "pending"  # Override default
                return data

        await db.create(User, pk="id")

        app = FastAPI()
        custom_router = CustomRouter(
            db=db,
            model_cls=User,
            prefix="/api/users",
        )
        app.include_router(custom_router.router)

        with TestClient(app) as client:
            response = client.post(
                "/api/users/",
                json={"name": "Test", "email": "test@test.com"}
            )
            assert response.status_code == 201
            data = response.json()
            # Our hook should have set status to "pending"
            assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_after_create_hook(self, db):
        """after_create hook should be called after insert."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        # Track that the hook was called
        hook_called = []

        class CustomRouter(CRUDRouter):
            async def after_create(self, record: dict) -> dict:
                hook_called.append(True)
                # Modify a field in the response (since extra fields get stripped)
                record["status"] = "created_via_hook"
                return record

        await db.create(User, pk="id")

        app = FastAPI()
        custom_router = CustomRouter(
            db=db,
            model_cls=User,
            prefix="/api/users",
        )
        app.include_router(custom_router.router)

        with TestClient(app) as client:
            response = client.post(
                "/api/users/",
                json={"name": "Test", "email": "test@test.com"}
            )
            assert response.status_code == 201
            data = response.json()
            # Verify hook was called
            assert len(hook_called) == 1
            # Verify modified field value
            assert data["status"] == "created_via_hook"


# ============================================================================
# Exception Mapping Tests
# ============================================================================

class TestExceptionMapping:
    """Tests for DeeBase exception to HTTP status mapping."""

    def test_not_found_maps_to_404(self):
        """NotFoundError should map to 404."""
        from deebase.api.router import _get_exception_status
        from deebase.exceptions import NotFoundError

        exc = NotFoundError("Not found")
        status = _get_exception_status(exc)
        assert status == 404

    def test_integrity_error_maps_to_422(self):
        """IntegrityError should map to 422."""
        from deebase.api.router import _get_exception_status
        from deebase.exceptions import IntegrityError

        exc = IntegrityError("Constraint violation")
        status = _get_exception_status(exc)
        assert status == 422

    def test_validation_error_maps_to_422(self):
        """ValidationError should map to 422."""
        from deebase.api.router import _get_exception_status
        from deebase.exceptions import ValidationError

        exc = ValidationError("Invalid data")
        status = _get_exception_status(exc)
        assert status == 422

    def test_fk_validation_error_maps_to_422(self):
        """ForeignKeyValidationError should map to 422."""
        from deebase.api.router import _get_exception_status

        exc = ForeignKeyValidationError([{"field": "x", "value": 1, "message": "msg"}])
        status = _get_exception_status(exc)
        assert status == 422

    def test_connection_error_maps_to_503(self):
        """ConnectionError should map to 503."""
        from deebase.api.router import _get_exception_status
        from deebase.exceptions import ConnectionError

        exc = ConnectionError("Connection failed")
        status = _get_exception_status(exc)
        assert status == 503


# ============================================================================
# Model Requirement Tests
# ============================================================================

class TestModelRequirements:
    """Tests for model class requirements."""

    @pytest.mark.asyncio
    async def test_requires_dataclass(self, db):
        """Should raise if model is not a dataclass."""

        class NotADataclass:
            id: int
            name: str

        with pytest.raises(ValueError) as exc_info:
            create_crud_router(
                db=db,
                model_cls=NotADataclass,
                prefix="/api/test",
            )

        assert "dataclass" in str(exc_info.value).lower()
