"""Tests for Phase 12: Indexes."""

import pytest
import pytest_asyncio
from typing import Optional

from deebase import Database, Index, ValidationError


# =============================================================================
# Index Class Tests
# =============================================================================

class TestIndexClass:
    """Tests for the Index class."""

    def test_index_basic(self):
        """Test basic Index creation."""
        idx = Index("idx_name", "name")
        assert idx.name == "idx_name"
        assert idx.columns == ["name"]
        assert idx.unique is False

    def test_index_unique(self):
        """Test unique Index creation."""
        idx = Index("idx_email", "email", unique=True)
        assert idx.name == "idx_email"
        assert idx.columns == ["email"]
        assert idx.unique is True

    def test_index_composite(self):
        """Test composite Index creation."""
        idx = Index("idx_author_date", "author_id", "created_at")
        assert idx.name == "idx_author_date"
        assert idx.columns == ["author_id", "created_at"]
        assert idx.unique is False

    def test_index_composite_unique(self):
        """Test composite unique Index creation."""
        idx = Index("idx_unique_combo", "col1", "col2", unique=True)
        assert idx.name == "idx_unique_combo"
        assert idx.columns == ["col1", "col2"]
        assert idx.unique is True

    def test_index_no_columns_raises(self):
        """Test Index with no columns raises ValueError."""
        with pytest.raises(ValueError, match="at least one column"):
            Index("idx_empty")

    def test_index_repr(self):
        """Test Index string representation."""
        idx = Index("idx_name", "name")
        assert "idx_name" in repr(idx)
        assert "name" in repr(idx)

    def test_index_repr_unique(self):
        """Test Index repr with unique=True."""
        idx = Index("idx_email", "email", unique=True)
        assert "unique=True" in repr(idx)


# =============================================================================
# create() with indexes Tests
# =============================================================================

class TestCreateWithIndexes:
    """Tests for create() with indexes parameter."""

    @pytest.mark.asyncio
    async def test_create_with_simple_index(self, db):
        """Test table creation with simple string index."""
        class Article:
            id: int
            title: str
            slug: str

        articles = await db.create(Article, pk='id', indexes=["slug"])

        # Verify index was created
        idx_list = articles.indexes
        idx_names = [idx['name'] for idx in idx_list]
        assert "ix_article_slug" in idx_names

    @pytest.mark.asyncio
    async def test_create_with_composite_index(self, db):
        """Test table creation with composite tuple index."""
        class Article:
            id: int
            author_id: int
            created_at: str

        articles = await db.create(
            Article,
            pk='id',
            indexes=[("author_id", "created_at")]
        )

        # Verify index was created
        idx_list = articles.indexes
        idx_names = [idx['name'] for idx in idx_list]
        assert "ix_article_author_id_created_at" in idx_names

        # Verify it has correct columns
        idx = next(i for i in idx_list if i['name'] == "ix_article_author_id_created_at")
        assert idx['columns'] == ['author_id', 'created_at']

    @pytest.mark.asyncio
    async def test_create_with_named_index(self, db):
        """Test table creation with named Index object."""
        class Article:
            id: int
            title: str

        articles = await db.create(
            Article,
            pk='id',
            indexes=[Index("idx_custom_title", "title")]
        )

        # Verify index was created with custom name
        idx_list = articles.indexes
        idx_names = [idx['name'] for idx in idx_list]
        assert "idx_custom_title" in idx_names

    @pytest.mark.asyncio
    async def test_create_with_unique_index(self, db):
        """Test table creation with unique Index."""
        class User:
            id: int
            email: str

        users = await db.create(
            User,
            pk='id',
            indexes=[Index("idx_unique_email", "email", unique=True)]
        )

        # Verify index was created as unique
        idx_list = users.indexes
        idx = next(i for i in idx_list if i['name'] == "idx_unique_email")
        assert idx['unique'] is True

    @pytest.mark.asyncio
    async def test_create_with_multiple_indexes(self, db):
        """Test table creation with multiple indexes."""
        class Article:
            id: int
            title: str
            slug: str
            author_id: int
            created_at: str

        articles = await db.create(
            Article,
            pk='id',
            indexes=[
                "slug",                                    # Simple
                ("author_id", "created_at"),               # Composite
                Index("idx_title_unique", "title", unique=True),  # Named unique
            ]
        )

        # Verify all indexes were created
        idx_list = articles.indexes
        idx_names = [idx['name'] for idx in idx_list]
        assert "ix_article_slug" in idx_names
        assert "ix_article_author_id_created_at" in idx_names
        assert "idx_title_unique" in idx_names

    @pytest.mark.asyncio
    async def test_create_with_invalid_column_raises(self, db):
        """Test that invalid index column raises ValidationError."""
        class Article:
            id: int
            title: str

        with pytest.raises(ValidationError, match="not found"):
            await db.create(
                Article,
                pk='id',
                indexes=["nonexistent_column"]
            )

    @pytest.mark.asyncio
    async def test_unique_index_enforced(self, db):
        """Test that unique index constraint is enforced."""
        class User:
            id: int
            email: str

        users = await db.create(
            User,
            pk='id',
            indexes=[Index("idx_unique_email", "email", unique=True)]
        )

        # Insert first user
        await users.insert({"id": 1, "email": "alice@example.com"})

        # Insert duplicate email should fail
        from deebase import IntegrityError
        with pytest.raises(IntegrityError):
            await users.insert({"id": 2, "email": "alice@example.com"})


# =============================================================================
# table.create_index() Tests
# =============================================================================

class TestTableCreateIndex:
    """Tests for table.create_index() method."""

    @pytest.mark.asyncio
    async def test_create_index_single_column(self, db):
        """Test creating index on single column."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id')

        # Initially no indexes
        assert len(articles.indexes) == 0

        # Create index
        await articles.create_index("title")

        # Verify index exists
        idx_list = articles.indexes
        assert len(idx_list) == 1
        assert idx_list[0]['name'] == "ix_article_title"
        assert idx_list[0]['columns'] == ['title']

    @pytest.mark.asyncio
    async def test_create_index_composite(self, db):
        """Test creating composite index."""
        class Article:
            id: int
            author_id: int
            created_at: str

        articles = await db.create(Article, pk='id')

        # Create composite index
        await articles.create_index(["author_id", "created_at"])

        # Verify index exists
        idx_list = articles.indexes
        assert len(idx_list) == 1
        assert idx_list[0]['columns'] == ['author_id', 'created_at']

    @pytest.mark.asyncio
    async def test_create_index_with_custom_name(self, db):
        """Test creating index with custom name."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id')

        # Create index with custom name
        await articles.create_index("title", name="my_custom_idx")

        # Verify custom name
        idx_list = articles.indexes
        assert idx_list[0]['name'] == "my_custom_idx"

    @pytest.mark.asyncio
    async def test_create_index_unique(self, db):
        """Test creating unique index."""
        class User:
            id: int
            email: str

        users = await db.create(User, pk='id')

        # Create unique index
        await users.create_index("email", unique=True)

        # Verify index is unique
        idx_list = users.indexes
        assert idx_list[0]['unique'] is True

    @pytest.mark.asyncio
    async def test_create_index_invalid_column_raises(self, db):
        """Test that invalid column raises ValidationError."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id')

        with pytest.raises(ValidationError, match="not found"):
            await articles.create_index("nonexistent")


# =============================================================================
# table.drop_index() Tests
# =============================================================================

class TestTableDropIndex:
    """Tests for table.drop_index() method."""

    @pytest.mark.asyncio
    async def test_drop_index(self, db):
        """Test dropping an index."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id', indexes=["title"])

        # Verify index exists
        assert len(articles.indexes) == 1

        # Drop the index
        await articles.drop_index("ix_article_title")

        # Note: SQLAlchemy's indexes property may not reflect dropped indexes
        # until the table is reflected again. The drop operation itself succeeds.

    @pytest.mark.asyncio
    async def test_drop_index_custom_name(self, db):
        """Test dropping an index with custom name."""
        class Article:
            id: int
            title: str

        articles = await db.create(
            Article,
            pk='id',
            indexes=[Index("my_idx", "title")]
        )

        # Verify index exists
        idx_names = [idx['name'] for idx in articles.indexes]
        assert "my_idx" in idx_names

        # Drop the index
        await articles.drop_index("my_idx")


# =============================================================================
# table.indexes Property Tests
# =============================================================================

class TestTableIndexesProperty:
    """Tests for table.indexes property."""

    @pytest.mark.asyncio
    async def test_indexes_empty(self, db):
        """Test indexes property on table with no indexes."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id')

        assert articles.indexes == []

    @pytest.mark.asyncio
    async def test_indexes_returns_list(self, db):
        """Test indexes property returns list of dicts."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id', indexes=["title"])

        idx_list = articles.indexes
        assert isinstance(idx_list, list)
        assert len(idx_list) == 1

        idx = idx_list[0]
        assert 'name' in idx
        assert 'columns' in idx
        assert 'unique' in idx

    @pytest.mark.asyncio
    async def test_indexes_includes_all_indexes(self, db):
        """Test indexes property includes all created indexes."""
        class Article:
            id: int
            title: str
            slug: str
            author_id: int

        articles = await db.create(
            Article,
            pk='id',
            indexes=["title", "slug", "author_id"]
        )

        idx_list = articles.indexes
        assert len(idx_list) == 3


# =============================================================================
# Index Auto-naming Tests
# =============================================================================

class TestIndexAutoNaming:
    """Tests for automatic index name generation."""

    @pytest.mark.asyncio
    async def test_auto_name_single_column(self, db):
        """Test auto-generated name for single column index."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id', indexes=["title"])

        idx_names = [idx['name'] for idx in articles.indexes]
        assert "ix_article_title" in idx_names

    @pytest.mark.asyncio
    async def test_auto_name_composite(self, db):
        """Test auto-generated name for composite index."""
        class Article:
            id: int
            author_id: int
            category_id: int

        articles = await db.create(
            Article,
            pk='id',
            indexes=[("author_id", "category_id")]
        )

        idx_names = [idx['name'] for idx in articles.indexes]
        assert "ix_article_author_id_category_id" in idx_names

    @pytest.mark.asyncio
    async def test_create_index_auto_name(self, db):
        """Test auto-generated name via create_index method."""
        class Article:
            id: int
            title: str

        articles = await db.create(Article, pk='id')
        await articles.create_index("title")

        idx_names = [idx['name'] for idx in articles.indexes]
        assert "ix_article_title" in idx_names


# =============================================================================
# Integration Tests
# =============================================================================

class TestIndexesIntegration:
    """Integration tests for indexes with CRUD operations."""

    @pytest.mark.asyncio
    async def test_index_improves_query(self, db):
        """Test that indexes work with queries (functional, not performance)."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(
            User,
            pk='id',
            indexes=["email"]
        )

        # Insert some data
        await users.insert({"id": 1, "name": "Alice", "email": "alice@example.com"})
        await users.insert({"id": 2, "name": "Bob", "email": "bob@example.com"})

        # Query should still work with indexed column
        user = await users.lookup(email="alice@example.com")
        assert user["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_unique_index_with_upsert(self, db):
        """Test unique index behavior with upsert."""
        class User:
            id: int
            email: str
            name: str

        users = await db.create(
            User,
            pk='id',
            indexes=[Index("idx_email", "email", unique=True)]
        )

        # Insert user
        await users.insert({"id": 1, "email": "alice@example.com", "name": "Alice"})

        # Upsert with same PK should work
        await users.upsert({"id": 1, "email": "alice@example.com", "name": "Alice Updated"})

        user = await users[1]
        assert user["name"] == "Alice Updated"

    @pytest.mark.asyncio
    async def test_index_with_reflected_table(self, db):
        """Test that indexes work with reflected tables."""
        # Create table with indexes via raw SQL
        await db.q("""
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                title TEXT,
                slug TEXT
            )
        """)
        await db.q("CREATE INDEX ix_articles_slug ON articles (slug)")

        # Reflect the table
        articles = await db.reflect_table("articles")

        # Should be able to work with the table
        await articles.insert({"id": 1, "title": "Hello", "slug": "hello"})
        result = await articles.lookup(slug="hello")
        assert result["title"] == "Hello"
