"""Tests for Phase 10: Enhanced create() with Foreign Keys & Defaults."""

import pytest
import pytest_asyncio
from dataclasses import dataclass, field
from typing import Optional

from deebase import Database, ForeignKey, Text
from deebase.types import is_foreign_key, get_foreign_key_info, _ForeignKeyType
from deebase.dataclass_utils import extract_defaults
from deebase.exceptions import SchemaError, IntegrityError


# =============================================================================
# ForeignKey Type Tests
# =============================================================================

class TestForeignKeyType:
    """Tests for ForeignKey type annotation."""

    def test_foreign_key_basic(self):
        """Test ForeignKey[int, 'users'] creates correct type."""
        fk = ForeignKey[int, "users"]
        assert isinstance(fk, _ForeignKeyType)
        assert fk.base_type is int
        assert fk.table == "users"
        assert fk.column == "id"  # Default column

    def test_foreign_key_with_explicit_column(self):
        """Test ForeignKey[int, 'users.email'] parses column correctly."""
        fk = ForeignKey[int, "users.email"]
        assert fk.base_type is int
        assert fk.table == "users"
        assert fk.column == "email"

    def test_foreign_key_str_type(self):
        """Test ForeignKey with str base type."""
        fk = ForeignKey[str, "categories.slug"]
        assert fk.base_type is str
        assert fk.table == "categories"
        assert fk.column == "slug"

    def test_is_foreign_key(self):
        """Test is_foreign_key helper function."""
        fk = ForeignKey[int, "users"]
        assert is_foreign_key(fk) is True
        assert is_foreign_key(int) is False
        assert is_foreign_key(str) is False

    def test_get_foreign_key_info(self):
        """Test get_foreign_key_info extracts all info."""
        fk = ForeignKey[int, "posts.author_id"]
        base_type, table, column = get_foreign_key_info(fk)
        assert base_type is int
        assert table == "posts"
        assert column == "author_id"

    def test_foreign_key_repr(self):
        """Test ForeignKey string representation."""
        fk = ForeignKey[int, "users"]
        assert 'ForeignKey' in repr(fk)
        assert 'users' in repr(fk)

    def test_foreign_key_missing_params_raises(self):
        """Test ForeignKey with missing params raises TypeError."""
        with pytest.raises(TypeError):
            ForeignKey[int]  # Missing reference string

    def test_foreign_key_invalid_reference_type(self):
        """Test ForeignKey with non-string reference raises TypeError."""
        with pytest.raises(TypeError):
            ForeignKey[int, 123]  # Reference must be string


# =============================================================================
# extract_defaults Tests
# =============================================================================

class TestExtractDefaults:
    """Tests for extract_defaults function."""

    def test_extract_defaults_regular_class_str(self):
        """Test extracting string default from regular class."""
        class Article:
            id: int
            status: str = "draft"

        defaults = extract_defaults(Article)
        assert defaults == {"status": "draft"}

    def test_extract_defaults_regular_class_int(self):
        """Test extracting int default from regular class."""
        class Article:
            id: int
            views: int = 0

        defaults = extract_defaults(Article)
        assert defaults == {"views": 0}

    def test_extract_defaults_regular_class_multiple(self):
        """Test extracting multiple defaults from regular class."""
        class Article:
            id: int
            status: str = "pending"
            views: int = 0
            featured: bool = False

        defaults = extract_defaults(Article)
        assert defaults == {"status": "pending", "views": 0, "featured": False}

    def test_extract_defaults_skips_mutable_dict(self):
        """Test that mutable dict default is skipped."""
        class Article:
            id: int
            metadata: dict = {}

        defaults = extract_defaults(Article)
        assert "metadata" not in defaults

    def test_extract_defaults_skips_mutable_list(self):
        """Test that mutable list default is skipped."""
        class Article:
            id: int
            tags: list = []

        defaults = extract_defaults(Article)
        assert "tags" not in defaults

    def test_extract_defaults_dataclass_str(self):
        """Test extracting string default from dataclass."""
        @dataclass
        class Article:
            id: Optional[int] = None
            status: str = "published"

        defaults = extract_defaults(Article)
        assert defaults == {"status": "published"}

    def test_extract_defaults_dataclass_skips_none(self):
        """Test that None default is not extracted (it means nullable)."""
        @dataclass
        class Article:
            id: Optional[int] = None
            title: Optional[str] = None

        defaults = extract_defaults(Article)
        assert defaults == {}

    def test_extract_defaults_dataclass_skips_default_factory(self):
        """Test that default_factory is skipped."""
        @dataclass
        class Article:
            id: Optional[int] = None
            status: str = "draft"
            metadata: dict = field(default_factory=dict)

        defaults = extract_defaults(Article)
        assert defaults == {"status": "draft"}
        assert "metadata" not in defaults

    def test_extract_defaults_dataclass_multiple(self):
        """Test extracting multiple defaults from dataclass."""
        @dataclass
        class Article:
            id: Optional[int] = None
            status: str = "draft"
            views: int = 0
            active: bool = True

        defaults = extract_defaults(Article)
        assert defaults == {"status": "draft", "views": 0, "active": True}

    def test_extract_defaults_no_defaults(self):
        """Test class with no defaults returns empty dict."""
        class Article:
            id: int
            title: str

        defaults = extract_defaults(Article)
        assert defaults == {}


# =============================================================================
# create() with Defaults Tests
# =============================================================================

class TestCreateWithDefaults:
    """Tests for create() with default values."""

    # Uses the shared db fixture from conftest.py

    @pytest.mark.asyncio
    async def test_create_with_string_default(self, db):
        """Test table creation with string default value."""
        class Article:
            id: int
            status: str = "draft"

        table = await db.create(Article, pk='id')

        # Insert without specifying status - should get default
        article = await table.insert({"id": 1})
        assert article["status"] == "draft"

    @pytest.mark.asyncio
    async def test_create_with_int_default(self, db):
        """Test table creation with int default value."""
        class Article:
            id: int
            views: int = 0

        table = await db.create(Article, pk='id')

        # Insert without specifying views - should get default
        article = await table.insert({"id": 1})
        assert article["views"] == 0

    @pytest.mark.asyncio
    async def test_create_with_bool_default(self, db):
        """Test table creation with bool default value."""
        class Article:
            id: int
            active: bool = True

        table = await db.create(Article, pk='id')

        # Insert without specifying active - should get default
        article = await table.insert({"id": 1})
        assert article["active"] == True

    @pytest.mark.asyncio
    async def test_create_with_multiple_defaults(self, db):
        """Test table creation with multiple default values."""
        class Article:
            id: int
            status: str = "pending"
            views: int = 100
            featured: bool = False

        table = await db.create(Article, pk='id')

        # Insert without specifying any optional fields
        article = await table.insert({"id": 1})
        assert article["status"] == "pending"
        assert article["views"] == 100
        assert article["featured"] == False

    @pytest.mark.asyncio
    async def test_create_with_dataclass_defaults(self, db):
        """Test table creation from dataclass with defaults."""
        @dataclass
        class Article:
            id: Optional[int] = None
            status: str = "published"
            views: int = 50

        table = await db.create(Article, pk='id')

        # Insert without specifying optional fields
        article = await table.insert({})
        assert article.status == "published"
        assert article.views == 50

    @pytest.mark.asyncio
    async def test_create_default_overridden_by_explicit_value(self, db):
        """Test that explicit values override defaults."""
        class Article:
            id: int
            status: str = "draft"

        table = await db.create(Article, pk='id')

        # Insert with explicit status
        article = await table.insert({"id": 1, "status": "published"})
        assert article["status"] == "published"


# =============================================================================
# create() with ForeignKey Tests
# =============================================================================

class TestCreateWithForeignKey:
    """Tests for create() with ForeignKey types."""

    # Uses the shared db fixture from conftest.py

    @pytest.mark.asyncio
    async def test_create_with_foreign_key(self, db):
        """Test table creation with ForeignKey type."""
        # First create the referenced table
        class User:
            id: int
            name: str

        await db.create(User, pk='id')

        class Post:
            id: int
            title: str
            author_id: ForeignKey[int, "user"]

        posts = await db.create(Post, pk='id')

        # Verify FK column exists
        assert 'author_id' in posts.sa_table.c

    @pytest.mark.asyncio
    async def test_foreign_key_constraint_enforced(self, db):
        """Test that FK constraint is enforced on insert."""
        # First create the referenced table
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.insert({"id": 1, "name": "Alice"})

        class Post:
            id: int
            title: str
            author_id: ForeignKey[int, "user"]

        posts = await db.create(Post, pk='id')

        # Insert with valid FK should succeed
        post = await posts.insert({"id": 1, "title": "Hello", "author_id": 1})
        assert post["author_id"] == 1

        # Enable FK enforcement for SQLite
        await db.q("PRAGMA foreign_keys = ON")

        # Insert with invalid FK should fail
        with pytest.raises(IntegrityError):
            await posts.insert({"id": 2, "title": "Fail", "author_id": 999})

    @pytest.mark.asyncio
    async def test_foreign_key_with_explicit_column(self, db):
        """Test FK referencing explicit column."""
        class Category:
            id: int
            slug: str

        await db.create(Category, pk='id')

        # Insert a category
        categories = db.t.category
        await categories.insert({"id": 1, "slug": "tech"})

        class Article:
            id: int
            category_slug: ForeignKey[str, "category.slug"]

        # Note: This requires the referenced column to have a unique constraint
        # For this test, we just verify the column is created
        articles = await db.create(Article, pk='id')
        assert 'category_slug' in articles.sa_table.c

    @pytest.mark.asyncio
    async def test_create_with_multiple_foreign_keys(self, db):
        """Test table with multiple FK columns."""
        class User:
            id: int
            name: str

        class Category:
            id: int
            name: str

        await db.create(User, pk='id')
        await db.create(Category, pk='id')

        class Article:
            id: int
            title: str
            author_id: ForeignKey[int, "user"]
            category_id: ForeignKey[int, "category"]

        articles = await db.create(Article, pk='id')

        assert 'author_id' in articles.sa_table.c
        assert 'category_id' in articles.sa_table.c


# =============================================================================
# create() with if_not_exists Tests
# =============================================================================

class TestCreateIfNotExists:
    """Tests for create() with if_not_exists parameter."""

    # Uses the shared db fixture from conftest.py

    @pytest.mark.asyncio
    async def test_create_if_not_exists_new_table(self, db):
        """Test if_not_exists with new table creates it."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id', if_not_exists=True)
        assert users is not None

        # Should work normally
        user = await users.insert({"id": 1, "name": "Alice"})
        assert user["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_create_if_not_exists_existing_table(self, db):
        """Test if_not_exists with existing table doesn't error."""
        class User:
            id: int
            name: str

        # Create first time
        await db.create(User, pk='id')

        # Create again with if_not_exists - should not error
        users = await db.create(User, pk='id', if_not_exists=True)
        assert users is not None

    @pytest.mark.asyncio
    async def test_create_without_if_not_exists_errors(self, db):
        """Test create without if_not_exists errors on existing table."""
        class User:
            id: int
            name: str

        # Create first time
        await db.create(User, pk='id')

        # Create again without if_not_exists - should error
        with pytest.raises((SchemaError, Exception)):
            await db.create(User, pk='id')


# =============================================================================
# create() with replace Tests
# =============================================================================

class TestCreateReplace:
    """Tests for create() with replace parameter."""

    # Uses the shared db fixture from conftest.py

    @pytest.mark.asyncio
    async def test_replace_drops_and_recreates(self, db):
        """Test replace=True drops existing table and recreates."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.insert({"id": 1, "name": "Alice"})

        # Verify data exists
        all_users = await users()
        assert len(all_users) == 1

        # Replace - should drop and recreate
        users = await db.create(User, pk='id', replace=True)

        # Table should be empty now
        all_users = await users()
        assert len(all_users) == 0

    @pytest.mark.asyncio
    async def test_replace_with_schema_change(self, db):
        """Test replace allows schema changes."""
        class User:
            id: int
            name: str

        await db.create(User, pk='id')

        # New schema with different fields
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id', replace=True)

        # Should have new column
        assert 'email' in users.sa_table.c


# =============================================================================
# Input/Output Type Behavior Tests
# =============================================================================

class TestInputOutputBehavior:
    """Tests verifying input/output type behavior is unchanged."""

    # Uses the shared db fixture from conftest.py

    @pytest.mark.asyncio
    async def test_regular_class_returns_dicts(self, db):
        """Test that regular class input returns dict rows."""
        class User:
            id: int
            name: str
            status: str = "active"

        users = await db.create(User, pk='id')
        user = await users.insert({"id": 1, "name": "Alice"})

        assert isinstance(user, dict)
        assert user["status"] == "active"

    @pytest.mark.asyncio
    async def test_dataclass_returns_instances(self, db):
        """Test that dataclass input returns dataclass instances."""
        @dataclass
        class User:
            id: Optional[int] = None
            name: str = ""
            status: str = "active"

        users = await db.create(User, pk='id')
        user = await users.insert({"name": "Alice"})

        assert isinstance(user, User)
        assert user.status == "active"

    @pytest.mark.asyncio
    async def test_dataclass_method_switches_output(self, db):
        """Test that .dataclass() switches to dataclass output."""
        class User:
            id: int
            name: str
            status: str = "active"

        users = await db.create(User, pk='id')

        # Before .dataclass() - returns dict
        user1 = await users.insert({"id": 1, "name": "Alice"})
        assert isinstance(user1, dict)

        # Call .dataclass()
        UserDC = users.dataclass()

        # After .dataclass() - returns dataclass instances
        user2 = await users.insert({"id": 2, "name": "Bob"})
        assert isinstance(user2, UserDC)
