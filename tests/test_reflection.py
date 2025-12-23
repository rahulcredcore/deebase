"""Tests for table reflection (Phase 5)."""

import pytest
from deebase import Database


class TestReflectAll:
    """Tests for db.reflect() method."""

    @pytest.mark.asyncio
    async def test_reflect_tables_created_with_raw_sql(self, db):
        """Test reflecting tables created with raw SQL."""
        # Create tables with raw SQL
        await db.q("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT
            )
        """)
        await db.q("""
            CREATE TABLE posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                user_id INTEGER
            )
        """)

        # Reflect all tables
        await db.reflect()

        # Now we can access them via db.t
        users = db.t.users
        posts = db.t.posts

        assert users is not None
        assert posts is not None
        assert users._name == 'users'
        assert posts._name == 'posts'

    @pytest.mark.asyncio
    async def test_reflect_preserves_schema(self, db):
        """Test that reflection correctly captures table schema."""
        # Create table with specific schema
        await db.q("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL,
                stock INTEGER
            )
        """)

        # Reflect
        await db.reflect()

        # Access reflected table
        products = db.t.products

        # Verify columns exist
        assert 'id' in products.sa_table.c
        assert 'name' in products.sa_table.c
        assert 'price' in products.sa_table.c
        assert 'stock' in products.sa_table.c

        # Verify primary key
        pk_cols = list(products.sa_table.primary_key.columns)
        assert len(pk_cols) == 1
        assert pk_cols[0].name == 'id'

    @pytest.mark.asyncio
    async def test_reflect_skips_already_cached_tables(self, db):
        """Test that reflection doesn't overwrite cached tables."""
        # Create table via db.create()
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        original_table = users

        # Create another table with raw SQL
        await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT)")

        # Reflect - should skip 'user' (already cached), add 'posts'
        await db.reflect()

        # Verify original table is unchanged
        users_from_cache = db.t.user
        assert users_from_cache is original_table

        # Verify posts was added
        posts = db.t.posts
        assert posts is not None

    @pytest.mark.asyncio
    async def test_reflect_empty_database(self, db):
        """Test reflecting an empty database."""
        # Reflect empty database (should not error)
        await db.reflect()

        # No tables should be cached (except any from fixtures)
        # This should just work without errors


class TestReflectTable:
    """Tests for db.reflect_table() method."""

    @pytest.mark.asyncio
    async def test_reflect_single_table(self, db):
        """Test reflecting a single table."""
        # Create table with raw SQL
        await db.q("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                price REAL
            )
        """)

        # Reflect just this table
        products = await db.reflect_table('products')

        assert products is not None
        assert products._name == 'products'
        assert 'name' in products.sa_table.c
        assert 'price' in products.sa_table.c

    @pytest.mark.asyncio
    async def test_reflect_table_returns_cached_if_exists(self, db):
        """Test that reflect_table returns cached table if already reflected."""
        # Create and cache a table
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Reflect the same table (should return cached)
        reflected = await db.reflect_table('user')

        assert reflected is users  # Same instance

    @pytest.mark.asyncio
    async def test_reflect_table_makes_available_via_db_t(self, db):
        """Test that reflect_table makes table available via db.t."""
        # Create table with raw SQL
        await db.q("CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)")

        # Reflect it
        orders = await db.reflect_table('orders')

        # Now db.t.orders works
        orders_via_t = db.t.orders
        assert orders_via_t is orders  # Same instance


class TestTableAccessor:
    """Tests for TableAccessor (db.t) cache-only access."""

    @pytest.mark.asyncio
    async def test_access_table_via_attribute(self, db):
        """Test accessing table via db.t.tablename."""
        # Create table
        class User:
            id: int
            name: str

        await db.create(User, pk='id')

        # Access via db.t (already cached from db.create)
        users = db.t.user
        assert users is not None
        assert users._name == 'user'

    @pytest.mark.asyncio
    async def test_access_table_via_index(self, db):
        """Test accessing table via db.t['tablename']."""
        # Create table
        class User:
            id: int
            name: str

        await db.create(User, pk='id')

        # Access via db.t['user']
        users = db.t['user']
        assert users is not None
        assert users._name == 'user'

    @pytest.mark.asyncio
    async def test_access_multiple_tables(self, db):
        """Test accessing multiple tables at once."""
        # Create tables
        class User:
            id: int
            name: str

        class Post:
            id: int
            title: str

        await db.create(User, pk='id')
        await db.create(Post, pk='id')

        # Access multiple tables
        users, posts = db.t['user', 'post']

        assert users._name == 'user'
        assert posts._name == 'post'

    @pytest.mark.asyncio
    async def test_table_not_found_raises_attribute_error(self, db):
        """Test that accessing non-existent table raises AttributeError."""
        # Try to access table that doesn't exist and isn't cached
        with pytest.raises(AttributeError) as exc_info:
            _ = db.t.nonexistent

        # Verify helpful error message
        assert "not found in cache" in str(exc_info.value)
        assert "db.reflect()" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_table_not_found_in_index_access(self, db):
        """Test that accessing non-existent table via index raises AttributeError."""
        with pytest.raises(AttributeError) as exc_info:
            _ = db.t['nonexistent']

        assert "not found in cache" in str(exc_info.value)


class TestReflectionWorkflow:
    """Tests for complete reflection workflows."""

    @pytest.mark.asyncio
    async def test_reflect_then_access_workflow(self, db):
        """Test typical workflow: create with SQL, reflect, then access."""
        # Step 1: Create tables with raw SQL (like loading existing database)
        await db.q("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
        await db.q("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL)")

        # Step 2: Reflect to load schemas
        await db.reflect()

        # Step 3: Access via db.t (sync, fast)
        customers = db.t.customers
        orders = db.t.orders

        # Step 4: Use CRUD operations
        customer = await customers.insert({"name": "Alice"})
        order = await orders.insert({"customer_id": customer['id'], "total": 99.99})

        assert customer['id'] is not None
        assert order['customer_id'] == customer['id']

    @pytest.mark.asyncio
    async def test_create_during_session_then_reflect_table(self, db):
        """Test creating table during session and reflecting it."""
        # Start with some tables
        class User:
            id: int
            name: str

        await db.create(User, pk='id')

        # Later, create table with raw SQL
        await db.q("CREATE TABLE temp (id INTEGER PRIMARY KEY, value TEXT)")

        # Reflect just this new table
        temp = await db.reflect_table('temp')

        # Now db.t.temp works
        temp_via_t = db.t.temp
        assert temp_via_t is temp

        # CRUD works
        row = await temp.insert({"value": "test"})
        assert row['value'] == "test"

    @pytest.mark.asyncio
    async def test_reflect_after_create_combines_both(self, db):
        """Test that reflect() works alongside db.create()."""
        # Create one table via db.create()
        class User:
            id: int
            name: str

        users_created = await db.create(User, pk='id')

        # Create another with raw SQL
        await db.q("CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT)")

        # Reflect all
        await db.reflect()

        # Both accessible via db.t
        users = db.t.user
        posts = db.t.posts

        # db.create() table is the same instance
        assert users is users_created

        # Raw SQL table is newly reflected
        assert posts is not None

    @pytest.mark.asyncio
    async def test_crud_on_reflected_tables(self, db):
        """Test that CRUD operations work on reflected tables."""
        # Create table with raw SQL
        await db.q("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0
            )
        """)

        # Reflect it
        await db.reflect()

        # Access via db.t
        tasks = db.t.tasks

        # CRUD operations should work
        task = await tasks.insert({"title": "Learn DeeBase", "completed": False})
        assert task['id'] is not None

        all_tasks = await tasks()
        assert len(all_tasks) == 1

        fetched = await tasks[task['id']]
        assert fetched['title'] == "Learn DeeBase"

        await tasks.update({"id": task['id'], "title": "Learn DeeBase", "completed": True})
        await tasks.delete(task['id'])

        remaining = await tasks()
        assert len(remaining) == 0
