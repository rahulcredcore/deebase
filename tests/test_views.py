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
