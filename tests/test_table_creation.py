"""Tests for table creation (Phase 2)."""

import pytest
from typing import Optional
from datetime import datetime
from deebase import Database, Text, ValidationError, SchemaError


class TestTableCreation:
    """Tests for db.create() method."""

    @pytest.mark.asyncio
    async def test_create_simple_table(self, db):
        """Test creating a simple table with basic types."""
        class User:
            id: int
            name: str
            age: int

        users = await db.create(User, pk='id')

        assert users is not None
        assert users._name == 'user'
        assert users._dataclass_cls == User

    @pytest.mark.asyncio
    async def test_create_table_with_text_type(self, db):
        """Test creating table with Text type for unlimited text."""
        class Article:
            id: int
            title: str
            content: Text

        articles = await db.create(Article, pk='id')

        # Verify Text column was created
        content_col = articles.sa_table.c['content']
        assert content_col is not None

    @pytest.mark.asyncio
    async def test_create_table_with_json_type(self, db):
        """Test creating table with dict type for JSON columns."""
        class Post:
            id: int
            title: str
            metadata: dict

        posts = await db.create(Post, pk='id')

        # Verify JSON column was created
        metadata_col = posts.sa_table.c['metadata']
        assert metadata_col is not None

    @pytest.mark.asyncio
    async def test_create_table_with_datetime(self, db):
        """Test creating table with datetime columns."""
        class Event:
            id: int
            name: str
            created_at: datetime

        events = await db.create(Event, pk='id')

        # Verify datetime column exists
        created_col = events.sa_table.c['created_at']
        assert created_col is not None

    @pytest.mark.asyncio
    async def test_create_table_with_optional_fields(self, db):
        """Test that Optional fields become nullable columns."""
        class User:
            id: int
            name: str
            email: Optional[str]
            bio: Optional[Text]

        users = await db.create(User, pk='id')

        # Check nullable properties
        assert users.sa_table.c['id'].nullable is False  # PK not nullable
        assert users.sa_table.c['name'].nullable is False  # Required
        assert users.sa_table.c['email'].nullable is True  # Optional
        assert users.sa_table.c['bio'].nullable is True  # Optional

    @pytest.mark.asyncio
    async def test_create_table_default_pk(self, db):
        """Test creating table with default primary key ('id')."""
        class Product:
            id: int
            name: str
            price: float

        products = await db.create(Product)  # No pk specified

        # Verify 'id' is the primary key
        assert products.sa_table.c['id'].primary_key is True

    @pytest.mark.asyncio
    async def test_create_table_custom_pk(self, db):
        """Test creating table with custom primary key."""
        class Item:
            item_id: int
            name: str

        items = await db.create(Item, pk='item_id')

        # Verify custom PK
        assert items.sa_table.c['item_id'].primary_key is True

    @pytest.mark.asyncio
    async def test_create_table_composite_pk(self, db):
        """Test creating table with composite primary key."""
        class OrderItem:
            order_id: int
            product_id: int
            quantity: int

        order_items = await db.create(OrderItem, pk=['order_id', 'product_id'])

        # Verify composite PK
        assert order_items.sa_table.c['order_id'].primary_key is True
        assert order_items.sa_table.c['product_id'].primary_key is True
        assert order_items.sa_table.c['quantity'].primary_key is False

    @pytest.mark.asyncio
    async def test_create_table_no_annotations(self, db):
        """Test that creating table without annotations raises error."""
        class Empty:
            pass

        with pytest.raises(ValidationError, match="has no type annotations"):
            await db.create(Empty)

    @pytest.mark.asyncio
    async def test_create_table_invalid_pk(self, db):
        """Test that specifying non-existent PK raises error."""
        class User:
            id: int
            name: str

        with pytest.raises(SchemaError, match="Primary key column 'user_id' not found"):
            await db.create(User, pk='user_id')

    @pytest.mark.asyncio
    async def test_table_actually_created_in_db(self, db):
        """Test that table is actually created in the database."""
        class TestTable:
            id: int
            value: str

        await db.create(TestTable, pk='id')

        # Verify table exists by querying sqlite_master
        result = await db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='testtable'"
        )
        assert len(result) == 1
        assert result[0]['name'] == 'testtable'


class TestTableSchema:
    """Tests for Table.schema property."""

    @pytest.mark.asyncio
    async def test_schema_property(self, db):
        """Test that schema property returns CREATE TABLE SQL."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        schema = users.schema

        assert 'CREATE TABLE' in schema
        assert 'user' in schema.lower()
        assert 'id' in schema.lower()
        assert 'name' in schema.lower()

    @pytest.mark.asyncio
    async def test_schema_shows_types(self, db):
        """Test that schema shows column types."""
        class Product:
            id: int
            name: str
            price: float

        products = await db.create(Product, pk='id')
        schema = products.schema.upper()

        # Check for types (SQLite specific)
        assert 'INTEGER' in schema
        assert any(t in schema for t in ['VARCHAR', 'TEXT'])
        assert any(t in schema for t in ['FLOAT', 'REAL'])


class TestTableDrop:
    """Tests for Table.drop() method."""

    @pytest.mark.asyncio
    async def test_drop_table(self, db):
        """Test dropping a table."""
        class TempTable:
            id: int
            value: str

        temp = await db.create(TempTable, pk='id')

        # Verify table exists
        result = await db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='temptable'"
        )
        assert len(result) == 1

        # Drop table
        await temp.drop()

        # Verify table no longer exists
        result = await db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='temptable'"
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_drop_nonexistent_table_raises_error(self, db):
        """Test that dropping non-existent table raises error."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.drop()

        # Try to drop again
        with pytest.raises(Exception):  # SQLAlchemy will raise an error
            await users.drop()


class TestTableCaching:
    """Tests for table caching in Database."""

    @pytest.mark.asyncio
    async def test_table_cached_after_creation(self, db):
        """Test that created tables are cached."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Check that table is in cache
        cached_table = db._get_table('user')
        assert cached_table is users
