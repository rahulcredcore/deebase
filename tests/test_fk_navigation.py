"""Tests for Phase 11: FK Relationship Navigation."""

import pytest
import pytest_asyncio
from typing import Optional

from deebase import Database, ForeignKey
from deebase.exceptions import ValidationError, SchemaError

pytestmark = pytest.mark.asyncio


# Test classes for FK relationships
class Author:
    id: int
    name: str
    email: str


class Category:
    id: int
    name: str


class Post:
    id: int
    author_id: ForeignKey[int, "author"]
    category_id: ForeignKey[int, "category.id"]
    title: str


class Comment:
    id: int
    post_id: ForeignKey[int, "post"]
    author_id: ForeignKey[int, "author"]
    content: str


class OptionalFKPost:
    id: int
    author_id: Optional[ForeignKey[int, "author"]]
    title: str


@pytest_asyncio.fixture
async def db_with_fk_tables(db):
    """Create database with FK-related tables."""
    # Enable FK enforcement in SQLite
    await db.q("PRAGMA foreign_keys = ON")

    # Create tables in order (parent before child)
    authors = await db.create(Author, pk='id')
    categories = await db.create(Category, pk='id')
    posts = await db.create(Post, pk='id')
    comments = await db.create(Comment, pk='id')

    # Insert sample data
    alice = await authors.insert({"name": "Alice", "email": "alice@example.com"})
    bob = await authors.insert({"name": "Bob", "email": "bob@example.com"})

    tech = await categories.insert({"name": "Technology"})
    life = await categories.insert({"name": "Lifestyle"})

    post1 = await posts.insert({
        "author_id": alice["id"],
        "category_id": tech["id"],
        "title": "Intro to Python"
    })
    post2 = await posts.insert({
        "author_id": alice["id"],
        "category_id": life["id"],
        "title": "Work-Life Balance"
    })
    post3 = await posts.insert({
        "author_id": bob["id"],
        "category_id": tech["id"],
        "title": "Async Programming"
    })

    await comments.insert({
        "post_id": post1["id"],
        "author_id": bob["id"],
        "content": "Great post!"
    })
    await comments.insert({
        "post_id": post1["id"],
        "author_id": alice["id"],
        "content": "Thanks!"
    })

    yield db


# =============================================================================
# Tests for foreign_keys property
# =============================================================================

class TestForeignKeysProperty:
    """Tests for table.foreign_keys property."""

    async def test_foreign_keys_from_create(self, db_with_fk_tables):
        """FK metadata is populated during create()."""
        posts = db_with_fk_tables.t.post
        fks = posts.foreign_keys

        assert len(fks) == 2
        assert any(fk['column'] == 'author_id' and fk['references'] == 'author.id' for fk in fks)
        assert any(fk['column'] == 'category_id' and fk['references'] == 'category.id' for fk in fks)

    async def test_foreign_keys_single_fk(self, db_with_fk_tables):
        """Table with single FK has correct metadata."""
        comments = db_with_fk_tables.t.comment
        fks = comments.foreign_keys

        assert len(fks) == 2  # post_id and author_id
        assert any(fk['column'] == 'post_id' for fk in fks)
        assert any(fk['column'] == 'author_id' for fk in fks)

    async def test_foreign_keys_no_fk(self, db_with_fk_tables):
        """Table without FKs has empty foreign_keys list."""
        authors = db_with_fk_tables.t.author
        fks = authors.foreign_keys

        assert fks == []

    async def test_foreign_keys_returns_copy(self, db_with_fk_tables):
        """foreign_keys returns a copy, not the internal list."""
        posts = db_with_fk_tables.t.post
        fks1 = posts.foreign_keys
        fks2 = posts.foreign_keys

        assert fks1 is not fks2
        assert fks1 == fks2


# =============================================================================
# Tests for fk accessor (convenience API)
# =============================================================================

class TestFKAccessor:
    """Tests for table.fk accessor (convenience API)."""

    async def test_fk_accessor_basic(self, db_with_fk_tables):
        """fk accessor navigates to parent."""
        posts = db_with_fk_tables.t.post

        post = await posts[1]
        author = await posts.fk.author_id(post)

        assert author is not None
        assert author['name'] == 'Alice'

    async def test_fk_accessor_different_fk(self, db_with_fk_tables):
        """fk accessor works with different FK columns."""
        posts = db_with_fk_tables.t.post

        post = await posts[1]
        category = await posts.fk.category_id(post)

        assert category is not None
        assert category['name'] == 'Technology'

    async def test_fk_accessor_returns_awaitable(self, db_with_fk_tables):
        """fk accessor returns an awaitable."""
        posts = db_with_fk_tables.t.post
        post = await posts[1]

        # The result of fk.column_name(record) should be awaitable
        coro = posts.fk.author_id(post)
        assert hasattr(coro, '__await__') or hasattr(coro, '__anext__')

        author = await coro
        assert author['name'] == 'Alice'


# =============================================================================
# Tests for get_parent() method (power user API)
# =============================================================================

class TestGetParent:
    """Tests for table.get_parent() method (power user API)."""

    async def test_get_parent_basic(self, db_with_fk_tables):
        """get_parent fetches parent record."""
        posts = db_with_fk_tables.t.post

        post = await posts[1]
        author = await posts.get_parent(post, "author_id")

        assert author is not None
        assert author['name'] == 'Alice'
        assert author['email'] == 'alice@example.com'

    async def test_get_parent_different_column(self, db_with_fk_tables):
        """get_parent works with different FK columns."""
        posts = db_with_fk_tables.t.post

        post = await posts[1]
        category = await posts.get_parent(post, "category_id")

        assert category is not None
        assert category['name'] == 'Technology'

    async def test_get_parent_null_fk_returns_none(self, db):
        """get_parent returns None for NULL FK value."""
        await db.q("PRAGMA foreign_keys = ON")

        # Create tables
        await db.create(Author, pk='id')

        class NullableFKPost:
            id: int
            author_id: Optional[int]
            title: str

        posts = await db.create(NullableFKPost, pk='id')

        # Manually add FK metadata since Optional doesn't trigger ForeignKey
        posts._foreign_keys = [{'column': 'author_id', 'references': 'author.id'}]

        # Insert post with NULL author_id
        post = await posts.insert({"author_id": None, "title": "Anonymous"})

        author = await posts.get_parent(post, "author_id")
        assert author is None

    async def test_get_parent_dangling_fk_returns_none(self, db):
        """get_parent returns None for dangling FK (parent deleted)."""
        # Don't enable FK enforcement so we can delete parent
        # Create all referenced tables first
        await db.create(Author, pk='id')
        await db.create(Category, pk='id')
        posts = await db.create(Post, pk='id')

        # Insert author, category, create post, then delete author (FK not enforced)
        await db.t.author.insert({"name": "Ghost", "email": "ghost@example.com"})
        await db.t.category.insert({"name": "Test"})
        post = await posts.insert({"author_id": 1, "category_id": 1, "title": "Orphan"})

        # Delete the author (creates dangling FK - works because FK not enforced)
        await db.t.author.delete(1)

        # get_parent should return None, not raise
        author = await posts.get_parent(post, "author_id")
        assert author is None

    async def test_get_parent_invalid_column_raises(self, db_with_fk_tables):
        """get_parent raises ValidationError for non-existent column."""
        posts = db_with_fk_tables.t.post
        post = await posts[1]

        with pytest.raises(ValidationError) as exc_info:
            await posts.get_parent(post, "nonexistent_column")

        assert "nonexistent_column" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    async def test_get_parent_non_fk_column_raises(self, db_with_fk_tables):
        """get_parent raises ValidationError for non-FK column."""
        posts = db_with_fk_tables.t.post
        post = await posts[1]

        with pytest.raises(ValidationError) as exc_info:
            await posts.get_parent(post, "title")

        assert "title" in str(exc_info.value)
        assert "not a foreign key" in str(exc_info.value)

    async def test_get_parent_referenced_table_not_cached_raises(self, db):
        """get_parent raises SchemaError if referenced table not in cache."""
        # Create all tables first (required by SQLAlchemy for FK references)
        await db.create(Author, pk='id')
        await db.create(Category, pk='id')
        posts = await db.create(Post, pk='id')

        # Remove author from cache to simulate "not cached" scenario
        del db._tables['author']

        # Now 'author' table doesn't exist in cache but FK metadata still points to it
        with pytest.raises(SchemaError) as exc_info:
            await posts.get_parent({"id": 1, "author_id": 1, "title": "Test", "category_id": 1}, "author_id")

        assert "author" in str(exc_info.value)
        assert "not found in cache" in str(exc_info.value)


# =============================================================================
# Tests for get_children() method (power user API)
# =============================================================================

class TestGetChildren:
    """Tests for table.get_children() method (power user API)."""

    async def test_get_children_basic(self, db_with_fk_tables):
        """get_children fetches child records."""
        authors = db_with_fk_tables.t.author

        alice = await authors.lookup(name="Alice")
        alice_posts = await authors.get_children(alice, "post", "author_id")

        assert len(alice_posts) == 2
        titles = [p['title'] for p in alice_posts]
        assert "Intro to Python" in titles
        assert "Work-Life Balance" in titles

    async def test_get_children_with_table_object(self, db_with_fk_tables):
        """get_children accepts Table object instead of string."""
        authors = db_with_fk_tables.t.author
        posts = db_with_fk_tables.t.post

        alice = await authors.lookup(name="Alice")
        alice_posts = await authors.get_children(alice, posts, "author_id")

        assert len(alice_posts) == 2

    async def test_get_children_returns_empty_list(self, db_with_fk_tables):
        """get_children returns empty list when no children exist."""
        categories = db_with_fk_tables.t.category

        # Insert a new category with no posts
        empty_cat = await categories.insert({"name": "Empty Category"})

        posts = await categories.get_children(empty_cat, "post", "category_id")
        assert posts == []

    async def test_get_children_different_fk_columns(self, db_with_fk_tables):
        """get_children works with different FK columns."""
        posts = db_with_fk_tables.t.post

        post1 = await posts[1]
        comments = await posts.get_children(post1, "comment", "post_id")

        assert len(comments) == 2

    async def test_get_children_child_table_not_cached_raises(self, db_with_fk_tables):
        """get_children raises SchemaError if child table not in cache."""
        authors = db_with_fk_tables.t.author
        alice = await authors.lookup(name="Alice")

        with pytest.raises(SchemaError) as exc_info:
            await authors.get_children(alice, "nonexistent_table", "author_id")

        assert "nonexistent_table" in str(exc_info.value)
        assert "not found in cache" in str(exc_info.value)

    async def test_get_children_invalid_fk_column_raises(self, db_with_fk_tables):
        """get_children raises ValidationError if FK column doesn't exist in child."""
        authors = db_with_fk_tables.t.author
        alice = await authors.lookup(name="Alice")

        with pytest.raises(ValidationError) as exc_info:
            await authors.get_children(alice, "post", "nonexistent_column")

        assert "nonexistent_column" in str(exc_info.value)
        assert "not found" in str(exc_info.value)


# =============================================================================
# Tests for dataclass integration
# =============================================================================

class TestDataclassIntegration:
    """Tests for FK navigation with dataclass support."""

    async def test_get_parent_respects_dataclass_setting(self, db_with_fk_tables):
        """get_parent returns dataclass if target table uses dataclass."""
        authors = db_with_fk_tables.t.author
        posts = db_with_fk_tables.t.post

        # Enable dataclass on authors
        AuthorDC = authors.dataclass()

        post = await posts[1]
        author = await posts.get_parent(post, "author_id")

        # Should be a dataclass instance
        assert hasattr(author, 'name')
        assert author.name == 'Alice'

    async def test_get_children_respects_dataclass_setting(self, db_with_fk_tables):
        """get_children returns dataclasses if child table uses dataclass."""
        authors = db_with_fk_tables.t.author
        posts = db_with_fk_tables.t.post

        # Enable dataclass on posts
        PostDC = posts.dataclass()

        alice = await authors.lookup(name="Alice")
        alice_posts = await authors.get_children(alice, posts, "author_id")

        assert len(alice_posts) == 2
        for post in alice_posts:
            assert hasattr(post, 'title')


# =============================================================================
# Tests for FK metadata from reflection
# =============================================================================

class TestFKReflection:
    """Tests for FK metadata extraction during reflection."""

    async def test_reflect_table_extracts_fk_metadata(self, db):
        """reflect_table extracts FK metadata from database."""
        # Create tables with raw SQL
        await db.q("""
            CREATE TABLE parent_table (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        await db.q("""
            CREATE TABLE child_table (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER REFERENCES parent_table(id),
                value TEXT
            )
        """)

        # Reflect
        await db.reflect_table("parent_table")
        child = await db.reflect_table("child_table")

        # Check FK metadata was extracted
        fks = child.foreign_keys
        assert len(fks) == 1
        assert fks[0]['column'] == 'parent_id'
        assert 'parent_table' in fks[0]['references']

    async def test_reflect_extracts_fk_metadata(self, db):
        """db.reflect() extracts FK metadata for all tables."""
        # Create tables with raw SQL
        await db.q("""
            CREATE TABLE users_raw (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        await db.q("""
            CREATE TABLE orders_raw (
                id INTEGER PRIMARY KEY,
                user_id INTEGER REFERENCES users_raw(id),
                total REAL
            )
        """)

        # Reflect all
        await db.reflect()

        orders = db.t.orders_raw
        fks = orders.foreign_keys

        assert len(fks) == 1
        assert fks[0]['column'] == 'user_id'


# =============================================================================
# Tests for xtra() with FK navigation
# =============================================================================

class TestXtraWithFK:
    """Tests for FK navigation with xtra() filtered tables."""

    async def test_xtra_preserves_fk_metadata(self, db_with_fk_tables):
        """xtra() preserves FK metadata on filtered table."""
        posts = db_with_fk_tables.t.post

        # Apply xtra filter
        alice_posts = posts.xtra(author_id=1)

        # FK metadata should be preserved
        assert alice_posts.foreign_keys == posts.foreign_keys

    async def test_fk_navigation_on_xtra_filtered_table(self, db_with_fk_tables):
        """FK navigation works on xtra-filtered tables."""
        posts = db_with_fk_tables.t.post

        # Apply xtra filter
        alice_posts = posts.xtra(author_id=1)

        # Get a post from filtered table
        post = await alice_posts(limit=1)
        post = post[0]

        # Navigate to parent
        author = await alice_posts.get_parent(post, "author_id")
        assert author['name'] == 'Alice'
