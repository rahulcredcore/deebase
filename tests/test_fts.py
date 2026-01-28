"""Tests for Phase 18: Full-Text Search (BM25) with SQLite FTS5."""

import pytest
import pytest_asyncio

from deebase import Database, FTSIndex, Text, NotFoundError
from deebase.fts import (
    FTSIndex as FTSIndexCls,
    _fts_table_name,
    generate_sqlite_fts_sql,
    generate_sqlite_fts_drop_sql,
    generate_sqlite_search_sql,
    generate_pg_fts_create_sql,
    generate_pg_fts_drop_sql,
    generate_pg_search_sql,
)
from deebase.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """Create an in-memory SQLite database."""
    database = Database("sqlite+aiosqlite:///:memory:")
    yield database
    await database.close()


@pytest_asyncio.fixture
async def articles_table(db):
    """Create an articles table with sample data."""
    class Article:
        id: int
        title: str
        content: Text
        author_id: int

    table = await db.create(Article, pk="id")
    # Insert sample data
    await table.insert({"title": "Getting Started with Python", "content": "Python is a great programming language for beginners.", "author_id": 1})
    await table.insert({"title": "Advanced SQLAlchemy", "content": "SQLAlchemy provides powerful ORM and Core APIs.", "author_id": 1})
    await table.insert({"title": "Async Programming Guide", "content": "Learn about async and await in modern Python applications.", "author_id": 2})
    await table.insert({"title": "Database Design Patterns", "content": "Good database design is essential for scalable applications.", "author_id": 2})
    await table.insert({"title": "Full-Text Search Explained", "content": "BM25 is a ranking function used in full-text search engines.", "author_id": 1})
    return table


# ---------------------------------------------------------------------------
# FTSIndex class tests
# ---------------------------------------------------------------------------

class TestFTSIndexClass:
    def test_single_column(self):
        idx = FTSIndex("title")
        assert idx.columns == ["title"]
        assert idx.name is None
        assert idx.language == "english"

    def test_multi_column(self):
        idx = FTSIndex("title", "content")
        assert idx.columns == ["title", "content"]

    def test_with_name(self):
        idx = FTSIndex("title", name="title_fts")
        assert idx.name == "title_fts"

    def test_with_language(self):
        idx = FTSIndex("title", language="french")
        assert idx.language == "french"

    def test_no_columns_raises(self):
        with pytest.raises(ValueError, match="at least one column"):
            FTSIndex()

    def test_repr(self):
        idx = FTSIndex("title", "content", name="my_fts")
        r = repr(idx)
        assert "FTSIndex" in r
        assert "title" in r
        assert "content" in r
        assert "my_fts" in r


# ---------------------------------------------------------------------------
# SQL generation tests (unit)
# ---------------------------------------------------------------------------

class TestSQLiteGeneration:
    def test_fts_table_name_default(self):
        assert _fts_table_name("article") == "article_fts"

    def test_fts_table_name_custom(self):
        assert _fts_table_name("article", "my_idx") == "my_idx"

    def test_create_sql_count(self):
        stmts = generate_sqlite_fts_sql("article", ["title", "content"], "id")
        # 1 CREATE VIRTUAL TABLE + 3 triggers + 1 populate
        assert len(stmts) == 5

    def test_create_sql_virtual_table(self):
        stmts = generate_sqlite_fts_sql("article", ["title"], "id")
        assert "CREATE VIRTUAL TABLE" in stmts[0]
        assert "fts5" in stmts[0]
        assert "content='article'" in stmts[0]

    def test_create_sql_triggers(self):
        stmts = generate_sqlite_fts_sql("article", ["title"], "id")
        assert "AFTER INSERT" in stmts[1]
        assert "AFTER DELETE" in stmts[2]
        assert "AFTER UPDATE" in stmts[3]

    def test_create_sql_populate(self):
        stmts = generate_sqlite_fts_sql("article", ["title", "content"], "id")
        assert stmts[4].startswith("INSERT INTO article_fts")
        assert "SELECT id, title, content FROM article" in stmts[4]

    def test_drop_sql(self):
        stmts = generate_sqlite_fts_drop_sql("article")
        assert len(stmts) == 4  # 3 triggers + 1 table
        assert any("DROP TRIGGER" in s for s in stmts)
        assert any("DROP TABLE" in s for s in stmts)

    def test_search_sql_basic(self):
        sql, params = generate_sqlite_search_sql(
            "article", "article_fts", "id", "python"
        )
        assert "MATCH" in sql
        assert '"python"' in params["query"]

    def test_search_sql_with_columns(self):
        sql, params = generate_sqlite_search_sql(
            "article", "article_fts", "id", "python", columns=["title"]
        )
        assert "{title}" in params["query"]
        assert '"python"' in params["query"]

    def test_search_sql_with_score(self):
        sql, _ = generate_sqlite_search_sql(
            "article", "article_fts", "id", "python", score=True
        )
        assert "_score" in sql
        assert "bm25" in sql

    def test_search_sql_with_limit(self):
        sql, _ = generate_sqlite_search_sql(
            "article", "article_fts", "id", "python", limit=5
        )
        assert "LIMIT 5" in sql


class TestPostgresGeneration:
    def test_create_sql_single_column(self):
        stmts = generate_pg_fts_create_sql("article", ["title"])
        assert len(stmts) == 2
        assert "CREATE EXTENSION" in stmts[0]
        assert "USING bm25 (title)" in stmts[1]
        assert "text_config='english'" in stmts[1]

    def test_create_sql_multi_column(self):
        stmts = generate_pg_fts_create_sql("article", ["title", "content"])
        # 1 extension + 2 indexes (one per column)
        assert len(stmts) == 3
        assert "USING bm25 (title)" in stmts[1]
        assert "USING bm25 (content)" in stmts[2]

    def test_create_sql_custom_language(self):
        stmts = generate_pg_fts_create_sql("article", ["title"], language="french")
        assert "text_config='french'" in stmts[1]

    def test_drop_sql_single(self):
        stmts = generate_pg_fts_drop_sql("article", ["title"])
        assert len(stmts) == 1
        assert "DROP INDEX IF EXISTS article_fts" in stmts[0]

    def test_drop_sql_multi(self):
        stmts = generate_pg_fts_drop_sql("article", ["title", "content"])
        assert len(stmts) == 2
        assert "article_fts_title" in stmts[0]
        assert "article_fts_content" in stmts[1]

    def test_search_sql(self):
        sql, params = generate_pg_search_sql(
            "article", ["title", "content"], "python"
        )
        assert "<@>" in sql
        assert "to_bm25query" in sql
        assert params["query"] == "python"

    def test_search_sql_with_score(self):
        sql, _ = generate_pg_search_sql(
            "article", ["title"], "python", score=True
        )
        assert "_score" in sql
        assert "<@>" in sql

    def test_search_sql_single_column(self):
        sql, _ = generate_pg_search_sql(
            "article", ["title"], "python", index_name="article_fts"
        )
        assert "article_fts" in sql


# ---------------------------------------------------------------------------
# Integration tests — SQLite FTS5
# ---------------------------------------------------------------------------

class TestCreateFTSIndex:
    @pytest.mark.asyncio
    async def test_create_fts_index_basic(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        assert len(articles_table.fts_indexes) == 1
        assert articles_table.fts_indexes[0]["name"] == "article_fts"
        assert articles_table.fts_indexes[0]["columns"] == ["title", "content"]

    @pytest.mark.asyncio
    async def test_create_fts_index_single_column(self, articles_table):
        await articles_table.create_fts_index("title", name="title_fts")
        assert articles_table.fts_indexes[0]["name"] == "title_fts"

    @pytest.mark.asyncio
    async def test_create_fts_index_custom_name(self, articles_table):
        await articles_table.create_fts_index(["title"], name="my_custom_fts")
        assert articles_table.fts_indexes[0]["name"] == "my_custom_fts"

    @pytest.mark.asyncio
    async def test_create_fts_index_invalid_column(self, articles_table):
        with pytest.raises(ValidationError, match="not found"):
            await articles_table.create_fts_index(["nonexistent"])

    @pytest.mark.asyncio
    async def test_create_multiple_fts_indexes(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        await articles_table.create_fts_index("title", name="title_only_fts")
        assert len(articles_table.fts_indexes) == 2


class TestDropFTSIndex:
    @pytest.mark.asyncio
    async def test_drop_fts_index(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        assert len(articles_table.fts_indexes) == 1
        await articles_table.drop_fts_index()
        assert len(articles_table.fts_indexes) == 0

    @pytest.mark.asyncio
    async def test_drop_fts_index_by_name(self, articles_table):
        await articles_table.create_fts_index("title", name="title_fts")
        await articles_table.create_fts_index(["title", "content"])
        assert len(articles_table.fts_indexes) == 2
        await articles_table.drop_fts_index("title_fts")
        assert len(articles_table.fts_indexes) == 1
        assert articles_table.fts_indexes[0]["name"] == "article_fts"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_basic(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        results = await articles_table.search("python")
        assert len(results) >= 2
        titles = [r["title"] for r in results]
        assert "Getting Started with Python" in titles

    @pytest.mark.asyncio
    async def test_search_with_limit(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        results = await articles_table.search("python", limit=1)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_with_score(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        results = await articles_table.search("python", score=True)
        assert len(results) >= 1
        # Each result is (record, score) tuple
        record, score = results[0]
        assert isinstance(record, dict)
        assert isinstance(score, float)
        assert score < 0  # BM25 scores are negative

    @pytest.mark.asyncio
    async def test_search_column_filter(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        results = await articles_table.search("python", columns=["title"])
        # Should find "Getting Started with Python" via title
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_no_results(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        results = await articles_table.search("xyznonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_no_fts_index_raises(self, articles_table):
        with pytest.raises(ValidationError, match="No FTS index"):
            await articles_table.search("python")

    @pytest.mark.asyncio
    async def test_search_invalid_columns_raises(self, articles_table):
        await articles_table.create_fts_index("title", name="title_fts")
        with pytest.raises(ValidationError, match="No FTS index covers"):
            await articles_table.search("python", columns=["content"])

    @pytest.mark.asyncio
    async def test_search_ordered_by_relevance(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        results = await articles_table.search("full-text search", score=True)
        if len(results) >= 2:
            # Scores should be in ascending order (more negative = more relevant = first)
            scores = [s for _, s in results]
            assert scores == sorted(scores)


class TestSearchWithXtra:
    @pytest.mark.asyncio
    async def test_search_respects_xtra_filter(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        # Filter to author_id=1 only
        filtered = articles_table.xtra(author_id=1)
        # xtra creates a new Table without _fts_indexes; copy them
        filtered._fts_indexes = articles_table._fts_indexes

        results = await filtered.search("python")
        for r in results:
            assert r["author_id"] == 1


class TestSearchWithDataclass:
    @pytest.mark.asyncio
    async def test_search_returns_dataclass(self, db):
        from dataclasses import dataclass

        @dataclass
        class Article:
            id: int
            title: str
            content: str

        table = await db.create(Article, pk="id")
        await table.insert(Article(id=None, title="Python Guide", content="Learn Python"))
        await table.create_fts_index(["title", "content"])

        results = await table.search("python")
        assert len(results) >= 1
        assert hasattr(results[0], "title")  # dataclass attribute access

    @pytest.mark.asyncio
    async def test_search_score_returns_dataclass(self, db):
        from dataclasses import dataclass

        @dataclass
        class Article:
            id: int
            title: str
            content: str

        table = await db.create(Article, pk="id")
        await table.insert(Article(id=None, title="Python Guide", content="Learn Python"))
        await table.create_fts_index(["title", "content"])

        results = await table.search("python", score=True)
        assert len(results) >= 1
        record, score = results[0]
        assert hasattr(record, "title")
        assert isinstance(score, float)


class TestFTSSync:
    """Test that FTS stays in sync via triggers."""

    @pytest.mark.asyncio
    async def test_insert_syncs_to_fts(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        # Insert a new record after FTS index creation
        await articles_table.insert({
            "title": "Rust Programming",
            "content": "Rust is a systems programming language.",
            "author_id": 3,
        })
        results = await articles_table.search("rust")
        assert len(results) == 1
        assert results[0]["title"] == "Rust Programming"

    @pytest.mark.asyncio
    async def test_update_syncs_to_fts(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        # Update title
        record = await articles_table[1]
        record["title"] = "Getting Started with Rust"
        await articles_table.update(record)

        # Old term should not match this record via title
        results = await articles_table.search("python", columns=["title"])
        titles = [r["title"] for r in results]
        assert "Getting Started with Rust" not in titles

        # New term should match
        results = await articles_table.search("rust")
        titles = [r["title"] for r in results]
        assert "Getting Started with Rust" in titles

    @pytest.mark.asyncio
    async def test_delete_syncs_to_fts(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        # Verify initial search finds the record
        results = await articles_table.search("full-text search")
        assert any(r["title"] == "Full-Text Search Explained" for r in results)

        # Delete the record
        await articles_table.delete(5)

        # Search should no longer find it
        results = await articles_table.search("full-text search engines")
        assert not any(r.get("title") == "Full-Text Search Explained" for r in results)


class TestFTSViaDbCreate:
    """Test creating FTS indexes via db.create() indexes parameter."""

    @pytest.mark.asyncio
    async def test_fts_index_in_create(self, db):
        class Post:
            id: int
            title: str
            body: Text

        table = await db.create(Post, pk="id", indexes=[
            FTSIndex("title", "body"),
        ])

        await table.insert({"title": "Hello World", "body": "This is my first post."})
        results = await table.search("hello")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fts_and_regular_indexes_together(self, db):
        from deebase import Index

        class Post:
            id: int
            title: str
            body: Text
            slug: str

        table = await db.create(Post, pk="id", indexes=[
            "slug",  # Regular B-tree index
            FTSIndex("title", "body"),  # FTS index
        ])

        assert len(table.indexes) >= 1  # Regular index
        assert len(table.fts_indexes) == 1  # FTS index

    @pytest.mark.asyncio
    async def test_fts_index_with_name_in_create(self, db):
        class Post:
            id: int
            title: str

        table = await db.create(Post, pk="id", indexes=[
            FTSIndex("title", name="post_title_fts"),
        ])

        assert table.fts_indexes[0]["name"] == "post_title_fts"


class TestFTSIntrospection:
    @pytest.mark.asyncio
    async def test_fts_indexes_empty(self, articles_table):
        assert articles_table.fts_indexes == []

    @pytest.mark.asyncio
    async def test_fts_indexes_after_create(self, articles_table):
        await articles_table.create_fts_index(["title", "content"], language="english")
        idxs = articles_table.fts_indexes
        assert len(idxs) == 1
        assert idxs[0]["columns"] == ["title", "content"]
        assert idxs[0]["language"] == "english"

    @pytest.mark.asyncio
    async def test_fts_indexes_returns_copy(self, articles_table):
        await articles_table.create_fts_index(["title"])
        idxs1 = articles_table.fts_indexes
        idxs2 = articles_table.fts_indexes
        assert idxs1 is not idxs2  # Different list objects


class TestFTSEdgeCases:
    @pytest.mark.asyncio
    async def test_search_empty_table(self, db):
        class Empty:
            id: int
            title: str

        table = await db.create(Empty, pk="id")
        await table.create_fts_index(["title"])
        results = await table.search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_special_characters(self, articles_table):
        await articles_table.create_fts_index(["title", "content"])
        # FTS5 handles special chars gracefully
        results = await articles_table.search("python's")
        # Should not raise, may or may not find results
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_fts_no_pk_table_raises(self, db):
        """FTS requires a primary key."""
        # Create table via raw SQL without PK, then reflect
        await db.q("CREATE TABLE nopk (name TEXT, value TEXT)")
        table = await db.reflect_table("nopk")
        with pytest.raises(ValidationError, match="primary key"):
            await table.create_fts_index(["name"])

    @pytest.mark.asyncio
    async def test_multiple_searches(self, articles_table):
        """Multiple searches should all work."""
        await articles_table.create_fts_index(["title", "content"])
        r1 = await articles_table.search("python")
        r2 = await articles_table.search("database")
        r3 = await articles_table.search("async")
        assert len(r1) >= 1
        assert len(r2) >= 1
        assert len(r3) >= 1
