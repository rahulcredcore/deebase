"""Tests for view support (Phase 7)."""

import pytest
from deebase import Database


class TestViewCreation:
    """Tests for db.create_view() method."""

    @pytest.mark.asyncio
    async def test_create_simple_view(self, db):
        """Test creating a simple view."""
        # Create a table first
        class User:
            id: int
            name: str
            active: bool

        users = await db.create(User, pk='id')

        # Insert some data
        await users.insert({"name": "Alice", "active": True})
        await users.insert({"name": "Bob", "active": False})
        await users.insert({"name": "Charlie", "active": True})

        # Create a view
        active_users = await db.create_view(
            "active_users",
            "SELECT * FROM user WHERE active = 1"
        )

        assert active_users is not None
        assert active_users._name == "active_users"

    @pytest.mark.asyncio
    async def test_create_view_with_joins(self, db):
        """Test creating a view with JOIN."""
        # Create tables
        class User:
            id: int
            name: str

        class Post:
            id: int
            title: str
            user_id: int

        users = await db.create(User, pk='id')
        posts = await db.create(Post, pk='id')

        # Insert data
        await users.insert({"name": "Alice"})
        await posts.insert({"title": "Post 1", "user_id": 1})

        # Create view with JOIN
        view = await db.create_view(
            "posts_with_authors",
            """
            SELECT p.id, p.title, u.name as author_name
            FROM post p
            JOIN user u ON p.user_id = u.id
            """
        )

        assert view is not None

    @pytest.mark.asyncio
    async def test_create_view_with_replace(self, db):
        """Test creating view with replace=True."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice"})

        # Create view
        view1 = await db.create_view("test_view", "SELECT * FROM user")

        # Replace it
        view2 = await db.create_view(
            "test_view",
            "SELECT name FROM user",
            replace=True
        )

        assert view2 is not None


class TestViewQuerying:
    """Tests for querying views."""

    @pytest.mark.asyncio
    async def test_select_from_view(self, db):
        """Test selecting data from a view."""
        # Create table and data
        class User:
            id: int
            name: str
            age: int

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice", "age": 30})
        await users.insert({"name": "Bob", "age": 25})
        await users.insert({"name": "Charlie", "age": 35})

        # Create view for users over 30
        older_users = await db.create_view(
            "older_users",
            "SELECT * FROM user WHERE age >= 30"
        )

        # Query the view
        results = await older_users()

        assert len(results) == 2
        names = {r['name'] for r in results}
        assert names == {"Alice", "Charlie"}

    @pytest.mark.asyncio
    async def test_get_from_view_by_pk(self, db):
        """Test getting a record from view by primary key."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        user1 = await users.insert({"name": "Alice"})
        await users.insert({"name": "Bob"})

        # Create view
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Get by PK from view
        result = await view[user1['id']]

        assert result['name'] == "Alice"

    @pytest.mark.asyncio
    async def test_lookup_in_view(self, db):
        """Test lookup operation in view."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice", "email": "alice@example.com"})

        # Create view
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Lookup in view
        result = await view.lookup(email="alice@example.com")

        assert result['name'] == "Alice"

    @pytest.mark.asyncio
    async def test_select_with_limit_from_view(self, db):
        """Test selecting with limit from view."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice"})
        await users.insert({"name": "Bob"})
        await users.insert({"name": "Charlie"})

        # Create view
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Select with limit
        results = await view(limit=2)

        assert len(results) == 2


class TestViewReadOnly:
    """Tests that views are read-only."""

    @pytest.mark.asyncio
    async def test_view_insert_raises_error(self, db):
        """Test that insert on view raises NotImplementedError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Insert should fail
        with pytest.raises(NotImplementedError, match="Cannot insert into a view"):
            await view.insert({"name": "Alice"})

    @pytest.mark.asyncio
    async def test_view_update_raises_error(self, db):
        """Test that update on view raises NotImplementedError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice"})
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Update should fail
        with pytest.raises(NotImplementedError, match="Cannot update a view"):
            await view.update({"id": 1, "name": "Bob"})

    @pytest.mark.asyncio
    async def test_view_upsert_raises_error(self, db):
        """Test that upsert on view raises NotImplementedError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Upsert should fail
        with pytest.raises(NotImplementedError, match="Cannot upsert into a view"):
            await view.upsert({"name": "Alice"})

    @pytest.mark.asyncio
    async def test_view_delete_raises_error(self, db):
        """Test that delete on view raises NotImplementedError."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice"})
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Delete should fail
        with pytest.raises(NotImplementedError, match="Cannot delete from a view"):
            await view.delete(1)


class TestViewDrop:
    """Tests for dropping views."""

    @pytest.mark.asyncio
    async def test_drop_view(self, db):
        """Test dropping a view."""
        # Create table and view
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Drop the view
        await view.drop()

        # View should be gone (can create again)
        view2 = await db.create_view("user_view", "SELECT * FROM user")
        assert view2 is not None


class TestViewAccessor:
    """Tests for ViewAccessor (db.v) access."""

    @pytest.mark.asyncio
    async def test_access_view_via_attribute(self, db):
        """Test accessing view via db.v.viewname."""
        # Create table and view
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await db.create_view("user_view", "SELECT * FROM user")

        # Access via db.v
        view = db.v.user_view

        assert view is not None
        assert view._name == "user_view"

    @pytest.mark.asyncio
    async def test_access_view_via_index(self, db):
        """Test accessing view via db.v['viewname']."""
        # Create table and view
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await db.create_view("user_view", "SELECT * FROM user")

        # Access via db.v['viewname']
        view = db.v['user_view']

        assert view is not None
        assert view._name == "user_view"

    @pytest.mark.asyncio
    async def test_access_multiple_views(self, db):
        """Test accessing multiple views at once."""
        # Create table and views
        class User:
            id: int
            name: str
            active: bool

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice", "active": True})
        await users.insert({"name": "Bob", "active": False})

        await db.create_view("active_users", "SELECT * FROM user WHERE active = 1")
        await db.create_view("inactive_users", "SELECT * FROM user WHERE active = 0")

        # Access multiple views
        active, inactive = db.v['active_users', 'inactive_users']

        assert active._name == "active_users"
        assert inactive._name == "inactive_users"

    @pytest.mark.asyncio
    async def test_view_not_found_raises_attribute_error(self, db):
        """Test that accessing non-existent view raises AttributeError."""
        # Try to access view that doesn't exist
        with pytest.raises(AttributeError) as exc_info:
            _ = db.v.nonexistent

        # Verify helpful error message
        assert "not found in cache" in str(exc_info.value)
        assert "create_view" in str(exc_info.value)


class TestViewReflection:
    """Tests for reflecting existing views."""

    @pytest.mark.asyncio
    async def test_reflect_view_created_with_sql(self, db):
        """Test reflecting a view created with raw SQL."""
        # Create table
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice"})

        # Create view with raw SQL
        await db.q("CREATE VIEW user_names AS SELECT name FROM user")

        # Reflect the view
        view = await db.reflect_view('user_names')

        assert view is not None
        assert view._name == "user_names"

        # Query it
        results = await view()
        assert len(results) == 1
        assert results[0]['name'] == "Alice"

    @pytest.mark.asyncio
    async def test_reflect_view_makes_available_via_db_v(self, db):
        """Test that reflect_view makes view available via db.v."""
        # Create table and view with SQL
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        await db.q("CREATE VIEW user_view AS SELECT * FROM user")

        # Reflect the view
        view = await db.reflect_view('user_view')

        # Now db.v.user_view works
        view_via_v = db.v.user_view
        assert view_via_v is view


class TestViewWithDataclass:
    """Tests for views with dataclass support."""

    @pytest.mark.asyncio
    async def test_view_with_dataclass(self, db):
        """Test that views work with dataclass mode."""
        # Create table
        class User:
            id: int
            name: str
            age: int

        users = await db.create(User, pk='id')
        await users.insert({"name": "Alice", "age": 30})
        await users.insert({"name": "Bob", "age": 25})

        # Create view
        view = await db.create_view("user_view", "SELECT * FROM user")

        # Enable dataclass mode
        UserViewDC = view.dataclass()

        # Query should return dataclass instances
        results = await view()

        assert len(results) == 2
        for user in results:
            assert type(user).__name__ == 'User_view'
            # Can access as dataclass
            assert hasattr(user, 'name')
            assert hasattr(user, 'age')


class TestViewsForJoins:
    """Tests demonstrating views as the solution for JOINs in DeeBase.

    Views provide an elegant way to handle JOIN queries without adding
    a join API. The database provides column metadata during reflection,
    so you get full DeeBase API support without defining a Python schema.
    """

    @pytest.mark.asyncio
    async def test_view_with_join_full_api(self, db):
        """Test that views with JOINs support the full DeeBase API."""
        # Create tables
        class Author:
            id: int
            name: str
            email: str

        class Book:
            id: int
            author_id: int
            title: str
            sales: int

        authors = await db.create(Author, pk='id')
        books = await db.create(Book, pk='id')

        # Insert data
        alice = await authors.insert({"name": "Alice", "email": "alice@example.com"})
        bob = await authors.insert({"name": "Bob", "email": "bob@example.com"})
        await books.insert({"author_id": alice['id'], "title": "Python Guide", "sales": 1000})
        await books.insert({"author_id": alice['id'], "title": "Async Patterns", "sales": 500})
        await books.insert({"author_id": bob['id'], "title": "Data Science", "sales": 2000})

        # Create view with JOIN
        book_details = await db.create_view(
            "book_details",
            """
            SELECT b.id, b.title, b.sales, a.name as author_name, a.email as author_email
            FROM book b
            JOIN author a ON b.author_id = a.id
            """
        )

        # Test select all
        all_books = await book_details()
        assert len(all_books) == 3

        # Test limit
        limited = await book_details(limit=2)
        assert len(limited) == 2

        # Test lookup
        alice_book = await book_details.lookup(author_name="Alice")
        assert alice_book['author_name'] == "Alice"

        # Test get by id (views often have id column from source)
        book = await book_details[1]
        assert book['id'] == 1

    @pytest.mark.asyncio
    async def test_view_join_dataclass_type_safety(self, db):
        """Test that views with JOINs support dataclass generation for type safety."""
        # Create tables
        class User:
            id: int
            name: str

        class Post:
            id: int
            user_id: int
            title: str
            views: int

        users = await db.create(User, pk='id')
        posts = await db.create(Post, pk='id')

        # Insert data
        user = await users.insert({"name": "Alice"})
        await posts.insert({"user_id": user['id'], "title": "Hello World", "views": 100})

        # Create view with JOIN
        await db.create_view(
            "posts_with_authors",
            """
            SELECT p.id, p.title, p.views, u.name as author_name
            FROM post p JOIN user u ON p.user_id = u.id
            """
        )

        # Access via db.v and generate dataclass
        view = db.v.posts_with_authors
        PostAuthorDC = view.dataclass()

        # Query returns dataclass instances
        results = await view()
        assert len(results) == 1
        post = results[0]

        # Type-safe field access
        assert post.title == "Hello World"
        assert post.author_name == "Alice"
        assert post.views == 100
        assert hasattr(post, 'id')

    @pytest.mark.asyncio
    async def test_view_aggregation_query(self, db):
        """Test views for aggregation queries (GROUP BY, SUM, COUNT)."""
        # Create tables
        class Category:
            id: int
            name: str

        class Product:
            id: int
            category_id: int
            price: float

        categories = await db.create(Category, pk='id')
        products = await db.create(Product, pk='id')

        # Insert data
        tech = await categories.insert({"name": "Technology"})
        books = await categories.insert({"name": "Books"})
        await products.insert({"category_id": tech['id'], "price": 99.99})
        await products.insert({"category_id": tech['id'], "price": 149.99})
        await products.insert({"category_id": books['id'], "price": 29.99})

        # Create aggregation view
        await db.create_view(
            "category_stats",
            """
            SELECT
                c.id,
                c.name as category_name,
                COUNT(p.id) as product_count,
                COALESCE(SUM(p.price), 0) as total_value,
                COALESCE(AVG(p.price), 0) as avg_price
            FROM category c
            LEFT JOIN product p ON c.id = p.category_id
            GROUP BY c.id, c.name
            """
        )

        # Query the aggregation view
        stats = await db.v.category_stats()
        assert len(stats) == 2

        # Find technology stats
        tech_stats = next(s for s in stats if s['category_name'] == "Technology")
        assert tech_stats['product_count'] == 2
        assert tech_stats['total_value'] == pytest.approx(249.98, rel=0.01)

        # Find books stats
        books_stats = next(s for s in stats if s['category_name'] == "Books")
        assert books_stats['product_count'] == 1
        assert books_stats['total_value'] == pytest.approx(29.99, rel=0.01)

    @pytest.mark.asyncio
    async def test_view_xtra_filtering(self, db):
        """Test that xtra() works with views for additional filtering."""
        # Create tables
        class User:
            id: int
            name: str
            role: str

        class Task:
            id: int
            user_id: int
            title: str
            status: str

        users = await db.create(User, pk='id')
        tasks = await db.create(Task, pk='id')

        # Insert data
        alice = await users.insert({"name": "Alice", "role": "admin"})
        bob = await users.insert({"name": "Bob", "role": "user"})
        await tasks.insert({"user_id": alice['id'], "title": "Task 1", "status": "done"})
        await tasks.insert({"user_id": alice['id'], "title": "Task 2", "status": "pending"})
        await tasks.insert({"user_id": bob['id'], "title": "Task 3", "status": "done"})

        # Create view with JOIN
        await db.create_view(
            "task_details",
            """
            SELECT t.id, t.title, t.status, u.name as assignee, u.role
            FROM task t JOIN user u ON t.user_id = u.id
            """
        )

        view = db.v.task_details

        # Use xtra to filter
        done_tasks = view.xtra(status="done")
        results = await done_tasks()
        assert len(results) == 2
        assert all(r['status'] == "done" for r in results)

        # Filter by assignee
        alice_tasks = view.xtra(assignee="Alice")
        results = await alice_tasks()
        assert len(results) == 2
        assert all(r['assignee'] == "Alice" for r in results)

    @pytest.mark.asyncio
    async def test_view_no_python_class_needed(self, db):
        """Test that views work without a Python class - schema from database."""
        # Create table with raw SQL
        await db.q("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                price REAL
            )
        """)
        await db.q("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                quantity INTEGER
            )
        """)

        # Insert data
        await db.q("INSERT INTO products (id, name, price) VALUES (1, 'Widget', 9.99)")
        await db.q("INSERT INTO orders (id, product_id, quantity) VALUES (1, 1, 5)")

        # Create view with JOIN - no Python class needed!
        await db.q("""
            CREATE VIEW order_details AS
            SELECT o.id, o.quantity, p.name as product_name, p.price,
                   (o.quantity * p.price) as total
            FROM orders o JOIN products p ON o.product_id = p.id
        """)

        # Reflect the view - DeeBase discovers columns from database
        view = await db.reflect_view('order_details')

        # Full API works
        results = await view()
        assert len(results) == 1
        assert results[0]['product_name'] == "Widget"
        assert results[0]['quantity'] == 5
        assert results[0]['total'] == pytest.approx(49.95, rel=0.01)

        # Dataclass generation works too
        OrderDetailDC = view.dataclass()
        typed_results = await view()
        assert typed_results[0].product_name == "Widget"
