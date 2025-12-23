"""Tests for dataclass support (Phase 4)."""

import pytest
from dataclasses import dataclass, fields, is_dataclass
from typing import Optional
from datetime import datetime
from deebase import Database, Text


class TestDataclassGeneration:
    """Tests for Table.dataclass() method."""

    @pytest.mark.asyncio
    async def test_dataclass_method_generates_dataclass(self, db):
        """Test that .dataclass() generates a dataclass from table metadata."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Call .dataclass() to generate dataclass
        UserDC = users.dataclass()

        # Verify it's a dataclass
        assert is_dataclass(UserDC)

        # Verify it has the correct fields
        field_names = {f.name for f in fields(UserDC)}
        assert field_names == {'id', 'name', 'email'}

    @pytest.mark.asyncio
    async def test_dataclass_fields_are_optional(self, db):
        """Test that generated dataclass fields are Optional (for auto-generated values)."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')
        UserDC = users.dataclass()

        # All fields should be Optional (default None) to handle auto-increment
        dc_fields = fields(UserDC)
        for field in dc_fields:
            # Check that default is None
            assert field.default is None

    @pytest.mark.asyncio
    async def test_dataclass_cached_on_table(self, db):
        """Test that dataclass is cached on Table instance."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Call .dataclass() twice
        UserDC1 = users.dataclass()
        UserDC2 = users.dataclass()

        # Should return the same class
        assert UserDC1 is UserDC2


class TestCRUDWithDataclasses:
    """Tests for CRUD operations returning dataclass instances."""

    @pytest.mark.asyncio
    async def test_insert_returns_dataclass_after_dataclass_call(self, db):
        """Test that insert returns dataclass instance after calling .dataclass()."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        # Enable dataclass mode
        UserDC = users.dataclass()

        # Insert should return dataclass instance
        user = await users.insert({"name": "Alice", "email": "alice@example.com"})

        # Verify it's a dataclass instance
        assert is_dataclass(user)
        assert isinstance(user, UserDC)
        assert user.name == "Alice"
        assert user.email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_select_returns_dataclasses(self, db):
        """Test that select operations return dataclass instances."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert some records (returns dicts initially)
        await users.insert({"name": "Alice"})
        await users.insert({"name": "Bob"})

        # Enable dataclass mode
        UserDC = users.dataclass()

        # Select all should return dataclass instances
        all_users = await users()

        assert len(all_users) == 2
        for user in all_users:
            assert is_dataclass(user)
            assert isinstance(user, UserDC)

    @pytest.mark.asyncio
    async def test_get_by_pk_returns_dataclass(self, db):
        """Test that get by PK returns dataclass instance."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        inserted = await users.insert({"name": "Alice"})
        user_id = inserted['id']

        # Enable dataclass mode
        UserDC = users.dataclass()

        # Get by PK should return dataclass
        user = await users[user_id]

        assert is_dataclass(user)
        assert isinstance(user, UserDC)
        assert user.id == user_id
        assert user.name == "Alice"

    @pytest.mark.asyncio
    async def test_lookup_returns_dataclass(self, db):
        """Test that lookup returns dataclass instance."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')

        await users.insert({"name": "Alice", "email": "alice@example.com"})

        # Enable dataclass mode
        UserDC = users.dataclass()

        # Lookup should return dataclass
        user = await users.lookup(email="alice@example.com")

        assert is_dataclass(user)
        assert isinstance(user, UserDC)
        assert user.name == "Alice"

    @pytest.mark.asyncio
    async def test_update_returns_dataclass(self, db):
        """Test that update returns dataclass instance."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        inserted = await users.insert({"name": "Alice"})

        # Enable dataclass mode
        UserDC = users.dataclass()

        # Update should return dataclass
        updated = await users.update({"id": inserted['id'], "name": "Alice Smith"})

        assert is_dataclass(updated)
        assert isinstance(updated, UserDC)
        assert updated.name == "Alice Smith"

    @pytest.mark.asyncio
    async def test_upsert_returns_dataclass(self, db):
        """Test that upsert returns dataclass instance."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Enable dataclass mode
        UserDC = users.dataclass()

        # Upsert (insert) should return dataclass
        user = await users.upsert({"name": "Alice"})

        assert is_dataclass(user)
        assert isinstance(user, UserDC)


class TestActualDataclass:
    """Tests for using actual @dataclass decorated classes."""

    @pytest.mark.asyncio
    async def test_create_with_actual_dataclass(self, db):
        """Test creating table with actual @dataclass."""
        @dataclass
        class User:
            id: Optional[int] = None
            name: str = ""
            email: str = ""

        users = await db.create(User, pk='id')

        # Should recognize it as a dataclass
        assert users._dataclass_cls is User
        assert is_dataclass(users._dataclass_cls)

    @pytest.mark.asyncio
    async def test_crud_with_actual_dataclass(self, db):
        """Test CRUD operations with actual @dataclass."""
        @dataclass
        class User:
            id: Optional[int] = None
            name: str = ""
            email: str = ""

        users = await db.create(User, pk='id')

        # Insert with dataclass instance
        user = await users.insert(User(name="Alice", email="alice@example.com"))

        # Should return dataclass instance
        assert is_dataclass(user)
        assert isinstance(user, User)
        assert user.name == "Alice"
        assert user.email == "alice@example.com"

        # Select should return dataclass instances
        all_users = await users()
        assert len(all_users) == 1
        assert is_dataclass(all_users[0])
        assert isinstance(all_users[0], User)


class TestMixedInputs:
    """Tests for mixing dict and dataclass inputs."""

    @pytest.mark.asyncio
    async def test_insert_dict_then_dataclass(self, db):
        """Test inserting with dict then with dataclass."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        UserDC = users.dataclass()

        # Insert with dict
        user1 = await users.insert({"name": "Alice"})
        assert is_dataclass(user1)

        # Insert with dataclass instance
        user2 = await users.insert(UserDC(id=None, name="Bob"))
        assert is_dataclass(user2)
        assert user2.name == "Bob"

    @pytest.mark.asyncio
    async def test_update_with_dataclass_instance(self, db):
        """Test updating with dataclass instance."""
        class User:
            id: int
            name: str
            email: str

        users = await db.create(User, pk='id')
        UserDC = users.dataclass()

        # Insert with dict
        user = await users.insert({"name": "Alice", "email": "alice@example.com"})

        # Update with dataclass instance
        user.name = "Alice Smith"
        updated = await users.update(user)

        assert is_dataclass(updated)
        assert updated.name == "Alice Smith"

    @pytest.mark.asyncio
    async def test_update_with_dict_when_dataclass_enabled(self, db):
        """Test updating with dict when dataclass mode is enabled."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')
        UserDC = users.dataclass()

        # Insert
        user = await users.insert({"name": "Alice"})

        # Update with dict (should still work)
        updated = await users.update({"id": user.id, "name": "Alice Smith"})

        # Should return dataclass
        assert is_dataclass(updated)
        assert updated.name == "Alice Smith"


class TestDataclassWithRichTypes:
    """Tests for dataclass with rich types (Text, JSON, datetime)."""

    @pytest.mark.asyncio
    async def test_dataclass_with_text_type(self, db):
        """Test dataclass generation with Text type."""
        class Article:
            id: int
            title: str
            content: Text

        articles = await db.create(Article, pk='id')
        ArticleDC = articles.dataclass()

        # Insert and verify
        article = await articles.insert({
            "title": "Test",
            "content": "A" * 1000
        })

        assert is_dataclass(article)
        assert article.title == "Test"
        assert len(article.content) == 1000

    @pytest.mark.asyncio
    async def test_dataclass_with_json_type(self, db):
        """Test dataclass generation with JSON (dict) type."""
        class Post:
            id: int
            title: str
            metadata: dict

        posts = await db.create(Post, pk='id')
        PostDC = posts.dataclass()

        # Insert and verify
        post = await posts.insert({
            "title": "Test",
            "metadata": {"author": "Alice", "tags": ["test"]}
        })

        assert is_dataclass(post)
        assert post.metadata['author'] == "Alice"
        assert post.metadata['tags'] == ["test"]

    @pytest.mark.asyncio
    async def test_dataclass_with_datetime(self, db):
        """Test dataclass generation with datetime type."""
        class Event:
            id: int
            name: str
            created_at: datetime

        events = await db.create(Event, pk='id')
        EventDC = events.dataclass()

        # Insert and verify
        now = datetime.now()
        event = await events.insert({
            "name": "Test Event",
            "created_at": now
        })

        assert is_dataclass(event)
        assert event.name == "Test Event"
        assert event.created_at is not None


class TestDataclassBeforeAndAfter:
    """Tests for behavior before and after calling .dataclass()."""

    @pytest.mark.asyncio
    async def test_returns_dict_before_dataclass_call(self, db):
        """Test that operations return dicts before calling .dataclass()."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert should return dict (User is not a @dataclass)
        user = await users.insert({"name": "Alice"})

        assert isinstance(user, dict)
        assert not is_dataclass(user)

    @pytest.mark.asyncio
    async def test_returns_dataclass_after_dataclass_call(self, db):
        """Test that operations return dataclasses after calling .dataclass()."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Call .dataclass() to enable dataclass mode
        UserDC = users.dataclass()

        # Insert should return dataclass instance
        user = await users.insert({"name": "Alice"})

        assert is_dataclass(user)
        assert isinstance(user, UserDC)

    @pytest.mark.asyncio
    async def test_existing_records_returned_as_dataclass(self, db):
        """Test that existing records are returned as dataclasses after .dataclass() call."""
        class User:
            id: int
            name: str

        users = await db.create(User, pk='id')

        # Insert records before enabling dataclass mode
        await users.insert({"name": "Alice"})
        await users.insert({"name": "Bob"})

        # Enable dataclass mode
        UserDC = users.dataclass()

        # Fetch existing records - should be returned as dataclasses
        all_users = await users()

        assert len(all_users) == 2
        for user in all_users:
            assert is_dataclass(user)
            assert isinstance(user, UserDC)
