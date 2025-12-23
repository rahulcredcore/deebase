"""Tests for Database class."""

import pytest
from deebase import Database


class TestDatabaseInit:
    """Tests for Database initialization."""

    @pytest.mark.asyncio
    async def test_database_creation(self):
        """Test creating a Database instance."""
        db = Database("sqlite+aiosqlite:///:memory:")
        assert db is not None
        assert db.engine is not None
        await db.close()

    @pytest.mark.asyncio
    async def test_database_context_manager(self):
        """Test Database as async context manager."""
        async with Database("sqlite+aiosqlite:///:memory:") as db:
            assert db is not None
            result = await db.q("SELECT 1 as num")
            assert result == [{"num": 1}]


class TestDatabaseQuery:
    """Tests for Database.q() method."""

    @pytest.mark.asyncio
    async def test_simple_select(self, db):
        """Test executing a simple SELECT query."""
        result = await db.q("SELECT 1 as num")
        assert result == [{"num": 1}]

    @pytest.mark.asyncio
    async def test_multiple_columns(self, db):
        """Test query returning multiple columns."""
        result = await db.q("SELECT 1 as a, 2 as b, 'test' as c")
        assert result == [{"a": 1, "b": 2, "c": "test"}]

    @pytest.mark.asyncio
    async def test_multiple_rows(self, db_with_sample_table):
        """Test query returning multiple rows."""
        result = await db_with_sample_table.q("SELECT name FROM users ORDER BY name")
        assert len(result) == 3
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"
        assert result[2]["name"] == "Charlie"

    @pytest.mark.asyncio
    async def test_empty_result(self, db_with_sample_table):
        """Test query returning no rows."""
        result = await db_with_sample_table.q("SELECT * FROM users WHERE name = 'NonExistent'")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_with_where_clause(self, db_with_sample_table):
        """Test query with WHERE clause."""
        result = await db_with_sample_table.q("SELECT name, age FROM users WHERE age > 25 ORDER BY age")
        assert len(result) == 2
        assert result[0] == {"name": "Alice", "age": 30}
        assert result[1] == {"name": "Charlie", "age": 35}

    @pytest.mark.asyncio
    async def test_query_all_columns(self, db_with_sample_table):
        """Test query selecting all columns."""
        result = await db_with_sample_table.q("SELECT * FROM users WHERE name = 'Alice'")
        assert len(result) == 1
        assert result[0]["name"] == "Alice"
        assert result[0]["email"] == "alice@example.com"
        assert result[0]["age"] == 30
        assert "id" in result[0]


class TestDatabaseTableCreation:
    """Tests for creating tables with raw SQL."""

    @pytest.mark.asyncio
    async def test_create_table(self, db):
        """Test creating a table with q()."""
        await db.q("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """)

        # Verify table was created by querying it
        result = await db.q("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        assert len(result) == 1
        assert result[0]["name"] == "test_table"

    @pytest.mark.asyncio
    async def test_insert_and_query(self, db):
        """Test inserting data and querying it."""
        # Create table
        await db.q("""
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL
            )
        """)

        # Insert data
        await db.q("INSERT INTO items (name, price) VALUES ('Widget', 9.99)")
        await db.q("INSERT INTO items (name, price) VALUES ('Gadget', 19.99)")

        # Query data
        result = await db.q("SELECT name, price FROM items ORDER BY price")
        assert len(result) == 2
        assert result[0] == {"name": "Widget", "price": 9.99}
        assert result[1] == {"name": "Gadget", "price": 19.99}


class TestDatabaseAccessors:
    """Tests for table and view accessors."""

    @pytest.mark.asyncio
    async def test_table_accessor_exists(self, db):
        """Test that db.t accessor exists."""
        assert db.t is not None

    @pytest.mark.asyncio
    async def test_view_accessor_exists(self, db):
        """Test that db.v accessor exists."""
        assert db.v is not None


class TestDatabaseSessionManagement:
    """Tests for async session management."""

    @pytest.mark.asyncio
    async def test_session_commit(self, db):
        """Test that sessions commit successfully."""
        # Create a table
        await db.q("""
            CREATE TABLE test_commit (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """)

        # Insert data
        await db.q("INSERT INTO test_commit (id, value) VALUES (1, 'test')")

        # Verify data persists (was committed)
        result = await db.q("SELECT value FROM test_commit WHERE id = 1")
        assert result == [{"value": "test"}]

    @pytest.mark.asyncio
    async def test_multiple_queries_in_sequence(self, db):
        """Test executing multiple queries in sequence."""
        await db.q("CREATE TABLE seq_test (id INTEGER PRIMARY KEY, val TEXT)")
        await db.q("INSERT INTO seq_test (id, val) VALUES (1, 'a')")
        await db.q("INSERT INTO seq_test (id, val) VALUES (2, 'b')")
        result = await db.q("SELECT val FROM seq_test ORDER BY id")
        assert result == [{"val": "a"}, {"val": "b"}]
